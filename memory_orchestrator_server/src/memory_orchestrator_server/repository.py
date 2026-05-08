from __future__ import annotations
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy import delete as sa_delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator_server import reranker
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory, Project, SystemSetting
from memory_orchestrator_server.scoring import hybrid_score, truncate_by_budget
from memory_orchestrator_server.time_utils import utc_now

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
        if slug == "*":
            stmt = (
                pg_insert(Project)
                .values(
                    id=GLOBAL_PROJECT_ID,
                    slug="*",
                    display_name="Global",
                    root_paths=[],
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
        if slug == "*":
            return GLOBAL_PROJECT_ID
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
            # blend: reranker dominates (80%) but importance+recency still influence (20%)
            blended = [(h, 0.8 * float(s) + 0.2 * h.score) for h, s in zip(hits, scores)]
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
            or_(
                Memory.project_id == GLOBAL_PROJECT_ID,
                (Memory.project_id == resolved_project_id) & (Memory.type == "feedback") & (Memory.importance >= 3),
                (Memory.project_id == resolved_project_id) & (Memory.type == "project") & (
                    Memory.updated_at >= utc_now() - timedelta(days=30)
                ),
                (Memory.project_id == resolved_project_id) & (Memory.type == "reference"),
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


@dataclass
class Hit:
    memory: Memory
    score: float
    cosine_sim: float
