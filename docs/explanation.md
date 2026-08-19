# RippleGraph — Complete Project Explanation

> Written for someone with zero context. No prior knowledge required.

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [What RippleGraph Is](#2-what-ripplegraph-is)
3. [The Core Idea (Analogy)](#3-the-core-idea-analogy)
4. [How Traditional AI Memory Works (And Why It Fails)](#4-how-traditional-ai-memory-works-and-why-it-fails)
5. [How RippleGraph Works](#5-how-ripplegraph-works)
6. [The Tech Stack](#6-the-tech-stack)
7. [Project Structure Walkthrough](#7-project-structure-walkthrough)
8. [The Ingestion Pipeline (Storing Memories)](#8-the-ingestion-pipeline-storing-memories)
9. [The Retrieval Pipeline (Answering Questions)](#9-the-retrieval-pipeline-answering-questions)
10. [The Abstention Gate (Saying "I Don't Know")](#10-the-abstention-gate-saying-i-dont-know)
11. [The Frontend](#11-the-frontend)
12. [The Evaluation System](#12-the-evaluation-system)
13. [How to Run It](#13-how-to-run-it)
14. [Glossary](#14-glossary)

---

## 1. The Problem

Imagine you're working with an AI assistant on a software project over several months. In March, you tell it:

> "Let's use MongoDB for our database."

Then in April, after running into performance issues, you say:

> "We're switching to PostgreSQL."

Now in May, you ask:

> "What database are we using?"

Most AI assistants will either:
- **Give the wrong answer** (MongoDB) because it found the older conversation first
- **Hallucinate** a confident-sounding but incorrect answer
- **Lose context entirely** because it can only "remember" the current conversation

This is the **long-term memory problem** for AI agents. Current systems treat each conversation as an isolated event. They have no concept of:
- **Time**: "We *used to* use MongoDB, but *now* we use PostgreSQL"
- **Change**: "The database was *switched* in April"
- **Relationships**: "The switch from MongoDB to PostgreSQL was *because of* performance issues"
- **Uncertainty**: "I don't have information about that — let me say so instead of guessing"

**RippleGraph solves all four of these problems.**

---

## 2. What RippleGraph Is

RippleGraph is a **long-term memory layer for AI agents**. It sits between the AI's brain (the language model) and its memory store (a database called HydraDB).

Think of it as giving the AI a proper filing system with:
- A way to **organize** memories (not just dump them in a pile)
- A way to **connect** related memories (like a web of knowledge)
- A way to **track changes over time** (like a history book)
- A way to **know when it doesn't know something** (like an honest librarian)

### What it is NOT:
- It is **not** a chatbot (it's the memory system *behind* a chatbot)
- It is **not** generic search (it understands *relationships* between memories)
- It is **not** "just HydraDB + an LLM" (the graph expansion algorithm is the core innovation)

---

## 3. The Core Idea (Analogy)

### Traditional Memory (Top-K Search)
Imagine a library where you ask:
> "What database are we using?"

The librarian searches every book, finds the 5 most relevant pages, and hands them to you. But those 5 pages might include outdated information, contradictory facts, and no context about *when* things changed.

### RippleGraph Memory (Associative Expansion)
Now imagine a smarter librarian. When you ask the same question:

1. **She finds the most relevant pages** (anchors) — just like before
2. **Then she follows the connections.** One page says "We use PostgreSQL." She notices it has a sticky note: "This replaced MongoDB in April." She pulls that page too.
3. **She checks the timeline.** She sees MongoDB was the answer in March, PostgreSQL became the answer in April. Since you asked "what are we using" (present tense), she prioritizes PostgreSQL.
4. **She checks her confidence.** She found 3 independent sources confirming PostgreSQL. That's enough evidence.
5. **She gives you the answer** with full receipts: "PostgreSQL, based on evidence from sessions 3, 4, and 5."

The "ripple" in RippleGraph refers to step 2 — the way the search *ripples outward* from the initial results through the graph of connections, like a stone dropped in water.

---

## 4. How Traditional AI Memory Works (And Why It Fails)

### The Standard Approach: RAG (Retrieval-Augmented Generation)

```
User asks a question
      ↓
Search a vector database for similar text
      ↓
Return the top 5 most similar chunks
      ↓
Give them to the LLM
      ↓
LLM generates an answer
```

**The failures:**

| Scenario | What Happens | Why It Fails |
|----------|-------------|--------------|
| "What DB are we using?" | Returns both "MongoDB" and "PostgreSQL" chunks | No concept of time — doesn't know which is current |
| "What DB were we using *before*?" | Returns the most *similar* text, not the most *temporally relevant* | No temporal reasoning |
| "When did we switch DBs?" | Probably returns nothing useful | Can't trace state transitions |
| "What's our revenue?" (never discussed) | LLM confidently makes something up | No abstention mechanism |

### What RippleGraph Does Differently

```
User asks a question
      ↓
[1] PLAN: Detect temporal intent (current? historical? transition?)
      ↓
[2] ANCHOR: Search for initial high-quality memories
      ↓
[3] EXPAND: Ripple outward through graph connections
      ↓
[4] FILTER: Apply temporal logic based on the query type
      ↓
[5] SCORE: Calculate confidence from evidence structure
      ↓
[6] GATE: If confidence is too low → ABSTAIN (say "I don't know")
      ↓
[7] ANSWER: Generate answer ONLY from gathered evidence
```

The key differences:
- Steps 1 and 4 give it **temporal awareness**
- Step 3 gives it **associative recall** (not just similarity search)
- Step 6 gives it **honest uncertainty**
- Step 7 constrains it to **evidence-only answers**

---

## 5. How RippleGraph Works

### The Two Main Pipelines

RippleGraph has two main operations:

#### A) Ingestion: "Remember this conversation"
Takes a conversation → breaks it into pieces → extracts durable facts → detects changes → stores in HydraDB with connections

#### B) Retrieval: "What do you know about X?"
Takes a question → finds relevant memories → expands through connections → filters by time → checks confidence → generates answer

Both are explained in detail in sections 8 and 9.

### The Memory Graph

At the heart of RippleGraph is a **graph** — a network of connected memories. Each memory is a **node**, and the connections between them are **edges** (relationships).

```
[MongoDB is our DB]  ──SUPERSEDED_BY──→  [PostgreSQL is our DB]
   (March 2026)                            (April 2026)
                                              │
                                         DECIDED_IN
                                              │
                                              ↓
                                    [Session 3: scaling issues]
```

This graph is stored inside HydraDB using its "Bring Your Own Graph" (BYOG) feature.

---

## 6. The Tech Stack

| Component | Technology | Why |
|-----------|------------|-----|
| **Language** | Python 3.11+ | Industry standard for AI/ML |
| **Web Framework** | FastAPI | Fast, modern, automatic API docs |
| **Data Validation** | Pydantic v2 | Type-safe models, settings management |
| **Memory Store** | HydraDB | Vector search + graph storage in one platform |
| **LLM Providers** | Gemini, Groq, Mistral, Cerebras | Pluggable — use whichever you have a key for |
| **Package Manager** | uv | Fast Python dependency management |
| **Frontend** | Jinja2 + vanilla HTML/CSS/JS | Simple, no build step required |
| **Tracing** | LangSmith (optional) | Observability for LLM calls |
| **Retries** | Tenacity | Automatic retry with exponential backoff |

### What is HydraDB?

HydraDB is a cloud database specifically designed for AI applications. It provides:
- **Vector search**: Find memories by meaning (not just keywords)
- **Graph storage**: Store connections between memories
- **Hybrid search**: Combine vector + keyword search
- **"Thinking" mode**: Deep graph traversal during queries

RippleGraph uses HydraDB as its storage layer but adds all the temporal logic, graph expansion algorithm, confidence scoring, and abstention on top.

---

## 7. Project Structure Walkthrough

```
RippleGraph/
├── src/ripplegraph/           ← All production code lives here
│   ├── __init__.py            ← Package version
│   ├── config.py              ← Configuration (reads .env file)
│   ├── logging_config.py      ← Structured JSON logging
│   ├── tracing.py             ← LangSmith integration
│   │
│   ├── models/                ← Data structures (Pydantic models)
│   │   ├── conversation.py    ← Message, Session, Segment
│   │   ├── memory.py          ← MemoryRecord, make_memory_id()
│   │   ├── evidence.py        ← EvidenceNode, EvidenceLedger
│   │   ├── query.py           ← QueryPlan, TemporalMode
│   │   └── results.py         ← QueryResult (ANSWERED/ABSTAINED)
│   │
│   ├── clients/               ← External service wrappers
│   │   ├── hydra_client.py    ← HydraDB SDK wrapper
│   │   └── llm_client.py      ← LLM abstraction (4 providers)
│   │
│   ├── ingestion/             ← "Remember this" pipeline
│   │   ├── loader.py          ← Read conversation JSON files
│   │   ├── segmenter.py       ← Split conversations into chunks
│   │   ├── extractor.py       ← Extract memories using LLM
│   │   ├── temporal.py        ← Detect supersessions & contradictions
│   │   └── ingest.py          ← Orchestrates the full pipeline
│   │
│   ├── retrieval/             ← "What do you know?" pipeline
│   │   ├── planner.py         ← Classify query temporal intent
│   │   ├── anchor.py          ← Find initial relevant memories
│   │   ├── associative.py     ← THE CORE: graph expansion algorithm
│   │   ├── temporal.py        ← Filter by temporal mode
│   │   ├── conflicts.py       ← Resolve contradictions
│   │   ├── evidence.py        ← Build auditable evidence ledger
│   │   ├── confidence.py      ← Calculate confidence score
│   │   └── query.py           ← Orchestrates the full pipeline
│   │
│   ├── eval/                  ← Testing & evaluation
│   │   └── runner.py          ← Run eval queries, measure accuracy
│   │
│   └── api/                   ← Web interface
│       ├── main.py            ← FastAPI app with all endpoints
│       ├── schemas.py         ← Request/response schemas
│       ├── templates/         ← HTML pages (Jinja2)
│       │   ├── index.html     ← Landing page
│       │   └── chat.html      ← Chat interface
│       └── static/
│           └── style.css      ← Premium dark-mode styling
│
├── tests/                     ← 33 unit tests
├── scripts/                   ← CLI entry points
├── data/demo/                 ← Demo conversation data
├── docs/                      ← Documentation (you are here)
├── results/                   ← Evaluation output
├── pyproject.toml             ← Dependencies & project config
├── Dockerfile                 ← Container deployment
└── .env                       ← Your API keys (not in git)
```

---

## 8. The Ingestion Pipeline (Storing Memories)

When you feed conversations into RippleGraph, they go through 5 stages:

### Stage 1: Loading
**File**: `ingestion/loader.py`

Reads a JSON file containing conversation sessions. Each session has messages with speaker, text, and timestamp.

```json
{
    "session_id": "session-3",
    "user_id": "demo-user",
    "messages": [
        {"speaker": "user", "text": "We need to switch to PostgreSQL.", "timestamp": "2026-04-15T09:00:00"},
        {"speaker": "assistant", "text": "What prompted this?", "timestamp": "2026-04-15T09:01:00"}
    ]
}
```

### Stage 2: Segmentation
**File**: `ingestion/segmenter.py`

Conversations can be long. The segmenter splits them into coherent chunks using **deterministic rules** (no LLM needed):

1. **Max turns**: After 8 messages, start a new segment
2. **Time gaps**: If 30+ minutes pass between messages, start a new segment
3. **Topic shifts**: If someone says "actually," "switched to," "instead," etc., start a new segment

Example: If a conversation starts discussing MongoDB, then someone says "Actually, we switched to PostgreSQL," that triggers a boundary. The MongoDB discussion and the PostgreSQL discussion become separate segments.

**Why deterministic?** Because we need this to be predictable and testable. An LLM might segment differently each time, making the system unreliable.

### Stage 3: Memory Extraction
**File**: `ingestion/extractor.py`

Each segment is sent to an LLM with a carefully crafted prompt that says: "Extract durable facts, decisions, preferences, and events from this conversation." The LLM returns structured data:

```json
{
    "type": "DECISION",
    "subject": "project",
    "predicate": "uses_database",
    "object": "PostgreSQL",
    "text": "The team decided to switch to PostgreSQL due to scaling issues with MongoDB.",
    "importance": 0.9
}
```

**The Write Gate**: Low-importance memories (greetings, filler) are filtered out. Only memories with importance ≥ 0.3 are kept.

**Stable IDs**: Each memory gets a deterministic ID based on `sha256(session_id + subject + predicate + text)`. This means if you ingest the same conversation twice, you get the same IDs — no duplicates.

### Stage 4: Temporal Processing
**File**: `ingestion/temporal.py`

This is where RippleGraph detects **changes over time**:

**Supersession Detection**: If a new memory has the same subject and predicate as an old one but different content, and it's newer, it's a supersession:
- Old: "Project uses MongoDB" (March)
- New: "Project uses PostgreSQL" (April)
- Result: New memory gets a `supersedes_id` pointing to the old one. The old memory gets a `valid_to` timestamp.

**Contradiction Detection**: If two memories claim incompatible things for the same time period (and neither supersedes the other), they're contradictions. Both are kept and linked.

### Stage 5: Storage in HydraDB
**File**: `ingestion/ingest.py`

Each memory is stored in HydraDB with:
- **Text**: The memory content (for vector search)
- **Additional metadata**: session_id, timestamps, validity intervals, memory type
- **Graph relations**: SUPERSEDES, CONTRADICTS connections to other memories
- **BYOG graph**: Entity-relationship triples (subject → predicate → object)

```
Example stored in HydraDB:
  ID: mem-a3f72b1c9e4d0815
  Text: "The team decided to switch to PostgreSQL."
  Metadata: {session_id: "session-3", valid_from: "2026-04-15", supersedes_id: "mem-7b2e1a..."}
  Graph: subject:project ─USES_DATABASE→ object:PostgreSQL
         subject:project ─SUPERSEDES→ superseded:mem-7b2e1a...
```

---

## 9. The Retrieval Pipeline (Answering Questions)

When you ask RippleGraph a question, it goes through 8 stages:

### Stage 1: Query Planning
**File**: `retrieval/planner.py`

The system classifies your question's **temporal intent** using keyword matching:

| Query | Detected Mode | What It Means |
|-------|--------------|---------------|
| "What DB are we using **now**?" | CURRENT | Return the latest active state |
| "What DB **were** we using **before**?" | HISTORICAL | Return past state |
| "**When did** we **switch** DBs?" | TRANSITION | Find the change point |
| "What DBs **have we** used **over time**?" | TIMELINE | Return chronological history |
| "What's the weather?" | NONE | No temporal aspect |

This is done **deterministically** using keyword lists — no LLM required. If keywords don't match, an LLM fallback is used.

### Stage 2: Anchor Retrieval
**File**: `retrieval/anchor.py`

HydraDB's hybrid search finds the top 5 most relevant memories. These are the **anchors** — starting points for expansion.

For "What database are we using?", HydraDB might return:
1. "Project uses PostgreSQL" (score: 0.92)
2. "Project uses MongoDB" (score: 0.85)
3. "Switching to PostgreSQL due to scaling issues" (score: 0.78)

### Stage 3: Associative Expansion (THE CORE ALGORITHM)
**File**: `retrieval/associative.py`

This is what makes RippleGraph different from traditional RAG. Starting from the anchors, it **ripples outward** through graph connections:

```
Hop 0 (anchors):
  [PostgreSQL memory] (score: 0.92)

Hop 1 (expand from anchors):
  [PostgreSQL memory] ─SUPERSEDES→ [MongoDB memory] (score: 0.92 × 0.75 × 1.0 = 0.69)
  [PostgreSQL memory] ─DECIDED_IN→ [Session 3 context] (score: 0.92 × 0.75 × 0.8 = 0.55)

Hop 2 (expand from hop 1):
  [MongoDB memory] ─ABOUT→ [Schema-less requirements] (score: 0.69 × 0.75 × 0.6 = 0.31)
```

**The formula for each expanded node:**
```
score = parent_score × hop_decay × relation_weight
```

- `hop_decay` (default 0.75): Each hop reduces the score by 25%
- `relation_weight`: How important the connection type is (SUPERSEDES=1.0, SUPPORTS=0.9, MENTIONS=0.25)

**Stopping conditions:**
- Max hops reached (default: 2)
- Max nodes reached (default: 30)
- Frontier scores too weak (below 0.05)

### Stage 4: Temporal Filtering
**File**: `retrieval/temporal.py`

Based on the temporal mode from Stage 1:
- **CURRENT**: Boost active memories, penalize superseded ones
- **HISTORICAL**: Don't penalize old memories — that's the point
- **TRANSITION**: Boost supersession chain evidence
- **TIMELINE**: Keep everything, sort chronologically

### Stage 5: Conflict Resolution
**File**: `retrieval/conflicts.py`

If contradicting evidence is found, the system resolves it **deterministically**:
- For CURRENT queries: prefer the latest non-superseded fact
- Superseded memories are marked as not supporting the answer
- Contradictions are tracked for transparency

**Important**: This is never done by the LLM. The LLM does not decide what's true — the graph structure does.

### Stage 6: Evidence Ledger
**File**: `retrieval/evidence.py`

All gathered evidence is organized into an auditable ledger:
```
Evidence Ledger for "What database are we using?"
├── Anchors: [PostgreSQL memory, MongoDB memory]
├── Supporting: [PostgreSQL memory, Session 3 context]
├── Contradicting: []
├── Superseded: [MongoDB memory]
├── Distinct sessions: 2 (session-3, session-1)
└── Total evidence: 4 nodes
```

### Stage 7: Confidence Calculation
**File**: `retrieval/confidence.py`

Confidence is calculated using a **deterministic formula**, not LLM judgment:

```
confidence = 0.4 × corroboration + 0.2 × recency - 0.3 × contradiction_penalty + 0.1 × log(evidence_count + 1)
```

- **Corroboration** (40%): How many independent sessions support the answer?
- **Recency** (20%): For CURRENT queries, are the supporting memories still active?
- **Contradiction penalty** (30%): Are there unresolved contradictions?
- **Evidence count** (10%): More evidence = slightly more confident

### Stage 8: Answer Generation
**File**: `retrieval/query.py`

**But first — the abstention gate:**

Before generating any answer, the system checks:
- Is confidence ≥ 0.50 (the threshold)?
- Are there ≥ 2 pieces of evidence?

If either check fails: **ABSTAIN**. Return "I don't know" with the reason. The LLM is never called. No hallucination is possible.

If the gate passes: The LLM receives ONLY the evidence from the ledger and generates an answer. It is explicitly instructed: "Answer exclusively from the supplied evidence. Do not use outside knowledge."

---

## 10. The Abstention Gate (Saying "I Don't Know")

This deserves its own section because it's a key innovation.

### The Problem with Traditional AI
If you ask ChatGPT "What's our company's Q3 revenue?", it will confidently generate a number — even though it has no idea. This is called **hallucination**.

### How RippleGraph Prevents This

The abstention gate is a **firewall between retrieval and generation**:

```
Evidence gathered → Confidence calculated → Gate check → ???
                                               │
                                    ┌──────────┴──────────┐
                                    │                     │
                              confidence ≥ 0.50     confidence < 0.50
                              evidence ≥ 2          OR evidence < 2
                                    │                     │
                               Call LLM              ABSTAIN
                               Generate answer       Return "I don't know"
                                    │                 + reason why
                                    ↓                     ↓
                              ANSWERED               ABSTAINED
```

**Why this matters:** The gate fires BEFORE the LLM is called. This means:
1. No compute is wasted on hopeless queries
2. No hallucination is possible — the LLM never gets a chance to guess
3. The user gets an honest "I don't know" with an explanation

---

## 11. The Frontend

### Landing Page (`/`)
A sleek dark-mode page explaining what RippleGraph does, showing the 6-step pipeline, and linking to the chat interface.

### Chat Interface (`/chat`)
A modern chat UI (similar to ChatGPT/Claude) with additional features:

- **Status badges**: Each answer shows ANSWERED (green) or ABSTAINED (amber)
- **Confidence meter**: Shows the confidence percentage with color coding
- **Temporal mode**: Shows which temporal mode was detected
- **Latency**: Shows how long the query took
- **Evidence panel**: Expandable section showing every piece of evidence used, including hop depth and session IDs

### Seed Button
The chat page has a "Seed Demo Data" button that loads the sample conversations into HydraDB so you can immediately start asking questions.

---

## 12. The Evaluation System

### Demo Dataset

**5 conversation sessions** that simulate a real project evolving over months:
1. Session 1 (March): Choose MongoDB
2. Session 2 (March): Choose React/Next.js, deploy on AWS ECS
3. Session 3 (April): Switch from MongoDB to PostgreSQL
4. Session 4 (April): Add Tailwind CSS, switch to GraphQL
5. Session 5 (May): Move deployment from AWS ECS to Kubernetes on GCP

### 8 Evaluation Queries

| # | Question | Expected | Category |
|---|----------|----------|----------|
| 1 | "What database are we using?" | PostgreSQL (ANSWERED) | Current state |
| 2 | "What database were we using before PostgreSQL?" | MongoDB (ANSWERED) | Historical |
| 3 | "When did we switch from MongoDB to PostgreSQL?" | April 2026 (ANSWERED) | Transition |
| 4 | "What frontend framework are we using?" | React/Next.js (ANSWERED) | Current state |
| 5 | "Where are we deploying?" | GCP/Kubernetes (ANSWERED) | Current state |
| 6 | "What was our deployment platform before GCP?" | AWS ECS (ANSWERED) | Historical |
| 7 | "What is the company's revenue this quarter?" | N/A (ABSTAINED) | Unanswerable |
| 8 | "What databases have we considered over time?" | MongoDB + PostgreSQL (ANSWERED) | Timeline |

### Metrics
The evaluation measures three things:
- **Status accuracy**: Did it correctly answer vs. abstain?
- **Content accuracy**: Does the answer contain the expected keywords?
- **Temporal accuracy**: Did it detect the correct temporal mode?

---

## 13. How to Run It

### Prerequisites
1. Python 3.11 or newer
2. A HydraDB API key (free at [hydradb.com](https://hydradb.com))
3. At least one LLM API key (Gemini, Groq, Mistral, or Cerebras)

### Step-by-Step

```bash
# 1. Install dependencies
cd RippleGraph
uv sync

# 2. Configure your API keys
cp .env.example .env
# Edit .env with your real API keys

# 3. Run the tests (should see 33 passing)
uv run pytest

# 4. Start the server
uv run python scripts/run_server.py
# Server starts at http://localhost:8000

# 5. Open the chat interface
# Visit http://localhost:8000/chat in your browser

# 6. Click "Seed Demo Data" in the chat to load conversations

# 7. Start asking questions!
# Try: "What database are we using?"
# Try: "What database were we using before PostgreSQL?"
# Try: "What is our company's revenue?" (should abstain)

# 8. (Optional) Run the evaluation
uv run python scripts/run_eval.py
```

---

## 14. Glossary

| Term | Meaning |
|------|---------|
| **Anchor** | Initial high-quality memory retrieved via search (hop 0) |
| **Associative Expansion** | The process of following graph connections from anchors to discover related memories |
| **Abstention** | When the system declines to answer due to insufficient evidence |
| **BYOG** | "Bring Your Own Graph" — HydraDB feature for custom entity-relationship graphs |
| **Confidence** | A 0-1 score calculated from evidence structure (not by the LLM) |
| **Contradiction** | Two memories claiming incompatible facts for the same time period |
| **Evidence Ledger** | An auditable record of all evidence gathered for a query |
| **Graph Expansion** | Following edges in the memory graph to discover connected memories |
| **Hop** | One step outward in graph expansion (hop 0 = anchors, hop 1 = neighbors) |
| **Hop Decay** | The factor by which scores decrease with each hop (default: 0.75) |
| **HydraDB** | The cloud database providing vector search + graph storage |
| **Ingestion** | The process of converting conversations into structured memories |
| **LLM** | Large Language Model — the AI that generates text (Gemini, etc.) |
| **Memory Record** | A single durable fact extracted from a conversation |
| **Provenance** | The origin trail of a piece of evidence (which session, which messages) |
| **RAG** | Retrieval-Augmented Generation — the standard approach RippleGraph improves upon |
| **Ripple** | Metaphor for how search expands outward from anchors, like ripples in water |
| **Segment** | A coherent chunk of conversation, bounded by topic shifts or time gaps |
| **Supersession** | When a newer fact replaces an older one (MongoDB → PostgreSQL) |
| **Temporal Mode** | The time-related intent of a query (CURRENT, HISTORICAL, TRANSITION, TIMELINE) |
| **Vector Search** | Finding text by meaning/similarity rather than exact keyword match |
| **Write Gate** | The importance filter that prevents low-value memories from being stored |
