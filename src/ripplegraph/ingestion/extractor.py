"""Memory extractor — converts conversation segments into durable memories."""

from __future__ import annotations

import logging
from typing import Any

from ripplegraph.clients.llm_client import LLMClient
from ripplegraph.models.conversation import ConversationSegment
from ripplegraph.models.memory import MemoryRecord, MemoryType, make_memory_id

logger = logging.getLogger(__name__)

# Noise phrases that should never become memories
NOISE_PHRASES = {
    "hello", "hi", "hey", "thanks", "thank you", "okay", "ok", "cool",
    "sure", "yes", "no", "bye", "goodbye", "great", "got it", "understood",
    "alright", "right", "yep", "nope", "mm", "hmm", "uh",
}

# Minimum importance to pass the write gate
IMPORTANCE_THRESHOLD = 0.3


def _is_noise(text: str) -> bool:
    """Return True if the text is low-value filler."""
    stripped = text.strip().lower().rstrip(".!?")
    return stripped in NOISE_PHRASES or len(stripped) < 5


def _segment_to_text(segment: ConversationSegment) -> str:
    """Convert a segment's messages into readable text."""
    lines = []
    for msg in segment.messages:
        lines.append(f"[{msg.speaker}]: {msg.text}")
    return "\n".join(lines)


def extract_memories(
    segment: ConversationSegment,
    llm: LLMClient,
) -> list[MemoryRecord]:
    """Extract durable memories from a conversation segment using LLM.

    Steps:
    1. Convert segment to text
    2. Skip if all messages are noise
    3. Call LLM for structured extraction
    4. Validate and filter by importance gate
    5. Generate stable IDs
    """
    # Skip entirely-noisy segments
    non_noise = [m for m in segment.messages if not _is_noise(m.text)]
    if not non_noise:
        logger.debug("Skipping noise-only segment %s", segment.segment_id)
        return []

    segment_text = _segment_to_text(segment)

    # LLM extraction
    raw_memories = llm.extract_memories(segment_text, segment.session_id)

    memories: list[MemoryRecord] = []
    for raw in raw_memories:
        try:
            # Validate memory type
            mem_type = raw.get("type", "FACT").upper()
            if mem_type not in MemoryType.__members__:
                mem_type = "FACT"

            importance = float(raw.get("importance", 0.5))

            # Importance / write gate
            if importance < IMPORTANCE_THRESHOLD:
                logger.debug("Skipping low-importance memory: %s", raw.get("text", "")[:50])
                continue

            subject = raw.get("subject", "unknown")
            predicate = raw.get("predicate", "unknown")
            text = raw.get("text", "")

            if not text:
                continue

            memory_id = make_memory_id(
                session_id=segment.session_id,
                subject=subject,
                predicate=predicate,
                content=text,
            )

            source_msg_ids = [m.message_id for m in segment.messages]

            memory = MemoryRecord(
                id=memory_id,
                type=MemoryType(mem_type),
                subject=subject,
                predicate=predicate,
                object=raw.get("object"),
                text=text,
                user_id=segment.user_id,
                session_id=segment.session_id,
                source_message_ids=source_msg_ids,
                created_at=segment.end_time,
                valid_from=segment.start_time,
                confidence=1.0,
                importance=importance,
            )
            memories.append(memory)

        except Exception as e:
            logger.warning("Failed to parse memory: %s — %s", raw, e)
            continue

    logger.info(
        "Extracted %d memories from segment %s",
        len(memories),
        segment.segment_id,
    )
    return memories
