"""Temporal memory management — supersession and contradiction detection."""

from __future__ import annotations

import logging
from datetime import datetime

from ripplegraph.clients.llm_client import LLMClient
from ripplegraph.models.memory import MemoryRecord

logger = logging.getLogger(__name__)


def detect_supersession(
    new_memory: MemoryRecord,
    existing_memories: list[MemoryRecord],
    llm: LLMClient | None = None,
) -> MemoryRecord | None:
    """Detect if a new memory supersedes an existing one.

    A supersession candidate must have:
    - Same subject (case-insensitive)
    - Same predicate (case-insensitive)
    - Different object/text
    - Newer timestamp

    Returns the superseded memory, or None.
    """
    candidates = []
    for existing in existing_memories:
        if (
            existing.subject.lower().strip() == new_memory.subject.lower().strip()
            and existing.predicate.lower().strip() == new_memory.predicate.lower().strip()
            and existing.text.lower().strip() != new_memory.text.lower().strip()
            and existing.id != new_memory.id
        ):
            # Check temporal ordering
            new_time = new_memory.valid_from or new_memory.created_at
            old_time = existing.valid_from or existing.created_at
            if new_time >= old_time:
                candidates.append(existing)

    if not candidates:
        return None

    # Sort by time — supersede the most recent predecessor
    candidates.sort(
        key=lambda m: m.valid_from or m.created_at,
        reverse=True,
    )
    target = candidates[0]

    # Deterministic check is sufficient for clear cases
    # Use LLM only for ambiguous cases
    if llm and _is_ambiguous(new_memory, target):
        verified = llm.verify_supersession(
            old_text=target.text,
            new_text=new_memory.text,
            subject=new_memory.subject,
            predicate=new_memory.predicate,
        )
        if not verified:
            return None

    logger.info(
        "Supersession detected: %s supersedes %s",
        new_memory.id,
        target.id,
        extra={"memory_id": new_memory.id},
    )
    return target


def _is_ambiguous(new: MemoryRecord, old: MemoryRecord) -> bool:
    """Heuristic: is the supersession ambiguous enough to need LLM verification?"""
    # If objects are clearly different, it's unambiguous
    if new.object and old.object and new.object.lower() != old.object.lower():
        return False
    # If text similarity is high but not identical, it's ambiguous
    return True


def apply_supersession(
    new_memory: MemoryRecord,
    superseded: MemoryRecord,
) -> tuple[MemoryRecord, MemoryRecord]:
    """Apply supersession: update validity intervals and link memories.

    Returns (updated_new, updated_old) with temporal markers set.
    """
    transition_time = new_memory.valid_from or new_memory.created_at

    # Mark old memory as no longer valid
    superseded.valid_to = transition_time

    # Link new memory to old
    new_memory.supersedes_id = superseded.id
    new_memory.valid_from = transition_time

    return new_memory, superseded


def detect_contradiction(
    new_memory: MemoryRecord,
    existing_memories: list[MemoryRecord],
) -> list[MemoryRecord]:
    """Detect contradictions: incompatible states with overlapping validity.

    Contradiction != supersession. A contradiction means two facts
    claim incompatible states for overlapping time periods.
    """
    contradictions = []
    for existing in existing_memories:
        if existing.id == new_memory.id:
            continue

        # Same subject and predicate
        if (
            existing.subject.lower().strip() == new_memory.subject.lower().strip()
            and existing.predicate.lower().strip() == new_memory.predicate.lower().strip()
        ):
            # Different claims
            if existing.text.lower().strip() != new_memory.text.lower().strip():
                # Check temporal overlap
                if _has_temporal_overlap(new_memory, existing):
                    # Already linked as supersession? Not a contradiction.
                    if (
                        new_memory.supersedes_id == existing.id
                        or existing.supersedes_id == new_memory.id
                    ):
                        continue
                    contradictions.append(existing)

    if contradictions:
        new_memory.contradicts_ids = [c.id for c in contradictions]
        logger.info(
            "Contradictions detected for %s: %s",
            new_memory.id,
            [c.id for c in contradictions],
        )

    return contradictions


def _has_temporal_overlap(a: MemoryRecord, b: MemoryRecord) -> bool:
    """Check if two memories have overlapping validity periods."""
    a_from = a.valid_from or a.created_at
    a_to = a.valid_to  # None means still active
    b_from = b.valid_from or b.created_at
    b_to = b.valid_to

    # If either has no end, they potentially overlap
    if a_to is None and b_to is None:
        return True
    if a_to is None:
        return b_to is None or b_to >= a_from
    if b_to is None:
        return a_to >= b_from

    return a_from <= b_to and b_from <= a_to
