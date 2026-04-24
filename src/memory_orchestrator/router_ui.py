from __future__ import annotations
import uuid
import httpx
from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memory_orchestrator.config import get_settings
from memory_orchestrator.models import GLOBAL_PROJECT_ID, Memory, Project
from memory_orchestrator.repository import MemoryRepository

SETTINGS_KEYS = ["extraction_base_url", "extraction_model", "extraction_api_key", "embed_model", "embed_dim",
                 "hook_cooldown_sec", "hook_min_turns", "hook_budget_tokens",
                 "search_top_k", "dup_threshold", "db_dsn", "http_port"]


class SettingsPatch(BaseModel):
    extraction_base_url: str | None = None
    extraction_model: str | None = None
    extraction_api_key: str | None = None
    embed_model: str | None = None
    embed_dim: str | None = None
    hook_cooldown_sec: str | None = None
    hook_min_turns: str | None = None
    hook_budget_tokens: str | None = None
    search_top_k: str | None = None
    dup_threshold: str | None = None
    db_dsn: str | None = None
    http_port: str | None = None


def make_ui_router(*, maker: async_sessionmaker) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/timezone")
    async def timezone() -> dict:
        import datetime
        tz = datetime.datetime.now().astimezone().tzname()
        offset = datetime.datetime.now().astimezone().utcoffset()
        total_seconds = int(offset.total_seconds())
        hours, remainder = divmod(abs(total_seconds), 3600)
        minutes = remainder // 60
        sign = "+" if total_seconds >= 0 else "-"
        iana = str(datetime.datetime.now().astimezone().tzinfo)
        return {"name": tz, "iana": iana, "offset_minutes": total_seconds // 60,
                "label": f"UTC{sign}{hours:02d}:{minutes:02d}"}

    @router.get("/projects")
    async def projects() -> list[dict]:
        async with maker() as s:
            result = await s.execute(
                select(Project)
                .where(Project.id != GLOBAL_PROJECT_ID)
                .order_by(Project.last_active_at.desc())
            )
            return [{"id": str(p.id), "slug": p.slug, "display_name": p.display_name} for p in result.scalars().all()]

    @router.get("/stats")
    async def stats(project_slug: str | None = None) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            stmt = select(Memory.type, func.count()).where(Memory.superseded_by.is_(None))
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                if pid and pid != GLOBAL_PROJECT_ID:
                    stmt = stmt.where(Memory.project_id.in_([pid, GLOBAL_PROJECT_ID]))
                elif pid:
                    stmt = stmt.where(Memory.project_id == pid)
            stmt = stmt.group_by(Memory.type)
            result = await s.execute(stmt)
            by_type = {row[0]: row[1] for row in result.all()}
            return {"total": sum(by_type.values()), "by_type": by_type}

    @router.get("/memories")
    async def memories(project_slug: str | None = None, type: str | None = None, q: str | None = None, limit: int = 100) -> list[dict]:
        async with maker() as s:
            repo = MemoryRepository(s)
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                mems = await repo.list(project_ids=[pid] if pid else [], type=type, q=q, limit=limit)
            else:
                mems = await repo.list(type=type, q=q, limit=limit)
            result = []
            for m in mems:
                d = {
                    "id": str(m.id), "type": m.type, "name": m.name,
                    "description": m.description, "content": m.content,
                    "importance": m.importance, "hit_count": m.hit_count,
                    "last_hit_at": m.last_hit_at.isoformat() if m.last_hit_at else None,
                    "project_id": str(m.project_id), "updated_at": m.updated_at.isoformat(),
                }
                if m.why:
                    d["why"] = m.why
                if m.how_to_apply:
                    d["how_to_apply"] = m.how_to_apply
                result.append(d)
            return result

    @router.delete("/memories/{memory_id}", status_code=204)
    async def delete_memory(memory_id: uuid.UUID, hard: bool = False) -> None:
        async with maker() as s:
            repo = MemoryRepository(s)
            m = await repo.get(memory_id, include_superseded=True)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            await repo.delete(memory_id, hard=hard)
            await s.commit()

    @router.patch("/memories/{memory_id}/move", status_code=200)
    async def move_memory(memory_id: uuid.UUID, project_slug: str) -> dict:
        from sqlalchemy import update as sa_update
        from memory_orchestrator.models import Memory
        async with maker() as s:
            repo = MemoryRepository(s)
            m = await repo.get(memory_id)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            target_uuid = await repo.slug_to_id(project_slug)
            if not target_uuid:
                raise HTTPException(status_code=404, detail=f"project not found: {project_slug}")
            await s.execute(sa_update(Memory).where(Memory.id == memory_id).values(project_id=target_uuid))
            await s.commit()
        return {"moved": True, "project_slug": project_slug}

    @router.get("/settings")
    async def get_settings_endpoint() -> dict:
        s = get_settings()
        defaults = {
            "extraction_base_url": s.extraction_base_url,
            "extraction_model": s.extraction_model,
            "extraction_api_key": s.extraction_api_key,
            "embed_model": s.embed_model,
            "embed_dim": str(s.embed_dim),
            "hook_cooldown_sec": "300",
            "hook_min_turns": "1",
            "hook_budget_tokens": "1500",
            "search_top_k": "8",
            "dup_threshold": "0.92",
            "db_dsn": s.db_dsn,
            "http_port": str(s.http_port),
        }
        async with maker() as session:
            repo = MemoryRepository(session)
            overrides = await repo.get_settings()
        merged = {**defaults, **{k: v for k, v in overrides.items() if k in SETTINGS_KEYS}}
        # mask api key
        merged["extraction_api_key"] = "***" if merged.get("extraction_api_key") else ""
        return merged

    @router.patch("/settings", status_code=200)
    async def patch_settings(body: SettingsPatch = Body(...)) -> dict:
        updates = {k: v for k, v in body.model_dump().items() if v is not None and v != "***"}
        if not updates:
            return {"saved": 0}
        async with maker() as session:
            repo = MemoryRepository(session)
            await repo.set_settings(updates)
            await session.commit()
        return {"saved": len(updates)}

    @router.get("/models")
    async def list_models(base_url: str, x_api_key: str | None = Header(default=None)) -> list[str]:
        api_key = x_api_key or ""
        if not api_key:
            async with maker() as s:
                repo = MemoryRepository(s)
                cfg = await repo.get_settings()
                api_key = cfg.get("extraction_api_key", "") or get_settings().extraction_api_key
        url = base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
        return sorted(models)

    return router
