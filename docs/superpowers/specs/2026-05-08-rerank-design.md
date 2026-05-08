# Rerank + BGE-M3 Embedding Upgrade Design

## Goal

Replace the current `bge-small-zh-v1.5` (FastEmbed, 512-dim) embedder with `BAAI/bge-m3` (FlagEmbedding, 1024-dim), and add a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) to the search pipeline. Both models are loaded at HTTP server startup and cached locally by HuggingFace.

---

## Architecture

Two responsibilities are added to `memory_orchestrator_server`:

1. **Embedder swap** — `embedder.py` switches from `fastembed.TextEmbedding` to `FlagEmbedding.BGEM3FlagModel`. The public interface (`embed_one`, `embed_batch`) remains unchanged; callers don't change.

2. **Reranker** — a new `reranker.py` module wraps `FlagEmbedding.FlagReranker`. `repository.search()` calls it when `rerank_enabled=true`.

The stdio MCP server is a pure HTTP bridge with no model access; no changes needed there.

---

## Search Pipeline

### Before (hybrid score only)
```
pgvector cosine → top_k×3 candidates → hybrid_score sort → top_k
```

### After (rerank enabled)
```
pgvector cosine → top_k×3 candidates → cross-encoder rerank → top_k
```

### After (rerank disabled)
```
pgvector cosine → top_k×3 candidates → hybrid_score sort → top_k   (unchanged fallback)
```

`hybrid_score = 0.6×cosine + 0.3×importance_norm + 0.1×recency_decay` is kept as the fallback.

---

## Module Changes

| File | Change |
|------|--------|
| `embedder.py` | Replace `fastembed.TextEmbedding` with `FlagEmbedding.BGEM3FlagModel`. Singleton loaded at module import. `embed_one(text) → list[float]`, `embed_batch(texts) → list[list[float]]` signatures unchanged. |
| `reranker.py` | **New.** `FlagReranker` singleton. `rerank(query: str, candidates: list[Memory], top_k: int) → list[ScoredMemory]`. Returns hybrid-score order unchanged if reranker is disabled or raises. |
| `repository.py` | `search(query_embedding, query, project_ids, types, top_k, record_hits)` — adds `query: str \| None = None`. When `rerank_enabled` and `query` provided, replaces hybrid sort with `reranker.rerank()`. |
| `mcp_core.py` | `handle_search_memory` passes `args["query"]` to `repo.search()`. |
| `routers/hooks.py` | `build_context()` passes the hook query string to `repo.search()`. |
| `alembic/versions/XXXX_embed_dim_1024.py` | **New migration.** `ALTER COLUMN embedding TYPE vector(1024) USING NULL`. Nulls out existing vectors; `migrate-embeddings` backfills. |
| `cli.py` | New `mo-server migrate-embeddings` command. Reads all memories in batches, re-embeds, writes back. Progress tracked in `system_settings.embed_migration_offset`. |
| `pyproject.toml` | Replace `fastembed` with `FlagEmbedding>=1.2`. |

---

## Configuration (system_settings)

Keys editable at `/ui` → Settings without restart (except `embed_dim` and `embed_model`, which require a server restart and re-embedding):

| Key | Old value | New value |
|-----|-----------|-----------|
| `embed_model` | `BAAI/bge-small-zh-v1.5` | `BAAI/bge-m3` |
| `embed_dim` | `512` | `1024` |
| `rerank_enabled` | — (new) | `true` |
| `rerank_model` | — (new) | `BAAI/bge-reranker-v2-m3` |

`rerank_enabled` is checked on every search call; toggling it in Settings takes effect immediately.

---

## Data Migration

```bash
cd memory_orchestrator_server
uv run alembic upgrade head          # vector(512) → vector(1024), existing rows set to NULL
uv run mo-server migrate-embeddings  # re-embed all memories in batches of 32
```

During migration, memories with NULL embeddings are excluded from vector search (exact-match fallback remains). Progress is resumable: `embed_migration_offset` in `system_settings` tracks the last processed row ID.

---

## Model Loading

Both models load at `serve-http` startup via module-level singletons:

```python
# embedder.py
from FlagEmbedding import BGEM3FlagModel
_MODEL = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

# reranker.py
from FlagEmbedding import FlagReranker
_RERANKER = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)
```

Models are downloaded once to `~/.cache/huggingface/hub/` (or `HF_HOME`). Subsequent startups load from disk (~5-20 s depending on hardware).

If either model fails to load, `serve-http` logs the error and exits — a misconfigured embedder is not recoverable at runtime.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Model fails to load at startup | Log error, process exits with non-zero code |
| Reranker raises during search | Log warning, fall back to hybrid_score ordering; request returns normally |
| `migrate-embeddings` fails mid-batch | Record offset in `system_settings`, exit non-zero; re-run resumes from offset |
| Memory with NULL embedding queried | Excluded from vector search results; not an error |

---

## Testing Strategy

### Unit (no DB, no models)

- Mock `embedder.embed_one` and `reranker.rerank` in all unit tests.
- Test `repository.search()` branching: rerank enabled → calls reranker; disabled → calls hybrid_score.
- Test `migrate-embeddings` CLI: mock embed_batch, verify offset advances correctly.

### Integration (Postgres on port 5433)

- `test_repository.py`: insert memories, run `search()` with rerank enabled/disabled, assert ordering differs as expected.
- `test_http_app.py`: POST `/context` with a query, assert 200; POST `/mcp/tools/call` search, assert result includes reranked content.
- Migration test: apply migration on test DB, verify column type, run `migrate-embeddings`, verify no NULL embeddings remain.

### Package boundary

- `test_package_boundaries.py`: assert `memory_orchestrator_mcp` does not import `FlagEmbedding`, `reranker`, or any model loading code.

---

## Dependencies

```toml
# memory_orchestrator_server/pyproject.toml
# Remove:  fastembed
# Add:
"FlagEmbedding>=1.2",
```

`FlagEmbedding` pulls in PyTorch; first install is large (~1.5 GB with CUDA or ~500 MB CPU-only). This is acceptable for a server-side dependency.
