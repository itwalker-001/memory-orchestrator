# memory-orchestrator-server

FastAPI server for Memory Orchestrator. Stores, embeds, and retrieves cross-project memories
for Claude Code and Codex via HTTP API, MCP bridge, and a web UI.

## Requirements

- Python ≥ 3.11
- PostgreSQL 16 with `pgvector` and `Apache AGE` extensions
- `uv` package manager

## Installation

```bash
cd memory_orchestrator_server
uv sync
```

## Setup

### 1. Database

PostgreSQL must be running. Default DSN: `postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator`.

```bash
uv run alembic upgrade head
```

Override the DSN:

```bash
export MO_DB_DSN=postgresql+asyncpg://user:pass@host:5432/dbname
```

### 2. Download models

BGE-M3 embedding model and BGE-reranker are required for memory search.

```bash
uv run python download_models.py
```

Models are saved to `models/BAAI/`. ModelScope is used as the download source.

### 3. Start the server

```bash
uv run mo-server serve-http
```

Server starts on `http://127.0.0.1:8765` by default.

### 4. Wire a coding client

```bash
# Claude Code
uv run mo-server setup --client claude --scope user
uv run mo-server doctor --client claude

# Codex
uv run mo-server setup --client codex --scope user
uv run mo-server doctor --client codex
```

## Configuration

Environment variables prefixed `MO_`, or a `.env` file next to the server directory.

| Variable | Default | Purpose |
|---|---|---|
| `MO_DB_DSN` | `postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator` | PostgreSQL connection |
| `MO_HTTP_HOST` | `127.0.0.1` | Bind address |
| `MO_HTTP_PORT` | `8765` | HTTP port |
| `MO_EMBED_MODEL` | `models/BAAI/bge-m3` | Embedding model path (relative to package) |
| `MO_EMBED_DIM` | `1024` | Embedding vector dimension |
| `MO_RERANK_MODEL` | `models/BAAI/bge-reranker-v2-m3` | Reranker model path |
| `MO_EXTRACTION_BASE_URL` | _(empty)_ | LLM extraction endpoint (OpenAI-compatible) |
| `MO_EXTRACTION_MODEL` | `gpt-4o-mini` | Model used for memory extraction |
| `MO_EXTRACTION_API_KEY` | `local` | API key for extraction LLM |
| `MO_LOG_LEVEL` | `DEBUG` | Python log level |
| `MO_LOG_DIR` | `./logs` | Rotating log file directory |

Runtime parameters (search weights, cooldown, graph depth, etc.) are stored in the
`system_settings` table and can be changed via the UI without restarting the server.

## Authentication

Tokens are required once any token row exists in the database.

```bash
uv run mo-server token create --kind ui_admin   --name admin
uv run mo-server token create --kind mcp_client --name "local claude"
uv run mo-server token list
uv run mo-server token revoke <token-id>
```

| Token kind | Protects |
|---|---|
| `ui_admin` | `/ui/*`, `/api/*` — web UI and management API |
| `mcp_client` | `/mcp/*` — MCP tool bridge |

The `setup` command automatically injects `MO_MCP_TOKEN` into the client environment.
Set `MO_UI_TOKEN` / `MO_MCP_TOKEN` as env vars to bypass the DB token check during local dev.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness check |
| `GET` | `/context` | Fetch memory context for a project (used by hooks) |
| `POST` | `/hooks/ingest` | Trigger session transcript ingestion |
| `POST` | `/mcp/tools/{tool}` | MCP tool call (Bearer `mcp_client` token) |
| `GET` | `/mcp/resources/{uri}` | MCP resource read |
| `GET/POST` | `/ui/memories` | List/search memories |
| `GET/PUT` | `/ui/memories/{id}` | Read/update a single memory |
| `GET/POST` | `/ui/tokens` | List/create tokens |
| `DELETE` | `/ui/tokens/{id}` | Revoke a token |
| `GET/POST` | `/ui/settings` | Read/update runtime settings |

## MCP tools

Available to Claude Code and Codex via the MCP bridge:

| Tool | Description |
|---|---|
| `search_memory` | Vector search + rerank, returns scored memories |
| `save_memory` | Create or update a memory entry |
| `list_memories` | List memories for a project |
| `delete_memory` | Soft-delete (supersede) a memory |
| `promote_memory` | Increase importance of a memory |
| `ingest_session` | Trigger LLM extraction from a transcript |

## Tests

```bash
uv run pytest tests/unit/         # No DB required
uv run pytest tests/integration/  # Requires Postgres

# Override test DB:
export MO_TEST_DB_DSN=postgresql+asyncpg://postgres:1234@localhost:5433/mo_test
```

Smoke tests (server must be running):

```bash
uv run python scripts/smoke_save_search.py
uv run python scripts/smoke_ingest.py
```

## Docker

Docker deployment is managed from the **repository root**, not from this directory.

```bash
cd ..
./scripts/build.sh
```

See the root `README.md` for full Docker workflow and image tagging strategy.
