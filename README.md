# Memory Orchestrator

Cross-project memory center for Claude Code. Collects, organizes, and serves
memories across all projects via MCP and HTTP API.

## Quickstart

```bash
# 1. Ensure local Postgres 16 is running with pgvector installed
#    (see scripts/README.md for Windows pgvector install)
#    Default DSN: localhost:5433, user postgres, db memory_orchestrator

# 2. Create test database (for integration tests)
#    psql -U postgres -c "CREATE DATABASE memory_orchestrator_test;"
#    psql -U postgres -d memory_orchestrator_test -c "CREATE EXTENSION vector; CREATE EXTENSION pgcrypto;"

# 3. Install
uv sync

# 4. Migrate DB
uv run alembic upgrade head

# 5. Wire hooks + MCP server into ~/.claude/settings.json
uv run mo setup --scope user

# 6. Run the service (in another terminal)
uv run mo serve-http
```

Open Claude Code in any project. The UserPromptSubmit hook pre-injects
relevant memories; `save_memory` / `search_memory` MCP tools are available.

## Configuration

Env vars (prefixed `MO_`), or `.env` in CWD:

| Var | Default |
|---|---|
| `MO_DB_DSN` | `postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator` |
| `MO_HTTP_PORT` | `8765` |
| `MO_EMBED_MODEL` | `BAAI/bge-small-zh-v1.5` |
| `MO_HAIKU_MODEL` | `claude-haiku-4-5` |

`ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` are reused from
`~/.claude/settings.json` (not re-prefixed).

## Tests

```bash
# Unit tests (no external deps)
pytest tests/unit/

# Integration tests (requires local Postgres on port 5433)
# Set MO_TEST_DB_DSN if needed (default: postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator_test)
pytest tests/integration/
```

## Smoke Tests

After `mo serve-http` is running:

```bash
# Save/search roundtrip via MCP
uv run python scripts/smoke_save_search.py

# Ingest a fake transcript (requires ANTHROPIC_AUTH_TOKEN)
uv run python scripts/smoke_ingest.py
```

## Docs

- Design: `docs/superpowers/specs/2026-04-21-memory-orchestrator-design.md`
- Plan: `docs/superpowers/plans/2026-04-21-memory-orchestrator.md`
