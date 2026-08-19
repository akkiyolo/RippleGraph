"""Graph-structural confidence calculation."""

from __future__ import annotations

import logging
import math

from ripplegraph.config import Settings
from ripplegraph.models.evidence import EvidenceLedger
from ripplegraph.models.query import TemporalMode

logger = logging.getLogger(__name__)


def calculate_confidence(
    ledger: EvidenceLedger,
    temporal_mode: TemporalMode,
    settings: Settings,
) -> float:
    """Calculate confidence from graph/evidence structure. Deterministic — no LLM."""
    w_corr = settings.confidence_corroboration_weight
    w_rec = settings.confidence_recency_weight
    w_contra = settings.confidence_contradiction_penalty
    w_ev = settings.confidence_evidence_weight

    total_sessions = set()
    for node in ledger.supporting_evidence + ledger.contradicting_evidence + ledger.superseded_evidence:
        if node.session_id:
            total_sessions.add(node.session_id)

    corroboration = ledger.distinct_supporting_sessions / len(total_sessions) if total_sessions else 0.0

    if temporal_mode == TemporalMode.CURRENT:
        active_count = sum(
            1 for n in ledger.supporting_evidence
            if not n.relation_from_parent or "SUPERSED" not in (n.relation_from_parent or "").upper()
        )
        recency = active_count / max(len(ledger.supporting_evidence), 1)
    elif temporal_mode == TemporalMode.HISTORICAL:
        recency = 0.8
    else:
        recency = 0.5

    if ledger.contradicting_evidence:
        contra_ratio = len(ledger.contradicting_evidence) / max(ledger.evidence_count, 1)
        contradiction_penalty = min(contra_ratio * 2, 1.0)
    else:
        contradiction_penalty = 0.0

    evidence_bonus = math.log(ledger.evidence_count + 1)

    confidence = w_corr * corroboration + w_rec * recency - w_contra * contradiction_penalty + w_ev * evidence_bonus
    confidence = max(0.0, min(1.0, confidence))

    logger.info("Confidence: %.3f (corr=%.2f, rec=%.2f, contra=%.2f, ev=%.2f)", confidence, corroboration, recency, contradiction_penalty, evidence_bonus)
    return confidence
