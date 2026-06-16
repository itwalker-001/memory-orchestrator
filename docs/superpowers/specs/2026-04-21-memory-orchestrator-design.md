# Memory Orchestrator 设计文档

**日期**:2026-04-21
**状态**:已对齐,待实现
**作者**:walker + Claude

## 目标

构建一个**跨项目统一记忆中心**,解决 Claude Code 现有内置 memory 机制的两个核心不足:

1. 记忆只存在单项目的 `~/.claude/projects/<project>/memory/` 下,跨项目无法共享
2. MEMORY.md 作为纯索引,缺少语义检索与相关性排序,规模变大后查找效率下降

Memory Orchestrator 是一个独立的本地可部署服务,统一收集、归纳、提供记忆给所有接入的 Claude Code 会话使用。

## 非目标(v1 明确不做)

- Web 管理 UI(交给 v2)
- 多租户/团队共享(v2+)
- 从现有 MEMORY.md 历史迁移导入(v2)
- 非 Claude Code 客户端的接入(如 Cursor、Continue)

## 核心决策

| 决策点 | 选择 | 备选 | 理由 |
|---|---|---|---|
| 定位 | 跨项目统一记忆中心 | 增强内置 / 替代内置 / 离线工具 | 最能满足"记忆跨项目流动"这一核心痛点 |
| 接入方式 | MCP Server | Hooks+CLI / 纯 CLI / 混合 | 模型可主动检索,Claude Code 生态兼容最好 |
| 存储 | PostgreSQL + pgvector | SQLite+FTS5 / 纯文件 / sqlite-vec | 混合查询强,可伸缩,生态成熟 |
| Embedding | 本地 bge-small-zh-v1.5 | OpenAI / Voyage / 可插拔 | fastembed 0.8 原生支持,无需 custom_model 注册;中文场景足够用。原计划 bge-m3 因 fastembed 未内置暂缓 |
| 写入策略 | 模型主动 + Stop hook 自动扫描 | 纯主动 / 纯自动 / 纯手动 | 模型主动保留语义准确性,自动扫描补漏 |
| 注入策略 | 两层混合(预注入 + 按需检索) | 纯检索 / 纯预注入 / 每轮检索 | 覆盖率和 token 成本的平衡 |
| MVP 范围 | 完整核心闭环 | 骨架 / 全功能 | 一版就能用,不做 throw-away demo |

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                            │
│   ┌──────────────────┐      ┌────────────────────────┐      │
│   │ UserPromptSubmit │      │   MCP Client (stdio/   │      │
│   │   hook (注入层)  │      │   SSE) (检索/写入层)   │      │
│   └────────┬─────────┘      └──────────┬─────────────┘      │
└────────────┼────────────────────────────┼────────────────────┘
             │ HTTP /context              │ MCP JSON-RPC
             ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Memory Orchestrator Service (Python FastAPI + MCP SDK)     │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ MCP Tools API │  │ Context API  │  │ Ingestor (Stop   │  │
│  │ save/search/  │  │ (预注入 top-K│  │ hook 调用,LLM    │  │
│  │ list/delete/  │  │ 核心记忆)    │  │ 扫 transcript 提 │  │
│  │ promote...    │  │              │  │ 取归纳)          │  │
│  └───────┬───────┘  └──────┬───────┘  └─────────┬────────┘  │
│          │                 │                    │           │
│          ▼                 ▼                    ▼           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            Memory Repository (SQLAlchemy)             │  │
│  └──────────┬──────────────────────────────┬─────────────┘  │
│             │                              │                │
│             ▼                              ▼                │
│   ┌───────────────────┐          ┌───────────────────┐      │
│   │ PostgreSQL 16     │          │  bge-small-zh-v1.5│      │
│   │ + pgvector        │          │  embedding(本地)  │      │
│   └───────────────────┘          └───────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 边界划分

1. **Claude Code 侧**:一个 UserPromptSubmit hook(预注入)+ 一个 MCP server 连接(工具调用)+ 一个 Stop hook(会话归纳触发)
2. **Orchestrator 服务**:单 Python 进程,同时暴露 MCP stdio/SSE 和 HTTP
3. **数据层**:PostgreSQL 负责元数据 + 向量,bge-small-zh-v1.5 跑在 orchestrator 进程内

### 技术栈

- Python 3.11+
- FastAPI(HTTP API)
- `mcp` Python SDK(MCP server)
- SQLAlchemy 2 + asyncpg
- PostgreSQL 16 + pgvector 扩展
- FastEmbed(bge-small-zh-v1.5 本地推理)
- Alembic(DB 迁移)
- Docker Compose(开发 & 单机部署)

---

## 数据模型

### `memories`(主表)

```sql
CREATE TABLE memories (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      TEXT NOT NULL,              -- 项目作用域,'*' 表示全局
  type            TEXT NOT NULL,              -- user | feedback | project | reference
  name            TEXT NOT NULL,              -- 短标题
  description     TEXT NOT NULL,              -- 一行 hook,相关性判断用
  content         TEXT NOT NULL,              -- 正文 markdown
  why             TEXT,                       -- feedback/project 类型必填(由应用层校验)
  how_to_apply    TEXT,                       -- feedback/project 类型必填
  embedding       vector(512),                -- bge-small-zh-v1.5 输出维度
  importance      SMALLINT NOT NULL DEFAULT 3,-- 1-5,预注入排序用
  hit_count       INT NOT NULL DEFAULT 0,
  last_hit_at     TIMESTAMPTZ,
  source          TEXT NOT NULL,              -- explicit | auto_extracted | imported
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_by   UUID REFERENCES memories(id)
);

CREATE INDEX memories_project_type_idx ON memories (project_id, type) WHERE superseded_by IS NULL;
CREATE INDEX memories_embedding_idx ON memories USING hnsw (embedding vector_cosine_ops);
```

### `projects`(项目注册表)

```sql
CREATE TABLE projects (
  id              TEXT PRIMARY KEY,           -- 归一化后的 git remote / 路径 hash
  display_name    TEXT NOT NULL,
  root_paths      TEXT[] NOT NULL DEFAULT '{}',
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `memory_links`

```sql
CREATE TABLE memory_links (
  from_id   UUID REFERENCES memories(id) ON DELETE CASCADE,
  to_id     UUID REFERENCES memories(id) ON DELETE CASCADE,
  relation  TEXT NOT NULL,  -- supersedes | duplicates | related
  PRIMARY KEY (from_id, to_id, relation)
);
```

### `sessions`(会话归纳幂等表)

```sql
CREATE TABLE sessions (
  session_id       TEXT PRIMARY KEY,
  project_id       TEXT NOT NULL,
  last_ingested_at TIMESTAMPTZ,
  last_offset      INT NOT NULL DEFAULT 0,    -- transcript 行偏移,保证增量
  status           TEXT NOT NULL DEFAULT 'pending',  -- pending | done | failed
  last_error       TEXT
);
```

### project_id 归一化规则

1. 有 `git remote.origin.url`:去协议前缀、去 `.git` 后缀、转小写。如 `https://github.com/foo/bar.git` 和 `git@github.com:Foo/Bar.git` 都归一化为 `github.com/foo/bar`
2. 无 remote:取项目根绝对路径的 SHA256 前 12 位,前缀 `local:`,如 `local:a1b2c3d4e5f6`
3. 全局记忆:`project_id = "*"`,由 `user` 类型默认,`feedback` 类型可选指定

### 默认作用域规则

| 记忆类型 | 默认 project_id |
|---|---|
| user | `*`(全局) |
| feedback | `*`(全局,可指定项目) |
| project | 当前项目(必填) |
| reference | 当前项目(可提升到全局) |

---

## MCP 工具接口

Orchestrator 通过 MCP stdio 暴露以下工具:

### `search_memory` — 混合检索

```json
{
  "name": "search_memory",
  "inputs": {
    "query": "string (required)",
    "project_id": "string (optional, default: current + '*')",
    "type": "string[] (optional)",
    "top_k": "int (optional, default: 8)"
  },
  "outputs": [
    {"id", "name", "description", "content", "type", "project_id", "score", "why?", "how_to_apply?"}
  ]
}
```

- 默认作用域:**当前项目 + 全局(`*`)**。跨项目检索显式传 `"all"`
- 混合打分公式:`score = 0.6 * cosine_sim + 0.3 * normalized_importance + 0.1 * recency_decay`
  - `recency_decay = exp(-age_days / 60)`
- 命中副作用:`hit_count += 1`,`last_hit_at = now()`

### `save_memory` — 写入/更新

```json
{
  "name": "save_memory",
  "inputs": {
    "type": "user | feedback | project | reference",
    "name": "string",
    "description": "string",
    "content": "string",
    "project_id": "string (optional)",
    "why": "string (feedback/project 必填)",
    "how_to_apply": "string (feedback/project 必填)",
    "importance": "int 1-5 (optional, default: 3)",
    "replace_id": "uuid (optional, 显式覆盖目标)"
  },
  "outputs": {
    "id": "uuid",
    "action": "created | updated | merged",
    "conflicts": "[{id, name, similarity}] (存在时)"
  }
}
```

- 去重:先对 `content` 做 embedding,检索 `cos_sim ≥ 0.92` 的同类同项目记忆,视为重复
- 冲突策略:
  - 有 `replace_id`:旧记录置 `superseded_by`,新记录插入并回填 link
  - 无 `replace_id` 且检测到重复:返回 `conflicts` 让模型决定调 `save_memory(replace_id=...)` 或放弃

### `list_memories` — 枚举

```json
{
  "inputs": { "project_id?", "type?", "limit": 50 },
  "outputs": [{"id", "name", "description", "type", "importance", "updated_at"}]
}
```

### `delete_memory` — 软删/硬删

```json
{
  "inputs": { "id": "uuid", "hard": "bool (default: false)" }
}
```

软删置 `superseded_by = id`(自引),retrieval 自动过滤。

### `promote_memory` — 提升重要度

```json
{
  "inputs": { "id": "uuid", "importance?": 1-5 }
}
```

### `ingest_session` — Stop hook 调用入口

```json
{
  "inputs": { "session_id", "project_id", "transcript_path" },
  "outputs": { "extracted", "saved", "skipped" }
}
```

服务端异步执行,立即返回 202。真正的提取在后台任务里调 Claude Haiku(沿用 `~/.claude/settings.json` 的 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN`)。

---

## 集成层

### UserPromptSubmit Hook(预注入)

**触发**:每次用户 prompt 发送前。

**流程**:
1. 读取环境变量 `$CLAUDE_PROJECT_DIR`,cd 进去
2. 调用 `git config --get remote.origin.url`,按规则归一化 project_id
3. `GET http://localhost:8765/context?project_id=X&budget_tokens=1500`
4. Orchestrator 返回 markdown 片段:
   - 全局 `user` 记忆(全部,通常 3-8 条)
   - 当前 project 的 `feedback` 记忆(`importance ≥ 3`)
   - 当前 project 的 `project` 记忆(`last_hit_at` 或 `updated_at` 在 14 天内)
5. hook 把片段 echo 到 stdout,Claude Code 自动拼到 system prompt 尾部

**Token 预算**:默认 1500 tokens。超出时按 importance 降序截断,再按 updated_at 降序。

**降级**:Orchestrator 不可达时 hook 超时 2s 静默退出,不阻塞用户。日志写 `~/.claude/memory-orchestrator/hook.log`。

### Stop Hook(会话归纳)

**触发**:Claude Code 一轮响应结束。

**流程**:
1. 检查冷却:距上次该 session_id ingest 超过 10 分钟?
2. 检查信号:当前 session 自上次 ingest 后有 ≥ 3 轮对话?
3. 两条都满足则 `POST /ingest {session_id, project_id, transcript_path}`,立即退出
4. Orchestrator 后台任务:
   - 读 transcript 增量(靠 `sessions.last_offset`)
   - 调用 Claude Haiku(复用用户 `~/.claude/settings.json` 的 API 凭据),prompt 里塞 auto-memory 四分类规则
   - 每条候选走 `save_memory` 的同一套去重逻辑
   - 更新 `sessions.last_ingested_at`、`sessions.last_offset`

**为什么不每次 Stop 都跑**:避免短对话反复触发 LLM 调用浪费 token。

**幂等保障**:`sessions.last_offset` 记录 transcript 已处理的行号,同一段对话不会被重复提取。

### 安装 / 卸载

```bash
mo install-hooks [--user | --project]   # 写 ~/.claude/settings.json 的 hooks 段 + mcpServers
mo uninstall-hooks                       # 逆操作,保留已有记忆
mo doctor                                # 检查 DB / embedder / hook 配置完整性
```

---

## 错误处理

| 场景 | 策略 |
|---|---|
| Postgres 连不上 | MCP 工具返回明确错误(让模型感知退化);hook 2s 超时静默退出 |
| Embedding 模型加载失败 | 启动时 fail-fast,不允许半残状态 |
| Ingestor LLM 调用失败 | `sessions.status = failed`,记 `last_error`,下次 Stop 重试 |
| save_memory 向量化 | 同步做(单条 ≤ 200ms),不引入队列 |
| 重复/冲突 | 永不静默覆盖,返回 conflicts 让模型/用户决定 |
| hook 脚本崩 | 日志写 `~/.claude/memory-orchestrator/hook.log`,永不阻塞 Claude Code |

**边界验证原则**:只在 MCP 入参、HTTP 请求入口做 schema 校验。内部模块之间信任契约,不做防御式校验。

---

## 可观测

- **结构化日志**(JSON Lines):`service`, `event`, `project_id`, `memory_id`, `latency_ms`,输出到 stdout
- **健康检查**:`GET /healthz` → `{db, embedder, last_ingest_ok_at}`
- **统计视图**:`GET /stats?project_id=X` → `{total, by_type, hit_rate_7d, last_save_at}`

**v1 明确不做**:Prometheus 导出、OpenTelemetry trace、Grafana dashboard、Web UI。

---

## 测试策略

### 单元(pytest,无外部依赖)

- `memory_repository` 的去重、冲突判定、软删
- project_id 归一化(各种 git remote 分支、无 remote 分支)
- context 拼装的 token 预算截断

### 集成(pytest + testcontainers-pg)

- `save_memory → search_memory` 能查回同义改写的 query
- 向量相似度去重阈值在 0.92 附近的边界行为
- Stop hook 增量 ingest 幂等(跑两次结果一致)

### 端到端(手动 + smoke 脚本)

- 起 Docker Compose,装 hook,在真实 Claude Code 里跑:
  - "告诉它记住 X" → 新 session → 问它 X → 应能召回
  - 写入冲突场景 → 模型应收到 conflicts 并正确处理

### 不覆盖

MCP SDK 通信、FastAPI 框架本身、PostgreSQL/pgvector 正确性。这些不是本项目的代码。

---

## 项目结构

```
memory-orchestrator/
├── pyproject.toml
├── docker-compose.yml           # postgres + orchestrator 一键起
├── alembic/                     # DB 迁移
├── src/memory_orchestrator/
│   ├── __init__.py
│   ├── config.py                # 环境变量、默认值
│   ├── models.py                # SQLAlchemy ORM
│   ├── repository.py            # 数据层,所有 SQL 在这
│   ├── embedder.py              # bge-small-zh-v1.5 封装
│   ├── scoring.py               # 混合打分
│   ├── project_id.py            # 归一化规则
│   ├── ingestor.py              # transcript → LLM → candidates
│   ├── mcp_server.py            # MCP tools 注册
│   ├── http_app.py              # FastAPI(/context, /ingest, /healthz, /stats)
│   └── cli.py                   # mo install-hooks / mo doctor
├── hooks/
│   ├── user_prompt_submit.py
│   └── stop.py
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

**预计代码量**:1500-2500 行 Python
**预计工期**:单人 5-8 天

---

## 开放问题(不影响 v1 启动,实现时再决)

1. bge-small-zh-v1.5 512 维索引在 HNSW 下的 m / ef_construction 参数调优 — 先用 pgvector 默认值,有性能问题再调
2. Haiku ingestion prompt 的具体措辞 — 在 `ingestor.py` 实现时迭代
3. `recency_decay` 的衰减半衰期(60 天是初值) — 跑一段时间看 hit_rate 再调
