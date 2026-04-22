from __future__ import annotations
import logging
from fastapi import FastAPI, Response, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from memory_orchestrator.config import get_settings
from memory_orchestrator.models import Memory
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.ingestor import ingest_session
from memory_orchestrator.embedder import ensure_loaded as ensure_embedder

log = logging.getLogger(__name__)


class IngestRequest(BaseModel):
    session_id: str
    project_id: str
    transcript_path: str


def create_app(*, engine_override: AsyncEngine | None = None, skip_embedder: bool = False) -> FastAPI:
    settings = get_settings()
    engine = engine_override or create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI(title="Memory Orchestrator")

    @app.on_event("startup")
    async def _startup() -> None:
        if not skip_embedder:
            ensure_embedder()

    @app.get("/healthz")
    async def healthz() -> dict:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = "ok"
        except Exception as e:
            db_ok = f"err:{e}"
        return {"db": db_ok, "embedder": "skipped" if skip_embedder else "ok"}

    @app.get("/context")
    async def context(project_id: str, budget_tokens: int = 1500) -> Response:
        async with maker() as s:
            repo = MemoryRepository(s)
            md = await repo.build_context(project_id=project_id, budget_tokens=budget_tokens)
        return Response(content=md, media_type="text/markdown; charset=utf-8")

    @app.get("/stats")
    async def stats(project_id: str | None = None) -> dict:
        async with maker() as s:
            stmt = select(Memory.type, func.count()).where(Memory.superseded_by.is_(None))
            if project_id:
                stmt = stmt.where(Memory.project_id == project_id)
            stmt = stmt.group_by(Memory.type)
            result = await s.execute(stmt)
            by_type = {row[0]: row[1] for row in result.all()}
            return {"total": sum(by_type.values()), "by_type": by_type}

    @app.post("/ingest", status_code=202)
    async def ingest(req: IngestRequest, background: BackgroundTasks) -> dict:
        async def _run() -> None:
            async with maker() as s:
                try:
                    await ingest_session(
                        db=s,
                        session_id=req.session_id,
                        project_id=req.project_id,
                        transcript_path=req.transcript_path,
                    )
                except Exception:
                    log.exception("ingest failed for session=%s", req.session_id)
        background.add_task(_run)
        return {"accepted": True}

    return app
