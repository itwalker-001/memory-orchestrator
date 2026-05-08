# Rerank + BGE-M3 Embedding Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FastEmbed/bge-small-zh-v1.5 (512-dim) embedder with FlagEmbedding/BGE-M3 (1024-dim) and add a cross-encoder reranker (bge-reranker-v2-m3) to the search pipeline.

**Architecture:** FlagEmbedding library handles both embedding (BGEM3FlagModel) and reranking (FlagReranker) via PyTorch. The reranker takes query-text pairs and scores them; `repository.search()` calls it after pgvector retrieval when `rerank_enabled=true` in system_settings. Both models are loaded at HTTP server startup via `lru_cache` singletons.

**Tech Stack:** FlagEmbedding>=1.2, PyTorch (pulled by FlagEmbedding), pgvector vector(1024), Alembic migration, FastAPI startup event.

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `memory_orchestrator_server/pyproject.toml` | Modify | Remove `fastembed`, add `FlagEmbedding>=1.2` |
| `memory_orchestrator_server/src/memory_orchestrator_server/config.py` | Modify | `embed_model`, `embed_dim`, add `rerank_model` |
| `memory_orchestrator_server/src/memory_orchestrator_server/embedder.py` | Modify | Replace FastEmbed with FlagEmbedding BGEM3FlagModel |
| `memory_orchestrator_server/src/memory_orchestrator_server/reranker.py` | Create | FlagReranker singleton; `rerank_scores(query, texts) → list[float]` |
| `memory_orchestrator_server/src/memory_orchestrator_server/models.py` | No change | Vector dim already read from `get_settings().embed_dim`; will be 1024 after config change |
| `memory_orchestrator_server/src/memory_orchestrator_server/alembic/versions/0006_embed_dim_1024.py` | Create | Drop HNSW index, null embeddings, alter to vector(1024), recreate index, insert default system_settings |
| `memory_orchestrator_server/src/memory_orchestrator_server/repository.py` | Modify | `search()` adds `query: str \| None = None`; calls reranker when enabled |
| `memory_orchestrator_server/src/memory_orchestrator_server/http_app.py` | Modify | Call `ensure_reranker()` at startup |
| `memory_orchestrator_server/src/memory_orchestrator_server/mcp_core.py` | Modify | Pass `query=query` to `repo.search()` |
| `memory_orchestrator_server/src/memory_orchestrator_server/cli.py` | Modify | Add `mo-server migrate-embeddings` command |
| `memory_orchestrator_server/src/memory_orchestrator_server/tests/integration/test_repository.py` | Modify | Update 512-dim vectors → 1024-dim; add rerank test |
| `memory_orchestrator_server/src/memory_orchestrator_server/tests/integration/test_mcp_tools.py` | Modify | Update `FAKE_EMB` to 1024-dim |
| `memory_orchestrator_server/src/memory_orchestrator_server/tests/unit/test_package_boundaries.py` | Modify | Add `FlagEmbedding` to MCP forbidden imports |

---

## Task 1: Update Dependencies and Config

**Files:**
- Modify: `memory_orchestrator_server/pyproject.toml`
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/config.py`

- [ ] **Step 1: Edit pyproject.toml — remove fastembed, add FlagEmbedding**

In `memory_orchestrator_server/pyproject.toml`, replace:
```toml
    "fastembed>=0.4",
```
with:
```toml
    "FlagEmbedding>=1.2",
```

- [ ] **Step 2: Update config.py defaults and add rerank_model**

Replace the full `config.py` with:

```python
from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PKG_ROOT = Path(__file__).parent.parent.parent  # memory_orchestrator_server/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MO_",
        env_file=[str(_PKG_ROOT / ".env"), ".env"],
        extra="ignore",
    )

    db_dsn: str = Field(default="postgresql+asyncpg://postgres:1234@localhost:5432/memory_orchestrator")
    http_port: int = 8765
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    log_level: str = "DEBUG"

    extraction_base_url: str = Field(default="", validation_alias="MO_EXTRACTION_BASE_URL")
    extraction_model: str = Field(default="gpt-4o-mini", validation_alias="MO_EXTRACTION_MODEL")
    extraction_api_key: str = Field(default="local", validation_alias="MO_EXTRACTION_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

Note: `embed_cache_dir` is removed — FlagEmbedding uses the standard HuggingFace cache (`~/.cache/huggingface/hub/`).

- [ ] **Step 3: Install updated dependencies**

```bash
cd memory_orchestrator_server
uv sync
```

Expected: resolves without error, `FlagEmbedding` appears in the lockfile, `fastembed` is gone.

- [ ] **Step 4: Commit**

```bash
cd memory_orchestrator_server
git add pyproject.toml src/memory_orchestrator_server/config.py
git commit -m "feat: switch to FlagEmbedding, update embed/rerank config defaults"
```

---

## Task 2: Replace Embedder

**Files:**
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/embedder.py`

- [ ] **Step 1: Write the test first**

Create `memory_orchestrator_server/src/memory_orchestrator_server/tests/unit/test_embedder.py`:

```python
from unittest.mock import MagicMock, patch
import pytest


def _make_fake_model(dim: int = 1024):
    import numpy as np
    model = MagicMock()
    def fake_encode(texts, batch_size=1, **kw):
        return {"dense_vecs": np.zeros((len(texts), dim), dtype=float)}
    model.encode.side_effect = fake_encode
    return model


def test_embed_sync_returns_1024_dim():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model()):
        from memory_orchestrator_server.embedder import _embed_sync
        result = _embed_sync("hello world")
    assert len(result) == 1024
    assert isinstance(result[0], float)


def test_embed_batch_returns_list_of_vectors():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model()):
        from memory_orchestrator_server.embedder import _embed_batch_sync
        result = _embed_batch_sync(["hello", "world"])
    assert len(result) == 2
    assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_embed_one_is_async():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model()):
        from memory_orchestrator_server import embedder
        result = await embedder.embed_one("test")
    assert len(result) == 1024
```

- [ ] **Step 2: Run test — expect import failure because embedder still uses fastembed**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/test_embedder.py -v
```

Expected: FAIL (ImportError on `fastembed` or assertion error on dim 512)

- [ ] **Step 3: Replace embedder.py**

```python
from __future__ import annotations
import asyncio
from functools import lru_cache


@lru_cache(maxsize=1)
def _model():
    from FlagEmbedding import BGEM3FlagModel
    from memory_orchestrator_server.config import get_settings
    return BGEM3FlagModel(get_settings().embed_model, use_fp16=True)


async def embed_one(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_sync, text)


def _embed_sync(text: str) -> list[float]:
    vecs = _model().encode([text], batch_size=1)["dense_vecs"]
    return vecs[0].tolist()


async def embed_batch(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_batch_sync, texts)


def _embed_batch_sync(texts: list[str]) -> list[list[float]]:
    vecs = _model().encode(texts, batch_size=32)["dense_vecs"]
    return [v.tolist() for v in vecs]


def ensure_loaded() -> None:
    _model()
    _embed_sync("probe")
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/test_embedder.py -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd memory_orchestrator_server
git add src/memory_orchestrator_server/embedder.py src/memory_orchestrator_server/tests/unit/test_embedder.py
git commit -m "feat: replace FastEmbed with FlagEmbedding BGEM3FlagModel"
```

---

## Task 3: Create Reranker Module

**Files:**
- Create: `memory_orchestrator_server/src/memory_orchestrator_server/reranker.py`
- Create: `memory_orchestrator_server/src/memory_orchestrator_server/tests/unit/test_reranker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_reranker.py
from unittest.mock import MagicMock, patch


def _make_fake_reranker(scores: list[float]):
    r = MagicMock()
    r.compute_score.return_value = scores
    return r


def test_rerank_scores_returns_scores_per_text():
    fake = _make_fake_reranker([0.9, 0.3, 0.7])
    with patch("memory_orchestrator_server.reranker._reranker", return_value=fake):
        from memory_orchestrator_server.reranker import rerank_scores
        scores = rerank_scores("my query", ["text a", "text b", "text c"])
    assert len(scores) == 3
    assert scores[0] == 0.9
    assert scores[1] == 0.3
    assert scores[2] == 0.7


def test_rerank_scores_handles_single_text():
    # FlagReranker.compute_score can return a float for single input
    fake = _make_fake_reranker(0.85)  # scalar, not list
    with patch("memory_orchestrator_server.reranker._reranker", return_value=fake):
        from memory_orchestrator_server.reranker import rerank_scores
        scores = rerank_scores("query", ["only text"])
    assert scores == [0.85]


def test_ensure_loaded_calls_reranker():
    fake = _make_fake_reranker([])
    with patch("memory_orchestrator_server.reranker._reranker", return_value=fake):
        from memory_orchestrator_server.reranker import ensure_loaded
        ensure_loaded()  # must not raise
```

- [ ] **Step 2: Run test — expect ImportError (module doesn't exist yet)**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/test_reranker.py -v
```

Expected: FAIL (ModuleNotFoundError: No module named 'memory_orchestrator_server.reranker')

- [ ] **Step 3: Create reranker.py**

```python
from __future__ import annotations
from functools import lru_cache


@lru_cache(maxsize=1)
def _reranker():
    from FlagEmbedding import FlagReranker
    from memory_orchestrator_server.config import get_settings
    return FlagReranker(get_settings().rerank_model, use_fp16=True)


def rerank_scores(query: str, texts: list[str]) -> list[float]:
    """Score (query, text) pairs. Returns scores in same order as texts."""
    if not texts:
        return []
    pairs = [(query, t) for t in texts]
    scores = _reranker().compute_score(pairs, normalize=True)
    if isinstance(scores, (int, float)):
        return [float(scores)]
    return [float(s) for s in scores]


def ensure_loaded() -> None:
    _reranker()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/test_reranker.py -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd memory_orchestrator_server
git add src/memory_orchestrator_server/reranker.py src/memory_orchestrator_server/tests/unit/test_reranker.py
git commit -m "feat: add reranker module with FlagReranker"
```

---

## Task 4: Alembic Migration — vector(512) → vector(1024) + Default Settings

**Files:**
- Create: `memory_orchestrator_server/src/memory_orchestrator_server/alembic/versions/0006_embed_dim_1024.py`

- [ ] **Step 1: Create migration file**

```python
# memory_orchestrator_server/src/memory_orchestrator_server/alembic/versions/0006_embed_dim_1024.py
"""Change embedding column to vector(1024) and add rerank system_settings

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop HNSW index (required before altering column type)
    op.execute("DROP INDEX IF EXISTS memories_embedding_idx")

    # 2. Set all existing embeddings to NULL (512-dim vectors can't be cast to 1024-dim)
    op.execute("UPDATE memories SET embedding = NULL")

    # 3. Alter column to new dimension
    op.execute("ALTER TABLE memories ALTER COLUMN embedding TYPE vector(1024)")

    # 4. Recreate HNSW index for the new dimension
    op.execute(
        "CREATE INDEX memories_embedding_idx ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # 5. Insert default system_settings (skip if already present)
    op.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES
            ('embed_model', 'BAAI/bge-m3', now()),
            ('embed_dim', '1024', now()),
            ('rerank_enabled', 'true', now()),
            ('rerank_model', 'BAAI/bge-reranker-v2-m3', now())
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("UPDATE system_settings SET value = '512' WHERE key = 'embed_dim'")
    op.execute("DELETE FROM system_settings WHERE key IN ('rerank_enabled', 'rerank_model')")
    op.execute("DROP INDEX IF EXISTS memories_embedding_idx")
    op.execute("UPDATE memories SET embedding = NULL")
    op.execute("ALTER TABLE memories ALTER COLUMN embedding TYPE vector(512)")
    op.execute(
        "CREATE INDEX memories_embedding_idx ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )
```

- [ ] **Step 2: Apply migration to the development database**

```bash
cd memory_orchestrator_server
uv run alembic upgrade head
```

Expected: Migration 0006 runs successfully. Output shows "Running upgrade 0005 -> 0006".

- [ ] **Step 3: Verify column type changed**

```bash
cd memory_orchestrator_server
uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from memory_orchestrator_server.config import get_settings

async def check():
    eng = create_async_engine(get_settings().db_dsn)
    async with eng.connect() as c:
        r = await c.execute(__import__('sqlalchemy').text(
            \"SELECT data_type, udt_name FROM information_schema.columns \"
            \"WHERE table_name='memories' AND column_name='embedding'\"
        ))
        print(r.fetchone())
    await eng.dispose()

asyncio.run(check())
"
```

Expected: output shows `udt_name='vector'` and the dimension is now 1024.

- [ ] **Step 4: Commit**

```bash
cd memory_orchestrator_server
git add src/memory_orchestrator_server/alembic/versions/0006_embed_dim_1024.py
git commit -m "feat: migration 0006 — vector(512)→(1024), add rerank system_settings"
```

---

## Task 5: Update repository.search() for Reranking

**Files:**
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/repository.py`
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/tests/integration/test_repository.py`

- [ ] **Step 1: Add missing imports to test_repository.py**

At the top of `tests/integration/test_repository.py`, add:

```python
from unittest.mock import AsyncMock, patch
```

- [ ] **Step 2: Update ALL existing vector fixtures in test_repository.py from 512-dim to 1024-dim**

In `tests/integration/test_repository.py`, find and replace every occurrence of the vector patterns:

```python
# BEFORE (512-dim):
v1 = [1.0] + [0.0] * 511
v2 = [0.0, 1.0] + [0.0] * 510
v = [1.0] + [0.0] * 511
v1_near = [1.0, 0.3] + [0.0] * 510
orthogonal = [0.0, 1.0] + [0.0] * 510

# AFTER (1024-dim):
v1 = [1.0] + [0.0] * 1023
v2 = [0.0, 1.0] + [0.0] * 1022
v = [1.0] + [0.0] * 1023
v1_near = [1.0, 0.3] + [0.0] * 1022
orthogonal = [0.0, 1.0] + [0.0] * 1022
```

- [ ] **Step 3: Add reranking test to test_repository.py**

Append to `test_repository.py`:

```python
@pytest.mark.asyncio
async def test_vector_search_rerank_changes_order(session):
    """When reranking is enabled, cross-encoder scores override hybrid ordering."""
    from unittest.mock import patch
    repo = MemoryRepository(session)
    v1 = [1.0] + [0.0] * 1023
    v2 = [0.0, 1.0] + [0.0] * 1022
    await repo.save(
        type="user", name="first-cosine", description="best cosine match",
        content="best cosine", project_id="*", source="explicit", embedding=v1,
    )
    await repo.save(
        type="user", name="second-cosine", description="second best cosine",
        content="second best", project_id="*", source="explicit", embedding=v2,
    )
    # Without rerank: first-cosine wins (higher cosine sim to v1)
    hits_no_rerank = await repo.search(
        query_embedding=v1, project_ids=["*"], top_k=2
    )
    assert hits_no_rerank[0].memory.name == "first-cosine"

    # With rerank: mock reranker to prefer second-cosine
    def mock_rerank_scores(query, texts):
        # Reverse order: second text gets higher score
        return [0.1, 0.9]

    with patch("memory_orchestrator_server.repository.reranker") as mock_mod:
        mock_mod.rerank_scores.side_effect = mock_rerank_scores
        # Patch settings to enable rerank
        with patch.object(repo, "get_settings", new=AsyncMock(return_value={"rerank_enabled": "true", "search_top_k": "8"})):
            hits_reranked = await repo.search(
                query_embedding=v1, project_ids=["*"], top_k=2, query="test query"
            )
    assert hits_reranked[0].memory.name == "second-cosine"
```

- [ ] **Step 4: Run existing tests — expect FAIL on dim mismatch**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/integration/test_repository.py -v
```

Expected: FAIL on tests that insert 512-dim vectors into 1024-dim column.

- [ ] **Step 5: Update repository.search() to support reranking**

In `repository.py`, at the top add:

```python
from memory_orchestrator_server import reranker
```

Then modify `search()` to add the `query` parameter and rerank logic. The full updated `search()` method:

```python
async def search(
    self,
    *,
    query_embedding: list[float],
    project_ids: list[ProjectRef],
    types: list[str] | None = None,
    top_k: int = 8,
    record_hits: bool = False,
    query: str | None = None,
) -> list[Hit]:
    resolved_project_ids = await self._resolve_project_refs(project_ids)
    if not resolved_project_ids:
        return []
    distance = Memory.embedding.cosine_distance(query_embedding)
    stmt = (
        select(Memory, distance.label("distance"))
        .where(
            Memory.superseded_by.is_(None),
            Memory.project_id.in_(resolved_project_ids),
            Memory.embedding.isnot(None),
        )
        .order_by(distance)
        .limit(top_k * 3)
    )
    if types:
        stmt = stmt.where(Memory.type.in_(types))
    result = await self.session.execute(stmt)
    rows = result.all()

    hits: list[Hit] = []
    for mem, dist in rows:
        sim = 1.0 - float(dist)
        score = hybrid_score(
            cosine_sim=sim, importance=mem.importance, updated_at=mem.updated_at
        )
        hits.append(Hit(memory=mem, score=score, cosine_sim=sim))
    hits.sort(key=lambda h: -h.score)

    cfg = await self.get_settings()
    if query and cfg.get("rerank_enabled", "false").lower() == "true":
        texts = [
            f"{h.memory.name} {h.memory.description} {h.memory.content}"
            for h in hits
        ]
        scores = reranker.rerank_scores(query, texts)
        hits = [
            Hit(memory=h.memory, score=float(s), cosine_sim=h.cosine_sim)
            for h, s in sorted(zip(hits, scores), key=lambda x: -x[1])
        ]

    hits = hits[:top_k]

    if record_hits and hits:
        ids = [h.memory.id for h in hits]
        await self.session.execute(
            update(Memory)
            .where(Memory.id.in_(ids))
            .values(
                hit_count=Memory.hit_count + 1,
                last_hit_at=utc_now(),
            )
            .execution_options(synchronize_session="fetch")
        )
    return hits
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/integration/test_repository.py -v
```

Expected: all PASS (including new rerank test)

- [ ] **Step 7: Commit**

```bash
cd memory_orchestrator_server
git add src/memory_orchestrator_server/repository.py \
        src/memory_orchestrator_server/tests/integration/test_repository.py
git commit -m "feat: repository.search() supports reranking via query param"
```

---

## Task 6: Wire Startup and Call Sites

**Files:**
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/http_app.py`
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/mcp_core.py`
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/tests/integration/test_mcp_tools.py`

- [ ] **Step 1: Update FAKE_EMB in test_mcp_tools.py from 512-dim to 1024-dim**

In `tests/integration/test_mcp_tools.py`, replace line:

```python
FAKE_EMB = [1.0] + [0.0] * 511
```

with:

```python
FAKE_EMB = [1.0] + [0.0] * 1023
```

- [ ] **Step 2: Run mcp_tools tests — expect FAIL (dim mismatch)**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/integration/test_mcp_tools.py -v
```

Expected: FAIL

- [ ] **Step 3: Update http_app.py to load reranker at startup**

In `http_app.py`, add import at top:

```python
from memory_orchestrator_server.reranker import ensure_loaded as ensure_reranker
```

In the `_startup()` function, after `ensure_embedder()`:

```python
        if not skip_embedder:
            ensure_embedder()
            ensure_reranker()
```

- [ ] **Step 4: Update mcp_core.handle_search_memory to pass query**

In `mcp_core.py`, find `handle_search_memory`. Replace the final search call:

```python
    # BEFORE:
    hits = await repo.search(query_embedding=qvec, project_ids=project_ids, types=types, top_k=top_k, record_hits=True)
    
    # AFTER:
    hits = await repo.search(
        query_embedding=qvec, project_ids=project_ids, types=types,
        top_k=top_k, record_hits=True, query=query,
    )
```

- [ ] **Step 5: Run mcp_tools tests — expect PASS**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/integration/test_mcp_tools.py -v
```

Expected: all PASS

- [ ] **Step 6: Run all unit tests**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/ -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
cd memory_orchestrator_server
git add src/memory_orchestrator_server/http_app.py \
        src/memory_orchestrator_server/mcp_core.py \
        src/memory_orchestrator_server/tests/integration/test_mcp_tools.py
git commit -m "feat: wire reranker at startup; pass query through MCP search"
```

---

## Task 7: Add migrate-embeddings CLI Command

**Files:**
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/cli.py`

- [ ] **Step 1: Add migrate-embeddings command to cli.py**

Add the following command to `cli.py` (after the `doctor` command):

```python
@main.command(name="migrate-embeddings")
@click.option("--batch-size", default=32, show_default=True, help="Memories per embed batch.")
def migrate_embeddings(batch_size: int) -> None:
    """Re-embed all memories using the current embed_model (for dimension changes)."""
    import asyncio
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from memory_orchestrator_server.embedder import embed_batch
    from memory_orchestrator_server.models import Memory, SystemSetting

    _preflight_database()
    settings = get_settings()

    async def _run() -> None:
        engine = create_async_engine(settings.db_dsn)
        maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async with maker() as session:
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == "embed_migration_offset")
            )
            offset_row = result.scalar_one_or_none()
            start_offset = int(offset_row.value) if offset_row else 0

        click.echo(f"Starting from offset {start_offset}")
        total = 0

        async with maker() as session:
            result = await session.execute(
                select(Memory.id, Memory.name, Memory.description, Memory.content)
                .where(Memory.superseded_by.is_(None))
                .order_by(Memory.id)
                .offset(start_offset)
            )
            rows = result.all()

        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            texts = [f"{r.name} {r.description} {r.content}" for r in batch]
            vectors = await embed_batch(texts)

            async with maker() as session:
                for row, vec in zip(batch, vectors):
                    await session.execute(
                        sa_update(Memory).where(Memory.id == row.id).values(embedding=vec)
                    )
                    # track progress
                    await session.merge(
                        SystemSetting(
                            key="embed_migration_offset",
                            value=str(start_offset + i + len(batch)),
                        )
                    )
                await session.commit()

            total += len(batch)
            click.echo(f"  embedded {total} / {len(rows)}")

        # clear offset on success
        async with maker() as session:
            await session.execute(
                sa_update(SystemSetting)
                .where(SystemSetting.key == "embed_migration_offset")
                .values(value="0")
            )
            await session.commit()

        click.echo(f"Done. Re-embedded {total} memories.")
        await engine.dispose()

    asyncio.run(_run())
```

- [ ] **Step 2: Run --help to verify command registered**

```bash
cd memory_orchestrator_server
uv run mo-server migrate-embeddings --help
```

Expected: shows help text with `--batch-size` option.

- [ ] **Step 3: Commit**

```bash
cd memory_orchestrator_server
git add src/memory_orchestrator_server/cli.py
git commit -m "feat: add mo-server migrate-embeddings command"
```

---

## Task 8: Update Package Boundary Test

**Files:**
- Modify: `memory_orchestrator_server/src/memory_orchestrator_server/tests/unit/test_package_boundaries.py`

- [ ] **Step 1: Add FlagEmbedding to MCP forbidden imports**

In `test_package_boundaries.py`, find:

```python
    forbidden = {
        "asyncpg",
        "fastembed",
        "pgvector",
        "sqlalchemy",
        "memory_orchestrator_server.models",
        "memory_orchestrator_server.repository",
        "memory_orchestrator_server.embedder",
    }
```

Replace with:

```python
    forbidden = {
        "asyncpg",
        "fastembed",
        "FlagEmbedding",
        "pgvector",
        "sqlalchemy",
        "torch",
        "memory_orchestrator_server.models",
        "memory_orchestrator_server.repository",
        "memory_orchestrator_server.embedder",
        "memory_orchestrator_server.reranker",
    }
```

- [ ] **Step 2: Run package boundary tests**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/test_package_boundaries.py -v
```

Expected: 2 PASS

- [ ] **Step 3: Run full test suite**

```bash
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/ -v --ignore=src/memory_orchestrator_server/tests/integration/test_http_app.py
```

Expected: all PASS (skip test_http_app if it needs embedder models loaded in-process; integration tests are OK since they mock embed_one)

- [ ] **Step 4: Commit**

```bash
cd memory_orchestrator_server
git add src/memory_orchestrator_server/tests/unit/test_package_boundaries.py
git commit -m "test: add FlagEmbedding to MCP package boundary forbidden imports"
```

---

## Task 9: Run Migration and Restart Server

This task runs the migration on the live development database, downloads models, and verifies the full pipeline end-to-end.

- [ ] **Step 1: Apply migration (if not already done in Task 4)**

```bash
cd memory_orchestrator_server
uv run alembic upgrade head
```

Expected: "Running upgrade 0005 -> 0006" or "Already at head."

- [ ] **Step 2: Stop any running mo-server process**

On Windows PowerShell:
```powershell
Get-Process -Name python | Where-Object { $_.MainWindowTitle -like "*mo-server*" } | Stop-Process
```

Or find and kill the process using port 8765:
```powershell
netstat -ano | findstr :8765
taskkill /PID <PID> /F
```

- [ ] **Step 3: Start mo-server serve-http (this downloads models on first run)**

```bash
cd memory_orchestrator_server
uv run mo-server serve-http
```

Expected first run output (model download):
```
Fetching 10 files: 100%|...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765
```

Wait for "Application startup complete" — model download may take several minutes on first run (~2.2 GB for BGE-M3, ~1.1 GB for reranker). Subsequent starts load from `~/.cache/huggingface/hub/` in seconds.

- [ ] **Step 4: Re-embed all existing memories**

In a separate terminal:
```bash
cd memory_orchestrator_server
uv run mo-server migrate-embeddings
```

Expected:
```
Starting from offset 0
  embedded 32 / N
  embedded 64 / N
  ...
Done. Re-embedded N memories.
```

- [ ] **Step 5: Verify search with reranking works**

```bash
curl "http://localhost:8765/healthz"
```

Expected: `{"db": "ok", "embedder": "ok"}`

```bash
curl -s -X POST "http://localhost:8765/mcp/tools/call" \
  -H "Content-Type: application/json" \
  -d '{"name":"search_memory","arguments":{"query":"project architecture"},"project_slug":"*","cwd":".","client":"claude"}' \
  | python -m json.dumps -
```

Expected: JSON result with `score` fields reflecting reranker output.

- [ ] **Step 6: Final commit**

```bash
cd memory_orchestrator_server
git add -A
git status
# Should be clean
git commit -m "chore: all tests pass with FlagEmbedding + reranker pipeline"
```

---

## Quick Reference: Run All Tests

```bash
# Unit tests (no DB, models mocked)
cd memory_orchestrator_server
uv run pytest src/memory_orchestrator_server/tests/unit/ -v

# Integration tests (needs Postgres on port 5433)
uv run pytest src/memory_orchestrator_server/tests/integration/ -v

# MCP package tests
cd ../memory_orchestrator_mcp
uv run pytest -v
```
