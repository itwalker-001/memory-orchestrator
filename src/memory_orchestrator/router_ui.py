from __future__ import annotations
import uuid
import httpx
from fastapi import APIRouter, Body, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import async_sessionmaker

from memory_orchestrator.config import get_settings
from memory_orchestrator.models import GLOBAL_PROJECT_ID, Memory, Project
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.time_utils import isoformat_utc, utc_now

SETTINGS_KEYS = ["extraction_base_url", "extraction_model", "extraction_api_key", "embed_model", "embed_dim",
                 "hook_cooldown_sec", "hook_min_turns", "hook_budget_tokens",
                 "search_top_k", "dup_threshold", "db_dsn", "http_port"]


class MemoryCreate(BaseModel):
    type: str
    name: str
    description: str
    content: str
    why: str | None = None
    how_to_apply: str | None = None
    importance: int = 3
    project_id: str | None = None  # slug; None → global
    source_client: str = "claude"


class MemoryPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    why: str | None = None
    how_to_apply: str | None = None
    importance: int | None = None


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


class BatchDeleteBody(BaseModel):
    ids: list[uuid.UUID]


class BatchMoveBody(BaseModel):
    ids: list[uuid.UUID]
    project_slug: str


def make_ui_router(*, maker: async_sessionmaker) -> APIRouter:
    router = APIRouter(prefix="/api")

    async def _pg_dsn() -> str:
        async with maker() as s:
            repo = MemoryRepository(s)
            cfg = await repo.get_settings()
        dsn = cfg.get("db_dsn") or get_settings().db_dsn
        return dsn.replace("postgresql+asyncpg://", "postgresql://")

    def _pg_bin(name: str) -> str:
        import glob
        import sys
        if sys.platform == "win32":
            candidates = sorted(glob.glob(f"C:/Program Files/PostgreSQL/*/bin/{name}.exe"), reverse=True)
            if candidates:
                return candidates[0]
        return name

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
    async def projects(hide_empty: bool = False) -> list[dict]:
        async with maker() as s:
            stmt = select(Project).order_by(
                (Project.id == GLOBAL_PROJECT_ID).desc(),
                Project.memory_count.desc(),
            )
            if hide_empty:
                stmt = stmt.where(Project.memory_count > 0)
            result = await s.execute(stmt)
            return [
                {"id": str(p.id), "slug": p.slug, "display_name": p.display_name, "memory_count": p.memory_count}
                for p in result.scalars().all()
            ]

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
    async def memories(project_slug: str | None = None, type: str | None = None, q: str | None = None, limit: int = 100, sort_by: str = "time", sort_desc: bool = True) -> list[dict]:
        async with maker() as s:
            repo = MemoryRepository(s)
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                mems = await repo.list(project_ids=[pid] if pid else [], type=type, q=q, limit=limit, sort_by=sort_by, sort_desc=sort_desc)
            else:
                mems = await repo.list(type=type, q=q, limit=limit, sort_by=sort_by, sort_desc=sort_desc)
            result = []
            for m in mems:
                d = {
                    "id": str(m.id), "type": m.type, "name": m.name,
                    "description": m.description, "content": m.content,
                    "importance": m.importance, "hit_count": m.hit_count,
                    "source_client": m.source_client,
                    "last_hit_at": isoformat_utc(m.last_hit_at) if m.last_hit_at else None,
                    "project_id": str(m.project_id), "updated_at": isoformat_utc(m.updated_at),
                }
                if m.why:
                    d["why"] = m.why
                if m.how_to_apply:
                    d["how_to_apply"] = m.how_to_apply
                result.append(d)
            return result

    @router.post("/memories", status_code=201)
    async def create_memory(body: MemoryCreate = Body(...)) -> dict:
        from memory_orchestrator.embedder import embed_one
        if body.type not in ("user", "feedback", "project", "reference"):
            raise HTTPException(status_code=422, detail=f"invalid type: {body.type}")
        async with maker() as s:
            repo = MemoryRepository(s)
            if body.project_id:
                pid = await repo.slug_to_id(body.project_id)
                if not pid:
                    raise HTTPException(status_code=404, detail=f"project not found: {body.project_id}")
            else:
                pid = GLOBAL_PROJECT_ID
            embedding = await embed_one(body.content)
            m = await repo.save(
                type=body.type, name=body.name, description=body.description,
                content=body.content, why=body.why or None, how_to_apply=body.how_to_apply or None,
                importance=max(1, min(5, body.importance)),
                project_id=pid, source="ui", embedding=embedding,
                source_client=body.source_client if body.source_client in {"claude", "codex"} else "claude",
            )
            await s.commit()
        return {"id": str(m.id), "action": "created"}

    @router.delete("/memories/{memory_id}", status_code=204)
    async def delete_memory(memory_id: uuid.UUID, hard: bool = False) -> None:
        async with maker() as s:
            repo = MemoryRepository(s)
            m = await repo.get(memory_id, include_superseded=True)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            await repo.delete(memory_id, hard=hard)
            await s.commit()

    @router.patch("/memories/{memory_id}", status_code=200)
    async def patch_memory(memory_id: uuid.UUID, body: MemoryPatch = Body(...)) -> dict:
        from memory_orchestrator.embedder import embed_one
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            return {"saved": 0}
        async with maker() as s:
            m = await s.get(Memory, memory_id)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            for k, v in updates.items():
                setattr(m, k, v)
            m.updated_at = utc_now()
            if "content" in updates:
                m.embedding = await embed_one(updates["content"])
            if "importance" in updates:
                m.importance = max(1, min(5, updates["importance"]))
            await s.commit()
        return {"saved": len(updates)}

    @router.post("/memories/{memory_id}/clone", status_code=201)
    async def clone_memory(memory_id: uuid.UUID, project_slug: str) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            src = await repo.get(memory_id)
            if not src:
                raise HTTPException(status_code=404, detail="not found")
            target_uuid = await repo.slug_to_id(project_slug)
            if not target_uuid:
                raise HTTPException(status_code=404, detail=f"project not found: {project_slug}")
            new_m = await repo.save(
                type=src.type, name=src.name, description=src.description,
                content=src.content, why=src.why, how_to_apply=src.how_to_apply,
                importance=src.importance, project_id=target_uuid,
                source="ui", source_client=src.source_client or "claude",
                embedding=src.embedding,
            )
            await s.commit()
        return {"id": str(new_m.id), "action": "cloned"}

    @router.patch("/memories/{memory_id}/move", status_code=200)
    async def move_memory(memory_id: uuid.UUID, project_slug: str) -> dict:
        from memory_orchestrator.repository import _sync_project_count
        async with maker() as s:
            repo = MemoryRepository(s)
            m = await repo.get(memory_id)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            target_uuid = await repo.slug_to_id(project_slug)
            if not target_uuid:
                raise HTTPException(status_code=404, detail=f"project not found: {project_slug}")
            old_uuid = m.project_id
            await s.execute(sa_update(Memory).where(Memory.id == memory_id).values(project_id=target_uuid))
            if old_uuid != target_uuid:
                await s.execute(_sync_project_count(old_uuid))
                await s.execute(_sync_project_count(target_uuid))
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

    @router.post("/memories/batch-delete", status_code=200)
    async def batch_delete(body: BatchDeleteBody = Body(...)) -> dict:
        deleted = 0
        async with maker() as s:
            repo = MemoryRepository(s)
            for mid in body.ids:
                m = await repo.get(mid, include_superseded=True)
                if m:
                    await repo.delete(mid, hard=False)
                    deleted += 1
            await s.commit()
        return {"deleted": deleted}

    @router.post("/memories/batch-move", status_code=200)
    async def batch_move(body: BatchMoveBody = Body(...)) -> dict:
        from memory_orchestrator.repository import _sync_project_count
        async with maker() as s:
            repo = MemoryRepository(s)
            target_uuid = await repo.slug_to_id(body.project_slug)
            if not target_uuid:
                raise HTTPException(status_code=404, detail=f"project not found: {body.project_slug}")
            affected: set = set()
            moved = 0
            for mid in body.ids:
                m = await repo.get(mid)
                if not m:
                    continue
                affected.add(m.project_id)
                await s.execute(sa_update(Memory).where(Memory.id == mid).values(project_id=target_uuid))
                moved += 1
            affected.add(target_uuid)
            for pid in affected:
                await s.execute(_sync_project_count(pid))
            await s.commit()
        return {"moved": moved, "project_slug": body.project_slug}

    @router.get("/export")
    async def export_memories(project_slug: str | None = None, type: str | None = None, q: str | None = None) -> list[dict]:
        async with maker() as s:
            repo = MemoryRepository(s)
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                mems = await repo.list(project_ids=[pid] if pid else [], type=type, q=q, limit=10000, sort_by="time", sort_desc=True)
            else:
                mems = await repo.list(type=type, q=q, limit=10000, sort_by="time", sort_desc=True)
            proj_result = await s.execute(select(Project))
            slug_map = {p.id: p.slug for p in proj_result.scalars().all()}
            result = []
            for m in mems:
                d = {
                    "type": m.type, "name": m.name,
                    "description": m.description, "content": m.content,
                    "importance": m.importance,
                    "source_client": m.source_client,
                    "project_slug": slug_map.get(m.project_id, "*"),
                }
                if m.why:
                    d["why"] = m.why
                if m.how_to_apply:
                    d["how_to_apply"] = m.how_to_apply
                result.append(d)
            return result

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
                ct = r.headers.get("content-type", "")
                if "json" not in ct:
                    raise HTTPException(status_code=502, detail=f"Non-JSON response from {url} (content-type: {ct}). Check base_url — it should include /v1 (e.g. https://api.example.com/v1)")
                data = r.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
        return sorted(models)

    @router.get("/duplicates")
    async def find_duplicates(
        threshold: float | None = None,
        project_slug: str | None = None,
        type: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        from sqlalchemy import text
        async with maker() as s:
            repo = MemoryRepository(s)
            cfg = await repo.get_settings()
            effective_threshold = threshold
            if effective_threshold is None:
                effective_threshold = float(cfg.get("dup_threshold") or 0.92)
            params: dict = {"threshold": effective_threshold, "limit": limit}
            filters = []
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                if not pid:
                    return []
                filters.append("m1.project_id = :project_id AND m2.project_id = :project_id")
                params["project_id"] = pid
            if type:
                filters.append("m1.type = :type AND m2.type = :type")
                params["type"] = type
            where_extra = f" AND {' AND '.join(filters)}" if filters else ""
            result = await s.execute(text(f"""
                SELECT
                    m1.id AS id1, m1.type AS type1, m1.name AS name1,
                    m1.description AS desc1, m1.content AS content1, m1.project_id AS pid1,
                    m2.id AS id2, m2.type AS type2, m2.name AS name2,
                    m2.description AS desc2, m2.content AS content2, m2.project_id AS pid2,
                    1 - (m1.embedding <=> m2.embedding) AS similarity
                FROM memories m1
                JOIN memories m2 ON m1.id < m2.id
                WHERE m1.superseded_by IS NULL
                  AND m2.superseded_by IS NULL
                  AND m1.embedding IS NOT NULL
                  AND m2.embedding IS NOT NULL
                  {where_extra}
                  AND 1 - (m1.embedding <=> m2.embedding) >= :threshold
                ORDER BY similarity DESC
                LIMIT :limit
            """), params)
            rows = result.fetchall()
            proj_result = await s.execute(select(Project))
            slug_map = {p.id: p.slug for p in proj_result.scalars().all()}
        pairs = []
        for row in rows:
            pairs.append({
                "id1": str(row.id1), "type1": row.type1, "name1": row.name1,
                "description1": row.desc1, "content1": row.content1,
                "project_slug1": slug_map.get(row.pid1, "*"),
                "id2": str(row.id2), "type2": row.type2, "name2": row.name2,
                "description2": row.desc2, "content2": row.content2,
                "project_slug2": slug_map.get(row.pid2, "*"),
                "similarity": round(float(row.similarity), 3),
            })
        return pairs

    @router.get("/backup")
    async def backup_db():
        import asyncio
        import datetime
        from fastapi.responses import Response
        dsn = await _pg_dsn()
        proc = await asyncio.create_subprocess_exec(
            _pg_bin("pg_dump"), "--clean", "--if-exists", "--format=plain", dsn,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=stderr.decode(errors="replace"))
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        return Response(
            content=stdout,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="mo-backup-{ts}.sql"'},
        )

    @router.post("/restore", status_code=200)
    async def restore_db(file: UploadFile):
        import asyncio
        import os
        import tempfile
        dsn = await _pg_dsn()
        sql_bytes = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
            f.write(sql_bytes)
            tmp = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                _pg_bin("psql"), dsn, "-f", tmp,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
        finally:
            os.unlink(tmp)
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=stderr.decode(errors="replace")[:1000])
        return {"ok": True}

    return router
