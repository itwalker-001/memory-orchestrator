---
name: memory-orchestrator
description: Use when saving, searching, or managing persistent memories across Claude Code sessions via the mcp__memory-orchestrator__ tools. Use when recalling prior context, storing user preferences, project decisions, feedback, or reference pointers.
---

# Memory Orchestrator MCP

## Overview

Persistent cross-session memory for Claude Code. Memories are scoped to a project (resolved
server-side from the `project_token` in `.mcp.json`). Six tools handle the full lifecycle.

## Memory Types

| Type | When to Save | Scope |
|------|-------------|-------|
| `user` | Role, expertise, communication preferences | Current project |
| `feedback` | AI corrected by user / bug fixed / confirmed good approach | Current project |
| `project` | 技术框架、选型、需求、整体设计、架构决策 | Current project |
| `reference` | Pointers to external resources, dashboards, issue trackers | Current project |

→ Detailed routing criteria, triggers, and write templates per type: see **memory-types.md**

## Proactive Save — When to Call save_memory Without Being Asked

**Rule: if any trigger below fires during a conversation, call `save_memory` immediately — do not wait for the user to say "remember this".**

| Signal | Type to save |
|--------|-------------|
| User corrects your output ("不要这样", "改成X", "你理解错了") | `feedback` |
| User confirms a non-obvious choice ("对", "就这样", accepts unusual approach without pushback) | `feedback` |
| Bug root cause traced to a repeatable AI mistake (wrong assumption, wrong API, wrong pattern) | `feedback` |
| User reveals their role, expertise level, or communication preference | `user` |
| A tech stack decision is made: language, library, framework chosen with reason | `project` |
| A module boundary, data model, or API design is decided | `project` |
| User mentions an external resource they'll need again (dashboard, tracker, wiki, DB) | `reference` |

### Anti-triggers — do NOT save

- Ephemeral task state ("正在实现X"、"下一步Y") → use tasks, not memory
- Information already in the codebase (derivable by reading files)
- Information already in a CLAUDE.md file
- Things that will change within this session

### How to save proactively

1. Finish the current response first — don't interrupt mid-task
2. After completing the response, silently call `save_memory` (no announcement needed unless user asks)
3. If `action == "conflict"`, inspect conflicts and use `replace_id` to supersede if same topic
4. For `project` / `feedback` / `reference`, route into the skeleton tree first — see **skeleton-nodes.md**

## Proactive Search — When to Call search_memory Without Being Asked

**Rule: call `search_memory` first before responding whenever any trigger below applies.**

| Trigger | What to search |
|---------|---------------|
| Starting work in a project (first message of session) | `type=["project","feedback"]` — load tech decisions and AI behavior rules |
| User asks "how does X work" / "why did we choose Y" | semantic query on the topic |
| About to recommend a library, pattern, or architecture | search for prior decisions on that topic |
| User mentions an external system, dashboard, or tracker | `type=["reference"]` — find the pointer |
| About to repeat an action Claude was previously corrected on | `type=["feedback"]` on that action |
| User seems to be a returning collaborator (not first session) | `type=["user"]` — load their preferences |

**How to search:**
1. Call `search_memory` with a semantic query — don't use keyword search
2. If results conflict with current code, trust the code; update or delete the stale memory
3. Never present memory content as fact without verifying against current files

## Tool Reference

Six tools: `search_memory`, `save_memory`, `list_memories`, `delete_memory`, `promote_memory`,
`ingest_session`.

→ Full parameter tables, importance scale, and `project_id` scoping: see **tools.md**

## Saving into the Skeleton Tree

Each project has its own skeleton tree of categories. Before saving any `project`, `feedback`, or
`reference` memory, fetch the live tree, pick the matching `node_name` (+ `parent_node`), then save.
`user` memories have no tree.

→ Full fetch / match / create-node / save workflow: see **skeleton-nodes.md**

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Passing `project_id` to `save_memory` to redirect a save | Ignored — save always uses the token-bound project; drop the arg |
| Acting on stale memory | Always verify against current files before recommending |
| Ignoring `conflict` response | Always check `action` field; use `replace_id` to merge |
| Hard-deleting by default | Use soft delete; hard delete only for wrong/sensitive content |
| Putting ephemeral task state in memory | Memory is cross-session; use tasks/plans for current-session state |
| Hardcoding the skeleton tree | Always fetch the live tree (skeleton-nodes.md); node names drift |
