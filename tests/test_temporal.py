"""Unit tests for temporal logic (supersession & contradiction)."""

from datetime import datetime

from ripplegraph.ingestion.temporal import detect_supersession, detect_contradiction, apply_supersession
from ripplegraph.models.memory import MemoryRecord, MemoryType


def _make_memory(
    mid: str, subject: str, predicate: str, text: str, time_str: str, obj: str = ""
) -> MemoryRecord:
    return MemoryRecord(
        id=mid,
        type=MemoryType.FACT,
        subject=subject,
        predicate=predicate,
        object=obj,
        text=text,
        user_id="demo-user",
        session_id="s1",
        valid_from=datetime.fromisoformat(time_str),
        created_at=datetime.fromisoformat(time_str),
    )


class TestSupersession:
    def test_detects_supersession(self):
        old = _make_memory("m1", "project", "database", "Uses MongoDB", "2026-03-01T10:00:00", "MongoDB")
        new = _make_memory("m2", "project", "database", "Uses PostgreSQL", "2026-04-15T10:00:00", "PostgreSQL")
        result = detect_supersession(new, [old])
        assert result is not None
        assert result.id == "m1"

    def test_no_supersession_same_text(self):
        old = _make_memory("m1", "project", "database", "Uses MongoDB", "2026-03-01T10:00:00")
        new = _make_memory("m2", "project", "database", "Uses MongoDB", "2026-04-01T10:00:00")
        result = detect_supersession(new, [old])
        assert result is None

    def test_no_supersession_different_subject(self):
        old = _make_memory("m1", "frontend", "database", "Uses MongoDB", "2026-03-01T10:00:00")
        new = _make_memory("m2", "backend", "database", "Uses PostgreSQL", "2026-04-01T10:00:00")
        result = detect_supersession(new, [old])
        assert result is None


class TestApplySupersession:
    def test_applies_correctly(self):
        old = _make_memory("m1", "project", "database", "Uses MongoDB", "2026-03-01T10:00:00")
        new = _make_memory("m2", "project", "database", "Uses PostgreSQL", "2026-04-15T10:00:00")
        new_updated, old_updated = apply_supersession(new, old)
        assert new_updated.supersedes_id == "m1"
        assert old_updated.valid_to is not None


class TestContradiction:
    def test_detects_contradiction(self):
        m1 = _make_memory("m1", "project", "database", "Uses MongoDB", "2026-03-01T10:00:00")
        m2 = _make_memory("m2", "project", "database", "Uses PostgreSQL", "2026-03-01T10:00:00")
        contradictions = detect_contradiction(m2, [m1])
        assert len(contradictions) == 1

    def test_no_contradiction_when_superseded(self):
        m1 = _make_memory("m1", "project", "database", "Uses MongoDB", "2026-03-01T10:00:00")
        m2 = _make_memory("m2", "project", "database", "Uses PostgreSQL", "2026-04-15T10:00:00")
        m2.supersedes_id = "m1"
        contradictions = detect_contradiction(m2, [m1])
        assert len(contradictions) == 0
