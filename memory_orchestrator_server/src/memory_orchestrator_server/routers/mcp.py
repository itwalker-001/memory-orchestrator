from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from memory_orchestrator_server.auth_tokens import TOKEN_KIND_MCP, require_token_kind
from memory_orchestrator_server.mcp_core import DISPATCH, handle_read_memory_resource
from memory_orchestrator_server.repository import MemoryRepository


class McpToolRequest(BaseModel):
    name: str
    arguments: dict = {}
    project_slug: str
    cwd: str | None = None
    client: str | None = None
    os_user: str | None = None


class McpResourceRequest(BaseModel):
    uri: str
    project_slug: str
    cwd: str | None = None
    client: str | None = None
    os_user: str | None = None


def make_mcp_http_router(*, maker: async_sessionmaker) -> APIRouter:
    router = APIRouter(prefix="/mcp")

    @router.post("/tools/call")
    async def call_tool(
        body: McpToolRequest = Body(...),
        authorization: str | None = Header(default=None),
    ) -> dict:
        handler = DISPATCH.get(body.name)
        if not handler:
            raise HTTPException(status_code=404, detail=f"unknown tool: {body.name}")
        async with maker() as s:
            await require_token_kind(session=s, kind=TOKEN_KIND_MCP, authorization=authorization)
            repo = MemoryRepository(s)
            project_uuid = await repo.ensure_project(body.project_slug, body.cwd)
            result = await handler(
                session=s,
                project_uuid=project_uuid,
                args=body.arguments,
                cwd=body.cwd or "",
                client=body.client,
            )
            await s.commit()
        return {"result": result}

    @router.post("/resources/read")
    async def read_resource(
        body: McpResourceRequest = Body(...),
        authorization: str | None = Header(default=None),
    ) -> dict:
        async with maker() as s:
            await require_token_kind(session=s, kind=TOKEN_KIND_MCP, authorization=authorization)
            repo = MemoryRepository(s)
            project_uuid = await repo.ensure_project(body.project_slug, body.cwd)
            try:
                result = await handle_read_memory_resource(
                    session=s,
                    project_uuid=project_uuid,
                    uri=body.uri,
                )
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            await s.commit()
        return {"result": result}

    return router
