"""Conversation loader — reads demo/LongMemEval data into domain models."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from ripplegraph.models.conversation import ConversationMessage, ConversationSession

logger = logging.getLogger(__name__)


def load_conversations(path: str | Path) -> list[ConversationSession]:
    """Load conversation sessions from a JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Conversations file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    sessions: list[ConversationSession] = []
    for session_data in data:
        messages = []
        for msg in session_data.get("messages", []):
            messages.append(
                ConversationMessage(
                    message_id=msg["message_id"],
                    session_id=session_data["session_id"],
                    speaker=msg["speaker"],
                    text=msg["text"],
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                )
            )
        sessions.append(
            ConversationSession(
                session_id=session_data["session_id"],
                user_id=session_data["user_id"],
                messages=messages,
            )
        )
    logger.info("Loaded %d sessions from %s", len(sessions), path)
    return sessions
