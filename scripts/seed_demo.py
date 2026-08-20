"""Seed demo data into HydraDB."""

import json
import logging
import sys

from ripplegraph.clients.hydra_client import HydraClient
from ripplegraph.clients.llm_client import create_llm_client
from ripplegraph.config import get_settings
from ripplegraph.ingestion.ingest import IngestionPipeline
from ripplegraph.ingestion.loader import load_conversations
from ripplegraph.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info("=== RippleGraph Demo Seed ===")

    # Initialize clients
    hydra = HydraClient(settings)
    hydra.ensure_database()
    llm = create_llm_client(settings)

    # Load conversations
    conversations_path = sys.argv[1] if len(sys.argv) > 1 else "data/demo/conversations.json"
    sessions = load_conversations(conversations_path)
    logger.info("Loaded %d sessions", len(sessions))

    # Run ingestion pipeline
    pipeline = IngestionPipeline(hydra, llm)
    memories = pipeline.ingest_sessions(sessions)

    logger.info("=== Seed Complete: %d memories created ===", len(memories))

    # Print summary
    for mem in memories:
        print(f"  [{mem.type.value:18s}] {mem.id}: {mem.text[:80]}")
        if mem.supersedes_id:
            print(f"    ↳ supersedes: {mem.supersedes_id}")


if __name__ == "__main__":
    main()
