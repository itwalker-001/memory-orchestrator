# Skeleton Nodes — Organizing Memories into a Project Tree

Full workflow for routing a memory into the project's skeleton tree. Read this when
saving a `project`, `feedback`, or `reference` memory. `user` memories have no tree —
skip this file for them.

Each project has its own skeleton tree (categories). Before saving any `project`, `feedback`, or
`reference` memory, **fetch the live tree from the server** and pick the matching `node_name`
(+ `parent_node` to disambiguate). Do NOT rely on a hardcoded tree — node names are user-editable
and drift over time; always read the current structure.

## Step 1 — Fetch the live skeleton tree

Run the helper script shipped with this skill — **do not hand-write the request each time.** It reads
`MO_HTTP_BASE_URL` and `MO_MCP_TOKEN` from the project's `.mcp.json`
(`mcpServers.memory-orchestrator.env`), calls `GET {base}/mcp/skeleton` with the Bearer token, and
prints every node as `path` + `prompt_hint` for routing. The token identifies the project, so no
`project_slug` is needed.

```bash
# From the project root (where .mcp.json lives). Use `python`/`python3` if `py` is unavailable.
py .claude/skills/memory-orchestrator/scripts/fetch_skeleton.py
```

Output (one block per node, deepest paths included):

```
project_id: e42d2fe9-...
------------------------------------------------------------
技术栈
    hint: 记录技术选型：框架、数据库、ORM、中间件、消息队列、基础设施
    tags: stack, tech
技术栈/前端技术栈
    hint: (empty)
    tags: (none)
...
```

`hint` is the primary routing signal; `tags` are a secondary tie-breaker (see Step 2).

- **Script:** `.claude/skills/memory-orchestrator/scripts/fetch_skeleton.py` (stdlib only; installed by `mo-mcp setup`)
- **Endpoint it calls:** `GET {MO_HTTP_BASE_URL}/mcp/skeleton`
- **Auth:** `Authorization: Bearer {MO_MCP_TOKEN}` (both read from `.mcp.json`)
- **Raw response shape** (if you need to call the endpoint directly):
  ```json
  {
    "project_id": "e42d2fe9-...",
    "skeleton": [
      {
        "id": "...", "name": "技术栈", "parent_id": null, "sort_order": 3,
        "description": "...", "prompt_hint": "...", "is_builtin": true,
        "tags": ["stack","tech"],
        "children": [ { "name": "前端技术栈", "parent_id": "...", "children": [] } ]
      }
    ]
  }
  ```

The script flattens the nested `children[]` for you. Each node carries a `prompt_hint` describing what
belongs there — use it to choose the right node (Step 2).

Cache the script output for the duration of the session; re-run it if a save returns an unknown-node
error or the user edits the tree.

## Step 2 — Match content to a node

**`prompt_hint` is the primary signal; `tags` are a secondary signal.** Each node in the fetched tree
carries a `prompt_hint` written by the project owner that describes exactly what content belongs there
(e.g. 技术栈's hint: "记录技术选型：框架、数据库、ORM、中间件、消息队列、基础设施"), plus a `tags`
array of short keywords. To route a memory:

1. **Primary — `prompt_hint`:** read the `prompt_hint` of each candidate node and pick the one whose
   hint best describes the memory's content. The hint is authoritative — it reflects the owner's
   intent and overrides the generic routing table below.
2. **Secondary — `tags`:** when two or more nodes' hints fit similarly well (or a hint is borderline),
   use `tags` to break the tie — prefer the node whose tags overlap the memory's keywords/topic.
3. **Fallback — `name` / `description`:** use these only when a node has an empty `prompt_hint` and no
   informative `tags`.
4. Prefer the most specific (deepest) node whose signals still match; don't stop at a broad parent if
   a child fits better.

Then pass:

- `node_name` = the chosen node's `name`
- `parent_node` = the parent node's `name` (required when `node_name` is ambiguous across branches,
  e.g. `功能实现` may exist under both `前端` and `后端`)

Omit both for `user` type (user memories have no tree).

### Routing guide (fallback when `prompt_hint` is empty/ambiguous)

The built-in top-level nodes are: `项目概况`, `需求`, `设计`, `技术栈`, `前端`, `后端`, `数据库`,
`测试`, `部署`, `决策记录`, `经验库`. Use this only when `prompt_hint` doesn't settle it (verify the
node still exists in the fetched tree first):

| Signal | node_name | parent_node |
|--------|-----------|-------------|
| Project overview / goals / architecture | 项目概况 | _(omit)_ |
| Requirements / user stories / breakdown | 需求 | _(omit)_ |
| Architecture / interface / data-model design | 设计 | _(omit)_ |
| Tech stack choice (framework, DB, infra) | 技术栈 | _(omit)_ |
| Specific frontend stack (e.g. Vue) | 前端技术栈 | 技术栈 |
| Frontend feature / bug / optimization | 前端 | _(omit)_ |
| Backend feature / bug / service logic | 后端 | _(omit)_ |
| DB schema / index / SQL tuning / migration | 数据库 | _(omit)_ |
| Unit / integration / e2e test, mock | 测试 | _(omit)_ |
| Deploy config / CI/CD / Docker / release | 部署 | _(omit)_ |
| Why we chose tech X / architecture tradeoff | 决策记录 | _(omit)_ |
| Reusable tip / pitfall / debug technique | 经验库 | _(omit)_ |

For user-created child nodes (`is_builtin: false`), use the exact `name` from the fetched tree and
set `parent_node` to its parent's `name`.

## Step 2b — Create a node when none fits

If, after walking the fetched tree, **no existing node is a good fit**, create a new one on demand by
running the helper script shipped with this skill — **don't hand-write the request.** It reads the base
URL and token from `.mcp.json` and POSTs to `{base}/mcp/skeleton`. Prefer nesting the new node under the
closest matching built-in top-level node rather than adding more root nodes.

```bash
# From the project root (where .mcp.json lives). Use `python`/`python3` if `py` is unavailable.
py .claude/skills/memory-orchestrator/scripts/create_skeleton_node.py \
  --name 前端技术栈 --parent 技术栈 \
  --hint "记录前端框架、UI库、状态管理、构建工具的选型与版本"
```

Output:

```
project_id: e42d2fe9-...
node_id:    d51ab323-...
node '前端技术栈' under '技术栈' ready.
```

- **Script:** `.claude/skills/memory-orchestrator/scripts/create_skeleton_node.py` (stdlib only; installed by `mo-mcp setup`)
- **Args:**
  - `--name` (required) — the new node's name
  - `--parent` (optional) — parent node's `name`; omit to create a top-level node
  - `--hint` (recommended) — one line describing what content belongs in this node. **Always set
    this** — it becomes the primary routing signal (Step 2) for future memories, so an empty hint
    makes the node hard to route into later.
  - `--desc` (optional) — longer description of the node's scope
  - `--mcp-json` (optional) — path to `.mcp.json` (default: `./.mcp.json`)
- **Endpoint it calls:** `POST {MO_HTTP_BASE_URL}/mcp/skeleton` with `Authorization: Bearer {MO_MCP_TOKEN}`
- **Idempotent:** if a node with the same `name`+parent already exists, the existing `node_id` is
  returned (no duplicate created). A non-empty `--hint`/`--desc` backfills the existing node if it was
  previously blank — safe to call without checking first.

After creating, re-run Step 1 so the cached tree includes the new node, then proceed to Step 3 using
the new node's `name` (and `parent_name`).

**When to create vs. reuse:** only create a node for a genuinely new, recurring category. For a
one-off memory that loosely fits an existing node, reuse the existing node — don't grow the tree with
near-duplicates.

## Step 3 — Save workflow

1. Call `save_memory` with the chosen `node_name` / `parent_node` → check `action` field
2. `"created"` → done
3. `"conflict"` → inspect `conflicts[]`, then either call again with `replace_id` or drop
4. If the save reports an unknown node, either re-fetch the skeleton (Step 1) or create the node
   (Step 2b), then retry
