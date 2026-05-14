# Project Skeleton — Design Spec
Date: 2026-05-14  
Status: Approved  
Approach: Phase B (期 1 core structure, 期 2 hook integration)

## Overview

Introduce a structured "skeleton" concept to Memory Orchestrator:
- Projects become explicit first-class entities (manually created, not auto-built from git hash)
- Each project has a multi-level skeleton tree (8 fixed first-level nodes + LLM-driven sub-nodes)
- Memories can be linked to skeleton nodes via an association table
- MCP tokens become project-scoped (`project_token` kind replaces `mcp_client`)
- The "New Memory" modal surfaces the skeleton tree as a guided form

---

## Scope

### 期 1 (This spec)
- DB: `project_skeleton_nodes` + `skeleton_node_memories` tables; `api_tokens` new `project_token` kind
- Backend API: project CRUD, skeleton node CRUD, memory-node association, project token issuance
- Ingestor: LLM assigns memories to skeleton nodes, creates sub-nodes dynamically
- Frontend: project creation, skeleton-aware new-memory modal, inline prompt_hint editing, token admin

### 期 2 (Follow-up spec)
- `mo-mcp` client: configure `project_token` replacing `MO_MCP_TOKEN`
- `GET /context` gains `?section=<node_id>` filter for skeleton-aware injection
- Hook-level section filtering based on token's project + active section

---

## Data Model

### New table: `project_skeleton_nodes`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | UUID FK → projects | NOT NULL |
| `parent_id` | UUID FK → self | NULL = top-level node |
| `name` | TEXT | NOT NULL |
| `description` | TEXT | NOT NULL DEFAULT '' |
| `prompt_hint` | TEXT | NOT NULL DEFAULT '' — shown in UI as fill guidance |
| `is_builtin` | BOOL | NOT NULL DEFAULT false — builtin nodes cannot be deleted |
| `sort_order` | INT | NOT NULL DEFAULT 0 |
| `created_at` | TIMESTAMPTZ | |

**Fixed first-level builtin nodes** (seeded on project creation, `is_builtin=true`):
需求 / 设计 / 前端 / 后端 / 测试 / 部署 / 经验库 / 决策记录

### New table: `skeleton_node_memories`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `skeleton_node_id` | UUID FK → project_skeleton_nodes | NOT NULL, CASCADE DELETE |
| `memory_id` | UUID FK → memories | NOT NULL |
| `created_at` | TIMESTAMPTZ | |
| UNIQUE | `(skeleton_node_id, memory_id)` | |

A memory may be linked to multiple nodes. Deleting a node cascades to association rows only; `memories` rows are untouched.

### Changed: `api_tokens.kind`

| kind | Purpose | Status |
|---|---|---|
| `ui_admin` | UI admin access | Unchanged |
| `project_token` | Project-scoped MCP access | **New** |
| `mcp_client` | Old global MCP | **Removed** — migration deletes all existing rows |

`project_token` rows must carry a valid `project_id` (enforced at application layer, not DB constraint).

### Unchanged: `memories`, `projects`

No schema changes. `projects.root_paths` column is kept but no longer written.

### Alembic migration

1. `CREATE TABLE project_skeleton_nodes`
2. `CREATE TABLE skeleton_node_memories`
3. `ALTER TABLE api_tokens ADD COLUMN project_id UUID REFERENCES projects(id) NULL`
4. `DELETE FROM api_tokens WHERE kind = 'mcp_client'`

---

## Backend API

All endpoints under `routers/ui.py`, protected by `ui_admin` token.

### Project management

| Method | Path | Behaviour |
|---|---|---|
| `POST` | `/api/projects` | Create project (slug + display_name); auto-seed 8 builtin skeleton nodes |
| `DELETE` | `/api/projects/{project_id}` | Delete project + skeleton nodes + associations |

### Skeleton nodes

| Method | Path | Behaviour |
|---|---|---|
| `GET` | `/api/projects/{project_id}/skeleton` | Return nested skeleton tree |
| `PATCH` | `/api/skeleton-nodes/{node_id}` | Update name / prompt_hint (builtin: prompt_hint only) |
| `DELETE` | `/api/skeleton-nodes/{node_id}` | Non-builtin nodes only |

Sub-nodes are not manually created via API — they are created dynamically by the ingestor (see below).

### Memory-node association

| Method | Path | Behaviour |
|---|---|---|
| `POST` | `/api/skeleton-nodes/{node_id}/memories` | Link memory to node; body: `{memory_id}` |
| `DELETE` | `/api/skeleton-nodes/{node_id}/memories/{memory_id}` | Unlink |

### Token issuance

`POST /api/tokens` — existing endpoint gains `project_token` kind support:
```json
{ "kind": "project_token", "project_id": "<uuid>", "name": "my project" }
```
Response includes the raw token value (shown once).

### `auth_tokens.py`

`validate_token()` returns `(token_row, project_id | None)`.  
For `project_token` kind, `project_id` is resolved from the token row and passed to MCP handlers.

---

## Ingestor Changes (`ingestor.py`)

When ingesting a transcript for a project that has a skeleton:

1. **Skeleton context**: Before calling LLM, fetch the project's skeleton tree (first-level nodes + existing sub-nodes).
2. **Prompt augmentation**: Append skeleton to extraction prompt:
   - List of first-level node names with their `prompt_hint`
   - Instruction: for each extracted memory, output `skeleton_node: {name, parent_name, create_if_missing: bool}`
3. **Post-processing**:
   - If `create_if_missing=true` and node doesn't exist → INSERT into `project_skeleton_nodes` (non-builtin)
   - Write `skeleton_node_memories` row linking memory ↔ node
4. **Fallback**: If LLM omits `skeleton_node`, memory is saved without skeleton association (no error).

---

## Frontend Changes

### Routing strategy

Introduce **Vue Router** (history mode). Existing `App.vue` is **not modified**.

Changes to existing files (minimal):
- `main.js`: wrap app with `createRouter` + `createWebHistory`; route `/ui/` → `App.vue`, `/ui/projects/` → `SkeletonPage.vue`
- `vite.config.js`: base stays `/ui/`, no other change needed

FastAPI `http_app.py`: SPA fallback already catches all `/ui/*` paths — no change needed.

### New file: `src/SkeletonPage.vue`

Completely new page at `/ui/projects/`. Shares `apiFetch` auth helper (extracted to `src/api.js`).

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  [← Memory Orchestrator]   Projects & Skeletons         ⚙  │
├──────────────┬──────────────────────────────────────────────┤
│  Projects    │  项目A                          [+ Token]    │
│  ──────────  │  ─────────────────────────────────────────── │
│  項目A  ●   │  Skeleton                                    │
│  项目B      │                                               │
│             │  ▶ 需求   ✎ (hover)                         │
│  [+ New]    │  ▶ 设计   ✎                                  │
│             │  ● 前端   ✎  ← selected                      │
│             │    ├ 组件  ✕                                  │
│             │    └ 页面  ✕                                  │
│             │  ▶ 后端   ✎                                  │
│             │  ▶ 测试   ✎                                  │
│             │  ▶ 部署   ✎                                  │
│             │  ▶ 经验库  ✎                                  │
│             │  ▶ 决策记录 ✎                                 │
│             │                                               │
│             │  [Selected node panel]                        │
│             │  prompt_hint: <editable inline>               │
│             │  Memories in this node: 3  [+ Add Memory]     │
└─────────────┴──────────────────────────────────────────────┘
```

#### Behaviour

- **Left panel**: project list, `[+ New]` button opens inline form (display_name input → POST `/api/projects`)
- **Right panel**: skeleton tree for selected project
  - First-level builtin nodes: name read-only, ✎ edits `prompt_hint` inline
  - Sub-nodes (LLM-created): ✎ edits name+prompt_hint, ✕ deletes (DELETE `/api/skeleton-nodes/{id}`)
  - Node hover → edit/delete icons appear
- **Selected node detail** (bottom of right panel): shows `prompt_hint` editable field + list of linked memories + `[+ Add Memory]` button
- **`[+ Add Memory]`**: opens a memory picker modal (search existing memories → POST link) OR a create+link flow (new memory form pre-filled with node's prompt_hint as placeholder)

#### New Memory create+link flow (on SkeletonPage)

```
┌──────────────────────────────────────────────────────┐
│  New Memory → 前端 / 组件                       ✕    │
│  📌 <prompt_hint guidance text>                      │
│  ──────────────────────────────────────────────      │
│  [user|feedback|project|reference]                   │
│  Name ___________________________________________    │
│  Description ____________________________________    │
│  Content                                             │
│  ┌──────────────────────────────────────────────┐   │
│  │                                              │   │
│  └──────────────────────────────────────────────┘   │
│  [Optional fields ▾]          [Cancel]  [Write]     │
└──────────────────────────────────────────────────────┘
```

Node context shown in header; prompt_hint as dimmed placeholder. On submit: POST `/api/memories` then POST `/api/skeleton-nodes/{id}/memories`.

#### Token management (on SkeletonPage)

`[+ Token]` button in project header → modal:
- `name` input + `kind = project_token` (fixed) → POST `/api/tokens`
- Response: show raw token in copy-to-clipboard box, "Shown once" warning

---

## 期 2 Preview (out of scope for this spec)

- `mo-mcp` CLI: `mo-mcp setup` emits `project_token` into Claude/Codex config instead of `mcp_client` token
- `GET /context?section=<node_id>`: filter injected memories by skeleton section
- `UserPromptSubmit` hook: reads current section from config, passes to `/context`

---

## Testing

### Unit tests (no DB)
- `test_skeleton_seed.py`: verify 8 builtin nodes created on project POST
- `test_ingestor_prompts.py`: verify skeleton context appended to extraction prompt
- `test_auth_tokens.py`: verify `project_token` resolves correct `project_id`

### Integration tests (Postgres)
- `test_repository.py`: skeleton CRUD, node cascade delete, association uniqueness
- `test_http_app.py`: POST /api/projects seeds nodes; DELETE cascades

### Frontend
- Manual smoke test: create project → open New Memory → verify two-panel layout → select node → Write → verify association via GET /api/skeleton-nodes/{id}/memories
