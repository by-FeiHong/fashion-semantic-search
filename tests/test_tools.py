"""Tests for the lightweight tool framework and built-in tools."""

from typing import Any

import pytest
from pydantic import BaseModel

from ai_service.tools import (
    ToolContext, ToolError, ToolRegistry, ToolValidationError, UnknownToolError,
    create_tool_registry, tool,
)


class FakeRuntime:
    metadata: list[dict[str, Any]] = []

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        return [{"item_id": "search-1", "category": "dress", "query_seen": query}][:top_k]


class EchoInput(BaseModel):
    value: int


@tool(description="Echo a typed value.")
def echo(args: EchoInput, context: ToolContext) -> dict[str, int]:
    del context
    return {"value": args.value, "result_count": 1}


@tool(description="Raise an unexpected error for boundary testing.")
def broken(args: EchoInput, context: ToolContext) -> None:
    del args, context
    raise RuntimeError("private implementation detail")


CONTEXT = ToolContext(FakeRuntime())


def test_register_find_list_schema_and_successful_invoke() -> None:
    registry = ToolRegistry()
    registry.register(echo)
    assert registry.get("echo") is echo
    assert registry.list_specs()[0].input_schema["properties"]["value"]["type"] == "integer"
    assert registry.invoke("echo", {"value": 7}, CONTEXT)["data"]["value"] == 7


def test_duplicate_registration_is_rejected() -> None:
    registry = ToolRegistry()
    registry.register(echo)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(echo)


def test_unknown_tool_and_validation_error_are_distinct() -> None:
    registry = ToolRegistry()
    registry.register(echo)
    with pytest.raises(UnknownToolError):
        registry.invoke("missing", {}, CONTEXT)
    with pytest.raises(ToolValidationError) as error:
        registry.invoke("echo", {"value": "not-an-int"}, CONTEXT)
    assert error.value.details


def test_execution_error_is_wrapped_without_leaking_details() -> None:
    registry = ToolRegistry()
    registry.register(broken)
    with pytest.raises(ToolError, match="Tool execution failed") as error:
        registry.invoke("broken", {"value": 1}, CONTEXT)
    assert "private implementation detail" not in str(error.value)


def test_semantic_search_reuses_runtime() -> None:
    result = create_tool_registry().invoke(
        "semantic_search", {"query": "black dress", "top_k": 2}, CONTEXT
    )
    assert result["data"][0]["query_seen"] == "black dress"


def test_category_filter() -> None:
    result = create_tool_registry().invoke("filter_by_category", {
        "category": "shoe",
        "candidates": [{"item_id": "1", "category": "Shoes"}, {"item_id": "2", "category": "dress"}],
    }, CONTEXT)
    assert [item["item_id"] for item in result["data"]] == ["1"]


def test_price_filter_is_unsupported_without_real_prices() -> None:
    result = create_tool_registry().invoke("filter_by_price", {
        "candidates": [{"item_id": "1"}], "max_price": 100
    }, CONTEXT)["data"]
    assert result["status"] == "unsupported"
    assert result["items"] == []


def test_price_filter_demo_mode_is_explicit_and_deterministic() -> None:
    arguments = {"candidates": [{"item_id": "1"}], "demo_mode": True, "max_price": 1000}
    first = create_tool_registry().invoke("filter_by_price", arguments, CONTEXT)["data"]
    second = create_tool_registry().invoke("filter_by_price", arguments, CONTEXT)["data"]
    assert first == second
    assert first["items"][0]["price_source"] == "synthetic_demo"


def test_build_outfit_is_deterministic_and_reports_missing_categories() -> None:
    candidates = [
        {"item_id": "top-1", "category": "top"},
        {"item_id": "top-2", "category": "top"},
        {"item_id": "shoe-1", "category": "shoes"},
    ]
    result = create_tool_registry().invoke("build_outfit", {
        "candidates": candidates, "categories": ["top", "shoes", "bag"]
    }, CONTEXT)["data"]
    assert [item["item_id"] for item in result["items"]] == ["top-1", "shoe-1"]
    assert result["missing_categories"] == ["bag"]
    assert result["complete"] is False


def test_constraint_scoring_stable_order_substitution_and_unsupported_fields() -> None:
    candidates = [
        {"item_id": "z", "category": "top", "score": 0.9, "color": "red", "style": "sporty"},
        {"item_id": "a", "category": "top", "score": 0.9, "color": "black", "style": "minimal"},
        {"item_id": "d", "category": "dress", "score": 0.8, "color": "black"},
    ]
    arguments = {"candidates": candidates, "categories": ["top", "bottom", "shoes"],
                 "constraints": {"colors": ["black"], "style": "minimal", "season": "autumn"}}
    first = create_tool_registry().invoke("build_outfit", arguments, CONTEXT)["data"]
    second = create_tool_registry().invoke("build_outfit", arguments, CONTEXT)["data"]
    assert first == second
    assert first["selected_items"][0]["item"]["item_id"] == "a"
    assert first["substitutions"]["bottom"] == "dress"
    assert first["missing_categories"] == ["shoes"]
    assert "season" in first["constraint_summary"]["unsupported"]


def test_budget_unsupported_by_default_and_hard_constraint_in_demo_mode() -> None:
    candidates = [{"item_id": "top-1", "category": "top", "score": 1.0},
                  {"item_id": "shoe-1", "category": "shoes", "score": 1.0}]
    base = {"candidates": candidates, "categories": ["top", "shoes"], "constraints": {"budget": 1}}
    unsupported = create_tool_registry().invoke("build_outfit", base, CONTEXT)["data"]
    assert "budget" in unsupported["constraint_summary"]["unsupported"]
    assert all("price" not in item["item"] for item in unsupported["selected_items"])
    demo = create_tool_registry().invoke("build_outfit", {**base, "demo_mode": True}, CONTEXT)["data"]
    assert "budget" in demo["constraint_summary"]["supported"]
    assert demo["selected_items"] == []
