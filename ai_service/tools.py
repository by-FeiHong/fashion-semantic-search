"""Small, dependency-free tool framework and deterministic fashion tools."""

from __future__ import annotations

import hashlib
import inspect
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Protocol, get_type_hints

from pydantic import BaseModel, Field, ValidationError

from ai_service.weather import WeatherProvider, WeatherProviderError

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
    weather_provider: WeatherProvider | None = None


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
    constraints: dict[str, Any] = Field(default_factory=dict)
    query: str | None = None
    demo_mode: bool = False
    weather_context: dict[str, Any] | None = None
    derived_from_weather: list[dict[str, Any]] = Field(default_factory=list)


class WeatherLookupInput(BaseModel):
    location: str = Field(min_length=1)
    date: str | None = None
    date_offset: int | None = Field(default=None, ge=0, le=14)


@tool(description="Look up normalized weather for a location and date through the configured provider.")
def weather_lookup(args: WeatherLookupInput, context: ToolContext) -> dict[str, Any]:
    if context.weather_provider is None:
        raise WeatherProviderError("Weather provider is unavailable")
    try:
        target = date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=args.date_offset or 0)
    except ValueError as exc:
        raise ToolValidationError("date must use YYYY-MM-DD") from exc
    try:
        values = context.weather_provider.lookup(location=args.location.strip(), target_date=target)
    except WeatherProviderError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "location": args.location.strip(), "date": target.isoformat(),
        "temperature": values.get("temperature"), "feels_like": values.get("feels_like"),
        "precipitation": values.get("precipitation"), "rain": values.get("rain"),
        "wind": values.get("wind"), "condition": values.get("condition"),
        "source": values.get("source", "weather_provider"),
        "provider": values.get("provider", context.weather_provider.name),
        "result_count": 1,
    }


class OutfitItem(BaseModel):
    requested_category: str
    matched_category: str
    item: dict[str, Any]
    score: float
    score_components: dict[str, float]
    unsupported_constraints: list[str] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    selected_items: list[OutfitItem]
    missing_categories: list[str]
    substitutions: dict[str, str] = Field(default_factory=dict)
    constraint_summary: dict[str, Any]
    score_summary: dict[str, Any]
    recommendation_reason: str = ""
    complete: bool
    result_count: int


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


_CATEGORY_ALIASES = {
    "top": ("top", "shirt", "blouse", "tee", "sweater"), "bottom": ("bottom", "pants", "trousers", "jeans", "skirt", "shorts"),
    "shoes": ("shoe", "shoes", "sneaker", "boot", "loafer", "sandal"), "outerwear": ("outerwear", "coat", "jacket", "blazer"),
    "dress": ("dress",), "bag": ("bag", "handbag", "backpack"),
}
_SUBSTITUTES = {"top": ("dress",), "bottom": ("dress",), "outerwear": ("top",), "shoes": (), "bag": ()}


def _field_text(record: dict[str, Any], names: tuple[str, ...]) -> str:
    return " ".join(str(record.get(name, "")) for name in names).casefold()


def _canonical_category(record: dict[str, Any]) -> str:
    value = _category(record)
    return next((canonical for canonical, aliases in _CATEGORY_ALIASES.items() if any(alias in value for alias in aliases)), value)


def _semantic_score(record: dict[str, Any]) -> float:
    try:
        return max(0.0, min(1.0, float(record.get("score", record.get("semantic_score", 0.0)))))
    except (TypeError, ValueError):
        return 0.0


@tool(description="Build a deterministic, constraint-aware and scored outfit by requested category.")
def build_outfit(args: BuildOutfitInput, context: ToolContext) -> dict[str, Any]:
    del context
    selected: list[OutfitItem] = []
    missing: list[str] = []
    substitutions: dict[str, str] = {}
    used: set[str] = set()
    constraints = {key: value for key, value in args.constraints.items() if value not in (None, [], "") and key not in {"source", "location", "date", "date_offset", "weather_intent"}}
    candidates = list(args.candidates)
    budget = float(constraints["budget"]) if "budget" in constraints else None
    real_prices_available = bool(candidates) and all(record.get("price") not in (None, "") for record in candidates)
    budget_supported = budget is not None and (args.demo_mode or real_prices_available)
    if budget_supported and args.demo_mode:
        candidates = [{**record, "price": record.get("price") or _demo_price(record),
                       "price_source": "real" if record.get("price") not in (None, "") else "synthetic_demo"} for record in candidates]
    remaining_budget = budget
    supported: set[str] = set()
    unsupported: set[str] = set()

    def rank(record: dict[str, Any], requested: str, matched: str) -> tuple[float, dict[str, float], list[str]]:
        components = {"semantic": round(_semantic_score(record) * 0.45, 4), "category": 0.25 if requested == matched else 0.12}
        item_unsupported: list[str] = []
        fields = {"colors": ("color", "colors", "description", "name"), "style": ("style", "description", "name"),
                  "season": ("season", "description", "name"), "occasion": ("occasion", "description", "name")}
        for key, names in fields.items():
            wanted = constraints.get(key)
            if not wanted:
                continue
            explicit = _field_text(record, names)
            values = wanted if isinstance(wanted, list) else [wanted]
            if not explicit.strip():
                item_unsupported.append(key)
                unsupported.add(key)
                components[key] = 0.0
            else:
                supported.add(key)
                components[key] = round(0.075 * sum(str(v).casefold() in explicit for v in values) / len(values), 4)
        return round(sum(components.values()), 4), components, item_unsupported

    for requested in args.categories:
        wanted = requested.strip().casefold()
        pool = [(record, _canonical_category(record)) for record in candidates if str(record.get("item_id", record.get("image_path", id(record)))) not in used]
        if budget_supported and remaining_budget is not None:
            pool = [(record, category) for record, category in pool if float(record["price"]) <= remaining_budget]
        matches = [(record, category) for record, category in pool if category == wanted]
        if not matches:
            matches = [(record, category) for record, category in pool if category in _SUBSTITUTES.get(wanted, ())]
        if not matches:
            missing.append(requested)
        else:
            ranked = [(rank(record, wanted, category), record, category) for record, category in matches]
            (score, components, item_unsupported), match, matched_category = sorted(ranked, key=lambda row: (-row[0][0], str(row[1].get("item_id", row[1].get("image_path", "")))))[0]
            if matched_category != wanted:
                substitutions[requested] = matched_category
            selected.append(OutfitItem(requested_category=requested, matched_category=matched_category, item=match,
                                       score=score, score_components=components, unsupported_constraints=item_unsupported))
            used.add(str(match.get("item_id", match.get("image_path", id(match)))))
            if budget_supported and remaining_budget is not None:
                remaining_budget -= float(match["price"])
    if "budget" in constraints:
        if budget_supported:
            supported.add("budget")
        else:
            unsupported.add("budget")
    scores = [item.score for item in selected]
    result = RecommendationResult(selected_items=selected, missing_categories=missing, substitutions=substitutions,
        constraint_summary={"requested": constraints, "supported": sorted(supported), "unsupported": sorted(unsupported),
                            "derived_from_weather": args.derived_from_weather},
        score_summary={"overall": round(sum(scores) / len(scores), 4) if scores else 0.0, "item_scores": scores,
                       "total_price": round((budget - remaining_budget), 2) if budget_supported and budget is not None and remaining_budget is not None else None,
                       "method": "deterministic_weighted_v1"}, complete=not missing, result_count=len(selected))
    data = _validate_dump(result)
    data["items"] = [item["item"] for item in data["selected_items"]]
    return data


def _validate_dump(model: BaseModel) -> dict[str, Any]:
    dumper = getattr(model, "model_dump", None)
    return dumper() if dumper else model.dict()


def create_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for definition in (semantic_search, filter_by_category, filter_by_price, weather_lookup, build_outfit):
        registry.register(definition)
    return registry
