# Memory Orchestrator

Use the `memory-orchestrator` MCP server to save, search, and manage durable
memories across Codex sessions.

## Memory Types

| Type | When to Save | Scope |
|------|-------------|-------|
| `user` | Role, expertise, communication preferences | Always global |
| `feedback` | AI corrected / bug fixed / confirmed good approach | Project or global |
| `project` | Tech stack, architecture decisions, requirements, design | Current project |
| `reference` | Pointers to external resources, dashboards, trackers | Current project |

## Proactive Search — call search_memory before responding when:

| Trigger | Query |
|---------|-------|
| First message of session in a project | `type=["project","feedback"]` |
| About to recommend a library, pattern, or architecture | semantic query on topic |
| User mentions an external system, dashboard, or tracker | `type=["reference"]` |
| About to repeat an action you were previously corrected on | `type=["feedback"]` |
| User seems to be a returning collaborator | `type=["user"]` |

## Proactive Save — call save_memory immediately (without being asked) when:

| Signal | Type |
|--------|------|
| User corrects your output ("不要这样", "改成X") | `feedback` |
| User confirms a non-obvious choice (accepts unusual approach) | `feedback` |
| Bug root cause traced to a repeatable AI mistake | `feedback` |
| User reveals their role, expertise, or communication preference | `user` |
| Tech stack decision made: language, library, framework with reason | `project` |
| Module boundary, data model, or API design decided | `project` |
| User mentions an external resource they'll need again | `reference` |

Do NOT save: ephemeral task state, facts already in codebase, content already in AGENTS.md.

## Tool Reference

### search_memory
```
query        (required) semantic search string
top_k        default 3
type         array filter, e.g. ["feedback","project"]
project_id   omit = current + global; "all" = every project
```

### save_memory
```
type         (required) user | feedback | project | reference
name         (required) short identifier
description  (required) one-line hook used for future retrieval
content      (required) full memory body
why          reason behind rule/decision (feedback/project)
how_to_apply when this memory kicks in
importance   integer 1–5 only, default 3 (out-of-range rejected)
replace_id   UUID of memory to supersede
project_id   omit = auto; "global" = 00000000-...
```

Save workflow: call `save_memory` → check `action` field.
- `"created"` → done
- `"conflict"` → inspect `conflicts[]`, call again with `replace_id` to merge

### list_memories
```
project_id   omit = current + global; "all" = every project
type         single type string
limit        default 50
```

### delete_memory
```
id           (required) UUID
hard         false = soft-delete (default); true = permanent
```

### promote_memory
```
id           (required) UUID
importance   1–5
make_global  true = moves to global project
```

### ingest_session
```
session_id      (required)
transcript_path (required) absolute path to JSONL transcript
project_id      optional slug override
```

## Importance Scale

Valid range: **1–5 only** (integers outside this range are rejected).

| Level | Meaning |
|-------|---------|
| 5 | Critical — must always apply |
| 3 | Normal — default |
| 1 | Minimal — may expire soon |

## project_id Scoping

```
omit           → current project + global  ← default for most saves
"all"          → every project (read-only)
specific slug  → pin to exact project
```

`user` type auto-routes to global — omit `project_id` when saving user memories.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Acting on stale memory | Verify against current files first |
| Ignoring `conflict` response | Check `action` field; use `replace_id` to merge |
| Hard-deleting by default | Use soft delete; hard only for wrong/sensitive content |
| Saving ephemeral task state | Use tasks/plans, not memory |
