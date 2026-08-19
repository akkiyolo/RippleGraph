"""Deterministic conversation segmenter.

Groups conversation turns into coherent segments using
boundary signals — no LLM required for the MVP.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from ripplegraph.models.conversation import (
    ConversationMessage,
    ConversationSegment,
    ConversationSession,
)

logger = logging.getLogger(__name__)

# State-change phrases that signal a topic boundary
STATE_CHANGE_PHRASES = [
    "actually",
    "instead",
    "switched to",
    "no longer",
    "now using",
    "changed to",
    "decided to",
    "moved to",
    "replaced",
    "swapped",
    "migrated to",
    "transitioned to",
]

# Max turns per segment
MAX_TURNS_PER_SEGMENT = 8

# Timestamp gap that triggers a boundary (minutes)
TIME_GAP_MINUTES = 30


def _has_state_change(text: str) -> bool:
    """Check if a message contains a state-change phrase."""
    lower = text.lower()
    return any(phrase in lower for phrase in STATE_CHANGE_PHRASES)


def _has_time_gap(prev: ConversationMessage, curr: ConversationMessage) -> bool:
    """Check if there's a large timestamp gap between messages."""
    gap = abs((curr.timestamp - prev.timestamp).total_seconds())
    return gap > TIME_GAP_MINUTES * 60


def segment_session(session: ConversationSession) -> list[ConversationSegment]:
    """Split a session into coherent conversation segments.

    Boundary signals:
    1. Maximum number of turns reached
    2. Large timestamp gap between messages
    3. State-change phrases detected
    """
    if not session.messages:
        return []

    segments: list[ConversationSegment] = []
    current_messages: list[ConversationMessage] = []
    boundary_reason = "session_start"
    seg_idx = 0

    for i, msg in enumerate(session.messages):
        # Check boundary conditions (skip for first message)
        if current_messages:
            should_split = False
            reason = ""

            # 1. Max turns
            if len(current_messages) >= MAX_TURNS_PER_SEGMENT:
                should_split = True
                reason = "max_turns"

            # 2. Time gap
            elif _has_time_gap(current_messages[-1], msg):
                should_split = True
                reason = "time_gap"

            # 3. State change in current message
            elif _has_state_change(msg.text):
                should_split = True
                reason = "state_change"

            if should_split:
                # Flush current segment
                segments.append(
                    ConversationSegment(
                        segment_id=f"{session.session_id}-seg-{seg_idx}",
                        session_id=session.session_id,
                        user_id=session.user_id,
                        messages=current_messages,
                        start_time=current_messages[0].timestamp,
                        end_time=current_messages[-1].timestamp,
                        boundary_reason=boundary_reason,
                    )
                )
                seg_idx += 1
                current_messages = []
                boundary_reason = reason

        current_messages.append(msg)

    # Flush remaining
    if current_messages:
        segments.append(
            ConversationSegment(
                segment_id=f"{session.session_id}-seg-{seg_idx}",
                session_id=session.session_id,
                user_id=session.user_id,
                messages=current_messages,
                start_time=current_messages[0].timestamp,
                end_time=current_messages[-1].timestamp,
                boundary_reason=boundary_reason,
            )
        )

    logger.info(
        "Segmented session %s into %d segments",
        session.session_id,
        len(segments),
    )
    return segments
