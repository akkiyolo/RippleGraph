"""Conversation domain models."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """A single message within a conversation session."""

    message_id: str
    session_id: str
    speaker: str
    text: str
    timestamp: datetime


class ConversationSession(BaseModel):
    """A complete conversation session."""

    session_id: str
    user_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)


class ConversationSegment(BaseModel):
    """A coherent segment of conversation turns, grouped for memory extraction."""

    segment_id: str
    session_id: str
    user_id: str
    messages: list[ConversationMessage]
    start_time: datetime
    end_time: datetime
    boundary_reason: str = ""
