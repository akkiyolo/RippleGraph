"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnswerRequest(BaseModel):
    question: str
    user_id: str = "demo-user"


class AnswerResponse(BaseModel):
    question: str
    status: str
    answer: str | None = None
    confidence: float = 0.0
    reason: str | None = None
    temporal_mode: str = "NONE"
    evidence: list[dict] = Field(default_factory=list)
    traversal_path: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class IngestRequest(BaseModel):
    conversations_path: str = "data/demo/conversations.json"
    user_id: str = "demo-user"


class IngestResponse(BaseModel):
    status: str
    memories_created: int = 0
    message: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
