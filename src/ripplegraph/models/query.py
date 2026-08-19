"""Query domain models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TemporalMode(str, Enum):
    """How RippleGraph interprets the temporal intent of a query."""

    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    TRANSITION = "TRANSITION"
    TIMELINE = "TIMELINE"
    NONE = "NONE"


class QueryPlan(BaseModel):
    """The result of query planning — entities, intent, and temporal mode."""

    original_query: str
    entities: list[str] = Field(default_factory=list)
    intent: str = ""
    temporal_mode: TemporalMode = TemporalMode.NONE
    relevant_time: str | None = None
