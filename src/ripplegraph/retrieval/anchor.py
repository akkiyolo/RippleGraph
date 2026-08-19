"""Anchor retrieval — high-quality initial memory retrieval."""

from __future__ import annotations

import logging
from typing import Any

from ripplegraph.clients.hydra_client import HydraClient
from ripplegraph.models.evidence import EvidenceNode
from ripplegraph.models.query import QueryPlan

logger = logging.getLogger(__name__)


def retrieve_anchors(
    plan: QueryPlan,
    hydra: HydraClient,
    max_anchors: int = 5,
) -> list[EvidenceNode]:
    """Retrieve a small number of high-quality initial memories.

    Uses HydraDB's semantic/hybrid search to find the best starting
    points for graph expansion. Does NOT perform graph expansion.
    """
    result = hydra.query(
        query=plan.original_query,
        max_results=max_anchors,
        graph_context=True,
        mode="thinking",
    )

    anchors: list[EvidenceNode] = []
    if not result or not result.data:
        return anchors

    chunks = result.data.chunks or []
    for i, chunk in enumerate(chunks):
        # Extract metadata from the chunk
        chunk_id = getattr(chunk, "id", "") or getattr(chunk, "chunk_id", "") or f"chunk-{i}"
        text = getattr(chunk, "text", "") or getattr(chunk, "content", "") or ""
        score = getattr(chunk, "score", 0.0) or getattr(chunk, "relevance_score", 0.0) or 0.0

        # Extract additional metadata
        add_meta = getattr(chunk, "additional_metadata", {}) or {}
        if isinstance(add_meta, str):
            import json
            try:
                add_meta = json.loads(add_meta)
            except Exception:
                add_meta = {}

        session_id = add_meta.get("session_id", "")
        source_id = getattr(chunk, "source_id", "") or add_meta.get("source_id", chunk_id)

        # Parse timestamp
        ts = None
        ts_str = add_meta.get("created_at", "")
        if ts_str:
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(ts_str)
            except Exception:
                pass

        node = EvidenceNode(
            memory_id=source_id,
            text=text,
            session_id=session_id,
            timestamp=ts,
            anchor_score=float(score),
            semantic_score=float(score),
            hop=0,
        )
        anchors.append(node)

    logger.info(
        "Retrieved %d anchors for query: %s",
        len(anchors),
        plan.original_query[:50],
    )
    return anchors
