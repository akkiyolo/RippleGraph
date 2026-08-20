"""Associative graph expansion via PostgreSQL relations table.

R0 = anchor memories from full-text search
R1 = expand through relations from R0
R2 = expand through relations from R1
E  = R0 ∪ R1 ∪ R2  (deduplicated, scored)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ripplegraph.clients.pg_store import PgStore
from ripplegraph.config import Settings
from ripplegraph.models.evidence import EvidenceNode

logger = logging.getLogger(__name__)


def expand_from_anchors(
    anchors: list[EvidenceNode],
    store: PgStore,
    settings: Settings,
) -> list[EvidenceNode]:
    """Perform associative graph expansion from anchor memories through PostgreSQL relations."""
    max_hops = settings.ripple_max_hops
    max_nodes = settings.ripple_max_nodes
    decay_factor = settings.ripple_hop_decay

    all_evidence: dict[str, EvidenceNode] = {}

    # Add anchors
    for anchor in anchors:
        all_evidence[anchor.memory_id] = anchor

    # Iterative expansion
    frontier = list(anchors)

    for hop in range(1, max_hops + 1):
        if len(all_evidence) >= max_nodes:
            break

        hop_decay = decay_factor ** hop
        next_frontier: list[EvidenceNode] = []

        for parent in frontier:
            if len(all_evidence) >= max_nodes:
                break

            try:
                relations = store.get_relations(parent.memory_id, limit=20)

                for rel in relations:
                    if len(all_evidence) >= max_nodes:
                        break

                    target_id = rel["target_id"]
                    relation_type = rel["relation_type"]
                    target_text = rel.get("target_text") or rel.get("context", "")

                    if target_id in all_evidence:
                        # Update score if better path found
                        existing = all_evidence[target_id]
                        new_score = settings.get_relation_weight(relation_type) * hop_decay * parent.anchor_score
                        if new_score > existing.graph_score:
                            existing.graph_score = new_score
                            existing.hop = hop
                            existing.relation_from_parent = relation_type
                            existing.parent_id = parent.memory_id
                        continue

                    # Calculate graph score
                    relation_weight = settings.get_relation_weight(relation_type)
                    graph_score = relation_weight * hop_decay * parent.anchor_score

                    if graph_score < 0.05:
                        continue

                    # Parse timestamp
                    ts = rel.get("target_valid_from")
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(ts)
                        except Exception:
                            ts = None

                    node = EvidenceNode(
                        memory_id=target_id,
                        text=target_text or f"Related: {relation_type}",
                        session_id=rel.get("target_session_id", parent.session_id),
                        timestamp=ts or parent.timestamp,
                        graph_score=graph_score,
                        anchor_score=parent.anchor_score * hop_decay,
                        hop=hop,
                        relation_from_parent=relation_type,
                        parent_id=parent.memory_id,
                    )

                    if relation_type.upper() in ("CONTRADICTS",):
                        node.contradicts_answer = True
                        node.supports_answer = False

                    all_evidence[target_id] = node
                    next_frontier.append(node)

            except Exception as e:
                logger.warning("Failed to expand from %s: %s", parent.memory_id, e)
                continue

        frontier = next_frontier
        if not frontier:
            break

    logger.info("Expansion: %d evidence nodes across %d hops", len(all_evidence), min(hop, max_hops) if 'hop' in dir() else 0)
    return list(all_evidence.values())
