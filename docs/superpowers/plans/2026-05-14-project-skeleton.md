# Project Skeleton Implementation Plan (期 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project skeleton support — manually-created projects with multi-level skeleton trees, memories linkable to skeleton nodes, project-scoped `project_token` auth, skeleton-aware LLM extraction, and a new `SkeletonPage.vue` at `/ui/` as the app home page.

**Architecture:** DB migration adds `project_skeleton_nodes` + `skeleton_node_memories` tables and a `project_id` column on `api_tokens`. Backend adds skeleton CRUD + project CRUD endpoints and a new `project_token` auth kind. Ingestor passes skeleton context to LLM and links extracted memories to nodes. Frontend introduces Vue Router 4: `/ui/` → new `SkeletonPage.vue`, `/ui/memories` → existing `App.vue` (unchanged).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, pydantic-ai, Alembic, pytest-asyncio, Vue 3, Vue Router 4, Vite

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `alembic/versions/0011_project_skeleton.py` | DB migration |
| Modify | `models.py` | 2 new ORM classes; `project_id` on `ApiToken` |
| Modify | `repository.py` | Skeleton CRUD methods + BUILTIN_NODES constant |
| Modify | `auth_tokens.py` | `TOKEN_KIND_PROJECT` + `resolve_project_token()` |
| Modify | `routers/ui.py` | 8 new endpoints; update token creation |
| Modify | `ingestor.py` | `MemoryCandidate` + prompt + node linking |
| Create | `tests/unit/test_skeleton_seed.py` | Seed logic unit tests |
| Create | `tests/unit/test_project_token_auth.py` | Auth unit tests |
| Create | `tests/unit/test_ingestor_skeleton.py` | Ingestor prompt unit tests |
| Create | `tests/integration/test_skeleton_api.py` | API integration tests |
| Modify | `frontend/package.json` | Add `vue-router` |
| Modify | `frontend/src/main.js` | Vue Router setup |
| Create | `frontend/src/api.js` | Shared `apiFetch` for SkeletonPage |
| Create | `frontend/src/SkeletonPage.vue` | New main page at `/ui/` |

All commands run from `memory_orchestrator_server/` unless noted.

---

## Task 1: DB Migration

**Files:**
- Create: `alembic/versions/0011_project_skeleton.py`

- [ ] **Step 1: Write migration file**

```python
# alembic/versions/0011_project_skeleton.py
"""project skeleton tables + api_tokens.project_id

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_skeleton_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("parent_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_hint", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_table(
        "skeleton_node_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("skeleton_node_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("memory_id", UUID(as_uuid=True),
                  sa.ForeignKey("memories.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("skeleton_node_id", "memory_id", name="uq_snm_node_memory"),
    )
    op.add_column(
        "api_tokens",
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"),
                  nullable=True),
    )
    # Remove all legacy mcp_client tokens
    op.execute("DELETE FROM api_tokens WHERE kind = 'mcp_client'")


def downgrade() -> None:
    op.drop_column("api_tokens", "project_id")
    op.drop_table("skeleton_node_memories")
    op.drop_table("project_skeleton_nodes")
```

- [ ] **Step 2: Apply migration**

```bash
uv run alembic upgrade head
```

Expected output ends with: `Running upgrade 0010 -> 0011, project skeleton tables + api_tokens.project_id`

- [ ] **Step 3: Verify schema**

```bash
uv run python -c "
from memory_orchestrator_server.db_check import get_engine_sync
from sqlalchemy import text, create_engine
import os
e = create_engine(os.environ.get('MO_DB_DSN', 'postgresql+psycopg2://mo:mo@localhost:5433/memory_orchestrator'))
with e.connect() as c:
    for t in ['project_skeleton_nodes', 'skeleton_node_memories']:
        r = c.execute(text(f'SELECT count(*) FROM {t}'))
        print(t, r.scalar())
    r = c.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='api_tokens' AND column_name='project_id'\"))
    print('api_tokens.project_id exists:', r.scalar() is not None)
"
```

Expected: all three lines print without error, `api_tokens.project_id exists: True`.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/0011_project_skeleton.py
git commit -m "feat: migration 0011 — project_skeleton_nodes, skeleton_node_memories, api_tokens.project_id"
```

---

## Task 2: ORM Models

**Files:**
- Modify: `models.py`

- [ ] **Step 1: Add new ORM classes and column**

Add after the `Session` class at the bottom of `models.py`:

```python
class ProjectSkeletonNode(Base):
    __tablename__ = "project_skeleton_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    prompt_hint: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    is_builtin: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SkeletonNodeMemory(Base):
    __tablename__ = "skeleton_node_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skeleton_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
```

Also add `project_id` to `ApiToken` (after `scopes` column):

```python
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from memory_orchestrator_server.models import ProjectSkeletonNode, SkeletonNodeMemory; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add models.py
git commit -m "feat: add ProjectSkeletonNode, SkeletonNodeMemory ORM models; project_id on ApiToken"
```

---

## Task 3: Repository — Skeleton CRUD

**Files:**
- Modify: `repository.py`
- Create: `tests/unit/test_skeleton_seed.py`

- [ ] **Step 1: Write failing unit test**

```python
# tests/unit/test_skeleton_seed.py
from memory_orchestrator_server.repository import BUILTIN_SKELETON_NODES


def test_builtin_nodes_count():
    assert len(BUILTIN_SKELETON_NODES) == 8


def test_builtin_nodes_names():
    names = [n["name"] for n in BUILTIN_SKELETON_NODES]
    assert names == ["需求", "设计", "前端", "后端", "测试", "部署", "经验库", "决策记录"]


def test_builtin_nodes_have_required_keys():
    for node in BUILTIN_SKELETON_NODES:
        assert "name" in node
        assert "description" in node
        assert "prompt_hint" in node
        assert "sort_order" in node
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_skeleton_seed.py -v
```

Expected: FAIL with `ImportError: cannot import name 'BUILTIN_SKELETON_NODES'`

- [ ] **Step 3: Add BUILTIN_SKELETON_NODES and skeleton methods to repository.py**

Add at top of `repository.py` after existing imports:

```python
from memory_orchestrator_server.models import ProjectSkeletonNode, SkeletonNodeMemory
```

Add constant after imports:

```python
BUILTIN_SKELETON_NODES: list[dict] = [
    {"name": "需求",   "description": "产品需求、用户故事、验收标准", "prompt_hint": "记录功能需求、用户故事或验收条件", "sort_order": 0},
    {"name": "设计",   "description": "架构设计、技术方案、接口设计", "prompt_hint": "记录架构决策、设计方案或接口约定", "sort_order": 1},
    {"name": "前端",   "description": "UI 组件、页面、状态管理", "prompt_hint": "记录前端组件、页面结构或状态管理约定", "sort_order": 2},
    {"name": "后端",   "description": "API、服务、数据库操作", "prompt_hint": "记录后端接口、业务逻辑或 DB 操作经验", "sort_order": 3},
    {"name": "测试",   "description": "单元测试、集成测试、测试策略", "prompt_hint": "记录测试方法、测试工具或测试覆盖约定", "sort_order": 4},
    {"name": "部署",   "description": "CI/CD、Docker、环境配置", "prompt_hint": "记录部署流程、环境变量或 Docker 配置", "sort_order": 5},
    {"name": "经验库", "description": "踩坑记录、最佳实践、解决方案", "prompt_hint": "记录遇到的问题、原因和解决方案", "sort_order": 6},
    {"name": "决策记录", "description": "关键技术和产品决策", "prompt_hint": "记录重要决策：背景、选项、最终选择及原因", "sort_order": 7},
]
```

Add these methods to `MemoryRepository`:

```python
    async def create_project_with_skeleton(self, slug: str, display_name: str) -> uuid.UUID:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        now = utc_now()
        stmt = (
            pg_insert(Project)
            .values(slug=slug, display_name=display_name, root_paths=[], first_seen_at=now, last_active_at=now)
            .on_conflict_do_nothing(index_elements=["slug"])
            .returning(Project.id)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            # already exists
            existing = await self.session.execute(select(Project.id).where(Project.slug == slug))
            row = existing.scalar_one()
        project_id = row
        # Seed builtin nodes only if none exist yet
        existing_nodes = await self.session.execute(
            select(func.count(ProjectSkeletonNode.id))
            .where(ProjectSkeletonNode.project_id == project_id)
        )
        if existing_nodes.scalar_one() == 0:
            for n in BUILTIN_SKELETON_NODES:
                self.session.add(ProjectSkeletonNode(
                    project_id=project_id,
                    name=n["name"], description=n["description"],
                    prompt_hint=n["prompt_hint"], sort_order=n["sort_order"],
                    is_builtin=True,
                ))
        return project_id

    async def get_skeleton_tree(self, project_id: uuid.UUID) -> list[dict]:
        result = await self.session.execute(
            select(ProjectSkeletonNode)
            .where(ProjectSkeletonNode.project_id == project_id)
            .order_by(ProjectSkeletonNode.sort_order, ProjectSkeletonNode.created_at)
        )
        nodes = result.scalars().all()
        by_id = {n.id: n for n in nodes}
        children: dict[uuid.UUID | None, list] = {}
        for n in nodes:
            children.setdefault(n.parent_id, []).append(n)

        def _build(parent_id):
            return [
                {
                    "id": str(n.id), "name": n.name, "description": n.description,
                    "prompt_hint": n.prompt_hint, "is_builtin": n.is_builtin,
                    "sort_order": n.sort_order,
                    "children": _build(n.id),
                }
                for n in children.get(parent_id, [])
            ]
        return _build(None)

    async def patch_skeleton_node(
        self, node_id: uuid.UUID, *, name: str | None = None, prompt_hint: str | None = None
    ) -> bool:
        node = await self.session.get(ProjectSkeletonNode, node_id)
        if node is None:
            return False
        if name is not None and not node.is_builtin:
            node.name = name
        if prompt_hint is not None:
            node.prompt_hint = prompt_hint
        return True

    async def delete_skeleton_node(self, node_id: uuid.UUID) -> bool:
        node = await self.session.get(ProjectSkeletonNode, node_id)
        if node is None or node.is_builtin:
            return False
        await self.session.delete(node)
        return True

    async def add_memory_to_node(self, node_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = (
            pg_insert(SkeletonNodeMemory)
            .values(skeleton_node_id=node_id, memory_id=memory_id)
            .on_conflict_do_nothing(constraint="uq_snm_node_memory")
        )
        await self.session.execute(stmt)
        return True

    async def remove_memory_from_node(self, node_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        await self.session.execute(
            sa_delete(SkeletonNodeMemory).where(
                SkeletonNodeMemory.skeleton_node_id == node_id,
                SkeletonNodeMemory.memory_id == memory_id,
            )
        )

    async def get_node_memories(self, node_id: uuid.UUID) -> list[Memory]:
        result = await self.session.execute(
            select(Memory)
            .join(SkeletonNodeMemory, SkeletonNodeMemory.memory_id == Memory.id)
            .where(SkeletonNodeMemory.skeleton_node_id == node_id, Memory.superseded_by.is_(None))
            .order_by(Memory.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_skeleton_flat(self, project_id: uuid.UUID) -> list[ProjectSkeletonNode]:
        result = await self.session.execute(
            select(ProjectSkeletonNode)
            .where(ProjectSkeletonNode.project_id == project_id)
            .order_by(ProjectSkeletonNode.sort_order, ProjectSkeletonNode.created_at)
        )
        return list(result.scalars().all())

    async def get_or_create_skeleton_node(
        self, project_id: uuid.UUID, name: str, parent_name: str | None
    ) -> uuid.UUID:
        parent_id: uuid.UUID | None = None
        if parent_name:
            r = await self.session.execute(
                select(ProjectSkeletonNode.id).where(
                    ProjectSkeletonNode.project_id == project_id,
                    ProjectSkeletonNode.name == parent_name,
                    ProjectSkeletonNode.parent_id.is_(None),
                )
            )
            parent_id = r.scalar_one_or_none()

        r = await self.session.execute(
            select(ProjectSkeletonNode.id).where(
                ProjectSkeletonNode.project_id == project_id,
                ProjectSkeletonNode.name == name,
                ProjectSkeletonNode.parent_id == parent_id if parent_id else ProjectSkeletonNode.parent_id.is_(None),
            )
        )
        existing = r.scalar_one_or_none()
        if existing:
            return existing
        node = ProjectSkeletonNode(
            project_id=project_id, parent_id=parent_id, name=name,
            description="", prompt_hint="", is_builtin=False,
        )
        self.session.add(node)
        await self.session.flush()
        return node.id
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest tests/unit/test_skeleton_seed.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add repository.py tests/unit/test_skeleton_seed.py
git commit -m "feat: skeleton CRUD methods + BUILTIN_SKELETON_NODES"
```

---

## Task 4: Auth Tokens — project_token Kind

**Files:**
- Modify: `auth_tokens.py`
- Create: `tests/unit/test_project_token_auth.py`

- [ ] **Step 1: Write failing unit test**

```python
# tests/unit/test_project_token_auth.py
from memory_orchestrator_server.auth_tokens import TOKEN_KIND_PROJECT


def test_token_kind_project_constant():
    assert TOKEN_KIND_PROJECT == "project_token"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_project_token_auth.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Update auth_tokens.py**

Add constant after `TOKEN_KIND_UI`:

```python
TOKEN_KIND_PROJECT = "project_token"
```

Add new function after `_db_has_tokens`:

```python
async def resolve_project_token(
    *,
    session: AsyncSession,
    authorization: str | None,
) -> tuple[ApiToken, uuid.UUID] | None:
    """Validate a project_token Bearer token. Returns (token_row, project_id) or raises 401."""
    import uuid as _uuid
    from memory_orchestrator_server.models import ApiToken as _ApiToken
    token = bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    token_hash = hash_token(token)
    result = await session.execute(
        select(_ApiToken).where(
            _ApiToken.kind == TOKEN_KIND_PROJECT,
            _ApiToken.token_hash == token_hash,
            _ApiToken.revoked_at.is_(None),
            _ApiToken.enabled.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=401, detail="invalid project token")
    if not row.project_id:
        raise HTTPException(status_code=401, detail="token has no project binding")
    await session.execute(
        update(_ApiToken).where(_ApiToken.id == row.id)
        .values(last_used_at=utc_now())
        .execution_options(synchronize_session=False)
    )
    return row, row.project_id
```

Add `import uuid` at top of `auth_tokens.py` (after existing imports).

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_project_token_auth.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auth_tokens.py tests/unit/test_project_token_auth.py
git commit -m "feat: TOKEN_KIND_PROJECT + resolve_project_token() in auth_tokens"
```

---

## Task 5: API — Projects + Skeleton Endpoints

**Files:**
- Modify: `routers/ui.py`
- Create: `tests/integration/test_skeleton_api.py`

- [ ] **Step 1: Write failing integration tests**

```python
# tests/integration/test_skeleton_api.py
import pytest
import uuid
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project_seeds_skeleton(client: AsyncClient):
    r = await client.post("/api/projects", json={"slug": "test-proj", "display_name": "Test Project"})
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "test-proj"
    project_id = data["id"]

    r2 = await client.get(f"/api/projects/{project_id}/skeleton")
    assert r2.status_code == 200
    tree = r2.json()
    assert len(tree) == 8
    assert tree[0]["name"] == "需求"
    assert tree[0]["is_builtin"] is True
    assert tree[0]["children"] == []


@pytest.mark.asyncio
async def test_patch_skeleton_node_prompt_hint(client: AsyncClient):
    r = await client.post("/api/projects", json={"slug": "proj-patch", "display_name": "P"})
    project_id = r.json()["id"]
    tree = (await client.get(f"/api/projects/{project_id}/skeleton")).json()
    node_id = tree[0]["id"]

    r2 = await client.patch(f"/api/skeleton-nodes/{node_id}", json={"prompt_hint": "test hint"})
    assert r2.status_code == 200

    tree2 = (await client.get(f"/api/projects/{project_id}/skeleton")).json()
    assert tree2[0]["prompt_hint"] == "test hint"


@pytest.mark.asyncio
async def test_delete_builtin_node_forbidden(client: AsyncClient):
    r = await client.post("/api/projects", json={"slug": "proj-del", "display_name": "D"})
    project_id = r.json()["id"]
    tree = (await client.get(f"/api/projects/{project_id}/skeleton")).json()
    node_id = tree[0]["id"]

    r2 = await client.delete(f"/api/skeleton-nodes/{node_id}")
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_add_remove_memory_from_node(client: AsyncClient):
    r = await client.post("/api/projects", json={"slug": "proj-mem", "display_name": "M"})
    project_id = r.json()["id"]
    tree = (await client.get(f"/api/projects/{project_id}/skeleton")).json()
    node_id = tree[0]["id"]

    # create a memory
    rm = await client.post("/api/memories", json={
        "type": "project", "name": "test mem", "description": "d",
        "content": "c", "why": "w", "how_to_apply": "h", "project_id": project_id,
    })
    memory_id = rm.json()["id"]

    r2 = await client.post(f"/api/skeleton-nodes/{node_id}/memories", json={"memory_id": memory_id})
    assert r2.status_code == 201

    r3 = await client.get(f"/api/skeleton-nodes/{node_id}/memories")
    assert any(m["id"] == memory_id for m in r3.json())

    r4 = await client.delete(f"/api/skeleton-nodes/{node_id}/memories/{memory_id}")
    assert r4.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/integration/test_skeleton_api.py -v
```

Expected: FAIL with 404 (endpoints not yet defined).

- [ ] **Step 3: Add Pydantic models to routers/ui.py**

Add after existing Pydantic models (after `TokenPatch`):

```python
class ProjectCreate(BaseModel):
    slug: str
    display_name: str


class SkeletonNodePatch(BaseModel):
    name: str | None = None
    prompt_hint: str | None = None


class NodeMemoryAdd(BaseModel):
    memory_id: uuid.UUID
```

- [ ] **Step 4: Add endpoints inside make_ui_router (after token endpoints)**

```python
    # ── Projects ─────────────────────────────────────────────────────────────

    @router.post("/projects", status_code=201)
    async def create_project(body: ProjectCreate = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            project_id = await repo.create_project_with_skeleton(body.slug, body.display_name)
            await s.commit()
            proj = await s.get(Project, project_id)
        return {
            "id": str(proj.id), "slug": proj.slug,
            "display_name": proj.display_name,
            "memory_count": proj.memory_count,
        }

    @router.delete("/projects/{project_id}", status_code=204)
    async def delete_project(project_id: uuid.UUID) -> None:
        async with maker() as s:
            proj = await s.get(Project, project_id)
            if not proj:
                raise HTTPException(status_code=404, detail="project not found")
            await s.delete(proj)
            await s.commit()

    # ── Skeleton nodes ────────────────────────────────────────────────────────

    @router.get("/projects/{project_id}/skeleton")
    async def get_skeleton(project_id: uuid.UUID) -> list:
        async with maker() as s:
            repo = MemoryRepository(s)
            return await repo.get_skeleton_tree(project_id)

    @router.patch("/skeleton-nodes/{node_id}", status_code=200)
    async def patch_skeleton_node(node_id: uuid.UUID, body: SkeletonNodePatch = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            ok = await repo.patch_skeleton_node(node_id, name=body.name, prompt_hint=body.prompt_hint)
            if not ok:
                raise HTTPException(status_code=404, detail="node not found")
            await s.commit()
        return {"ok": True}

    @router.delete("/skeleton-nodes/{node_id}", status_code=204)
    async def delete_skeleton_node(node_id: uuid.UUID) -> None:
        async with maker() as s:
            repo = MemoryRepository(s)
            ok = await repo.delete_skeleton_node(node_id)
            await s.commit()
        if not ok:
            raise HTTPException(status_code=409, detail="cannot delete builtin node or node not found")

    @router.post("/skeleton-nodes/{node_id}/memories", status_code=201)
    async def add_memory_to_node(node_id: uuid.UUID, body: NodeMemoryAdd = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            await repo.add_memory_to_node(node_id, body.memory_id)
            await s.commit()
        return {"ok": True}

    @router.get("/skeleton-nodes/{node_id}/memories")
    async def get_node_memories(node_id: uuid.UUID) -> list:
        async with maker() as s:
            repo = MemoryRepository(s)
            mems = await repo.get_node_memories(node_id)
        return [
            {
                "id": str(m.id), "type": m.type, "name": m.name,
                "description": m.description, "content": m.content,
                "importance": m.importance,
                "created_at": isoformat_utc(m.created_at),
            }
            for m in mems
        ]

    @router.delete("/skeleton-nodes/{node_id}/memories/{memory_id}", status_code=204)
    async def remove_memory_from_node(node_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        async with maker() as s:
            repo = MemoryRepository(s)
            await repo.remove_memory_from_node(node_id, memory_id)
            await s.commit()
```

Also add `Project` to the import at top of `make_ui_router`:

```python
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory, Project
from memory_orchestrator_server.repository import MemoryRepository, _sync_project_count
```

- [ ] **Step 5: Run integration tests**

```bash
uv run pytest tests/integration/test_skeleton_api.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add routers/ui.py tests/integration/test_skeleton_api.py
git commit -m "feat: project + skeleton CRUD API endpoints"
```

---

## Task 6: API — Token Creation for project_token

**Files:**
- Modify: `routers/ui.py`

- [ ] **Step 1: Update TokenCreate model**

Replace existing `TokenCreate`:

```python
class TokenCreate(BaseModel):
    kind: str
    name: str
    project_id: uuid.UUID | None = None
```

- [ ] **Step 2: Update create_token endpoint**

Replace the existing `create_token` function body:

```python
    @router.post("/tokens", status_code=201)
    async def create_token(body: TokenCreate = Body(...)) -> dict:
        from memory_orchestrator_server.auth_tokens import TOKEN_KIND_PROJECT
        from memory_orchestrator_server.models import ApiToken

        if body.kind not in ("ui_admin", TOKEN_KIND_PROJECT):
            raise HTTPException(status_code=422, detail="kind must be ui_admin or project_token")
        if body.kind == TOKEN_KIND_PROJECT and not body.project_id:
            raise HTTPException(status_code=422, detail="project_id required for project_token")

        raw, token_hash = _new_token_pair()
        async with maker() as s:
            t = ApiToken(
                name=body.name, kind=body.kind, token_hash=token_hash,
                project_id=body.project_id,
            )
            s.add(t)
            await s.commit()
            await s.refresh(t)
        return {
            "id": str(t.id), "name": t.name, "kind": t.kind,
            "token": raw,  # shown once
            "project_id": str(t.project_id) if t.project_id else None,
            "created_at": isoformat_utc(t.created_at),
        }
```

- [ ] **Step 3: Verify tokens endpoint returns project_id**

```bash
uv run pytest tests/integration/ -k "token" -v
```

Expected: existing token tests still pass.

- [ ] **Step 4: Commit**

```bash
git add routers/ui.py
git commit -m "feat: project_token support in token creation endpoint"
```

---

## Task 7: Ingestor — Skeleton-Aware Extraction

**Files:**
- Modify: `ingestor.py`
- Create: `tests/unit/test_ingestor_skeleton.py`

- [ ] **Step 1: Write failing unit test**

```python
# tests/unit/test_ingestor_skeleton.py
from memory_orchestrator_server.ingestor import (
    MemoryCandidateWithNode, build_extraction_prompt_with_skeleton,
)


def test_memory_candidate_with_node_optional():
    m = MemoryCandidateWithNode(
        type="project", name="n", description="d", content="c",
        why="w", how_to_apply="h",
    )
    assert m.skeleton_node is None


def test_memory_candidate_with_node_set():
    m = MemoryCandidateWithNode(
        type="project", name="n", description="d", content="c",
        why="w", how_to_apply="h",
        skeleton_node={"name": "前端", "parent_name": None, "create_if_missing": False},
    )
    assert m.skeleton_node["name"] == "前端"


def test_build_extraction_prompt_with_skeleton_includes_nodes():
    skeleton = [
        {"name": "前端", "prompt_hint": "UI components", "children": []},
        {"name": "后端", "prompt_hint": "API logic", "children": []},
    ]
    prompt = build_extraction_prompt_with_skeleton("transcript text", "proj-123", skeleton)
    assert "前端" in prompt
    assert "UI components" in prompt
    assert "skeleton_node" in prompt


def test_build_extraction_prompt_no_skeleton_unchanged():
    from memory_orchestrator_server.ingestor import build_extraction_prompt
    prompt = build_extraction_prompt("transcript text", "proj-123")
    assert "transcript text" in prompt
    assert "proj-123" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_ingestor_skeleton.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Update ingestor.py**

Add `MemoryCandidateWithNode` class after `MemoryCandidate`:

```python
class SkeletonNodeAssignment(BaseModel):
    name: str
    parent_name: str | None = None
    create_if_missing: bool = False


class MemoryCandidateWithNode(MemoryCandidate):
    skeleton_node: SkeletonNodeAssignment | None = None


class _ExtractionOutputWithSkeleton(BaseModel):
    memories: list[MemoryCandidateWithNode]
```

Add new prompt builder after `build_extraction_prompt`:

```python
def build_extraction_prompt_with_skeleton(
    transcript_chunk: str, project_id: str, skeleton: list[dict]
) -> str:
    def _flatten(nodes, depth=0):
        lines = []
        for n in nodes:
            indent = "  " * depth
            hint = f" — {n['prompt_hint']}" if n.get("prompt_hint") else ""
            lines.append(f"{indent}- {n['name']}{hint}")
            lines.extend(_flatten(n.get("children", []), depth + 1))
        return lines

    skeleton_text = "\n".join(_flatten(skeleton))
    return (
        f"Project: {project_id}\n\n"
        f"Project skeleton (assign each memory to the best node):\n{skeleton_text}\n\n"
        f"For each memory add a 'skeleton_node' field: "
        f"{{\"name\": \"<node name>\", \"parent_name\": \"<parent or null>\", "
        f"\"create_if_missing\": false}}. "
        f"Use an existing node when possible; set create_if_missing=true only for sub-nodes.\n\n"
        f"Transcript chunk:\n<transcript>\n{transcript_chunk}\n</transcript>\n\n"
        f"Extract memories now."
    )
```

Update `ingest_session` to use skeleton when available. Replace the block from `chunk = _render_chunk(lines)` through `memory_candidates = result.output.memories`:

```python
    chunk = _render_chunk(lines)

    try:
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(base_url=extraction_base_url, api_key=extraction_api_key)

        # Fetch skeleton if project has one
        skeleton: list[dict] = []
        if project_id != GLOBAL_PROJECT_ID:
            skeleton = await repo.get_skeleton_tree(project_id)

        if skeleton:
            agent: Agent[None, _ExtractionOutputWithSkeleton] = Agent(
                model=OpenAIChatModel(extraction_model, provider=provider),
                output_type=_ExtractionOutputWithSkeleton,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
            )
            result = await agent.run(
                build_extraction_prompt_with_skeleton(chunk, str(project_id), skeleton),
                model_settings={"max_tokens": 2048},
            )
            memory_candidates = result.output.memories
        else:
            agent2: Agent[None, _ExtractionOutput] = Agent(
                model=OpenAIChatModel(extraction_model, provider=provider),
                output_type=_ExtractionOutput,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
            )
            result2 = await agent2.run(
                build_extraction_prompt(chunk, str(project_id)),
                model_settings={"max_tokens": 2048},
            )
            memory_candidates = result2.output.memories
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)[:500]
        await db.commit()
        raise
```

After `m = await repo.save(...)` and `saved += 1`, add node linking:

```python
            # Link to skeleton node if LLM provided one
            cand_with_node = cand if isinstance(cand, MemoryCandidateWithNode) else None
            if cand_with_node and cand_with_node.skeleton_node and project_id != GLOBAL_PROJECT_ID:
                sn = cand_with_node.skeleton_node
                try:
                    node_id = await repo.get_or_create_skeleton_node(
                        project_id=cand_pid,
                        name=sn.name,
                        parent_name=sn.parent_name,
                    ) if sn.create_if_missing else None
                    if not node_id:
                        # Try to find existing node
                        nodes = await repo.get_skeleton_flat(cand_pid)
                        match = next((n for n in nodes if n.name == sn.name), None)
                        if match:
                            node_id = match.id
                    if node_id:
                        await repo.add_memory_to_node(node_id, m.id)
                except Exception:
                    pass  # skeleton linking is best-effort; don't fail ingestion
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest tests/unit/test_ingestor_skeleton.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ingestor.py tests/unit/test_ingestor_skeleton.py
git commit -m "feat: skeleton-aware LLM extraction — MemoryCandidateWithNode + node linking"
```

---

## Task 8: Frontend — Vue Router + api.js

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.js`
- Create: `frontend/src/api.js`

All commands in `frontend/`.

- [ ] **Step 1: Install vue-router**

```bash
npm install vue-router@4
```

- [ ] **Step 2: Create api.js**

```javascript
// frontend/src/api.js
export const BASE = '/api'

export function apiFetch(url, opts = {}) {
  return fetch(url, opts)
}

export async function apiJSON(url, opts = {}) {
  const r = await apiFetch(url, opts)
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}
```

- [ ] **Step 3: Update main.js**

```javascript
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import '@fontsource/orbitron/700.css'
import '@fontsource/orbitron/900.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'
import './style.css'
import App from './App.vue'
import SkeletonPage from './SkeletonPage.vue'

const router = createRouter({
  history: createWebHistory('/ui/'),
  routes: [
    { path: '/', component: SkeletonPage },
    { path: '/memories', component: App },
  ],
})

createApp({ template: '<router-view />' })
  .use(router)
  .mount('#app')
```

- [ ] **Step 4: Verify build works**

```bash
npm run build 2>&1 | tail -5
```

Expected: build completes without errors (SkeletonPage.vue doesn't exist yet so it will error — create a stub first):

Create `src/SkeletonPage.vue` with just:

```vue
<template><div>Loading…</div></template>
<script setup></script>
```

Then run build again — should succeed.

- [ ] **Step 5: Commit**

```bash
cd ..  # back to memory_orchestrator_server/
git add frontend/package.json frontend/package-lock.json frontend/src/main.js frontend/src/api.js frontend/src/SkeletonPage.vue
git commit -m "feat: Vue Router setup — /ui/ → SkeletonPage, /ui/memories → App.vue"
```

---

## Task 9: SkeletonPage.vue — Full Implementation

**Files:**
- Modify: `frontend/src/SkeletonPage.vue`

- [ ] **Step 1: Replace stub with full component**

```vue
<template>
  <div class="sk-app" :class="{ dark: isDark }">
    <!-- Login overlay (same as App.vue) -->
    <div v-if="loginOpen" class="modal-overlay login-overlay">
      <div class="login-modal">
        <div class="login-title">Memory Orchestrator</div>
        <input v-model="loginInput" class="login-input" type="password"
          placeholder="Admin token…" @keydown.enter="submitLogin" />
        <p v-if="loginError" class="login-error">{{ loginError }}</p>
        <button class="btn-login" :disabled="loginLoading" @click="submitLogin">
          {{ loginLoading ? 'Signing in…' : 'Sign in' }}
        </button>
        <button class="btn-skip" @click="skipLogin">Continue without token</button>
      </div>
    </div>

    <template v-if="!loginOpen">
      <header class="sk-header">
        <span class="sk-logo">Memory Orchestrator</span>
        <nav class="sk-nav">
          <router-link to="/memories" class="sk-nav-link">→ Memories</router-link>
        </nav>
        <div class="sk-header-right">
          <button @click="isDark = !isDark" class="btn-icon" title="Toggle theme">◑</button>
        </div>
      </header>

      <div class="sk-body">
        <!-- Left: project list -->
        <aside class="sk-sidebar">
          <div class="sk-sidebar-title">Projects</div>
          <ul class="sk-project-list">
            <li v-for="p in projects" :key="p.id"
              :class="['sk-project-item', { active: selectedProject?.id === p.id }]"
              @click="selectProject(p)">
              {{ p.display_name || p.slug }}
              <span class="sk-mem-count">{{ p.memory_count }}</span>
            </li>
          </ul>
          <div v-if="showNewProject" class="sk-new-project-form">
            <input v-model="newProjectName" class="sk-input" placeholder="Project name…"
              @keydown.enter="createProject" ref="newProjectInput" />
            <button class="btn-sm btn-primary" :disabled="!newProjectName || isCreatingProject"
              @click="createProject">
              {{ isCreatingProject ? '…' : 'Create' }}
            </button>
            <button class="btn-sm" @click="showNewProject = false">✕</button>
          </div>
          <button v-else class="btn-new-project" @click="openNewProject">+ New Project</button>
        </aside>

        <!-- Right: skeleton tree -->
        <main class="sk-main" v-if="selectedProject">
          <div class="sk-main-header">
            <span class="sk-project-title">{{ selectedProject.display_name || selectedProject.slug }}</span>
            <button class="btn-sm btn-secondary" @click="openTokenModal">+ Token</button>
            <button class="btn-sm btn-danger" @click="confirmDeleteProject">Delete Project</button>
          </div>

          <div class="sk-skeleton" v-if="skeletonTree.length">
            <div class="sk-tree-title">Skeleton</div>
            <ul class="sk-tree">
              <sk-node
                v-for="node in skeletonTree" :key="node.id"
                :node="node"
                :selected-node-id="selectedNode?.id"
                @select="selectNode"
                @patch="patchNode"
                @delete="deleteNode"
              />
            </ul>
          </div>

          <!-- Node detail -->
          <div class="sk-node-detail" v-if="selectedNode">
            <div class="sk-node-detail-title">{{ selectedNode.name }}</div>
            <div class="sk-prompt-hint-wrap">
              <label class="sk-field-label">Prompt hint</label>
              <input class="sk-input" v-model="editingPromptHint"
                @blur="savePromptHint" @keydown.enter="savePromptHint"
                placeholder="Guide text shown when creating memories in this section…" />
            </div>
            <div class="sk-node-memories-header">
              <span class="sk-field-label">Memories ({{ nodeMemories.length }})</span>
              <button class="btn-sm btn-primary" @click="openAddMemory">+ Add Memory</button>
            </div>
            <ul class="sk-memory-list">
              <li v-for="m in nodeMemories" :key="m.id" class="sk-memory-item">
                <span :class="['badge', m.type]">{{ m.type }}</span>
                <span class="sk-mem-name">{{ m.name }}</span>
                <button class="btn-icon btn-danger-sm" @click="unlinkMemory(m.id)" title="Unlink">✕</button>
              </li>
            </ul>
          </div>
        </main>

        <main class="sk-main sk-main-empty" v-else>
          <p>Select or create a project to see its skeleton.</p>
        </main>
      </div>
    </template>

    <!-- Add Memory Modal -->
    <div v-if="addMemoryOpen" class="modal-overlay" @click.self="addMemoryOpen = false">
      <div class="write-modal">
        <div class="write-header">
          <span class="write-title">New Memory → {{ selectedNode?.name }}</span>
          <button class="modal-close" @click="addMemoryOpen = false">✕</button>
        </div>
        <div class="write-body">
          <p v-if="selectedNode?.prompt_hint" class="sk-prompt-hint-text">
            {{ selectedNode.prompt_hint }}
          </p>
          <div class="write-type-tabs">
            <button v-for="tp in ['user','feedback','project','reference']" :key="tp"
              :class="['type-tab', 'type-tab-'+tp, memForm.type === tp ? 'active' : '']"
              @click="memForm.type = tp">{{ tp }}</button>
          </div>
          <div class="write-section">
            <label class="write-field-label">Name</label>
            <input class="write-input" v-model="memForm.name" placeholder="Short identifier…" />
          </div>
          <div class="write-section">
            <label class="write-field-label">Description</label>
            <input class="write-input" v-model="memForm.description" placeholder="One-line summary…" />
          </div>
          <div class="write-section write-section-grow">
            <label class="write-field-label">Content</label>
            <textarea class="write-input write-textarea" v-model="memForm.content" rows="5" />
          </div>
          <div v-if="memForm.type === 'feedback' || memForm.type === 'project'" class="write-section">
            <label class="write-field-label">Why</label>
            <input class="write-input" v-model="memForm.why" placeholder="Reason…" />
          </div>
          <div v-if="memForm.type === 'feedback' || memForm.type === 'project'" class="write-section">
            <label class="write-field-label">How to apply</label>
            <input class="write-input" v-model="memForm.how_to_apply" placeholder="When / how to use…" />
          </div>
          <p v-if="memError" class="save-hint err">{{ memError }}</p>
        </div>
        <div class="write-footer">
          <button class="btn-cancel" @click="addMemoryOpen = false">Cancel</button>
          <button class="btn-save" :disabled="isMemSaving || !memForm.name || !memForm.content"
            @click="submitAddMemory">
            {{ isMemSaving ? 'Saving…' : 'Write' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Token Modal -->
    <div v-if="tokenModalOpen" class="modal-overlay" @click.self="tokenModalOpen = false">
      <div class="modal" style="max-width:420px">
        <div class="modal-header">
          <span class="modal-title">New Project Token</span>
          <button class="modal-close" @click="tokenModalOpen = false">✕</button>
        </div>
        <div style="padding:16px;display:flex;flex-direction:column;gap:10px">
          <input class="sk-input" v-model="newTokenName" placeholder="Token name…" />
          <div v-if="!newTokenValue">
            <button class="btn-save" :disabled="!newTokenName || isCreatingToken" @click="createToken">
              {{ isCreatingToken ? 'Creating…' : 'Create Token' }}
            </button>
          </div>
          <div v-else class="token-reveal">
            <p style="color:var(--warn);font-size:12px">Shown once — copy now!</p>
            <code class="token-code" @click="copyToken">{{ newTokenValue }}</code>
            <button class="btn-sm" @click="copyToken">Copy</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, defineComponent, h } from 'vue'
import { BASE, apiFetch, apiJSON } from './api.js'

// ── Theme ──
const isDark = ref(document.documentElement.classList.contains('dark') ||
  window.matchMedia('(prefers-color-scheme: dark)').matches)
watch(isDark, v => document.documentElement.classList.toggle('dark', v))

// ── Auth (mirrors App.vue) ──
const loginOpen = ref(false)
const loginInput = ref('')
const loginError = ref('')
const loginLoading = ref(false)

async function submitLogin() {
  loginLoading.value = true
  loginError.value = ''
  try {
    const r = await fetch(`${BASE}/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: loginInput.value }),
    })
    if (r.status === 401) { loginError.value = 'Invalid token'; return }
    loginOpen.value = false
    loginInput.value = ''
    await loadProjects()
  } catch (e) { loginError.value = e.message }
  finally { loginLoading.value = false }
}

async function skipLogin() {
  loginLoading.value = true
  try {
    const r = await fetch(`${BASE}/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: '' }),
    })
    if (r.status === 401) { loginError.value = 'Server requires a token'; return }
    loginOpen.value = false
    await loadProjects()
  } finally { loginLoading.value = false }
}

// ── Projects ──
const projects = ref([])
const selectedProject = ref(null)

async function loadProjects() {
  try {
    const r = await apiFetch(`${BASE}/projects`)
    if (r.status === 401) { loginOpen.value = true; return }
    projects.value = await r.json()
  } catch (e) { loginOpen.value = true }
}

function selectProject(p) {
  selectedProject.value = p
  selectedNode.value = null
  nodeMemories.value = []
  loadSkeleton(p.id)
}

const showNewProject = ref(false)
const newProjectName = ref('')
const isCreatingProject = ref(false)
const newProjectInput = ref(null)

function openNewProject() {
  showNewProject.value = true
  newProjectName.value = ''
  setTimeout(() => newProjectInput.value?.focus(), 50)
}

async function createProject() {
  if (!newProjectName.value) return
  isCreatingProject.value = true
  try {
    const slug = newProjectName.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
    const p = await apiJSON(`${BASE}/projects`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug, display_name: newProjectName.value }),
    })
    showNewProject.value = false
    newProjectName.value = ''
    await loadProjects()
    selectProject(p)
  } catch (e) { alert(e.message) }
  finally { isCreatingProject.value = false }
}

async function confirmDeleteProject() {
  if (!selectedProject.value) return
  if (!confirm(`Delete project "${selectedProject.value.display_name}"?`)) return
  await apiFetch(`${BASE}/projects/${selectedProject.value.id}`, { method: 'DELETE' })
  selectedProject.value = null
  skeletonTree.value = []
  await loadProjects()
}

// ── Skeleton ──
const skeletonTree = ref([])
const selectedNode = ref(null)
const nodeMemories = ref([])
const editingPromptHint = ref('')

async function loadSkeleton(projectId) {
  const tree = await apiJSON(`${BASE}/projects/${projectId}/skeleton`)
  skeletonTree.value = tree
}

function selectNode(node) {
  selectedNode.value = node
  editingPromptHint.value = node.prompt_hint || ''
  loadNodeMemories(node.id)
}

async function loadNodeMemories(nodeId) {
  nodeMemories.value = await apiJSON(`${BASE}/skeleton-nodes/${nodeId}/memories`)
}

async function savePromptHint() {
  if (!selectedNode.value) return
  await apiFetch(`${BASE}/skeleton-nodes/${selectedNode.value.id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt_hint: editingPromptHint.value }),
  })
  selectedNode.value.prompt_hint = editingPromptHint.value
  loadSkeleton(selectedProject.value.id)
}

async function patchNode(nodeId, patch) {
  await apiFetch(`${BASE}/skeleton-nodes/${nodeId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  await loadSkeleton(selectedProject.value.id)
}

async function deleteNode(nodeId) {
  if (!confirm('Delete this node and unlink its memories?')) return
  const r = await apiFetch(`${BASE}/skeleton-nodes/${nodeId}`, { method: 'DELETE' })
  if (r.status === 409) { alert('Cannot delete a builtin node.'); return }
  if (selectedNode.value?.id === nodeId) { selectedNode.value = null; nodeMemories.value = [] }
  await loadSkeleton(selectedProject.value.id)
}

async function unlinkMemory(memoryId) {
  await apiFetch(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories/${memoryId}`, { method: 'DELETE' })
  await loadNodeMemories(selectedNode.value.id)
}

// ── Add Memory ──
const addMemoryOpen = ref(false)
const isMemSaving = ref(false)
const memError = ref('')
const memForm = ref({ type: 'project', name: '', description: '', content: '', why: '', how_to_apply: '' })

function openAddMemory() {
  memForm.value = {
    type: selectedNode.value?.name === '需求' || selectedNode.value?.name === '设计' ? 'project' : 'project',
    name: '', description: '', content: '', why: '', how_to_apply: '',
  }
  memError.value = ''
  addMemoryOpen.value = true
}

async function submitAddMemory() {
  if (!memForm.value.name || !memForm.value.content) return
  isMemSaving.value = true
  memError.value = ''
  try {
    const payload = {
      ...memForm.value,
      project_id: selectedProject.value.id,
    }
    if (!payload.why) delete payload.why
    if (!payload.how_to_apply) delete payload.how_to_apply
    const mem = await apiJSON(`${BASE}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: mem.id }),
    })
    addMemoryOpen.value = false
    await loadNodeMemories(selectedNode.value.id)
  } catch (e) { memError.value = e.message }
  finally { isMemSaving.value = false }
}

// ── Token ──
const tokenModalOpen = ref(false)
const newTokenName = ref('')
const newTokenValue = ref('')
const isCreatingToken = ref(false)

function openTokenModal() {
  newTokenName.value = ''
  newTokenValue.value = ''
  tokenModalOpen.value = true
}

async function createToken() {
  isCreatingToken.value = true
  try {
    const data = await apiJSON(`${BASE}/tokens`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: 'project_token',
        name: newTokenName.value,
        project_id: selectedProject.value.id,
      }),
    })
    newTokenValue.value = data.token
  } catch (e) { alert(e.message) }
  finally { isCreatingToken.value = false }
}

async function copyToken() {
  await navigator.clipboard.writeText(newTokenValue.value)
}

// ── Init ──
onMounted(async () => {
  const r = await apiFetch(`${BASE}/projects`)
  if (r.status === 401) { loginOpen.value = true; return }
  projects.value = await r.json()
})
</script>

<script>
// SkNode recursive component for skeleton tree
export default {
  components: {
    SkNode: {
      name: 'SkNode',
      props: ['node', 'selectedNodeId'],
      emits: ['select', 'patch', 'delete'],
      data() { return { hovering: false, editing: false, editName: '' } },
      methods: {
        startEdit() { this.editName = this.node.name; this.editing = true },
        saveEdit() {
          if (this.editName && this.editName !== this.node.name)
            this.$emit('patch', this.node.id, { name: this.editName })
          this.editing = false
        },
      },
      template: `
        <li class="sk-node" @mouseenter="hovering=true" @mouseleave="hovering=false">
          <div :class="['sk-node-row', { active: selectedNodeId === node.id }]"
            @click="$emit('select', node)">
            <span v-if="!editing" class="sk-node-name">{{ node.name }}</span>
            <input v-else class="sk-node-edit-input" v-model="editName"
              @blur="saveEdit" @keydown.enter="saveEdit" @keydown.esc="editing=false" ref="ei"
              @vue:mounted="$refs.ei?.focus()" />
            <span class="sk-node-actions" v-show="hovering">
              <button class="btn-icon-xs" @click.stop="startEdit" title="Edit">✎</button>
              <button v-if="!node.is_builtin" class="btn-icon-xs btn-danger-xs"
                @click.stop="$emit('delete', node.id)" title="Delete">✕</button>
            </span>
          </div>
          <ul v-if="node.children?.length" class="sk-tree sk-subtree">
            <sk-node v-for="c in node.children" :key="c.id" :node="c"
              :selected-node-id="selectedNodeId"
              @select="$emit('select', $event)"
              @patch="(id, p) => $emit('patch', id, p)"
              @delete="$emit('delete', $event)" />
          </ul>
        </li>
      `,
    },
  },
}
</script>

<style scoped>
.sk-app { min-height: 100vh; background: var(--bg, #fff); color: var(--fg, #1a1a1a); font-family: 'JetBrains Mono', monospace; }
.sk-header { display: flex; align-items: center; gap: 12px; padding: 10px 20px; border-bottom: 1px solid var(--border, #e0e0e0); }
.sk-logo { font-weight: 700; font-size: 14px; }
.sk-nav { margin-left: auto; }
.sk-nav-link { font-size: 12px; color: var(--accent, #2563eb); text-decoration: none; }
.sk-nav-link:hover { text-decoration: underline; }
.sk-header-right { display: flex; gap: 8px; }
.sk-body { display: grid; grid-template-columns: 220px 1fr; height: calc(100vh - 41px); }
.sk-sidebar { border-right: 1px solid var(--border, #e0e0e0); padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.sk-sidebar-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--fg-muted, #6e7681); margin-bottom: 6px; }
.sk-project-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 2px; }
.sk-project-item { padding: 6px 8px; border-radius: 5px; cursor: pointer; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
.sk-project-item:hover { background: var(--hover, #f5f5f5); }
.sk-project-item.active { background: var(--active-bg, #dbeafe); color: var(--accent, #2563eb); }
.sk-mem-count { font-size: 11px; color: var(--fg-muted, #6e7681); }
.sk-new-project-form { display: flex; gap: 4px; margin-top: 6px; }
.btn-new-project { margin-top: 8px; font-size: 12px; color: var(--accent, #2563eb); background: none; border: 1px dashed var(--border, #ccc); border-radius: 5px; padding: 5px 8px; cursor: pointer; width: 100%; }
.sk-main { padding: 16px 20px; overflow-y: auto; }
.sk-main-empty { display: flex; align-items: center; justify-content: center; color: var(--fg-muted, #999); font-size: 13px; }
.sk-main-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.sk-project-title { font-size: 16px; font-weight: 700; flex: 1; }
.sk-tree-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--fg-muted, #6e7681); margin-bottom: 8px; }
.sk-tree { list-style: none; padding: 0; margin: 0; }
.sk-subtree { padding-left: 16px; }
.sk-node-row { display: flex; align-items: center; padding: 5px 6px; border-radius: 4px; cursor: pointer; font-size: 13px; gap: 6px; }
.sk-node-row:hover { background: var(--hover, #f5f5f5); }
.sk-node-row.active { background: var(--active-bg, #dbeafe); }
.sk-node-name { flex: 1; }
.sk-node-actions { display: flex; gap: 4px; }
.sk-node-edit-input { flex: 1; border: 1px solid var(--border, #ccc); border-radius: 3px; padding: 1px 4px; font-size: 12px; }
.sk-node-detail { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border, #e0e0e0); }
.sk-node-detail-title { font-size: 15px; font-weight: 700; margin-bottom: 10px; }
.sk-prompt-hint-wrap { margin-bottom: 12px; }
.sk-field-label { display: block; font-size: 11px; font-weight: 600; color: var(--fg-muted, #6e7681); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.sk-input { width: 100%; border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 6px 8px; font-size: 13px; font-family: inherit; background: var(--input-bg, #fff); color: var(--fg, #1a1a1a); }
.sk-node-memories-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.sk-memory-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.sk-memory-item { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border: 1px solid var(--border, #eee); border-radius: 5px; font-size: 12px; }
.sk-mem-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-icon { background: none; border: none; cursor: pointer; padding: 3px 5px; font-size: 13px; color: var(--fg-muted, #666); }
.btn-icon:hover { color: var(--fg, #1a1a1a); }
.btn-sm { padding: 4px 10px; border-radius: 5px; border: 1px solid var(--border, #ccc); font-size: 12px; cursor: pointer; background: var(--btn-bg, #f5f5f5); color: var(--fg, #1a1a1a); }
.btn-primary { background: var(--accent, #2563eb); color: #fff; border-color: transparent; }
.btn-secondary { background: transparent; border-color: var(--accent, #2563eb); color: var(--accent, #2563eb); }
.btn-danger { background: transparent; border-color: #dc2626; color: #dc2626; }
.btn-icon-xs { background: none; border: none; cursor: pointer; padding: 1px 3px; font-size: 11px; color: var(--fg-muted, #888); }
.btn-icon-xs:hover { color: var(--fg, #1a1a1a); }
.btn-danger-xs { color: #dc2626; }
.btn-danger-sm { padding: 1px 4px; font-size: 11px; background: none; border: none; color: #dc2626; cursor: pointer; }
.sk-prompt-hint-text { font-size: 12px; color: var(--fg-muted, #888); background: var(--hint-bg, #f8f9fa); padding: 8px 10px; border-radius: 4px; margin-bottom: 10px; font-style: italic; }
.token-reveal { display: flex; flex-direction: column; gap: 6px; }
.token-code { display: block; padding: 8px; background: var(--code-bg, #f5f5f5); border-radius: 4px; font-size: 11px; word-break: break-all; cursor: pointer; border: 1px solid var(--border, #ddd); }
/* Dark mode vars */
.dark { --bg: #0d1117; --fg: #e6edf3; --fg-muted: #8b949e; --border: #30363d; --hover: #161b22; --active-bg: #1d2d3e; --input-bg: #161b22; --btn-bg: #21262d; --hint-bg: #161b22; --code-bg: #161b22; --accent: #58a6ff; --warn: #f0883e; }
/* Reuse write-modal styles from global style.css */
</style>
```

- [ ] **Step 2: Build and test manually**

```bash
cd frontend && npm run build
```

Expected: build succeeds without errors.

Start server and open `/ui/`:

```bash
cd .. && uv run mo-server serve-http
```

Open `http://localhost:8765/ui/` — should show SkeletonPage with project list.
Open `http://localhost:8765/ui/memories` — should show existing App.vue memory list.

**Manual smoke test checklist:**
- [ ] Create a new project → 8 skeleton nodes auto-appear
- [ ] Click a node → detail panel appears with prompt_hint field
- [ ] Edit prompt_hint → saved on blur/enter
- [ ] Click "+ Add Memory" → form opens with node name in header, prompt_hint as hint text
- [ ] Fill and submit form → memory appears in node's memory list
- [ ] Click ✕ next to memory → memory unlinked from node
- [ ] Click ✎ on non-builtin node → inline rename
- [ ] Try to delete builtin node → alert "Cannot delete a builtin node"
- [ ] Click "+ Token" → create project token → copy value
- [ ] Navigate to `/ui/memories` → App.vue loads unchanged

- [ ] **Step 3: Commit**

```bash
cd ..  # memory_orchestrator_server/
git add frontend/src/SkeletonPage.vue
git commit -m "feat: SkeletonPage.vue — project skeleton management at /ui/"
```

---

## Final: Run Full Test Suite

- [ ] **Run all unit tests**

```bash
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Run integration tests**

```bash
uv run pytest tests/integration/ -v
```

Expected: all pass.

- [ ] **Build frontend**

```bash
cd frontend && npm run build
```

Expected: no errors, `dist/` updated.
