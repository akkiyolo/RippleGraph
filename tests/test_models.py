"""Unit tests for core domain models."""

from datetime import datetime

from ripplegraph.models.memory import MemoryRecord, MemoryType, make_memory_id
from ripplegraph.models.evidence import EvidenceNode, EvidenceLedger
from ripplegraph.models.query import QueryPlan, TemporalMode
from ripplegraph.models.results import QueryResult, QueryStatus


class TestMakeMemoryId:
    def test_deterministic(self):
        id1 = make_memory_id("s1", "user", "prefers", "PostgreSQL")
        id2 = make_memory_id("s1", "user", "prefers", "PostgreSQL")
        assert id1 == id2

    def test_different_inputs(self):
        id1 = make_memory_id("s1", "user", "prefers", "PostgreSQL")
        id2 = make_memory_id("s1", "user", "prefers", "MongoDB")
        assert id1 != id2

    def test_case_insensitive(self):
        id1 = make_memory_id("s1", "User", "Prefers", "PostgreSQL")
        id2 = make_memory_id("s1", "user", "prefers", "postgresql")
        assert id1 == id2

    def test_format(self):
        mid = make_memory_id("s1", "user", "prefers", "pg")
        assert mid.startswith("mem-")
        assert len(mid) == 20  # "mem-" + 16 hex chars


class TestMemoryRecord:
    def test_create(self):
        mem = MemoryRecord(
            id="mem-123",
            type=MemoryType.FACT,
            subject="project",
            predicate="uses_database",
            object="PostgreSQL",
            text="The project uses PostgreSQL.",
            user_id="demo-user",
            session_id="session-3",
        )
        assert mem.type == MemoryType.FACT
        assert mem.subject == "project"


class TestEvidenceLedger:
    def test_empty_ledger(self):
        ledger = EvidenceLedger(query="test")
        assert ledger.evidence_count == 0

    def test_with_evidence(self):
        node = EvidenceNode(
            memory_id="m1",
            text="test",
            session_id="s1",
        )
        ledger = EvidenceLedger(
            query="test",
            anchors=[node],
            supporting_evidence=[node],
            evidence_count=1,
            distinct_supporting_sessions=1,
        )
        assert ledger.evidence_count == 1


class TestQueryPlan:
    def test_default(self):
        plan = QueryPlan(original_query="test")
        assert plan.temporal_mode == TemporalMode.NONE

    def test_with_mode(self):
        plan = QueryPlan(
            original_query="What db do we use now?",
            temporal_mode=TemporalMode.CURRENT,
        )
        assert plan.temporal_mode == TemporalMode.CURRENT


class TestQueryResult:
    def test_answered(self):
        result = QueryResult(
            question="test?",
            status=QueryStatus.ANSWERED,
            answer="PostgreSQL",
            confidence=0.85,
        )
        assert result.status == QueryStatus.ANSWERED

    def test_abstained(self):
        result = QueryResult(
            question="test?",
            status=QueryStatus.ABSTAINED,
            confidence=0.2,
            reason="low confidence",
        )
        assert result.answer is None
