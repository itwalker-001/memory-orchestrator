# Memory Ingest Pipeline

> 记录 Memory Orchestrator 嵌入（保存）记忆的完整逻辑（截至 2026-05-08）

---

## 全流程概览

```
对话结束（Stop 事件）
    ↓
Stop hook
    ↓
POST /ingest  { session_id, transcript_path, project_slug }
    ↓
ingestor.py
    ├─ 1. 读取对话 transcript（JSONL）
    ├─ 2. 截取未处理的新增内容（last_offset 游标）
    ├─ 3. 调用 LLM 提取记忆
    ├─ 4. 对每条记忆：向量化
    ├─ 5. 去重检查（余弦距离）
    └─ 6. 保存 / soft-replace
    ↓
memories 表 + pgvector 索引
```

---

## 分步详解

### Step 1 — 触发入口

```
Stop hook  →  POST http://127.0.0.1:8765/ingest
```

请求体：
```json
{
  "session_id": "<uuid>",
  "transcript_path": "/path/to/conversation.jsonl",
  "project_slug": "github.com/user/repo"
}
```

端点定义：`routers/hooks.py → POST /ingest`

---

### Step 2 — 读取 transcript & 游标推进

```python
# ingestor.py
session = await get_or_create_session(session_id)
raw = Path(transcript_path).read_text(encoding="utf-8")
lines = raw.splitlines()
new_lines = lines[session.last_offset:]   # 仅处理新增部分
```

- `sessions` 表记录 `last_offset`（已处理行数）和 `status`（pending/done/failed）
- 重复 ingest 同一 session 时，从上次断点续处理

---

### Step 3 — LLM 提取记忆

```python
# ingestor.py
prompt = EXTRACTION_PROMPT.format(transcript="\n".join(new_lines))
response = await llm_client.chat(
    model=settings["extraction_model"],   # 默认同 base_url 下的模型
    messages=[{"role": "user", "content": prompt}],
)
memories_json = parse_json_from_response(response)
```

LLM 输出格式（每条）：
```json
{
  "type": "feedback",          // user | feedback | project | reference
  "name": "记忆标题",
  "description": "一句话描述",
  "content": "详细内容",
  "importance": 3,             // 1–5
  "why": "原因（可选）",
  "how_to_apply": "应用方式（可选）"
}
```

可配置项（system_settings）：
- `extraction_base_url`：LLM API 地址
- `extraction_model`：提取用的模型名

---

### Step 4 — 向量化（BGE-M3）

```python
# embedder.py
async def embed_one(text: str) -> list[float]:
    return (await embed_batch([text]))[0]
```

文本拼接策略：
```python
embed_text = f"{memory['name']} {memory['description']} {memory['content']}"
embedding = await embed_one(embed_text)
```

- 输出：1024-dim float 列表
- 在 ingestor 中并发批量处理（`asyncio.gather`）

---

### Step 5 — 去重检查

```python
# repository.find_duplicates()
duplicates = await repo.find_duplicates(
    type=memory.type,
    project_id=project_id,
    embedding=embedding,
    threshold=dup_threshold,   # 默认 0.92，可在 Settings 修改
    limit=5,
)
```

- 仅在同类型（type）、同项目范围内查重
- 相似度 ≥ 0.92 则视为重复
- 返回最多 5 条候选，按余弦距离升序排列

---

### Step 6 — 保存 / Soft-replace

**无重复** → 直接插入新记忆：
```python
await repo.save(
    type=..., name=..., description=..., content=...,
    project_id=project_id, source=transcript_path,
    importance=..., embedding=embedding,
    why=..., how_to_apply=...,
)
```

**有重复（replace_id 触发）**：
```python
# 1. soft-delete 旧记忆（superseded_by = self.id）
await repo.delete(old_memory_id, hard=False)
# 2. 插入新记忆
await repo.save(...)
```

所有查询过滤 `superseded_by IS NULL`，soft-delete 的旧记忆对检索不可见。

---

### Step 7 — 更新游标 & 状态

```python
session.last_offset = len(lines)
session.status = "done"
await db.commit()
```

---

## 数据模型

### memories 表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `type` | text | user / feedback / project / reference |
| `name` | text | 记忆标题 |
| `description` | text | 一句话描述（用于列表显示） |
| `content` | text | 详细内容 |
| `importance` | int | 1–5，默认 3 |
| `embedding` | vector(1024) | BGE-M3 嵌入向量 |
| `project_id` | UUID | 所属项目（FK → projects） |
| `source` | text | transcript 路径 |
| `source_client` | text | claude / codex |
| `superseded_by` | UUID | 软删除标记，非 NULL 则不可见 |
| `hit_count` | int | 被检索命中次数 |
| `last_hit_at` | timestamptz | 最后命中时间 |
| `why` | text | 记录原因（可选） |
| `how_to_apply` | text | 应用方式（可选） |

### sessions 表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | text | Claude/Codex 会话 ID |
| `transcript_path` | text | JSONL 文件路径 |
| `last_offset` | int | 已处理行数（游标） |
| `status` | text | pending / done / failed |
| `project_id` | UUID | 所属项目 |

---

## 关键参数（system_settings）

| key | 默认值 | 说明 |
|-----|--------|------|
| `extraction_base_url` | （本地 LLM URL） | LLM 提取 API 地址 |
| `extraction_model` | （配置值） | 提取用模型名 |
| `dup_threshold` | 0.92 | 去重余弦相似度阈值 |
| `hook_cooldown_sec` | 30 | Stop hook 最短触发间隔 |
| `hook_min_turns` | 3 | 至少 N 轮才触发 ingest |

---

## 代码位置速查

| 逻辑 | 文件 |
|------|------|
| Stop hook 入口 | `memory_orchestrator_mcp/src/.../hooks/stop.py` |
| /ingest 端点 | `memory_orchestrator_server/src/.../routers/hooks.py` |
| 提取 + 保存主逻辑 | `memory_orchestrator_server/src/.../ingestor.py` |
| 去重查询 | `repository.py → MemoryRepository.find_duplicates()` |
| 保存记忆 | `repository.py → MemoryRepository.save()` |
| 软删除 | `repository.py → MemoryRepository.delete(hard=False)` |
| 向量化 | `embedder.py → embed_one()` |
