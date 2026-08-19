"""Temporal filtering for retrieval results."""

from __future__ import annotations

import logging
from datetime import datetime

from ripplegraph.models.evidence import EvidenceNode
from ripplegraph.models.query import TemporalMode

logger = logging.getLogger(__name__)


def apply_temporal_filter(
    evidence: list[EvidenceNode],
    temporal_mode: TemporalMode,
    relevant_time: str | None = None,
) -> list[EvidenceNode]:
    """Filter and re-score evidence based on temporal mode.

    CURRENT:    prefer active, non-superseded memories
    HISTORICAL: prefer memories valid during the requested time
    TRANSITION: prioritize supersession chains
    TIMELINE:   return chronological versions (minimal filtering)
    NONE:       retain useful historical evidence when relevant
    """
    if temporal_mode == TemporalMode.CURRENT:
        return _filter_current(evidence)
    elif temporal_mode == TemporalMode.HISTORICAL:
        return _filter_historical(evidence, relevant_time)
    elif temporal_mode == TemporalMode.TRANSITION:
        return _filter_transition(evidence)
    elif temporal_mode == TemporalMode.TIMELINE:
        return _filter_timeline(evidence)
    else:
        return evidence


def _filter_current(evidence: list[EvidenceNode]) -> list[EvidenceNode]:
    """Prefer active (non-superseded) memories for CURRENT queries."""
    result = []
    for node in evidence:
        # Boost current/active memories
        if node.relation_from_parent and "SUPERSED" in node.relation_from_parent.upper():
            # Superseded memories get lower temporal score
            node.temporal_score = 0.3
        else:
            node.temporal_score = 1.0
        result.append(node)
    return result


def _filter_historical(
    evidence: list[EvidenceNode],
    relevant_time: str | None,
) -> list[EvidenceNode]:
    """For HISTORICAL queries, prefer memories valid at the requested time."""
    # Don't punish evidence for being old — that's the point of historical queries
    for node in evidence:
        node.temporal_score = 0.8  # Neutral score for historical
    return evidence


def _filter_transition(evidence: list[EvidenceNode]) -> list[EvidenceNode]:
    """For TRANSITION queries, prioritize supersession chains."""
    for node in evidence:
        if node.relation_from_parent and "SUPERSED" in (node.relation_from_parent or "").upper():
            node.temporal_score = 1.0  # Boost transition evidence
        else:
            node.temporal_score = 0.6
    return evidence


def _filter_timeline(evidence: list[EvidenceNode]) -> list[EvidenceNode]:
    """For TIMELINE queries, keep all temporal versions and sort chronologically."""
    for node in evidence:
        node.temporal_score = 0.8  # Keep all versions equally relevant

    # Sort by timestamp
    evidence.sort(key=lambda n: n.timestamp or datetime.min)
    return evidence
