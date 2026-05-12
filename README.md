# Memory Orchestrator

Cross-project memory center for Claude Code and Codex. Collects, organizes, and serves
memories across all projects via MCP and HTTP API.

## Packages

| Package | Directory | Description | Docs |
|---------|-----------|-------------|------|
| `memory-orchestrator-server` | `memory_orchestrator_server/` | FastAPI server, PostgreSQL + pgvector + Apache AGE, embedder, frontend, MCP bridge | [README](memory_orchestrator_server/README.md) · [CLAUDE](memory_orchestrator_server/CLAUDE.md) |
| `memory-orchestrator-mcp` | `memory_orchestrator_mcp/` | Hooks, client rules, agent/skill instructions (zero heavy deps) | [README](memory_orchestrator_mcp/README.md) · [CLAUDE](memory_orchestrator_mcp/CLAUDE.md) |

## Quickstart

```bash
# 1. Ensure PostgreSQL 16 (+ pgvector + Apache AGE) is running
#    Default DSN: localhost:5433, user postgres, db memory_orchestrator

# 2. Install and set up the server
cd memory_orchestrator_server
uv sync
uv run alembic upgrade head
uv run python download_models.py   # BGE-M3 + reranker (~1 GB)

# 3. Wire hooks + MCP into your coding client
uv run mo-server setup --scope user              # Claude Code
uv run mo-server setup --client codex --scope user  # or Codex

# 4. Start the service
uv run mo-server serve-http                      # http://127.0.0.1:8765
```

Open Claude Code or Codex in any project. The `UserPromptSubmit` hook pre-injects relevant
memories; `save_memory` / `search_memory` MCP tools are available during the session;
the `Stop` hook extracts and persists new memories when the session ends.

→ Server installation detail: [`memory_orchestrator_server/README.md`](memory_orchestrator_server/README.md)
→ Client wiring detail: [`memory_orchestrator_mcp/README.md`](memory_orchestrator_mcp/README.md)

## Client setup

### Claude Code

```bash
cd memory_orchestrator_server
uv run mo-server setup --client claude --scope user
uv run mo-server doctor --client claude
```

Installs: `UserPromptSubmit` + `Stop` hooks, MCP server entry (`mo-mcp serve-mcp`),
skill file at `~/.claude/skills/memory-orchestrator/SKILL.md`.

### Codex

```bash
cd memory_orchestrator_server
uv run mo-server setup --client codex --scope user
uv run mo-server doctor --client codex
```

Writes: `~/.codex/config.toml`, `~/.codex/hooks.json`, `~/.codex/AGENTS.md`.

→ What each setup step installs: [`memory_orchestrator_mcp/README.md § What setup installs`](memory_orchestrator_mcp/README.md)

## Docker Deployment

Run from the **repository root**:

```bash
chmod +x scripts/build.sh
./scripts/build.sh
```

`scripts/build.sh` builds versioned images, starts `db` + `migrate` + `server` via
`docker-compose`, waits for `/healthz`, then creates or rotates a `ui_admin` token and
prints the token value.

| Image | Hash inputs |
|---|---|
| `memory-orchestrator-db:<hash>` | `Dockerfile.db` |
| `memory-orchestrator-server-base:<hash>` | `memory_orchestrator_server/Dockerfile.base`, `pyproject.toml`, `uv.lock`, `download_models.py` |

Regular app changes rebuild only `memory-orchestrator-server:latest`; DB and base images
are reused until their hash inputs change.

```bash
./scripts/build.sh --force                            # force rebuild hash images
./scripts/build.sh --admin-token-name admin           # set ui_admin token name
DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain ./scripts/build.sh  # uncollapsed build logs
```

The CUDA `torch` chain is ~2.5 GiB on Linux x86_64. `Dockerfile.base` uses the Tsinghua
PyPI mirror and `UV_HTTP_TIMEOUT=300` to handle slow downloads.

## Configuration

Env vars prefixed `MO_`, or a `.env` file in the repository root next to `docker-compose.yml`:

| Var | Default | Purpose |
|---|---|---|
| `MO_DB_DSN` | `postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator` | PostgreSQL connection |
| `MO_HTTP_PORT` | `8765` | HTTP port |
| `MO_EMBED_MODEL` | `BAAI/bge-m3` | Embedding model |
| `MO_DB_PORT` | `15432` (Docker) | Exposed Postgres port |
| `MO_PGDATA` | `./data/postgres` (Docker) | Postgres data directory |
| `MO_DB_IMAGE` | `memory-orchestrator-db:latest` | DB image override |
| `MO_BASE_IMAGE` | `memory-orchestrator-server-base:latest` | Base image override |

On a server, use an absolute data path:

```env
MO_PGDATA=/opt/memory-orchestrator/data/postgres
```

→ Full env var reference: [`memory_orchestrator_server/README.md § Configuration`](memory_orchestrator_server/README.md)
→ Hook env vars: [`memory_orchestrator_mcp/README.md § Configuration`](memory_orchestrator_mcp/README.md)

## Authentication

```bash
cd memory_orchestrator_server
uv run mo-server token create --kind ui_admin --name admin
uv run mo-server token create --kind mcp_client --name "local claude"
```

`mo-server setup` auto-injects `MO_MCP_TOKEN` into the client. Set `MO_UI_TOKEN` /
`MO_MCP_TOKEN` as env vars to bypass DB token checks in local dev.

→ Token detail: [`memory_orchestrator_server/README.md § Authentication`](memory_orchestrator_server/README.md)

## Tests

```bash
# Server (unit + integration)
cd memory_orchestrator_server
uv run pytest tests/unit/        # no DB required
uv run pytest tests/integration/ # needs Postgres on port 5433

# MCP client
cd memory_orchestrator_mcp
uv run pytest
```

Override test DB: `MO_TEST_DB_DSN=postgresql+asyncpg://postgres:1234@localhost:5433/mo_test`

→ Server test file listing: [`memory_orchestrator_server/CLAUDE.md § Tests`](memory_orchestrator_server/CLAUDE.md)
→ Hook test patterns: [`memory_orchestrator_mcp/CLAUDE.md § Tests`](memory_orchestrator_mcp/CLAUDE.md)

## Smoke Tests

After `mo-server serve-http` is running:

```bash
cd memory_orchestrator_server
uv run python scripts/smoke_save_search.py
uv run python scripts/smoke_ingest.py
```

## Docs

- AGE Graph Design: `docs/superpowers/specs/2026-05-11-apache-age-graph-reasoning-design.md`
- AGE Graph Plan: `docs/superpowers/plans/2026-05-11-apache-age-graph-reasoning.md`
