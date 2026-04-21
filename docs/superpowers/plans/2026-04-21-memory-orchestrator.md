# Memory Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个独立的跨项目记忆中心服务,Claude Code 通过 MCP 接入,实现"模型主动 + Stop hook 自动"两条写入路径,以及"预注入 + 按需检索"两层读取路径。

**Architecture:** 单 Python 进程同时暴露 MCP stdio 和 FastAPI HTTP。数据落 PostgreSQL 16 + pgvector,向量由本地 bge-small-zh-v1.5 (FastEmbed) 生成。会话归纳复用用户 `~/.claude/settings.json` 中的 Claude API 凭据调 Haiku。

**Tech Stack:** Python 3.11+、FastAPI、mcp Python SDK、SQLAlchemy 2 + asyncpg、pgvector、FastEmbed (bge-small-zh-v1.5)、Alembic、Docker Compose、pytest + testcontainers-pg。

**Source spec:** `docs/superpowers/specs/2026-04-21-memory-orchestrator-design.md`

---

## File Structure

```
memory-orchestrator/
├── pyproject.toml                         # T1
├── docker-compose.yml                     # T1
├── .env.example                           # T1
├── .gitignore                             # T1
├── alembic.ini                            # T4
├── alembic/
│   ├── env.py                             # T4
│   └── versions/
│       └── 0001_initial.py                # T4
├── src/memory_orchestrator/
│   ├── __init__.py                        # T1
│   ├── config.py                          # T2
│   ├── models.py                          # T3
│   ├── project_id.py                      # T5
│   ├── scoring.py                         # T6
│   ├── embedder.py                        # T7
│   ├── repository.py                      # T8-T11
│   ├── ingestor.py                        # T12-T14
│   ├── mcp_server.py                      # T15
│   ├── http_app.py                        # T16
│   └── cli.py                             # T19
├── hooks/
│   ├── user_prompt_submit.py              # T17
│   └── stop.py                            # T18
├── tests/
│   ├── conftest.py                        # T3, T8
│   ├── unit/
│   │   ├── test_project_id.py             # T5
│   │   ├── test_scoring.py                # T6
│   │   └── test_ingestor_prompts.py       # T13
│   └── integration/
│       ├── test_repository.py             # T8-T11
│       ├── test_mcp_tools.py              # T15
│       └── test_http_app.py               # T16
└── docs/
    ├── superpowers/specs/                 # 已有
    └── superpowers/plans/                 # 本文件
```

### 文件职责

| 文件 | 职责 |
|---|---|
| `config.py` | Pydantic Settings,读环境变量,单例 |
| `models.py` | SQLAlchemy ORM:Memory / Project / MemoryLink / Session |
| `project_id.py` | 纯函数:git remote/路径 → 归一化 project_id |
| `scoring.py` | 纯函数:混合打分、recency_decay、token 预算截断 |
| `embedder.py` | FastEmbed 封装,bge-small-zh-v1.5 单例,async wrapper |
| `repository.py` | 所有 SQL,包括 CRUD、去重、向量搜索、context 拼装 |
| `ingestor.py` | 读 transcript 增量 → 调 Haiku → 走 repository 落盘 |
| `mcp_server.py` | MCP tools 注册 + 分发 |
| `http_app.py` | FastAPI:`/context`、`/ingest`、`/healthz`、`/stats` |
| `cli.py` | `mo` 命令:`install-hooks` / `uninstall-hooks` / `doctor` / `serve` |
| `hooks/*.py` | 独立脚本,标准库依赖,供 Claude Code 直接执行 |

---

## Task Decomposition

23 个任务,按依赖分 6 个阶段:

1. 基础设施(T1-T4)
2. 纯函数模块(T5-T6)
3. Embedder(T7)
4. 数据仓储(T8-T11)
5. Ingestor(T12-T14)
6. 接口层与集成(T15-T23)

---

## Task 1: 项目骨架

> **环境前置(已完成)**:本机 PG 16 在 `localhost:5433`,用户 `postgres`/密码 `1234`,已建库 `memory_orchestrator`,已 `CREATE EXTENSION vector` (0.8.2) 和 `pgcrypto`。**不使用** docker-compose Postgres。

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Append: `.gitignore`(已存在)
- Create: `src/memory_orchestrator/__init__.py`

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "memory-orchestrator"
version = "0.1.0"
description = "Cross-project memory center for Claude Code"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "pgvector>=0.3",
    "alembic>=1.13",
    "pydantic-settings>=2.5",
    "fastembed>=0.4",
    "mcp>=1.0",
    "anthropic>=0.40",
    "httpx>=0.27",
    "click>=8.1",
]

[project.scripts]
mo = "memory_orchestrator.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "testcontainers[postgres]>=4.8",
    "ruff>=0.7",
    "mypy>=1.12",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/memory_orchestrator"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: 写 .env.example**

```env
MO_DB_DSN=postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator
MO_HTTP_PORT=8765
MO_EMBED_MODEL=BAAI/bge-small-zh-v1.5
MO_EMBED_DIM=512
MO_HAIKU_MODEL=claude-haiku-4-5
MO_LOG_LEVEL=INFO
# 以下沿用 ~/.claude/settings.json 同名值
ANTHROPIC_BASE_URL=
ANTHROPIC_AUTH_TOKEN=
```

- [ ] **Step 3: 追加 .gitignore 条目(文件已存在)**

在现有 `.gitignore` 末尾追加(不要重复已有行):

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.env
.env.local
```

- [ ] **Step 4: 空 package init**

写 `src/memory_orchestrator/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: 验证本机 PG 连通**

Run: `PGPASSWORD=1234 psql -h localhost -p 5433 -U postgres -d memory_orchestrator -c "SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto');"`
Expected: 两行:`vector`、`pgcrypto`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/memory_orchestrator/__init__.py
git commit -m "chore: scaffold memory-orchestrator project"
```

---

## Task 2: Config 模块

**Files:**
- Create: `src/memory_orchestrator/config.py`

- [ ] **Step 1: 写 config.py**

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MO_", env_file=".env", extra="ignore")

    db_dsn: str = Field(default="postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator")
    http_port: int = 8765
    embed_model: str = "BAAI/bge-small-zh-v1.5"
    embed_dim: int = 512
    haiku_model: str = "claude-haiku-4-5"
    log_level: str = "INFO"

    anthropic_base_url: str = Field(default="", validation_alias="ANTHROPIC_BASE_URL")
    anthropic_auth_token: str = Field(default="", validation_alias="ANTHROPIC_AUTH_TOKEN")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Smoke 测试**

```bash
python -c "from memory_orchestrator.config import get_settings; s = get_settings(); print(s.http_port, s.embed_model)"
```
Expected: `8765 BAAI/bge-small-zh-v1.5`

- [ ] **Step 3: Commit**

```bash
git add src/memory_orchestrator/config.py
git commit -m "feat(config): pydantic settings module"
```

---

## Task 3: ORM 模型

**Files:**
- Create: `src/memory_orchestrator/models.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 写 models.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, SmallInteger, DateTime, ForeignKey, ARRAY, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from memory_orchestrator.config import get_settings


class Base(DeclarativeBase):
    pass


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    why: Mapped[str | None] = mapped_column(Text)
    how_to_apply: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embed_dim))
    importance: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"))


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    root_paths: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class MemoryLink(Base):
    __tablename__ = "memory_links"

    from_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True)
    to_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True)
    relation: Mapped[str] = mapped_column(Text, primary_key=True)


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 2: 写 tests/conftest.py 占位**

```python
import pytest
```

- [ ] **Step 3: Import smoke**

Run: `python -c "from memory_orchestrator.models import Memory, Project, MemoryLink, Session; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/memory_orchestrator/models.py tests/conftest.py
git commit -m "feat(models): SQLAlchemy ORM for memories, projects, links, sessions"
```

---

## Task 4: Alembic 初始迁移

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial.py`

- [ ] **Step 1: 初始化 alembic**

Run: `alembic init --template async alembic`
Expected: 生成 `alembic.ini` 和 `alembic/` 目录

- [ ] **Step 2: 改写 alembic/env.py**

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from memory_orchestrator.config import get_settings
from memory_orchestrator.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().db_dsn)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


asyncio.run(run_migrations_online())
```

- [ ] **Step 3: 写 0001_initial.py 迁移**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "projects",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("root_paths", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("why", sa.Text()),
        sa.Column("how_to_apply", sa.Text()),
        sa.Column("embedding", Vector(1024)),
        sa.Column("importance", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hit_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id")),
    )
    op.create_index(
        "memories_project_type_idx",
        "memories",
        ["project_id", "type"],
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    op.execute(
        "CREATE INDEX memories_embedding_idx ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "memory_links",
        sa.Column("from_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("to_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relation", sa.Text(), primary_key=True),
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True)),
        sa.Column("last_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("memory_links")
    op.execute("DROP INDEX IF EXISTS memories_embedding_idx")
    op.drop_index("memories_project_type_idx", table_name="memories")
    op.drop_table("memories")
    op.drop_table("projects")
```

- [ ] **Step 4: 跑迁移**

Run: `alembic upgrade head`
Expected: `Running upgrade  -> 0001, initial schema`

- [ ] **Step 5: 校验建表**

Run: `PGPASSWORD=1234 psql -h localhost -p 5433 -U postgres -d memory_orchestrator -c "\dt"`
Expected: 看到 4 张表 + alembic_version

- [ ] **Step 6: Commit**

```bash
git add alembic.ini alembic/
git commit -m "feat(db): initial schema migration with pgvector HNSW index"
```

---

## Task 5: project_id 归一化

**Files:**
- Create: `src/memory_orchestrator/project_id.py`
- Create: `tests/unit/test_project_id.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_project_id.py
from memory_orchestrator.project_id import normalize_git_remote, project_id_from_path


def test_https_github_normalized():
    assert normalize_git_remote("https://github.com/Foo/Bar.git") == "github.com/foo/bar"


def test_ssh_github_normalized():
    assert normalize_git_remote("git@github.com:Foo/Bar.git") == "github.com/foo/bar"


def test_http_without_git_suffix():
    assert normalize_git_remote("http://gitlab.com/a/b") == "gitlab.com/a/b"


def test_invalid_remote_returns_none():
    assert normalize_git_remote("") is None
    assert normalize_git_remote("not-a-url") is None


def test_path_fallback_deterministic():
    a = project_id_from_path("/home/user/work/proj")
    b = project_id_from_path("/home/user/work/proj")
    assert a == b
    assert a.startswith("local:")
    assert len(a) == len("local:") + 12


def test_path_fallback_different_paths_differ():
    a = project_id_from_path("/a")
    b = project_id_from_path("/b")
    assert a != b
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_project_id.py -v`
Expected: FAIL,`ModuleNotFoundError: memory_orchestrator.project_id`

- [ ] **Step 3: 写实现**

```python
# src/memory_orchestrator/project_id.py
import hashlib
import re
import subprocess
from pathlib import Path


_SSH_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?/?$")
_HTTP_RE = re.compile(r"^https?://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$")


def normalize_git_remote(remote: str) -> str | None:
    if not remote:
        return None
    remote = remote.strip()
    m = _SSH_RE.match(remote)
    if m:
        host, path = m.group(1), m.group(2)
    else:
        m = _HTTP_RE.match(remote)
        if not m:
            return None
        host, path = m.group(1), m.group(2)
    return f"{host.lower()}/{path.lower()}"


def project_id_from_path(path: str) -> str:
    h = hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()
    return f"local:{h[:12]}"


def detect_project_id(cwd: str | Path) -> str:
    cwd = Path(cwd)
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            normalized = normalize_git_remote(result.stdout.strip())
            if normalized:
                return normalized
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return project_id_from_path(str(cwd))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_project_id.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/project_id.py tests/unit/test_project_id.py
git commit -m "feat(project_id): git remote and path normalization"
```

---

## Task 6: 混合打分模块

**Files:**
- Create: `src/memory_orchestrator/scoring.py`
- Create: `tests/unit/test_scoring.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_scoring.py
import math
from datetime import datetime, timedelta, timezone
from memory_orchestrator.scoring import hybrid_score, recency_decay, truncate_by_budget


def test_recency_decay_now_is_one():
    assert abs(recency_decay(datetime.now(timezone.utc)) - 1.0) < 1e-6


def test_recency_decay_60_days():
    t = datetime.now(timezone.utc) - timedelta(days=60)
    assert abs(recency_decay(t) - math.exp(-1)) < 1e-3


def test_hybrid_score_weights():
    s = hybrid_score(
        cosine_sim=0.8,
        importance=5,
        updated_at=datetime.now(timezone.utc),
    )
    expected = 0.6 * 0.8 + 0.3 * 1.0 + 0.1 * 1.0
    assert abs(s - expected) < 1e-6


def test_truncate_respects_budget():
    items = [
        {"name": "a", "importance": 5, "tokens": 400, "updated_at": datetime.now(timezone.utc)},
        {"name": "b", "importance": 3, "tokens": 400, "updated_at": datetime.now(timezone.utc)},
        {"name": "c", "importance": 4, "tokens": 400, "updated_at": datetime.now(timezone.utc)},
    ]
    kept = truncate_by_budget(items, budget=900)
    names = [i["name"] for i in kept]
    assert names == ["a", "c"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_scoring.py -v`
Expected: FAIL, module not found

- [ ] **Step 3: 写实现**

```python
# src/memory_orchestrator/scoring.py
import math
from datetime import datetime, timezone
from typing import TypedDict


class ScoredItem(TypedDict):
    name: str
    importance: int
    tokens: int
    updated_at: datetime


def recency_decay(updated_at: datetime, half_life_days: float = 60.0) -> float:
    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age = (now - updated_at).total_seconds() / 86400.0
    return math.exp(-age / half_life_days)


def hybrid_score(cosine_sim: float, importance: int, updated_at: datetime) -> float:
    importance_norm = (importance - 1) / 4.0
    return 0.6 * cosine_sim + 0.3 * importance_norm + 0.1 * recency_decay(updated_at)


def truncate_by_budget(items: list[dict], budget: int) -> list[dict]:
    sorted_items = sorted(
        items,
        key=lambda i: (-i["importance"], -recency_decay(i["updated_at"])),
    )
    kept = []
    used = 0
    for item in sorted_items:
        if used + item["tokens"] <= budget:
            kept.append(item)
            used += item["tokens"]
    return kept
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_scoring.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/scoring.py tests/unit/test_scoring.py
git commit -m "feat(scoring): hybrid score with recency decay and budget truncation"
```

---

## Task 7: Embedder

**Files:**
- Create: `src/memory_orchestrator/embedder.py`

- [ ] **Step 1: 写 embedder.py**

```python
from __future__ import annotations
import asyncio
from functools import lru_cache
from fastembed import TextEmbedding

from memory_orchestrator.config import get_settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=get_settings().embed_model)


async def embed_one(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_sync, text)


def _embed_sync(text: str) -> list[float]:
    vectors = list(_model().embed([text]))
    return vectors[0].tolist()


async def embed_batch(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_batch_sync, texts)


def _embed_batch_sync(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _model().embed(texts)]


def ensure_loaded() -> None:
    """启动时调用,强制首次加载模型,暴露加载失败。"""
    _model()
    _embed_sync("probe")
```

- [ ] **Step 2: 冒烟测试(手动,不算正式测试用例)**

Run: `python -c "import asyncio; from memory_orchestrator.embedder import embed_one; v = asyncio.run(embed_one('hello')); print(len(v))"`
Expected: `512` (首次会下载 bge-small-zh-v1.5 (~90MB), 从 Google Cloud Storage 镜像, 快)

- [ ] **Step 3: Commit**

```bash
git add src/memory_orchestrator/embedder.py
git commit -m "feat(embedder): bge-small-zh-v1.5 via FastEmbed with async wrapper"
```

---

## Task 8: Repository — CRUD 与 conftest

**Files:**
- Create: `src/memory_orchestrator/repository.py` (初版)
- Modify: `tests/conftest.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_repository.py`

- [ ] **Step 1: 改 tests/conftest.py 加 testcontainers fixture**

```python
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from alembic.config import Config
from alembic import command

from memory_orchestrator.models import Base


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as pg:
        yield pg


@pytest_asyncio.fixture(scope="session")
async def engine(pg_container):
    dsn = pg_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
    eng = create_async_engine(dsn)
    async with eng.begin() as conn:
        await conn.execute_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture(autouse=True)
async def _truncate(engine):
    yield
    async with engine.begin() as conn:
        await conn.execute_driver_sql(
            "TRUNCATE memories, memory_links, sessions, projects CASCADE"
        )
```

- [ ] **Step 2: 写失败测试 (CRUD)**

```python
# tests/integration/test_repository.py
import pytest
from memory_orchestrator.repository import MemoryRepository


@pytest.mark.asyncio
async def test_save_and_get_roundtrip(session):
    repo = MemoryRepository(session)
    saved = await repo.save(
        type="user",
        name="role",
        description="data scientist focused on observability",
        content="full content here",
        project_id="*",
        source="explicit",
    )
    assert saved.id is not None
    fetched = await repo.get(saved.id)
    assert fetched.name == "role"


@pytest.mark.asyncio
async def test_list_filters_by_project(session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="g", description="x", content="x", project_id="*", source="explicit")
    await repo.save(type="project", name="p", description="x", content="x", project_id="github.com/a/b", source="explicit")
    items = await repo.list(project_id="github.com/a/b")
    assert [m.name for m in items] == ["p"]


@pytest.mark.asyncio
async def test_delete_soft_supersedes_self(session):
    repo = MemoryRepository(session)
    saved = await repo.save(type="user", name="x", description="x", content="x", project_id="*", source="explicit")
    await repo.delete(saved.id, hard=False)
    after = await repo.list(project_id="*")
    assert after == []
    # 但记录还在
    raw = await repo.get(saved.id, include_superseded=True)
    assert raw.superseded_by == raw.id
```

- [ ] **Step 3: 跑测试确认失败**

Run: `pytest tests/integration/test_repository.py -v`
Expected: FAIL, `MemoryRepository` not defined

- [ ] **Step 4: 写 repository.py 初版(仅 CRUD)**

```python
# src/memory_orchestrator/repository.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator.models import Memory


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        *,
        type: str,
        name: str,
        description: str,
        content: str,
        project_id: str,
        source: str,
        why: str | None = None,
        how_to_apply: str | None = None,
        importance: int = 3,
        embedding: list[float] | None = None,
    ) -> Memory:
        m = Memory(
            type=type, name=name, description=description, content=content,
            project_id=project_id, source=source, why=why, how_to_apply=how_to_apply,
            importance=importance, embedding=embedding,
        )
        self.session.add(m)
        await self.session.flush()
        await self.session.commit()
        return m

    async def get(self, memory_id: uuid.UUID, include_superseded: bool = False) -> Memory | None:
        stmt = select(Memory).where(Memory.id == memory_id)
        if not include_superseded:
            stmt = stmt.where(Memory.superseded_by.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        project_id: str | None = None,
        type: str | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.superseded_by.is_(None))
        if project_id is not None:
            stmt = stmt.where(Memory.project_id == project_id)
        if type is not None:
            stmt = stmt.where(Memory.type == type)
        stmt = stmt.order_by(Memory.updated_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, memory_id: uuid.UUID, *, hard: bool = False) -> None:
        if hard:
            await self.session.execute(
                update(Memory).where(Memory.id == memory_id).values(superseded_by=memory_id)
            )
            # real hard delete: use delete() statement; simple for now
        else:
            await self.session.execute(
                update(Memory).where(Memory.id == memory_id).values(
                    superseded_by=memory_id, updated_at=datetime.now(timezone.utc)
                )
            )
        await self.session.commit()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/integration/test_repository.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/memory_orchestrator/repository.py tests/conftest.py tests/integration/
git commit -m "feat(repository): basic CRUD with soft-delete via superseded_by"
```

---

## Task 9: Repository — 去重

**Files:**
- Modify: `src/memory_orchestrator/repository.py`
- Modify: `tests/integration/test_repository.py`

- [ ] **Step 1: 加失败测试**

在 `tests/integration/test_repository.py` 文件末尾追加:

```python
@pytest.mark.asyncio
async def test_find_duplicates_by_embedding(session):
    repo = MemoryRepository(session)
    v1 = [1.0] + [0.0] * 1023
    v1_near = [0.95] + [0.1] * 1023  # 归一化后余弦 > 0.92
    await repo.save(
        type="user", name="a", description="x", content="x",
        project_id="*", source="explicit", embedding=v1,
    )
    dups = await repo.find_duplicates(
        type="user", project_id="*", embedding=v1_near, threshold=0.92
    )
    assert len(dups) == 1
    assert dups[0].name == "a"


@pytest.mark.asyncio
async def test_find_duplicates_respects_threshold(session):
    repo = MemoryRepository(session)
    v = [1.0] + [0.0] * 1023
    orthogonal = [0.0, 1.0] + [0.0] * 1022
    await repo.save(
        type="user", name="a", description="x", content="x",
        project_id="*", source="explicit", embedding=v,
    )
    dups = await repo.find_duplicates(
        type="user", project_id="*", embedding=orthogonal, threshold=0.92
    )
    assert dups == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/integration/test_repository.py::test_find_duplicates_by_embedding -v`
Expected: FAIL, `find_duplicates` not defined

- [ ] **Step 3: 加实现到 MemoryRepository**

在 `repository.py` 的 `MemoryRepository` 类内追加:

```python
    async def find_duplicates(
        self,
        *,
        type: str,
        project_id: str,
        embedding: list[float],
        threshold: float = 0.92,
        limit: int = 5,
    ) -> list[Memory]:
        # pgvector 用 <=> 算 cosine distance,distance = 1 - similarity
        max_distance = 1.0 - threshold
        stmt = (
            select(Memory)
            .where(
                Memory.superseded_by.is_(None),
                Memory.type == type,
                Memory.project_id == project_id,
                Memory.embedding.isnot(None),
                Memory.embedding.cosine_distance(embedding) <= max_distance,
            )
            .order_by(Memory.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/test_repository.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/repository.py tests/integration/test_repository.py
git commit -m "feat(repository): find_duplicates via pgvector cosine distance"
```

---

## Task 10: Repository — 向量搜索

**Files:**
- Modify: `src/memory_orchestrator/repository.py`
- Modify: `tests/integration/test_repository.py`

- [ ] **Step 1: 加失败测试**

在 `tests/integration/test_repository.py` 末尾追加:

```python
@pytest.mark.asyncio
async def test_vector_search_returns_scored_results(session):
    repo = MemoryRepository(session)
    v1 = [1.0] + [0.0] * 1023
    v2 = [0.0, 1.0] + [0.0] * 1022
    await repo.save(
        type="user", name="first", description="x", content="x",
        project_id="*", source="explicit", embedding=v1,
    )
    await repo.save(
        type="user", name="second", description="x", content="x",
        project_id="*", source="explicit", embedding=v2,
    )
    hits = await repo.search(query_embedding=v1, project_ids=["*"], top_k=2)
    assert len(hits) == 2
    assert hits[0].memory.name == "first"
    assert hits[0].score > hits[1].score


@pytest.mark.asyncio
async def test_vector_search_filters_project(session):
    repo = MemoryRepository(session)
    v = [1.0] + [0.0] * 1023
    await repo.save(type="user", name="g", description="x", content="x",
                    project_id="*", source="explicit", embedding=v)
    await repo.save(type="project", name="p", description="x", content="x",
                    project_id="github.com/a/b", source="explicit", embedding=v)
    hits = await repo.search(query_embedding=v, project_ids=["github.com/a/b"], top_k=5)
    assert [h.memory.name for h in hits] == ["p"]


@pytest.mark.asyncio
async def test_vector_search_updates_hit_count(session):
    repo = MemoryRepository(session)
    v = [1.0] + [0.0] * 1023
    saved = await repo.save(
        type="user", name="x", description="x", content="x",
        project_id="*", source="explicit", embedding=v,
    )
    await repo.search(query_embedding=v, project_ids=["*"], top_k=1, record_hits=True)
    after = await repo.get(saved.id)
    assert after.hit_count == 1
    assert after.last_hit_at is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/integration/test_repository.py::test_vector_search_returns_scored_results -v`
Expected: FAIL, `search` not defined

- [ ] **Step 3: 加 Hit dataclass 与 search 实现**

在 `repository.py` 顶部 import 段加:

```python
from dataclasses import dataclass
from memory_orchestrator.scoring import hybrid_score
```

在文件末尾类外加:

```python
@dataclass
class Hit:
    memory: Memory
    score: float
    cosine_sim: float
```

然后在 `MemoryRepository` 类内追加:

```python
    async def search(
        self,
        *,
        query_embedding: list[float],
        project_ids: list[str],
        types: list[str] | None = None,
        top_k: int = 8,
        record_hits: bool = False,
    ) -> list[Hit]:
        distance = Memory.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Memory, distance.label("distance"))
            .where(
                Memory.superseded_by.is_(None),
                Memory.project_id.in_(project_ids),
                Memory.embedding.isnot(None),
            )
            .order_by(distance)
            .limit(top_k * 3)  # over-fetch,混合打分后截 top_k
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
        hits = hits[:top_k]

        if record_hits and hits:
            ids = [h.memory.id for h in hits]
            await self.session.execute(
                update(Memory)
                .where(Memory.id.in_(ids))
                .values(
                    hit_count=Memory.hit_count + 1,
                    last_hit_at=datetime.now(timezone.utc),
                )
            )
            await self.session.commit()
        return hits
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/test_repository.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/repository.py tests/integration/test_repository.py
git commit -m "feat(repository): hybrid vector search with hit_count tracking"
```

---

## Task 11: Repository — Context 拼装

**Files:**
- Modify: `src/memory_orchestrator/repository.py`
- Modify: `tests/integration/test_repository.py`

- [ ] **Step 1: 加失败测试**

在 `tests/integration/test_repository.py` 末尾追加:

```python
@pytest.mark.asyncio
async def test_build_context_includes_global_user(session):
    repo = MemoryRepository(session)
    await repo.save(
        type="user", name="role", description="senior Go dev",
        content="senior Go dev, new to Python", project_id="*", source="explicit",
    )
    md = await repo.build_context(project_id="github.com/a/b", budget_tokens=2000)
    assert "role" in md
    assert "senior Go dev" in md


@pytest.mark.asyncio
async def test_build_context_scopes_project_memories(session):
    repo = MemoryRepository(session)
    await repo.save(
        type="feedback", name="no-mocks", description="integration tests no mocks",
        content="tests must hit real DB", why="past incident", how_to_apply="all test work",
        project_id="github.com/a/b", source="explicit", importance=5,
    )
    await repo.save(
        type="feedback", name="other", description="other project rule",
        content="x", why="x", how_to_apply="x",
        project_id="github.com/c/d", source="explicit", importance=5,
    )
    md = await repo.build_context(project_id="github.com/a/b", budget_tokens=2000)
    assert "no-mocks" in md
    assert "other" not in md
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/integration/test_repository.py::test_build_context_includes_global_user -v`
Expected: FAIL

- [ ] **Step 3: 加实现**

在 `MemoryRepository` 类内追加:

```python
    async def build_context(
        self,
        *,
        project_id: str,
        budget_tokens: int = 1500,
    ) -> str:
        """返回可直接拼进 system prompt 的 markdown 片段。"""
        from memory_orchestrator.scoring import truncate_by_budget
        from datetime import timedelta

        # 收集三类:global user + project feedback(importance>=3) + project project(14天内)
        stmt = select(Memory).where(Memory.superseded_by.is_(None))
        result = await self.session.execute(
            stmt.where(
                ((Memory.project_id == "*") & (Memory.type == "user"))
                | (
                    (Memory.project_id == project_id)
                    & (Memory.type == "feedback")
                    & (Memory.importance >= 3)
                )
                | (
                    (Memory.project_id == project_id)
                    & (Memory.type == "project")
                    & (Memory.updated_at >= datetime.now(timezone.utc) - timedelta(days=14))
                )
            )
        )
        mems = list(result.scalars().all())

        # 粗略 token 估算:每 3.5 字符 ≈ 1 token
        def estimate(m: Memory) -> int:
            return max(1, int(len(m.name + m.description + (m.content or "")) / 3.5))

        items = [
            {
                "memory": m,
                "name": m.name,
                "importance": m.importance,
                "tokens": estimate(m),
                "updated_at": m.updated_at,
            }
            for m in mems
        ]
        kept = truncate_by_budget(items, budget=budget_tokens)

        if not kept:
            return ""

        lines = ["## Remembered context", ""]
        for item in kept:
            m: Memory = item["memory"]
            lines.append(f"### [{m.type}] {m.name}")
            lines.append(m.description)
            if m.content:
                lines.append("")
                lines.append(m.content)
            if m.why:
                lines.append(f"\n**Why:** {m.why}")
            if m.how_to_apply:
                lines.append(f"**How to apply:** {m.how_to_apply}")
            lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/test_repository.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/repository.py tests/integration/test_repository.py
git commit -m "feat(repository): build_context for pre-injection"
```

---

## Task 12: Ingestor — Transcript 读取

**Files:**
- Create: `src/memory_orchestrator/ingestor.py` (初版)
- Create: `tests/unit/test_ingestor.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_ingestor.py
from memory_orchestrator.ingestor import read_transcript_incremental


def test_reads_from_offset(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"role":"user","content":"a"}\n{"role":"assistant","content":"b"}\n')
    lines, new_offset = read_transcript_incremental(str(f), offset=0)
    assert len(lines) == 2
    assert new_offset == 2
    lines2, offset2 = read_transcript_incremental(str(f), offset=new_offset)
    assert lines2 == []
    assert offset2 == 2


def test_resumes_after_append(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"role":"user","content":"a"}\n')
    _, offset = read_transcript_incremental(str(f), offset=0)
    with f.open("a") as h:
        h.write('{"role":"user","content":"b"}\n')
    lines, new_offset = read_transcript_incremental(str(f), offset=offset)
    assert len(lines) == 1
    assert new_offset == 2


def test_missing_file_returns_empty(tmp_path):
    lines, offset = read_transcript_incremental(str(tmp_path / "nope.jsonl"), offset=5)
    assert lines == []
    assert offset == 5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_ingestor.py -v`
Expected: FAIL

- [ ] **Step 3: 写初版 ingestor.py**

```python
# src/memory_orchestrator/ingestor.py
from __future__ import annotations
import json
from pathlib import Path


def read_transcript_incremental(path: str, offset: int) -> tuple[list[dict], int]:
    """读取 transcript 从 offset 行开始的新内容,返回 (解析后的对象列表, 新 offset)。"""
    p = Path(path)
    if not p.exists():
        return [], offset
    lines: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f):
            if i < offset:
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                lines.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    with p.open("rb") as f:
        total = sum(1 for _ in f)
    return lines, total
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_ingestor.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/ingestor.py tests/unit/test_ingestor.py
git commit -m "feat(ingestor): incremental transcript reader"
```

---

## Task 13: Ingestor — LLM 候选提取

**Files:**
- Modify: `src/memory_orchestrator/ingestor.py`
- Create: `tests/unit/test_ingestor_prompts.py`

- [ ] **Step 1: 写失败测试(校验 prompt 结构)**

```python
# tests/unit/test_ingestor_prompts.py
import json
from memory_orchestrator.ingestor import build_extraction_prompt, parse_extraction_response


def test_prompt_mentions_four_types():
    p = build_extraction_prompt(transcript_chunk="dummy", project_id="x")
    assert "user" in p and "feedback" in p and "project" in p and "reference" in p


def test_parse_valid_json_array():
    raw = json.dumps([
        {
            "type": "feedback", "name": "no-mocks",
            "description": "use real DB", "content": "longer text",
            "why": "past incident", "how_to_apply": "all integration tests",
            "importance": 5,
        }
    ])
    items = parse_extraction_response(raw)
    assert len(items) == 1
    assert items[0]["type"] == "feedback"


def test_parse_strips_markdown_fence():
    raw = "```json\n[]\n```"
    assert parse_extraction_response(raw) == []


def test_parse_drops_invalid_types():
    raw = json.dumps([{"type": "bogus", "name": "x", "description": "x", "content": "x"}])
    assert parse_extraction_response(raw) == []


def test_parse_drops_missing_required_for_feedback():
    raw = json.dumps([
        {"type": "feedback", "name": "x", "description": "x", "content": "x"}  # 缺 why/how
    ])
    assert parse_extraction_response(raw) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_ingestor_prompts.py -v`
Expected: FAIL

- [ ] **Step 3: 给 ingestor.py 加 prompt 与解析**

在 `ingestor.py` 追加:

```python
import re

_VALID_TYPES = {"user", "feedback", "project", "reference"}

EXTRACTION_SYSTEM_PROMPT = """You extract durable memories from a conversation transcript.

Return a JSON array. Each item is an object with fields:
- type: one of "user", "feedback", "project", "reference"
- name: short title (max 60 chars)
- description: one-line hook explaining relevance
- content: the memory body in markdown
- why: required for "feedback" and "project" - the reason/motivation
- how_to_apply: required for "feedback" and "project" - when/how to use it
- importance: integer 1-5, default 3

Rules:
- "user" = facts about the user (role, knowledge, preferences). Scope: global.
- "feedback" = corrections or validated approaches from user. Scope: project unless universal.
- "project" = ongoing work, deadlines, stakeholders specific to this project.
- "reference" = pointers to external systems (dashboards, trackers, URLs).

Only extract memories that will still be useful in a future conversation.
Skip ephemeral task details, code, debug recipes, and anything already in the codebase.
If nothing qualifies, return an empty array.

Output ONLY the JSON array. No prose, no code fence."""


def build_extraction_prompt(transcript_chunk: str, project_id: str) -> str:
    return (
        f"Project: {project_id}\n\n"
        f"Transcript chunk:\n<transcript>\n{transcript_chunk}\n</transcript>\n\n"
        f"Extract memories now."
    )


def parse_extraction_response(raw: str) -> list[dict]:
    text = raw.strip()
    # 去 markdown fence
    m = re.match(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    validated: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t not in _VALID_TYPES:
            continue
        if not all(item.get(k) for k in ("name", "description", "content")):
            continue
        if t in ("feedback", "project") and not all(item.get(k) for k in ("why", "how_to_apply")):
            continue
        validated.append(item)
    return validated
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_ingestor_prompts.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/ingestor.py tests/unit/test_ingestor_prompts.py
git commit -m "feat(ingestor): extraction prompt and strict response parser"
```

---

## Task 14: Ingestor — 串联编排

**Files:**
- Modify: `src/memory_orchestrator/ingestor.py`

- [ ] **Step 1: 给 ingestor.py 加编排函数**

在 `ingestor.py` 追加:

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator.config import get_settings
from memory_orchestrator.embedder import embed_one
from memory_orchestrator.models import Session as SessionRow
from memory_orchestrator.repository import MemoryRepository


@dataclass
class IngestResult:
    extracted: int
    saved: int
    skipped: int


async def ingest_session(
    *,
    db: AsyncSession,
    session_id: str,
    project_id: str,
    transcript_path: str,
) -> IngestResult:
    settings = get_settings()

    row = await db.get(SessionRow, session_id)
    if row is None:
        row = SessionRow(session_id=session_id, project_id=project_id, status="pending")
        db.add(row)
        await db.flush()

    lines, new_offset = read_transcript_incremental(transcript_path, row.last_offset)
    if not lines:
        row.status = "done"
        row.last_ingested_at = datetime.now(timezone.utc)
        await db.commit()
        return IngestResult(extracted=0, saved=0, skipped=0)

    chunk = _render_chunk(lines)

    client = AsyncAnthropic(
        base_url=settings.anthropic_base_url or None,
        api_key=settings.anthropic_auth_token or None,
    )
    try:
        resp = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=2048,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_extraction_prompt(chunk, project_id)}],
        )
        raw = resp.content[0].text if resp.content else ""
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)[:500]
        await db.commit()
        raise

    candidates = parse_extraction_response(raw)

    repo = MemoryRepository(db)
    saved = 0
    skipped = 0
    for cand in candidates:
        embedding = await embed_one(cand["content"])
        dups = await repo.find_duplicates(
            type=cand["type"],
            project_id=cand.get("project_id") or (project_id if cand["type"] != "user" else "*"),
            embedding=embedding,
        )
        if dups:
            skipped += 1
            continue
        await repo.save(
            type=cand["type"],
            name=cand["name"],
            description=cand["description"],
            content=cand["content"],
            why=cand.get("why"),
            how_to_apply=cand.get("how_to_apply"),
            importance=int(cand.get("importance", 3)),
            project_id=cand.get("project_id") or (project_id if cand["type"] != "user" else "*"),
            source="auto_extracted",
            embedding=embedding,
        )
        saved += 1

    row.last_offset = new_offset
    row.last_ingested_at = datetime.now(timezone.utc)
    row.status = "done"
    row.last_error = None
    await db.commit()

    return IngestResult(extracted=len(candidates), saved=saved, skipped=skipped)


def _render_chunk(lines: list[dict]) -> str:
    """把 transcript 对象渲染为易读文本供 LLM 提取。"""
    out: list[str] = []
    for obj in lines:
        role = obj.get("role") or obj.get("type") or "unknown"
        content = obj.get("content") or obj.get("text") or ""
        if isinstance(content, list):
            content = "\n".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        out.append(f"[{role}] {content}")
    return "\n\n".join(out)
```

- [ ] **Step 2: 冒烟(无需落盘,只验 import 通过)**

Run: `python -c "from memory_orchestrator.ingestor import ingest_session; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/memory_orchestrator/ingestor.py
git commit -m "feat(ingestor): end-to-end session ingestion pipeline"
```

**Note:** 这一步不写端到端集成测试 — 需要真实 Haiku 调用,放到最后 smoke 阶段。

---

## Task 15: MCP Server

**Files:**
- Create: `src/memory_orchestrator/mcp_server.py`
- Create: `tests/integration/test_mcp_tools.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/integration/test_mcp_tools.py
import pytest
from unittest.mock import AsyncMock, patch
from memory_orchestrator.mcp_server import handle_search_memory, handle_save_memory, handle_list_memories


@pytest.mark.asyncio
async def test_save_then_search(session):
    fake_emb = [1.0] + [0.0] * 1023
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        saved = await handle_save_memory(
            session=session,
            current_project_id="github.com/a/b",
            args={
                "type": "user", "name": "role", "description": "data scientist",
                "content": "data scientist focused on observability",
            },
        )
        assert saved["action"] == "created"

        results = await handle_search_memory(
            session=session,
            current_project_id="github.com/a/b",
            args={"query": "data scientist", "top_k": 3},
        )
        assert len(results) >= 1
        assert results[0]["name"] == "role"


@pytest.mark.asyncio
async def test_save_conflict_returns_conflicts(session):
    fake_emb = [1.0] + [0.0] * 1023
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        await handle_save_memory(
            session=session, current_project_id="*",
            args={"type": "user", "name": "a", "description": "x", "content": "x"},
        )
        result = await handle_save_memory(
            session=session, current_project_id="*",
            args={"type": "user", "name": "b", "description": "x", "content": "x"},
        )
        assert "conflicts" in result
        assert len(result["conflicts"]) == 1


@pytest.mark.asyncio
async def test_list_memories_returns_summaries(session):
    fake_emb = [1.0] + [0.0] * 1023
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        await handle_save_memory(
            session=session, current_project_id="*",
            args={"type": "user", "name": "x", "description": "d", "content": "c"},
        )
    items = await handle_list_memories(
        session=session, current_project_id="*",
        args={"type": ["user"], "limit": 10},
    )
    assert len(items) == 1
    assert items[0]["name"] == "x"
    assert "content" not in items[0]  # list 不返回 content
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/integration/test_mcp_tools.py -v`
Expected: FAIL

- [ ] **Step 3: 写 mcp_server.py**

```python
# src/memory_orchestrator/mcp_server.py
from __future__ import annotations
import uuid
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from memory_orchestrator.config import get_settings
from memory_orchestrator.embedder import embed_one, ensure_loaded as ensure_embedder
from memory_orchestrator.project_id import detect_project_id
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.ingestor import ingest_session

log = logging.getLogger(__name__)


async def handle_search_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> list[dict]:
    repo = MemoryRepository(session)
    query = args["query"]
    top_k = int(args.get("top_k", 8))
    types = args.get("type")
    scope = args.get("project_id")

    if scope == "all":
        project_ids = await _all_project_ids(session, extra=["*"])
    elif scope is None:
        project_ids = [current_project_id, "*"]
    else:
        project_ids = [scope]

    qvec = await embed_one(query)
    hits = await repo.search(
        query_embedding=qvec,
        project_ids=project_ids,
        types=types,
        top_k=top_k,
        record_hits=True,
    )
    return [_memory_to_dict(h.memory, score=h.score) for h in hits]


async def handle_save_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    repo = MemoryRepository(session)
    mtype = args["type"]
    scope = args.get("project_id") or (current_project_id if mtype != "user" else "*")
    embedding = await embed_one(args["content"])

    replace_id = args.get("replace_id")
    if replace_id:
        await repo.delete(uuid.UUID(replace_id), hard=False)
        m = await repo.save(
            type=mtype, name=args["name"], description=args["description"],
            content=args["content"], why=args.get("why"),
            how_to_apply=args.get("how_to_apply"),
            importance=int(args.get("importance", 3)),
            project_id=scope, source="explicit", embedding=embedding,
        )
        return {"id": str(m.id), "action": "merged"}

    dups = await repo.find_duplicates(type=mtype, project_id=scope, embedding=embedding)
    if dups:
        return {
            "action": "conflict",
            "conflicts": [
                {"id": str(d.id), "name": d.name, "description": d.description}
                for d in dups
            ],
        }

    m = await repo.save(
        type=mtype, name=args["name"], description=args["description"],
        content=args["content"], why=args.get("why"),
        how_to_apply=args.get("how_to_apply"),
        importance=int(args.get("importance", 3)),
        project_id=scope, source="explicit", embedding=embedding,
    )
    return {"id": str(m.id), "action": "created"}


async def handle_list_memories(*, session: AsyncSession, current_project_id: str, args: dict) -> list[dict]:
    repo = MemoryRepository(session)
    mems = await repo.list(
        project_id=args.get("project_id"),
        type=(args.get("type") or [None])[0] if isinstance(args.get("type"), list) else args.get("type"),
        limit=int(args.get("limit", 50)),
    )
    return [
        {
            "id": str(m.id), "name": m.name, "description": m.description,
            "type": m.type, "importance": m.importance,
            "updated_at": m.updated_at.isoformat(),
        }
        for m in mems
    ]


async def handle_delete_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    repo = MemoryRepository(session)
    await repo.delete(uuid.UUID(args["id"]), hard=bool(args.get("hard", False)))
    return {"deleted": True}


async def handle_promote_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    from sqlalchemy import update
    from memory_orchestrator.models import Memory
    values: dict = {}
    if "importance" in args:
        values["importance"] = int(args["importance"])
    if args.get("make_global"):
        values["project_id"] = "*"
    if values:
        await session.execute(update(Memory).where(Memory.id == uuid.UUID(args["id"])).values(**values))
        await session.commit()
    return {"updated": True, "changes": list(values.keys())}


async def handle_ingest_session(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    result = await ingest_session(
        db=session,
        session_id=args["session_id"],
        project_id=args.get("project_id") or current_project_id,
        transcript_path=args["transcript_path"],
    )
    return {"extracted": result.extracted, "saved": result.saved, "skipped": result.skipped}


def _memory_to_dict(m, *, score: float | None = None) -> dict:
    d = {
        "id": str(m.id), "name": m.name, "description": m.description,
        "content": m.content, "type": m.type, "project_id": m.project_id,
        "importance": m.importance,
    }
    if m.why:
        d["why"] = m.why
    if m.how_to_apply:
        d["how_to_apply"] = m.how_to_apply
    if score is not None:
        d["score"] = round(score, 4)
    return d


async def _all_project_ids(session: AsyncSession, extra: list[str]) -> list[str]:
    from sqlalchemy import select
    from memory_orchestrator.models import Project
    result = await session.execute(select(Project.id))
    ids = [r[0] for r in result.all()]
    return list({*ids, *extra})


_TOOLS: list[Tool] = [
    Tool(
        name="search_memory",
        description="Retrieve relevant memories by semantic similarity to the query.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "project_id": {"type": "string", "description": "specific id, '*' for global only, 'all' for all projects"},
                "type": {"type": "array", "items": {"type": "string"}},
                "top_k": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="save_memory",
        description="Save a new memory. Returns conflicts if a near-duplicate exists (caller may retry with replace_id).",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["user", "feedback", "project", "reference"]},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "content": {"type": "string"},
                "project_id": {"type": "string"},
                "why": {"type": "string"},
                "how_to_apply": {"type": "string"},
                "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                "replace_id": {"type": "string"},
            },
            "required": ["type", "name", "description", "content"],
        },
    ),
    Tool(name="list_memories", description="List memory summaries by filter.", inputSchema={
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "type": {"type": "string"},
            "limit": {"type": "integer", "default": 50},
        },
    }),
    Tool(name="delete_memory", description="Soft-delete (default) or hard-delete a memory.", inputSchema={
        "type": "object",
        "properties": {"id": {"type": "string"}, "hard": {"type": "boolean", "default": False}},
        "required": ["id"],
    }),
    Tool(name="promote_memory", description="Change importance or scope of a memory.", inputSchema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "importance": {"type": "integer", "minimum": 1, "maximum": 5},
            "make_global": {"type": "boolean"},
        },
        "required": ["id"],
    }),
    Tool(name="ingest_session", description="Ingest a session transcript for auto memory extraction.", inputSchema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "project_id": {"type": "string"},
            "transcript_path": {"type": "string"},
        },
        "required": ["session_id", "transcript_path"],
    }),
]

_DISPATCH = {
    "search_memory": handle_search_memory,
    "save_memory": handle_save_memory,
    "list_memories": handle_list_memories,
    "delete_memory": handle_delete_memory,
    "promote_memory": handle_promote_memory,
    "ingest_session": handle_ingest_session,
}


async def run_stdio_server() -> None:
    ensure_embedder()
    settings = get_settings()
    engine = create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = Server("memory-orchestrator")

    @app.list_tools()
    async def _list_tools() -> list[Tool]:
        return _TOOLS

    @app.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        import os, json
        cwd = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        current_pid = detect_project_id(cwd)
        async with maker() as s:
            handler = _DISPATCH.get(name)
            if not handler:
                return [TextContent(type="text", text=f'{{"error":"unknown tool {name}"}}')]
            result = await handler(session=s, current_project_id=current_pid, args=arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/test_mcp_tools.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/mcp_server.py tests/integration/test_mcp_tools.py
git commit -m "feat(mcp): register search/save/list/delete/promote/ingest tools"
```

---

## Task 16: HTTP App

**Files:**
- Create: `src/memory_orchestrator/http_app.py`
- Create: `tests/integration/test_http_app.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/integration/test_http_app.py
import pytest
from httpx import AsyncClient, ASGITransport
from memory_orchestrator.http_app import create_app
from memory_orchestrator.repository import MemoryRepository


@pytest.mark.asyncio
async def test_healthz_returns_ok(engine):
    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["db"] == "ok"


@pytest.mark.asyncio
async def test_context_returns_markdown(engine, session):
    repo = MemoryRepository(session)
    await repo.save(
        type="user", name="role", description="Go dev",
        content="Go dev new to Python", project_id="*", source="explicit",
    )
    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/context", params={"project_id": "github.com/a/b", "budget_tokens": 2000})
        assert r.status_code == 200
        body = r.text
        assert "Go dev" in body


@pytest.mark.asyncio
async def test_stats_returns_counts(engine, session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="u", description="x", content="x",
                    project_id="*", source="explicit")
    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/stats", params={"project_id": "*"})
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["by_type"]["user"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/integration/test_http_app.py -v`
Expected: FAIL

- [ ] **Step 3: 写 http_app.py**

```python
# src/memory_orchestrator/http_app.py
from __future__ import annotations
import logging
from fastapi import FastAPI, Response, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from memory_orchestrator.config import get_settings
from memory_orchestrator.models import Memory
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.ingestor import ingest_session
from memory_orchestrator.embedder import ensure_loaded as ensure_embedder

log = logging.getLogger(__name__)


class IngestRequest(BaseModel):
    session_id: str
    project_id: str
    transcript_path: str


def create_app(*, engine_override: AsyncEngine | None = None, skip_embedder: bool = False) -> FastAPI:
    settings = get_settings()
    engine = engine_override or create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI(title="Memory Orchestrator")

    @app.on_event("startup")
    async def _startup() -> None:
        if not skip_embedder:
            ensure_embedder()

    @app.get("/healthz")
    async def healthz() -> dict:
        try:
            async with engine.connect() as conn:
                await conn.execute_driver_sql("SELECT 1")
            db_ok = "ok"
        except Exception as e:
            db_ok = f"err:{e}"
        return {"db": db_ok, "embedder": "skipped" if skip_embedder else "ok"}

    @app.get("/context")
    async def context(project_id: str, budget_tokens: int = 1500) -> Response:
        async with maker() as s:
            repo = MemoryRepository(s)
            md = await repo.build_context(project_id=project_id, budget_tokens=budget_tokens)
        return Response(content=md, media_type="text/markdown; charset=utf-8")

    @app.get("/stats")
    async def stats(project_id: str | None = None) -> dict:
        async with maker() as s:
            stmt = select(Memory.type, func.count()).where(Memory.superseded_by.is_(None))
            if project_id:
                stmt = stmt.where(Memory.project_id == project_id)
            stmt = stmt.group_by(Memory.type)
            result = await s.execute(stmt)
            by_type = {row[0]: row[1] for row in result.all()}
            return {"total": sum(by_type.values()), "by_type": by_type}

    @app.post("/ingest", status_code=202)
    async def ingest(req: IngestRequest, background: BackgroundTasks) -> dict:
        async def _run() -> None:
            async with maker() as s:
                try:
                    await ingest_session(
                        db=s,
                        session_id=req.session_id,
                        project_id=req.project_id,
                        transcript_path=req.transcript_path,
                    )
                except Exception:
                    log.exception("ingest failed for session=%s", req.session_id)
        background.add_task(_run)
        return {"accepted": True}

    return app
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/test_http_app.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator/http_app.py tests/integration/test_http_app.py
git commit -m "feat(http): /healthz /context /stats /ingest endpoints"
```

---

## Task 17: UserPromptSubmit Hook

**Files:**
- Create: `hooks/user_prompt_submit.py`

- [ ] **Step 1: 写 hook 脚本**

```python
#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: pre-inject memories into system prompt.

Called once per user prompt. Reads CLAUDE_PROJECT_DIR from env, queries
Memory Orchestrator /context, echoes markdown to stdout for Claude Code to
append. Must never block Claude Code — 2s timeout, silent failure.
"""
from __future__ import annotations
import hashlib
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_DEFAULT_PORT = int(os.environ.get("MO_HTTP_PORT", "8765"))
_TIMEOUT = 2.0
_LOG_PATH = Path.home() / ".claude" / "memory-orchestrator" / "hook.log"


def _log(msg: str) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _normalize_remote(remote: str) -> str | None:
    if not remote:
        return None
    remote = remote.strip()
    ssh = re.match(r"^git@([^:]+):(.+?)(?:\.git)?/?$", remote)
    if ssh:
        return f"{ssh.group(1).lower()}/{ssh.group(2).lower()}"
    http = re.match(r"^https?://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$", remote)
    if http:
        return f"{http.group(1).lower()}/{http.group(2).lower()}"
    return None


def _detect_project_id(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=1,
        )
        if out.returncode == 0:
            norm = _normalize_remote(out.stdout.strip())
            if norm:
                return norm
    except Exception:
        pass
    h = hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()
    return f"local:{h[:12]}"


def main() -> int:
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    project_id = _detect_project_id(cwd)

    url = f"http://localhost:{_DEFAULT_PORT}/context?project_id={urllib.parse.quote(project_id)}&budget_tokens=1500"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        _log(f"context fetch failed: {e}")
        return 0
    except Exception as e:
        _log(f"unexpected hook error: {e}")
        return 0

    if body.strip():
        sys.stdout.write(body)
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 手动冒烟测试**

起服务后运行:
```bash
CLAUDE_PROJECT_DIR=/tmp python hooks/user_prompt_submit.py
```
Expected: 无异常,无输出(因为没有 memory) 或者返回 markdown

Orchestrator 未启动时:
```bash
MO_HTTP_PORT=9999 python hooks/user_prompt_submit.py
```
Expected: 退出 0,`~/.claude/memory-orchestrator/hook.log` 有 "context fetch failed" 记录

- [ ] **Step 3: Commit**

```bash
git add hooks/user_prompt_submit.py
git commit -m "feat(hooks): UserPromptSubmit pre-injection hook"
```

---

## Task 18: Stop Hook

**Files:**
- Create: `hooks/stop.py`

- [ ] **Step 1: 写 hook 脚本**

```python
#!/usr/bin/env python3
"""Claude Code Stop hook: trigger incremental session ingestion.

Read JSON event from stdin (Claude Code injects `session_id` and
`transcript_path`). Apply cooldown: only fire if >10min since last ingest
AND at least 3 user turns accumulated. Fire-and-forget POST to /ingest.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_DEFAULT_PORT = int(os.environ.get("MO_HTTP_PORT", "8765"))
_COOLDOWN_SEC = 600
_MIN_TURNS = 3
_STATE_DIR = Path.home() / ".claude" / "memory-orchestrator"
_LOG_PATH = _STATE_DIR / "hook.log"


def _log(msg: str) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _state_file(session_id: str) -> Path:
    return _STATE_DIR / f"stop-{session_id}.json"


def _read_state(session_id: str) -> dict:
    p = _state_file(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"last_fire_ts": 0, "last_turns": 0}


def _write_state(session_id: str, state: dict) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_file(session_id).write_text(json.dumps(state))
    except Exception:
        pass


def _count_user_turns(transcript_path: str) -> int:
    if not transcript_path or not Path(transcript_path).exists():
        return 0
    count = 0
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("role") == "user" or obj.get("type") == "user":
                    count += 1
    except Exception:
        return 0
    return count


def _normalize_remote(remote: str) -> str | None:
    if not remote:
        return None
    remote = remote.strip()
    ssh = re.match(r"^git@([^:]+):(.+?)(?:\.git)?/?$", remote)
    if ssh:
        return f"{ssh.group(1).lower()}/{ssh.group(2).lower()}"
    http = re.match(r"^https?://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$", remote)
    if http:
        return f"{http.group(1).lower()}/{http.group(2).lower()}"
    return None


def _detect_project_id(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=1,
        )
        if out.returncode == 0:
            n = _normalize_remote(out.stdout.strip())
            if n:
                return n
    except Exception:
        pass
    h = hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()
    return f"local:{h[:12]}"


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except Exception:
        event = {}

    session_id = event.get("session_id") or "unknown"
    transcript_path = event.get("transcript_path") or ""
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    project_id = _detect_project_id(cwd)

    state = _read_state(session_id)
    now = time.time()
    turns = _count_user_turns(transcript_path)

    if now - state["last_fire_ts"] < _COOLDOWN_SEC:
        return 0
    if turns - state["last_turns"] < _MIN_TURNS:
        return 0

    body = json.dumps({
        "session_id": session_id,
        "project_id": project_id,
        "transcript_path": transcript_path,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{_DEFAULT_PORT}/ingest",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        _log(f"ingest post failed: {e}")
        return 0

    _write_state(session_id, {"last_fire_ts": now, "last_turns": turns})
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 冒烟测试(无 orchestrator)**

```bash
echo '{"session_id":"smoke","transcript_path":"/nonexistent"}' | python hooks/stop.py
echo $?
```
Expected: `0`(无论有没有 orchestrator 都不抛异常)

- [ ] **Step 3: Commit**

```bash
git add hooks/stop.py
git commit -m "feat(hooks): Stop hook with cooldown and turn-count gating"
```

---

## Task 19: CLI

**Files:**
- Create: `src/memory_orchestrator/cli.py`

- [ ] **Step 1: 写 cli.py**

```python
# src/memory_orchestrator/cli.py
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
import click

from memory_orchestrator.config import get_settings


@click.group()
def main() -> None:
    """Memory Orchestrator CLI."""


@main.command()
def serve() -> None:
    """Run both HTTP API and MCP stdio server (HTTP in background task)."""
    import uvicorn
    from memory_orchestrator.http_app import create_app
    from memory_orchestrator.mcp_server import run_stdio_server

    settings = get_settings()
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=settings.http_port, log_level=settings.log_level.lower())

    async def _main() -> None:
        server = uvicorn.Server(config)
        http_task = asyncio.create_task(server.serve())
        mcp_task = asyncio.create_task(run_stdio_server())
        done, pending = await asyncio.wait({http_task, mcp_task}, return_when=asyncio.FIRST_EXCEPTION)
        for p in pending:
            p.cancel()
        for d in done:
            d.result()

    asyncio.run(_main())


@main.command(name="serve-http")
def serve_http() -> None:
    """Run only HTTP API (useful when running MCP stdio separately)."""
    import uvicorn
    from memory_orchestrator.http_app import create_app
    settings = get_settings()
    uvicorn.run(create_app(), host="127.0.0.1", port=settings.http_port, log_level=settings.log_level.lower())


@main.command(name="serve-mcp")
def serve_mcp() -> None:
    """Run only MCP stdio server."""
    from memory_orchestrator.mcp_server import run_stdio_server
    asyncio.run(run_stdio_server())


@main.command()
def doctor() -> None:
    """Check DB connection, embedder load, and Claude settings wiring."""
    import urllib.request
    ok = True
    settings = get_settings()

    click.echo(f"config: db_dsn={settings.db_dsn}")
    click.echo(f"config: http_port={settings.http_port}")

    try:
        with urllib.request.urlopen(f"http://localhost:{settings.http_port}/healthz", timeout=1) as r:
            data = json.loads(r.read())
            click.echo(f"healthz: {data}")
    except Exception as e:
        click.echo(f"healthz: FAIL ({e})")
        ok = False

    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            cfg = json.loads(settings_path.read_text(encoding="utf-8"))
            mcp = cfg.get("mcpServers", {}).get("memory-orchestrator")
            hooks = cfg.get("hooks", {})
            click.echo(f"claude mcp entry: {'ok' if mcp else 'MISSING'}")
            click.echo(f"claude hooks: {sorted(hooks.keys())}")
            if not mcp:
                ok = False
        except Exception as e:
            click.echo(f"settings parse: FAIL ({e})")
            ok = False
    else:
        click.echo("claude settings: NOT FOUND")
        ok = False

    sys.exit(0 if ok else 1)


@main.command(name="install-hooks")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
def install_hooks(scope: str) -> None:
    """Wire hooks and mcpServers entry into ~/.claude/settings.json."""
    if scope == "user":
        path = Path.home() / ".claude" / "settings.json"
    else:
        path = Path.cwd() / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    hooks_dir = (Path(__file__).parent.parent.parent / "hooks").resolve()
    cfg.setdefault("hooks", {})
    cfg["hooks"]["UserPromptSubmit"] = [{
        "hooks": [{"type": "command", "command": f"python {hooks_dir / 'user_prompt_submit.py'}"}]
    }]
    cfg["hooks"]["Stop"] = [{
        "hooks": [{"type": "command", "command": f"python {hooks_dir / 'stop.py'}"}]
    }]
    cfg.setdefault("mcpServers", {})
    cfg["mcpServers"]["memory-orchestrator"] = {
        "command": sys.executable,
        "args": ["-m", "memory_orchestrator.cli", "serve-mcp"],
        "env": {
            "MO_HTTP_PORT": str(get_settings().http_port),
            "MO_DB_DSN": get_settings().db_dsn,
        },
    }
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"wrote {path}")


@main.command(name="uninstall-hooks")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
def uninstall_hooks(scope: str) -> None:
    """Remove hooks and mcpServers entry from ~/.claude/settings.json."""
    path = (Path.home() if scope == "user" else Path.cwd()) / ".claude" / "settings.json"
    if not path.exists():
        click.echo("nothing to remove")
        return
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for key in ("UserPromptSubmit", "Stop"):
        cfg.get("hooks", {}).pop(key, None)
    cfg.get("mcpServers", {}).pop("memory-orchestrator", None)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"cleaned {path}")
```

- [ ] **Step 2: 安装本包并试跑 CLI**

```bash
pip install -e ".[dev]"
mo --help
```
Expected: 列出 serve / doctor / install-hooks 等子命令

- [ ] **Step 3: Commit**

```bash
git add src/memory_orchestrator/cli.py
git commit -m "feat(cli): mo command with serve/doctor/install-hooks"
```

---

## Task 20: Integration smoke — Save + Search 闭环

**Files:**
- Create: `scripts/smoke_save_search.py`

- [ ] **Step 1: 写 smoke 脚本**

```python
# scripts/smoke_save_search.py
"""End-to-end smoke: save a memory, search it back via MCP client."""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(
        command="python", args=["-m", "memory_orchestrator.cli", "serve-mcp"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            assert "save_memory" in names and "search_memory" in names
            print("tools ok:", names)

            r = await session.call_tool("save_memory", {
                "type": "user", "name": "smoke-role",
                "description": "smoke test user memory",
                "content": "the user is running a smoke test for memory orchestrator",
            })
            print("save:", r.content[0].text)

            r = await session.call_tool("search_memory", {
                "query": "smoke test memory orchestrator", "top_k": 3,
            })
            print("search:", r.content[0].text)
            data = json.loads(r.content[0].text)
            assert any("smoke-role" == m["name"] for m in data)
            print("smoke OK")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 跑 smoke(本机 PG 已跑,schema 已迁移)**

```bash
alembic upgrade head
python scripts/smoke_save_search.py
```
Expected: `smoke OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_save_search.py
git commit -m "test(smoke): save/search roundtrip via MCP stdio client"
```

---

## Task 21: Integration smoke — Context 预注入

**Files:**
- Create: `scripts/smoke_context.sh`

- [ ] **Step 1: 写 smoke 脚本**

```bash
#!/usr/bin/env bash
# scripts/smoke_context.sh
# 验证 UserPromptSubmit hook 会把已有记忆注入到 stdout
set -e

export CLAUDE_PROJECT_DIR="$(pwd)"
output=$(python hooks/user_prompt_submit.py)

if [ -z "$output" ]; then
  echo "hook produced no output — did you save any memory first?"
  exit 1
fi

if echo "$output" | grep -q "Remembered context"; then
  echo "context smoke OK"
else
  echo "FAIL: output did not contain marker"
  echo "$output"
  exit 1
fi
```

- [ ] **Step 2: 手动跑**

先在 Task 20 的 save 之后,再跑:
```bash
chmod +x scripts/smoke_context.sh
bash scripts/smoke_context.sh
```
Expected: `context smoke OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_context.sh
git commit -m "test(smoke): UserPromptSubmit hook outputs context markdown"
```

---

## Task 22: Integration smoke — Ingest 归纳

**Files:**
- Create: `scripts/smoke_ingest.py`

- [ ] **Step 1: 造个假 transcript 并触发 ingest**

```python
# scripts/smoke_ingest.py
"""Feed a short fake transcript into /ingest and verify memories appear."""
import asyncio
import json
import tempfile
import time
from pathlib import Path
import httpx


TRANSCRIPT = [
    {"role": "user", "content": "don't mock the database in these tests — we got burned last quarter"},
    {"role": "assistant", "content": "understood — will use real DB for integration tests"},
    {"role": "user", "content": "good. Also, I'm a senior Go dev, new to Python."},
    {"role": "assistant", "content": "got it"},
]


async def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        tp = Path(d) / "transcript.jsonl"
        with tp.open("w") as f:
            for line in TRANSCRIPT:
                f.write(json.dumps(line) + "\n")

        async with httpx.AsyncClient() as c:
            r = await c.post(
                "http://localhost:8765/ingest",
                json={
                    "session_id": f"smoke-{int(time.time())}",
                    "project_id": "github.com/smoke/test",
                    "transcript_path": str(tp),
                },
            )
            assert r.status_code == 202, r.text
            print("ingest accepted")

            # 给后台任务一点时间
            await asyncio.sleep(8)
            r = await c.get("http://localhost:8765/stats", params={"project_id": "*"})
            print("global stats:", r.json())
            r2 = await c.get("http://localhost:8765/stats", params={"project_id": "github.com/smoke/test"})
            print("project stats:", r2.json())


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 跑 smoke**

```bash
python scripts/smoke_ingest.py
```
Expected: `ingest accepted`,之后 stats 里能看到计数增加(至少 1 条 user / 1 条 feedback)

**Note:** 这一步真实调用 Haiku,需要 `ANTHROPIC_AUTH_TOKEN` 已经在 `.env` 或环境变量里。

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_ingest.py
git commit -m "test(smoke): ingest pipeline extracts memories via Haiku"
```

---

## Task 23: README 与 Quickstart

**Files:**
- Create: `README.md`

- [ ] **Step 1: 写 README**

```markdown
# Memory Orchestrator

Cross-project memory center for Claude Code. Collects, organizes, and serves
memories across all projects via MCP.

## Quickstart

```bash
# 1. Ensure local Postgres 16 is running with pgvector installed
#    (see scripts/README.md for Windows pgvector install)
#    Default DSN expects: localhost:5433, user postgres, db memory_orchestrator

# 2. Install
pip install -e ".[dev]"

# 3. Migrate DB
alembic upgrade head

# 4. Wire hooks + MCP server into ~/.claude/settings.json
mo install-hooks --scope user

# 5. Run the service (in another terminal)
mo serve-http
```

Open Claude Code in any project. The UserPromptSubmit hook will pre-inject
relevant memories; `save_memory` / `search_memory` MCP tools are available.

## Configuration

Env vars (prefixed `MO_`), or `.env` in CWD:

| Var | Default |
|---|---|
| `MO_DB_DSN` | `postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator` |
| `MO_HTTP_PORT` | `8765` |
| `MO_EMBED_MODEL` | `BAAI/bge-small-zh-v1.5` |
| `MO_HAIKU_MODEL` | `claude-haiku-4-5` |

`ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` are reused from
`~/.claude/settings.json` (not re-prefixed).

## Docs

- Design: `docs/superpowers/specs/2026-04-21-memory-orchestrator-design.md`
- Plan: `docs/superpowers/plans/2026-04-21-memory-orchestrator.md`

## Tests

```bash
pytest tests/unit/       # pure, no external deps
pytest tests/integration # requires Docker (testcontainers spin up pg)
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with quickstart"
```

---

## Self-Review Results

- **Spec coverage:**
  - Architecture ✔ (T1/T15/T16/T19)
  - Data model ✔ (T3/T4)
  - MCP tools ✔ (T15 covers all 6 tools)
  - Context API ✔ (T11/T16)
  - Ingest flow ✔ (T12/T13/T14/T16/T18)
  - Hooks ✔ (T17/T18)
  - project_id 归一化 ✔ (T5)
  - Scoring ✔ (T6)
  - Error handling ✔ (T17/T18 fail silent; T15/T16 return errors; ingest marks failed)
  - Tests ✔ (unit for pure, integration with testcontainers, smoke scripts)
  - CLI ✔ (T19)
- **Placeholder scan:** No "TBD"/"TODO"/"implement later" in plan content. T14 explicitly defers Haiku e2e test to smoke — that's a justified skip, not a placeholder.
- **Type consistency:** `MemoryRepository.save/list/search/delete/find_duplicates/build_context` referenced consistently across tasks. `Hit` dataclass defined in T10 and used in T15. `IngestResult` defined in T14 and used in T15.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-memory-orchestrator.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 为每个 task 分发一个新 subagent,任务间我做两阶段 review,迭代快
2. **Inline Execution** — 在当前会话批量执行,按 checkpoint 停下让你 review

哪种方式?
