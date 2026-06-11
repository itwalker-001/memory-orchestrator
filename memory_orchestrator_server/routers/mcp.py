from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from memory_orchestrator_server.auth_tokens import TOKEN_KIND_PROJECT, resolve_project_token
from memory_orchestrator_server.mcp_core import DISPATCH, handle_read_memory_resource
from memory_orchestrator_server.repository import MemoryRepository


class McpToolRequest(BaseModel):
    name: str
    arguments: dict = {}
    project_slug: str = ""      # informational; project resolved from token (fallback for env token)
    cwd: str | None = None
    client: str | None = None
    os_user: str | None = None


class McpResourceRequest(BaseModel):
    uri: str
    project_slug: str = ""
    cwd: str | None = None
    client: str | None = None
    os_user: str | None = None


class SkeletonNodeCreateRequest(BaseModel):
    name: str
    parent_name: str | None = None
    description: str = ""
    prompt_hint: str = ""
    project_slug: str = ""      # fallback when token doesn't resolve a project
    cwd: str | None = None


def make_mcp_http_router(*, maker: async_sessionmaker) -> APIRouter:
    router = APIRouter(prefix="/mcp", tags=["MCP"])

    @router.post("/tools/call", summary="Call an MCP tool", description="Dispatches a named MCP tool (search_memory, save_memory, list/delete/promote, ingest) for the token's project. Project resolved from the project_token; falls back to project_slug for env-token mode.")
    async def call_tool(
        body: McpToolRequest = Body(...),
        authorization: str | None = Header(default=None),
    ) -> dict:
        handler = DISPATCH.get(body.name)
        if not handler:
            raise HTTPException(status_code=404, detail=f"unknown tool: {body.name}")
        async with maker() as s:
            _, project_uuid = await resolve_project_token(session=s, authorization=authorization)
            repo = MemoryRepository(s)
            if project_uuid is None:
                if not body.project_slug:
                    raise HTTPException(status_code=400, detail="project_slug required")
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

    @router.get("/skeleton", summary="Get skeleton tree", description="Returns the full nested knowledge-skeleton tree (with prompt_hint and tags) for the token's project.")
    async def get_skeleton(
        authorization: str | None = Header(default=None),
        project_slug: str = "",
        cwd: str | None = None,
    ) -> dict:
        """Return the full skeleton tree (with prompt_hint) for the token's project."""
        async with maker() as s:
            _, project_uuid = await resolve_project_token(session=s, authorization=authorization)
            repo = MemoryRepository(s)
            if project_uuid is None:
                if not project_slug:
                    raise HTTPException(status_code=400, detail="project_slug required")
                project_uuid = await repo.ensure_project(project_slug, cwd)
            tree = await repo.get_skeleton_tree(project_uuid)
            await s.commit()
        return {"project_id": str(project_uuid), "skeleton": tree}

    @router.post("/skeleton", status_code=201, summary="Create skeleton node", description="Create (or reuse) a skeleton node by name for the token's project. Idempotent on (name, parent).")
    async def create_skeleton_node(
        body: SkeletonNodeCreateRequest = Body(...),
        authorization: str | None = Header(default=None),
    ) -> dict:
        """Create (or reuse) a skeleton node by name for the token's project.

        Idempotent: returns the existing node if one with the same name/parent exists.
        Pass ``parent_name`` to nest under a top-level node; omit for a root node.
        ``prompt_hint`` (and ``description``) describe what content belongs in the node and
        drive future routing — set a clear hint when creating a new category.
        """
        async with maker() as s:
            _, project_uuid = await resolve_project_token(session=s, authorization=authorization)
            repo = MemoryRepository(s)
            if project_uuid is None:
                if not body.project_slug:
                    raise HTTPException(status_code=400, detail="project_slug required")
                project_uuid = await repo.ensure_project(body.project_slug, body.cwd)
            node_id = await repo.get_or_create_skeleton_node(
                project_id=project_uuid,
                name=body.name,
                parent_name=body.parent_name,
                description=body.description,
                prompt_hint=body.prompt_hint,
            )
            await s.commit()
        return {"project_id": str(project_uuid), "node_id": str(node_id)}

    @router.post("/resources/read", summary="Read an MCP resource", description="Reads an MCP memory resource by URI for the token's project.")
    async def read_resource(
        body: McpResourceRequest = Body(...),
        authorization: str | None = Header(default=None),
    ) -> dict:
        async with maker() as s:
            _, project_uuid = await resolve_project_token(session=s, authorization=authorization)
            repo = MemoryRepository(s)
            if project_uuid is None:
                if not body.project_slug:
                    raise HTTPException(status_code=400, detail="project_slug required")
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
