"""Complete query pipeline orchestrator — PostgreSQL backed."""

from __future__ import annotations

import logging
import time

from ripplegraph.clients.llm_client import LLMClient
from ripplegraph.clients.pg_store import PgStore
from ripplegraph.config import Settings
from ripplegraph.models.results import QueryResult, QueryStatus
from ripplegraph.retrieval.anchor import retrieve_anchors
from ripplegraph.retrieval.associative import expand_from_anchors
from ripplegraph.retrieval.confidence import calculate_confidence
from ripplegraph.retrieval.conflicts import resolve_conflicts
from ripplegraph.retrieval.evidence import build_evidence_ledger
from ripplegraph.retrieval.planner import plan_query
from ripplegraph.retrieval.temporal import apply_temporal_filter

logger = logging.getLogger(__name__)


def execute_query(
    question: str,
    store: PgStore,
    llm: LLMClient,
    settings: Settings,
) -> QueryResult:
    """Execute the complete RippleGraph query pipeline.

    Pipeline:
    1. Query Planning (temporal mode + entities)
    2. Anchor Retrieval (PostgreSQL full-text search)
    3. Associative Graph Expansion (PostgreSQL relations)
    4. Temporal Filtering
    5. Conflict Resolution
    6. Evidence Ledger
    7. Confidence Calculation
    8. Abstention Gate (BEFORE answer generation)
    9. Answer Generation (ONLY if gate passes)
    """
    start = time.time()

    # 1. Plan
    plan = plan_query(question, llm)
    logger.info("Query plan: mode=%s, entities=%s", plan.temporal_mode, plan.entities)

    # 2. Anchor retrieval
    anchors = retrieve_anchors(plan, store, max_anchors=5)

    # 3. Associative expansion
    evidence = expand_from_anchors(anchors, store, settings)

    # 4. Temporal filtering
    evidence = apply_temporal_filter(evidence, plan.temporal_mode, plan.relevant_time)

    # 5. Conflict resolution
    evidence = resolve_conflicts(evidence, plan.temporal_mode)

    # 6. Evidence ledger
    ledger = build_evidence_ledger(question, evidence)

    # 7. Confidence
    confidence = calculate_confidence(ledger, plan.temporal_mode, settings)

    latency_ms = (time.time() - start) * 1000

    # 8. Abstention gate — BEFORE answer generation
    if confidence < settings.abstention_threshold or ledger.evidence_count < settings.min_evidence_count:
        reason = "insufficient evidence"
        if confidence < settings.abstention_threshold:
            reason = f"confidence {confidence:.2f} below threshold {settings.abstention_threshold}"
        elif ledger.evidence_count < settings.min_evidence_count:
            reason = f"evidence count {ledger.evidence_count} below minimum {settings.min_evidence_count}"

        logger.info("ABSTAINED: %s", reason)
        return QueryResult(
            question=question,
            status=QueryStatus.ABSTAINED,
            answer=None,
            confidence=confidence,
            reason=reason,
            evidence=evidence,
            traversal_path=ledger.traversal_path,
            temporal_mode=plan.temporal_mode.value,
            latency_ms=latency_ms,
        )

    # 9. Generate answer — ONLY from evidence
    evidence_text = _format_evidence_for_llm(ledger)
    answer = llm.generate_answer(evidence_text, question)

    latency_ms = (time.time() - start) * 1000

    return QueryResult(
        question=question,
        status=QueryStatus.ANSWERED,
        answer=answer,
        confidence=confidence,
        evidence=evidence,
        traversal_path=ledger.traversal_path,
        temporal_mode=plan.temporal_mode.value,
        latency_ms=latency_ms,
    )


def _format_evidence_for_llm(ledger) -> str:
    """Format the evidence ledger for the LLM answer generation prompt."""
    lines = []
    for i, node in enumerate(ledger.supporting_evidence, 1):
        session_info = f" [session: {node.session_id}]" if node.session_id else ""
        lines.append(f"[{i}]{session_info} {node.text}")

    if ledger.contradicting_evidence:
        lines.append("\n--- Contradicting evidence ---")
        for node in ledger.contradicting_evidence:
            lines.append(f"[CONTRADICTS] {node.text}")

    if ledger.superseded_evidence:
        lines.append("\n--- Superseded (historical) evidence ---")
        for node in ledger.superseded_evidence:
            lines.append(f"[SUPERSEDED] {node.text}")

    return "\n".join(lines)
