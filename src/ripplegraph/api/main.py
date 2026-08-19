"""FastAPI application — the main entry point for RippleGraph."""

from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ripplegraph import __version__
from ripplegraph.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
)
from ripplegraph.clients.hydra_client import HydraClient
from ripplegraph.clients.llm_client import create_llm_client
from ripplegraph.config import get_settings
from ripplegraph.ingestion.ingest import IngestionPipeline
from ripplegraph.ingestion.loader import load_conversations
from ripplegraph.logging_config import setup_logging
from ripplegraph.retrieval.query import execute_query

logger = logging.getLogger(__name__)

# Global state
_hydra: HydraClient | None = None
_llm = None
_settings = None

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global _hydra, _llm, _settings
    _settings = get_settings()
    setup_logging(_settings.log_level)
    logger.info("Starting RippleGraph v%s", __version__)
    try:
        _hydra = HydraClient(_settings)
        _hydra.ensure_database()
    except Exception as e:
        logger.error("HydraDB init failed: %s", e)
        _hydra = None
    try:
        _llm = create_llm_client(_settings)
    except Exception as e:
        logger.error("LLM client init failed: %s", e)
        _llm = None
    yield
    logger.info("Shutting down RippleGraph")


app = FastAPI(
    title="RippleGraph",
    description="Associative Temporal Memory for Long-Running AI Agents",
    version=__version__,
    lifespan=lifespan,
)

# Mount templates and static
if TEMPLATE_DIR.exists():
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── API Endpoints ────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version=__version__)


@app.post("/answer", response_model=AnswerResponse)
async def answer(req: AnswerRequest):
    if not _hydra or not _llm or not _settings:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        result = execute_query(req.question, _hydra, _llm, _settings)
        return AnswerResponse(
            question=result.question,
            status=result.status.value,
            answer=result.answer,
            confidence=result.confidence,
            reason=result.reason,
            temporal_mode=result.temporal_mode,
            evidence=[
                {"memory_id": e.memory_id, "text": e.text, "hop": e.hop, "session_id": e.session_id, "score": e.graph_score}
                for e in result.evidence
            ],
            traversal_path=result.traversal_path,
            latency_ms=result.latency_ms,
        )
    except Exception as e:
        logger.error("Query failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    if not _hydra or not _llm:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        sessions = load_conversations(req.conversations_path)
        pipeline = IngestionPipeline(_hydra, _llm)
        memories = pipeline.ingest_sessions(sessions)
        return IngestResponse(status="ok", memories_created=len(memories), message=f"Ingested {len(memories)} memories from {len(sessions)} sessions")
    except Exception as e:
        logger.error("Ingestion failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/demo/seed", response_model=IngestResponse)
async def demo_seed():
    """Seed the demo dataset."""
    req = IngestRequest(conversations_path="data/demo/conversations.json")
    return await ingest(req)


@app.get("/memory/{memory_id}")
async def get_memory(memory_id: str):
    if not _hydra:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        result = _hydra.inspect_context(memory_id)
        return {"status": "ok", "data": str(result)}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/graph/{user_id}")
async def get_graph(user_id: str):
    if not _hydra:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        stats = _hydra.get_stats()
        return {"status": "ok", "user_id": user_id, "stats": str(stats)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Frontend Routes ──────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if TEMPLATE_DIR.exists():
        return templates.TemplateResponse(request, "index.html", {"version": __version__})
    return HTMLResponse("<h1>RippleGraph</h1><p>Frontend not found.</p>")


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    if TEMPLATE_DIR.exists():
        return templates.TemplateResponse(request, "chat.html", {"version": __version__})
    return HTMLResponse("<h1>RippleGraph Chat</h1>")
