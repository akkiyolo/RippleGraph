"""LangSmith tracing integration."""

from __future__ import annotations

import logging
import os

from ripplegraph.config import Settings

logger = logging.getLogger(__name__)


def setup_tracing(settings: Settings) -> None:
    """Configure LangSmith tracing if enabled in settings."""
    if not settings.langsmith_tracing:
        logger.info("LangSmith tracing disabled")
        return

    if not settings.langsmith_api_key:
        logger.warning("LangSmith tracing enabled but no API key set")
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

    logger.info("LangSmith tracing enabled for project: %s", settings.langsmith_project)
