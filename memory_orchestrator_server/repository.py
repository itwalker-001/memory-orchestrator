from __future__ import annotations
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy import delete as sa_delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator_server import reranker
from memory_orchestrator_server.models import Memory, Project, SystemSetting
from memory_orchestrator_server.models import ProjectSkeletonNode, SkeletonNodeMemory
from memory_orchestrator_server.scoring import hybrid_score, truncate_by_budget
from memory_orchestrator_server.time_utils import utc_now

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

ProjectRef = uuid.UUID | str

_SETTINGS_CACHE: tuple[float, dict[str, str]] | None = None
_SETTINGS_TTL = 60.0  # seconds


def _sync_project_count(project_id: uuid.UUID):
    subq = (
        select(func.count(Memory.id))
        .where(Memory.project_id == project_id, Memory.superseded_by.is_(None))
        .scalar_subquery()
    )
    return (
        update(Project)
        .where(Project.id == project_id)
        .values(memory_count=subq)
        .execution_options(synchronize_session=False)
    )


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_project(self, slug: str, cwd: str | None = None) -> uuid.UUID:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        now = utc_now()
        display_name = slug.split("/")[-1] if "/" in slug else slug
        stmt = (
            pg_insert(Project)
            .values(
                slug=slug,
                display_name=display_name,
                root_paths=[cwd] if cwd else [],
                first_seen_at=now,
                last_active_at=now,
            )
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={"last_active_at": now},
            )
            .returning(Project.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def slug_to_id(self, slug: str) -> uuid.UUID | None:
        result = await self.session.execute(
            select(Project.id).where(Project.slug == slug)
        )
        return result.scalar_one_or_none()

    async def _ensure_project_ref(self, project_id: ProjectRef) -> uuid.UUID:
        if isinstance(project_id, uuid.UUID):
            return project_id
        try:
            return uuid.UUID(project_id)
        except ValueError:
            return await self.ensure_project(project_id)

    async def _resolve_project_ref(self, project_id: ProjectRef) -> uuid.UUID | None:
        if isinstance(project_id, uuid.UUID):
            return project_id
        try:
            return uuid.UUID(project_id)
        except ValueError:
            return await self.slug_to_id(project_id)

    async def _resolve_project_refs(self, project_ids: list[ProjectRef]) -> list[uuid.UUID]:
        resolved = [await self._resolve_project_ref(project_id) for project_id in project_ids]
        return [project_id for project_id in resolved if project_id is not None]

    async def save(
        self,
        *,
        type: str,
        name: str,
        description: str,
        content: str,
        project_id: ProjectRef,
        source: str,
        source_client: str = "claude",
        why: str | None = None,
        how_to_apply: str | None = None,
        importance: int = 3,
        embedding: list[float] | None = None,
    ) -> Memory:
        resolved_project_id = await self._ensure_project_ref(project_id)
        m = Memory(
            type=type, name=name, description=description, content=content,
            project_id=resolved_project_id, source=source, source_client=source_client,
            why=why, how_to_apply=how_to_apply,
            importance=max(1, min(5, importance)), embedding=embedding,
        )
        self.session.add(m)
        await self.session.flush()
        await self.session.execute(_sync_project_count(resolved_project_id))
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
        project_id: ProjectRef | None = None,
        project_ids: list[ProjectRef] | None = None,
        type: str | None = None,
        q: str | None = None,
        limit: int = 50,
        sort_by: str = "time",
        sort_desc: bool = True,
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.superseded_by.is_(None))
        if project_ids is not None:
            resolved_project_ids = await self._resolve_project_refs(project_ids)
            if not resolved_project_ids:
                return []
            stmt = stmt.where(Memory.project_id.in_(resolved_project_ids))
        elif project_id is not None:
            resolved_project_id = await self._resolve_project_ref(project_id)
            if resolved_project_id is None:
                return []
            stmt = stmt.where(Memory.project_id == resolved_project_id)
        if type is not None:
            stmt = stmt.where(Memory.type == type)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                Memory.name.ilike(pattern) | Memory.description.ilike(pattern)
            )
        col = Memory.hit_count if sort_by == "hits" else Memory.updated_at
        stmt = stmt.order_by(col.desc() if sort_desc else col.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_duplicates(
        self,
        *,
        type: str,
        project_id: ProjectRef,
        embedding: list[float],
        threshold: float = 0.92,
        limit: int = 5,
    ) -> list[Memory]:
        resolved_project_id = await self._resolve_project_ref(project_id)
        if resolved_project_id is None:
            return []
        max_distance = 1.0 - threshold
        stmt = (
            select(Memory)
            .where(
                Memory.superseded_by.is_(None),
                Memory.type == type,
                Memory.project_id == resolved_project_id,
                Memory.embedding.isnot(None),
                Memory.embedding.cosine_distance(embedding) <= max_distance,
            )
            .order_by(Memory.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        *,
        query_embedding: list[float],
        project_ids: list[ProjectRef],
        types: list[str] | None = None,
        top_k: int = 3,
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

        cfg = await self.get_settings()
        cosine_w = float(cfg.get("score_cosine_weight", "0.6"))
        importance_w = float(cfg.get("score_importance_weight", "0.3"))
        recency_w = float(cfg.get("score_recency_weight", "0.1"))
        half_life = float(cfg.get("score_recency_half_life", "60"))
        rerank_blend = float(cfg.get("score_rerank_blend", "0.8"))
        min_score = float(cfg.get("search_min_score", "0.05"))
        type_boosts = {
            "feedback":  float(cfg.get("score_type_feedback",  "1.2")),
            "project":   float(cfg.get("score_type_project",   "1.0")),
            "user":      float(cfg.get("score_type_user",      "1.0")),
            "reference": float(cfg.get("score_type_reference", "1.0")),
        }

        hits: list[Hit] = []
        for mem, dist in rows:
            sim = 1.0 - float(dist)
            score = hybrid_score(
                cosine_sim=sim, importance=mem.importance, updated_at=mem.updated_at,
                cosine_weight=cosine_w, importance_weight=importance_w,
                recency_weight=recency_w, half_life_days=half_life,
                type_boost=type_boosts.get(mem.type, 1.0),
            )
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
            texts = [
                f"{h.memory.name} {h.memory.description} {h.memory.content}"
                for h in hits
            ]
            scores = reranker.rerank_scores(query, texts)
            blended = [(h, rerank_blend * float(s) + (1 - rerank_blend) * h.score) for h, s in zip(hits, scores)]
            hits = [
                Hit(memory=h.memory, score=final_s, cosine_sim=h.cosine_sim)
                for h, final_s in sorted(blended, key=lambda x: -x[1])
            ]

        if min_score > 0:
            hits = [h for h in hits if h.score >= min_score]
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

    async def build_context(
        self,
        *,
        project_id: ProjectRef,
        budget_tokens: int = 1500,
        top_k: int | None = None,
        node_id: uuid.UUID | None = None,
        node_name: str | None = None,
        parent_node: str | None = None,
        include_descendants: bool = True,
    ) -> str:
        resolved_project_id = await self._ensure_project_ref(project_id)
        stmt = select(Memory).where(
            Memory.superseded_by.is_(None),
            Memory.project_id == resolved_project_id,
        )
        has_node_filter = node_id is not None or node_name is not None
        if has_node_filter:
            resolved_node_id = node_id
            if resolved_node_id is None and node_name:
                node_stmt = select(ProjectSkeletonNode.id).where(
                    ProjectSkeletonNode.project_id == resolved_project_id,
                    ProjectSkeletonNode.name == node_name,
                )
                if parent_node:
                    parent_id_stmt = select(ProjectSkeletonNode.id).where(
                        ProjectSkeletonNode.project_id == resolved_project_id,
                        ProjectSkeletonNode.name == parent_node,
                        ProjectSkeletonNode.parent_id.is_(None),
                    )
                    parent_id = (await self.session.execute(parent_id_stmt)).scalar_one_or_none()
                    if parent_id is None:
                        return ""
                    node_stmt = node_stmt.where(ProjectSkeletonNode.parent_id == parent_id)
                else:
                    node_stmt = node_stmt.where(ProjectSkeletonNode.parent_id.is_(None))
                resolved_node_id = (await self.session.execute(node_stmt)).scalar_one_or_none()
            if resolved_node_id is None:
                return ""
            node_ids = (
                await self._descendant_node_ids(resolved_node_id)
                if include_descendants
                else [resolved_node_id]
            )
            stmt = (
                stmt.join(SkeletonNodeMemory, SkeletonNodeMemory.memory_id == Memory.id)
                .where(SkeletonNodeMemory.skeleton_node_id.in_(node_ids))
                .distinct()
            )
        else:
            stmt = stmt.where(
                or_(
                    Memory.type == "user",
                    (Memory.type == "feedback") & (Memory.importance >= 3),
                    (Memory.type == "project") & (Memory.updated_at >= utc_now() - timedelta(days=30)),
                    Memory.type == "reference",
                )
            )
        result = await self.session.execute(stmt)
        mems = list(result.scalars().all())

        def estimate(m: Memory) -> int:
            return max(1, int(len(m.name + m.description + (m.content or "")) / 3.5))

        items = [
            {"memory": m, "name": m.name, "importance": m.importance,
             "tokens": estimate(m), "updated_at": m.updated_at}
            for m in mems
        ]
        if top_k is not None and top_k >= 0:
            items = sorted(
                items,
                key=lambda i: (-i["importance"], -i["updated_at"].timestamp()),
            )[:top_k]
        kept = truncate_by_budget(items, budget=budget_tokens)

        if not kept:
            return ""

        ids = [item["memory"].id for item in kept]
        await self.session.execute(
            update(Memory)
            .where(Memory.id.in_(ids))
            .values(hit_count=Memory.hit_count + 1, last_hit_at=utc_now())
            .execution_options(synchronize_session="fetch")
        )
        await self.session.commit()

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

    async def get_settings(self) -> dict[str, str]:
        global _SETTINGS_CACHE
        if _SETTINGS_CACHE is not None and time.monotonic() - _SETTINGS_CACHE[0] < _SETTINGS_TTL:
            return _SETTINGS_CACHE[1]
        result = await self.session.execute(select(SystemSetting))
        data = {row.key: row.value for row in result.scalars().all()}
        _SETTINGS_CACHE = (time.monotonic(), data)
        return data

    async def set_settings(self, updates: dict[str, str]) -> None:
        global _SETTINGS_CACHE
        _SETTINGS_CACHE = None
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        now = utc_now()
        for key, value in updates.items():
            stmt = (
                pg_insert(SystemSetting)
                .values(key=key, value=value, updated_at=now)
                .on_conflict_do_update(index_elements=["key"], set_={"value": value, "updated_at": now})
            )
            await self.session.execute(stmt)

    async def seed_settings(self, defaults: dict[str, str]) -> None:
        """Insert missing system_settings rows; never overwrites existing values."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        now = utc_now()
        for key, value in defaults.items():
            stmt = (
                pg_insert(SystemSetting)
                .values(key=key, value=value, updated_at=now)
                .on_conflict_do_nothing(index_elements=["key"])
            )
            await self.session.execute(stmt)

    async def delete(self, memory_id: uuid.UUID, *, hard: bool = False) -> None:
        pid_row = await self.session.execute(select(Memory.project_id).where(Memory.id == memory_id))
        project_id = pid_row.scalar_one_or_none()
        if hard:
            await self.session.execute(sa_delete(Memory).where(Memory.id == memory_id))
        else:
            await self.session.execute(
                update(Memory).where(Memory.id == memory_id).values(
                    superseded_by=memory_id, updated_at=utc_now()
                )
            )
        if project_id:
            await self.session.execute(_sync_project_count(project_id))

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
            existing = await self.session.execute(select(Project.id).where(Project.slug == slug))
            row = existing.scalar_one()
        project_id = row
        existing_count = await self.session.execute(
            select(func.count(ProjectSkeletonNode.id))
            .where(ProjectSkeletonNode.project_id == project_id)
        )
        if existing_count.scalar_one() == 0:
            for n in BUILTIN_SKELETON_NODES:
                self.session.add(ProjectSkeletonNode(
                    project_id=project_id,
                    name=n["name"], description=n["description"],
                    prompt_hint=n["prompt_hint"], sort_order=n["sort_order"],
                    is_builtin=True,
                    tags=n.get("tags", []),
                ))
        return project_id

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
                    "project_id": str(n.project_id),
                    "parent_id": str(n.parent_id) if n.parent_id else None,
                    "name": n.name,
                    "description": n.description,
                    "prompt_hint": n.prompt_hint,
                    "is_builtin": n.is_builtin,
                    "sort_order": n.sort_order,
                    "tags": list(n.tags) if n.tags else [],
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                    "children": _build(n.id),
                }
                for n in children.get(parent_id, [])
            ]
        return _build(None)

    async def patch_skeleton_node(
        self, node_id: uuid.UUID, *, name: str | None = None, description: str | None = None,
        prompt_hint: str | None = None, tags: list[str] | None = None
    ) -> bool:
        node = await self.session.get(ProjectSkeletonNode, node_id)
        if node is None:
            return False
        if name is not None and not node.is_builtin:
            node.name = name
        if description is not None:
            node.description = description
        if prompt_hint is not None:
            node.prompt_hint = prompt_hint
        if tags is not None:
            node.tags = tags
        return True

    async def create_skeleton_node(
        self,
        project_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None = None,
        description: str = "",
        prompt_hint: str = "",
        tags: list[str] | None = None,
    ) -> dict:
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
            description=description,
            prompt_hint=prompt_hint,
            is_builtin=False,
            sort_order=max_order + 10,
            tags=tags or [],
        )
        self.session.add(node)
        await self.session.flush()
        return {
            "id": str(node.id),
            "name": node.name,
            "description": node.description,
            "prompt_hint": node.prompt_hint,
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "is_builtin": False,
            "sort_order": node.sort_order,
            "tags": list(node.tags or []),
            "children": [],
        }

    async def reorder_skeleton_nodes(
        self, project_id: uuid.UUID, ordered_ids: list[uuid.UUID]
    ) -> None:
        for i, node_id in enumerate(ordered_ids):
            await self.session.execute(
                update(ProjectSkeletonNode)
                .where(
                    ProjectSkeletonNode.id == node_id,
                    ProjectSkeletonNode.project_id == project_id,
                )
                .values(sort_order=i * 10)
            )

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
        node_ids = await self._descendant_node_ids(node_id)
        result = await self.session.execute(
            select(Memory)
            .join(SkeletonNodeMemory, SkeletonNodeMemory.memory_id == Memory.id)
            .where(
                SkeletonNodeMemory.skeleton_node_id.in_(node_ids),
                Memory.superseded_by.is_(None),
            )
            .order_by(Memory.created_at.desc())
            .distinct()
        )
        return list(result.scalars().all())

    async def _descendant_node_ids(self, node_id: uuid.UUID) -> list[uuid.UUID]:
        """Return node_id plus all descendant node ids (whole sub-tree)."""
        r = await self.session.execute(
            select(ProjectSkeletonNode.project_id).where(ProjectSkeletonNode.id == node_id)
        )
        project_id = r.scalar_one_or_none()
        if project_id is None:
            return [node_id]
        children: dict[uuid.UUID, list[uuid.UUID]] = {}
        for n in await self.get_skeleton_flat(project_id):
            children.setdefault(n.parent_id, []).append(n.id)
        collected: list[uuid.UUID] = []
        stack = [node_id]
        seen: set[uuid.UUID] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            collected.append(cur)
            stack.extend(children.get(cur, []))
        return collected

    async def get_memory_nodes(self, memory_id: uuid.UUID) -> list[ProjectSkeletonNode]:
        result = await self.session.execute(
            select(ProjectSkeletonNode)
            .join(SkeletonNodeMemory, SkeletonNodeMemory.skeleton_node_id == ProjectSkeletonNode.id)
            .where(SkeletonNodeMemory.memory_id == memory_id)
            .order_by(ProjectSkeletonNode.sort_order, ProjectSkeletonNode.created_at)
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
        self, project_id: uuid.UUID, name: str, parent_name: str | None,
        description: str = "", prompt_hint: str = "",
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
            select(ProjectSkeletonNode).where(
                ProjectSkeletonNode.project_id == project_id,
                ProjectSkeletonNode.name == name,
                (ProjectSkeletonNode.parent_id == parent_id) if parent_id else ProjectSkeletonNode.parent_id.is_(None),
            )
        )
        existing = r.scalar_one_or_none()
        if existing:
            # Backfill hint/description if the caller now provides one and it was blank.
            if prompt_hint and not existing.prompt_hint:
                existing.prompt_hint = prompt_hint
            if description and not existing.description:
                existing.description = description
            return existing.id
        node = ProjectSkeletonNode(
            project_id=project_id, parent_id=parent_id, name=name,
            description=description, prompt_hint=prompt_hint, is_builtin=False,
        )
        self.session.add(node)
        await self.session.flush()
        return node.id


@dataclass
class Hit:
    memory: Memory
    score: float
    cosine_sim: float


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
