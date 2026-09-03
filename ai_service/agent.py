"""Single-agent planning and bounded deterministic tool orchestration."""

from __future__ import annotations

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from ai_service.llm import LLMProvider, LLMProviderError
from ai_service.tools import ToolContext, ToolError, ToolRegistry


class ToolCall(BaseModel):
    tool: Literal["semantic_search", "filter_by_category", "filter_by_price", "build_outfit"]
    arguments: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    intent: str = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(min_length=1)


def _validate_plan(payload: dict[str, Any]) -> Plan:
    validator = getattr(Plan, "model_validate", None)
    return validator(payload) if validator else Plan.parse_obj(payload)


def _dump(model: BaseModel) -> dict[str, Any]:
    dumper = getattr(model, "model_dump", None)
    return dumper() if dumper else model.dict()


class Planner:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def plan(self, query: str) -> tuple[Plan, bool, str | None]:
        try:
            payload = self.provider.complete_json(
                system_prompt=(
                    "Return only a JSON object with intent, constraints and tool_calls. "
                    "Each tool call has tool and arguments. Available tools: semantic_search, "
                    "filter_by_category, filter_by_price, build_outfit. Use '$last' for candidates "
                    "from the latest successful list-like tool result. Never invent product data."
                ),
                user_prompt=query,
            )
            return _validate_plan(payload), False, None
        except Exception:
            return self.deterministic_plan(query), True, "llm_unavailable_or_invalid_plan"

    @staticmethod
    def deterministic_plan(query: str) -> Plan:
        return Plan(
            intent="fashion_recommendation",
            constraints={"source": "deterministic_fallback"},
            tool_calls=[
                ToolCall(tool="semantic_search", arguments={"query": query, "top_k": 12}),
                ToolCall(tool="build_outfit", arguments={"candidates": "$last", "categories": ["top", "bottom", "shoes"]}),
            ],
        )


class AgentRuntime:
    def __init__(self, registry: ToolRegistry, planner: Planner, default_max_steps: int = 6):
        self.registry = registry
        self.planner = planner
        self.default_max_steps = default_max_steps

    def recommend(self, query: str, context: ToolContext, max_steps: int | None = None) -> dict[str, Any]:
        limit = max_steps if max_steps is not None else self.default_max_steps
        plan, degraded, fallback_reason = self.planner.plan(query)
        trace: list[dict[str, Any]] = []
        outputs: list[dict[str, Any]] = []
        seen: set[str] = set()
        last_candidates: list[dict[str, Any]] = []

        for call in plan.tool_calls[:limit]:
            arguments = self._resolve(call.arguments, last_candidates)
            signature = json.dumps({"tool": call.tool, "arguments": arguments}, sort_keys=True, default=str)
            if signature in seen:
                trace.append({"tool": call.tool, "elapsed_ms": 0.0, "status": "skipped_duplicate"})
                degraded = True
                continue
            seen.add(signature)
            started = time.perf_counter()
            try:
                result = self.registry.invoke(call.tool, arguments, context)
                data = result["data"]
                outputs.append({"tool": call.tool, "data": data})
                candidates = self._candidates(data)
                if candidates is not None:
                    last_candidates = candidates
                status = "success"
            except ToolError as exc:
                status = f"failed:{exc.error_type}"
                degraded = True
            trace.append({"tool": call.tool, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "status": status})

        if len(plan.tool_calls) > limit:
            degraded = True
            fallback_reason = fallback_reason or "max_steps_reached"
        final = next((item["data"] for item in reversed(outputs) if item["tool"] == "build_outfit"), None)
        if final is None and outputs:
            final = outputs[-1]["data"]
        return {
            "success": bool(outputs),
            "recommendation": final,
            "plan": {"intent": plan.intent, "constraints": plan.constraints, "tools": [call.tool for call in plan.tool_calls]},
            "trace": trace,
            "degraded": degraded,
            "fallback_reason": fallback_reason,
            "partial_results": outputs if degraded else [],
        }

    @staticmethod
    def _resolve(value: Any, last_candidates: list[dict[str, Any]]) -> Any:
        if value == "$last":
            return last_candidates
        if isinstance(value, dict):
            return {key: AgentRuntime._resolve(item, last_candidates) for key, item in value.items()}
        if isinstance(value, list):
            return [AgentRuntime._resolve(item, last_candidates) for item in value]
        return value

    @staticmethod
    def _candidates(data: Any) -> list[dict[str, Any]] | None:
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return None
