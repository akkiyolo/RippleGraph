# RippleGraph
<img width="1895" height="908" alt="image" src="https://github.com/user-attachments/assets/e0a93e24-d3fd-4e4a-9a29-b5af400e31fc" />


**Associative Temporal Memory for Long-Running AI Agents**

> Hack Hydra 2026 — Track 03: Memory + Context Retrieval

## Research Hypothesis

> Can graph-based associative recollection improve cross-session, temporal, and unanswerable-query performance compared with isolated top-k memory retrieval?

## What Makes RippleGraph Different

| Capability | Traditional RAG | RippleGraph |
|------------|----------------|-------------|
| Cross-session retrieval | ❌ Isolated top-k | ✅ Graph-based associative expansion |
| Temporal reasoning | ❌ Latest embedding wins | ✅ Validity intervals + supersession chains |
| Contradiction handling | ❌ Silent conflicts | ✅ Explicit CONTRADICTS relations |
| Unanswerable queries | ❌ Hallucinated answers | ✅ Deterministic abstention gate |
| Provenance | ❌ Opaque scores | ✅ Full evidence ledger with session IDs |

## Architecture

```
Query → Plan → Anchor Retrieval → Ripple Expansion → Temporal Filter → Confidence Gate → Answer
                    ↓                    ↓                                     ↓
               HydraDB Query      Graph Traversal                    Evidence Ledger
```

### Pipeline Stages

1. **Query Planning** — Deterministic temporal mode detection (CURRENT/HISTORICAL/TRANSITION/TIMELINE)
2. **Anchor Retrieval** — HydraDB hybrid search for initial high-quality memories
3. **Associative Expansion** — Graph traversal outward from anchors with hop decay
4. **Temporal Filtering** — Mode-specific filtering and re-scoring
5. **Conflict Resolution** — Deterministic supersession/contradiction resolution
6. **Confidence Gate** — Graph-structural confidence calculation → abstain if below threshold
7. **Answer Generation** — LLM generates ONLY from evidence (never from general knowledge)

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- HydraDB API key ([hydradb.com](https://hydradb.com))
- At least one LLM API key (Gemini, Groq, Mistral, or Cerebras)

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/RippleGraph.git
cd RippleGraph

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run tests
uv run pytest

# Start the server
uv run python scripts/run_server.py

# Seed demo data (in another terminal)
uv run python scripts/seed_demo.py

# Run evaluation
uv run python scripts/run_eval.py
```

### Web Interface

Open http://localhost:8000 for the landing page, or http://localhost:8000/chat for the chat interface.

## Project Structure

```
RippleGraph/
├── src/ripplegraph/
│   ├── api/                    # FastAPI endpoints + frontend
│   │   ├── main.py             # App entry point
│   │   ├── schemas.py          # Request/response models
│   │   ├── templates/          # Jinja2 HTML templates
│   │   └── static/             # CSS/JS assets
│   ├── clients/
│   │   ├── hydra_client.py     # HydraDB SDK wrapper
│   │   └── llm_client.py       # Multi-provider LLM abstraction
│   ├── ingestion/
│   │   ├── loader.py           # Conversation JSON loader
│   │   ├── segmenter.py        # Deterministic conversation segmenter
│   │   ├── extractor.py        # LLM-based memory extraction
│   │   ├── temporal.py         # Supersession & contradiction detection
│   │   └── ingest.py           # Full ingestion orchestrator
│   ├── retrieval/
│   │   ├── planner.py          # Query planning & temporal classification
│   │   ├── anchor.py           # Initial anchor retrieval
│   │   ├── associative.py      # Graph expansion algorithm
│   │   ├── temporal.py         # Temporal filtering
│   │   ├── conflicts.py        # Conflict resolution
│   │   ├── evidence.py         # Evidence ledger builder
│   │   ├── confidence.py       # Graph-structural confidence
│   │   └── query.py            # Query pipeline orchestrator
│   ├── eval/
│   │   └── runner.py           # Evaluation harness
│   ├── models/                 # Pydantic domain models
│   ├── config.py               # pydantic-settings configuration
│   ├── logging_config.py       # Structured JSON logging
│   └── tracing.py              # LangSmith integration
├── data/demo/                  # Demo conversation data
├── tests/                      # Unit & integration tests
├── scripts/                    # CLI scripts
├── docs/                       # Documentation
└── results/                    # Evaluation output
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/answer` | Query the memory system |
| POST | `/ingest` | Ingest conversations |
| POST | `/demo/seed` | Seed demo data |
| GET | `/memory/{id}` | Inspect a memory |
| GET | `/` | Landing page |
| GET | `/chat` | Chat interface |

## Tech Stack

- **Backend**: FastAPI, Pydantic v2, Python 3.12
- **Memory Store**: HydraDB (vector + graph hybrid)
- **LLM**: Gemini / Groq / Mistral / Cerebras (pluggable)
- **Frontend**: Jinja2, vanilla HTML/CSS/JS
- **Tracing**: LangSmith (optional)
- **Package Manager**: uv

## License

MIT
