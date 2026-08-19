"""Evidence ledger builder — assembles auditable evidence from retrieval."""

from __future__ import annotations

import logging

from ripplegraph.models.evidence import EvidenceLedger, EvidenceNode

logger = logging.getLogger(__name__)


def build_evidence_ledger(
    query: str,
    evidence: list[EvidenceNode],
) -> EvidenceLedger:
    """Build an auditable evidence ledger from expanded and filtered evidence."""
    anchors = [n for n in evidence if n.hop == 0]
    supporting = [n for n in evidence if n.supports_answer and not n.contradicts_answer]
    contradicting = [n for n in evidence if n.contradicts_answer]
    superseded = [
        n for n in evidence
        if n.relation_from_parent and "SUPERSED" in (n.relation_from_parent or "").upper()
    ]

    # Count distinct supporting sessions
    supporting_sessions = set()
    for node in supporting:
        if node.session_id:
            supporting_sessions.add(node.session_id)

    traversal_path = [n.memory_id for n in evidence]

    ledger = EvidenceLedger(
        query=query,
        anchors=anchors,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        superseded_evidence=superseded,
        traversal_path=traversal_path,
        distinct_supporting_sessions=len(supporting_sessions),
        evidence_count=len(evidence),
    )

    logger.info(
        "Evidence ledger: %d anchors, %d supporting, %d contradicting, %d superseded",
        len(anchors),
        len(supporting),
        len(contradicting),
        len(superseded),
    )
    return ledger
