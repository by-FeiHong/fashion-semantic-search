"""Tests for planning, bounded orchestration and graceful degradation."""

from typing import Any

from pydantic import BaseModel

from ai_service.agent import AgentRuntime, Planner
from ai_service.llm import LLMProvider, LLMProviderError
from ai_service.tools import ToolContext, ToolRegistry, create_tool_registry, tool


class FakeRuntime:
    metadata: list[dict[str, Any]] = []

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        del query
        return [
            {"item_id": "t", "category": "top"},
            {"item_id": "b", "category": "bottom"},
            {"item_id": "s", "category": "shoes"},
        ][:top_k]


class StubProvider(LLMProvider):
    def __init__(self, value: Any):
        self.value = value

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        del system_prompt, user_prompt
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def valid_plan(calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"intent": "recommend", "constraints": {"style": "minimal"}, "tool_calls": calls or [
        {"tool": "semantic_search", "arguments": {"query": "black outfit", "top_k": 10}},
        {"tool": "build_outfit", "arguments": {"candidates": "$last", "categories": ["top", "bottom", "shoes"]}},
    ]}


CONTEXT = ToolContext(FakeRuntime())


def test_valid_llm_plan_and_multi_tool_execution() -> None:
    result = AgentRuntime(create_tool_registry(), Planner(StubProvider(valid_plan()))).recommend("request", CONTEXT)
    assert result["degraded"] is False
    assert [entry["tool"] for entry in result["trace"]] == ["semantic_search", "build_outfit"]
    assert result["recommendation"]["complete"] is True


def test_invalid_plan_and_llm_exception_use_deterministic_fallback() -> None:
    for response in ({"bad": True}, LLMProviderError("offline"), RuntimeError("provider bug")):
        result = AgentRuntime(create_tool_registry(), Planner(StubProvider(response))).recommend("request", CONTEXT)
        assert result["degraded"] is True
        assert result["fallback_reason"] == "llm_unavailable_or_invalid_plan"
        assert result["recommendation"] is not None


def test_duplicate_call_is_skipped() -> None:
    call = {"tool": "semantic_search", "arguments": {"query": "x", "top_k": 2}}
    result = AgentRuntime(create_tool_registry(), Planner(StubProvider(valid_plan([call, call])))).recommend("x", CONTEXT)
    assert result["trace"][1]["status"] == "skipped_duplicate"


def test_max_steps_bounds_execution() -> None:
    result = AgentRuntime(create_tool_registry(), Planner(StubProvider(valid_plan()))).recommend("x", CONTEXT, max_steps=1)
    assert len(result["trace"]) == 1
    assert result["fallback_reason"] == "max_steps_reached"


class FailInput(BaseModel):
    candidates: list[dict[str, Any]] = []


@tool(name="filter_by_category", description="fail")
def failing_tool(args: FailInput, context: ToolContext) -> None:
    del args, context
    raise RuntimeError("boom")


def test_single_tool_failure_returns_partial_results_and_continues() -> None:
    registry = create_tool_registry()
    registry._tools["filter_by_category"] = failing_tool
    calls = [
        {"tool": "semantic_search", "arguments": {"query": "x", "top_k": 5}},
        {"tool": "filter_by_category", "arguments": {"candidates": "$last"}},
        {"tool": "build_outfit", "arguments": {"candidates": "$last", "categories": ["top"]}},
    ]
    result = AgentRuntime(registry, Planner(StubProvider(valid_plan(calls)))).recommend("x", CONTEXT)
    assert result["trace"][1]["status"].startswith("failed:")
    assert result["recommendation"]["items"][0]["item_id"] == "t"
    assert result["partial_results"]
