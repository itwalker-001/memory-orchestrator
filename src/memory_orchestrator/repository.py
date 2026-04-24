from __future__ import annotations
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete as sa_delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

_SETTINGS_CACHE: tuple[float, dict[str, str]] | None = None
_SETTINGS_TTL = 60.0  # seconds

from memory_orchestrator.models import GLOBAL_PROJECT_ID, Memory, Project, SystemSetting
from memory_orchestrator.scoring import hybrid_score, truncate_by_budget


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_project(self, slug: str, cwd: str | None = None) -> uuid.UUID:
        """Upsert a project by slug; return its UUID. slug='*' returns GLOBAL_PROJECT_ID."""
        if slug == "*":
            return GLOBAL_PROJECT_ID
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        now = datetime.now(timezone.utc)
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
        """Resolve a slug to its project UUID. Returns None if not found (not GLOBAL)."""
        if slug == "*":
            return GLOBAL_PROJECT_ID
        result = await self.session.execute(
            select(Project.id).where(Project.slug == slug)
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        *,
        type: str,
        name: str,
        description: str,
        content: str,
        project_id: uuid.UUID,
        source: str,
        why: str | None = None,
        how_to_apply: str | None = None,
        importance: int = 3,
        embedding: list[float] | None = None,
    ) -> Memory:
        m = Memory(
            type=type, name=name, description=description, content=content,
            project_id=project_id, source=source, why=why, how_to_apply=how_to_apply,
            importance=max(1, min(5, importance)), embedding=embedding,
        )
        self.session.add(m)
        await self.session.flush()
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
        project_id: uuid.UUID | None = None,
        project_ids: list[uuid.UUID] | None = None,
        type: str | None = None,
        q: str | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.superseded_by.is_(None))
        if project_ids is not None:
            stmt = stmt.where(Memory.project_id.in_(project_ids))
        elif project_id is not None:
            stmt = stmt.where(Memory.project_id == project_id)
        if type is not None:
            stmt = stmt.where(Memory.type == type)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                Memory.name.ilike(pattern) | Memory.description.ilike(pattern)
            )
        stmt = stmt.order_by(Memory.updated_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_duplicates(
        self,
        *,
        type: str,
        project_id: uuid.UUID,
        embedding: list[float],
        threshold: float = 0.92,
        limit: int = 5,
    ) -> list[Memory]:
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

    async def search(
        self,
        *,
        query_embedding: list[float],
        project_ids: list[uuid.UUID],
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
                .execution_options(synchronize_session="fetch")
            )
        return hits

    async def build_context(
        self,
        *,
        project_id: uuid.UUID,
        budget_tokens: int = 1500,
    ) -> str:
        stmt = select(Memory).where(
            Memory.superseded_by.is_(None),
            or_(
                Memory.project_id == GLOBAL_PROJECT_ID,
                (Memory.project_id == project_id) & (Memory.type == "feedback") & (Memory.importance >= 3),
                (Memory.project_id == project_id) & (Memory.type == "project") & (
                    Memory.updated_at >= datetime.now(timezone.utc) - timedelta(days=30)
                ),
                (Memory.project_id == project_id) & (Memory.type == "reference"),
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
        _SETTINGS_CACHE = None  # invalidate on write
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        now = datetime.now(timezone.utc)
        for key, value in updates.items():
            stmt = (
                pg_insert(SystemSetting)
                .values(key=key, value=value, updated_at=now)
                .on_conflict_do_update(index_elements=["key"], set_={"value": value, "updated_at": now})
            )
            await self.session.execute(stmt)

    async def delete(self, memory_id: uuid.UUID, *, hard: bool = False) -> None:
        if hard:
            await self.session.execute(sa_delete(Memory).where(Memory.id == memory_id))
        else:
            await self.session.execute(
                update(Memory).where(Memory.id == memory_id).values(
                    superseded_by=memory_id, updated_at=datetime.now(timezone.utc)
                )
            )


@dataclass
class Hit:
    memory: Memory
    score: float
    cosine_sim: float
