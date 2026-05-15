# Knowledge Tree UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current two-column SkeletonPage with a three-column Obsidian-style knowledge tree UI: icon strip (project switcher) + collapsible tree panel + node detail panel, with tags, drag-and-drop reordering, right-click context menu, hover tooltip, and in-project search.

**Architecture:** Backend gains a `tags ARRAY(Text)` column on `project_skeleton_nodes`, a `POST /skeleton-nodes/reorder` bulk-sort endpoint, and a `POST /skeleton-nodes` create endpoint. Frontend replaces the monolithic `SkeletonPage.vue` with six focused components wired by a refactored orchestrator. All child components emit intents upward; only `SkeletonPage.vue` calls the API.

**Tech Stack:** Vue 3 Composition API, FastAPI, PostgreSQL ARRAY, Alembic, HTML5 Drag API, `<Teleport>`.

---

## File Map

### Backend — new / modified
| File | Action | Purpose |
|---|---|---|
| `alembic/versions/0012_skeleton_node_tags.py` | **create** | Add `tags ARRAY(Text)` column |
| `models.py` | **modify** | Add `tags` mapped column to `ProjectSkeletonNode` |
| `repository.py` | **modify** | Update `BUILTIN_SKELETON_NODES`; update `get_skeleton_tree`; update `patch_skeleton_node`; add `create_skeleton_node`; add `reorder_skeleton_nodes` |
| `routers/ui.py` | **modify** | New `SkeletonNodeCreate` schema; update `SkeletonNodePatch`; add create + reorder endpoints |

### Frontend — new
| File | Purpose |
|---|---|
| `frontend/src/SkNode.vue` | Recursive single-node renderer: emoji, drag handle, chevron, tooltip, context-menu emit |
| `frontend/src/ContextMenu.vue` | Right-click floating menu (fixed position, viewport-flip) |
| `frontend/src/TagPicker.vue` | Tag chip input with fuzzy autocomplete |
| `frontend/src/ProjectIconStrip.vue` | 52 px icon strip — project switcher |
| `frontend/src/SkeletonTreePanel.vue` | Tree container with search bar + `useTreeSearch` composable |
| `frontend/src/NodeDetailPanel.vue` | Right panel: tags, prompt hint, memory list |

### Frontend — modified
| File | Action |
|---|---|
| `frontend/src/SkeletonPage.vue` | Refactor to pure data orchestrator; wire six sub-components |

---

## Task 1: DB Migration — Add `tags` Column

**Files:**
- Create: `alembic/versions/0012_skeleton_node_tags.py`

Run from `memory_orchestrator_server/`.

- [ ] **Step 1: Create the migration file**

```python
# alembic/versions/0012_skeleton_node_tags.py
"""skeleton node tags column

Revision ID: 0012_skeleton_node_tags
Revises: 0011_project_skeleton
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_skeleton_node_tags"
down_revision = "0011_project_skeleton"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_skeleton_nodes",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("project_skeleton_nodes", "tags")
```

- [ ] **Step 2: Apply migration**

```bash
cd memory_orchestrator_server
uv run alembic upgrade head
```

Expected: `Running upgrade 0011_project_skeleton -> 0012_skeleton_node_tags, skeleton node tags column`

- [ ] **Step 3: Verify column exists**

```bash
uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from memory_orchestrator_server.config import get_settings
async def check():
    e = create_async_engine(get_settings().db_dsn)
    async with e.connect() as c:
        r = await c.execute(__import__('sqlalchemy').text(
            \"SELECT column_name FROM information_schema.columns \"
            \"WHERE table_name='project_skeleton_nodes' AND column_name='tags'\"
        ))
        print('tags column found:', r.scalar())
asyncio.run(check())
"
```

Expected: `tags column found: tags`

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/0012_skeleton_node_tags.py
git commit -m "feat: migration 0012 — add tags ARRAY column to project_skeleton_nodes"
```

---

## Task 2: ORM Model — Add `tags` Field

**Files:**
- Modify: `models.py:89-106`

- [ ] **Step 1: Add `tags` column to `ProjectSkeletonNode`**

In `models.py`, after the `sort_order` mapped column (line ~104), add:

```python
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default="{}"
    )
```

The full `ProjectSkeletonNode` class should look like:

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
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
```

- [ ] **Step 2: Verify server starts**

```bash
uv run mo-server serve-http &
sleep 2 && curl -s http://localhost:8765/healthz | python -m json.tool
kill %1
```

Expected: `{"status": "ok", ...}`

- [ ] **Step 3: Commit**

```bash
git add models.py
git commit -m "feat: add tags mapped column to ProjectSkeletonNode ORM"
```

---

## Task 3: Repository — BUILTIN_SKELETON_NODES + Tags + Reorder + Create

**Files:**
- Modify: `repository.py`

- [ ] **Step 1: Update BUILTIN_SKELETON_NODES with enriched data**

Replace the existing `BUILTIN_SKELETON_NODES` list (lines ~15-27 in `repository.py`) with:

```python
BUILTIN_SKELETON_NODES: list[dict] = [
    {
        "name": "项目概况", "sort_order": 0,
        "tags": ["overview", "architecture", "stack", "system"],
        "description": "项目基本信息、目标、技术栈总览、架构概览、外部依赖、系统边界说明",
        "prompt_hint": "记录项目是什么、解决什么问题、整体架构、技术栈总览、外部系统依赖",
    },
    {
        "name": "需求", "sort_order": 1,
        "tags": ["requirement", "user_story", "spec"],
        "description": "产品需求、用户故事、需求拆解、需求变更、待确认问题",
        "prompt_hint": "记录功能需求、用户故事、需求拆解、需求变更或待确认问题",
    },
    {
        "name": "设计", "sort_order": 2,
        "tags": ["design", "architecture", "api", "schema"],
        "description": "系统架构设计、接口设计、数据模型、流程设计、协议设计",
        "prompt_hint": "记录架构设计、接口定义、数据结构设计、流程设计或协议说明",
    },
    {
        "name": "技术栈", "sort_order": 3,
        "tags": ["stack", "tech", "dependency"],
        "description": "前后端技术选型、数据库、中间件、基础设施、外部服务",
        "prompt_hint": "记录技术选型：框架、数据库、ORM、中间件、消息队列、基础设施",
    },
    {
        "name": "前端", "sort_order": 4,
        "tags": ["frontend", "ui", "component", "reactive"],
        "description": "前端功能实现、组件设计、状态管理、性能优化、问题记录",
        "prompt_hint": "记录前端页面实现、组件设计、状态管理、联调问题或优化经验",
    },
    {
        "name": "后端", "sort_order": 5,
        "tags": ["backend", "api", "service", "logic"],
        "description": "后端接口实现、业务逻辑、服务拆分、异常处理、性能优化",
        "prompt_hint": "记录后端接口设计、业务逻辑、服务架构、异常处理或优化经验",
    },
    {
        "name": "数据库", "sort_order": 6,
        "tags": ["database", "sql", "index", "transaction"],
        "description": "表结构设计、索引策略、SQL优化、数据迁移、事务与一致性",
        "prompt_hint": "记录数据库设计、索引优化、SQL调优、迁移方案或一致性问题",
    },
    {
        "name": "测试", "sort_order": 7,
        "tags": ["testing", "qa", "mock", "e2e"],
        "description": "单元测试、集成测试、E2E测试、Mock方案、缺陷记录",
        "prompt_hint": "记录测试策略、测试工具、Mock方案、覆盖率或缺陷问题",
    },
    {
        "name": "部署", "sort_order": 8,
        "tags": ["deploy", "ci_cd", "devops", "infra"],
        "description": "环境配置、CI/CD、容器化、发布流程、运维与故障恢复",
        "prompt_hint": "记录部署流程、Docker配置、CI/CD、环境问题或发布经验",
    },
    {
        "name": "决策记录", "sort_order": 9,
        "tags": ["decision", "tradeoff", "architecture_choice"],
        "description": "关键技术决策、架构选择、方案对比、历史原因、权衡分析",
        "prompt_hint": "记录为什么这样做：背景、备选方案、选择原因与权衡",
    },
    {
        "name": "经验库", "sort_order": 10,
        "tags": ["experience", "best_practice", "pitfall", "debug"],
        "description": "开发技巧、调试技巧、性能优化、踩坑记录、最佳实践",
        "prompt_hint": "记录可复用经验：踩坑、调试方法、优化技巧、最佳实践",
    },
]
```

- [ ] **Step 2: Update `create_project_with_skeleton` to write tags**

In `repository.py`, inside `create_project_with_skeleton`, update the loop that creates builtin nodes (around line 425):

```python
        if existing_count.scalar_one() == 0:
            for n in BUILTIN_SKELETON_NODES:
                self.session.add(ProjectSkeletonNode(
                    project_id=project_id,
                    name=n["name"], description=n["description"],
                    prompt_hint=n["prompt_hint"], sort_order=n["sort_order"],
                    tags=n.get("tags", []),
                    is_builtin=True,
                ))
```

- [ ] **Step 3: Update `get_skeleton_tree` to include `tags` and `parent_id`**

Replace the `_build` inner function in `get_skeleton_tree` (around line 445):

```python
    async def get_skeleton_tree(self, project_id: uuid.UUID) -> list[dict]:
        result = await self.session.execute(
            select(ProjectSkeletonNode)
            .where(ProjectSkeletonNode.project_id == project_id)
            .order_by(ProjectSkeletonNode.sort_order, ProjectSkeletonNode.created_at)
        )
        nodes = result.scalars().all()
        children: dict = {}
        for n in nodes:
            children.setdefault(n.parent_id, []).append(n)

        def _build(parent_id):
            return [
                {
                    "id": str(n.id),
                    "name": n.name,
                    "description": n.description,
                    "prompt_hint": n.prompt_hint,
                    "is_builtin": n.is_builtin,
                    "sort_order": n.sort_order,
                    "parent_id": str(n.parent_id) if n.parent_id else None,
                    "tags": list(n.tags) if n.tags else [],
                    "children": _build(n.id),
                }
                for n in children.get(parent_id, [])
            ]
        return _build(None)
```

- [ ] **Step 4: Update `patch_skeleton_node` to accept tags**

Replace the method signature and body (around line 457):

```python
    async def patch_skeleton_node(
        self,
        node_id: uuid.UUID,
        *,
        name: str | None = None,
        prompt_hint: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        node = await self.session.get(ProjectSkeletonNode, node_id)
        if node is None:
            return False
        if name is not None and not node.is_builtin:
            node.name = name
        if prompt_hint is not None:
            node.prompt_hint = prompt_hint
        if tags is not None:
            node.tags = tags
        return True
```

- [ ] **Step 5: Add `create_skeleton_node` method**

After `patch_skeleton_node`, add:

```python
    async def create_skeleton_node(
        self,
        project_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None = None,
    ) -> dict:
        # Determine sort_order = max sibling sort_order + 10
        result = await self.session.execute(
            select(func.max(ProjectSkeletonNode.sort_order))
            .where(
                ProjectSkeletonNode.project_id == project_id,
                ProjectSkeletonNode.parent_id == parent_id,
            )
        )
        max_order = result.scalar_one_or_none() or 0
        node = ProjectSkeletonNode(
            project_id=project_id,
            parent_id=parent_id,
            name=name,
            is_builtin=False,
            sort_order=max_order + 10,
            tags=[],
        )
        self.session.add(node)
        await self.session.flush()
        return {
            "id": str(node.id),
            "name": node.name,
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "is_builtin": False,
            "sort_order": node.sort_order,
            "tags": [],
            "children": [],
        }
```

- [ ] **Step 6: Add `reorder_skeleton_nodes` method**

After `create_skeleton_node`, add:

```python
    async def reorder_skeleton_nodes(
        self, project_id: uuid.UUID, ordered_ids: list[uuid.UUID]
    ) -> None:
        for i, node_id in enumerate(ordered_ids):
            await self.session.execute(
                sa_update(ProjectSkeletonNode)
                .where(
                    ProjectSkeletonNode.id == node_id,
                    ProjectSkeletonNode.project_id == project_id,
                )
                .values(sort_order=i * 10)
            )
```

Note: `sa_update` is already imported as `from sqlalchemy import ... update as sa_update` in `repository.py`. Verify by checking the top of the file imports.

- [ ] **Step 7: Write unit test for new repository methods**

Create `tests/unit/test_skeleton_node_ops.py`:

```python
"""Unit tests for skeleton node repository operations (no DB required)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from memory_orchestrator_server.repository import BUILTIN_SKELETON_NODES


def test_builtin_skeleton_nodes_have_tags():
    for node in BUILTIN_SKELETON_NODES:
        assert "tags" in node, f"Node '{node['name']}' missing tags"
        assert isinstance(node["tags"], list)
        assert len(node["tags"]) > 0, f"Node '{node['name']}' has empty tags"


def test_builtin_skeleton_nodes_count():
    assert len(BUILTIN_SKELETON_NODES) == 11


def test_builtin_skeleton_nodes_sort_order():
    orders = [n["sort_order"] for n in BUILTIN_SKELETON_NODES]
    assert orders == list(range(11))
```

- [ ] **Step 8: Run unit tests**

```bash
uv run pytest tests/unit/test_skeleton_node_ops.py -v
```

Expected:
```
PASSED tests/unit/test_skeleton_node_ops.py::test_builtin_skeleton_nodes_have_tags
PASSED tests/unit/test_skeleton_node_ops.py::test_builtin_skeleton_nodes_count
PASSED tests/unit/test_skeleton_node_ops.py::test_builtin_skeleton_nodes_sort_order
```

- [ ] **Step 9: Commit**

```bash
git add repository.py tests/unit/test_skeleton_node_ops.py
git commit -m "feat: repository — tags support, create/reorder skeleton nodes, enriched BUILTIN_SKELETON_NODES"
```

---

## Task 4: API — Schemas + New Endpoints

**Files:**
- Modify: `routers/ui.py:103-106` (SkeletonNodePatch)

- [ ] **Step 1: Add `SkeletonNodeCreate` schema and update `SkeletonNodePatch`**

Replace the existing schemas at lines 103-108 in `routers/ui.py`:

```python
class SkeletonNodeCreate(BaseModel):
    project_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None = None


class SkeletonNodePatch(BaseModel):
    name: str | None = None
    prompt_hint: str | None = None
    tags: list[str] | None = None


class SkeletonNodeReorder(BaseModel):
    project_id: uuid.UUID
    ordered_ids: list[uuid.UUID]


class NodeMemoryAdd(BaseModel):
    memory_id: uuid.UUID
```

- [ ] **Step 2: Update `patch_skeleton_node` endpoint to pass tags**

Replace the endpoint at line ~743:

```python
    @router.patch("/skeleton-nodes/{node_id}", status_code=200)
    async def patch_skeleton_node(node_id: uuid.UUID, body: SkeletonNodePatch = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            ok = await repo.patch_skeleton_node(
                node_id, name=body.name, prompt_hint=body.prompt_hint, tags=body.tags
            )
            if not ok:
                raise HTTPException(status_code=404, detail="node not found")
            await s.commit()
        return {"ok": True}
```

- [ ] **Step 3: Add `POST /skeleton-nodes` create endpoint**

After the `patch_skeleton_node` endpoint and before `delete_skeleton_node`, add:

```python
    @router.post("/skeleton-nodes", status_code=201)
    async def create_skeleton_node(body: SkeletonNodeCreate = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            node = await repo.create_skeleton_node(
                project_id=body.project_id,
                name=body.name,
                parent_id=body.parent_id,
            )
            await s.commit()
        return node
```

- [ ] **Step 4: Add `POST /skeleton-nodes/reorder` endpoint**

After the `create_skeleton_node` endpoint, add:

```python
    @router.post("/skeleton-nodes/reorder", status_code=200)
    async def reorder_skeleton_nodes(body: SkeletonNodeReorder = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            await repo.reorder_skeleton_nodes(body.project_id, body.ordered_ids)
            await s.commit()
        return {"ok": True}
```

- [ ] **Step 5: Smoke-test the API**

```bash
uv run mo-server serve-http &
sleep 2

# Check healthz
curl -s http://localhost:8765/healthz

# The new endpoints exist (will 422 without auth/body — that's fine)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8765/api/skeleton-nodes
# Expected: 401 or 422 (not 404)

curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8765/api/skeleton-nodes/reorder
# Expected: 401 or 422 (not 404)

kill %1
```

- [ ] **Step 6: Commit**

```bash
git add routers/ui.py
git commit -m "feat: API — SkeletonNodeCreate/Reorder schemas, create + reorder endpoints, tags in patch"
```

---

## Task 5: `SkNode.vue` — Standalone Recursive Node

**Files:**
- Create: `frontend/src/SkNode.vue`

This component renders a single tree node recursively. It emits all interactions upward.

- [ ] **Step 1: Create `SkNode.vue`**

```vue
<!-- frontend/src/SkNode.vue -->
<template>
  <li
    class="sk-node"
    :draggable="true"
    @dragstart.stop="onDragStart"
    @dragover.stop.prevent="onDragOver"
    @dragleave.stop="onDragLeave"
    @drop.stop="onDrop"
    @dragend.stop="onDragEnd"
  >
    <div
      :class="['sk-node-row', { active: selectedId === node.id, dragging: isDragging, 'drop-above': isDragOver === 'above', 'drop-below': isDragOver === 'below' }]"
      @click="$emit('select', node)"
      @contextmenu.prevent="onContextMenu"
      @mouseenter="startTooltip"
      @mouseleave="cancelTooltip"
    >
      <span class="sk-drag-handle">⠿</span>
      <span class="sk-chevron" @click.stop="toggleExpand">
        <span v-if="node.children?.length">{{ expanded ? '▼' : '▶' }}</span>
        <span v-else style="opacity:0">▶</span>
      </span>
      <span class="sk-emoji">{{ nodeEmoji }}</span>
      <span v-if="!editing" class="sk-node-name">{{ node.name }}</span>
      <input
        v-else
        ref="editInput"
        class="sk-node-edit-input"
        v-model="editName"
        @blur="saveEdit"
        @keydown.enter="saveEdit"
        @keydown.esc="editing = false"
      />
      <span v-if="memCount > 0" class="sk-node-badge">{{ memCount }}</span>
      <span v-for="tag in (node.tags || []).slice(0, 2)" :key="tag" class="sk-node-tag">{{ tag }}</span>
    </div>

    <!-- Tooltip via Teleport -->
    <Teleport to="body">
      <div v-if="showTooltip" class="sk-tooltip" :style="tooltipStyle">
        <div class="sk-tooltip-name">{{ nodeEmoji }} {{ node.name }}</div>
        <div v-if="node.prompt_hint" class="sk-tooltip-hint">{{ node.prompt_hint.slice(0, 80) }}</div>
        <div class="sk-tooltip-stats">
          <span>记忆 {{ memCount }}</span>
          <span>子节点 {{ node.children?.length || 0 }}</span>
        </div>
        <div v-if="node.tags?.length" class="sk-tooltip-tags">
          <span v-for="t in node.tags" :key="t" class="sk-tooltip-tag">{{ t }}</span>
        </div>
      </div>
    </Teleport>

    <!-- Children -->
    <ul v-if="expanded && node.children?.length" class="sk-tree sk-subtree">
      <SkNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :selected-id="selectedId"
        :depth="depth + 1"
        @select="$emit('select', $event)"
        @patch="$emit('patch', $event)"
        @delete="$emit('delete', $event)"
        @context-menu="$emit('context-menu', $event)"
        @reorder="$emit('reorder', $event)"
      />
    </ul>
  </li>
</template>

<script setup>
import { ref, computed, nextTick, inject } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  selectedId: { type: String, default: null },
  depth: { type: Number, default: 0 },
})

const emit = defineEmits(['select', 'patch', 'delete', 'context-menu', 'reorder'])

// ── Expand/collapse ──────────────────────────────────────────────────────────
const expanded = ref(true)
function toggleExpand() { expanded.value = !expanded.value }

// Expose so SkeletonTreePanel can force-expand on search
defineExpose({ forceExpand: () => { expanded.value = true } })

// ── Emoji map ────────────────────────────────────────────────────────────────
const EMOJI_MAP = {
  '项目概况': '📌', '需求': '📋', '设计': '🎨', '技术栈': '🔧',
  '前端': '🖥', '后端': '⚙️', '数据库': '🗄️', '测试': '🧪',
  '部署': '🚀', '决策记录': '📝', '经验库': '💡',
}
const nodeEmoji = computed(() => EMOJI_MAP[props.node.name] || '📄')

// ── Memory count ─────────────────────────────────────────────────────────────
// Injected from SkeletonTreePanel which tracks per-node memory counts
const memoryCountMap = inject('memoryCountMap', {})
const memCount = computed(() => memoryCountMap[props.node.id] || 0)

// ── Inline edit ──────────────────────────────────────────────────────────────
const editing = ref(false)
const editName = ref('')
const editInput = ref(null)

function startEdit() {
  if (props.node.is_builtin) return
  editName.value = props.node.name
  editing.value = true
  nextTick(() => editInput.value?.focus())
}

function saveEdit() {
  if (editName.value && editName.value !== props.node.name) {
    emit('patch', { id: props.node.id, patch: { name: editName.value } })
  }
  editing.value = false
}

// Exposed for context menu rename action
defineExpose({ startEdit, forceExpand: () => { expanded.value = true } })

// ── Context menu ─────────────────────────────────────────────────────────────
function onContextMenu(e) {
  emit('context-menu', { x: e.clientX, y: e.clientY, node: props.node, depth: props.depth })
}

// ── Tooltip ──────────────────────────────────────────────────────────────────
const showTooltip = ref(false)
const tooltipStyle = ref({})
let tooltipTimer = null
const nodeRow = ref(null)

function startTooltip(e) {
  tooltipTimer = setTimeout(() => {
    const rect = e.currentTarget.getBoundingClientRect()
    tooltipStyle.value = {
      position: 'fixed',
      left: rect.right + 10 + 'px',
      top: rect.top + 'px',
      zIndex: 9999,
    }
    showTooltip.value = true
  }, 500)
}

function cancelTooltip() {
  clearTimeout(tooltipTimer)
  showTooltip.value = false
}

// ── Drag and drop ────────────────────────────────────────────────────────────
const isDragging = ref(false)
const isDragOver = ref(null) // 'above' | 'below' | null

function onDragStart(e) {
  isDragging.value = true
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', props.node.id)
}

function onDragOver(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const mid = rect.top + rect.height / 2
  isDragOver.value = e.clientY < mid ? 'above' : 'below'
}

function onDragLeave() {
  isDragOver.value = null
}

function onDrop(e) {
  const draggedId = e.dataTransfer.getData('text/plain')
  if (draggedId === props.node.id) { isDragOver.value = null; return }
  emit('reorder', { draggedId, targetId: props.node.id, position: isDragOver.value })
  isDragOver.value = null
}

function onDragEnd() {
  isDragging.value = false
  isDragOver.value = null
}
</script>

<style scoped>
.sk-node { list-style: none; }
.sk-node-row {
  display: flex; align-items: center; padding: 3px 6px; border-radius: 4px;
  cursor: pointer; font-size: 12px; gap: 3px; user-select: none;
  border-top: 2px solid transparent; border-bottom: 2px solid transparent;
}
.sk-node-row:hover { background: var(--hover, #161b22); }
.sk-node-row.active { background: var(--active-bg, #1d2d3e); }
.sk-node-row.active .sk-node-name { color: var(--accent, #58a6ff); }
.sk-node-row.dragging { opacity: 0.4; }
.sk-node-row.drop-above { border-top-color: var(--accent, #58a6ff); }
.sk-node-row.drop-below { border-bottom-color: var(--accent, #58a6ff); }
.sk-drag-handle { color: var(--fg-muted, #6e7681); font-size: 10px; cursor: grab; flex-shrink: 0; }
.sk-chevron { font-size: 8px; color: var(--fg-muted, #6e7681); width: 12px; text-align: center; flex-shrink: 0; }
.sk-emoji { font-size: 12px; flex-shrink: 0; }
.sk-node-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--fg, #c9d1d9); }
.sk-node-edit-input { flex: 1; border: 1px solid var(--accent, #58a6ff); border-radius: 3px; padding: 1px 4px; font-size: 12px; background: var(--input-bg, #161b22); color: var(--fg, #e6edf3); }
.sk-node-badge { font-size: 9px; color: var(--fg-muted, #6e7681); background: var(--btn-bg, #21262d); border-radius: 8px; padding: 1px 5px; flex-shrink: 0; }
.sk-node-tag { font-size: 9px; background: var(--tag-bg, #1a3a52); color: var(--accent, #58a6ff); border-radius: 3px; padding: 1px 4px; flex-shrink: 0; }
.sk-tree { list-style: none; padding: 0; margin: 0; }
.sk-subtree { padding-left: 16px; }
/* Tooltip */
.sk-tooltip {
  background: var(--tooltip-bg, #1c2128); border: 1px solid var(--border, #30363d);
  border-radius: 8px; padding: 10px 12px; max-width: 240px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5); pointer-events: none;
}
.sk-tooltip-name { font-size: 12px; font-weight: 700; color: var(--fg, #e6edf3); margin-bottom: 4px; }
.sk-tooltip-hint { font-size: 10px; color: var(--fg-muted, #8b949e); margin-bottom: 6px; font-style: italic; line-height: 1.5; }
.sk-tooltip-stats { display: flex; gap: 12px; font-size: 10px; color: var(--fg-muted, #6e7681); margin-bottom: 4px; }
.sk-tooltip-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.sk-tooltip-tag { font-size: 9px; background: var(--tag-bg, #1a3a52); color: var(--accent, #58a6ff); border-radius: 3px; padding: 1px 4px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/SkNode.vue
git commit -m "feat: SkNode.vue — emoji, drag-drop, tooltip, context-menu emit, inline edit"
```

---

## Task 6: `ContextMenu.vue`

**Files:**
- Create: `frontend/src/ContextMenu.vue`

- [ ] **Step 1: Create `ContextMenu.vue`**

```vue
<!-- frontend/src/ContextMenu.vue -->
<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="ctx-menu"
      :style="menuStyle"
      @click.stop
    >
      <div
        :class="['ctx-item', { disabled: depth >= 2 }]"
        @click="depth < 2 && emit('add-child')"
      >
        <span class="ctx-icon">➕</span>
        添加子节点
        <span v-if="depth >= 2" class="ctx-dim">已达上限</span>
      </div>
      <div class="ctx-item" @click="emit('rename')">
        <span class="ctx-icon">✏️</span>
        重命名
        <span class="ctx-shortcut">F2</span>
      </div>
      <div class="ctx-item" @click="emit('manage-tags')">
        <span class="ctx-icon">🏷️</span>
        管理标签
      </div>
      <div class="ctx-sep"></div>
      <div class="ctx-item danger" @click="emit('delete')">
        <span class="ctx-icon">🗑</span>
        删除节点
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  depth: { type: Number, default: 0 },
})

const emit = defineEmits(['add-child', 'rename', 'manage-tags', 'delete', 'close'])

const menuStyle = computed(() => {
  const w = 160, h = 160
  const left = props.x + w > window.innerWidth ? props.x - w : props.x
  const top = props.y + h > window.innerHeight ? props.y - h : props.y
  return { position: 'fixed', left: left + 'px', top: top + 'px', zIndex: 9999 }
})
</script>

<style scoped>
.ctx-menu {
  background: var(--tooltip-bg, #161b22); border: 1px solid var(--border, #30363d);
  border-radius: 8px; padding: 4px; min-width: 160px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
}
.ctx-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  font-size: 11px; border-radius: 5px; cursor: pointer; color: var(--fg, #c9d1d9);
}
.ctx-item:hover:not(.disabled) { background: var(--btn-bg, #21262d); }
.ctx-item.disabled { color: var(--fg-muted, #6e7681); cursor: not-allowed; }
.ctx-item.danger { color: #ff7b72; }
.ctx-item.danger:hover { background: #ff7b7211; }
.ctx-icon { width: 16px; text-align: center; font-size: 12px; }
.ctx-shortcut { margin-left: auto; font-size: 9px; color: var(--fg-muted, #6e7681); background: var(--btn-bg, #21262d); padding: 1px 5px; border-radius: 3px; }
.ctx-dim { margin-left: auto; font-size: 9px; color: var(--fg-muted, #6e7681); }
.ctx-sep { height: 1px; background: var(--border, #30363d); margin: 3px 6px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/ContextMenu.vue
git commit -m "feat: ContextMenu.vue — right-click menu with depth-aware add-child"
```

---

## Task 7: `TagPicker.vue`

**Files:**
- Create: `frontend/src/TagPicker.vue`

- [ ] **Step 1: Create `TagPicker.vue`**

```vue
<!-- frontend/src/TagPicker.vue -->
<template>
  <div class="tag-picker">
    <div class="tag-chips">
      <span v-for="tag in modelValue" :key="tag" class="tag-chip">
        {{ tag }}
        <button class="chip-rm" @click="removeTag(tag)">×</button>
      </span>
    </div>
    <div class="tag-input-wrap">
      <input
        ref="inputEl"
        v-model="query"
        class="tag-input"
        placeholder="搜索或新建标签…"
        @input="onInput"
        @keydown.enter.prevent="selectFirst"
        @keydown.escape="query = ''"
        @focus="showSuggestions = true"
        @blur="onBlur"
      />
    </div>
    <ul v-if="showSuggestions && (suggestions.length || query)" class="tag-suggestions">
      <li
        v-for="s in suggestions"
        :key="s"
        class="tag-sug"
        @mousedown.prevent="addTag(s)"
        v-html="highlight(s)"
      ></li>
      <li
        v-if="query && !suggestions.includes(query)"
        class="tag-create"
        @mousedown.prevent="addTag(query)"
      >
        + 创建 "{{ query }}"
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const query = ref('')
const showSuggestions = ref(false)
const inputEl = ref(null)

const suggestions = computed(() => {
  if (!query.value) return props.allTags.filter(t => !props.modelValue.includes(t)).slice(0, 8)
  const q = query.value.toLowerCase()
  return props.allTags.filter(t => t.toLowerCase().includes(q) && !props.modelValue.includes(t)).slice(0, 8)
})

function highlight(tag) {
  if (!query.value) return tag
  const idx = tag.toLowerCase().indexOf(query.value.toLowerCase())
  if (idx === -1) return tag
  return tag.slice(0, idx) + '<mark>' + tag.slice(idx, idx + query.value.length) + '</mark>' + tag.slice(idx + query.value.length)
}

function addTag(tag) {
  const clean = tag.trim().replace(/^#/, '')
  if (!clean || props.modelValue.includes(clean)) return
  emit('update:modelValue', [...props.modelValue, clean])
  query.value = ''
  showSuggestions.value = false
}

function removeTag(tag) {
  emit('update:modelValue', props.modelValue.filter(t => t !== tag))
}

function selectFirst() {
  if (suggestions.value.length) addTag(suggestions.value[0])
  else if (query.value) addTag(query.value)
}

function onInput() { showSuggestions.value = true }
function onBlur() { setTimeout(() => { showSuggestions.value = false }, 150) }
</script>

<style scoped>
.tag-picker { display: flex; flex-direction: column; gap: 6px; }
.tag-chips { display: flex; flex-wrap: wrap; gap: 4px; min-height: 20px; }
.tag-chip {
  display: inline-flex; align-items: center; gap: 3px;
  background: var(--tag-bg, #1a3a52); color: var(--accent, #58a6ff);
  border-radius: 10px; font-size: 10px; padding: 2px 8px;
  border: 1px solid var(--accent-dim, #1f6feb44);
}
.chip-rm { background: none; border: none; color: var(--fg-muted, #6e7681); cursor: pointer; font-size: 11px; padding: 0; line-height: 1; }
.chip-rm:hover { color: #ff7b72; }
.tag-input-wrap { position: relative; }
.tag-input {
  width: 100%; background: var(--input-bg, #0d1117); border: 1px solid var(--border, #30363d);
  border-radius: 5px; padding: 5px 8px; font-size: 11px; color: var(--fg, #c9d1d9);
  font-family: inherit; outline: none;
}
.tag-input:focus { border-color: var(--accent, #58a6ff); }
.tag-suggestions {
  list-style: none; padding: 4px; margin: 0;
  background: var(--tooltip-bg, #161b22); border: 1px solid var(--border, #30363d);
  border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}
.tag-sug, .tag-create {
  padding: 5px 8px; font-size: 11px; border-radius: 4px; cursor: pointer;
  color: var(--fg, #c9d1d9);
}
.tag-sug:hover, .tag-create:hover { background: var(--btn-bg, #21262d); }
.tag-create { color: #3fb950; }
.tag-sug :deep(mark) { background: transparent; color: var(--accent, #58a6ff); font-style: normal; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/TagPicker.vue
git commit -m "feat: TagPicker.vue — fuzzy tag autocomplete, create new tags, chip removal"
```

---

## Task 8: `ProjectIconStrip.vue`

**Files:**
- Create: `frontend/src/ProjectIconStrip.vue`

- [ ] **Step 1: Create `ProjectIconStrip.vue`**

```vue
<!-- frontend/src/ProjectIconStrip.vue -->
<template>
  <div class="icon-strip">
    <button
      v-for="p in projects"
      :key="p.id"
      :class="['proj-icon', { active: p.id === activeId }]"
      :title="p.display_name || p.slug"
      @click="$emit('select', p)"
    >
      {{ initials(p.display_name || p.slug) }}
    </button>
    <div class="strip-divider"></div>
    <button class="proj-icon add-btn" title="新建项目" @click="$emit('create')">+</button>
  </div>
</template>

<script setup>
defineProps({
  projects: { type: Array, default: () => [] },
  activeId: { type: String, default: null },
})
defineEmits(['select', 'create'])

function initials(name) {
  return name.split(/[\s\-_\/]/).map(w => w[0]).join('').toUpperCase().slice(0, 2) || '?'
}
</script>

<style scoped>
.icon-strip {
  width: 52px; flex-shrink: 0;
  background: #010409; border-right: 1px solid var(--border, #30363d);
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 0; gap: 5px; overflow-y: auto;
}
.proj-icon {
  width: 32px; height: 32px; border-radius: 7px; border: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 800; cursor: pointer;
  color: var(--fg-muted, #8b949e); background: var(--btn-bg, #161b22);
  transition: all 0.15s; flex-shrink: 0;
}
.proj-icon:hover { background: var(--hover, #21262d); color: var(--fg, #c9d1d9); }
.proj-icon.active { background: var(--active-bg, #1d2d3e); color: var(--accent, #58a6ff); box-shadow: 0 0 0 1.5px var(--accent, #58a6ff); }
.add-btn { font-size: 16px; font-weight: 400; color: #3fb950; }
.add-btn:hover { color: #56d364; }
.strip-divider { width: 24px; height: 1px; background: var(--border, #30363d); margin: 2px 0; flex-shrink: 0; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/ProjectIconStrip.vue
git commit -m "feat: ProjectIconStrip.vue — icon strip project switcher with initials"
```

---

## Task 9: `SkeletonTreePanel.vue`

**Files:**
- Create: `frontend/src/SkeletonTreePanel.vue`

This is the tree container. It owns search state and handles drag-drop reorder logic before emitting `reorder` upward.

- [ ] **Step 1: Create `SkeletonTreePanel.vue`**

```vue
<!-- frontend/src/SkeletonTreePanel.vue -->
<template>
  <div class="tree-panel">
    <div class="tree-header">
      <div class="tree-proj-name">{{ projName }}</div>
      <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input v-model="searchQuery" class="search-input" placeholder="搜索节点…" />
        <span v-if="searchQuery" class="search-count">{{ matchCount }} 结果</span>
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">×</button>
      </div>
    </div>

    <ul class="sk-tree tree-scroll">
      <SkNode
        v-for="node in visibleRoots"
        :key="node.id"
        :node="node"
        :selected-id="selectedId"
        :depth="0"
        :class="{ faded: searchQuery && !matchIds.has(node.id) && !hasMatchDescendant(node) }"
        @select="$emit('select', $event)"
        @patch="$emit('patch', $event)"
        @delete="$emit('delete', $event)"
        @context-menu="$emit('context-menu', $event)"
        @reorder="handleReorder"
      />
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, provide } from 'vue'
import SkNode from './SkNode.vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },   // nested tree from API
  selectedId: { type: String, default: null },
  projName: { type: String, default: '' },
  memoryCountMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select', 'patch', 'delete', 'context-menu', 'reorder', 'add-child'])

// Inject memory count map into SkNode descendants
provide('memoryCountMap', computed(() => props.memoryCountMap))

// ── Search ────────────────────────────────────────────────────────────────────
const searchQuery = ref('')

// Flatten nested tree to find matches
function flattenTree(nodes, acc = []) {
  for (const n of nodes) {
    acc.push(n)
    if (n.children?.length) flattenTree(n.children, acc)
  }
  return acc
}

const flatNodes = computed(() => flattenTree(props.nodes))

const matchIds = computed(() => {
  if (!searchQuery.value) return new Set()
  const q = searchQuery.value.toLowerCase()
  const ids = new Set()
  for (const n of flatNodes.value) {
    if (n.name.toLowerCase().includes(q)) ids.add(n.id)
  }
  return ids
})

const matchCount = computed(() => matchIds.value.size)

function hasMatchDescendant(node) {
  if (matchIds.value.has(node.id)) return true
  return (node.children || []).some(c => hasMatchDescendant(c))
}

// When searching, show all nodes; fading is done via CSS class on SkNode wrapper
const visibleRoots = computed(() => props.nodes)

// ── Drag-drop reorder ─────────────────────────────────────────────────────────
function handleReorder({ draggedId, targetId, position }) {
  // Find the siblings array containing both nodes
  const siblingsRef = findSiblingsContaining(props.nodes, draggedId, targetId)
  if (!siblingsRef) return

  const siblings = [...siblingsRef]
  const fromIdx = siblings.findIndex(n => n.id === draggedId)
  const toIdx = siblings.findIndex(n => n.id === targetId)
  if (fromIdx === -1 || toIdx === -1) return

  // Reorder
  const [removed] = siblings.splice(fromIdx, 1)
  const insertAt = position === 'above' ? (fromIdx < toIdx ? toIdx - 1 : toIdx) : (fromIdx < toIdx ? toIdx : toIdx + 1)
  siblings.splice(insertAt, 0, removed)

  emit('reorder', siblings.map(n => n.id))
}

function findSiblingsContaining(nodes, id1, id2) {
  // Both nodes must be at same level
  const ids = nodes.map(n => n.id)
  if (ids.includes(id1) && ids.includes(id2)) return nodes
  for (const n of nodes) {
    if (n.children?.length) {
      const found = findSiblingsContaining(n.children, id1, id2)
      if (found) return found
    }
  }
  return null
}
</script>

<style scoped>
.tree-panel {
  width: 220px; flex-shrink: 0;
  background: var(--bg, #0d1117); border-right: 1px solid var(--border, #30363d);
  display: flex; flex-direction: column; overflow: hidden;
}
.tree-header { padding: 10px 10px 6px; border-bottom: 1px solid var(--border, #21262d); flex-shrink: 0; }
.tree-proj-name { font-size: 12px; font-weight: 700; color: var(--fg, #e6edf3); margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.search-wrap {
  display: flex; align-items: center; gap: 5px;
  background: var(--input-bg, #161b22); border: 1px solid var(--border, #30363d);
  border-radius: 5px; padding: 4px 8px;
}
.search-icon { font-size: 10px; color: var(--fg-muted, #6e7681); flex-shrink: 0; }
.search-input { background: none; border: none; outline: none; font-size: 11px; color: var(--fg, #c9d1d9); width: 100%; font-family: inherit; }
.search-count { font-size: 9px; color: var(--fg-muted, #6e7681); flex-shrink: 0; white-space: nowrap; }
.search-clear { background: none; border: none; color: var(--fg-muted, #6e7681); cursor: pointer; font-size: 13px; padding: 0; line-height: 1; flex-shrink: 0; }
.tree-scroll { flex: 1; overflow-y: auto; padding: 4px 0; list-style: none; margin: 0; }
.faded { opacity: 0.35; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/SkeletonTreePanel.vue
git commit -m "feat: SkeletonTreePanel.vue — search/highlight, drag-drop reorder logic, fading"
```

---

## Task 10: `NodeDetailPanel.vue`

**Files:**
- Create: `frontend/src/NodeDetailPanel.vue`

- [ ] **Step 1: Create `NodeDetailPanel.vue`**

```vue
<!-- frontend/src/NodeDetailPanel.vue -->
<template>
  <div class="detail-panel" v-if="node">
    <div class="detail-header">
      <span class="detail-emoji">{{ nodeEmoji }}</span>
      <span class="detail-title">{{ node.name }}</span>
      <button class="btn-sm btn-primary" @click="$emit('add-memory')">+ 添加记忆</button>
    </div>

    <div class="detail-body">
      <!-- Tags -->
      <section class="detail-section">
        <div class="detail-label">标签</div>
        <TagPicker
          :model-value="node.tags || []"
          :all-tags="allTags"
          @update:model-value="$emit('update-tags', $event)"
        />
      </section>

      <!-- Prompt hint -->
      <section class="detail-section">
        <div class="detail-label">Prompt Hint</div>
        <input
          class="sk-input"
          :value="hintDraft"
          @input="hintDraft = $event.target.value"
          @blur="saveHint"
          @keydown.enter="saveHint"
          placeholder="引导提示…"
        />
      </section>

      <!-- Memories -->
      <section class="detail-section">
        <div class="detail-label">记忆（{{ memories.length }}）</div>
        <ul class="mem-list">
          <li v-for="m in memories" :key="m.id" class="mem-item">
            <span :class="['badge', m.type]">{{ m.type }}</span>
            <span class="mem-name" :title="m.description">{{ m.name }}</span>
            <button class="btn-unlink" @click="$emit('unlink-memory', m.id)" title="取消关联">×</button>
          </li>
        </ul>
      </section>
    </div>
  </div>
  <div class="detail-empty" v-else>
    <span>选择左侧节点查看详情</span>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import TagPicker from './TagPicker.vue'

const props = defineProps({
  node: { type: Object, default: null },
  memories: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['save-hint', 'update-tags', 'add-memory', 'unlink-memory'])

const EMOJI_MAP = {
  '项目概况': '📌', '需求': '📋', '设计': '🎨', '技术栈': '🔧',
  '前端': '🖥', '后端': '⚙️', '数据库': '🗄️', '测试': '🧪',
  '部署': '🚀', '决策记录': '📝', '经验库': '💡',
}
const nodeEmoji = computed(() => EMOJI_MAP[props.node?.name] || '📄')

const hintDraft = ref(props.node?.prompt_hint || '')
watch(() => props.node?.id, () => { hintDraft.value = props.node?.prompt_hint || '' })

function saveHint() {
  if (hintDraft.value !== props.node?.prompt_hint) {
    emit('save-hint', hintDraft.value)
  }
}
</script>

<style scoped>
.detail-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg, #0d1117); }
.detail-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--fg-muted, #6e7681); font-size: 13px; }
.detail-header {
  display: flex; align-items: center; gap: 8px; padding: 12px 16px 10px;
  border-bottom: 1px solid var(--border, #21262d); flex-shrink: 0;
}
.detail-emoji { font-size: 18px; }
.detail-title { font-size: 14px; font-weight: 700; flex: 1; color: var(--fg, #e6edf3); }
.detail-body { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 14px; }
.detail-section { display: flex; flex-direction: column; gap: 6px; }
.detail-label { font-size: 10px; font-weight: 700; color: var(--fg-muted, #6e7681); text-transform: uppercase; letter-spacing: 0.05em; }
.sk-input { border: 1px solid var(--border, #30363d); border-radius: 5px; padding: 6px 8px; font-size: 12px; font-family: inherit; background: var(--input-bg, #161b22); color: var(--fg, #e6edf3); width: 100%; outline: none; }
.sk-input:focus { border-color: var(--accent, #58a6ff); }
.mem-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.mem-item { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border: 1px solid var(--border, #21262d); border-radius: 5px; font-size: 12px; }
.mem-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fg, #c9d1d9); }
.btn-unlink { background: none; border: none; color: var(--fg-muted, #6e7681); cursor: pointer; font-size: 14px; padding: 0 2px; line-height: 1; }
.btn-unlink:hover { color: #ff7b72; }
.badge { font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; }
.badge.feedback { background: #3a2a10; color: #f0883e; }
.badge.project { background: #1a2a3a; color: #58a6ff; }
.badge.reference { background: #1a2a1a; color: #3fb950; }
.badge.user { background: #2a1a3a; color: #d2a8ff; }
.btn-sm { padding: 4px 10px; border-radius: 5px; border: 1px solid transparent; font-size: 11px; cursor: pointer; }
.btn-primary { background: var(--accent, #2563eb); color: #fff; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/NodeDetailPanel.vue
git commit -m "feat: NodeDetailPanel.vue — tags, prompt hint, memories list"
```

---

## Task 11: `SkeletonPage.vue` — Refactor to Orchestrator

**Files:**
- Modify: `frontend/src/SkeletonPage.vue` (full rewrite)

- [ ] **Step 1: Replace `SkeletonPage.vue` with orchestrator**

Replace the entire contents of `frontend/src/SkeletonPage.vue`:

```vue
<!-- frontend/src/SkeletonPage.vue -->
<template>
  <div class="sk-app" :class="{ dark: isDark }">
    <!-- Login overlay -->
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
      <AppHeader
        :isDark="isDark" :lang="lang" :loginOpen="loginOpen"
        @toggle-theme="isDark = !isDark" @toggle-lang="toggleLang"
        @open-settings="router.push('/settings')"
        @open-admin="router.push('/tokens')"
        @logout="logout"
      >
        <template #nav>
          <router-link to="/memories">→ Memories</router-link>
        </template>
      </AppHeader>

      <div class="sk-body">
        <!-- Column 1: Icon strip -->
        <ProjectIconStrip
          :projects="projects"
          :activeId="selectedProject?.id"
          @select="selectProject"
          @create="openNewProjectModal"
        />

        <!-- Column 2: Tree panel -->
        <SkeletonTreePanel
          v-if="selectedProject"
          :nodes="skeletonTree"
          :selectedId="selectedNode?.id"
          :projName="selectedProject.display_name || selectedProject.slug"
          :memoryCountMap="memoryCountMap"
          @select="selectNode"
          @patch="onPatch"
          @delete="onDelete"
          @context-menu="openContextMenu"
          @reorder="onReorder"
        />
        <div v-else class="tree-empty">选择或创建项目</div>

        <!-- Column 3: Detail panel -->
        <NodeDetailPanel
          :node="selectedNode"
          :memories="nodeMemories"
          :all-tags="allTags"
          @save-hint="onSaveHint"
          @update-tags="onUpdateTags"
          @add-memory="addMemoryOpen = true"
          @unlink-memory="unlinkMemory"
        />
      </div>
    </template>

    <!-- Context menu -->
    <ContextMenu
      :visible="ctxVisible"
      :x="ctxX"
      :y="ctxY"
      :depth="ctxDepth"
      @add-child="onAddChild"
      @rename="onRenameNode"
      @manage-tags="focusTags"
      @delete="onDeleteNode"
    />

    <!-- New project modal -->
    <div v-if="newProjectOpen" class="modal-overlay" @click.self="newProjectOpen = false">
      <div class="modal" style="max-width:380px">
        <div class="modal-header">
          <span class="modal-title">新建项目</span>
          <button class="modal-close" @click="newProjectOpen = false">✕</button>
        </div>
        <div style="padding:16px;display:flex;flex-direction:column;gap:10px">
          <input class="sk-input" v-model="newProjectName" placeholder="项目名称…"
            @keydown.enter="createProject" ref="newProjectInput" />
          <button class="btn-save" :disabled="!newProjectName || isCreatingProject" @click="createProject">
            {{ isCreatingProject ? '创建中…' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Add memory modal -->
    <div v-if="addMemoryOpen" class="modal-overlay" @click.self="addMemoryOpen = false">
      <div class="write-modal">
        <div class="write-header">
          <span class="write-title">新记忆 → {{ selectedNode?.name }}</span>
          <button class="modal-close" @click="addMemoryOpen = false">✕</button>
        </div>
        <div class="write-body">
          <p v-if="selectedNode?.prompt_hint" class="sk-prompt-hint-text">{{ selectedNode.prompt_hint }}</p>
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
          <p v-if="memError" class="save-hint err">{{ memError }}</p>
        </div>
        <div class="write-footer">
          <button class="btn-cancel" @click="addMemoryOpen = false">Cancel</button>
          <button class="btn-save" :disabled="isMemSaving || !memForm.name || !memForm.content" @click="submitAddMemory">
            {{ isMemSaving ? 'Saving…' : 'Write' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { BASE, apiFetch, apiJSON } from './api.js'
import AppHeader from './AppHeader.vue'
import ProjectIconStrip from './ProjectIconStrip.vue'
import SkeletonTreePanel from './SkeletonTreePanel.vue'
import NodeDetailPanel from './NodeDetailPanel.vue'
import ContextMenu from './ContextMenu.vue'

const router = useRouter()

// ── Theme + lang ──────────────────────────────────────────────────────────────
const isDark = ref(
  document.documentElement.getAttribute('data-theme') === 'dark' ||
  (!document.documentElement.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)
)
watch(isDark, v => document.documentElement.setAttribute('data-theme', v ? 'dark' : 'light'))
const lang = ref(localStorage.getItem('mo-lang') || 'en')
function toggleLang() { lang.value = lang.value === 'en' ? 'zh' : 'en'; localStorage.setItem('mo-lang', lang.value) }

// ── Auth ──────────────────────────────────────────────────────────────────────
const loginOpen = ref(false)
const loginInput = ref('')
const loginError = ref('')
const loginLoading = ref(false)

async function submitLogin() {
  loginLoading.value = true; loginError.value = ''
  try {
    const r = await fetch(`${BASE}/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: loginInput.value }),
    })
    if (r.status === 401) { loginError.value = 'Invalid token'; return }
    loginOpen.value = false; loginInput.value = ''
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

async function logout() {
  await fetch(`${BASE}/logout`, { method: 'POST' })
  loginOpen.value = true
}

// ── Projects ──────────────────────────────────────────────────────────────────
const projects = ref([])
const selectedProject = ref(null)

async function loadProjects() {
  try {
    const r = await apiFetch(`${BASE}/projects`)
    if (r.status === 401) { loginOpen.value = true; return }
    projects.value = await r.json()
  } catch { loginOpen.value = true }
}

async function selectProject(p) {
  selectedProject.value = p
  selectedNode.value = null
  nodeMemories.value = []
  await loadSkeleton(p.id)
}

const newProjectOpen = ref(false)
const newProjectName = ref('')
const isCreatingProject = ref(false)
const newProjectInput = ref(null)

function openNewProjectModal() {
  newProjectName.value = ''
  newProjectOpen.value = true
  nextTick(() => newProjectInput.value?.focus())
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
    newProjectOpen.value = false
    await loadProjects()
    await selectProject(p)
  } catch (e) { alert(e.message) }
  finally { isCreatingProject.value = false }
}

// ── Skeleton tree ─────────────────────────────────────────────────────────────
const skeletonTree = ref([])
const selectedNode = ref(null)
const nodeMemories = ref([])

// Flat list of all nodes for allTags computation
function flattenTree(nodes, acc = []) {
  for (const n of nodes) { acc.push(n); if (n.children?.length) flattenTree(n.children, acc) }
  return acc
}
const flatNodes = computed(() => flattenTree(skeletonTree.value))
const allTags = computed(() => [...new Set(flatNodes.value.flatMap(n => n.tags || []))].sort())

// memoryCountMap: updated after loading memories
const memoryCountMap = ref({})

async function loadSkeleton(projectId) {
  skeletonTree.value = await apiJSON(`${BASE}/projects/${projectId}/skeleton`)
}

async function selectNode(node) {
  selectedNode.value = node
  nodeMemories.value = await apiJSON(`${BASE}/skeleton-nodes/${node.id}/memories`)
  memoryCountMap.value = { ...memoryCountMap.value, [node.id]: nodeMemories.value.length }
}

// ── Patch / delete ────────────────────────────────────────────────────────────
async function onPatch({ id, patch }) {
  await apiFetch(`${BASE}/skeleton-nodes/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  await loadSkeleton(selectedProject.value.id)
  // Update selectedNode if it was patched
  if (selectedNode.value?.id === id) {
    const updated = flatNodes.value.find(n => n.id === id)
    if (updated) selectedNode.value = updated
  }
}

async function onDelete(nodeId) {
  if (!confirm('删除此节点并取消关联其记忆？')) return
  const r = await apiFetch(`${BASE}/skeleton-nodes/${nodeId}`, { method: 'DELETE' })
  if (r.status === 409) { alert('内置节点无法删除。'); return }
  if (selectedNode.value?.id === nodeId) { selectedNode.value = null; nodeMemories.value = [] }
  await loadSkeleton(selectedProject.value.id)
}

async function onSaveHint(hint) {
  await onPatch({ id: selectedNode.value.id, patch: { prompt_hint: hint } })
}

async function onUpdateTags(tags) {
  await onPatch({ id: selectedNode.value.id, patch: { tags } })
  if (selectedNode.value) selectedNode.value = { ...selectedNode.value, tags }
}

async function onReorder(orderedIds) {
  // Optimistic: reload after API
  await apiFetch(`${BASE}/skeleton-nodes/reorder`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: selectedProject.value.id, ordered_ids: orderedIds }),
  })
  await loadSkeleton(selectedProject.value.id)
}

async function unlinkMemory(memoryId) {
  await apiFetch(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories/${memoryId}`, { method: 'DELETE' })
  nodeMemories.value = nodeMemories.value.filter(m => m.id !== memoryId)
  memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
}

// ── Context menu ──────────────────────────────────────────────────────────────
const ctxVisible = ref(false)
const ctxX = ref(0)
const ctxY = ref(0)
const ctxDepth = ref(0)
const ctxNode = ref(null)

function openContextMenu({ x, y, node, depth }) {
  ctxX.value = x; ctxY.value = y; ctxDepth.value = depth; ctxNode.value = node
  ctxVisible.value = true
}

function closeContextMenu() { ctxVisible.value = false; ctxNode.value = null }

onMounted(() => {
  document.addEventListener('click', closeContextMenu)
})

async function onAddChild() {
  closeContextMenu()
  if (!ctxNode.value) return
  const name = prompt('子节点名称：')
  if (!name?.trim()) return
  await apiJSON(`${BASE}/skeleton-nodes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: selectedProject.value.id, parent_id: ctxNode.value.id, name: name.trim() }),
  })
  await loadSkeleton(selectedProject.value.id)
}

function onRenameNode() {
  closeContextMenu()
  // The SkNode inline edit is triggered via the right-click action above,
  // but we can't easily call into SkNode from here without a ref.
  // Simplest: double-click on the name also triggers edit — user can use that.
  // For rename via menu: re-select the same node to show it active,
  // then user presses F2 or uses context menu.
  // A full implementation would use a template ref registry keyed by node id.
  // For this iteration, emit a custom event to SkeletonTreePanel or show a prompt.
  if (!ctxNode.value) return
  const name = prompt('新名称：', ctxNode.value.name)
  if (name?.trim() && name !== ctxNode.value.name) {
    onPatch({ id: ctxNode.value.id, patch: { name: name.trim() } })
  }
}

function focusTags() {
  closeContextMenu()
  // Select the node so the detail panel shows; tags section is always visible there
  if (ctxNode.value) selectNode(ctxNode.value)
}

async function onDeleteNode() {
  const node = ctxNode.value
  closeContextMenu()
  if (node) await onDelete(node.id)
}

// ── Add memory ────────────────────────────────────────────────────────────────
const addMemoryOpen = ref(false)
const isMemSaving = ref(false)
const memError = ref('')
const memForm = ref({ type: 'project', name: '', description: '', content: '' })

async function submitAddMemory() {
  if (!memForm.value.name || !memForm.value.content) return
  isMemSaving.value = true; memError.value = ''
  try {
    const mem = await apiJSON(`${BASE}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...memForm.value, project_id: selectedProject.value.id }),
    })
    await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: mem.id }),
    })
    addMemoryOpen.value = false
    memForm.value = { type: 'project', name: '', description: '', content: '' }
    nodeMemories.value = await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`)
    memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
  } catch (e) { memError.value = e.message }
  finally { isMemSaving.value = false }
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
  const r = await apiFetch(`${BASE}/projects`)
  if (r.status === 401) { loginOpen.value = true; return }
  projects.value = await r.json()
})
</script>

<style scoped>
.sk-app { width: 100%; min-height: 100vh; background: var(--bg, #fff); color: var(--fg, #1a1a1a); font-family: 'JetBrains Mono', monospace; box-sizing: border-box; text-align: left; }
.sk-body { display: flex; height: calc(100vh - 41px); overflow: hidden; }
.tree-empty { width: 220px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--fg-muted, #6e7681); font-size: 12px; border-right: 1px solid var(--border, #30363d); }
/* Login */
.login-overlay { display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 100; }
.login-modal { background: var(--bg, #fff); border-radius: 8px; padding: 24px; min-width: 300px; display: flex; flex-direction: column; gap: 12px; }
.login-title { font-size: 16px; font-weight: 700; }
.login-input { border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 8px; font-size: 13px; font-family: inherit; }
.login-error { color: #dc2626; font-size: 12px; margin: 0; }
.btn-login { background: var(--accent, #2563eb); color: #fff; border: none; border-radius: 5px; padding: 8px 16px; cursor: pointer; font-size: 13px; }
.btn-skip { background: none; border: none; color: var(--fg-muted, #888); cursor: pointer; font-size: 12px; text-decoration: underline; }
/* Modals */
.modal-overlay { display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 50; }
.modal { background: var(--bg, #fff); border-radius: 8px; border: 1px solid var(--border, #ddd); }
.modal-header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border, #ddd); }
.modal-title { font-size: 13px; font-weight: 700; flex: 1; }
.modal-close { background: none; border: none; cursor: pointer; font-size: 14px; color: var(--fg-muted, #888); padding: 2px 4px; }
.sk-input { width: 100%; border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 6px 8px; font-size: 13px; font-family: inherit; background: var(--input-bg, #fff); color: var(--fg, #1a1a1a); }
.btn-save { background: var(--accent, #2563eb); color: #fff; border: none; border-radius: 5px; padding: 8px 16px; cursor: pointer; font-size: 13px; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-cancel { background: none; border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 8px 16px; cursor: pointer; font-size: 13px; }
/* Write modal */
.write-modal { background: var(--bg, #fff); border-radius: 8px; border: 1px solid var(--border, #ddd); width: 500px; max-height: 80vh; display: flex; flex-direction: column; }
.write-header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border, #ddd); }
.write-title { font-size: 13px; font-weight: 700; flex: 1; }
.write-body { flex: 1; overflow-y: auto; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.write-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border, #ddd); }
.write-section { display: flex; flex-direction: column; gap: 4px; }
.write-section-grow { flex: 1; }
.write-field-label { font-size: 10px; font-weight: 700; color: var(--fg-muted, #6e7681); text-transform: uppercase; }
.write-input { border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 6px 8px; font-size: 12px; font-family: inherit; background: var(--input-bg, #fff); color: var(--fg, #1a1a1a); }
.write-textarea { resize: vertical; min-height: 80px; }
.write-type-tabs { display: flex; gap: 4px; }
.type-tab { padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border, #ddd); font-size: 11px; cursor: pointer; background: none; color: var(--fg-muted, #888); }
.type-tab.active { background: var(--accent, #2563eb); color: #fff; border-color: transparent; }
.sk-prompt-hint-text { font-size: 11px; color: var(--fg-muted, #888); background: var(--hint-bg, #f8f9fa); padding: 6px 10px; border-radius: 4px; font-style: italic; }
.save-hint.err { color: #dc2626; font-size: 11px; }
/* Dark theme vars */
.dark {
  --bg: #0d1117; --fg: #e6edf3; --fg-muted: #8b949e; --border: #30363d;
  --hover: #161b22; --active-bg: #1d2d3e; --input-bg: #161b22; --btn-bg: #21262d;
  --hint-bg: #161b22; --accent: #58a6ff; --tag-bg: #1a3a52; --accent-dim: #1f6feb44;
  --tooltip-bg: #1c2128;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/SkeletonPage.vue
git commit -m "feat: SkeletonPage.vue refactor — orchestrator wiring all 6 sub-components"
```

---

## Task 12: Build + Smoke Test

- [ ] **Step 1: Install frontend deps and build**

```bash
cd frontend
npm install
npm run build
```

Expected: `dist/` directory created with bundled assets, no errors.

- [ ] **Step 2: Start server and navigate to UI**

```bash
cd ..
uv run mo-server serve-http &
sleep 2
```

Open `http://localhost:8765/ui/` in browser.

- [ ] **Step 3: Smoke test checklist**

Verify each of the following manually:

| Check | Expected |
|---|---|
| Page loads | Three-column layout: icon strip + tree + detail |
| Icon strip shows projects | Project initials displayed, active project highlighted |
| Tree shows 11 builtin nodes | Each with correct emoji (📌 📋 🎨 🔧 🖥 ⚙️ 🗄️ 🧪 🚀 📝 💡) |
| Click chevron | Node expands/collapses children |
| Click node | Detail panel shows prompt hint and memory list |
| Hover node 500ms | Tooltip with prompt_hint + stats appears |
| Right-click node | Context menu with 4 items |
| Right-click 3rd-level node | "添加子节点" is greyed out |
| Type in search box | Non-matching nodes fade, matches highlight |
| Drag node up/down | Blue line indicator, order persists after page reload |
| Add tag in detail panel | Tag chip appears, survives page reload |
| Create new project | Appears in icon strip |
| + Add Memory | Modal opens, memory saved and appears in list |

- [ ] **Step 4: Run backend tests**

```bash
uv run pytest tests/unit/ -v
```

Expected: all tests pass including `test_skeleton_node_ops.py`.

- [ ] **Step 5: Final commit**

```bash
kill %1   # stop dev server
git add frontend/src/ frontend/dist/
git commit -m "feat: build knowledge tree UI — all 6 components + refactored SkeletonPage"
```

---

## Quick Reference

| Component | File | Emits upstream |
|---|---|---|
| ProjectIconStrip | `frontend/src/ProjectIconStrip.vue` | `select`, `create` |
| SkeletonTreePanel | `frontend/src/SkeletonTreePanel.vue` | `select`, `patch`, `delete`, `context-menu`, `reorder` |
| SkNode | `frontend/src/SkNode.vue` | `select`, `patch`, `delete`, `context-menu`, `reorder` |
| NodeDetailPanel | `frontend/src/NodeDetailPanel.vue` | `save-hint`, `update-tags`, `add-memory`, `unlink-memory` |
| ContextMenu | `frontend/src/ContextMenu.vue` | `add-child`, `rename`, `manage-tags`, `delete` |
| TagPicker | `frontend/src/TagPicker.vue` | `update:modelValue` |

| API endpoint | Purpose |
|---|---|
| `GET /api/projects/{id}/skeleton` | Returns nested tree with `tags` + `parent_id` |
| `POST /api/skeleton-nodes` | Create child node |
| `PATCH /api/skeleton-nodes/{id}` | Rename / update prompt_hint / update tags |
| `DELETE /api/skeleton-nodes/{id}` | Delete (409 for builtin) |
| `POST /api/skeleton-nodes/reorder` | Bulk sort_order update |
| `GET /api/skeleton-nodes/{id}/memories` | List linked memories |
| `POST /api/skeleton-nodes/{id}/memories` | Link memory to node |
| `DELETE /api/skeleton-nodes/{id}/memories/{mid}` | Unlink memory |
