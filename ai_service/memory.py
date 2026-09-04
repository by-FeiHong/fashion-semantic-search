"""Structured, explicit user preference memory with a replaceable store boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from pydantic import BaseModel, Field, model_validator


class UserPreferences(BaseModel):
    preferred_colors: list[str] = Field(default_factory=list)
    disliked_colors: list[str] = Field(default_factory=list)
    preferred_styles: list[str] = Field(default_factory=list)
    disliked_styles: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_budget(self) -> "UserPreferences":
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min must not exceed budget_max")
        return self


class UserPreferencePatch(BaseModel):
    preferred_colors: list[str] | None = None
    disliked_colors: list[str] | None = None
    preferred_styles: list[str] | None = None
    disliked_styles: list[str] | None = None
    preferred_categories: list[str] | None = None
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


def model_dump(model: BaseModel, *, exclude_unset: bool = False) -> dict[str, Any]:
    dumper = getattr(model, "model_dump", None)
    return dumper(exclude_unset=exclude_unset) if dumper else model.dict(exclude_unset=exclude_unset)


class UserPreferenceStore(ABC):
    """Persistence port. MySQL/Redis adapters only need to implement these methods."""

    @abstractmethod
    def get(self, user_id: str) -> UserPreferences | None: ...

    @abstractmethod
    def put(self, user_id: str, preferences: UserPreferences) -> UserPreferences: ...

    def patch(self, user_id: str, changes: dict[str, Any]) -> UserPreferences:
        current = self.get(user_id) or UserPreferences()
        values = model_dump(current)
        values.update(changes)
        values.pop("updated_at", None)
        return self.put(user_id, UserPreferences(**values))


class InMemoryUserPreferenceStore(UserPreferenceStore):
    def __init__(self) -> None:
        self._values: dict[str, UserPreferences] = {}
        self._lock = RLock()

    def get(self, user_id: str) -> UserPreferences | None:
        with self._lock:
            value = self._values.get(user_id)
            return UserPreferences(**model_dump(value)) if value else None

    def put(self, user_id: str, preferences: UserPreferences) -> UserPreferences:
        values = model_dump(preferences)
        values["updated_at"] = datetime.now(timezone.utc)
        stored = UserPreferences(**values)
        with self._lock:
            self._values[user_id] = stored
        return UserPreferences(**model_dump(stored))
