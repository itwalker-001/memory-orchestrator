# Tool Reference

Full parameter reference for the six `mcp__memory-orchestrator__*` tools, plus the
importance scale and `project_id` scoping rules.

## search_memory
```
query        (required) semantic search string
top_k        default 8
type         array of types to filter, e.g. ["feedback","project"]
project_id   omit = current project; "all" = every project; slug = specific
```

## save_memory
```
type         (required) user | feedback | project | reference
name         (required) short identifier
description  (required) one-line hook used for future retrieval
content      (required) full memory body
why          optional — reason behind rule/decision (feedback/project)
how_to_apply optional — when this memory kicks in
importance   integer 1–5 only, default 3 (out-of-range rejected)
replace_id   UUID of memory to supersede (soft-deletes old, saves new)
project_id   ignored — save always uses the token-bound current project
node_name    optional — skeleton leaf node name, e.g. "功能实现"
parent_node  optional — parent node name, e.g. "后端" (disambiguates node_name)
```

Parameter constraints:

- `content` must contain the actual memory body, not just a label or short reminder.
- For `project`, `reference`, and structured `feedback` memories, `content` should default to Markdown.
- Recommended Markdown shape:
  - short title or section heading when useful
  - flat bullet lists for stacks, steps, rules, or decisions
  - short concluding summary only when it adds retrieval value
- `project_id` does not redirect the save target and should normally be omitted.
- When routing into the tree, pass `parent_node` whenever `node_name` may exist under multiple branches.

For `node_name` / `parent_node` routing, see `skeleton-nodes.md`.

## list_memories
```
project_id   omit = current project; "all" = every project
type         single type string to filter
limit        default 50
```
Returns summaries only (no `content`). Use `search_memory` for full content retrieval.

## delete_memory
```
id           (required) UUID
hard         false = soft-delete (superseded); true = permanent
```
Prefer soft delete unless memory is wrong or sensitive.

## promote_memory
```
id           (required) UUID
importance   1–5
```
Use to boost the importance of a memory.

## ingest_session
```
session_id      (required)
transcript_path (required) absolute path to JSONL transcript
project_id      optional slug override
```
Extracts memories automatically from a conversation transcript via LLM.

## Hook context parameters

`UserPromptSubmit` hook context is fetched from `GET /context` using the Bearer token from
`.mcp.json`. The hook should not rely on `project_slug` / `project_id` query params to select the
project.

Supported context-shaping params:

```text
budget_tokens       optional total context budget
top_k               optional max number of injected memories
node_id             optional exact skeleton node id
node_name           optional node name
parent_node         optional parent name to disambiguate node_name
include_descendants optional bool, default true
client              optional client name, e.g. codex / claude
```

Guidance:

- Prefer `node_id` when the active node is known exactly.
- Otherwise pass `node_name` + `parent_node`.
- Use `top_k` and `budget_tokens` together when you need both count and size bounds.

## Importance Scale

Valid range: **1–5 only** (integers). Values outside this range are rejected by the database.

| Level | Meaning |
|-------|---------|
| 5 | Critical — must always apply |
| 4 | High — apply in most situations |
| 3 | Normal — default |
| 2 | Low — niche or decaying context |
| 1 | Minimal — may expire soon |

## project_id Scoping

```
omit           → current project ← default for most saves
"all"          → search across every project (read-only, for broad lookup)
specific slug  → pin to exact project (use for cross-project references)
```
