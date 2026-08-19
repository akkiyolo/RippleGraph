"""Unit tests for confidence calculation."""

from ripplegraph.retrieval.confidence import calculate_confidence
from ripplegraph.models.evidence import EvidenceLedger, EvidenceNode
from ripplegraph.models.query import TemporalMode
from ripplegraph.config import Settings


def _make_node(mid: str, sid: str, hop: int = 0) -> EvidenceNode:
    return EvidenceNode(memory_id=mid, text="test", session_id=sid, hop=hop)


class TestConfidence:
    def test_empty_evidence(self):
        settings = Settings(hydra_db_api_key="test")
        ledger = EvidenceLedger(query="test")
        conf = calculate_confidence(ledger, TemporalMode.NONE, settings)
        assert 0.0 <= conf <= 1.0

    def test_with_supporting_evidence(self):
        settings = Settings(hydra_db_api_key="test")
        nodes = [_make_node(f"m{i}", f"s{i}") for i in range(3)]
        ledger = EvidenceLedger(
            query="test",
            supporting_evidence=nodes,
            evidence_count=3,
            distinct_supporting_sessions=3,
        )
        conf = calculate_confidence(ledger, TemporalMode.CURRENT, settings)
        assert conf > 0.0

    def test_contradiction_lowers_confidence(self):
        settings = Settings(hydra_db_api_key="test")
        support = [_make_node("m1", "s1")]
        contra = [_make_node("m2", "s2")]
        contra[0].contradicts_answer = True

        ledger_clean = EvidenceLedger(
            query="test", supporting_evidence=support, evidence_count=1, distinct_supporting_sessions=1
        )
        ledger_contra = EvidenceLedger(
            query="test", supporting_evidence=support, contradicting_evidence=contra,
            evidence_count=2, distinct_supporting_sessions=1
        )
        conf_clean = calculate_confidence(ledger_clean, TemporalMode.NONE, settings)
        conf_contra = calculate_confidence(ledger_contra, TemporalMode.NONE, settings)
        assert conf_contra <= conf_clean
