"""Result domain models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ripplegraph.models.evidence import EvidenceNode


class QueryStatus(str, Enum):
    """Whether the system answered or abstained."""

    ANSWERED = "ANSWERED"
    ABSTAINED = "ABSTAINED"


class QueryResult(BaseModel):
    """Complete result of a RippleGraph query."""

    question: str
    status: QueryStatus
    answer: str | None = None
    confidence: float = 0.0
    reason: str | None = None

    evidence: list[EvidenceNode] = Field(default_factory=list)
    traversal_path: list[str] = Field(default_factory=list)

    temporal_mode: str = "NONE"
    latency_ms: float = 0.0
