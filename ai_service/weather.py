"""Provider-neutral weather boundary and configurable HTTP implementation."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any


class WeatherProviderError(RuntimeError):
    """Safe error raised at the weather provider boundary."""


class WeatherTimeoutError(WeatherProviderError):
    """The configured weather provider did not respond in time."""


class WeatherNoDataError(WeatherProviderError):
    """The provider returned no usable current/forecast record."""


@dataclass(frozen=True)
class WeatherSettings:
    provider: str = "disabled"
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "WeatherSettings":
        return cls(
            provider=os.getenv("FASHION_WEATHER_PROVIDER", "disabled"),
            base_url=os.getenv("FASHION_WEATHER_BASE_URL", ""),
            api_key=os.getenv("FASHION_WEATHER_API_KEY", ""),
            timeout_seconds=float(os.getenv("FASHION_WEATHER_TIMEOUT_SECONDS", "5")),
        )


class WeatherProvider(ABC):
    name = "unknown"

    @abstractmethod
    def lookup(self, *, location: str, target_date: date) -> dict[str, Any]:
        """Return normalized weather fields for a place and calendar date."""


class DisabledWeatherProvider(WeatherProvider):
    name = "disabled"

    def lookup(self, *, location: str, target_date: date) -> dict[str, Any]:
        del location, target_date
        raise WeatherProviderError("Weather provider is disabled")


class HttpWeatherProvider(WeatherProvider):
    """Generic JSON HTTP provider with a small, documented response contract."""

    name = "http"

    def __init__(self, settings: WeatherSettings):
        if not settings.base_url:
            raise ValueError("Weather HTTP provider requires a base URL")
        self.settings = settings

    def lookup(self, *, location: str, target_date: date) -> dict[str, Any]:
        query = {"location": location, "date": target_date.isoformat()}
        if self.settings.api_key:
            query["api_key"] = self.settings.api_key
        separator = "&" if "?" in self.settings.base_url else "?"
        url = self.settings.base_url + separator + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise WeatherTimeoutError("Weather request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise WeatherTimeoutError("Weather request timed out") from exc
            raise WeatherProviderError("Weather request failed") from exc
        except Exception as exc:
            raise WeatherProviderError("Weather response was invalid") from exc
        return _normalize_http_payload(payload)


def _normalize_http_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise WeatherNoDataError("Weather provider returned no usable data")
    record = payload.get("weather") or payload.get("current") or payload.get("forecast") or payload
    if isinstance(record, list):
        record = record[0] if record else None
    if not isinstance(record, dict):
        raise WeatherNoDataError("Weather provider returned no usable data")
    aliases = {
        "temperature": ("temperature", "temperature_c", "temp", "temp_c"),
        "feels_like": ("feels_like", "feelslike", "feelslike_c"),
        "precipitation": ("precipitation", "precipitation_mm", "rain", "rain_mm"),
        "wind": ("wind", "wind_speed", "wind_kph", "wind_mps"),
        "condition": ("condition", "summary", "description", "weather"),
    }
    normalized: dict[str, Any] = {}
    for canonical, names in aliases.items():
        value = next((record[name] for name in names if record.get(name) is not None), None)
        if isinstance(value, dict):
            value = value.get("text") or value.get("description") or value.get("main")
        if value is not None:
            normalized[canonical] = value
    if "temperature" not in normalized:
        raise WeatherNoDataError("Weather provider returned no temperature")
    return normalized


def create_weather_provider(settings: WeatherSettings | None = None) -> WeatherProvider:
    configured = settings or WeatherSettings.from_env()
    provider = configured.provider.casefold()
    if provider in {"", "disabled", "none"}:
        return DisabledWeatherProvider()
    if provider in {"http", "generic_http", "generic-http"}:
        return HttpWeatherProvider(configured)
    raise ValueError(f"Unsupported weather provider: {configured.provider}")
