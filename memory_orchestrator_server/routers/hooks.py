from __future__ import annotations
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memory_orchestrator_server.ingestor import ingest_session
from memory_orchestrator_server.models import Memory
from memory_orchestrator_server.repository import MemoryRepository

log = logging.getLogger(__name__)


class IngestRequest(BaseModel):
    session_id: str
    project_slug: str
    transcript_path: str
    client: str | None = None


def make_hooks_router(*, engine: AsyncEngine, maker: async_sessionmaker, skip_embedder: bool = False) -> APIRouter:
    router = APIRouter(tags=["Hooks"])

    @router.get("/healthz", summary="Health check", description="Returns database connectivity, embedder load status, and app version. Used by Docker healthchecks and the build script.")
    async def healthz() -> dict:
        from memory_orchestrator_server.http_app import read_version
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = "ok"
        except Exception as e:
            db_ok = f"err:{e}"
        return {"db": db_ok, "embedder": "skipped" if skip_embedder else "ok", "version": read_version()}

    @router.get("/context", summary="Build injected context", description="Returns markdown memory context for a project, truncated to the token budget. Called by the UserPromptSubmit hook.")
    async def context(
        project_slug: str | None = None,
        project_id: str | None = None,
        budget_tokens: int | None = None,
        client: str | None = None,
    ) -> Response:
        slug = project_slug or project_id
        if not slug:
            raise HTTPException(status_code=422, detail="project_slug or project_id is required")
        log.info("context client=%s project=%s", client or "unknown", slug)
        async with maker() as s:
            repo = MemoryRepository(s)
            cfg = await repo.get_settings()
            effective_budget = budget_tokens or int(cfg.get("hook_budget_tokens") or 1500)
            project_uuid = await repo.ensure_project(slug)
            await s.commit()
            md = await repo.build_context(project_id=project_uuid, budget_tokens=effective_budget)
        return Response(content=md, media_type="text/markdown; charset=utf-8")

    @router.get("/stats", summary="Memory counts", description="Total memory count and a per-type breakdown, optionally filtered to a single project.")
    async def stats(project_slug: str | None = None, project_id: str | None = None) -> dict:
        slug = project_slug or project_id
        async with maker() as s:
            repo = MemoryRepository(s)
            stmt = select(Memory.type, func.count()).where(Memory.superseded_by.is_(None))
            if slug:
                pid = await repo.slug_to_id(slug)
                if pid:
                    stmt = stmt.where(Memory.project_id == pid)
                else:
                    stmt = stmt.where(Memory.project_id.in_([]))
            stmt = stmt.group_by(Memory.type)
            result = await s.execute(stmt)
            by_type = {row[0]: row[1] for row in result.all()}
            return {"total": sum(by_type.values()), "by_type": by_type}

    @router.post("/ingest", status_code=202, summary="Trigger ingestion", description="Queues background LLM extraction of memories from a session transcript. Called by the Stop hook. Returns immediately (202).")
    async def ingest(req: IngestRequest, background: BackgroundTasks) -> dict:
        log.info("ingest client=%s session=%s project=%s", req.client or "unknown", req.session_id, req.project_slug)
        async def _run() -> None:
            async with maker() as s:
                try:
                    repo = MemoryRepository(s)
                    project_uuid = await repo.ensure_project(req.project_slug)
                    await s.commit()
                    await ingest_session(
                        db=s,
                        session_id=req.session_id,
                        project_id=project_uuid,
                        transcript_path=req.transcript_path,
                    )
                except Exception:
                    log.exception("ingest failed for session=%s client=%s", req.session_id, req.client or "unknown")
        background.add_task(_run)
        return {"accepted": True}

    return router
