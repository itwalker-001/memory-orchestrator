# BM25 混合召回（ParadeDB pg_search）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有纯向量召回（pgvector）旁并行加一路 BM25 全文检索（ParadeDB pg_search + jieba 中文分词），加权融合两路分数，补足向量对专有名词/代码符号/缩写以及 512 token 截断尾部的召回弱项。

**Architecture:** 换 DB 镜像为 `paradedb/paradedb:16-v0.23.5`（自带 pgvector 0.8.2 + pg_search，PG16 数据卷直接挂载、无需 dump/restore 迁移）。新增 alembic 迁移建 `pg_search` 扩展和一个 jieba BM25 索引（覆盖 name+description+content）。`repository.search()` 内在向量召回后并行查一路 BM25，按 min-max 归一化后与现有 hybrid_score 加权融合。新增 `bm25_enabled` / `score_bm25_weight` 两个运行时设置项。向量列、HNSW 索引、embedder、重嵌逻辑一律不动。

**Tech Stack:** PostgreSQL 16 + pgvector 0.8.2 + ParadeDB pg_search（Tantivy/jieba）、SQLAlchemy async、Alembic、FastAPI、Docker Compose。

---

## 背景事实（实施前必读，全部已实测确认）

- **当前 DB**：镜像 `pgvector/pgvector:pg16`（本地 tag `memory-orchestrator-db:dd7d4c3cdae8`），pgvector **0.8.2**，扩展 `vector` / `pgcrypto` / `plpgsql`。生产库（172.16.10.123:25432）**57 条记忆**。
- **备份已就位**：`/opt/memory-orchestrator/mo_backup_20260616_164226.dump`（357 KB，custom 格式）。回滚命令见末尾。
- **向量维度 1024**（BGE-M3，`embedding vector(1024)`），本计划**不改向量任何部分**。
- **当前 `search()`（repository.py:252-331）是纯向量召回**：cosine_distance 排序取 `top_k*3` → `hybrid_score` 重排 → 可选 reranker → 截 `top_k` → 可选 record_hits。
- **`hybrid_score`（scoring.py:22-39）**：`base = cosine_weight*cosine_sim + importance_weight*importance_norm + recency_weight*recency_decay; return base*type_boost`。`importance_norm=(importance-1)/4.0`。
- **`Hit`（repository.py:687-691）**：`@dataclass` 含 `memory: Memory`、`score: float`、`cosine_sim: float`。
- **设置项机制**：默认值在 `settings_defaults.json`，启动时 `seed_settings`（http_app.py:88，仅插入缺失键、不覆盖）。读取走 `repo.get_settings()`（60s 缓存）。UI 可编辑的键在 `routers/ui.py:20` 的 `SETTINGS_KEYS` 白名单 + `SettingsPayload` 模型字段。
- **ParadeDB v2 BM25 语法**（已确认）：
  - 建索引：`CREATE INDEX <name> ON memories USING bm25 (id, (name::pdb.jieba), (description::pdb.jieba), (content::pdb.jieba)) WITH (key_field='id');`
  - 查询：`SELECT id, paradedb.score(id) FROM memories WHERE id @@@ paradedb.boolean(...) ORDER BY paradedb.score(id) DESC`，或简单式 `WHERE name @@@ '词'`。本计划用跨列 disjunction（见 Task 4）。
- **AGE 图功能是死代码**：compose 只 preload 了 `vector`，从未 preload age，`graph.py` 的 `LOAD 'age'` 一直静默失败。换镜像不损失在用功能。
- **`Dockerfile.db` 全文一行** `FROM pgvector/pgvector:pg16`（CRLF 结尾），compose 传的 `SOCKS5_PROXY` build arg 未被使用。决定：**保留该文件、只改 FROM**（做法 A），build.sh / compose 的 db 构建逻辑不动。

## 文件结构（改动清单）

| 文件 | 动作 | 责任 |
|---|---|---|
| `Dockerfile.db` | 改 1 行 | base 镜像换 ParadeDB |
| `docker-compose.yml` | 改 1 行 | `shared_preload_libraries=vector` → `vector,pg_search` |
| `memory_orchestrator_server/db_check.py` | 改 | `REQUIRED_EXTENSIONS` 加 `pg_search`，提示文案同步 |
| `memory_orchestrator_server/alembic/versions/0003_pg_search_bm25.py` | 新建 | `CREATE EXTENSION pg_search` + 建 jieba BM25 索引 |
| `memory_orchestrator_server/settings_defaults.json` | 改 | 加 `bm25_enabled` / `score_bm25_weight` 默认值 |
| `memory_orchestrator_server/routers/ui.py` | 改 | `SETTINGS_KEYS` + `SettingsPayload` 加两个新键 |
| `memory_orchestrator_server/bm25_search.py` | 新建 | BM25 查询函数：跨列 jieba 检索 → `{memory_id: bm25_score}` |
| `memory_orchestrator_server/repository.py` | 改 | `search()` 融合 BM25 一路；新增 `_minmax_norm` 辅助 |
| `memory_orchestrator_server/tests/unit/test_bm25_fusion.py` | 新建 | 融合算法纯单测（不依赖 DB） |
| `memory_orchestrator_server/tests/integration/test_bm25_search.py` | 新建 | BM25 端到端（需 ParadeDB 测试库） |

**实施顺序**：基础设施（Task 1-3，换镜像+扩展+迁移）必须先在 123 上跑通，之后才是代码融合（Task 4-7）。Task 1-3 是部署动作，Task 4-7 是可 TDD 的代码。

---

### Task 1: DB 镜像换 ParadeDB

**Files:**
- Modify: `Dockerfile.db`
- Modify: `docker-compose.yml:19`

- [ ] **Step 1: 改 Dockerfile.db 的 base 镜像**

把 `Dockerfile.db` 全文替换为（注意去掉 CRLF，用 LF）：

```dockerfile
FROM paradedb/paradedb:16-v0.23.5
```

> 选 `16-v0.23.5` 这一具体 tag（PG16 + 钉死 ParadeDB 版本），不用浮动的 `latest-pg16`，保证可复现。该镜像自带 pgvector 0.8.2（= 现有库版本，无需 `ALTER EXTENSION vector UPDATE`）。若该 tag 拉取失败，回退用 `latest-pg16` 并在部署记录里写明实际版本。

- [ ] **Step 2: 改 compose 的 preload**

`docker-compose.yml` 第 19 行：

```yaml
      -c shared_preload_libraries=vector
```

改为：

```yaml
      -c shared_preload_libraries=vector,pg_search
```

> `pg_search` 是 preload 扩展，不加这行即使 `CREATE EXTENSION` 成功也无法建/用 BM25 索引。改 preload 必须重启容器才生效（Task 3 会重启）。

- [ ] **Step 3: 本地构建验证镜像可拉取**

Run（本地能联网时）：
```bash
docker pull paradedb/paradedb:16-v0.23.5 && echo PULL_OK
```
Expected: 输出 `PULL_OK`。若环境走代理拉不到，跳过本步，到 123 上 Task 3 时再拉。

- [ ] **Step 4: 提交**

```bash
git add Dockerfile.db docker-compose.yml
git commit -m "build: switch db image to ParadeDB pg16 (pgvector+pg_search), preload pg_search"
```

---

### Task 2: db_check 接受 pg_search 扩展

**Files:**
- Modify: `memory_orchestrator_server/db_check.py:9`（`REQUIRED_EXTENSIONS`）
- Modify: `memory_orchestrator_server/db_check.py:101,110`（查询与提示文案）

- [ ] **Step 1: 读现状确认行号**

Run:
```bash
grep -n "REQUIRED_EXTENSIONS\|pgcrypto', 'vector\|Install pgvector" memory_orchestrator_server/db_check.py
```
Expected: 看到 `REQUIRED_EXTENSIONS = {"pgcrypto", "vector"}`（line 9 附近）、`WHERE extname IN ('pgcrypto', 'vector')`（line 101 附近）、提示文案（line 110 附近）。

- [ ] **Step 2: 改 REQUIRED_EXTENSIONS**

`db_check.py:9`：
```python
REQUIRED_EXTENSIONS = {"pgcrypto", "vector"}
```
改为：
```python
REQUIRED_EXTENSIONS = {"pgcrypto", "vector", "pg_search"}
```

- [ ] **Step 3: 改扩展查询的 IN 列表**

`db_check.py:101` 附近：
```python
                "WHERE extname IN ('pgcrypto', 'vector')"
```
改为：
```python
                "WHERE extname IN ('pgcrypto', 'vector', 'pg_search')"
```

- [ ] **Step 4: 改缺失提示文案**

`db_check.py:110` 附近：
```python
                + ". Install pgvector, then run: uv run alembic upgrade head."
```
改为：
```python
                + ". Install pgvector + pg_search (use the ParadeDB image), then run: uv run alembic upgrade head."
```

- [ ] **Step 5: 跑现有 db_check 相关单测确认未破坏**

Run:
```bash
cd memory_orchestrator_server && uv run pytest tests/ -k "db_check or container_config" -q
```
Expected: PASS（或与基线一致的 skip）。若无对应测试，跳过本步。

- [ ] **Step 6: 提交**

```bash
git add memory_orchestrator_server/db_check.py
git commit -m "feat(db): require pg_search extension in preflight check"
```

---

### Task 3: alembic 迁移建 pg_search 扩展 + BM25 索引，并在 123 上施行

**Files:**
- Create: `memory_orchestrator_server/alembic/versions/0003_pg_search_bm25.py`

- [ ] **Step 1: 写迁移文件**

Create `memory_orchestrator_server/alembic/versions/0003_pg_search_bm25.py`：

```python
"""add pg_search extension and BM25 jieba index on memories

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-16
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

BM25_INDEX = "memories_bm25_idx"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    # BM25 covering index: key_field 必须是第一列且有唯一索引（id 是主键，满足）。
    # name/description/content 三列各自用 jieba 中文分词；其余列不入索引（只做全文）。
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {BM25_INDEX} ON memories "
        "USING bm25 (id, (name::pdb.jieba), (description::pdb.jieba), (content::pdb.jieba)) "
        "WITH (key_field='id')"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {BM25_INDEX}")
    # 不 DROP EXTENSION pg_search：preload 库不可在事务里随意卸载，且其他对象可能依赖。
```

- [ ] **Step 2: 本地无 ParadeDB 时跳过本地 upgrade，直接在 123 部署验证**

> 本地开发库若仍是 pgvector 镜像，`USING bm25` 会失败。该迁移的真实验证在 123（已是 ParadeDB 后）。本地仅做语法自检：

Run:
```bash
cd memory_orchestrator_server && uv run python -c "import alembic.versions"  2>/dev/null; python -c "import ast; ast.parse(open('alembic/versions/0003_pg_search_bm25.py').read()); print('SYNTAX_OK')"
```
Expected: `SYNTAX_OK`。

- [ ] **Step 3: 提交迁移**

```bash
git add memory_orchestrator_server/alembic/versions/0003_pg_search_bm25.py
git commit -m "feat(db): alembic 0003 — pg_search extension + jieba BM25 index on memories"
```

- [ ] **Step 4: 推送源码到 123 并重建（换镜像 + 重启 + 迁移）**

> 备份已在 `/opt/memory-orchestrator/mo_backup_20260616_164226.dump`。换镜像挂同一 PGDATA（PG16→PG16，无需 dump 迁移）。

Run（PowerShell，密码经环境变量，勿写入文件）：
```powershell
$env:MO_PUSH_PASSWORD='<服务器密码>'
.\scripts\push.ps1 -Server 172.16.10.123 -Force
```
Expected: tar 上传 → build.sh 重建 db（ParadeDB 镜像）+ server → healthcheck 通过。

> 若 `push.ps1 -Force` 因 base 镜像重建过久，可改用默认（不带 `-Force`）只重建 db+server。关键是 db 容器要用新镜像重启以加载 `shared_preload_libraries=vector,pg_search`。

- [ ] **Step 5: 在 123 上确认扩展与索引已建**

Run（plink，bash）：
```bash
export MO_PUSH_PASSWORD='<服务器密码>'
"/c/Program Files/PuTTY/plink.exe" -batch -pw "$MO_PUSH_PASSWORD" root@172.16.10.123 \
  "docker exec memory-orchestrator-db psql -U postgres -d memory_orchestrator -tAc \"SELECT extname FROM pg_extension WHERE extname IN ('vector','pg_search'); SELECT indexname FROM pg_indexes WHERE indexname='memories_bm25_idx';\""
```
Expected: 输出含 `vector`、`pg_search`、`memories_bm25_idx`。若 `pg_search` 缺失 → preload 未生效，检查 compose 改动是否上传并重启了 db 容器。

- [ ] **Step 6: 在 123 上冒烟测一条 BM25 查询**

Run:
```bash
export MO_PUSH_PASSWORD='<服务器密码>'
"/c/Program Files/PuTTY/plink.exe" -batch -pw "$MO_PUSH_PASSWORD" root@172.16.10.123 \
  "docker exec memory-orchestrator-db psql -U postgres -d memory_orchestrator -tAc \"SELECT name, paradedb.score(id) FROM memories WHERE id @@@ paradedb.match('content', '深色模式') ORDER BY paradedb.score(id) DESC LIMIT 3;\""
```
Expected: 返回若干行（name + 分数），证明 jieba 分词 + BM25 打分链路通。若报 `function paradedb.match does not exist`，改用简单式 `WHERE content @@@ '深色模式'` 再试（不同 ParadeDB 版本函数名略有差异，以实际可用者为准，并据此校准 Task 4 的 SQL）。

---

### Task 4: BM25 查询函数（bm25_search.py）

**Files:**
- Create: `memory_orchestrator_server/bm25_search.py`
- Test: `memory_orchestrator_server/tests/integration/test_bm25_search.py`

- [ ] **Step 1: 写失败的集成测试**

Create `memory_orchestrator_server/tests/integration/test_bm25_search.py`：

```python
import pytest
from memory_orchestrator_server.bm25_search import bm25_scores

pytestmark = pytest.mark.asyncio


async def test_bm25_scores_returns_keyword_hit(db_session, seeded_memories):
    """jieba BM25 命中含某关键词的记忆，返回 {memory_id: score>0}。
    seeded_memories 应至少含一条 content 提到 '深色模式' 的记忆。"""
    scores = await bm25_scores(
        db_session,
        query="深色模式",
        project_ids=[seeded_memories.project_id],
        limit=10,
    )
    assert isinstance(scores, dict)
    assert any(v > 0 for v in scores.values())


async def test_bm25_scores_empty_query_returns_empty(db_session, seeded_memories):
    scores = await bm25_scores(
        db_session, query="   ", project_ids=[seeded_memories.project_id], limit=10
    )
    assert scores == {}


async def test_bm25_scores_scopes_to_projects(db_session, seeded_memories):
    scores = await bm25_scores(
        db_session, query="深色模式", project_ids=[], limit=10
    )
    assert scores == {}
```

> `db_session` / `seeded_memories` fixture：若 `tests/integration/conftest.py` 已有等价 fixture，复用；否则在该 conftest 加一个 `seeded_memories`，插入 2-3 条已知 content 的记忆并返回带 `project_id` 的对象。本步只写测试，fixture 缺失会在 Step 2 暴露。

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd memory_orchestrator_server && uv run pytest tests/integration/test_bm25_search.py -v
```
Expected: FAIL，`ModuleNotFoundError: No module named 'memory_orchestrator_server.bm25_search'`（或 fixture 缺失错误）。

- [ ] **Step 3: 实现 bm25_search.py**

Create `memory_orchestrator_server/bm25_search.py`：

```python
"""BM25 全文检索（ParadeDB pg_search + jieba）。返回 {memory_id: bm25_score}，
供 repository.search() 与向量召回融合。与向量路完全独立——这里只查关键词分数。"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 跨 name/description/content 三列做 OR 匹配，任一列命中即计分；
# paradedb.score(id) 返回该行的 BM25 相关度。project 过滤用普通 WHERE（BM25 索引含 id 主键，
# 普通列过滤由规划器结合处理）。
_BM25_SQL = text(
    """
    SELECT m.id::text AS id, paradedb.score(m.id) AS score
    FROM memories m
    WHERE m.superseded_by IS NULL
      AND m.project_id = ANY(:project_ids)
      AND (m.name @@@ :q OR m.description @@@ :q OR m.content @@@ :q)
    ORDER BY paradedb.score(m.id) DESC
    LIMIT :limit
    """
)


async def bm25_scores(
    session: AsyncSession,
    *,
    query: str,
    project_ids: list[uuid.UUID],
    limit: int,
) -> dict[uuid.UUID, float]:
    q = (query or "").strip()
    if not q or not project_ids:
        return {}
    result = await session.execute(
        _BM25_SQL,
        {"q": q, "project_ids": [str(p) for p in project_ids], "limit": limit},
    )
    return {uuid.UUID(row.id): float(row.score) for row in result.all()}
```

> **校准提示**：`@@@ :q` 的右值语义随 ParadeDB 版本而定。若 Task 3 Step 6 证明本版本需要 `paradedb.match('col', :q)` 形式，则把 WHERE 子句改为 `(paradedb.match('name', :q) OR paradedb.match('description', :q) OR paradedb.match('content', :q))`。以 Task 3 Step 6 实测可用的语法为准。

- [ ] **Step 4: 运行测试确认通过**

Run（需指向 ParadeDB 测试库，见 conftest 的 `MO_TEST_DB_DSN`）:
```bash
cd memory_orchestrator_server && uv run pytest tests/integration/test_bm25_search.py -v
```
Expected: 3 PASS。若测试库仍是纯 pgvector，本 Task 的集成测试会 skip/fail——需先让测试库也用 ParadeDB 镜像（或临时指向 123）。

- [ ] **Step 5: 提交**

```bash
git add memory_orchestrator_server/bm25_search.py memory_orchestrator_server/tests/integration/test_bm25_search.py
git commit -m "feat(search): add BM25 jieba keyword scoring (bm25_search.py)"
```

---

### Task 5: 融合归一化辅助 + 纯单测

**Files:**
- Modify: `memory_orchestrator_server/repository.py`（新增模块级 `_minmax_norm`）
- Test: `memory_orchestrator_server/tests/unit/test_bm25_fusion.py`

- [ ] **Step 1: 写失败的单测**

Create `memory_orchestrator_server/tests/unit/test_bm25_fusion.py`：

```python
from memory_orchestrator_server.repository import _minmax_norm


def test_minmax_norm_basic():
    out = _minmax_norm({"a": 2.0, "b": 4.0, "c": 6.0})
    assert out["a"] == 0.0
    assert out["c"] == 1.0
    assert abs(out["b"] - 0.5) < 1e-9


def test_minmax_norm_single_value_maps_to_one():
    # 只有一个候选时，max==min，应映射为 1.0（满分），不能除零。
    assert _minmax_norm({"x": 3.7}) == {"x": 1.0}


def test_minmax_norm_empty():
    assert _minmax_norm({}) == {}


def test_minmax_norm_all_equal():
    out = _minmax_norm({"a": 5.0, "b": 5.0})
    assert out == {"a": 1.0, "b": 1.0}
```

- [ ] **Step 2: 运行确认失败**

Run:
```bash
cd memory_orchestrator_server && uv run pytest tests/unit/test_bm25_fusion.py -v
```
Expected: FAIL，`ImportError: cannot import name '_minmax_norm'`。

- [ ] **Step 3: 在 repository.py 加 _minmax_norm**

在 `repository.py` 模块级（靠近 `Hit` dataclass 之后，或文件顶部辅助区，确保在 `MemoryRepository.search` 可见的模块作用域）新增：

```python
def _minmax_norm(scores: dict) -> dict:
    """把一组分数 min-max 归一化到 [0,1]。空 → 空；max==min（含单元素）→ 全 1.0。
    用于把 BM25 原始分（无固定上界）拉到与 cosine 同量纲再加权融合。"""
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 1.0 for k in scores}
    span = hi - lo
    return {k: (v - lo) / span for k, v in scores.items()}
```

- [ ] **Step 4: 运行确认通过**

Run:
```bash
cd memory_orchestrator_server && uv run pytest tests/unit/test_bm25_fusion.py -v
```
Expected: 4 PASS。

- [ ] **Step 5: 提交**

```bash
git add memory_orchestrator_server/repository.py memory_orchestrator_server/tests/unit/test_bm25_fusion.py
git commit -m "feat(search): add _minmax_norm helper for BM25/vector fusion"
```

---

### Task 6: 新增 bm25 设置项

**Files:**
- Modify: `memory_orchestrator_server/settings_defaults.json`
- Modify: `memory_orchestrator_server/routers/ui.py:20`（`SETTINGS_KEYS`）
- Modify: `memory_orchestrator_server/routers/ui.py`（`SettingsPayload` 模型，line 61-67 附近）

- [ ] **Step 1: 加默认值**

`settings_defaults.json` 在 `score_rerank_blend` 行后加两键（注意 JSON 逗号）：

```json
{
  "hook_cooldown_sec": "300",
  "hook_min_turns": "1",
  "hook_budget_tokens": "2000",
  "search_top_k": "3",
  "dup_threshold": "0.92",
  "rerank_enabled": "false",
  "rerank_model": "",
  "score_cosine_weight": "0.6",
  "score_importance_weight": "0.3",
  "score_recency_weight": "0.1",
  "score_recency_half_life": "60",
  "score_rerank_blend": "0.8",
  "bm25_enabled": "true",
  "score_bm25_weight": "0.5",
  "score_type_feedback": "1.3",
  "score_type_project": "1.1",
  "score_type_user": "1.0",
  "score_type_reference": "0.9"
}
```

> `bm25_enabled` 默认 `true`（部署后即生效）；`score_bm25_weight=0.5` 表示融合时 BM25 归一化分占 0.5 权重叠加到 hybrid 分上（公式见 Task 7）。`seed_settings` 只插缺失键，已有库不会被覆盖，所以 123 升级后这两键会被新插入。

- [ ] **Step 2: 加进 SETTINGS_KEYS 白名单**

`routers/ui.py:20` 的 `SETTINGS_KEYS` 列表，在 `"score_recency_half_life", "score_rerank_blend",` 这行后加：

```python
    "bm25_enabled", "score_bm25_weight",
```

- [ ] **Step 3: 加进 SettingsPayload 模型**

`routers/ui.py` 的 `SettingsPayload`（含 `rerank_enabled`、`score_cosine_weight` 等字段，line 61-67 附近）新增两字段：

```python
    bm25_enabled: str | None = None
    score_bm25_weight: str | None = None
```

- [ ] **Step 4: 验证 settings 往返不报错**

Run:
```bash
cd memory_orchestrator_server && uv run python -c "import json; d=json.load(open('settings_defaults.json')); assert 'bm25_enabled' in d and 'score_bm25_weight' in d; print('SEED_OK')"
```
Expected: `SEED_OK`。

- [ ] **Step 5: 提交**

```bash
git add memory_orchestrator_server/settings_defaults.json memory_orchestrator_server/routers/ui.py
git commit -m "feat(settings): add bm25_enabled and score_bm25_weight runtime settings"
```

---

### Task 7: search() 融合 BM25 一路

**Files:**
- Modify: `memory_orchestrator_server/repository.py:252-331`（`search` 方法）
- Test: `memory_orchestrator_server/tests/integration/test_bm25_search.py`（加融合断言）

- [ ] **Step 1: 加融合集成测试**

在 `tests/integration/test_bm25_search.py` 末尾追加：

```python
async def test_search_fusion_boosts_keyword_match(db_session, seeded_memories, repo_factory):
    """开启 bm25 后，纯关键词命中（向量未必近）的记忆应进入结果。
    repo_factory 构造 MemoryRepository；seeded_memories 含一条 content 提到独特符号
    'IdleTimer' 的记忆，但其向量与查询语义未必接近。"""
    repo = repo_factory(db_session)
    # 确保开关开启（直接写 settings）
    await repo.set_settings({"bm25_enabled": "true", "score_bm25_weight": "0.8"})
    qvec = [0.0] * 1024  # 故意给一个无意义向量，逼近全靠 BM25
    hits = await repo.search(
        query_embedding=qvec,
        project_ids=[seeded_memories.project_id],
        top_k=5,
        query="IdleTimer",
    )
    names = [h.memory.name for h in hits]
    assert any("IdleTimer" in (h.memory.content or "") for h in hits), names
```

> `repo_factory` fixture：若 conftest 无，加一个返回 `lambda s: MemoryRepository(s)` 的 fixture。

- [ ] **Step 2: 运行确认失败**

Run:
```bash
cd memory_orchestrator_server && uv run pytest tests/integration/test_bm25_search.py::test_search_fusion_boosts_keyword_match -v
```
Expected: FAIL（融合未实现，零向量召不回 IdleTimer 那条）。

- [ ] **Step 3: 在 search() 注入 BM25 融合**

当前 `repository.py` 的 `search`（252-331）结构：建 distance stmt → 取 rows → 读 cfg 权重 → 逐行 `hybrid_score` 成 `hits` → `hits.sort` → 可选 reranker → `hits[:top_k]` → record_hits。

在 **`hits.sort(key=lambda h: -h.score)`（约 line 304）之后、reranker 块（约 line 306）之前**，插入 BM25 融合。改法如下——找到这段：

```python
            hits.append(Hit(memory=mem, score=score, cosine_sim=sim))
        hits.sort(key=lambda h: -h.score)

        if query and cfg.get("rerank_enabled", "false").lower() == "true":
```

替换为：

```python
            hits.append(Hit(memory=mem, score=score, cosine_sim=sim))
        hits.sort(key=lambda h: -h.score)

        # --- BM25 融合：在向量候选基础上叠加关键词分数 ---
        if query and cfg.get("bm25_enabled", "true").lower() == "true":
            from memory_orchestrator_server.bm25_search import bm25_scores

            bm25_w = float(cfg.get("score_bm25_weight", "0.5"))
            raw_bm25 = await bm25_scores(
                self.session, query=query,
                project_ids=resolved_project_ids, limit=top_k * 3,
            )
            if raw_bm25:
                norm_bm25 = _minmax_norm(raw_bm25)
                # 把 BM25 命中的记忆并入候选：向量已召回的叠加分数，
                # 纯 BM25 命中（向量没召回）的补成新 Hit。
                by_id = {h.memory.id: h for h in hits}
                for mem_id, nb in norm_bm25.items():
                    if mem_id in by_id:
                        h = by_id[mem_id]
                        h.score = h.score + bm25_w * nb
                    else:
                        extra = await self.session.get(Memory, mem_id)
                        if extra is not None and extra.superseded_by is None:
                            hits.append(Hit(memory=extra, score=bm25_w * nb, cosine_sim=0.0))
                hits.sort(key=lambda h: -h.score)

        if query and cfg.get("rerank_enabled", "false").lower() == "true":
```

> 设计要点：
> - 融合发生在 hybrid_score 之后、reranker 之前——reranker（若开）仍对融合后的候选做最终重排，三者可叠加。
> - `Hit.score` 是普通 float 字段，可直接 `+=`（dataclass 非 frozen）。
> - 纯 BM25 命中的记忆 `cosine_sim=0.0`（它本就不是向量召回的），UI/recall-test 显示 0 是真实情况。
> - `limit=top_k*3` 与向量候选池同量级，避免 BM25 拉入过多噪声。

- [ ] **Step 4: 运行融合测试确认通过**

Run:
```bash
cd memory_orchestrator_server && uv run pytest tests/integration/test_bm25_search.py -v
```
Expected: 全部 PASS（含新增融合用例）。

- [ ] **Step 5: 跑回归——确保向量路与现有 mcp 工具测试未破坏**

Run:
```bash
cd memory_orchestrator_server && uv run pytest tests/integration/test_mcp_tools.py tests/integration/test_repository.py -q
```
Expected: 与基线一致（注：基线已知有 11 个与 DB session 相关的预存失败，非本改动引入；只要不新增失败即可）。

- [ ] **Step 6: 提交**

```bash
git add memory_orchestrator_server/repository.py memory_orchestrator_server/tests/integration/test_bm25_search.py
git commit -m "feat(search): fuse BM25 keyword scores into hybrid recall"
```

---

### Task 8: 部署 123 + recall-test 端到端验证

**Files:** 无（部署 + 验证）

- [ ] **Step 1: 推送全部代码到 123 并重建**

Run（PowerShell）:
```powershell
$env:MO_PUSH_PASSWORD='<服务器密码>'
.\scripts\push.ps1 -Server 172.16.10.123
```
Expected: 同步 + 重建 + healthcheck 通过。

- [ ] **Step 2: 确认新设置项已 seed**

Run:
```bash
export MO_PUSH_PASSWORD='<服务器密码>'
"/c/Program Files/PuTTY/plink.exe" -batch -pw "$MO_PUSH_PASSWORD" root@172.16.10.123 \
  "docker exec memory-orchestrator-db psql -U postgres -d memory_orchestrator -tAc \"SELECT key,value FROM system_settings WHERE key IN ('bm25_enabled','score_bm25_weight');\""
```
Expected: `bm25_enabled|true`、`score_bm25_weight|0.5`。

- [ ] **Step 3: 通过 recall-test 端点对比开/关 BM25 的召回**

> recall-test 走同一 `search_memories` → `repo.search`，自动带 BM25。挑一个**含专有名词/代码符号**的查询（向量弱项），验证 BM25 把对应记忆拉上来。用 UI（http://<123>:<port>/ui → Recall 召回测试页）或直接 curl `/api/recall-test?query=IdleTimer&project_slug=all`（带 ui_admin token）。

人工验收标准：
- 查 `IdleTimer` / `Outbox` / `ZPL` 等代码符号，对应记忆出现在结果前列（开 BM25 前可能召不回）。
- 查一个语义性中文短语（如 `深色模式和快捷键偏好`），结果与改动前一致或更好（向量路未退化）。

- [ ] **Step 4: 若 BM25 噪声过大，调权重（运行时，无需重部署）**

在 UI Settings 把 `score_bm25_weight` 调小（如 0.3）或将 `bm25_enabled` 设 `false` 临时关闭。60s 缓存后生效。

- [ ] **Step 5: 记录最终权重，结束**

无需提交（设置存 DB）。在部署记录里写明最终 `score_bm25_weight` 值。

---

## 回滚预案

换镜像后若 ParadeDB 启动异常或 BM25 不可用，按以下顺序回滚：

1. **仅代码回滚（保留 ParadeDB 镜像）**：把 `bm25_enabled` 设 `false`（UI 或直接 SQL），召回退回纯向量。无需重部署。
2. **整体回滚到 pgvector 镜像**：
   - `Dockerfile.db` 改回 `FROM pgvector/pgvector:pg16`，compose preload 改回 `vector`。
   - **注意**：一旦建过 BM25 索引，回纯 pgvector 镜像前需先 `DROP INDEX memories_bm25_idx; DROP EXTENSION IF EXISTS pg_search;`（否则旧镜像加载 BM25 索引会失败）。
   - 重建 db 容器。数据本身（57 条记忆 + 向量）不受影响，PGDATA 同为 PG16。
3. **数据级灾难恢复**（仅在 PGDATA 损坏时）：
   ```bash
   docker exec -i memory-orchestrator-db pg_restore -U postgres -d memory_orchestrator --clean \
     < /opt/memory-orchestrator/mo_backup_20260616_164226.dump
   ```

---

## Self-Review

**Spec 覆盖**：换镜像（T1）、扩展校验（T2）、迁移建索引（T3）、BM25 查询（T4）、归一化（T5）、设置项（T6）、融合（T7）、部署验证（T8）——覆盖"加 BM25 提准确率 + 向量不动 + 加权融合 + ParadeDB 16 镜像 + dump 备份"全部决策。

**Placeholder 扫描**：所有 SQL、Python、命令均为完整内容；`<服务器密码>` 是有意的密钥占位（安全约束：不得写入文件，仅环境变量传入）；ParadeDB 版本 tag 与 `@@@` 语法给了"以 Task 3 Step 6 实测为准"的校准分支，因不同 ParadeDB 小版本函数名有差异，这是必要的现场校准而非占位。

**类型一致性**：`bm25_scores(session, *, query, project_ids, limit) -> dict[uuid.UUID, float]` 在 T4 定义、T7 调用签名一致；`_minmax_norm(dict)->dict` 在 T5 定义、T7 调用一致；`Hit(memory, score, cosine_sim)` 字段与现有 dataclass 一致；设置键 `bm25_enabled`/`score_bm25_weight` 在 T6 定义、T7 读取、T8 验证三处拼写一致。
