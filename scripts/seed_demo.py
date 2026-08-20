"""Seed demo data into PostgreSQL."""

import logging

from ripplegraph.clients.pg_store import PgStore
from ripplegraph.config import get_settings
from ripplegraph.ingestion.seed import seed_demo_data
from ripplegraph.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info("=== RippleGraph Demo Seed ===")

    # Initialize PostgreSQL
    store = PgStore(settings)
    store.initialize()

    # Run ingestion pipeline
    count = seed_demo_data(store, "demo-user")

    logger.info("=== Seed Complete: %d memories created ===", count)


if __name__ == "__main__":
    main()
