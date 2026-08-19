"""End-to-end ingestion orchestrator."""

from __future__ import annotations

import json
import logging
from typing import Any

from ripplegraph.clients.hydra_client import HydraClient
from ripplegraph.clients.llm_client import LLMClient
from ripplegraph.ingestion.extractor import extract_memories
from ripplegraph.ingestion.segmenter import segment_session
from ripplegraph.ingestion.temporal import (
    apply_supersession,
    detect_contradiction,
    detect_supersession,
)
from ripplegraph.models.conversation import ConversationSession
from ripplegraph.models.memory import MemoryRecord

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates the full ingestion pipeline:
    sessions → segments → memories → temporal processing → HydraDB.
    """

    def __init__(self, hydra: HydraClient, llm: LLMClient) -> None:
        self.hydra = hydra
        self.llm = llm
        self._all_memories: list[MemoryRecord] = []

    def ingest_sessions(self, sessions: list[ConversationSession]) -> list[MemoryRecord]:
        """Process multiple sessions through the complete pipeline."""
        all_memories: list[MemoryRecord] = []

        for session in sessions:
            session_memories = self._ingest_session(session)
            all_memories.extend(session_memories)

        self._all_memories = all_memories
        logger.info("Total memories after ingestion: %d", len(all_memories))
        return all_memories

    def _ingest_session(self, session: ConversationSession) -> list[MemoryRecord]:
        """Process a single session: segment → extract → temporal → store."""
        # 1. Segment
        segments = segment_session(session)

        # 2. Extract memories from each segment
        session_memories: list[MemoryRecord] = []
        for segment in segments:
            memories = extract_memories(segment, self.llm)
            session_memories.extend(memories)

        # 3. Temporal processing
        for memory in session_memories:
            # Check for supersession against all known memories
            superseded = detect_supersession(memory, self._all_memories, self.llm)
            if superseded:
                memory, superseded = apply_supersession(memory, superseded)
                # Update the superseded memory in our collection
                for i, m in enumerate(self._all_memories):
                    if m.id == superseded.id:
                        self._all_memories[i] = superseded
                        break

            # Check for contradictions
            detect_contradiction(memory, self._all_memories)

            self._all_memories.append(memory)

        # 4. Store in HydraDB
        self._store_memories(session_memories)

        return session_memories

    def _store_memories(self, memories: list[MemoryRecord]) -> None:
        """Store memories in HydraDB with graph relations."""
        if not memories:
            return

        # Build memory items for batch ingestion
        memory_items: list[dict[str, Any]] = []
        graph_payload: dict[str, Any] = {}

        for mem in memories:
            # Build the memory item
            item: dict[str, Any] = {
                "id": mem.id,
                "text": mem.text,
                "infer": False,
                "additional_metadata": {
                    "memory_type": mem.type.value,
                    "subject": mem.subject,
                    "predicate": mem.predicate,
                    "object": mem.object or "",
                    "session_id": mem.session_id,
                    "user_id": mem.user_id,
                    "created_at": mem.created_at.isoformat(),
                    "valid_from": mem.valid_from.isoformat() if mem.valid_from else "",
                    "valid_to": mem.valid_to.isoformat() if mem.valid_to else "",
                    "importance": str(mem.importance),
                    "supersedes_id": mem.supersedes_id or "",
                    "contradicts_ids": json.dumps(mem.contradicts_ids),
                },
            }

            # Build forceful relations
            relation_ids = []
            if mem.supersedes_id:
                relation_ids.append(mem.supersedes_id)
            for cid in mem.contradicts_ids:
                relation_ids.append(cid)
            if relation_ids:
                item["relations"] = {"ids": relation_ids}

            memory_items.append(item)

            # Build BYOG graph payload for this memory
            entities: dict[str, Any] = {
                "subject": {
                    "name": mem.subject,
                    "type": "ENTITY",
                    "namespace": "ripplegraph",
                },
            }
            relations_list: list[dict[str, Any]] = []

            if mem.object:
                entities["object"] = {
                    "name": mem.object,
                    "type": "VALUE",
                    "namespace": "ripplegraph",
                }
                relations_list.append({
                    "source": "subject",
                    "target": "object",
                    "predicate": mem.predicate.upper(),
                    "context": mem.text,
                    "temporal_details": (
                        f"from {mem.valid_from.isoformat()}" if mem.valid_from else ""
                    ),
                })

            if mem.supersedes_id:
                entities["superseded"] = {
                    "name": f"superseded:{mem.supersedes_id}",
                    "type": "MEMORY_REF",
                    "namespace": "ripplegraph",
                }
                relations_list.append({
                    "source": "subject",
                    "target": "superseded",
                    "predicate": "SUPERSEDES",
                    "context": f"This memory supersedes {mem.supersedes_id}",
                })

            if relations_list:
                graph_payload[mem.id] = {
                    "entities": entities,
                    "relations": relations_list,
                }

        # Batch ingest
        try:
            self.hydra.ingest_memories_batch(
                memories=memory_items,
                graph_payload=graph_payload if graph_payload else None,
            )
            logger.info("Stored %d memories in HydraDB", len(memory_items))
        except Exception as e:
            logger.error("Failed to store memories: %s", e)
            raise
