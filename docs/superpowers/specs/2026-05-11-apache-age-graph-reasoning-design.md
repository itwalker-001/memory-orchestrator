# Apache AGE 图谱推理集成设计

**日期**：2026-05-11  
**范围**：`memory_orchestrator_server/` 仅此包，不涉及 `memory_orchestrator_mcp/`  
**状态**：待实现

---

## 1. 目标

在现有 PostgreSQL + pgvector 基础上引入 Apache AGE 图扩展，实现：

1. **写时关系提取**：`save_memory` 后 LLM 自动分析新记忆与已有记忆的关联，写入 AGE 图边
2. **读时图增强**：`search_memory` 和 `build_context` 自动沿图边扩展召回，对调用方透明
3. **图数据 API**：`GET /api/graph` 暴露节点/边数据，供未来前端可视化消费

MCP 工具接口（`search_memory`、`save_memory` 等）**签名不变**，图推理完全透明。

---

## 2. 基础设施

### 2.1 Docker 镜像

新增 `memory_orchestrator_server/Dockerfile.db`，在 `pgvector/pgvector:pg16` 基础上编译安装 Apache AGE：

```dockerfile
FROM pgvector/pgvector:pg16

RUN apt-get update && apt-get install -y \
    build-essential git \
    postgresql-server-dev-16 \
    libreadline-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && git checkout PG16 \
    && make && make install \
    && rm -rf /tmp/age

RUN apt-get purge -y --auto-remove build-essential git \
    postgresql-server-dev-16 libreadline-dev zlib1g-dev
```

### 2.2 docker-compose.yml 修改

`db` 服务改为本地构建：

```yaml
db:
  build:
    context: .
    dockerfile: Dockerfile.db
  environment:
    POSTGRES_DB: memory_orchestrator
    POSTGRES_USER: mo
    POSTGRES_PASSWORD: mo
    # 确保 ag_catalog 在 search_path
    POSTGRES_INITDB_ARGS: ""
  command: >
    postgres
    -c shared_preload_libraries=age,vector
    -c search_path=ag_catalog,"$user",public
```

---

## 3. 图数据模型

### 3.1 AGE 图

- **图名**：`memory_graph`（单图，跨所有 project）
- 在 Alembic migration `0010_age_extension.py` 中初始化

### 3.2 顶点（Vertex）

标签：`Memory`

```
Memory {
  mem_id:     string   -- memories.id (UUID as string)
  name:       string
  type:       string   -- user / feedback / project / reference
  project_id: string
}
```

每次 `save_memory` / `patch_memory` 后同步 upsert 顶点。`delete_memory` 时删除顶点及其所有边。

### 3.3 边（Edge）标签

| relation | 含义 |
|----------|------|
| `supports` | A 为 B 提供支撑证据 |
| `contradicts` | A 与 B 存在矛盾 |
| `refines` | A 是对 B 的细化或更新 |
| `references` | A 引用了 B 的内容 |
| `caused_by` | A 由 B 引起（适用 feedback/project 类型）|

边属性：`{ weight: float, extracted_at: string (ISO 8601) }`

### 3.4 与现有表的关系

- `memory_links` 表结构保留，**不再写入**，由 AGE 完全承担图职责
- AGE 顶点 `mem_id` 与 `memories.id` 对应，无跨表 FK 约束（AGE 不支持）

---

## 4. 写时管道：关系提取

### 4.1 触发点

`repository.save()` 成功提交后，通过 `asyncio.create_task()` 异步触发，不阻塞调用方。

### 4.2 流程

```
save_memory(M) 提交成功
  → graph.sync_vertex(M)           # upsert AGE 顶点
  → candidates = search(M, top_k=20)  # 向量召回候选
  → edges = graph.extract_relations(M, candidates)  # LLM 提取
  → graph.write_edges(edges)       # 写入 AGE
```

### 4.3 LLM 提取 Prompt

使用现有 `extraction_base_url` / `extraction_model` 配置，无需新增模型。

```
System: You are a knowledge graph builder. Analyze relationships between memories.
User:
New memory:
  name: {M.name}
  type: {M.type}
  content: {M.content}

Candidates:
{candidates as JSON array with id, name, type, content}

For each meaningful relationship, output a JSON array:
[{"from": "<new_mem_id>", "to": "<candidate_id>",
  "relation": "supports|contradicts|refines|references|caused_by",
  "weight": 0.0-1.0}]

Only include high-confidence relationships (weight >= 0.6).
If no clear relationship exists, return [].
```

### 4.4 错误处理

- LLM 提取失败 → 记录 WARNING 日志，顶点已写入，边跳过，主流程不受影响
- AGE 不可用（扩展未安装）→ `graph_enabled` 自动降级为 false，所有图操作静默跳过

---

## 5. 读时增强

### 5.1 search_memory 图扩展

在向量召回 top_k 命中后执行：

```python
# 对每个命中，查询 graph_hop_depth 跳邻居
MATCH (m:Memory {mem_id: $id})-[r*1..{depth}]-(n:Memory)
RETURN n.mem_id, type(r[-1]) as relation, r[-1].weight as weight

# 合并邻居到结果集（去重，标记 source="graph"）
# 统一参与 hybrid_score 排序后截断到 top_k
```

图扩展召回的记忆在返回结果中增加字段：`graph_relation: str | None`。

### 5.2 build_context 图增强

同样在向量召回后做邻居扩展。`contradicts` 类型边的邻居在 context markdown 中额外标注前缀 `⚠️ [contradicts]`，提醒 Claude/Codex 注意矛盾信息。

---

## 6. 新增配置项

`system_settings` 增加两个键（含默认值）：

| key | 默认值 | 含义 |
|-----|--------|------|
| `graph_enabled` | `true` | 全局开关，false 时所有图操作跳过 |
| `graph_hop_depth` | `1` | 图扩展跳数，取值 1 或 2 |

在 UI Settings 面板新增 **Graph** 配置组展示这两个配置。

---

## 7. 图数据 API

### `GET /api/graph`

返回可视化所需的节点和边数据，供未来前端图谱页面消费。

**Query 参数**：
- `project_slug` (可选) — 只返回指定项目的节点
- `mem_id` (可选) — 以该节点为中心，返回 depth=2 的子图
- `limit` (默认 200) — 最多返回多少条边

**Response**：
```json
{
  "nodes": [
    {"id": "uuid", "name": "...", "type": "feedback", "project_id": "uuid"}
  ],
  "edges": [
    {"from": "uuid", "to": "uuid", "relation": "supports", "weight": 0.85}
  ]
}
```

此端点需 `ui_admin` 认证，在 `router`（protected）下注册。

---

## 8. 新增模块：graph.py

`memory_orchestrator_server/src/memory_orchestrator_server/graph.py`

公开函数：

```python
async def sync_vertex(session, mem: Memory) -> None
async def delete_vertex(session, mem_id: str) -> None
async def extract_relations(new_mem: Memory, candidates: list[Memory]) -> list[dict]
async def write_edges(session, edges: list[dict]) -> None
async def get_neighbors(session, mem_id: str, depth: int = 1) -> list[dict]
async def get_subgraph(session, project_id: str | None, mem_id: str | None, limit: int) -> dict
```

内部使用 `sqlalchemy text()` 执行 `SELECT * FROM cypher('memory_graph', $$...$$) AS (...)` 形式的查询。

---

## 9. Alembic Migration

`alembic/versions/0010_age_extension.py`：

```python
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS age")
    op.execute("LOAD 'age'")
    op.execute("SET search_path = ag_catalog, \"$user\", public")
    op.execute("SELECT create_graph('memory_graph')")

def downgrade():
    op.execute("SELECT drop_graph('memory_graph', true)")
    op.execute("DROP EXTENSION IF EXISTS age")
```

---

## 10. 文件变动清单

### 新增（仅 memory_orchestrator_server/）

| 文件 | 说明 |
|------|------|
| `Dockerfile.db` | pgvector:pg16 + AGE 编译镜像 |
| `src/.../graph.py` | 图操作模块 |
| `alembic/versions/0010_age_extension.py` | AGE 扩展迁移 |
| `docs/superpowers/specs/2026-05-11-apache-age-graph-reasoning-design.md` | 本文档 |

### 修改

| 文件 | 改动要点 |
|------|----------|
| `docker-compose.yml` | db 服务改用 Dockerfile.db |
| `repository.py` | save/delete 触发图同步；search/build_context 图扩展 |
| `settings_defaults.json` | 新增 graph_enabled, graph_hop_depth |
| `routers/ui.py` | GET /api/graph 端点；Settings 新增 graph 配置组 |
| `frontend/src/App.vue` | Settings UI Graph 配置组 |

### 不动

- `memory_orchestrator_mcp/`（全部）
- `mcp_core.py`、`mcp_contract.py`（MCP 工具签名不变）
- `memory_links` 表（结构保留，停止写入）

---

## 11. 后续（本次不实现）

- `/ui/graph` 可视化页面（Cytoscape.js，深色 sci-fi 风格）
- 图谱重建 CLI 命令（`mo-server rebuild-graph`，对已有记忆批量补建关系）
- 图算法（PageRank 重要性加权、社区发现）
