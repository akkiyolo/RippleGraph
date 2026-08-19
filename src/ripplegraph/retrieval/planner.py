"""Query planner — determines entities, intent, and temporal mode."""

from __future__ import annotations

import logging
import re

from ripplegraph.clients.llm_client import LLMClient
from ripplegraph.models.query import QueryPlan, TemporalMode

logger = logging.getLogger(__name__)

# Deterministic temporal keywords
CURRENT_KEYWORDS = ["now", "currently", "current", "right now", "at the moment", "today", "presently"]
HISTORICAL_KEYWORDS = ["before", "previously", "used to", "was", "were", "back then", "earlier", "in march", "in january", "last year", "ago"]
TRANSITION_KEYWORDS = ["when did", "switch", "change", "transition", "move from", "migrate"]
TIMELINE_KEYWORDS = ["over time", "history", "timeline", "have we", "have I", "all the", "considered"]


def plan_query(query: str, llm: LLMClient | None = None) -> QueryPlan:
    """Plan a query by detecting entities, intent, and temporal mode.

    Uses deterministic keyword matching first; falls back to LLM
    only for genuinely ambiguous queries.
    """
    lower = query.lower()

    # Deterministic temporal mode detection
    temporal_mode = _detect_temporal_mode(lower)

    # If deterministic detection worked, skip LLM
    if temporal_mode != TemporalMode.NONE or llm is None:
        entities = _extract_entities_simple(query)
        return QueryPlan(
            original_query=query,
            entities=entities,
            intent=query,
            temporal_mode=temporal_mode,
        )

    # LLM fallback for ambiguous queries
    try:
        result = llm.classify_query(query)
        mode_str = result.get("temporal_mode", "NONE").upper()
        if mode_str in TemporalMode.__members__:
            temporal_mode = TemporalMode(mode_str)
        return QueryPlan(
            original_query=query,
            entities=result.get("entities", []),
            intent=result.get("intent", query),
            temporal_mode=temporal_mode,
            relevant_time=result.get("relevant_time"),
        )
    except Exception as e:
        logger.warning("LLM query classification failed: %s", e)
        return QueryPlan(
            original_query=query,
            entities=_extract_entities_simple(query),
            intent=query,
            temporal_mode=TemporalMode.NONE,
        )


def _detect_temporal_mode(lower_query: str) -> TemporalMode:
    """Deterministic temporal mode detection from keywords."""
    for kw in TRANSITION_KEYWORDS:
        if kw in lower_query:
            return TemporalMode.TRANSITION

    for kw in TIMELINE_KEYWORDS:
        if kw in lower_query:
            return TemporalMode.TIMELINE

    for kw in CURRENT_KEYWORDS:
        if kw in lower_query:
            return TemporalMode.CURRENT

    for kw in HISTORICAL_KEYWORDS:
        if kw in lower_query:
            return TemporalMode.HISTORICAL

    return TemporalMode.NONE


def _extract_entities_simple(query: str) -> list[str]:
    """Simple entity extraction using capitalization heuristics."""
    words = query.split()
    entities = []
    for word in words:
        cleaned = word.strip("?.,!\"'")
        if cleaned and cleaned[0].isupper() and len(cleaned) > 2:
            if cleaned.lower() not in {"what", "when", "where", "who", "why", "how", "the", "are", "was", "did"}:
                entities.append(cleaned)
    return entities
