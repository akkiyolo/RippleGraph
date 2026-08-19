"""Unit tests for the segmenter."""

from datetime import datetime

from ripplegraph.ingestion.segmenter import segment_session
from ripplegraph.models.conversation import ConversationMessage, ConversationSession


def _make_msg(idx: int, text: str, minutes_offset: int = 0) -> ConversationMessage:
    return ConversationMessage(
        message_id=f"m{idx}",
        session_id="s1",
        speaker="user" if idx % 2 == 1 else "assistant",
        text=text,
        timestamp=datetime(2026, 3, 1, 10, minutes_offset),
    )


class TestSegmenter:
    def test_empty_session(self):
        session = ConversationSession(session_id="s1", user_id="u1", messages=[])
        segments = segment_session(session)
        assert segments == []

    def test_single_segment(self):
        msgs = [_make_msg(i, f"Message {i}", i) for i in range(1, 5)]
        session = ConversationSession(session_id="s1", user_id="u1", messages=msgs)
        segments = segment_session(session)
        assert len(segments) == 1
        assert len(segments[0].messages) == 4

    def test_state_change_boundary(self):
        msgs = [
            _make_msg(1, "Let's use MongoDB", 0),
            _make_msg(2, "OK", 1),
            _make_msg(3, "Actually, we switched to PostgreSQL", 2),
            _make_msg(4, "Got it", 3),
        ]
        session = ConversationSession(session_id="s1", user_id="u1", messages=msgs)
        segments = segment_session(session)
        assert len(segments) == 2

    def test_max_turns_boundary(self):
        msgs = [_make_msg(i, f"Message {i}", i) for i in range(1, 12)]
        session = ConversationSession(session_id="s1", user_id="u1", messages=msgs)
        segments = segment_session(session)
        assert len(segments) >= 2
