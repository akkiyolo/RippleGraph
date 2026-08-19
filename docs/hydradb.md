# HydraDB Verification Report

> **Date**: 2026-08-19
> **Verified against**: https://docs.hydradb.com (API v2)
> **SDK version**: `hydradb-sdk>=2,<3`
> **Status**: ✅ VERIFIED

---

## 1. Python SDK

| Item | Verified |
|------|----------|
| **Package name** | `hydradb-sdk` (on PyPI) |
| **Install** | `pip install "hydradb-sdk>=2,<3"` |
| **Import** | `from hydra_db import HydraDB, AsyncHydraDB` |
| **Sync client** | `client = HydraDB(token=os.environ["HYDRA_DB_API_KEY"])` |
| **Async client** | `async_client = AsyncHydraDB(token=os.environ["HYDRA_DB_API_KEY"])` |
| **Method pattern** | `client.<group>.<method>()` |
| **API version header** | Handled automatically by SDK (sets `API-Version: 2`) |

⚠️ **IMPORTANT**: The package on PyPI is `hydradb-sdk` but the Python import is `hydra_db` (with underscore).

---

## 2. Authentication

| Item | Verified |
|------|----------|
| **Method** | Bearer token via `Authorization: Bearer <api_key>` |
| **Key source** | https://app.hydradb.com |
| **SDK auth** | `HydraDB(token=...)` — single token param |
| **Base URL** | `https://api.hydradb.com` |

---

## 3. Database (Tenant) Management

HydraDB v2 uses **"database"** as the canonical term (replaces deprecated `tenant_id`).

| SDK Method | REST | Description |
|------------|------|-------------|
| `client.databases.create(database=...)` | `POST /databases` | Create a database |
| `client.databases.status(database=...)` | `GET /databases/status` | Check database readiness |
| `client.databases.list()` | `GET /databases` | List all databases |
| `client.databases.delete(database=...)` | `DELETE /databases` | Delete a database |
| `client.databases.collections(database=...)` | `GET /databases/collections` | List collections |
| `client.databases.stats(database=...)` | `GET /databases/stats` | Database statistics |

### Async behavior
- Database creation is **asynchronous**. Must poll `databases.status()` until `infra.ready_for_ingestion == True` before ingesting.

### Readiness check pattern
```python
while True:
    infra = client.databases.status(database=database).data.infra
    if infra.ready_for_ingestion:
        break
    time.sleep(5)
```

---

## 4. Collections (Sub-Tenants / Multi-Tenancy)

| Item | Verified |
|------|----------|
| **Canonical field** | `collection` (replaces deprecated `sub_tenant_id`) |
| **Scope** | Per-database. Collections partition data within a database |
| **B2C pattern** | One database for org; each end user is a collection |
| **B2B pattern** | Each customer is a database; departments are collections |
| **Default** | If `collection` is omitted, uses the default collection |
| **Query scoping** | Can query single collection, multiple via `collections` dict with weights |

### For RippleGraph
- `database` = `hackhydra` (from .env `HYDRA_DB_TENANT_ID`)
- `collection` = `demo-user` (from .env `HYDRA_DB_SUB_TENANT_ID`)
- We will use `collection` to scope per-user memories

---

## 5. Context Ingestion

### Endpoint: `POST /context/ingest`
### SDK: `client.context.ingest(...)`

### Two types:
1. **`type="knowledge"`** — Documents (PDF, DOCX, CSV, MD, TXT) + app_knowledge (JSON)
2. **`type="memory"`** — User-specific context

### Memory ingestion (our primary use case)
```python
import json

result = client.context.ingest(
    type="memory",
    database="hackhydra",
    collection="demo-user",
    upsert=True,
    memories=json.dumps([
        {
            "id": "stable-memory-id",
            "text": "User prefers PostgreSQL for the database.",
            "infer": False,
        }
    ]),
)
# Returns: result.data.results[0].id, result.data.results[0].status ("queued")
```

### Key fields for memory items

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Optional | Caller-supplied stable ID. **Must not contain commas**. |
| `text` | string | One of text/user_assistant_pairs | Raw text content |
| `user_assistant_pairs` | list | One of text/user_assistant_pairs | Conversation pairs |
| `infer` | bool | Optional | `true` = HydraDB extracts meaning; `false` = store as-is |
| `metadata` | string (JSON) | Optional | Schema-backed filterable fields |
| `additional_metadata` | dict | Optional | Free-form metadata |
| `relations` | dict | Optional | Forceful relations: `{"ids": ["other-memory-id"]}` |
| `user_name` | string | Optional | User name for inference context |

### Upsert support
- ✅ **`upsert=True`** is officially supported on ingestion
- Re-ingesting with the same `id` will update the memory

### Async indexing
- Ingestion returns `202 Accepted` — items are **queued, not immediately indexed**
- Must poll status before querying

---

## 6. Deterministic IDs

| Item | Verified |
|------|----------|
| **Caller-supplied IDs** | ✅ Supported via `id` field in memory items |
| **Constraint** | ID must not contain commas (`,`) |
| **Upsert behavior** | With `upsert=True`, same ID overwrites |
| **Auto-generated** | If no `id` provided, HydraDB generates one (e.g., `mem_abc123`) |

### For RippleGraph
- We will generate stable IDs using `make_memory_id()` hashing session_id + subject + predicate + content_hash
- This enables idempotent re-ingestion

---

## 7. Indexing Status / Polling

### Endpoint: `GET /context/status`
### SDK: `client.context.status(database=..., ids=[...])`

```python
while True:
    status = client.context.status(
        database="hackhydra",
        ids=["memory-id"],
    ).data.statuses[0]
    if status.indexing_status == "completed":
        break
    if status.indexing_status == "errored":
        raise RuntimeError(status.error_message)
    time.sleep(2)
```

### Status values
- `queued` → `graph_creation` → `completed`
- `errored` (with error_message)

---

## 8. Metadata

### Two types of metadata:

1. **`metadata`** — Schema-backed, filterable at query time via `metadata_filters`
   - Must define schema via `PATCH /databases/{database}/metadata-schema` 
   - Passed as JSON string on ingestion
   
2. **`additional_metadata`** — Free-form key-value pairs
   - No schema needed
   - Attached per source at ingestion
   - Filterable via `metadata_filters.additional_metadata` in queries

### For RippleGraph
- We will use `additional_metadata` for session_id, timestamps, memory_type, subject, predicate, etc.
- This avoids needing to define a strict schema upfront

---

## 9. Relations / Graph

### HydraDB supports two relation mechanisms:

#### 9a. Forceful Relations (between memories)
```python
# At ingestion time, link memories by ID
memories=json.dumps([{
    "id": "pref-postgres",
    "text": "User prefers PostgreSQL",
    "relations": {"ids": ["pref-mongodb"]},
}])
```
- Links are by source `id` → target `id`
- These create edges in the context graph
- Available at query time with `graph_context: true, mode: "thinking"`

#### 9b. BYOG (Bring Your Own Graph)
```python
# Supply explicit entity-relation graph via graph_payload
graph_payload=json.dumps({
    "memory-id": {
        "entities": {
            "user": {"name": "User", "type": "PERSON"},
            "postgres": {"name": "PostgreSQL", "type": "DATABASE"},
        },
        "relations": [{
            "source": "user",
            "target": "postgres",
            "predicate": "PREFERS",
            "context": "User prefers PostgreSQL.",
            "temporal_details": "since 2026-03",
        }]
    }
})
```
- Works for both `type="memory"` and `type="knowledge"`
- Entities have: `name` (required), `type`, `namespace`, `identifier`
- Relations have: `source`, `target`, `predicate` (required), `context`, `temporal_details` (optional)
- Entity names are normalized (lowercased) for matching
- **Replace mode**: BYOG replaces LLM graph extraction entirely
- Skips HydraDB's LLM extraction, but still chunks and embeds for vector search

#### 9c. Context Graph Retrieval at Query Time
```python
result = client.query(
    database="hackhydra",
    query="What database does the user prefer?",
    type="memory",
    query_by="hybrid",
    mode="thinking",
    graph_context=True,
)

# result.data.graph_context contains:
# - query_paths: multi-hop paths from query
# - chunk_relations: relationship paths between retrieved chunks  
# - chunk_id_to_group_ids: chunk-to-path mapping
```

### Graph response structure
```json
{
  "graph_context": {
    "query_paths": [{
      "triplets": [{
        "source": {"name": "user", "type": "PERSON"},
        "relation": {"canonical_predicate": "PREFERS", "context": "..."},
        "target": {"name": "postgresql", "type": "DATABASE"}
      }],
      "relevancy_score": 0.84,
      "group_id": "p_0",
      "source_chunk_ids": ["chunk_abc"]
    }],
    "chunk_relations": [],
    "chunk_id_to_group_ids": {"chunk_abc": ["p_0"]}
  }
}
```

---

## 10. Inspecting Relations

### Endpoint: `GET /context/relations`
### SDK: `client.context.relations(database=..., id=..., limit=...)`

```python
relations = client.context.relations(
    database="hackhydra",
    id="memory-id",
    limit=500,
)
```

- Returns source/target entities with their relations
- Each relation has: `canonical_predicate`, `raw_predicate`, `context`, `confidence`, `temporal_details`, `timestamp`, `relationship_id`, `chunk_id`
- Supports pagination via `cursor` / `next_cursor`
- Can query collection-wide by omitting `id`
- For memories, set `type="memory"`

---

## 11. Query API

### Endpoint: `POST /query`
### SDK: `client.query(...)`

```python
result = client.query(
    database="hackhydra",
    collection="demo-user",
    query="What database are we using?",
    type="memory",       # or "knowledge" or "all"
    query_by="hybrid",   # or "text"
    mode="thinking",     # or "fast" or "auto"
    max_results=10,
    graph_context=True,
    recency_bias=0.0,    # 0.0 to 1.0
)
```

### Query parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `type` | `"memory"`, `"knowledge"`, `"all"` | required | Which store to search |
| `query_by` | `"hybrid"`, `"text"` | `"hybrid"` | Retrieval strategy |
| `mode` | `"thinking"`, `"fast"`, `"auto"` | `"auto"` | Pipeline complexity |
| `max_results` | 1-50 | 10 | Max chunks returned |
| `graph_context` | bool | false (true with thinking) | Include graph traversal |
| `recency_bias` | 0.0-1.0 | 0.0 | Prefer recent content |
| `metadata_filters` | dict | null | Filter by metadata |
| `additional_context` | string | null | Extra context for query |
| `collections` | dict | null | Multi-collection query with weights |
| `query_forceful_relations` | bool | false | Include forceful relations |

### Response structure
```python
result.data.chunks      # Ranked retrieved chunks
result.data.sources     # Source metadata
result.data.graph_context  # Graph paths (if enabled)
```

---

## 12. Additional Context Endpoints

| SDK Method | REST | Description |
|------------|------|-------------|
| `client.context.inspect(database=..., id=...)` | `GET /context/inspect` | View ingested content |
| `client.context.list(database=..., ids=[...])` | `POST /context/list` | List sources by IDs |
| `client.context.delete(database=..., id=...)` | `DELETE /context` | Delete a source |

---

## 13. Design Implications for RippleGraph

### What HydraDB provides natively:
- ✅ Persistent memory storage with vector search
- ✅ Stable caller-supplied IDs for idempotent upserts
- ✅ Graph relations via BYOG (entities + predicates)
- ✅ Graph context retrieval with multi-hop paths
- ✅ Relation inspection API
- ✅ Collection-based per-user scoping
- ✅ Metadata and additional_metadata for provenance
- ✅ Hybrid and text-based retrieval
- ✅ Thinking mode for deeper graph traversal
- ✅ Recency bias control

### What RippleGraph must build on top:
- ❌ **Temporal validity intervals** (valid_from, valid_to) — must store in additional_metadata and filter client-side
- ❌ **SUPERSEDED_BY semantics** — must use forceful relations or BYOG with custom predicates, tracked client-side
- ❌ **Contradiction detection** — purely RippleGraph logic
- ❌ **Confidence calculation** — graph-structural analysis is RippleGraph's contribution
- ❌ **Abstention gate** — deterministic pre-generation decision
- ❌ **Hop decay scoring** — RippleGraph applies decay weights to HydraDB graph results
- ❌ **Temporal mode routing** — RippleGraph determines CURRENT/HISTORICAL/TRANSITION/TIMELINE
- ❌ **Evidence ledger** — assembled from HydraDB results + RippleGraph scoring
- ❌ **Semantic segmentation** — pre-ingestion conversation processing

### Architecture approach:
1. **Ingest**: Store memories via `type="memory"` with `infer=False` (we pre-extract memories ourselves)
2. **Graph**: Use BYOG `graph_payload` to supply our own SUPERSEDES/CONTRADICTS/SUPPORTS relations
3. **Retrieve**: Use `client.query()` with `graph_context=True, mode="thinking"` for anchor retrieval
4. **Expand**: Use `client.context.relations()` for explicit graph traversal from anchors
5. **Score**: Apply RippleGraph's hop decay, temporal filtering, and confidence on top of HydraDB results

---

## 14. Spec Changes Required

### 14.1 Terminology alignment
| Spec term | HydraDB v2 term | Action |
|-----------|-----------------|--------|
| `tenant_id` | `database` | Use `database` in all API calls |
| `sub_tenant_id` | `collection` | Use `collection` in all API calls |

### 14.2 Relation strategy  
The spec calls for explicit SUPERSEDED_BY, CONTRADICTS, SUPPORTS, etc. relationships. HydraDB supports this via:
- **Forceful relations** (`relations.ids`) — simple bidirectional links between memory IDs
- **BYOG** (`graph_payload`) — rich entities + typed predicate relations

**Decision**: Use **BYOG** for our typed semantic relations (SUPERSEDES, CONTRADICTS, etc.) since it supports named predicates, context, and temporal_details. Use forceful relations as a fallback for simple links.

### 14.3 Graph expansion approach
HydraDB's `graph_context` on query returns paths, but RippleGraph needs **iterative expansion from anchors**. The approach:
1. Query with `graph_context=True` to get initial anchors + nearby graph paths
2. Use `context.relations()` on anchor IDs to discover more connected memories
3. RippleGraph controls the expansion depth, scoring, and termination

### 14.4 Metadata for temporal tracking
Store temporal fields in `additional_metadata`:
```json
{
    "session_id": "session-5",
    "memory_type": "FACT",
    "subject": "user",
    "predicate": "preferred_database",
    "valid_from": "2026-03-15T10:00:00Z",
    "valid_to": null,
    "supersedes_id": "mem-mongodb-pref",
    "created_at": "2026-03-15T10:00:00Z"
}
```

---

## 15. Risks / Blockers

| Risk | Severity | Mitigation |
|------|----------|------------|
| BYOG for memories may have payload size limits | Medium | Test with demo data first; paginate if needed |
| Graph expansion depth via `context.relations()` may be limited to direct connections | Medium | Implement multi-round expansion in RippleGraph client |
| Indexing latency means tests need polling | Low | Build polling helper with configurable timeout |
| `additional_metadata` filtering may be limited | Medium | Verify exact filter capabilities; may need client-side filtering for temporal queries |
| No native "get all memories for a collection" without IDs | Low | Use `context.list()` or maintain a local index |
