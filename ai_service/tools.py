"""Small, dependency-free tool framework and deterministic fashion tools."""

from __future__ import annotations

import hashlib
import inspect
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol, get_type_hints

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class SearchRuntimeProtocol(Protocol):
    metadata: list[dict[str, Any]]

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]: ...


class ToolError(Exception):
    """Base class for errors intentionally exposed by the tool boundary."""

    error_type = "execution_error"


class UnknownToolError(ToolError):
    error_type = "unknown_tool"


class ToolValidationError(ToolError):
    error_type = "validation_error"

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.details = details or []


@dataclass(frozen=True)
class ToolContext:
    runtime: SearchRuntimeProtocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolDefinition:
    spec: ToolSpec
    input_model: type[BaseModel]
    handler: Callable[[BaseModel, ToolContext], Any]


def _model_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema_method = getattr(model, "model_json_schema", None)
    return schema_method() if schema_method else model.schema()


def _validate(model: type[BaseModel], arguments: dict[str, Any]) -> BaseModel:
    validate_method = getattr(model, "model_validate", None)
    return validate_method(arguments) if validate_method else model.parse_obj(arguments)


def tool(
    *, name: str | None = None, description: str | None = None
) -> Callable[[Callable[[BaseModel, ToolContext], Any]], ToolDefinition]:
    """Turn a typed function into a tool definition with generated JSON schema."""

    def decorate(handler: Callable[[BaseModel, ToolContext], Any]) -> ToolDefinition:
        parameters = list(inspect.signature(handler).parameters.values())
        hints = get_type_hints(handler)
        input_model = hints.get(parameters[0].name) if parameters else None
        if not inspect.isclass(input_model) or not issubclass(
            input_model, BaseModel
        ):
            raise TypeError("A tool handler's first parameter must be a Pydantic model")
        resolved_description = description or inspect.getdoc(handler)
        if not resolved_description:
            raise ValueError("Tool description is required")
        return ToolDefinition(
            spec=ToolSpec(
                name=name or handler.__name__,
                description=resolved_description,
                input_schema=_model_schema(input_model),
            ),
            input_model=input_model,
            handler=handler,
        )

    return decorate


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.spec.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.spec.name}")
        self._tools[definition.spec.name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise UnknownToolError(f"Unknown tool: {name}") from exc

    def list_specs(self) -> list[ToolSpec]:
        return [self._tools[name].spec for name in sorted(self._tools)]

    def invoke(
        self, name: str, arguments: dict[str, Any], context: ToolContext
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            definition = self.get(name)
            parsed = _validate(definition.input_model, arguments)
            data = definition.handler(parsed, context)
            count = len(data) if isinstance(data, list) else data.get("result_count") if isinstance(data, dict) else None
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info("tool_invoked tool=%s elapsed_ms=%s result_count=%s", name, elapsed_ms, count)
            return {"success": True, "tool": name, "data": data, "error": None}
        except ValidationError as exc:
            details = [
                {key: item[key] for key in ("type", "loc", "msg", "input") if key in item}
                for item in exc.errors()
            ]
            error = ToolValidationError("Invalid tool arguments", details)
            self._log_error(name, started, error.error_type)
            raise error from exc
        except ToolError as exc:
            self._log_error(name, started, exc.error_type)
            raise
        except Exception as exc:
            self._log_error(name, started, "execution_error")
            raise ToolError("Tool execution failed") from exc

    @staticmethod
    def _log_error(name: str, started: float, error_type: str) -> None:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.warning("tool_failed tool=%s elapsed_ms=%s error_type=%s", name, elapsed_ms, error_type)


class SemanticSearchInput(BaseModel):
    query: str = Field(min_length=1, description="Natural-language fashion query")
    top_k: int = Field(default=10, gt=0, le=100)


class CategoryFilterInput(BaseModel):
    candidates: list[dict[str, Any]]
    category: str = Field(min_length=1)


class PriceFilterInput(BaseModel):
    candidates: list[dict[str, Any]]
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    demo_mode: bool = False


class BuildOutfitInput(BaseModel):
    candidates: list[dict[str, Any]]
    categories: list[str] = Field(min_length=1)


@tool(description="Search the persistent semantic fashion index.")
def semantic_search(args: SemanticSearchInput, context: ToolContext) -> list[dict[str, Any]]:
    return context.runtime.search(args.query, args.top_k)


def _category(record: dict[str, Any]) -> str:
    for key in ("category", "product_type", "clothes_type", "description"):
        value = record.get(key)
        if value:
            return str(value).strip().casefold()
    return ""


@tool(description="Filter candidate fashion records by category.")
def filter_by_category(args: CategoryFilterInput, context: ToolContext) -> list[dict[str, Any]]:
    del context
    wanted = args.category.strip().casefold()
    return [record for record in args.candidates if wanted in _category(record)]


def _demo_price(record: dict[str, Any]) -> float:
    stable_id = str(record.get("item_id") or record.get("image_path") or "unknown")
    bucket = int(hashlib.sha256(stable_id.encode()).hexdigest()[:8], 16) % 181
    return float(20 + bucket)


@tool(description="Filter candidates by real price, or explicit deterministic demo prices.")
def filter_by_price(args: PriceFilterInput, context: ToolContext) -> dict[str, Any]:
    del context
    if args.min_price is not None and args.max_price is not None and args.min_price > args.max_price:
        raise ToolValidationError("min_price must not exceed max_price")
    priced: list[dict[str, Any]] = []
    for record in args.candidates:
        price = record.get("price")
        if price in (None, ""):
            if not args.demo_mode:
                continue
            price = _demo_price(record)
            record = {**record, "price": price, "price_source": "synthetic_demo"}
        try:
            numeric_price = float(price)
        except (TypeError, ValueError):
            continue
        if (args.min_price is None or numeric_price >= args.min_price) and (
            args.max_price is None or numeric_price <= args.max_price
        ):
            priced.append(record)
    unsupported = not args.demo_mode and bool(args.candidates) and not any(
        record.get("price") not in (None, "") for record in args.candidates
    )
    return {
        "status": "unsupported" if unsupported else "ok",
        "reason": "candidate records have no price field" if unsupported else None,
        "items": priced,
        "result_count": len(priced),
    }


@tool(description="Build a deterministic outfit with the first matching item per requested category.")
def build_outfit(args: BuildOutfitInput, context: ToolContext) -> dict[str, Any]:
    del context
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    used: set[str] = set()
    for requested in args.categories:
        wanted = requested.strip().casefold()
        match = next(
            (record for record in args.candidates if wanted in _category(record) and str(record.get("item_id", id(record))) not in used),
            None,
        )
        if match is None:
            missing.append(requested)
        else:
            selected.append(match)
            used.add(str(match.get("item_id", id(match))))
    return {"items": selected, "missing_categories": missing, "complete": not missing, "result_count": len(selected)}


def create_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for definition in (semantic_search, filter_by_category, filter_by_price, build_outfit):
        registry.register(definition)
    return registry
