"""Memory domain models."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Types of durable memories RippleGraph extracts."""

    FACT = "FACT"
    EVENT = "EVENT"
    DECISION = "DECISION"
    PREFERENCE = "PREFERENCE"
    EPISODE_SUMMARY = "EPISODE_SUMMARY"


class MemoryRecord(BaseModel):
    """A durable memory extracted from conversation."""

    id: str
    type: MemoryType

    subject: str
    predicate: str
    object: str | None = None

    text: str

    user_id: str
    session_id: str
    source_message_ids: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now())
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    confidence: float = 1.0
    importance: float = 0.5

    supersedes_id: str | None = None
    contradicts_ids: list[str] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)


def make_memory_id(
    session_id: str,
    subject: str,
    predicate: str,
    content: str,
) -> str:
    """Generate a deterministic memory ID from stable components.

    Same logical input → same ID, enabling idempotent ingestion.
    """
    components = f"{session_id}:{subject.lower().strip()}:{predicate.lower().strip()}:{content.lower().strip()}"
    content_hash = hashlib.sha256(components.encode("utf-8")).hexdigest()[:16]
    return f"mem-{content_hash}"
