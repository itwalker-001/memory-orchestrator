# Memory Orchestrator

Use the `memory-orchestrator` MCP server to save, search, and manage durable
memories across Codex sessions.

## Memory Types

| Type | When to Save | Scope |
|------|-------------|-------|
| `user` | Role, expertise, communication preferences | Current project |
| `feedback` | AI corrected / bug fixed / confirmed good approach | Current project |
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
project_id   omit = current project; "all" = every project
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
project_id   ignored — save always uses the token-bound current project
node_name    optional — skeleton leaf node name, e.g. "功能实现"
parent_node  optional — parent node, e.g. "后端" (disambiguates node_name)
```

## Skeleton Nodes — Project Memory Tree

Each project has a hierarchical skeleton. Use `node_name` + `parent_node` to file memories in the right place.

```
项目概况 / 技术栈 / 项目说明 / 架构概览 / 外部依赖
需求     / 原始需求 / 需求拆解 / 需求变更 / 待确认
设计     / 架构设计 / 接口设计 / 数据模型 / 原型设计
前端     / 功能实现 / 问题记录 / 优化记录 / 开发经验
后端     / 功能实现 / 问题记录 / 优化记录 / 开发经验
数据库   / 表结构 / SQL优化 / 数据迁移 / 故障记录
测试     / 单元测试 / 集成测试 / 测试技巧 / 缺陷记录
部署     / 环境配置 / Docker部署 / 发布流程 / 故障恢复
决策记录 / 技术选型 / 架构决策 / 历史原因 / 方案对比
经验库   / 开发技巧 / 调试技巧 / 测试技巧 / 常见坑
```

| Signal | node_name | parent_node |
|--------|-----------|-------------|
| Backend API implementation | 功能实现 | 后端 |
| Frontend bug fix | 问题记录 | 前端 |
| Why we chose PostgreSQL | 技术选型 | 决策记录 |
| DB schema change | 表结构 | 数据库 |
| Architecture overview | 架构概览 | 项目概况 |
| Deployment gotcha | 常见坑 | 经验库 |

Omit `node_name` for `user` type memories (no skeleton tree).

Save workflow: call `save_memory` → check `action` field.
- `"created"` → done
- `"conflict"` → inspect `conflicts[]`, call again with `replace_id` to merge

### list_memories
```
project_id   omit = current project; "all" = every project
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
omit           → current project  ← default for most saves and reads
"all"          → every project (read-only, for broad lookup)
specific slug  → pin to exact project (cross-project reference)
```

`save_memory` always writes to the token-bound current project; a passed `project_id` is ignored.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Acting on stale memory | Verify against current files first |
| Ignoring `conflict` response | Check `action` field; use `replace_id` to merge |
| Hard-deleting by default | Use soft delete; hard only for wrong/sensitive content |
| Saving ephemeral task state | Use tasks/plans, not memory |
