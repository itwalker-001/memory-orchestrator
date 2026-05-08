# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Server package (FastAPI, DB, frontend)
cd memory_orchestrator_server
uv sync                           # Install all dependencies
uv run alembic upgrade head       # Migrate database
uv run mo-server setup --scope user                    # Wire into ~/.claude/settings.json
uv run mo-server setup --client codex --scope user     # Wire into ~/.codex/
uv run python download_models.py                       # Download BGE-M3 + reranker via ModelScope
uv run mo-server serve-http                            # Start HTTP service on port 8765
uv run mo-server migrate-embeddings                    # Re-embed all memories after model change
uv run mo-server doctor                                # Check wiring
uv run pytest                                          # All tests (unit + integration)
uv run pytest src/memory_orchestrator_server/tests/unit/        # Unit tests only
uv run pytest src/memory_orchestrator_server/tests/integration/ # Integration tests (needs Postgres)

# MCP client package (hooks, client rules, zero deps)
cd memory_orchestrator_mcp
uv sync
uv run pytest                     # 9 tests

# Build frontend
cd memory_orchestrator_server/src/memory_orchestrator_server/frontend && npm run build
```

## Architecture

Two independently installable packages:

- **`memory_orchestrator_server/`** — Server package (entry point: `mo-server`)
  - FastAPI, PostgreSQL, pgvector, transformers (BGE-M3 + reranker), Alembic, repository, frontend, MCP HTTP bridge
  - CLI: `mo-server serve-http | serve-mcp | setup | teardown | doctor | token | migrate | migrate-embeddings`
  - Depends on `memory-orchestrator-mcp` (for client rules JSON files)
  - Models stored in `memory_orchestrator_server/models/` (downloaded via `download_models.py`)

- **`memory_orchestrator_mcp/`** — Client MCP package (no entry point, zero deps)
  - Hooks, client rules (JSON), agent instructions, skill files
  - Must stay lightweight: no DB, SQLAlchemy, FlagEmbedding, torch, pgvector, or Alembic

### Request flow

```
UserPromptSubmit hook  →  GET /context  →  repo.build_context()  →  inject markdown
Stop hook              →  POST /ingest  →  ingestor.py  →  LLM extraction  →  repo.save()
Claude/Codex MCP call  →  local stdio MCP  →  POST /mcp/tools/call  →  server repo.*()
```

### Key modules

| File | Role |
|---|---|
| `memory_orchestrator_server/src/memory_orchestrator_server/models.py` | SQLAlchemy ORM: `Project`, `Memory`, `Session`, `MemoryLink`, `SystemSetting`, `ApiToken` |
| `memory_orchestrator_server/src/memory_orchestrator_server/repository.py` | All DB operations |
| `memory_orchestrator_server/src/memory_orchestrator_server/routers/hooks.py` | `/healthz`, `/context`, `/ingest` endpoints |
| `memory_orchestrator_server/src/memory_orchestrator_server/routers/ui.py` | `/api/memories`, `/api/projects`, `/api/settings` |
| `memory_orchestrator_server/src/memory_orchestrator_server/routers/mcp.py` | `/mcp/tools/call`, `/mcp/resources/read` |
| `memory_orchestrator_server/src/memory_orchestrator_server/mcp_core.py` | Server-side MCP tool implementations |
| `memory_orchestrator_server/src/memory_orchestrator_server/embedder.py` | BGE-M3 dense embeddings via `transformers.AutoModel` |
| `memory_orchestrator_server/src/memory_orchestrator_server/reranker.py` | BGE-reranker-v2-m3 cross-encoder via `transformers.AutoModelForSequenceClassification` |
| `memory_orchestrator_server/src/memory_orchestrator_server/mcp_server.py` | stdio MCP runner (direct DB access) |
| `memory_orchestrator_server/src/memory_orchestrator_server/client_adapters.py` | Claude/Codex setup/teardown |
| `memory_orchestrator_server/src/memory_orchestrator_server/client_rules.py` | Reads JSON rules from `memory_orchestrator_mcp` |
| `memory_orchestrator_server/src/memory_orchestrator_server/cli.py` | `mo-server` entry point |
| `memory_orchestrator_mcp/src/memory_orchestrator_mcp/hooks/user_prompt_submit.py` | UserPromptSubmit hook |
| `memory_orchestrator_mcp/src/memory_orchestrator_mcp/hooks/stop.py` | Stop hook |
| `memory_orchestrator_mcp/src/memory_orchestrator_mcp/client_rules/` | `claude.json`, `codex.json` |

### Data model

- `projects`: slug → UUID. Global sentinel: `00000000-0000-0000-0000-000000000000` (slug `*`).
- `memories`: `type` ∈ {user, feedback, project, reference}; `embedding vector(1024)` (BGE-M3); `superseded_by` for soft-delete.
- `system_settings`: key-value; read on every request — no restart needed for most config.
- `sessions`: ingestion progress per session (`last_offset`, `status` ∈ pending/done/failed).
- `api_tokens`: hashed bearer tokens. `kind='ui_admin'` → `/api/*`; `kind='mcp_client'` → `/mcp/*`.

### Authentication

- `/api/*` requires `ui_admin` token when any DB token or `MO_UI_TOKEN` env var exists.
- `/mcp/*` requires `mcp_client` token when any DB token or `MO_MCP_TOKEN` env var exists.

```bash
# From memory_orchestrator_server/:
uv run mo-server token create --kind ui_admin --name admin
uv run mo-server token create --kind mcp_client --name "local claude"
```

### Runtime config (system_settings)

Editable at `/ui` → Settings without restart. Keys: `hook_budget_tokens`, `hook_cooldown_sec`,
`hook_min_turns`, `search_top_k`, `dup_threshold`, `extraction_base_url`, `extraction_model`,
`embed_model`, `embed_dim`, `rerank_enabled`, `rerank_model`.

### Tests

Run from each package directory with `uv run pytest`.

- Server: `memory_orchestrator_server/src/memory_orchestrator_server/tests/`
  - `unit/` — no DB required (27 tests)
  - `integration/` — Postgres on port 5433 required (75 tests)
    - `test_http_app.py` — HTTP endpoint coverage
    - `test_mcp_tools.py` — MCP tool coverage
    - `test_mcp_http.py` — MCP HTTP bridge coverage
    - `test_repository.py` — repository layer
    - `unit/test_package_boundaries.py` — package isolation enforcement
- MCP: `memory_orchestrator_mcp/src/memory_orchestrator_mcp/tests/` (9 tests, no deps)

### Database

PostgreSQL 16 + pgvector on port 5433. Override test DB with `MO_TEST_DB_DSN`.
