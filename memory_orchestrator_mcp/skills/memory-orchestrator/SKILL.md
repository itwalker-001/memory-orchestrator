---
name: memory-orchestrator
description: Use when saving, searching, or managing persistent memories across Claude Code sessions via the mcp__memory-orchestrator__ tools. Use when recalling prior context, storing user preferences, project decisions, feedback, or reference pointers.
---

# Memory Orchestrator MCP

## Overview

Persistent cross-session memory for Claude Code. Memories are scoped to a project (detected from `.git/config`) or global (available in all projects). Six tools handle the full lifecycle.

## Memory Types

| Type | When to Save | Scope |
|------|-------------|-------|
| `user` | Role, expertise, communication preferences | Always global |
| `feedback` | AI corrected by user / bug fixed / confirmed good approach | Project or global |
| `project` | 技术框架、选型、需求、整体设计、架构决策 | Current project |
| `reference` | Pointers to external resources, dashboards, issue trackers | Current project |

### user — 判断标准

`user` 记录**用户本人的持久特征**，用于跨项目个性化协作。自动路由到 global，无需指定 project_id。

触发条件（满足任一即保存为 user）：
- 用户的角色/职位（前端工程师、数据科学家、独立开发者）
- 技术深度：某语言/框架的熟练程度（精通 Go、初次接触 React）
- 沟通偏好：详细说明 vs 简洁回复、中文 vs 英文
- 工作习惯：偏好 TDD、不喜欢 mock、prefer small PRs
- 知识边界：有哪些领域需要更多解释 vs 可以直接跳过基础

**不**属于 user：
- 项目决策、技术选型（归入 project）
- AI 被纠正的行为（归入 feedback）
- 临时工作状态或当前任务进展

**user 写法：**
```
[用户特征描述]
How to apply: 影响所有未来对话的回复方式
```

---

### feedback — 判断标准

`feedback` 专门记录**对 AI 行为的纠正**和**已验证的做法**，不记录项目事实。

触发条件（满足任一即保存为 feedback）：
- 用户纠正了 AI 的错误做法（"不要这样做"、"改成这样"）
- 一个 bug 被修复，根因是 AI 的固定错误认知（需要下次避免）
- 用户明确确认某种做法正确（"对，就这样"、接受了非显然的选择）

**不**属于 feedback（应归入 project）：
- 项目状态、进展、技术选型
- 截止日期、外部约束
- 架构事实（用了什么库、数据库在哪个端口）

**feedback 写法模板：**
```
[规则本身]
Why: 用户纠正的具体原因 / bug 发生的根因
How to apply: 下次遇到什么情况时启用此规则
```

### project — 判断标准

`project` 记录**项目本身的技术事实**，这些信息不在代码里、但影响所有后续决策。

触发条件（满足任一即保存为 project）：
- **技术框架**：使用了哪些语言、框架、库及版本
- **技术选型**：为什么选 A 而不是 B（决策原因）
- **需求/功能边界**：这个项目要做什么、不做什么
- **整体设计**：模块划分、数据模型、API 风格、部署架构
- **环境配置事实**：数据库地址、端口、外部服务 URL

**不**属于 project（应归入 feedback）：
- AI 被纠正的行为规范
- 用户工作偏好（归入 user）

**project 写法模板：**
```
[事实/决策本身]
Why: 选型原因 / 需求背景 / 约束条件
How to apply: 涉及该模块时应参考此记忆
```

### reference — 判断标准

`reference` 记录**外部资源的位置指针**，让 AI 知道去哪里查找最新信息，而非把信息本身存进来。

触发条件（满足任一即保存为 reference）：
- Bug/需求跟踪系统：Linear 项目、GitHub Issues、Jira Board 的名称/链接
- 监控/运维入口：Grafana 面板、Datadog dashboard、日志平台 URL
- 文档/规范入口：内网 Wiki、Confluence 页面、API 文档地址
- 沟通渠道：相关 Slack 频道、飞书群、邮件列表
- 数据/报表入口：BI 系统、数据仓库、测试数据库连接信息

**不**属于 reference：
- 把外部文档的内容复制进来（内容会过时，只记位置）
- 代码库内部文件路径（直接读文件即可，不需要 reference）
- 环境变量或配置值（归入 project）

**reference 写法：**
```
[资源名称] 位于 [位置/URL/路径]
用途: 该资源的作用
How to apply: 何时去查这个资源
```

## Proactive Save — When to Call save_memory Without Being Asked

**Rule: if any trigger below fires during a conversation, call `save_memory` immediately — do not wait for the user to say "remember this".**

### Triggers

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

---

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

### search_memory
```
query        (required) semantic search string
top_k        default 8
type         array of types to filter, e.g. ["feedback","project"]
project_id   omit = current + global; "all" = every project; slug = specific
```

### save_memory
```
type         (required) user | feedback | project | reference
name         (required) short identifier
description  (required) one-line hook used for future retrieval
content      (required) full memory body
why          optional — reason behind rule/decision (feedback/project)
how_to_apply optional — when this memory kicks in
importance   integer 1–5 only, default 3 (out-of-range rejected)
replace_id   UUID of memory to supersede (soft-deletes old, saves new)
project_id   omit = current project; slug = specific project
node_name    optional — skeleton leaf node name, e.g. "功能实现"
parent_node  optional — parent node name, e.g. "后端" (disambiguates node_name)
```

## Skeleton Nodes — Organizing Memories into a Project Tree

Each project has a flat skeleton tree. Specify `node_name` to file the memory in the right category.

### Default Skeleton Tree

```
项目概况    需求        设计        技术栈
前端        后端        数据库      测试
部署        决策记录    经验库
```

### When to specify `node_name`

Always set `node_name` when saving `project`, `feedback`, or `reference` memories that clearly
belong to a category. `parent_node` is only needed if you add custom child nodes.
Omit for `user` type (no tree).

| Signal | node_name |
|--------|-----------|
| Tech stack choice | 技术栈 |
| Implementing a backend API | 后端 |
| Frontend bug fix | 前端 |
| DB schema or query | 数据库 |
| Architecture or interface design | 设计 |
| A deployment gotcha | 部署 |
| Why we made a decision | 决策记录 |
| Reusable tip or pitfall | 经验库 |

**Save workflow:**
1. Call `save_memory` → check `action` field in response
2. `"created"` → done
3. `"conflict"` → inspect `conflicts[]`, then either call again with `replace_id` or drop

### list_memories
```
project_id   omit = current + global; "all" = every project
type         single type string to filter
limit        default 50
```
Returns summaries only (no `content`). Use `search_memory` for full content retrieval.

### delete_memory
```
id           (required) UUID
hard         false = soft-delete (superseded); true = permanent
```
Prefer soft delete unless memory is wrong or sensitive.

### promote_memory
```
id           (required) UUID
importance   1–5
```
Use to boost the importance of a memory.

### ingest_session
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

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Saving `user` type to project scope | `user` type auto-routes to global; omit `project_id` |
| Acting on stale memory | Always verify against current files before recommending |
| Ignoring `conflict` response | Always check `action` field; use `replace_id` to merge |
| Hard-deleting by default | Use soft delete; hard delete only for wrong/sensitive content |
| Putting ephemeral task state in memory | Memory is cross-session; use tasks/plans for current-session state |

## project_id Scoping

```
omit           → current project ← default for most saves
"all"          → search across every project (read-only, for broad lookup)
specific slug  → pin to exact project (use for cross-project references)
```
