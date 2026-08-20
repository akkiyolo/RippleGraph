"""PostgreSQL memory store — replaces HydraDB for fast, self-hosted storage.

Uses PostgreSQL's built-in full-text search (tsvector/tsquery) for
semantic-like retrieval and a relations table for graph traversal.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras

from ripplegraph.config import Settings

logger = logging.getLogger(__name__)

# ── Schema ───────────────────────────────────────────────

CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL DEFAULT 'FACT',
    subject         TEXT NOT NULL,
    predicate       TEXT NOT NULL,
    object          TEXT DEFAULT '',
    text            TEXT NOT NULL,
    user_id         TEXT NOT NULL DEFAULT 'demo-user',
    session_id      TEXT NOT NULL,
    valid_from      TIMESTAMPTZ,
    valid_to        TIMESTAMPTZ,
    supersedes_id   TEXT,
    confidence      REAL DEFAULT 1.0,
    importance      REAL DEFAULT 0.5,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    search_vector   TSVECTOR
);
"""

CREATE_RELATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS relations (
    id              SERIAL PRIMARY KEY,
    source_id       TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    relation_type   TEXT NOT NULL,
    context         TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_memories_search ON memories USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories (user_id);
CREATE INDEX IF NOT EXISTS idx_memories_session ON memories (session_id);
CREATE INDEX IF NOT EXISTS idx_memories_subject ON memories (subject);
CREATE INDEX IF NOT EXISTS idx_memories_supersedes ON memories (supersedes_id);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations (source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations (target_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations (relation_type);
"""

UPDATE_SEARCH_VECTOR = """
UPDATE memories
SET search_vector = to_tsvector('english', subject || ' ' || predicate || ' ' || COALESCE(object, '') || ' ' || text)
WHERE search_vector IS NULL;
"""


class PgStore:
    """PostgreSQL-backed memory store with full-text search and graph relations."""

    def __init__(self, settings: Settings) -> None:
        self.database_url = settings.database_url
        if not self.database_url:
            raise ValueError("No DATABASE_URL configured. Set EXTERNAL_DATABASE_URL or INTERNAL_DATABASE_URL.")
        self._conn = None

    # ── Connection ───────────────────────────────────────

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.database_url)
            self._conn.autocommit = True
        return self._conn

    def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(CREATE_MEMORIES_TABLE)
            cur.execute(CREATE_RELATIONS_TABLE)
            cur.execute(CREATE_INDEXES)
        logger.info("PostgreSQL store initialized")

    # ── Write ────────────────────────────────────────────

    def upsert_memory(
        self,
        id: str,
        type: str,
        subject: str,
        predicate: str,
        object: str,
        text: str,
        user_id: str,
        session_id: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        supersedes_id: str | None = None,
        confidence: float = 1.0,
        importance: float = 0.5,
        metadata: dict | None = None,
    ) -> str:
        """Insert or update a memory record."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO memories (id, type, subject, predicate, object, text, user_id, session_id,
                                     valid_from, valid_to, supersedes_id, confidence, importance, metadata,
                                     search_vector)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        to_tsvector('english', %s || ' ' || %s || ' ' || %s || ' ' || %s))
                ON CONFLICT (id) DO UPDATE SET
                    type = EXCLUDED.type,
                    text = EXCLUDED.text,
                    valid_from = EXCLUDED.valid_from,
                    valid_to = EXCLUDED.valid_to,
                    supersedes_id = EXCLUDED.supersedes_id,
                    confidence = EXCLUDED.confidence,
                    importance = EXCLUDED.importance,
                    metadata = EXCLUDED.metadata,
                    search_vector = EXCLUDED.search_vector
                RETURNING id
            """, (
                id, type, subject, predicate, object or "", text, user_id, session_id,
                valid_from, valid_to, supersedes_id, confidence, importance,
                json.dumps(metadata or {}),
                subject, predicate, object or "", text,
            ))
            result = cur.fetchone()
        logger.info("Upserted memory %s", id)
        return result[0] if result else id

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        context: str = "",
    ) -> None:
        """Add a directional relation between two memories."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            # Avoid duplicates
            cur.execute("""
                INSERT INTO relations (source_id, target_id, relation_type, context)
                SELECT %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM relations
                    WHERE source_id = %s AND target_id = %s AND relation_type = %s
                )
            """, (source_id, target_id, relation_type, context,
                  source_id, target_id, relation_type))
        logger.debug("Added relation %s -[%s]-> %s", source_id, relation_type, target_id)

    def mark_superseded(self, old_id: str, new_id: str, transition_time: datetime | None = None) -> None:
        """Mark a memory as superseded by another."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            if transition_time:
                cur.execute("UPDATE memories SET valid_to = %s WHERE id = %s", (transition_time, old_id))
            self.add_relation(new_id, old_id, "SUPERSEDES", f"{new_id} supersedes {old_id}")
            self.add_relation(old_id, new_id, "SUPERSEDED_BY", f"{old_id} superseded by {new_id}")

    # ── Read / Search ────────────────────────────────────

    def search_memories(
        self,
        query: str,
        user_id: str = "demo-user",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text search for memories matching a query."""
        conn = self._get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, type, subject, predicate, object, text, user_id, session_id,
                       valid_from, valid_to, supersedes_id, confidence, importance, metadata,
                       created_at,
                       ts_rank_cd(search_vector, query) AS rank
                FROM memories, plainto_tsquery('english', %s) query
                WHERE search_vector @@ query
                  AND user_id = %s
                ORDER BY rank DESC
                LIMIT %s
            """, (query, user_id, max_results))
            results = cur.fetchall()
        return [dict(r) for r in results]

    def get_all_memories(self, user_id: str = "demo-user") -> list[dict[str, Any]]:
        """Get all memories for a user, ordered by creation time."""
        conn = self._get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, type, subject, predicate, object, text, user_id, session_id,
                       valid_from, valid_to, supersedes_id, confidence, importance, metadata, created_at
                FROM memories
                WHERE user_id = %s
                ORDER BY created_at ASC
            """, (user_id,))
            results = cur.fetchall()
        return [dict(r) for r in results]

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """Get a single memory by ID."""
        conn = self._get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM memories WHERE id = %s", (memory_id,))
            result = cur.fetchone()
        return dict(result) if result else None

    def get_relations(self, source_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get all relations from a source memory."""
        conn = self._get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT r.source_id, r.target_id, r.relation_type, r.context,
                       m.text AS target_text, m.subject AS target_subject,
                       m.predicate AS target_predicate, m.session_id AS target_session_id,
                       m.valid_from AS target_valid_from, m.valid_to AS target_valid_to,
                       m.type AS target_type
                FROM relations r
                LEFT JOIN memories m ON m.id = r.target_id
                WHERE r.source_id = %s
                LIMIT %s
            """, (source_id, limit))
            results = cur.fetchall()
        return [dict(r) for r in results]

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memories")
            memory_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM relations")
            relation_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT session_id) FROM memories")
            session_count = cur.fetchone()[0]
        return {
            "memories": memory_count,
            "relations": relation_count,
            "sessions": session_count,
        }

    # ── Cleanup ──────────────────────────────────────────

    def clear_all(self, user_id: str = "demo-user") -> None:
        """Clear all memories and relations for a user (for re-seeding)."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM relations WHERE source_id IN (SELECT id FROM memories WHERE user_id = %s)", (user_id,))
            cur.execute("DELETE FROM memories WHERE user_id = %s", (user_id,))
        logger.info("Cleared all data for user %s", user_id)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
