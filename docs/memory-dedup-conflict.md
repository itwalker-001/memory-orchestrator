# Memory Deduplication & Conflict Detection

> 记录 Memory Orchestrator 重复检测与冲突扫描的完整逻辑（截至 2026-05-08）

---

## 概念区分

| 概念 | 余弦相似度区间 | 含义 |
|------|--------------|------|
| **重复（Duplicate）** | `≥ dup_threshold`（默认 0.92） | 语义几乎相同，应合并或删除 |
| **潜在冲突（Conflict）** | `[min_sim, dup_threshold − 0.01)`（默认 0.50–0.91） | 话题相近，内容可能相反，需人工确认 |
| **无关（Unrelated）** | `< min_sim`（默认 < 0.50） | 话题差异过大，不做处理 |

两个区间**互不重叠**：冲突扫描的上界 = `dup_threshold − 0.01`，确保同一对记忆不会同时出现在两个列表中。

---

## 重复检测（Duplicates）

### 触发时机

- **写入时自动检测**：`repository.find_duplicates()` 在每次 `save_memory` 之前调用，若发现相似度 ≥ `dup_threshold` 的同类型记忆，则跳过写入并返回已有记忆 ID（MCP 工具侧处理）。
- **UI 手动扫描**：工具栏 → "Duplicates" → 弹窗扫描全库。

### SQL 逻辑（`GET /api/duplicates`）

```sql
SELECT m1.*, m2.*,
       1 - (m1.embedding <=> m2.embedding) AS similarity
FROM memories m1
JOIN memories m2 ON m1.id < m2.id
WHERE m1.superseded_by IS NULL
  AND m2.superseded_by IS NULL
  AND m1.embedding IS NOT NULL
  AND m2.embedding IS NOT NULL
  AND 1 - (m1.embedding <=> m2.embedding) >= :threshold  -- 默认 0.92
ORDER BY similarity DESC
LIMIT :limit
```

- `m1.id < m2.id AND m1.project_id = m2.project_id` — 避免重复对 (A,B)/(B,A)，且**只匹配同项目内的记忆**
- 跨项目的记忆不做比较（各项目上下文独立，不应互相干扰）

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `threshold` | 读取 `system_settings.dup_threshold`（默认 0.92） | UI 滑块范围 0.80–0.98 |
| `project_slug` | 无（全库） | 过滤到单个项目 |
| `type` | 无（全类型） | 过滤到单个类型 |
| `limit` | 200 | 最多返回对数 |

### UI 操作

- **Delete A / Delete B**：软删除其中一条，列表自动刷新
- **Skip**：从当前结果中移除该对（不写入数据库）
- 阈值滑块实时调整后需点 "Scan" 重新查询

---

## 冲突扫描（Conflicts）

### 触发时机

仅 UI 手动触发：工具栏 → "Conflicts" → 弹窗扫描。

> **设计决策**：写入时不做冲突检测，因为：
> 1. 冲突是主观判断（需人工确认），自动拦截会干扰正常写入
> 2. 计算量与记忆总量成平方关系，不适合实时触发

### SQL 逻辑（`GET /api/conflicts`）

```sql
SELECT m1.*, m2.*,
       1 - (m1.embedding <=> m2.embedding) AS similarity
FROM memories m1
JOIN memories m2 ON m1.id < m2.id AND m1.project_id = m2.project_id
WHERE m1.superseded_by IS NULL
  AND m2.superseded_by IS NULL
  AND m1.embedding IS NOT NULL
  AND m2.embedding IS NOT NULL
  AND 1 - (m1.embedding <=> m2.embedding) >= :min_sim   -- 默认 0.50
  AND 1 - (m1.embedding <=> m2.embedding) <  :max_sim   -- 自动 = dup_threshold − 0.01
ORDER BY similarity DESC
LIMIT :limit
```

- **仅匹配同项目内的记忆**（`m1.project_id = m2.project_id`）— 不同项目的上下文相互独立
- `max_sim` 由服务端从 `system_settings.dup_threshold` 动态读取，前端无需传入
- 相似度越高越靠前（越可能存在矛盾）

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `min_sim` | 0.50 | UI 滑块范围 0.40–0.85，决定"话题相近"的下界 |
| `project_slug` | 继承主界面过滤 | 打开时自动传入当前项目 |
| `type` | 继承主界面过滤 | 打开时自动传入当前类型 |
| `limit` | 200 | 最多返回对数 |

### UI 操作

- **Delete A / Delete B**：软删除其中一条
- **Skip**：从当前结果移除，保留两条记忆
- Min similarity 滑块向右（提高）= 更严格，结果更少但更可疑
- Min similarity 滑块向左（降低）= 更宽松，结果更多但信噪比下降

---

## 阈值关系图

```
0.0         0.40    0.50        0.91 0.92        1.0
 |------------|-------|-----------|---|------------|
              └── 可调 ──┘         ^   └─── 重复 ───┘
           min_sim 下限          自动上界
              (conflict 区间)   dup_threshold − 0.01
```

- 调高 `dup_threshold`（如 0.95）→ 重复区间收窄，冲突区间右界随之提高
- 调低 `min_sim`（如 0.40）→ 冲突区间左界左移，更多不相关对进入结果

---

## 数据流

```
前端 "Conflicts" 点击
  → openConflicts()
  → GET /api/conflicts?project_slug=...&type=...&min_sim=0.50
      → MemoryRepository 从 system_settings 读取 dup_threshold
      → pgvector 余弦距离查询（单次 SQL，无 Python 循环）
      → 返回 [{id1, name1, type1, ..., id2, name2, type2, ..., similarity}]
  → 渲染双列卡片，用户逐对审核
```

---

## 相关代码位置

| 文件 | 功能 |
|------|------|
| `routers/ui.py` → `find_duplicates()` | `GET /api/duplicates` 端点 |
| `routers/ui.py` → `find_conflicts()` | `GET /api/conflicts` 端点 |
| `repository.py` → `find_duplicates()` | 写入时调用的实时重复检测 |
| `settings_defaults.json` | `dup_threshold` 默认值 0.92 |
| `frontend/src/App.vue` → `scanDuplicates()` | UI 重复扫描逻辑 |
| `frontend/src/App.vue` → `scanConflicts()` | UI 冲突扫描逻辑 |
