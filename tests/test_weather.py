"""Offline tests for weather providers, tools, orchestration, and derivation."""

from __future__ import annotations

import json
import socket
import urllib.error
from datetime import date, timedelta
from typing import Any

import pytest

from ai_service.agent import AgentRuntime, Planner
from ai_service.llm import LLMProvider, LLMProviderError
from ai_service.tools import ToolContext, ToolError, create_tool_registry
from ai_service.weather import (
    HttpWeatherProvider,
    WeatherNoDataError,
    WeatherProvider,
    WeatherProviderError,
    WeatherSettings,
    WeatherTimeoutError,
    _normalize_http_payload,
)


class FakeRuntime:
    metadata: list[dict[str, Any]] = []

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        del query
        return [
            {"item_id": "top", "category": "top", "score": 0.9},
            {"item_id": "bottom", "category": "bottom", "score": 0.8},
            {"item_id": "shoes", "category": "shoes", "score": 0.7},
            {"item_id": "coat", "category": "outerwear", "score": 0.6},
        ][:top_k]


class OfflineLLM(LLMProvider):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        del system_prompt, user_prompt
        raise LLMProviderError("offline")


class StubWeather(WeatherProvider):
    name = "stub"

    def __init__(self, response: dict[str, Any] | Exception):
        self.response = response
        self.calls: list[tuple[str, date]] = []

    def lookup(self, *, location: str, target_date: date) -> dict[str, Any]:
        self.calls.append((location, target_date))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_location_date_and_bilingual_weather_intent_extraction() -> None:
    english = Planner.deterministic_plan("What should I wear in Lund tomorrow?").constraints
    assert (english.location, english.date_offset, english.weather_intent) == ("lund", 1, True)
    chinese = Planner.deterministic_plan("哥本哈根后天通勤穿搭").constraints
    assert (chinese.location, chinese.date_offset, chinese.occasion) == ("Copenhagen", 2, "commute")
    explicit = Planner.deterministic_plan("weather in Malmö 2026-09-10").constraints
    assert (explicit.location, explicit.date) == ("Malmö", "2026-09-10")


def test_weather_lookup_success_has_normalized_fields_and_metadata() -> None:
    provider = StubWeather({"temperature": 8, "feels_like": 6, "precipitation": 2.5,
                            "wind": 11, "condition": "rain", "source": "fixture"})
    result = create_tool_registry().invoke(
        "weather_lookup", {"location": "Lund", "date_offset": 1}, ToolContext(FakeRuntime(), provider)
    )["data"]
    assert result["date"] == (date.today() + timedelta(days=1)).isoformat()
    assert result["temperature"] == 8
    assert result["provider"] == "stub"
    assert result["source"] == "fixture"


@pytest.mark.parametrize("error", [WeatherProviderError("failed"), WeatherTimeoutError("timeout"), WeatherNoDataError("empty")])
def test_provider_failure_timeout_and_no_data_degrade_without_losing_recommendation(error: Exception) -> None:
    context = ToolContext(FakeRuntime(), StubWeather(error))
    result = AgentRuntime(create_tool_registry(), Planner(OfflineLLM())).recommend("明天 Lund 穿什么", context)
    assert result["success"] is True
    assert result["degraded"] is True
    assert result["fallback_reason"].startswith("llm_unavailable_or_invalid_plan")
    assert "weather_lookup_failed" in result["fallback_reason"]
    assert result["trace"][0]["tool"] == "weather_lookup"
    assert result["trace"][0]["status"].startswith("failed:")
    assert result["recommendation"]["weather_context"] is None


def test_weather_rules_are_deterministic_explainable_and_use_only_category_support() -> None:
    weather = {"temperature": 3, "feels_like": 0, "precipitation": 4, "wind": 12, "condition": "rain"}
    runtime = AgentRuntime(create_tool_registry(), Planner(OfflineLLM()))
    first = runtime.recommend("明天 Lund 穿什么", ToolContext(FakeRuntime(), StubWeather(weather)))
    second = runtime.recommend("明天 Lund 穿什么", ToolContext(FakeRuntime(), StubWeather(weather)))
    derived = first["recommendation"]["constraint_summary"]["derived_from_weather"]
    assert derived == second["recommendation"]["constraint_summary"]["derived_from_weather"]
    assert [item["constraint"] for item in derived] == ["outerwear", "layering", "rain_protection", "wind_protection"]
    assert first["recommendation"]["selected_items"][-1]["requested_category"] == "outerwear"
    assert "weather" not in first["recommendation"]["selected_items"][0]["score_components"]


def test_weather_explanation_quotes_returned_facts_without_llm_generation() -> None:
    weather = {"temperature": 7, "feels_like": 5, "precipitation": 1.2, "wind": 8, "condition": "light rain"}
    result = AgentRuntime(create_tool_registry(), Planner(OfflineLLM())).recommend(
        "What should I wear in Lund tomorrow?", ToolContext(FakeRuntime(), StubWeather(weather))
    )
    reason = result["recommendation"]["recommendation_reason"]
    assert "7°C" in reason and "feels like 5°C" in reason
    assert "precipitation 1.2 mm" in reason and "wind 8 m/s" in reason and "light rain" in reason


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps({"current": {"temp_c": 9, "feelslike_c": 7, "rain_mm": 0,
                                       "wind_mps": 4, "condition": {"text": "cloudy"}}}).encode()


def test_http_provider_is_configurable_and_network_is_fully_stubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        captured.update(url=request.full_url, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = HttpWeatherProvider(WeatherSettings(provider="http", base_url="https://weather.invalid/v1", api_key="secret", timeout_seconds=2.5))
    result = provider.lookup(location="Lund", target_date=date(2026, 9, 5))
    assert result == {"temperature": 9, "feels_like": 7, "precipitation": 0, "wind": 4, "condition": "cloudy"}
    assert "location=Lund" in captured["url"] and "api_key=secret" in captured["url"]
    assert captured["timeout"] == 2.5


def test_http_provider_maps_timeout_and_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpWeatherProvider(WeatherSettings(provider="http", base_url="https://weather.invalid"))
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(socket.timeout()))
    with pytest.raises(WeatherTimeoutError):
        provider.lookup(location="Lund", target_date=date.today())
    with pytest.raises(WeatherNoDataError):
        _normalize_http_payload({})
