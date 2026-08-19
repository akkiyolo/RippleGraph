"""Evaluation runner — tests RippleGraph against the eval dataset."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ripplegraph.clients.hydra_client import HydraClient
from ripplegraph.clients.llm_client import LLMClient
from ripplegraph.config import Settings
from ripplegraph.retrieval.query import execute_query

logger = logging.getLogger(__name__)


def run_evaluation(
    eval_path: str | Path,
    hydra: HydraClient,
    llm: LLMClient,
    settings: Settings,
) -> dict[str, Any]:
    """Run all eval queries and produce a results report."""
    eval_path = Path(eval_path)
    with open(eval_path) as f:
        queries = json.load(f)

    results = []
    total = len(queries)
    correct_status = 0
    correct_content = 0
    correct_temporal = 0

    for q in queries:
        qid = q["id"]
        question = q["question"]
        expected_status = q["expected_status"]
        expected_contains = q.get("expected_answer_contains", [])
        expected_temporal = q.get("expected_temporal_mode", "")

        logger.info("Eval [%s]: %s", qid, question)

        result = execute_query(question, hydra, llm, settings)

        # Status check
        status_match = result.status.value == expected_status
        if status_match:
            correct_status += 1

        # Content check
        content_match = True
        if expected_contains and result.answer:
            answer_lower = result.answer.lower()
            content_match = all(kw.lower() in answer_lower for kw in expected_contains)
        elif expected_contains and not result.answer:
            content_match = False
        if content_match:
            correct_content += 1

        # Temporal mode check
        temporal_match = result.temporal_mode == expected_temporal if expected_temporal else True
        if temporal_match:
            correct_temporal += 1

        results.append({
            "id": qid,
            "question": question,
            "category": q.get("category", ""),
            "expected_status": expected_status,
            "actual_status": result.status.value,
            "status_match": status_match,
            "expected_contains": expected_contains,
            "actual_answer": result.answer,
            "content_match": content_match,
            "expected_temporal": expected_temporal,
            "actual_temporal": result.temporal_mode,
            "temporal_match": temporal_match,
            "confidence": result.confidence,
            "evidence_count": len(result.evidence),
            "latency_ms": result.latency_ms,
        })

    report = {
        "total": total,
        "status_accuracy": correct_status / total if total else 0,
        "content_accuracy": correct_content / total if total else 0,
        "temporal_accuracy": correct_temporal / total if total else 0,
        "results": results,
    }

    logger.info(
        "Evaluation: status=%.0f%%, content=%.0f%%, temporal=%.0f%%",
        report["status_accuracy"] * 100,
        report["content_accuracy"] * 100,
        report["temporal_accuracy"] * 100,
    )
    return report
