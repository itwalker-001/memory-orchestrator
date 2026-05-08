# Memory Query Pipeline

> 记录 Memory Orchestrator 检索记忆的完整逻辑（截至 2026-05-08）

---

## 全流程概览

```
用户发消息
    ↓
UserPromptSubmit hook（每轮触发）
    ↓
GET /context?project_slug=<当前项目>&client=claude
    ↓
repo.build_context()
    ├─ 1. 确定搜索范围
    ├─ 2. 向量化查询
    ├─ 3. pgvector 粗排
    ├─ 4. hybrid_score 混合评分
    ├─ 5. 按分排序
    ├─ 6. [可选] reranker 精排
    ├─ 7. 混合分数融合
    ├─ 8. 截断 top_k
    └─ 9. token 预算截断
    ↓
Markdown 注入到系统提示（## Remembered context）
```

---

## 分步详解

### Step 1 — 确定搜索范围

`build_context()` 不走向量搜索，而是基于规则过滤（适合上下文注入场景）。
`search()` 走向量搜索（适合 MCP `search_memory` 工具调用）。

**build_context 过滤条件（OR）**：
- 全局项目的所有记忆（`project_id = 00000000-0000-0000-0000-000000000000`）
- 当前项目 `type=feedback` 且 `importance >= 3`
- 当前项目 `type=project` 且 `updated_at >= 30天内`
- 当前项目 `type=reference`（全部）

**search() 向量搜索范围**：由调用方传入 `project_ids`，通常为 `[当前项目 slug, "*"]`。

---

### Step 2 — 向量化查询（BGE-M3）

```python
# embedder.py
model = AutoModel.from_pretrained(model_path, local_files_only=True)

def _embed_sync(texts: list[str]) -> list[list[float]]:
    inputs = tokenizer(texts, padding=True, truncation=True, max_length=8192, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    # CLS token → L2 norm
    cls = outputs.last_hidden_state[:, 0, :]
    normed = cls / cls.norm(dim=-1, keepdim=True)
    return normed.tolist()   # 每条文本 1024-dim float 列表
```

- 模型：`BAAI/bge-m3`（ModelScope 镜像，本地 `models/bge-m3/`）
- 维度：1024
- 存储：`memories.embedding vector(1024)`（pgvector）

---

### Step 3 — pgvector 粗排

```python
distance = Memory.embedding.cosine_distance(query_embedding)
stmt = (
    select(Memory, distance.label("distance"))
    .where(...)
    .order_by(distance)
    .limit(top_k * 3)          # 默认 top_k=8 → 取 24 条候选
)
```

`cosine_distance ∈ [0, 2]`，相似度 `sim = 1.0 - distance`。

---

### Step 4 — hybrid_score 混合评分

```python
# scoring.py
def recency_decay(updated_at, half_life_days=60.0) -> float:
    age_days = (utc_now() - updated_at).total_seconds() / 86400.0
    return math.exp(-age_days / half_life_days)   # 60天后约 0.368

def hybrid_score(cosine_sim, importance, updated_at) -> float:
    importance_norm = (importance - 1) / 4.0      # [1,5] → [0.0, 1.0]
    return (
        0.6 * cosine_sim
      + 0.3 * importance_norm
      + 0.1 * recency_decay(updated_at)
    )
```

| 权重 | 信号 | 说明 |
|------|------|------|
| 0.6 | 余弦相似度 | 语义匹配程度 |
| 0.3 | 重要性（归一化） | 用户手动设置 1–5 |
| 0.1 | 时间衰减 | 半衰期 60 天 |

---

### Step 5 — 按 hybrid_score 排序

24 条候选按 `hybrid_score` 降序排列，进入精排或直接截断。

---

### Step 6 — Reranker 精排（可选）

由 `system_settings.rerank_enabled = "true"` 控制，无需重启。

```python
# reranker.py
model = AutoModelForSequenceClassification.from_pretrained(
    model_path, local_files_only=True, num_labels=1
)

def rerank_scores(query: str, texts: list[str]) -> list[float]:
    scores = []
    for text in texts:
        inputs = tokenizer([[query, text]], return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = model(**inputs).logits
        scores.append(torch.sigmoid(logits.squeeze()).item())  # → [0.0, 1.0]
    return scores
```

- 模型：`BAAI/bge-reranker-v2-m3`（本地 `models/bge-reranker-v2-m3/`）
- Cross-encoder：逐对评分，计算开销高于双编码器，故仅对 top_k×3 候选做精排
- 每次 forward 处理一对 (query, text)

---

### Step 7 — 混合分数融合

```python
# repository.py:247-253
scores = reranker.rerank_scores(query, texts)
blended = [(h, 0.8 * float(s) + 0.2 * h.score) for h, s in zip(hits, scores)]
hits = [
    Hit(memory=h.memory, score=final_s, cosine_sim=h.cosine_sim)
    for h, final_s in sorted(blended, key=lambda x: -x[1])
]
```

`final_score = 0.8 × reranker_score + 0.2 × hybrid_score`

Reranker 主导语义相关性，hybrid_score 保留重要性与时效性影响。

---

### Step 8 — 截断 top_k

```python
hits = hits[:top_k]   # 默认 top_k=8，可在 Settings → search_top_k 修改
```

---

### Step 9 — token 预算截断（仅 build_context）

```python
# repository.py
def estimate(m: Memory) -> int:
    return max(1, int(len(m.name + m.description + (m.content or "")) / 3.5))

items = [{"memory": m, "tokens": estimate(m), "importance": m.importance, ...}]
kept = truncate_by_budget(items, budget=hook_budget_tokens)  # 默认 1500 tokens
```

`truncate_by_budget` 按重要性降序贪心填满预算，超出则丢弃。

---

## 关键参数（system_settings）

| key | 默认值 | 说明 |
|-----|--------|------|
| `search_top_k` | 8 | 最终返回条数；粗排取 top_k×3 候选 |
| `hook_budget_tokens` | 1500 | 注入到系统提示的 token 上限 |
| `rerank_enabled` | "false" | "true" 开启 BGE-reranker 精排 |
| `rerank_model` | bge-reranker-v2-m3 | 精排模型路径（仅信息显示） |
| `hook_cooldown_sec` | 30 | UserPromptSubmit 最短触发间隔 |
| `hook_min_turns` | 3 | 至少 N 轮对话后才触发 context 注入 |
| `dup_threshold` | 0.92 | 保存时查重的余弦相似度阈值 |

---

## 去重（保存时）

```python
# repository.find_duplicates()
max_distance = 1.0 - threshold   # 默认 0.08
stmt = select(Memory).where(
    Memory.embedding.cosine_distance(embedding) <= max_distance,
    Memory.type == type,
    Memory.project_id == project_id,
    Memory.superseded_by.is_(None),
)
```

保存新记忆前，先用同类型、同项目的向量查重；若找到相似记忆，返回冲突供调用方决策（replace_id 触发 soft-delete 旧记忆）。

---

## Soft Delete

删除 = 将 `memories.superseded_by` 设为自身 ID（而非物理删除）。  
所有查询均过滤 `Memory.superseded_by.is_(None)`。

---

## 代码位置速查

| 逻辑 | 文件 | 关键函数 |
|------|------|---------|
| Hook 触发入口 | `memory_orchestrator_mcp/src/.../hooks/user_prompt_submit.py` | `main()` |
| Context 注入端点 | `memory_orchestrator_server/src/.../routers/hooks.py` | `GET /context` |
| build_context | `repository.py` | `MemoryRepository.build_context()` |
| 向量搜索 | `repository.py` | `MemoryRepository.search()` |
| 混合评分 | `scoring.py` | `hybrid_score()`, `recency_decay()` |
| Token 截断 | `scoring.py` | `truncate_by_budget()` |
| 嵌入向量 | `embedder.py` | `embed_one()`, `_embed_sync()` |
| Reranker | `reranker.py` | `rerank_scores()` |
| 去重 | `repository.py` | `MemoryRepository.find_duplicates()` |
