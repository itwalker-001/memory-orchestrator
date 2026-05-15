# Knowledge Tree UI — Design Spec

**Date:** 2026-05-14  
**Status:** Approved  
**Scope:** `memory_orchestrator_server/frontend/` + `memory_orchestrator_server/` (backend)

---

## 1. Overview

Replace the current `SkeletonPage.vue` (flat project list + plain tree) with a three-column Obsidian-style knowledge base UI. The new UI organises project memories in a collapsible, searchable, draggable, tagged tree.

### Goals

- Obsidian-like tree navigation for software project memories
- Node tags for categorisation and filtering
- Drag-and-drop reordering (persisted to DB)
- Right-click context menu with add/rename/delete/tag actions
- In-project full-text search with highlight and auto-expand
- Hover tooltip with node summary

### Non-goals

- Cross-project search (future iteration)
- Tag-level separate DB table (tags are `string[]` on each node)
- Unlimited nesting (max 3 levels enforced in UI)

---

## 2. Layout

Three-column layout replacing the current two-column layout:

```
┌──────┬──────────────────────┬──────────────────────────────┐
│ Icon │  Skeleton Tree Panel │  Node Detail Panel           │
│ Strip│  (220 px)            │  (flex: 1)                   │
│(52px)│  - search bar        │  - node title + emoji        │
│      │  - collapsible tree  │  - tags (TagPicker)          │
│      │  - emoji per node    │  - prompt hint               │
│      │  - badge counts      │  - memories list             │
│      │  - drag handles      │  - add memory button         │
└──────┴──────────────────────┴──────────────────────────────┘
```

- **Icon Strip** (`ProjectIconStrip.vue`): 52 px, dark `#010409`. Shows project initials as icon buttons. Active project has blue ring. `+` button at bottom to create a project.
- **Skeleton Tree Panel** (`SkeletonTreePanel.vue`): 220 px. Contains search input and the recursive node tree.
- **Node Detail Panel** (`NodeDetailPanel.vue`): fills remaining width. Shows selected node's tags, prompt hint, and memory list.

---

## 3. Component Structure

```
SkeletonPage.vue          ← refactored: data orchestration only, all API calls here
├── ProjectIconStrip.vue  ← new: project switcher icon strip
├── SkeletonTreePanel.vue ← new: tree container + search
│   └── SkNode.vue        ← extracted: recursive single-node renderer
├── NodeDetailPanel.vue   ← new: right panel (tags + memories)
├── ContextMenu.vue       ← new: right-click floating menu
└── TagPicker.vue         ← new: tag input with autocomplete
```

### State ownership

`SkeletonPage.vue` owns all server-derived state:

| State | Type | Description |
|---|---|---|
| `projects` | `Project[]` | All projects |
| `selectedProject` | `Project \| null` | Active project |
| `skeletonTree` | `SkNode[]` | Node tree for active project (includes `tags`) |
| `selectedNode` | `SkNode \| null` | Currently selected node |
| `nodeMemories` | `Memory[]` | Memories linked to selected node |

Child components hold only local UI state:

| Component | Local state |
|---|---|
| `SkeletonTreePanel` | `searchQuery: string`, `expandedIds: Set<string>` |
| `SkNode` | `isDragging: boolean`, `isDragOver: 'above'\|'below'\|null` |
| `ContextMenu` | `visible: boolean`, `position: {x,y}`, `targetNode` |
| `TagPicker` | `input: string`, `suggestions: string[]` |

Child components **never fetch directly** — they emit intents upward.

### Component interfaces

**ProjectIconStrip**
- Props: `projects: Project[]`, `activeId: string`
- Emits: `select(project)`, `create()`

**SkeletonTreePanel**
- Props: `nodes: SkNode[]`, `selectedId: string`
- Emits: `select(node)`, `patch(id, patch)`, `delete(id)`, `reorder(orderedIds)`, `add-child(parentId)`

**NodeDetailPanel**
- Props: `node: SkNode | null`, `memories: Memory[]`, `allTags: string[]`
- Emits: `save-hint(hint)`, `update-tags(tags[])`, `add-memory()`, `unlink-memory(memId)`

---

## 4. Node Data Model (Frontend)

```ts
interface SkNode {
  id: string
  name: string
  parent_id: string | null
  prompt_hint: string | null
  sort_order: number
  is_builtin: boolean
  tags: string[]          // new — from DB ARRAY(Text) column
  children: SkNode[]
  depth: number           // computed client-side during tree traversal
}
```

`depth` is computed by `SkeletonPage` when building the tree from the flat API response. It is used to disable "Add child" in the context menu when `depth >= 2` (0-indexed, max 3 levels = depth 0/1/2).

`allTags` is a computed property in `SkeletonPage`:
```ts
const allTags = computed(() =>
  [...new Set(flatTree.value.flatMap(n => n.tags))].sort()
)
```

---

## 5. Node Icons (Builtin Nodes)

| Node name | Emoji |
|---|---|
| 项目概况 | 📌 |
| 需求 | 📋 |
| 设计 | 🎨 |
| 技术栈 | 🔧 |
| 前端 | 🖥 |
| 后端 | ⚙️ |
| 数据库 | 🗄️ |
| 测试 | 🧪 |
| 部署 | 🚀 |
| 决策记录 | 📝 |
| 经验库 | 💡 |

User-created nodes show a default `📄` icon. Icons are stored as a client-side constant map keyed by node name; not persisted to DB.

---

## 6. Backend Changes

### 6a. DB Migration — `0002_skeleton_node_tags.py`

```python
def upgrade() -> None:
    op.add_column(
        "project_skeleton_nodes",
        sa.Column("tags", postgresql.ARRAY(sa.Text),
                  server_default="{}", nullable=False),
    )

def downgrade() -> None:
    op.drop_column("project_skeleton_nodes", "tags")
```

No data migration needed — existing rows default to empty array `{}`.

### 6b. ORM — `models.py`

Add to `ProjectSkeletonNode`:
```python
tags = Column(ARRAY(Text), server_default="{}", nullable=False)
```

### 6c. BUILTIN_SKELETON_NODES — `repository.py`

Update all 11 builtin node definitions with the enriched data provided (adds `tags`, updates `description` and `prompt_hint` for each node). Only affects new project creation; existing nodes are not auto-migrated.

### 6d. API Changes — `routers/ui.py`

| Method | Path | Change |
|---|---|---|
| PATCH | `/skeleton-nodes/{id}` | `SkeletonNodePatch` schema adds `tags: list[str] \| None` |
| POST | `/skeleton-nodes/reorder` | **New endpoint** — accepts `{project_id, ordered_ids: list[uuid]}`, bulk-updates `sort_order` |
| GET | `/projects/{id}/skeleton` | Response includes `tags` field per node |

### 6e. Reorder Endpoint

```python
class ReorderBody(BaseModel):
    project_id: uuid.UUID
    ordered_ids: list[uuid.UUID]  # complete ordered list of sibling node IDs

@router.post("/skeleton-nodes/reorder", status_code=200)
async def reorder_skeleton_nodes(body: ReorderBody) -> dict:
    async with repo as r:
        for i, node_id in enumerate(body.ordered_ids):
            await r.session.execute(
                update(ProjectSkeletonNode)
                .where(ProjectSkeletonNode.id == node_id,
                       ProjectSkeletonNode.project_id == body.project_id)
                .values(sort_order=i * 10)  # gap of 10 reduces future migrations
            )
    return {"ok": True}
```

### 6f. Files Modified

| File | Change |
|---|---|
| `models.py` | +1 column `tags` |
| `repository.py` | BUILTIN_SKELETON_NODES enriched; `patch_skeleton_node` supports tags; new `reorder_skeleton_nodes` method |
| `routers/ui.py` | `SkeletonNodePatch` + tags; new reorder endpoint; skeleton response includes tags |
| `alembic/versions/0002_skeleton_node_tags.py` | New migration file |

Files **not** changed: `auth_tokens.py`, `ingestor.py`, `embedder.py`, `mcp_core.py`, `scoring.py`.

---

## 7. Frontend Interactions

### 7a. Search (within current project)

- Search input in `SkeletonTreePanel`, filters by node name (case-insensitive substring)
- Non-matching nodes rendered at `opacity: 0.35` (not hidden — preserves tree context)
- Matching text wrapped in `<mark>` for highlight
- All ancestor nodes of matches are auto-expanded and shown at full opacity
- Match count shown in search bar (e.g. "2 结果")
- Implemented as a `computed` (`visibleNodes`) in `SkeletonTreePanel` using a `useTreeSearch` composable

### 7b. Drag-and-drop Reordering

- Uses HTML5 native Drag API (`draggable`, `dragstart`, `dragover`, `drop`, `dragend`)
- Only same-level sibling nodes can be reordered; cross-level moves are not supported
- Drop position (above/below) determined by mouse Y position relative to target node's midpoint
- Visual indicator: 2 px blue line (`border-top` or `border-bottom`) on target node
- Dragging node rendered at `opacity: 0.4`
- **Optimistic update**: local array reordered immediately on `drop`; API called once on `dragend`
- On API failure: tree reloaded from server (rollback)
- Payload: complete ordered `id[]` list of all siblings at that level

### 7c. Right-click Context Menu (`ContextMenu.vue`)

Menu items:
1. **添加子节点** — disabled (`cursor: not-allowed`, grey) when `node.depth >= 2`; emits `add-child(node.id)` otherwise
2. **重命名** — inline edit (same as current `F2` behaviour); shortcut label shown
3. **管理标签** — opens `TagPicker` inline in the detail panel
4. **删除节点** — red text; confirms before emitting `delete(node.id)`; blocked by server for builtin nodes (HTTP 409)

Implementation:
- `SkNode.vue` calls `e.preventDefault()` on `contextmenu` event; emits `context-menu` with `{x: e.clientX, y: e.clientY, node}`
- `ContextMenu.vue` uses `position: fixed` + `z-index: 9999`
- Auto-flips if menu would overflow viewport (right→left, bottom→top)
- Closed on `document.addEventListener('click', close)` registered in `onMounted`/`onUnmounted`

### 7d. Hover Tooltip

- 500 ms delay on `mouseenter` before showing (prevents flicker when mousing across tree)
- Cleared immediately on `mouseleave`
- Content: node emoji + name, `prompt_hint` (truncated to 80 chars), memory count, child count, tags chips
- Rendered via `<Teleport to="body">` to avoid being clipped by `overflow: hidden` on parent panels
- Positioned at `node.getBoundingClientRect()` right edge + 10 px offset

### 7e. TagPicker (`TagPicker.vue`)

- Displayed in `NodeDetailPanel` when tags section is active
- Input does fuzzy substring match against `allTags` (computed from all nodes in current project)
- Selecting a suggestion or pressing Enter adds the tag to the current node and immediately calls `PATCH /skeleton-nodes/{id}` with updated `tags[]`
- If input text matches no existing tag, "Create #tag" option is shown at bottom of dropdown
- Tags rendered as removable chips; clicking `×` removes tag and patches immediately
- `allTags` is a `computed` in `SkeletonPage` — no separate API needed

---

## 8. Depth Limit (Max 3 Levels)

`depth` is calculated during tree-building in `SkeletonPage`:

```ts
function buildTree(nodes: FlatNode[], parentId = null, depth = 0): SkNode[] {
  return nodes
    .filter(n => n.parent_id === parentId)
    .map(n => ({ ...n, depth, children: buildTree(nodes, n.id, depth + 1) }))
}
```

`ContextMenu` receives `node.depth` and disables "添加子节点" when `depth >= 2`.

---

## 9. File Checklist

### New frontend files
- `frontend/src/ProjectIconStrip.vue`
- `frontend/src/SkeletonTreePanel.vue`
- `frontend/src/SkNode.vue` (extracted from `SkeletonPage.vue`)
- `frontend/src/NodeDetailPanel.vue`
- `frontend/src/ContextMenu.vue`
- `frontend/src/TagPicker.vue`

### Modified frontend files
- `frontend/src/SkeletonPage.vue` (refactored to orchestrator)

### New backend files
- `alembic/versions/0002_skeleton_node_tags.py`

### Modified backend files
- `models.py`
- `repository.py`
- `routers/ui.py`
