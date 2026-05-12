# memory-orchestrator-mcp

Lightweight MCP client package for Memory Orchestrator. Provides hooks, client rules, and
agent/skill instructions that connect Claude Code and Codex to a running
`memory-orchestrator-server` instance.

Zero heavy dependencies: only `click`, `httpx`, and `mcp`.

## Requirements

- Python ≥ 3.11
- A running `memory-orchestrator-server` on `http://localhost:8765`
- Claude Code or Codex installed

## Installation

```bash
cd memory_orchestrator_mcp
uv sync
```

The server package's `mo-server setup` command installs this package automatically.
Manual installation is only needed for development or advanced setups.

## Setup

Use the server-side CLI, which reads the client rules from this package:

```bash
# From memory_orchestrator_server/:
uv run mo-server setup --client claude --scope user
uv run mo-server setup --client codex --scope user

# Verify:
uv run mo-server doctor --client claude
```

Or use the MCP package CLI directly (requires `mo-mcp` on PATH):

```bash
mo-mcp setup --client claude --scope user
mo-mcp teardown --client claude
mo-mcp doctor --client claude
```

## What setup installs

### Claude Code

- `UserPromptSubmit` hook → calls `hooks/user_prompt_submit.py`
- `Stop` hook → calls `hooks/stop.py`
- MCP server entry: `mo-mcp serve-mcp --client claude`
- Skill file: `~/.claude/skills/memory-orchestrator/SKILL.md`
- Env vars: `MO_CLIENT=claude`, `MO_HTTP_BASE_URL=http://localhost:8765`

### Codex

- `UserPromptSubmit` and `Stop` hooks in `~/.codex/hooks.json`
- MCP server entry in `~/.codex/config.toml`
- Agent instructions: `~/.codex/AGENTS.md`

## How it works

### Before each prompt — context injection

When you submit a prompt, the `UserPromptSubmit` hook fires:

1. Detects the current project (from git remote or path hash).
2. Calls `GET /context?project_slug=<id>` on the server.
3. Injects relevant memories as markdown into the prompt context.

### After each session — memory ingestion

When the session ends, the `Stop` hook fires:

1. Enforces a 5-minute cooldown (prevents spam on long sessions).
2. Posts the transcript path to `POST /ingest`.
3. The server uses an LLM to extract structured memories and stores them.

### During a session — MCP tools

Claude Code and Codex can call MCP tools directly:

| Tool | Description |
|---|---|
| `search_memory` | Semantic search across all memories |
| `save_memory` | Persist a new memory entry |
| `list_memories` | Browse memories for a project |
| `delete_memory` | Remove a memory |
| `promote_memory` | Increase a memory's importance |
| `ingest_session` | Trigger extraction from a specific transcript |

## Project scoping

Memories are scoped by project ID, derived deterministically:

```
git remote (SSH/HTTPS)  →  host/path  (e.g. github.com/org/repo)
       ↓ no remote
git root path  →  local:<name>-<hash>
       ↓ no git
cwd  →  local:<name>-<hash>
```

Memories with project ID `00000000-0000-0000-0000-000000000000` are global (shared across all projects).

## Configuration

The hook scripts read these env vars (set by `setup`, or override manually):

| Variable | Default | Purpose |
|---|---|---|
| `MO_HTTP_BASE_URL` | `http://localhost:8765` | Server base URL |
| `MO_CLIENT` | `claude` | Client identifier (`claude` or `codex`) |
| `MO_MCP_TOKEN` | _(from setup)_ | Bearer token for MCP tool calls |

## Tests

```bash
cd memory_orchestrator_mcp
uv run pytest
```
