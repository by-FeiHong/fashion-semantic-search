"""Tests for the persistent FastAPI semantic-search service."""

from fastapi.testclient import TestClient

from ai_service.app import create_app
from ai_service.llm import LLMProvider


class StubProvider(LLMProvider):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        del system_prompt
        return {"intent": "recommend", "constraints": {}, "tool_calls": [
            {"tool": "semantic_search", "arguments": {"query": user_prompt, "top_k": 2}}
        ]}


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int) -> list[dict[str, str | float]]:
        self.calls.append((query, top_k))
        return [{"item_id": "42", "score": 0.91, "image_path": "image.jpg"}]


def test_health_and_search_share_one_runtime_initialization() -> None:
    runtime = FakeRuntime()
    initialization_count = 0

    def loader() -> FakeRuntime:
        nonlocal initialization_count
        initialization_count += 1
        return runtime

    with TestClient(create_app(loader)) as client:
        assert client.get("/health").json() == {"status": "UP"}
        assert client.get("/health").status_code == 200
        response = client.post("/search", json={"query": "black dress", "topK": 3})
        assert response.status_code == 200
        assert response.json()[0]["item_id"] == "42"
        assert runtime.calls == [("black dress", 3)]
        assert initialization_count == 1


def test_search_validates_request() -> None:
    with TestClient(create_app(FakeRuntime)) as client:
        assert client.post("/search", json={"query": "", "topK": 0}).status_code == 422


def test_tools_endpoints_list_invoke_and_return_structured_errors() -> None:
    with TestClient(create_app(FakeRuntime)) as client:
        listing = client.get("/tools")
        assert listing.status_code == 200
        assert {item["name"] for item in listing.json()["tools"]} == {
            "semantic_search", "filter_by_category", "filter_by_price", "weather_lookup", "build_outfit"
        }
        success = client.post(
            "/tools/semantic_search/invoke",
            json={"query": "black dress", "top_k": 2},
        )
        assert success.status_code == 200
        assert success.json()["success"] is True
        unknown = client.post("/tools/missing/invoke", json={})
        assert unknown.status_code == 404
        assert unknown.json()["error"]["type"] == "unknown_tool"
        invalid = client.post("/tools/semantic_search/invoke", json={"query": ""})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["type"] == "validation_error"


def test_agent_recommend_success_response() -> None:
    with TestClient(create_app(FakeRuntime, llm_provider=StubProvider())) as client:
        response = client.post("/agent/recommend", json={"query": "minimal black outfit", "max_steps": 4})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["degraded"] is False
        assert body["trace"][0]["tool"] == "semantic_search"
        assert set(body["recommendation"]) >= {"selected_items", "missing_categories", "constraint_summary", "score_summary", "recommendation_reason"}
        assert "reasoning" not in body
