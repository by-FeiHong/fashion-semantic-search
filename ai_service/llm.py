"""Provider-neutral LLM boundary with an optional OpenAI-compatible transport."""

from __future__ import annotations

import json
import os
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class LLMProviderError(RuntimeError):
    """A safe provider-boundary error."""


class LLMProvider(ABC):
    @abstractmethod
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Return a decoded JSON object, or raise LLMProviderError."""


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "disabled"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "LLMSettings":
        return cls(
            provider=os.getenv("FASHION_LLM_PROVIDER", "disabled"),
            model=os.getenv("FASHION_LLM_MODEL", ""),
            base_url=os.getenv("FASHION_LLM_BASE_URL", ""),
            api_key=os.getenv("FASHION_LLM_API_KEY", ""),
            timeout_seconds=float(os.getenv("FASHION_LLM_TIMEOUT_SECONDS", "20")),
        )


class DisabledLLMProvider(LLMProvider):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        del system_prompt, user_prompt
        raise LLMProviderError("LLM provider is disabled")


class OpenAICompatibleProvider(LLMProvider):
    """Minimal configurable JSON-chat transport; business code remains provider-neutral."""

    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.settings.model or not self.settings.base_url or not self.settings.api_key:
            raise LLMProviderError("LLM provider configuration is incomplete")
        payload = json.dumps({
            "model": self.settings.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode()
        request = urllib.request.Request(
            self.settings.base_url.rstrip("/") + "/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                body = json.loads(response.read().decode())
            content = body["choices"][0]["message"]["content"]
            result = json.loads(content) if isinstance(content, str) else content
            if not isinstance(result, dict):
                raise ValueError("response is not an object")
            return result
        except Exception as exc:
            raise LLMProviderError("LLM request failed") from exc


def create_llm_provider(settings: LLMSettings | None = None) -> LLMProvider:
    configured = settings or LLMSettings.from_env()
    if configured.provider.casefold() in {"", "disabled", "none"}:
        return DisabledLLMProvider()
    if configured.provider.casefold() in {"openai_compatible", "openai-compatible"}:
        return OpenAICompatibleProvider(configured)
    raise ValueError(f"Unsupported LLM provider: {configured.provider}")
