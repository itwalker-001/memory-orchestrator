from __future__ import annotations
import logging
from fastapi import APIRouter, BackgroundTasks, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from memory_orchestrator.ingestor import ingest_session
from memory_orchestrator.repository import MemoryRepository

log = logging.getLogger(__name__)


class IngestRequest(BaseModel):
    session_id: str
    project_slug: str
    transcript_path: str


def make_hooks_router(*, engine: AsyncEngine, maker: async_sessionmaker, skip_embedder: bool = False) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = "ok"
        except Exception as e:
            db_ok = f"err:{e}"
        return {"db": db_ok, "embedder": "skipped" if skip_embedder else "ok"}

    @router.get("/context")
    async def context(project_slug: str, budget_tokens: int | None = None) -> Response:
        async with maker() as s:
            repo = MemoryRepository(s)
            cfg = await repo.get_settings()
            effective_budget = budget_tokens or int(cfg.get("hook_budget_tokens") or 1500)
            project_uuid = await repo.ensure_project(project_slug)
            await s.commit()
            md = await repo.build_context(project_id=project_uuid, budget_tokens=effective_budget)
        return Response(content=md, media_type="text/markdown; charset=utf-8")

    @router.post("/ingest", status_code=202)
    async def ingest(req: IngestRequest, background: BackgroundTasks) -> dict:
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
                    log.exception("ingest failed for session=%s", req.session_id)
        background.add_task(_run)
        return {"accepted": True}

    return router
