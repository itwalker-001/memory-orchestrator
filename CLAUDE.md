# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package documentation

Each package has its own focused docs — start there when working inside a single package:

| Package | Developer guide | User guide |
|---|---|---|
| `memory_orchestrator_server/` | [`memory_orchestrator_server/CLAUDE.md`](memory_orchestrator_server/CLAUDE.md) | [`memory_orchestrator_server/README.md`](memory_orchestrator_server/README.md) |
| `memory_orchestrator_mcp/` | [`memory_orchestrator_mcp/CLAUDE.md`](memory_orchestrator_mcp/CLAUDE.md) | [`memory_orchestrator_mcp/README.md`](memory_orchestrator_mcp/README.md) |

This file covers cross-package concerns: end-to-end request flow, shared data model, Docker
deployment, and the commands needed to operate the full system from the repository root.

## Commands

```bash
# --- Server package (run from memory_orchestrator_server/) ---
uv sync
uv run alembic upgrade head
uv run python download_models.py
uv run mo-server serve-http                            # port 8765
uv run mo-server setup --scope user                    # wire Claude Code
uv run mo-server setup --client codex --scope user     # wire Codex
uv run mo-server doctor
uv run mo-server migrate-embeddings                    # after model change
uv run pytest

# --- MCP client package (run from memory_orchestrator_mcp/) ---
uv sync
uv run pytest

# --- Frontend (run from memory_orchestrator_server/frontend/) ---
npm run build

# --- Docker (run from repository root) ---
./scripts/build.sh
DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain ./scripts/build.sh
```

→ Full command reference: [`memory_orchestrator_server/CLAUDE.md`](memory_orchestrator_server/CLAUDE.md)
→ Hook CLI reference: [`memory_orchestrator_mcp/CLAUDE.md`](memory_orchestrator_mcp/CLAUDE.md)

## Architecture

Two independently installable packages connected over HTTP:

```
memory_orchestrator_mcp  (hooks + MCP stdio bridge)
        │
        │  HTTP → localhost:8765
        ▼
memory_orchestrator_server  (FastAPI + PostgreSQL + ML)
```

### Request flow

```
UserPromptSubmit hook  →  GET /context        →  repo.build_context()  →  inject markdown
Stop hook              →  POST /hooks/ingest  →  ingestor.py           →  LLM extract → repo.save()
Claude/Codex MCP call  →  stdio MCP (mo-mcp)  →  POST /mcp/tools/call  →  repo.*()
```

### Server router layout

```
/healthz  /context  /hooks/ingest   →  routers/hooks.py
/mcp/tools/*  /mcp/resources/*      →  routers/mcp.py   →  mcp_core.py
/ui/*  /api/*                       →  routers/ui.py
                                            │
                                      repository.py
                                            │
                              PostgreSQL + pgvector + Apache AGE
```

→ Module detail: [`memory_orchestrator_server/CLAUDE.md § Key modules`](memory_orchestrator_server/CLAUDE.md)
→ Hook internals: [`memory_orchestrator_mcp/CLAUDE.md § Hook behavior`](memory_orchestrator_mcp/CLAUDE.md)

## Data model

Defined in `memory_orchestrator_server/models.py`; consumed by both packages via HTTP.

- `projects` — slug → UUID.
- `memories` — `type` ∈ {user, feedback, project, reference}; `embedding vector(1024)` (BGE-M3); `superseded_by` for soft-delete chain.
- `system_settings` — key-value; cached 60 s; editable at runtime without restart.
- `sessions` — ingestion progress per session (`last_offset`, `status` ∈ pending/done/failed).
- `api_tokens` — SHA256-hashed bearer tokens; `kind` ∈ {ui_admin, mcp_client}.

## Authentication

- `/ui/*` and `/api/*` require `ui_admin` token (or `MO_UI_TOKEN` env var).
- `/mcp/*` requires `mcp_client` token (or `MO_MCP_TOKEN` env var).
- No token rows in DB → auth disabled.

```bash
# From memory_orchestrator_server/:
uv run mo-server token create --kind ui_admin --name admin
uv run mo-server token create --kind mcp_client --name "local claude"
```

`mo-server setup` auto-injects `MO_MCP_TOKEN` into the client environment.

## Runtime config (system_settings)

Editable at `/ui` → Settings without restart.

| Key | Purpose |
|---|---|
| `hook_budget_tokens` | Max tokens injected per UserPromptSubmit |
| `hook_cooldown_sec` | Min seconds between Stop hook ingestions |
| `hook_min_turns` | Min user turns before Stop hook fires |
| `search_top_k` | Candidate count for vector search |
| `dup_threshold` | Cosine threshold for duplicate detection |
| `extraction_base_url` | LLM extraction endpoint (OpenAI-compatible) |
| `extraction_model` | Model for extraction (default: `gpt-4o-mini`) |
| `embed_model` | HuggingFace embedding model path |
| `embed_dim` | Embedding vector dimension (default: 1024) |
| `rerank_enabled` | Enable BGE reranker after vector search |
| `rerank_model` | HuggingFace reranker model path |
| `graph_enabled` | Enable Apache AGE graph reasoning |
| `graph_hop_depth` | Max hops in graph traversal |

## Tests

```bash
# Server (from memory_orchestrator_server/)
uv run pytest tests/unit/        # no DB required
uv run pytest tests/integration/ # needs Postgres on port 5433

# MCP client (from memory_orchestrator_mcp/)
uv run pytest
```

Override test DB: `MO_TEST_DB_DSN=postgresql+asyncpg://...`

→ Full test file listing: [`memory_orchestrator_server/CLAUDE.md § Tests`](memory_orchestrator_server/CLAUDE.md)
→ Hook test patterns: [`memory_orchestrator_mcp/CLAUDE.md § Tests`](memory_orchestrator_mcp/CLAUDE.md)

## Database

PostgreSQL 16 + pgvector + Apache AGE on port 5433.

```bash
# Local dev — after creating DB and enabling extensions:
cd memory_orchestrator_server
uv run alembic upgrade head

# New migration:
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

→ DB setup detail: [`memory_orchestrator_server/CLAUDE.md § Database`](memory_orchestrator_server/CLAUDE.md)

## Docker

Root-level Docker files and the compose entry point:

| Path | Role |
|---|---|
| `docker-compose.yml` | Compose file for `db`, `migrate`, `server` |
| `.env` | Compose environment file |
| `Dockerfile.db` | pgvector PostgreSQL 16 + Apache AGE image |
| `scripts/build.sh` | Full deployment entrypoint |
| `memory_orchestrator_server/Dockerfile.base` | Heavy base: apt deps, Python deps, BGE models |
| `memory_orchestrator_server/Dockerfile` | App image: frontend build, source, entry points |

`scripts/build.sh` manages hash-tagged images:

- `memory-orchestrator-db:<hash>` — from `Dockerfile.db`
- `memory-orchestrator-server-base:<hash>` — from `Dockerfile.base`, `pyproject.toml`, `uv.lock`, `download_models.py`

The script passes `MO_DB_IMAGE` and `MO_BASE_IMAGE` into `docker-compose up -d --build`,
waits for `/healthz`, then creates or rotates a `ui_admin` token and prints the token value.

```bash
./scripts/build.sh                                    # standard build
./scripts/build.sh --force                            # rebuild hash images unconditionally
DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain ./scripts/build.sh  # verbose CUDA build
```

The CUDA `torch` dependency chain is ~2.5 GiB on Linux x86_64. `Dockerfile.base` uses the
Tsinghua PyPI mirror (`UV_INDEX_URL`) and `UV_HTTP_TIMEOUT=300` to handle large downloads.
