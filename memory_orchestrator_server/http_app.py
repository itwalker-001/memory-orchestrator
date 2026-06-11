from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


def read_version() -> str:
    """App version from version.txt (single source of truth), falling back to 0.0.0."""
    try:
        return (Path(__file__).parent / "version.txt").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


class SPAStaticFiles(StaticFiles):
    """Serve index.html for any path that doesn't match a static file (SPA fallback)."""
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (StarletteHTTPException, FastAPIHTTPException) as exc:
            if getattr(exc, "status_code", None) == 404:
                return await super().get_response("index.html", scope)
            raise
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.db_check import (
    check_database_dsn,
    check_database_ready,
    format_database_startup_error,
)
from memory_orchestrator_server.embedder import ensure_loaded as ensure_embedder
from memory_orchestrator_server.reranker import ensure_loaded as ensure_reranker
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.routers.hooks import make_hooks_router
from memory_orchestrator_server.routers.mcp import make_mcp_http_router
from memory_orchestrator_server.routers.ui import SETTINGS_SEED, make_ui_router


def create_app(*, engine_override: AsyncEngine | None = None, skip_embedder: bool = False) -> FastAPI:
    settings = get_settings()
    engine = engine_override or create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI(
        title="Memory Orchestrator",
        version=read_version(),
        description=(
            "Memory Orchestrator HTTP API — context injection hooks, the MCP bridge "
            "(search/save/skeleton), and the admin UI/API for managing memories, "
            "projects, the knowledge skeleton, tokens and runtime settings."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "Hooks", "description": "Claude Code / Codex hook endpoints: health, context injection, ingestion."},
            {"name": "MCP", "description": "MCP stdio-bridge endpoints: tool calls, resource reads, skeleton access."},
            {"name": "Auth", "description": "UI session login / logout."},
            {"name": "Tokens", "description": "API token administration (ui_admin & project_token)."},
            {"name": "Memories", "description": "CRUD, clone/move, batch ops, import/export, duplicate & conflict scans."},
            {"name": "Projects", "description": "Project listing and management."},
            {"name": "Skeleton", "description": "Knowledge-tree nodes and node↔memory links."},
            {"name": "Settings", "description": "Runtime configuration (system_settings) and model discovery."},
            {"name": "System", "description": "Miscellaneous: stats, timezone."},
        ],
    )
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
        async with maker() as session:
            repo = MemoryRepository(session)
            await repo.seed_settings(SETTINGS_SEED)
            await session.commit()
        if not skip_embedder:
            ensure_embedder()
            ensure_reranker()

    app.include_router(make_hooks_router(engine=engine, maker=maker, skip_embedder=skip_embedder))
    app.include_router(make_ui_router(maker=maker))
    app.include_router(make_mcp_http_router(maker=maker))

    _dist = Path(__file__).parent / "frontend" / "dist"
    if _dist.exists():
        app.mount("/ui", SPAStaticFiles(directory=str(_dist), html=True), name="ui")

    return app
