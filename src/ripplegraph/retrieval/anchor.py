"""Anchor retrieval — PostgreSQL full-text search for initial memories."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ripplegraph.clients.pg_store import PgStore
from ripplegraph.models.evidence import EvidenceNode
from ripplegraph.models.query import QueryPlan

logger = logging.getLogger(__name__)


def retrieve_anchors(
    plan: QueryPlan,
    store: PgStore,
    max_anchors: int = 5,
) -> list[EvidenceNode]:
    """Retrieve initial high-quality memories via PostgreSQL full-text search."""
    results = store.search_memories(
        query=plan.original_query,
        max_results=max_anchors,
    )

    anchors: list[EvidenceNode] = []
    for row in results:
        ts = row.get("valid_from") or row.get("created_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except Exception:
                ts = None

        score = float(row.get("rank", 0.5))

        node = EvidenceNode(
            memory_id=row["id"],
            text=row["text"],
            session_id=row.get("session_id", ""),
            timestamp=ts,
            anchor_score=score,
            semantic_score=score,
            hop=0,
        )
        anchors.append(node)

    logger.info("Retrieved %d anchors for: %s", len(anchors), plan.original_query[:50])
    return anchors
