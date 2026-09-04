"""Single-agent planning and bounded deterministic tool orchestration."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from ai_service.llm import LLMProvider, LLMProviderError
from ai_service.tools import ToolContext, ToolError, ToolRegistry


class ToolCall(BaseModel):
    tool: Literal["semantic_search", "filter_by_category", "filter_by_price", "weather_lookup", "build_outfit"]
    arguments: dict[str, Any] = Field(default_factory=dict)


class RecommendationConstraints(BaseModel):
    season: str | None = None
    occasion: str | None = None
    colors: list[str] | None = None
    style: str | None = None
    budget: float | None = Field(default=None, ge=0)
    categories: list[str] | None = None
    source: str | None = None
    location: str | None = None
    date: str | None = None
    date_offset: int | None = Field(default=None, ge=0, le=14)
    weather_intent: bool = False


class Plan(BaseModel):
    intent: str = Field(min_length=1)
    constraints: RecommendationConstraints = Field(default_factory=RecommendationConstraints)
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
                    "Return only a JSON object with intent, constraints and tool_calls. Constraints "
                    "may contain season, occasion, colors (array), style, budget (number), categories (array), "
                    "location, date (YYYY-MM-DD), date_offset, and weather_intent. "
                    "Each tool call has tool and arguments. Available tools: semantic_search, "
                    "filter_by_category, filter_by_price, weather_lookup, build_outfit. Use '$last' for candidates "
                    "from the latest successful list-like tool result. Never invent product data."
                ),
                user_prompt=query,
            )
            plan = _validate_plan(payload)
            extracted = self._extract_constraints(query)
            for field in ("location", "date", "date_offset"):
                if getattr(plan.constraints, field) is None:
                    setattr(plan.constraints, field, getattr(extracted, field))
            plan.constraints.weather_intent = plan.constraints.weather_intent or extracted.weather_intent
            return plan, False, None
        except Exception:
            return self.deterministic_plan(query), True, "llm_unavailable_or_invalid_plan"

    @staticmethod
    def deterministic_plan(query: str) -> Plan:
        constraints = Planner._extract_constraints(query)
        categories = constraints.categories or ["top", "bottom", "shoes"]
        return Plan(
            intent="fashion_recommendation",
            constraints=constraints,
            tool_calls=[
                ToolCall(tool="semantic_search", arguments={"query": query, "top_k": 12}),
                ToolCall(tool="build_outfit", arguments={"candidates": "$last", "categories": categories}),
            ],
        )

    @staticmethod
    def _extract_constraints(query: str) -> RecommendationConstraints:
        text = query.casefold()
        seasons = {"spring": ("spring", "春"), "summer": ("summer", "夏"), "autumn": ("autumn", "fall", "秋"), "winter": ("winter", "冬")}
        occasions = {"commute": ("commute", "work", "office", "通勤", "上班"), "casual": ("casual", "休闲"), "formal": ("formal", "正式"), "party": ("party", "派对")}
        styles = {"minimal": ("minimal", "minimalist", "极简"), "casual": ("casual", "休闲"), "sporty": ("sporty", "运动"), "vintage": ("vintage", "复古")}
        colors = {"black": ("black", "黑"), "gray": ("gray", "grey", "灰"), "white": ("white", "白"), "blue": ("blue", "蓝"), "red": ("red", "红"), "green": ("green", "绿"), "beige": ("beige", "米色")}
        category_terms = {"top": ("top", "shirt", "上衣", "衬衫"), "bottom": ("bottom", "pants", "trousers", "skirt", "下装", "裤", "裙"), "shoes": ("shoe", "shoes", "sneaker", "鞋"), "outerwear": ("coat", "jacket", "outerwear", "外套"), "dress": ("dress", "连衣裙"), "bag": ("bag", "包")}
        pick = lambda mapping: next((key for key, words in mapping.items() if any(word in text for word in words)), None)
        found_colors = [key for key, words in colors.items() if any(word in text for word in words)]
        found_categories = [key for key, words in category_terms.items() if any(word in text for word in words)] or None
        budget_match = re.search(r"(?:budget|预算|under|以内|不超过)\s*[:：$¥￥]?\s*(\d+(?:\.\d+)?)|(?:[$¥￥])\s*(\d+(?:\.\d+)?)", text)
        budget = float(next(group for group in budget_match.groups() if group)) if budget_match else None
        date_offset = 2 if any(word in text for word in ("day after tomorrow", "后天")) else 1 if any(word in text for word in ("tomorrow", "明天")) else None
        explicit_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        known_locations = {"lund": ("lund", "隆德"), "Copenhagen": ("copenhagen", "哥本哈根")}
        location = next((canonical for canonical, words in known_locations.items() if any(word.casefold() in text for word in words)), None)
        if location is None:
            english = re.search(r"(?:in|at)\s+(\S+)", query, re.IGNORECASE)
            location = english.group(1).strip(".,!?;:") if english else None
        weather_intent = bool(location and date_offset is not None) or any(word in text for word in ("weather", "forecast", "temperature", "rain", "wind", "天气", "气温", "下雨", "大风", "穿什么"))
        return RecommendationConstraints(season=pick(seasons), occasion=pick(occasions), colors=found_colors or None,
                                         style=pick(styles), budget=budget, categories=found_categories,
                                         location=location, date=explicit_date.group(1) if explicit_date else None,
                                         date_offset=date_offset, weather_intent=weather_intent,
                                         source="deterministic_fallback")


class AgentRuntime:
    def __init__(self, registry: ToolRegistry, planner: Planner, default_max_steps: int = 6):
        self.registry = registry
        self.planner = planner
        self.default_max_steps = default_max_steps

    def recommend(self, query: str, context: ToolContext, max_steps: int | None = None, demo_mode: bool = False) -> dict[str, Any]:
        limit = max_steps if max_steps is not None else self.default_max_steps
        plan, degraded, fallback_reason = self.planner.plan(query)
        constraints = _dump(plan.constraints)
        trace: list[dict[str, Any]] = []
        outputs: list[dict[str, Any]] = []
        seen: set[str] = set()
        last_candidates: list[dict[str, Any]] = []
        weather_context: dict[str, Any] | None = None
        derived_weather: list[dict[str, Any]] = []

        if plan.constraints.location and (plan.constraints.weather_intent or plan.constraints.date or plan.constraints.date_offset is not None):
            weather_args = {"location": plan.constraints.location}
            if plan.constraints.date:
                weather_args["date"] = plan.constraints.date
            if plan.constraints.date_offset is not None:
                weather_args["date_offset"] = plan.constraints.date_offset
            started = time.perf_counter()
            try:
                weather_context = self.registry.invoke("weather_lookup", weather_args, context)["data"]
                derived_weather = self._derive_weather(weather_context)
                trace.append({"tool": "weather_lookup", "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "status": "success"})
            except ToolError as exc:
                degraded = True
                weather_reason = f"weather_lookup_failed:{exc.error_type}"
                fallback_reason = f"{fallback_reason};{weather_reason}" if fallback_reason else weather_reason
                trace.append({"tool": "weather_lookup", "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "status": f"failed:{exc.error_type}"})

        categories = list(plan.constraints.categories or ["top", "bottom", "shoes"])
        if any(rule["constraint"] == "outerwear" for rule in derived_weather) and "outerwear" not in categories:
            categories.append("outerwear")

        for call in plan.tool_calls[:limit]:
            arguments = self._resolve(call.arguments, last_candidates)
            if call.tool == "build_outfit":
                arguments = {**arguments, "categories": categories, "constraints": constraints, "query": query, "demo_mode": demo_mode,
                             "weather_context": weather_context, "derived_from_weather": derived_weather}
            if call.tool == "weather_lookup":
                continue
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
        if final is None:
            try:
                final = self.registry.invoke("build_outfit", {"candidates": last_candidates, "categories": categories,
                    "constraints": constraints, "query": query, "demo_mode": demo_mode, "weather_context": weather_context,
                    "derived_from_weather": derived_weather}, context)["data"]
                outputs.append({"tool": "build_outfit", "data": final})
            except ToolError:
                final = None
                degraded = True
        if isinstance(final, dict):
            final["weather_context"] = weather_context
            final["recommendation_reason"] = self._explain(query, constraints, final, weather_context)
        return {
            "success": bool(outputs),
            "recommendation": final,
            "plan": {"intent": plan.intent, "constraints": constraints, "tools": [call.tool for call in plan.tool_calls]},
            "trace": trace,
            "degraded": degraded,
            "fallback_reason": fallback_reason,
            "partial_results": outputs if degraded else [],
        }

    def _explain(self, query: str, constraints: dict[str, Any], result: dict[str, Any], weather: dict[str, Any] | None = None) -> str:
        if weather:
            facts = [f"{weather['location']} on {weather['date']}: {weather['temperature']}°C"]
            if weather.get("feels_like") is not None:
                facts.append(f"feels like {weather['feels_like']}°C")
            if weather.get("precipitation") is not None:
                facts.append(f"precipitation {weather['precipitation']} mm")
            if weather.get("wind") is not None:
                facts.append(f"wind {weather['wind']} m/s")
            if weather.get("condition"):
                facts.append(str(weather["condition"]))
            derived = [item["constraint"] for item in result.get("constraint_summary", {}).get("derived_from_weather", [])]
            suffix = f" Derived suggestions: {', '.join(derived)}." if derived else ""
            return "Weather used: " + ", ".join(facts) + f" Selected {len(result.get('selected_items', []))} item(s)." + suffix
        try:
            payload = self.planner.provider.complete_json(
                system_prompt="Return JSON with one short recommendation_reason. Explain matches and gaps only; no chain-of-thought.",
                user_prompt=json.dumps({"query": query, "constraints": constraints, "selected_items": result.get("selected_items", []),
                                        "missing_categories": result.get("missing_categories", [])}, ensure_ascii=False, default=str),
            )
            reason = payload.get("recommendation_reason")
            if isinstance(reason, str) and reason.strip():
                return reason.strip()
        except Exception:
            pass
        selected = len(result.get("selected_items", []))
        missing = result.get("missing_categories", [])
        supported = result.get("constraint_summary", {}).get("supported", [])
        reason = f"Selected {selected} item(s) using deterministic category and available attribute matching"
        if supported:
            reason += f" for {', '.join(supported)}"
        if missing:
            reason += f"; no suitable candidate was available for {', '.join(missing)}"
        return reason + "."

    @staticmethod
    def _derive_weather(weather: dict[str, Any]) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        temperature = float(weather["temperature"])
        if temperature <= 10:
            rules.append({"constraint": "outerwear", "rule": "temperature_lte_10c", "value": temperature})
        if temperature <= 5:
            rules.append({"constraint": "layering", "rule": "temperature_lte_5c", "value": temperature})
        precipitation = weather.get("precipitation")
        rain = weather.get("rain")
        if (precipitation is not None and float(precipitation) > 0) or rain is True:
            rules.append({"constraint": "rain_protection", "rule": "precipitation_gt_0", "value": precipitation})
        if weather.get("wind") is not None and float(weather["wind"]) >= 10:
            rules.append({"constraint": "wind_protection", "rule": "wind_gte_10mps", "value": weather["wind"]})
        return rules

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
