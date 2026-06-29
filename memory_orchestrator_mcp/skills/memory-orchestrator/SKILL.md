---
name: memory-orchestrator
description: >
  Use when saving, searching, or managing persistent memories across Claude Code sessions via the
  mcp__memory-orchestrator__ tools. Triggers: user asks to remember something ("记住这个", "帮我记一下",
  "保存这个", "记下来"), recall prior context ("之前说过什么", "上次的决定是什么", "还记得吗", "之前怎么做的"),
  store user preferences / project decisions / feedback / reference pointers, correct AI behavior that
  should persist ("不要这样", "下次别", "记住以后"), or at the start of a session when prior project
  context should be loaded. Also use proactively after any significant decision, correction, or new
  preference is expressed.
---

# Memory Orchestrator MCP

## Invocation Triggers

Load this skill automatically when the user says any of:

| Language | Phrases |
|----------|---------|
| 中文 | 记住 / 帮我记 / 记下来 / 保存这个 / 之前说过什么 / 上次的决定 / 还记得吗 / 之前怎么做的 / 不要这样（需跨会话持久化）/ 下次别忘了 / 记忆 |
| English | remember / recall / save this / what did we decide / prior context / persist / don't forget / last time / previous decision |

Also load at the **start of a session** for returning users to pre-load `project` and `feedback` memories before starting work.

Explicit invocation (always works): `/memory-orchestrator <query or instruction>`

---

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

### Save parameter constraints

- `content` is the full memory body, not a title or one-line summary.
- For structured memories such as tech stacks, architecture notes, workflows, conventions, incident notes,
  and decision records, write `content` in Markdown by default.
- Prefer Markdown headings and flat lists for `project`, `reference`, and long-form `feedback` memories.
- If the memory belongs to the skeleton tree, pass `node_name` and `parent_node` when needed to disambiguate.
- Do not pass `project_id` to redirect a save; the token-bound project is authoritative.

Recommended default:

```text
project / reference / structured feedback -> content uses Markdown
user / short feedback -> plain text is acceptable unless structure helps
```

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

## Hook parameter constraints

For hook-driven context injection, the current project must be resolved from the Bearer token, not from
`project_slug` or `project_id` query parameters.

- `UserPromptSubmit` -> `GET /context`
- Required auth -> `Authorization: Bearer {MO_MCP_TOKEN}`
- Project identity -> token-bound only
- Context shaping params may include:
  - `budget_tokens`
  - `top_k`
  - `node_id`
  - `node_name`
  - `parent_node`
  - `include_descendants`
  - `client`

Default guidance:

- Use `budget_tokens` to cap total injected context size.
- Use `top_k` to cap the number of injected memories.
- Use `node_id` when the active skeleton node is known exactly.
- Otherwise use `node_name` plus `parent_node` for disambiguation.
- Do not rely on URL project selectors for hooks.

## Update

When user says `/memory-orchestrator update` or asks to "update the MCP client" / "升级 MCP":

Run in terminal:
```bash
mo-mcp update                      # Claude Code
mo-mcp update --client codex       # Codex
```

This downloads the latest `memory-orchestrator-mcp` wheel from the MO server, installs it via
`uv tool install`, and syncs skill files — without touching hooks, tokens, or server config.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Passing `project_id` to `save_memory` to redirect a save | Ignored — save always uses the token-bound project; drop the arg |
| Acting on stale memory | Always verify against current files before recommending |
| Ignoring `conflict` response | Always check `action` field; use `replace_id` to merge |
| Hard-deleting by default | Use soft delete; hard delete only for wrong/sensitive content |
| Putting ephemeral task state in memory | Memory is cross-session; use tasks/plans for current-session state |
| Hardcoding the skeleton tree | Always fetch the live tree (skeleton-nodes.md); node names drift |
