# CLAUDE.md — memory_orchestrator_mcp

Developer guidance for the MCP client package. Run all commands from `memory_orchestrator_mcp/`.

## Commands

```bash
uv sync                  # Install dependencies
uv run pytest            # Run all tests

# CLI (requires uv run or installed entry point)
uv run mo-mcp setup --client claude --base-url http://<server>:8765   # Wire Claude Code hooks + MCP server
uv run mo-mcp setup --client codex  --base-url http://<server>:8765   # Wire Codex hooks + MCP server
uv run mo-mcp teardown --client claude              # Remove hooks + MCP server entry
uv run mo-mcp doctor    --client claude             # Check client-side wiring
uv run mo-mcp serve-mcp --client claude             # Start stdio MCP server (called by client)
uv run mo-mcp register  --base-url http://<server>:8765  # Register / refresh MCP token only
```

`--base-url` is **required** for `setup` and `register`. No default — must point to the running
`memory_orchestrator_server` instance (e.g. `http://172.16.10.124:8765`).

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
        │                              GET <base_url>/context
        │                                   │
        │                           inject memories as markdown
        │
        ├── Stop hook ──────────────→ hooks/stop.py
        │                                   │
        │                              POST <base_url>/ingest
        │
        └── MCP tool call ──────────→ mo-mcp serve-mcp (stdio MCP)
                                            │
                                       POST <base_url>/mcp/tools/call
```

## Key modules

| File | Role |
|---|---|
| `cli.py` | `mo-mcp` entry point; `setup`, `teardown`, `doctor`, `register`, `serve-mcp` |
| `project_id.py` | Detect project slug from git remote or path hash |
| `hooks/user_prompt_submit.py` | Read event JSON → GET /context → emit context markdown |
| `hooks/stop.py` | Read event JSON → rate-limit → POST /ingest |
| `client_rules/claude.json` | Reference config for Claude Code (`~/.claude/settings.json`) |
| `client_rules/codex.json` | Reference config for Codex (`~/.codex/config.toml` + `hooks.json`) |
| `skills/memory-orchestrator/SKILL.md` | Installed to `~/.claude/skills/` by `setup` |
| `agents/memory-orchestrator.AGENTS.md` | Installed to `~/.codex/AGENTS.md` by `setup` |

## setup behavior

### `--client claude`

1. Calls `claude mcp add memory-orchestrator --scope user` to register the MCP bridge.
2. Writes `UserPromptSubmit` and `Stop` hooks into `~/.claude/settings.json`.
3. Writes `MO_HTTP_BASE_URL` into `~/.claude.json` MCP server env.
4. Calls `POST <base_url>/api/register` to obtain an `mcp_client` token and writes it to
   `~/.claude.json` env as `MO_MCP_TOKEN`.

### `--client codex`

1. Patches `~/.codex/config.toml`:
   - Sets `[features] hooks = true` (replaces deprecated `codex_hooks`).
   - Writes `[mcp_servers.memory-orchestrator]` with `mo-mcp serve-mcp --client codex`.
   - Writes `MO_CLIENT`, `MO_HTTP_BASE_URL` into the MCP server env section.
2. Writes `~/.codex/hooks.json` in the new Codex array format (string commands).
3. Calls `POST <base_url>/api/register` and writes `MO_MCP_TOKEN` into `config.toml` env.

## Hook behavior

### `user_prompt_submit.py`

1. Read event JSON from stdin (`cwd`, `workspace_root`, session context).
2. Detect project ID via `project_id.py`.
3. Resolve server URL: `--base-url` CLI arg → `MO_HTTP_BASE_URL` env → `http://localhost:8765`.
4. `GET <base_url>/context?project_slug=<id>&client=<client>`.
5. Emit result:
   - **Claude**: plain text to stdout.
   - **Codex**: JSON `{ hookSpecificOutput: { hookEventName, additionalContext } }`.
6. Log to `~/.claude/memory-orchestrator/hook.log` (or `$CODEX_HOME/memory-orchestrator/hook.log`).

### `stop.py`

1. Read event JSON from stdin (`session_id`, `transcript_path`, `cwd`).
2. Detect project ID.
3. Load state from `<state_dir>/stop-<session_id>.json`.
4. Enforce rate limit: 5-minute cooldown + minimum 1 user turn.
5. Resolve server URL: `--base-url` CLI arg → `MO_HTTP_BASE_URL` env → `http://localhost:8765`.
6. `POST <base_url>/ingest` with `session_id`, `project_slug`, `transcript_path`, `client`.
7. Update state file.

## Project ID detection

```
git remote (SSH or HTTPS)  →  normalized to  host/path
        ↓ no remote
git root path  →  SHA256 hash  →  local:<name>-<hash[:8]>
        ↓ no git
cwd  →  SHA256 hash
```

## Client rules format

`client_rules/*.json` are reference specs describing what `setup` writes to each client's config.
They are **not** applied automatically — `cli.py setup` implements the write logic directly.
Keep these files in sync with the `setup` command when changing config layout.

## Tests

```
tests/
  test_project_id.py       Git remote normalization; path fallback; determinism
  test_hooks_codex.py      Hook stdin/stdout format; Codex JSON wrapping; state files
```

Tests mock `subprocess` and `urllib`; hooks are loaded via `runpy` to avoid import side effects.
Add new hook tests by providing synthetic stdin JSON and asserting stdout.
