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

`user` 记录**用户本人的持久特征**，用于跨项目个性化协作。自动路由到 global 范围。

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
node_name    optional — skeleton leaf node name, e.g. "功能实现"
parent_node  optional — parent node name, e.g. "后端" (disambiguates node_name)
```

> **范围由 token 决定，不可覆盖。** `save_memory` 始终写入 token 绑定的项目；不接受 `project_id` 参数。唯一例外是 `user` 类型，自动写入全局（`*`）范围以跨项目共享。

### Content 格式约定（Markdown）

`content` / `why` / `how_to_apply` 会被 UI 按 **GFM Markdown 渲染**。写入时务必遵守，否则前端显示为原始文本：

- **表格必须带分隔行。** 表头行下方紧跟 `|---|---|`（每列一个），否则整段表格不会被识别、原样显示为纯文本。这是最常见的渲染失败原因。
  ```
  | 字段 | 类型 | 说明 |
  |------|------|------|
  | port | int  | 默认 9100 |
  ```
- **简单两列数据优先用无序列表**，比表格更稳、移动端更易读：`- port (int)：默认 9100`。
- **代码 / 目录树 / 配置** 用围栏代码块并标注语言：` ```python ` / ` ```bash ` / ` ```json `（支持的语言见服务端 highlighter 配置）。
- **用真实换行**，不要写字面量 `\n`（渲染层虽会兜底替换，但仍以真实换行为准）。
- 标题用 `##` / `###`；列表项之间不要插入多余空行，避免被拆成多个段落。

## Skeleton Nodes — Organizing Memories into a Project Tree

Each project has its own skeleton tree (categories). Before saving any `project`, `feedback`, or
`reference` memory, **fetch the live tree from the server** and pick the matching `node_name`
(+ `parent_node` to disambiguate). Do NOT rely on a hardcoded tree — node names are user-editable
and drift over time; always read the current structure.

### Step 1 — Fetch the live skeleton tree

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

### Step 2 — Match content to a node

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

#### Routing guide (fallback when `prompt_hint` is empty/ambiguous)

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

### Step 2b — Create a node when none fits

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

### Step 3 — Save workflow

1. Call `save_memory` with the chosen `node_name` / `parent_node` → check `action` field
2. `"created"` → done
3. `"conflict"` → inspect `conflicts[]`, then either call again with `replace_id` or drop
4. If the save reports an unknown node, either re-fetch the skeleton (Step 1) or create the node
   (Step 2b), then retry

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
| Saving `user` type to project scope | `user` type auto-routes to global — nothing to specify |
| Trying to save into another project | Not possible — `save_memory` always writes to the token's project |
| Acting on stale memory | Always verify against current files before recommending |
| Ignoring `conflict` response | Always check `action` field; use `replace_id` to merge |
| Hard-deleting by default | Use soft delete; hard delete only for wrong/sensitive content |
| Putting ephemeral task state in memory | Memory is cross-session; use tasks/plans for current-session state |
| Markdown 表格缺少 `|---|` 分隔行 | GFM 要求表头下紧跟分隔行，否则 UI 原样显示为纯文本；简单两列改用无序列表 |

## project_id Scoping

`project_id` 仅用于 **读取类** 工具（`search_memory` / `list_memories`）。`save_memory` **不接受** 此参数——写入范围始终由 token 绑定的项目决定。

```
omit           → current project ← default for most reads
"all"          → search across every project (read-only, for broad lookup)
specific slug  → pin to exact project (use for cross-project references)
```
