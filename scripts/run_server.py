"""Run the RippleGraph FastAPI server."""

import uvicorn

from ripplegraph.config import get_settings
from ripplegraph.logging_config import setup_logging
from ripplegraph.tracing import setup_tracing


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    setup_tracing(settings)

    uvicorn.run(
        "ripplegraph.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
