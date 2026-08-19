"""Evidence domain models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceNode(BaseModel):
    """A single piece of evidence retrieved from the memory graph."""

    memory_id: str
    text: str
    session_id: str
    timestamp: datetime | None = None

    anchor_score: float = 0.0
    semantic_score: float = 0.0
    graph_score: float = 0.0
    temporal_score: float = 0.0
    provenance_score: float = 0.0

    hop: int = 0
    relation_from_parent: str | None = None
    parent_id: str | None = None

    supports_answer: bool = True
    contradicts_answer: bool = False


class EvidenceLedger(BaseModel):
    """Auditable record of all evidence gathered for a query."""

    query: str

    anchors: list[EvidenceNode] = Field(default_factory=list)
    supporting_evidence: list[EvidenceNode] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceNode] = Field(default_factory=list)
    superseded_evidence: list[EvidenceNode] = Field(default_factory=list)

    traversal_path: list[str] = Field(default_factory=list)

    distinct_supporting_sessions: int = 0
    evidence_count: int = 0
