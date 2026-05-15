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
        "children": [
            {"name": "技术栈", "sort_order": 0, "tags": ["stack", "tech", "dependency"],
             "description": "前后端技术选型、数据库、中间件、基础设施、外部服务",
             "prompt_hint": "记录技术选型：框架、数据库、ORM、中间件、消息队列、基础设施"},
            {"name": "项目说明", "sort_order": 1, "tags": ["overview", "intro"],
             "description": "项目背景、目标、核心功能说明",
             "prompt_hint": "记录项目的背景、目标、核心功能"},
            {"name": "架构概览", "sort_order": 2, "tags": ["architecture", "overview"],
             "description": "系统整体架构、模块划分、数据流",
             "prompt_hint": "记录系统架构图、模块划分、关键数据流"},
            {"name": "外部依赖", "sort_order": 3, "tags": ["dependency", "external"],
             "description": "外部系统、第三方服务、API依赖",
             "prompt_hint": "记录外部系统依赖、第三方服务、API集成"},
        ],
    },
    {
        "name": "需求", "sort_order": 1,
        "tags": ["requirement", "user_story", "spec"],
        "description": "产品需求、用户故事、需求拆解、需求变更、待确认问题",
        "prompt_hint": "记录功能需求、用户故事、需求拆解、需求变更或待确认问题",
        "children": [
            {"name": "原始需求", "sort_order": 0, "tags": ["requirement", "spec"],
             "description": "原始产品需求文档、用户故事",
             "prompt_hint": "记录原始需求文档、用户故事、产品原型"},
            {"name": "需求拆解", "sort_order": 1, "tags": ["requirement", "breakdown"],
             "description": "需求分解为开发任务、优先级排序",
             "prompt_hint": "记录需求拆解为具体开发任务、优先级"},
            {"name": "需求变更", "sort_order": 2, "tags": ["requirement", "change"],
             "description": "需求变更记录、版本差异",
             "prompt_hint": "记录需求变更原因、影响范围、版本差异"},
            {"name": "待确认", "sort_order": 3, "tags": ["requirement", "pending"],
             "description": "待确认的需求、模糊点、待决策问题",
             "prompt_hint": "记录待确认的需求细节、模糊点、需要产品决策的问题"},
        ],
    },
    {
        "name": "设计", "sort_order": 2,
        "tags": ["design", "architecture", "api", "schema"],
        "description": "系统架构设计、接口设计、数据模型、流程设计、协议设计",
        "prompt_hint": "记录架构设计、接口定义、数据结构设计、流程设计或协议说明",
        "children": [
            {"name": "架构设计", "sort_order": 0, "tags": ["design", "architecture"],
             "description": "系统架构方案、组件设计",
             "prompt_hint": "记录系统架构方案、组件职责划分"},
            {"name": "接口设计", "sort_order": 1, "tags": ["design", "api"],
             "description": "API接口定义、协议约定",
             "prompt_hint": "记录API接口设计、请求响应格式、协议约定"},
            {"name": "数据模型", "sort_order": 2, "tags": ["design", "schema", "model"],
             "description": "数据结构、实体关系、字段设计",
             "prompt_hint": "记录数据结构设计、实体关系、字段定义"},
            {"name": "原型设计", "sort_order": 3, "tags": ["design", "prototype", "ui"],
             "description": "UI原型、交互流程设计",
             "prompt_hint": "记录UI原型、交互设计、页面流程"},
        ],
    },
    {
        "name": "前端", "sort_order": 3,
        "tags": ["frontend", "ui", "component", "reactive"],
        "description": "前端功能实现、组件设计、状态管理、性能优化、问题记录",
        "prompt_hint": "记录前端页面实现、组件设计、状态管理、联调问题或优化经验",
        "children": [
            {"name": "功能实现", "sort_order": 0, "tags": ["frontend", "feature"],
             "description": "前端功能模块实现记录",
             "prompt_hint": "记录前端功能实现细节、组件逻辑"},
            {"name": "问题记录", "sort_order": 1, "tags": ["frontend", "bug", "issue"],
             "description": "前端Bug、兼容性问题、联调问题",
             "prompt_hint": "记录前端遇到的Bug、兼容性问题、联调问题及解决方案"},
            {"name": "优化记录", "sort_order": 2, "tags": ["frontend", "performance", "optimization"],
             "description": "前端性能优化、体验改进",
             "prompt_hint": "记录前端性能优化方案、用户体验改进"},
            {"name": "开发经验", "sort_order": 3, "tags": ["frontend", "experience", "best_practice"],
             "description": "前端开发技巧、最佳实践",
             "prompt_hint": "记录前端开发技巧、踩坑经验、最佳实践"},
        ],
    },
    {
        "name": "后端", "sort_order": 4,
        "tags": ["backend", "api", "service", "logic"],
        "description": "后端接口实现、业务逻辑、服务拆分、异常处理、性能优化",
        "prompt_hint": "记录后端接口设计、业务逻辑、服务架构、异常处理或优化经验",
        "children": [
            {"name": "功能实现", "sort_order": 0, "tags": ["backend", "feature"],
             "description": "后端接口、业务逻辑实现记录",
             "prompt_hint": "记录后端接口实现、业务逻辑、服务调用"},
            {"name": "问题记录", "sort_order": 1, "tags": ["backend", "bug", "issue"],
             "description": "后端Bug、异常处理、线上问题",
             "prompt_hint": "记录后端遇到的Bug、异常、线上问题及解决方案"},
            {"name": "优化记录", "sort_order": 2, "tags": ["backend", "performance", "optimization"],
             "description": "接口性能优化、并发处理改进",
             "prompt_hint": "记录后端性能优化、并发处理、接口响应改进"},
            {"name": "开发经验", "sort_order": 3, "tags": ["backend", "experience", "best_practice"],
             "description": "后端开发技巧、最佳实践",
             "prompt_hint": "记录后端开发技巧、踩坑经验、最佳实践"},
        ],
    },
    {
        "name": "数据库", "sort_order": 5,
        "tags": ["database", "sql", "index", "transaction"],
        "description": "表结构设计、索引策略、SQL优化、数据迁移、事务与一致性",
        "prompt_hint": "记录数据库设计、索引优化、SQL调优、迁移方案或一致性问题",
        "children": [
            {"name": "表结构", "sort_order": 0, "tags": ["database", "schema", "table"],
             "description": "数据库表设计、字段定义、关系约束",
             "prompt_hint": "记录数据库表结构、字段定义、索引设计"},
            {"name": "SQL优化", "sort_order": 1, "tags": ["database", "sql", "performance"],
             "description": "慢查询优化、索引调整、执行计划",
             "prompt_hint": "记录SQL优化过程、慢查询原因、索引改进方案"},
            {"name": "数据迁移", "sort_order": 2, "tags": ["database", "migration"],
             "description": "数据迁移方案、版本升级、数据清洗",
             "prompt_hint": "记录数据迁移方案、Alembic迁移脚本、数据清洗步骤"},
            {"name": "故障记录", "sort_order": 3, "tags": ["database", "incident", "bug"],
             "description": "数据库故障、死锁、数据异常事件",
             "prompt_hint": "记录数据库故障事件、死锁问题、数据异常及处理过程"},
        ],
    },
    {
        "name": "测试", "sort_order": 6,
        "tags": ["testing", "qa", "mock", "e2e"],
        "description": "单元测试、集成测试、E2E测试、Mock方案、缺陷记录",
        "prompt_hint": "记录测试策略、测试工具、Mock方案、覆盖率或缺陷问题",
        "children": [
            {"name": "单元测试", "sort_order": 0, "tags": ["testing", "unit"],
             "description": "单元测试用例、Mock策略",
             "prompt_hint": "记录单元测试设计、Mock策略、测试覆盖思路"},
            {"name": "集成测试", "sort_order": 1, "tags": ["testing", "integration"],
             "description": "集成测试方案、环境配置",
             "prompt_hint": "记录集成测试方案、测试环境配置、端到端流程验证"},
            {"name": "测试技巧", "sort_order": 2, "tags": ["testing", "technique", "best_practice"],
             "description": "测试设计技巧、工具使用、最佳实践",
             "prompt_hint": "记录测试技巧、工具使用方法、测试数据设计"},
            {"name": "缺陷记录", "sort_order": 3, "tags": ["testing", "bug", "defect"],
             "description": "测试发现的缺陷、复现步骤、修复状态",
             "prompt_hint": "记录测试发现的缺陷、复现步骤、影响范围、修复状态"},
        ],
    },
    {
        "name": "部署", "sort_order": 7,
        "tags": ["deploy", "ci_cd", "devops", "infra"],
        "description": "环境配置、CI/CD、容器化、发布流程、运维与故障恢复",
        "prompt_hint": "记录部署流程、Docker配置、CI/CD、环境问题或发布经验",
        "children": [
            {"name": "环境配置", "sort_order": 0, "tags": ["deploy", "env", "config"],
             "description": "开发/测试/生产环境配置",
             "prompt_hint": "记录环境变量、配置文件、环境差异说明"},
            {"name": "Docker部署", "sort_order": 1, "tags": ["deploy", "docker", "container"],
             "description": "容器化方案、Compose配置、镜像构建",
             "prompt_hint": "记录Docker配置、Compose方案、镜像构建流程"},
            {"name": "发布流程", "sort_order": 2, "tags": ["deploy", "release", "ci_cd"],
             "description": "CI/CD流程、版本发布步骤",
             "prompt_hint": "记录发布流程、CI/CD配置、版本管理策略"},
            {"name": "故障恢复", "sort_order": 3, "tags": ["deploy", "incident", "recovery"],
             "description": "故障排查、回滚方案、恢复步骤",
             "prompt_hint": "记录故障排查过程、回滚方案、恢复步骤"},
        ],
    },
    {
        "name": "决策记录", "sort_order": 8,
        "tags": ["decision", "tradeoff", "architecture_choice"],
        "description": "关键技术决策、架构选择、方案对比、历史原因、权衡分析",
        "prompt_hint": "记录为什么这样做：背景、备选方案、选择原因与权衡",
        "children": [
            {"name": "技术选型", "sort_order": 0, "tags": ["decision", "tech", "selection"],
             "description": "框架、库、工具的选型决策",
             "prompt_hint": "记录技术选型决策：为什么选A而不是B"},
            {"name": "架构决策", "sort_order": 1, "tags": ["decision", "architecture"],
             "description": "架构层面的重要决策",
             "prompt_hint": "记录重要架构决策：背景、方案、选择理由"},
            {"name": "历史原因", "sort_order": 2, "tags": ["decision", "history", "legacy"],
             "description": "历史遗留、历史包袱、历史决策背景",
             "prompt_hint": "记录历史遗留的技术债或决策背景，帮助理解现状"},
            {"name": "方案对比", "sort_order": 3, "tags": ["decision", "comparison", "tradeoff"],
             "description": "方案对比分析、权衡取舍",
             "prompt_hint": "记录方案对比结果、各方案优缺点、最终权衡"},
        ],
    },
    {
        "name": "经验库", "sort_order": 9,
        "tags": ["experience", "best_practice", "pitfall", "debug"],
        "description": "开发技巧、调试技巧、性能优化、踩坑记录、最佳实践",
        "prompt_hint": "记录可复用经验：踩坑、调试方法、优化技巧、最佳实践",
        "children": [
            {"name": "开发技巧", "sort_order": 0, "tags": ["experience", "dev_tip"],
             "description": "开发效率技巧、工具使用技巧",
             "prompt_hint": "记录提升开发效率的技巧、工具使用方法"},
            {"name": "调试技巧", "sort_order": 1, "tags": ["experience", "debug"],
             "description": "调试方法、问题定位技巧",
             "prompt_hint": "记录调试方法、问题定位技巧、日志分析方法"},
            {"name": "测试技巧", "sort_order": 2, "tags": ["experience", "testing"],
             "description": "测试经验、测试工具使用技巧",
             "prompt_hint": "记录测试经验、测试框架使用技巧"},
            {"name": "常见坑", "sort_order": 3, "tags": ["experience", "pitfall", "gotcha"],
             "description": "踩坑记录、常见错误、注意事项",
             "prompt_hint": "记录踩坑记录、常见错误及解决方案、注意事项"},
        ],
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
    ) -> str:
        resolved_project_id = await self._ensure_project_ref(project_id)
        stmt = select(Memory).where(
            Memory.superseded_by.is_(None),
            Memory.project_id == resolved_project_id,
            or_(
                Memory.type == "user",
                (Memory.type == "feedback") & (Memory.importance >= 3),
                (Memory.type == "project") & (Memory.updated_at >= utc_now() - timedelta(days=30)),
                Memory.type == "reference",
            ),
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
                parent_node_id = uuid.uuid4()
                self.session.add(ProjectSkeletonNode(
                    id=parent_node_id,
                    project_id=project_id,
                    name=n["name"], description=n["description"],
                    prompt_hint=n["prompt_hint"], sort_order=n["sort_order"],
                    is_builtin=True,
                    tags=n.get("tags", []),
                ))
                for c in n.get("children", []):
                    self.session.add(ProjectSkeletonNode(
                        project_id=project_id,
                        parent_id=parent_node_id,
                        name=c["name"], description=c["description"],
                        prompt_hint=c["prompt_hint"], sort_order=c["sort_order"],
                        is_builtin=True,
                        tags=c.get("tags", []),
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
        self, node_id: uuid.UUID, *, name: str | None = None, prompt_hint: str | None = None,
        tags: list[str] | None = None
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

    async def create_skeleton_node(
        self,
        project_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None = None,
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
                (ProjectSkeletonNode.parent_id == parent_id) if parent_id else ProjectSkeletonNode.parent_id.is_(None),
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


@dataclass
class Hit:
    memory: Memory
    score: float
    cosine_sim: float
