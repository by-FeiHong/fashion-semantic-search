"""Structured preference storage, API, merging, scoring, and explanations."""

from typing import Any
from fastapi.testclient import TestClient
from ai_service.agent import AgentRuntime, Planner
from ai_service.app import create_app
from ai_service.llm import LLMProvider, LLMProviderError
from ai_service.memory import InMemoryUserPreferenceStore, UserPreferences
from ai_service.tools import ToolContext, create_tool_registry


class OfflineLLM(LLMProvider):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        del system_prompt, user_prompt
        raise LLMProviderError("offline")


class MemoryRuntime:
    metadata: list[dict[str, Any]] = []

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        del query
        return [
            {"item_id": "white", "category": "top", "color": "white", "style": "bold", "price": 40, "score": .95},
            {"item_id": "black", "category": "top", "color": "black", "style": "minimal", "price": 45, "score": .8},
            {"item_id": "bottom", "category": "bottom", "color": "black", "style": "minimal", "price": 50, "score": .8},
            {"item_id": "shoes", "category": "shoes", "color": "gray", "style": "minimal", "price": 55, "score": .8},
        ][:top_k]


def test_preference_api_crud_validation_and_missing_user() -> None:
    with TestClient(create_app(MemoryRuntime, llm_provider=OfflineLLM())) as client:
        assert client.get("/memory/preferences/missing").status_code == 404
        created = client.put("/memory/preferences/u1", json={"preferred_colors": ["black"], "budget_min": 20, "budget_max": 100})
        assert created.status_code == 200 and created.json()["preferences"]["updated_at"]
        patched = client.patch("/memory/preferences/u1", json={"preferred_styles": ["minimal"]})
        assert patched.json()["preferences"]["preferred_colors"] == ["black"]
        assert client.get("/memory/preferences/u1").json()["preferences"]["preferred_styles"] == ["minimal"]
        assert client.put("/memory/preferences/bad", json={"budget_min": 100, "budget_max": 20}).status_code == 422


def test_memory_merge_dislikes_budget_and_real_explanation() -> None:
    preferences = UserPreferences(preferred_colors=["black"], preferred_styles=["minimal"],
        preferred_categories=["top"], disliked_colors=["white"], budget_min=30, budget_max=90)
    result = AgentRuntime(create_tool_registry(), Planner(OfflineLLM())).recommend(
        "recommend an outfit", ToolContext(MemoryRuntime()), preferences=preferences)
    constraints = result["plan"]["constraints"]
    assert constraints["colors"] == ["black"] and constraints["style"] == "minimal"
    assert constraints["budget"] == 90 and constraints["budget_min"] == 30
    assert result["recommendation"]["items"][0]["item_id"] == "black"
    assert "colors=['black']" in result["recommendation"]["recommendation_reason"]
    assert result["memory_summary"]["preferred_colors"] == ["black"]


def test_query_overrides_disliked_color_and_memory_budget() -> None:
    preferences = UserPreferences(preferred_colors=["black"], disliked_colors=["white"], budget_min=30, budget_max=90)
    result = AgentRuntime(create_tool_registry(), Planner(OfflineLLM())).recommend(
        "white top under 60", ToolContext(MemoryRuntime()), preferences=preferences)
    assert result["plan"]["constraints"]["colors"] == ["white"]
    assert result["plan"]["constraints"]["budget"] == 60
    assert result["plan"]["constraints"]["disliked_colors"] is None
    assert {entry["action"] for entry in result["applied_preferences"]} == {"overridden_by_query"}


def test_missing_user_and_no_user_id_do_not_change_recommendation() -> None:
    store = InMemoryUserPreferenceStore()
    with TestClient(create_app(MemoryRuntime, llm_provider=OfflineLLM(), preference_store=store)) as client:
        base = client.post("/agent/recommend", json={"query": "black top"}).json()
        missing = client.post("/agent/recommend", json={"query": "black top", "user_id": "missing"}).json()
    assert base["plan"] == missing["plan"]
    assert base["memory_summary"] is None and missing["memory_summary"] is None
    assert base["applied_preferences"] == missing["applied_preferences"] == []


def test_disliked_style_is_downweighted() -> None:
    preferences = UserPreferences(preferred_categories=["top"], disliked_styles=["bold"])
    result = AgentRuntime(create_tool_registry(), Planner(OfflineLLM())).recommend(
        "recommend something", ToolContext(MemoryRuntime()), preferences=preferences)
    selected = result["recommendation"]["selected_items"][0]
    assert selected["item"]["item_id"] == "black"
    assert "disliked_styles" in result["recommendation"]["constraint_summary"]["supported"]
