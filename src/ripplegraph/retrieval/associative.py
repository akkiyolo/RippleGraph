"""Associative graph expansion — THE CORE CONTRIBUTION of RippleGraph.

R0 = retrieve anchors
R1 = expand relevant graph neighbors of R0
R2 = expand relevant graph neighbors of R1
E  = R0 ∪ R1 ∪ R2

Then: deduplicate, temporal filter, conflict resolve, rank, build provenance.
"""

from __future__ import annotations

import logging
from typing import Any

from ripplegraph.clients.hydra_client import HydraClient
from ripplegraph.config import Settings
from ripplegraph.models.evidence import EvidenceNode

logger = logging.getLogger(__name__)


def expand_from_anchors(
    anchors: list[EvidenceNode],
    hydra: HydraClient,
    settings: Settings,
) -> list[EvidenceNode]:
    """Perform associative graph expansion outward from anchor memories.

    Algorithm:
    1. Start with anchor nodes (hop 0)
    2. For each hop up to max_hops:
       - For each frontier node, query HydraDB for relations
       - Score new nodes using relation_weight * hop_decay * anchor_score
       - Add to evidence set if score is above threshold
    3. Deduplicate across all hops

    Stop when:
    - max_hops reached
    - max_nodes reached
    - frontier relevance becomes too weak
    """
    max_hops = settings.ripple_max_hops
    max_nodes = settings.ripple_max_nodes
    decay_factor = settings.ripple_hop_decay

    all_evidence: dict[str, EvidenceNode] = {}
    traversal_path: list[str] = []

    # Add anchors
    for anchor in anchors:
        all_evidence[anchor.memory_id] = anchor
        traversal_path.append(anchor.memory_id)

    # Iterative expansion
    frontier = list(anchors)

    for hop in range(1, max_hops + 1):
        if len(all_evidence) >= max_nodes:
            logger.info("Max nodes (%d) reached at hop %d", max_nodes, hop)
            break

        hop_decay = decay_factor ** hop
        next_frontier: list[EvidenceNode] = []

        for parent in frontier:
            if len(all_evidence) >= max_nodes:
                break

            # Query HydraDB for relations from this node
            try:
                relations_result = hydra.get_relations(
                    source_id=parent.memory_id,
                    type_="memory",
                    limit=20,
                )

                if not relations_result or not hasattr(relations_result, "data"):
                    continue

                data = relations_result.data
                relations = getattr(data, "relations", []) or []

                for rel_group in relations:
                    if len(all_evidence) >= max_nodes:
                        break

                    # Extract target entity info
                    target = getattr(rel_group, "target", None)
                    if not target:
                        continue

                    target_name = getattr(target, "name", "")
                    chunk_id = getattr(rel_group, "chunk_id", "")

                    # Process individual relations within the group
                    inner_relations = getattr(rel_group, "relations", []) or []
                    for rel in inner_relations:
                        predicate = getattr(rel, "canonical_predicate", "") or getattr(rel, "raw_predicate", "")
                        context = getattr(rel, "context", "") or ""
                        confidence = float(getattr(rel, "confidence", 0.5) or 0.5)

                        # Calculate graph score
                        relation_weight = settings.get_relation_weight(predicate)
                        graph_score = relation_weight * hop_decay * parent.anchor_score

                        # Skip weak connections
                        if graph_score < 0.05:
                            continue

                        # Create evidence node for the related memory
                        node_id = chunk_id or f"{parent.memory_id}->{target_name}"

                        if node_id in all_evidence:
                            # Update score if better path found
                            existing = all_evidence[node_id]
                            if graph_score > existing.graph_score:
                                existing.graph_score = graph_score
                                existing.hop = hop
                                existing.relation_from_parent = predicate
                                existing.parent_id = parent.memory_id
                            continue

                        node = EvidenceNode(
                            memory_id=node_id,
                            text=context or f"{target_name} ({predicate})",
                            session_id=parent.session_id,
                            timestamp=parent.timestamp,
                            graph_score=graph_score,
                            anchor_score=parent.anchor_score * hop_decay,
                            hop=hop,
                            relation_from_parent=predicate,
                            parent_id=parent.memory_id,
                        )

                        # Mark based on relation type
                        if predicate.upper() in ("CONTRADICTS",):
                            node.contradicts_answer = True
                            node.supports_answer = False

                        all_evidence[node_id] = node
                        next_frontier.append(node)
                        traversal_path.append(node_id)

            except Exception as e:
                logger.warning(
                    "Failed to expand relations for %s: %s",
                    parent.memory_id,
                    e,
                )
                continue

        frontier = next_frontier

        if not frontier:
            logger.info("No more frontier nodes at hop %d", hop)
            break

    logger.info(
        "Expansion complete: %d total evidence nodes, %d hops traversed",
        len(all_evidence),
        min(hop, max_hops) if frontier or hop > 0 else 0,
    )
    return list(all_evidence.values())
