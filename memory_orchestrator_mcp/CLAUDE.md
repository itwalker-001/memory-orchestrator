# CLAUDE.md — memory_orchestrator_mcp

Developer guidance for the MCP client package. Run all commands from `memory_orchestrator_mcp/`.

## Commands

```bash
uv sync                  # Install dependencies
uv run pytest            # Run all tests

# CLI (requires uv run or installed entry point)
mo-mcp setup --client claude --scope user    # Wire Claude Code hooks + MCP server
mo-mcp setup --client codex --scope user     # Wire Codex hooks + MCP server
mo-mcp teardown --client claude              # Remove hooks + MCP server entry
mo-mcp doctor --client claude                # Check client-side wiring
mo-mcp serve-mcp --client claude             # Start stdio MCP server (called by client)
```

## Package constraints

This package **must stay lightweight**. Never add:

- `sqlalchemy`, `alembic`, `pgvector` — DB belongs in the server
- `torch`, `transformers`, `FlagEmbedding` — ML belongs in the server
- Any dependency not already in `pyproject.toml` without explicit justification

Allowed: `click`, `httpx`, `mcp`. Dev: `pytest`.

## Architecture

```
Client (Claude Code / Codex)
        │
        ├── UserPromptSubmit hook ──→ hooks/user_prompt_submit.py
        │                                   │
        │                              GET /context (HTTP → server)
        │                                   │
        │                           inject memories as markdown
        │
        ├── Stop hook ──────────────→ hooks/stop.py
        │                                   │
        │                              POST /ingest (HTTP → server)
        │
        └── MCP tool call ──────────→ mo-mcp serve-mcp (stdio MCP)
                                            │
                                       POST /mcp/tools/call (HTTP → server)
```

## Key modules

| File | Role |
|---|---|
| `cli.py` | `mo-mcp` entry point; `setup`, `teardown`, `doctor`, `serve-mcp` |
| `project_id.py` | Detect project slug from git remote or path hash |
| `hooks/user_prompt_submit.py` | Read event JSON → GET /context → emit context markdown |
| `hooks/stop.py` | Read event JSON → rate-limit → POST /ingest |
| `client_rules/claude.json` | Config patches applied to `~/.claude/settings.json` |
| `client_rules/codex.json` | Config patches applied to `~/.codex/config.toml` + `hooks.json` |
| `skills/memory-orchestrator/SKILL.md` | Installed to `~/.claude/skills/` by `setup` |
| `agents/memory-orchestrator.AGENTS.md` | Installed to `~/.codex/AGENTS.md` by `setup` |

## Hook behavior

### `user_prompt_submit.py`

1. Read event JSON from stdin (`cwd`, `workspace_root`, session context).
2. Detect project ID via `project_id.py`.
3. `GET http://localhost:8765/context?project_slug=<id>&client=<client>`.
4. Emit result:
   - **Claude**: plain text to stdout.
   - **Codex**: JSON `{ hookSpecificOutput: { additionalContext: "..." } }`.
5. Log to `~/.claude/memory-orchestrator/hook.log` (or `$CODEX_HOME/...`).

### `stop.py`

1. Read event JSON from stdin (`session_id`, `transcript_path`, `cwd`).
2. Detect project ID.
3. Load state from `~/.claude/memory-orchestrator/stop-<session_id>.json`.
4. Enforce rate limit: 5-minute cooldown + minimum 1 user turn.
5. `POST http://localhost:8765/ingest` with `session_id`, `project_slug`, `transcript_path`, `client`.
6. Update state file.

## Project ID detection

```
git remote (SSH or HTTPS)  →  normalized to  host/path
        ↓ no remote
git root path  →  SHA256 hash  →  local:<name>-<hash[:8]>
        ↓ no git
cwd  →  SHA256 hash
```

## Client rules format

`client_rules/*.json` files contain `patches` — arrays of operations applied to client config files.
The server's `client_rules.py` reads these and performs the patch when `setup` runs.
Do not introduce new patch operations without updating `client_rules.py` accordingly.

## Tests

```
tests/
  test_project_id.py       Git remote normalization; path fallback; determinism
  test_hooks_codex.py      Hook stdin/stdout format; Codex JSON wrapping; state files
```

Tests mock `subprocess` and `urllib`; hooks are loaded via `runpy` to avoid import side effects.
Add new hook tests by providing synthetic stdin JSON and asserting stdout.
