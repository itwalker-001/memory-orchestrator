# CLAUDE.md — memory_orchestrator_mcp

Developer guidance for the MCP client package. Run all commands from `memory_orchestrator_mcp/`.

## Commands

```bash
uv sync                  # Install dependencies
uv run pytest            # Run all tests

# CLI (requires uv run or installed entry point)
uv run mo-mcp setup --client claude --base-url http://<server>:8765 --project-token <TOKEN>
uv run mo-mcp setup --client codex  --base-url http://<server>:8765 --project-token <TOKEN>
uv run mo-mcp teardown --client claude   # Remove hooks + MCP server entry (project scope)
uv run mo-mcp doctor                     # Check client-side wiring + server reachability
uv run mo-mcp serve-mcp --client claude  # Start stdio MCP server (called by client, not by user)
```

`--base-url` and `--project-token` are required for `setup`.
Create a `project_token` first via the server UI (Admin → Tokens) or `POST /api/register` (localhost-only). The server CLI does not support creating `project_token` kind.

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
                                       Authorization: Bearer <project_token>
```

## Key modules

| File | Role |
|---|---|
| `cli.py` | `mo-mcp` entry point: `setup`, `teardown`, `doctor`, `serve-mcp` |
| `project_id.py` | Detect project slug from git remote or path hash |
| `hooks/user_prompt_submit.py` | Read event JSON → GET /context → emit context markdown |
| `hooks/stop.py` | Read event JSON → rate-limit → POST /ingest |
| `skills/memory-orchestrator/SKILL.md` | Installed to `<project>/.claude/skills/` by `setup` |
| `agents/memory-orchestrator.AGENTS.md` | Installed to `~/.codex/AGENTS.md` by `setup --client codex` |

## setup behavior

### `--client claude`

1. Calls `claude mcp add memory-orchestrator --scope project -e MO_MCP_TOKEN=<TOKEN> -e MO_HTTP_BASE_URL=<URL>` — writes `.mcp.json` with command, args, and env (including token).
2. Writes `UserPromptSubmit` and `Stop` hooks into `<cwd>/.claude/settings.json`.
3. Copies `SKILL.md` to `<cwd>/.claude/skills/memory-orchestrator/SKILL.md`.

Add `.mcp.json` to `.gitignore` — it contains the project token.

### `--client codex`

1. Patches `~/.codex/config.toml`:
   - Sets `[features] hooks = true`.
   - Writes `[mcp_servers.memory-orchestrator]` with `mo-mcp serve-mcp --client codex`.
   - Writes `MO_CLIENT`, `MO_HTTP_BASE_URL` into the MCP server env section (no token — global file).
2. Writes `~/.codex/hooks.json` in Codex array format (string commands).
3. Writes `MO_MCP_TOKEN` + `MO_HTTP_BASE_URL` into `<cwd>/.mcp.json` (per-project, same file as Claude).
4. Installs `AGENTS.md` into `~/.codex/AGENTS.md` using section markers (safe merge).

Codex has no project-level config, so the token is stored per-project in `.mcp.json`.
Add `.mcp.json` to `.gitignore`.

## Token storage

Both clients store the token in `<project>/.mcp.json`:

| Client | File | Key |
|---|---|---|
| Claude Code | `<project>/.mcp.json` | `mcpServers.memory-orchestrator.env.MO_MCP_TOKEN` |
| Codex | `<project>/.mcp.json` | same path |

`serve-mcp` token lookup order:
```
<cwd>/.mcp.json → MO_MCP_TOKEN env → RuntimeError
```

The token is a `project_token` bound to a specific project UUID on the server.
Authentication is enforced by `routers/mcp.py` via `resolve_project_token()`.

## Hook behavior

### `user_prompt_submit.py`

1. Read event JSON from stdin (`cwd`, `workspace_root`, session context).
2. Detect project ID via `project_id.py`.
3. Resolve server URL: `--base-url` CLI arg → `MO_HTTP_BASE_URL` env → `http://localhost:8765`.
4. `GET <base_url>/context?project_slug=<id>&client=<client>`.
5. Emit result:
   - **Claude**: plain text to stdout.
   - **Codex**: JSON `{ hookSpecificOutput: { hookEventName, additionalContext } }`.
6. Log to `~/.claude/memory-orchestrator/hook.log`.

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

## Tests

```
tests/
  test_project_id.py       Git remote normalization; path fallback; determinism
  test_hooks_codex.py      Hook stdin/stdout format; Codex JSON wrapping; state files
```

Tests mock `subprocess` and `urllib`; hooks are loaded via `runpy` to avoid import side effects.
Add new hook tests by providing synthetic stdin JSON and asserting stdout.
