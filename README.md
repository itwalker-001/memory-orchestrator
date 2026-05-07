# Memory Orchestrator

Cross-project memory center for Claude Code and Codex. Collects, organizes, and serves
memories across all projects via MCP and HTTP API.

## Packages

| Package | Directory | Description |
|---------|-----------|-------------|
| `memory-orchestrator-server` | `memory_orchestrator_server/` | FastAPI server, PostgreSQL, embedder, frontend, MCP bridge |
| `memory-orchestrator-mcp` | `memory_orchestrator_mcp/` | Hooks, client rules, agent/skill instructions (zero deps) |

## Quickstart

```bash
# 1. Ensure local Postgres 16 is running with pgvector installed
#    Default DSN: localhost:5433, user postgres, db memory_orchestrator
#    (see memory_orchestrator_server/src/memory_orchestrator_server/scripts/README.md for Windows pgvector install)

# 2. Install server package
cd memory_orchestrator_server
uv sync

# 3. Migrate DB
uv run alembic upgrade head

# 4. Wire hooks + MCP server into a coding client
uv run mo-server setup --scope user
# or for Codex:
uv run mo-server setup --client codex --scope user

# 5. Run the service (in another terminal)
uv run mo-server serve-http
```

Open Claude Code or Codex in any project. The UserPromptSubmit hook pre-injects
relevant memories; `save_memory` / `search_memory` MCP tools are available.

## Client Setup

Claude Code (default):
```bash
cd memory_orchestrator_server
uv run mo-server setup --client claude --scope user
uv run mo-server doctor --client claude
```

Codex — writes `~/.codex/config.toml`, `~/.codex/hooks.json`, and `~/.codex/AGENTS.md`:
```bash
cd memory_orchestrator_server
uv run mo-server setup --client codex --scope user
uv run mo-server doctor --client codex
```

## Configuration

Env vars (prefixed `MO_`), or `.env` in `memory_orchestrator_server/`:

| Var | Default |
|---|---|
| `MO_DB_DSN` | `postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator` |
| `MO_HTTP_PORT` | `8765` |
| `MO_EMBED_MODEL` | `BAAI/bge-small-zh-v1.5` |

## Authentication

```bash
cd memory_orchestrator_server
uv run mo-server token create --kind ui_admin --name admin
uv run mo-server token create --kind mcp_client --name "local claude"
```

## Tests

```bash
# Server (unit + integration, run from memory_orchestrator_server/)
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/        # no DB needed
uv run pytest src/memory_orchestrator_server/tests/integration/ # needs Postgres

# MCP client (run from memory_orchestrator_mcp/)
cd memory_orchestrator_mcp
uv run pytest
```

Set `MO_TEST_DB_DSN` to override the test database DSN
(default: `postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator_test`).

## Smoke Tests

After `mo-server serve-http` is running:

```bash
cd memory_orchestrator_server
uv run python src/memory_orchestrator_server/scripts/smoke_save_search.py
uv run python src/memory_orchestrator_server/scripts/smoke_ingest.py
```

## Docs

- Design: `docs/superpowers/specs/2026-04-21-memory-orchestrator-design.md`
- Plan: `docs/superpowers/plans/2026-04-21-memory-orchestrator.md`
