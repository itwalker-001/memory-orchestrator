# memory-orchestrator-mcp

Lightweight MCP client package for Memory Orchestrator. Provides hooks, skill/agent instructions,
and a stdio MCP bridge that connect Claude Code and Codex to a running
`memory-orchestrator-server` instance.

Zero heavy dependencies: only `click`, `httpx`, and `mcp`.

## Requirements

- Python ≥ 3.11
- A running `memory-orchestrator-server` (default: `http://localhost:8765`)
- Claude Code or Codex installed

## Installation

```bash
cd memory_orchestrator_mcp
uv sync
```

## Setup

### 1. Create a project token on the server

Via the server UI at `http://<server>:8765/ui` → Admin → Tokens (select kind `project_token` and bind to a project), or call `POST /api/register` (localhost-only, no auth required).

### 2. Configure the current project

Run from the project root directory:

```bash
# Claude Code
mo-mcp setup --base-url http://<server>:8765 --project-token <TOKEN>

# Codex
mo-mcp setup --client codex --base-url http://<server>:8765 --project-token <TOKEN>

# Without flags — interactive prompts
mo-mcp setup
```

### 3. Verify

```bash
mo-mcp doctor
```

### Teardown

```bash
mo-mcp teardown               # Claude (default)
mo-mcp teardown --client codex
```

## What setup installs

### Claude Code (`--client claude`)

| Location | Content |
|---|---|
| `<project>/.mcp.json` | MCP server entry + `MO_MCP_TOKEN`, `MO_HTTP_BASE_URL` (add to `.gitignore`) |
| `<project>/.claude/settings.json` | `UserPromptSubmit` + `Stop` hooks |
| `<project>/.claude/skills/memory-orchestrator/SKILL.md` | Memory tool usage guide |

`claude mcp add --scope project -e MO_MCP_TOKEN=... -e MO_HTTP_BASE_URL=...` writes `.mcp.json`.

### Codex (`--client codex`)

| Location | Content |
|---|---|
| `~/.codex/config.toml` | MCP server entry + `MO_HTTP_BASE_URL` (global, no token) |
| `~/.codex/hooks.json` | `UserPromptSubmit` + `Stop` hooks (global) |
| `<project>/.mcp.json` | `MO_MCP_TOKEN`, `MO_HTTP_BASE_URL` (per-project, same file as Claude) |
| `~/.codex/AGENTS.md` | Memory tool usage guide (section-marker merge) |

Codex has no project-level config, so the token is stored per-project in `.mcp.json`.

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
| `save_memory` | Persist a new memory entry (supports `node_name`/`parent_node` for skeleton) |
| `list_memories` | Browse memories for a project |
| `delete_memory` | Remove a memory |
| `promote_memory` | Increase a memory's importance |
| `ingest_session` | Trigger extraction from a specific transcript |

## Token

The `project_token` is a server-issued bearer token bound to a specific project UUID.

| Client | Token location |
|---|---|
| Claude Code | `<project>/.mcp.json` → `mcpServers.memory-orchestrator.env.MO_MCP_TOKEN` |
| Codex | `<project>/.mcp.json` → same path |

`serve-mcp` token lookup order at startup:
```
<cwd>/.mcp.json  →  MO_MCP_TOKEN env  →  error
```

Add `.mcp.json` to `.gitignore` to keep the token private.

## Project scoping

Memories are scoped by project ID, derived deterministically:

```
git remote (SSH/HTTPS)  →  host/path  (e.g. github.com/org/repo)
       ↓ no remote
git root path  →  local:<name>-<hash>
       ↓ no git
cwd  →  local:<name>-<hash>
```

## Configuration

The hook scripts read these env vars (set by `setup`, or override manually):

| Variable | Default | Purpose |
|---|---|---|
| `MO_HTTP_BASE_URL` | `http://localhost:8765` | Server base URL |
| `MO_CLIENT` | `claude` | Client identifier (`claude` or `codex`) |
| `MO_MCP_TOKEN` | _(from .mcp.json)_ | Bearer token for MCP tool calls |

## Tests

```bash
cd memory_orchestrator_mcp
uv run pytest
```
