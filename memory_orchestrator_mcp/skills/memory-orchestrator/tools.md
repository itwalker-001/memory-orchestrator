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
