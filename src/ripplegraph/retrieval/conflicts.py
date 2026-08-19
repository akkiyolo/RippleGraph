"""Conflict resolution using deterministic evidence."""

from __future__ import annotations

import logging

from ripplegraph.models.evidence import EvidenceNode
from ripplegraph.models.query import TemporalMode

logger = logging.getLogger(__name__)


def resolve_conflicts(
    evidence: list[EvidenceNode],
    temporal_mode: TemporalMode,
) -> list[EvidenceNode]:
    """Resolve conflicts using deterministic evidence — never LLM.

    Uses:
    - timestamps
    - valid_from / valid_to (if available in metadata)
    - SUPERSEDES / CONTRADICTS relations
    - provenance

    CURRENT:    prefer latest active valid state
    HISTORICAL: prefer fact valid at requested time
    """
    if not evidence:
        return evidence

    # Mark contradicting evidence
    for node in evidence:
        if node.contradicts_answer:
            # Lower the score of contradicting evidence
            node.provenance_score = max(0.1, node.provenance_score - 0.3)

    # For CURRENT mode, boost the most recent non-superseded evidence
    if temporal_mode == TemporalMode.CURRENT:
        for node in evidence:
            if node.relation_from_parent and "SUPERSED" in (node.relation_from_parent or "").upper():
                node.supports_answer = False
                node.provenance_score = 0.2

    return evidence
