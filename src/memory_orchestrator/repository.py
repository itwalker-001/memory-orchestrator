from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator.models import Memory
from memory_orchestrator.scoring import hybrid_score, truncate_by_budget


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

    async def find_duplicates(
        self,
        *,
        type: str,
        project_id: str,
        embedding: list[float],
        threshold: float = 0.92,
        limit: int = 5,
    ) -> list[Memory]:
        # pgvector cosine_distance = 1 - cosine_similarity
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
            .limit(top_k * 3)  # over-fetch, re-rank by hybrid score, then cut to top_k
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
        project_id: str,
        budget_tokens: int = 1500,
    ) -> str:
        """Return a markdown snippet ready to inject into the system prompt."""
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

    async def delete(self, memory_id: uuid.UUID, *, hard: bool = False) -> None:
        if hard:
            await self.session.execute(
                sa_delete(Memory).where(Memory.id == memory_id)
            )
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
