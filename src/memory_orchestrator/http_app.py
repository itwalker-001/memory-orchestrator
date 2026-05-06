from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from memory_orchestrator.config import get_settings
from memory_orchestrator.db_check import (
    check_database_dsn,
    check_database_ready,
    format_database_startup_error,
)
from memory_orchestrator.embedder import ensure_loaded as ensure_embedder
from memory_orchestrator.router_hooks import make_hooks_router
from memory_orchestrator.router_ui import make_ui_router


def create_app(*, engine_override: AsyncEngine | None = None, skip_embedder: bool = False) -> FastAPI:
    settings = get_settings()
    engine = engine_override or create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI(title="Memory Orchestrator")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.on_event("startup")
    async def _startup() -> None:
        try:
            if engine_override is None:
                await check_database_dsn(settings.db_dsn)
            else:
                await check_database_ready(engine)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).critical(
                format_database_startup_error(settings.db_dsn, exc)
            )
            raise
        if not skip_embedder:
            ensure_embedder()

    app.include_router(make_hooks_router(engine=engine, maker=maker, skip_embedder=skip_embedder))
    app.include_router(make_ui_router(maker=maker))

    _dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if _dist.exists():
        app.mount("/ui", StaticFiles(directory=str(_dist), html=True), name="ui")

    return app
