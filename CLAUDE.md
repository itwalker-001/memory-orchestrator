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

# Run unit tests (no external deps)
uv run pytest tests/unit/

# Run integration tests (requires Postgres on port 5433)
uv run pytest tests/integration/

# Run a single test
uv run pytest tests/unit/test_scoring.py::test_name -x

# Build frontend
cd src/memory_orchestrator_server/frontend && npm run build
```

## Architecture

Two separate processes serve different clients:

- **`mo serve-http`** — FastAPI on port 8765. Used by hooks (`/context`, `/ingest`) and the browser UI (`/ui`). Must be started manually.
- **`mo serve-mcp`** — MCP stdio server. Registered in `~/.claude/settings.json` or `~/.codex/config.toml` via `mo setup`; the client launches it automatically per-session.

Both processes share the same PostgreSQL database and `MemoryRepository`.

### Request flow

```
UserPromptSubmit hook  →  GET /context  →  repo.build_context()  →  inject markdown
Stop hook              →  POST /ingest  →  ingestor.py  →  LLM extraction  →  repo.save()
Claude/Codex MCP call  →  mcp_server.py handler  →  repo.*()
```

### Key modules

| File | Role |
|---|---|
| `models.py` | SQLAlchemy ORM: `Project`, `Memory`, `Session`, `MemoryLink`, `SystemSetting` |
| `repository.py` | All DB operations; `get_settings()` reads `system_settings` table for runtime config |
| `router_hooks.py` | `/healthz`, `/context`, `/ingest` endpoints |
| `router_ui.py` | `/api/memories`, `/api/projects`, `/api/settings` (PATCH persists to `system_settings`) |
| `mcp_server.py` | MCP tools: `save_memory`, `search_memory`, `list_memories`, `delete_memory`, `promote_memory`, `ingest_session` |
| `ingestor.py` | Reads transcript JSONL incrementally (`sessions.last_offset`), calls OpenAI-compatible API to extract memories |
| `embedder.py` | FastEmbed local vectorization; must set `HF_HUB_OFFLINE=1` after first download |
| `scoring.py` | Hybrid re-ranking and token-budget truncation for context injection |
| `client_adapters.py` | Client-specific setup/teardown for Claude Code and Codex |
| `cli.py` | `mo` CLI entry point: `setup`, `teardown`, `serve-http`, `serve-mcp`, `doctor` |

### Data model

- `projects`: slug (git remote URL or `local:<name>-<hash>`) → UUID. Global sentinel: `00000000-0000-0000-0000-000000000000` (slug `*`).
- `memories`: belongs to a project; `type` ∈ {user, feedback, project, reference}; `embedding vector(512)`; `superseded_by` for soft-delete chains.
- `system_settings`: key-value table; read on every request via `repo.get_settings()` — no restart needed for most config changes.
- `sessions`: tracks ingestion progress per session (`last_offset` for incremental reads, `status` ∈ pending/done/failed).

### Runtime config (system_settings)

All settings are editable at `/ui` → Settings without restart, except `db_dsn` and `http_port` which require a service restart. Keys: `hook_budget_tokens`, `hook_cooldown_sec`, `hook_min_turns`, `search_top_k`, `dup_threshold`, `extraction_base_url`, `extraction_model`, `embed_model`, `embed_dim`.

### Hooks

- `hooks/user_prompt_submit.py` — reads Claude env or Codex hook JSON, calls `/context`, writes markdown for Claude or `hookSpecificOutput.additionalContext` JSON for Codex.
- `hooks/stop.py` — reads transcript JSONL to count new user turns; fires `/ingest` if cooldown and min-turns thresholds are met; persists state under `~/.claude/memory-orchestrator/` or `~/.codex/memory-orchestrator/`.
- Hook commands use `uv run --no-sync --project <abs-path> python <hook.py>` — `--no-sync` prevents uv from trying to reinstall the package, which would fail with a file-lock error when `mo serve-http` is already running.

### Frontend

Vue 3 + Vite SPA in `frontend/`. Served statically by FastAPI at `/ui`. Build output goes to `frontend/dist/`. After any frontend change, run `npm run build` in `frontend/`.

### Database

PostgreSQL 16 + pgvector on port 5433. Integration tests use a separate `memory_orchestrator_test` database. Override with `MO_TEST_DB_DSN`.
