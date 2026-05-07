# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Migrate database
uv run alembic upgrade head

# Wire hooks + MCP into ~/.claude/settings.json
uv run mo setup --scope user

# Wire hooks + MCP into ~/.codex/config.toml and ~/.codex/hooks.json
uv run mo setup --client codex --scope user

# Start HTTP service (port 8765, keep running in separate terminal)
uv run mo serve-http

# Check wiring (DB reachable, MCP entry, hooks present)
uv run mo doctor
uv run mo doctor --client codex

# Run all unit tests (no external deps)
uv run pytest src/memory_orchestrator_server/tests/unit/ src/memory_orchestrator_mcp/tests/

# Run integration tests (requires Postgres on port 5433)
uv run pytest src/memory_orchestrator_server/tests/integration/

# Run a single test
uv run pytest src/memory_orchestrator_server/tests/unit/test_scoring.py::test_name -x

# Build frontend
cd src/memory_orchestrator_server/frontend && npm run build
```

## Architecture

Memory Orchestrator is split by runtime boundary:

- **Server package**: `memory_orchestrator_server`
  - Runs FastAPI via `mo serve-http`.
  - Owns PostgreSQL, pgvector, FastEmbed, Alembic, repository access, UI APIs, and hook APIs.
  - Source: `src/memory_orchestrator_server/`
- **Client MCP package**: `memory_orchestrator_mcp`
  - Owns hooks, client rules, client instructions (agents/skills).
  - Must stay lightweight: no DB, SQLAlchemy, FastEmbed, pgvector, or Alembic.
  - Source: `src/memory_orchestrator_mcp/`
- **Compat shims**: `memory_orchestrator`
  - Re-exports from `memory_orchestrator_server.*`. Existing code continues to work.
  - Source: `src/memory_orchestrator/`

New code should import from `memory_orchestrator_server` or `memory_orchestrator_mcp` directly.

### Request flow

```
UserPromptSubmit hook  →  GET /context  →  repo.build_context()  →  inject markdown
Stop hook              →  POST /ingest  →  ingestor.py  →  LLM extraction  →  repo.save()
Claude/Codex MCP call  →  mcp_server.py handler  →  repo.*()
```

### Key modules

| File | Role |
|---|---|
| `src/memory_orchestrator_server/models.py` | SQLAlchemy ORM: `Project`, `Memory`, `Session`, `MemoryLink`, `SystemSetting` |
| `src/memory_orchestrator_server/repository.py` | All DB operations; `get_settings()` reads `system_settings` table for runtime config |
| `src/memory_orchestrator_server/routers/hooks.py` | `/healthz`, `/context`, `/ingest` endpoints |
| `src/memory_orchestrator_server/routers/ui.py` | `/api/memories`, `/api/projects`, `/api/settings` (PATCH persists to `system_settings`) |
| `src/memory_orchestrator_server/ingestor.py` | Reads transcript JSONL incrementally (`sessions.last_offset`), calls OpenAI-compatible API to extract memories |
| `src/memory_orchestrator_server/embedder.py` | FastEmbed local vectorization; must set `HF_HUB_OFFLINE=1` after first download |
| `src/memory_orchestrator_server/scoring.py` | Hybrid re-ranking and token-budget truncation for context injection |
| `src/memory_orchestrator/client_adapters.py` | Client-specific setup/teardown for Claude Code and Codex |
| `src/memory_orchestrator/cli.py` | `mo` CLI entry point: `setup`, `teardown`, `serve-http`, `serve-mcp`, `doctor` |
| `src/memory_orchestrator_mcp/hooks/user_prompt_submit.py` | UserPromptSubmit hook: injects memory context |
| `src/memory_orchestrator_mcp/hooks/stop.py` | Stop hook: triggers session ingestion |

### Data model

- `projects`: slug (git remote URL or `local:<name>-<hash>`) → UUID. Global sentinel: `00000000-0000-0000-0000-000000000000` (slug `*`).
- `memories`: belongs to a project; `type` ∈ {user, feedback, project, reference}; `embedding vector(512)`; `superseded_by` for soft-delete chains.
- `system_settings`: key-value table; read on every request via `repo.get_settings()` — no restart needed for most config changes.
- `sessions`: tracks ingestion progress per session (`last_offset` for incremental reads, `status` ∈ pending/done/failed).

### Runtime config (system_settings)

All settings are editable at `/ui` → Settings without restart, except `db_dsn` and `http_port` which require a service restart. Keys: `hook_budget_tokens`, `hook_cooldown_sec`, `hook_min_turns`, `search_top_k`, `dup_threshold`, `extraction_base_url`, `extraction_model`, `embed_model`, `embed_dim`.

### Hooks

- `src/memory_orchestrator_mcp/hooks/user_prompt_submit.py` — reads Claude env or Codex hook JSON, calls `/context`, writes markdown for Claude or `hookSpecificOutput.additionalContext` JSON for Codex.
- `src/memory_orchestrator_mcp/hooks/stop.py` — reads transcript JSONL to count new user turns; fires `/ingest` if cooldown and min-turns thresholds are met; persists state under `~/.claude/memory-orchestrator/` or `~/.codex/memory-orchestrator/`.
- Hook commands use `uv run --no-sync --project <abs-path> python <hook.py>` — `--no-sync` prevents uv from trying to reinstall the package, which would fail with a file-lock error when `mo serve-http` is already running.

### Frontend

Vue 3 + Vite SPA in `src/memory_orchestrator_server/frontend/`. Served statically by FastAPI at `/ui`. Build output goes to `frontend/dist/`. After any frontend change, run `npm run build` in `src/memory_orchestrator_server/frontend/`.

### Database

PostgreSQL 16 + pgvector on port 5433. Integration tests use a separate `memory_orchestrator_test` database. Override with `MO_TEST_DB_DSN`.
