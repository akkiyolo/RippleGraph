"""HydraDB client abstraction.

Wraps the official hydradb-sdk so the rest of the codebase never
touches HydraDB types directly.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ripplegraph.config import Settings

logger = logging.getLogger(__name__)

# Import HydraDB SDK
try:
    from hydra_db import HydraDB
except ImportError:
    HydraDB = None  # type: ignore[assignment, misc]


def _is_transient(exc: Exception) -> bool:
    """Return True for errors worth retrying."""
    msg = str(exc).lower()
    return any(tok in msg for tok in ("429", "500", "502", "503", "504", "timeout", "connection"))


class HydraClient:
    """Thin wrapper around the HydraDB Python SDK."""

    def __init__(self, settings: Settings) -> None:
        if HydraDB is None:
            raise ImportError(
                "hydradb-sdk is not installed. Run: uv add 'hydradb-sdk>=2,<3'"
            )
        self.settings = settings
        self.client = HydraDB(token=settings.hydra_db_api_key)
        self.database = settings.hydra_db_tenant_id
        self.collection = settings.hydra_db_sub_tenant_id

    # ── Database management ──────────────────────────────────

    def ensure_database(self, timeout: int = 60) -> None:
        """Create the database if it doesn't exist and wait until ready."""
        try:
            status = self.client.databases.status(database=self.database)
            if status.data.infra.ready_for_ingestion:
                logger.info("Database '%s' already ready", self.database)
                return
        except Exception:
            logger.info("Creating database '%s'", self.database)
            try:
                self.client.databases.create(database=self.database)
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info("Database '%s' already exists", self.database)
                else:
                    raise

        # Poll until ready
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                status = self.client.databases.status(database=self.database)
                if status.data.infra.ready_for_ingestion:
                    logger.info("Database '%s' ready for ingestion", self.database)
                    return
            except Exception:
                pass
            time.sleep(3)
        raise TimeoutError(f"Database '{self.database}' not ready within {timeout}s")

    # ── Memory ingestion ─────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying ingest_memory (attempt %d)", retry_state.attempt_number
        ),
        reraise=True,
    )
    def ingest_memory(
        self,
        memory_id: str,
        text: str,
        additional_metadata: dict[str, Any] | None = None,
        graph_payload: dict[str, Any] | None = None,
        collection: str | None = None,
    ) -> str:
        """Ingest a single memory into HydraDB.

        Returns the ID assigned by HydraDB.
        """
        memory_item: dict[str, Any] = {
            "id": memory_id,
            "text": text,
            "infer": False,
        }
        if additional_metadata:
            memory_item["additional_metadata"] = additional_metadata

        kwargs: dict[str, Any] = {
            "type": "memory",
            "database": self.database,
            "collection": collection or self.collection,
            "upsert": True,
            "memories": json.dumps([memory_item]),
        }
        if graph_payload:
            kwargs["graph_payload"] = json.dumps(graph_payload)

        result = self.client.context.ingest(**kwargs)
        returned_id = result.data.results[0].id
        logger.info(
            "Ingested memory %s → %s",
            memory_id,
            returned_id,
            extra={"memory_id": memory_id},
        )
        return returned_id

    def ingest_memories_batch(
        self,
        memories: list[dict[str, Any]],
        graph_payload: dict[str, Any] | None = None,
        collection: str | None = None,
    ) -> list[str]:
        """Ingest a batch of memories. Returns list of IDs."""
        kwargs: dict[str, Any] = {
            "type": "memory",
            "database": self.database,
            "collection": collection or self.collection,
            "upsert": True,
            "memories": json.dumps(memories),
        }
        if graph_payload:
            kwargs["graph_payload"] = json.dumps(graph_payload)

        result = self.client.context.ingest(**kwargs)
        ids = [r.id for r in result.data.results]
        logger.info("Batch-ingested %d memories", len(ids))
        return ids

    # ── Indexing status ──────────────────────────────────────

    def wait_for_indexing(
        self, ids: list[str], timeout: int = 120, poll_interval: float = 2.0
    ) -> None:
        """Poll until all IDs reach 'completed' status."""
        deadline = time.time() + timeout
        pending = set(ids)

        while pending and time.time() < deadline:
            try:
                result = self.client.context.status(
                    database=self.database, ids=list(pending)
                )
                for status in result.data.statuses:
                    if status.indexing_status == "completed":
                        pending.discard(status.id if hasattr(status, "id") else "")
                    elif status.indexing_status == "errored":
                        err_msg = getattr(status, "error_message", "unknown error")
                        raise RuntimeError(f"Indexing failed: {err_msg}")
            except RuntimeError:
                raise
            except Exception as e:
                logger.warning("Status poll error: %s", e)

            if pending:
                time.sleep(poll_interval)

        if pending:
            logger.warning("Indexing timeout for IDs: %s", pending)

    # ── Query ────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying query (attempt %d)", retry_state.attempt_number
        ),
        reraise=True,
    )
    def query(
        self,
        query: str,
        type_: str = "memory",
        collection: str | None = None,
        max_results: int = 10,
        graph_context: bool = True,
        mode: str = "thinking",
        recency_bias: float = 0.0,
    ) -> Any:
        """Execute a query against HydraDB."""
        result = self.client.query(
            database=self.database,
            collection=collection or self.collection,
            query=query,
            type=type_,
            query_by="hybrid",
            mode=mode,
            max_results=max_results,
            graph_context=graph_context,
            recency_bias=recency_bias,
        )
        return result

    # ── Relation inspection ──────────────────────────────────

    def get_relations(
        self,
        source_id: str,
        type_: str = "memory",
        limit: int = 500,
    ) -> Any:
        """Get relations for a specific source ID."""
        return self.client.context.relations(
            database=self.database,
            id=source_id,
            type=type_,
            limit=limit,
        )

    # ── Context inspection ───────────────────────────────────

    def inspect_context(self, source_id: str) -> Any:
        """Inspect ingested context by ID."""
        return self.client.context.inspect(
            database=self.database,
            id=source_id,
        )

    def list_context(self, ids: list[str]) -> Any:
        """List context sources by IDs."""
        return self.client.context.list(
            database=self.database,
            ids=ids,
        )

    def delete_context(self, source_id: str) -> Any:
        """Delete a context source."""
        return self.client.context.delete(
            database=self.database,
            id=source_id,
        )

    # ── Database info ────────────────────────────────────────

    def get_stats(self) -> Any:
        """Get database statistics."""
        return self.client.databases.stats(database=self.database)

    def list_collections(self) -> Any:
        """List all collections in the database."""
        return self.client.databases.collections(database=self.database)
