from __future__ import annotations
import uuid
import logging
import os
from typing import Any
from urllib.parse import unquote
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, ResourceTemplate, TextContent
from mcp.types import Tool

from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.embedder import embed_one
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory
from memory_orchestrator_server.project_id import detect_project_id
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.ingestor import ingest_session
from memory_orchestrator_server.time_utils import isoformat_utc, utc_now

log = logging.getLogger(__name__)


def current_client() -> str:
    client = (os.environ.get("MO_CLIENT") or "").strip().lower()
    if client in {"claude", "codex"}:
        return client
    return "claude"


async def handle_search_memory(*, session: AsyncSession, project_uuid: uuid.UUID, args: dict, **_) -> list[dict]:
    repo = MemoryRepository(session)
    query = args["query"]
    cfg = await repo.get_settings()
    default_top_k = int(cfg.get("search_top_k") or 8)
    top_k = int(args.get("top_k", default_top_k))
    types = args.get("type")
    scope_slug = args.get("project_id")
    if scope_slug == "all":
        from sqlalchemy import select
        from memory_orchestrator_server.models import Project
        result = await session.execute(select(Project.id))
        project_ids = list({r[0] for r in result.all()} | {GLOBAL_PROJECT_ID})
    elif scope_slug:
        pid = await repo.slug_to_id(scope_slug)
        project_ids = [pid] if pid else [GLOBAL_PROJECT_ID]
    else:
        project_ids = list({project_uuid, GLOBAL_PROJECT_ID})
    qvec = await embed_one(query)
    hits = await repo.search(query_embedding=qvec, project_ids=project_ids, types=types, top_k=top_k, record_hits=True)
    return [_memory_to_dict(h.memory, score=h.score) for h in hits]


async def handle_save_memory(*, session: AsyncSession, project_uuid: uuid.UUID, args: dict, cwd: str = "", **_) -> dict:
    repo = MemoryRepository(session)
    mtype = args["type"]
    scope_slug = args.get("project_id")
    if scope_slug:
        scope_uuid = await repo.ensure_project(scope_slug, cwd or None)
    elif mtype == "user":
        scope_uuid = await repo.ensure_project("*")
    else:
        scope_uuid = project_uuid
    embedding = await embed_one(args["content"])
    replace_id = args.get("replace_id")
    if replace_id:
        await repo.delete(uuid.UUID(replace_id), hard=False)
        m = await repo.save(
            type=mtype, name=args["name"], description=args["description"],
            content=args["content"], why=args.get("why"), how_to_apply=args.get("how_to_apply"),
            importance=int(args.get("importance", 3)), project_id=scope_uuid,
            source="explicit", source_client=current_client(), embedding=embedding,
        )
        return {"id": str(m.id), "action": "merged"}
    dups = await repo.find_duplicates(type=mtype, project_id=scope_uuid, embedding=embedding,
                                       threshold=float((await repo.get_settings()).get("dup_threshold") or 0.92))
    if dups:
        return {"action": "conflict", "conflicts": [{"id": str(d.id), "name": d.name, "description": d.description} for d in dups]}
    m = await repo.save(
        type=mtype, name=args["name"], description=args["description"],
        content=args["content"], why=args.get("why"), how_to_apply=args.get("how_to_apply"),
        importance=int(args.get("importance", 3)), project_id=scope_uuid,
        source="explicit", embedding=embedding,
        source_client=current_client(),
    )
    return {"id": str(m.id), "action": "created"}


async def handle_list_memories(*, session: AsyncSession, project_uuid: uuid.UUID, args: dict, **_) -> list[dict]:
    repo = MemoryRepository(session)
    raw_type = args.get("type")
    mtype = (raw_type or [None])[0] if isinstance(raw_type, list) else raw_type
    scope_slug = args.get("project_id")
    if scope_slug == "all":
        mems = await repo.list(type=mtype, limit=int(args.get("limit", 50)))
    elif scope_slug:
        pid = await repo.slug_to_id(scope_slug)
        mems = await repo.list(project_id=pid, type=mtype, limit=int(args.get("limit", 50)))
    else:
        mems = await repo.list(project_ids=[project_uuid, GLOBAL_PROJECT_ID], type=mtype, limit=int(args.get("limit", 50)))
    result = []
    for m in mems:
        d = {"id": str(m.id), "name": m.name, "description": m.description,
             "type": m.type, "importance": m.importance, "updated_at": isoformat_utc(m.updated_at),
             "project_id": str(m.project_id)}
        if m.why:
            d["why"] = m.why
        if m.how_to_apply:
            d["how_to_apply"] = m.how_to_apply
        result.append(d)
    return result


async def handle_delete_memory(*, session: AsyncSession, args: dict, **_) -> dict:
    repo = MemoryRepository(session)
    await repo.delete(uuid.UUID(args["id"]), hard=bool(args.get("hard", False)))
    return {"deleted": True}


async def handle_promote_memory(*, session: AsyncSession, args: dict, **_) -> dict:
    from memory_orchestrator_server.repository import _sync_project_count
    memory_id = uuid.UUID(args["id"])
    values: dict = {}
    if "importance" in args:
        values["importance"] = int(args["importance"])
    old_project_id = None
    if args.get("make_global"):
        from sqlalchemy import select as sa_select
        row = await session.execute(sa_select(Memory.project_id).where(Memory.id == memory_id))
        old_project_id = row.scalar_one_or_none()
        values["project_id"] = GLOBAL_PROJECT_ID
    if values:
        await session.execute(update(Memory).where(Memory.id == memory_id).values(**values))
    if old_project_id and old_project_id != GLOBAL_PROJECT_ID:
        await session.execute(_sync_project_count(old_project_id))
        await session.execute(_sync_project_count(GLOBAL_PROJECT_ID))
    return {"updated": True, "changes": list(values.keys())}


async def handle_ingest_session(*, session: AsyncSession, project_uuid: uuid.UUID, args: dict, **_) -> dict:
    result = await ingest_session(
        db=session,
        session_id=args["session_id"],
        project_id=project_uuid,
        transcript_path=args["transcript_path"],
        source_client=current_client(),
    )
    return {"extracted": result.extracted, "saved": result.saved, "skipped": result.skipped}


def _memory_to_dict(m: Memory, *, score: float | None = None) -> dict:
    d = {"id": str(m.id), "name": m.name, "description": m.description, "content": m.content,
         "type": m.type, "project_id": str(m.project_id), "importance": m.importance,
         "source_client": m.source_client}
    if m.why:
        d["why"] = m.why
    if m.how_to_apply:
        d["how_to_apply"] = m.how_to_apply
    if score is not None:
        d["score"] = round(score, 4)
    return d


_TOOLS: list[Tool] = [
    Tool(name="search_memory", description="Retrieve memories by semantic similarity.",
         inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "project_id": {"type": "string"}, "type": {"type": "array", "items": {"type": "string"}}, "top_k": {"type": "integer", "default": 8}}, "required": ["query"]}),
    Tool(name="save_memory", description="Write a memory to Memory Orchestrator; returns conflicts if near-duplicate exists.",
         inputSchema={"type": "object", "properties": {"type": {"type": "string"}, "name": {"type": "string"}, "description": {"type": "string"}, "content": {"type": "string"}, "project_id": {"type": "string"}, "why": {"type": "string"}, "how_to_apply": {"type": "string"}, "importance": {"type": "integer"}, "replace_id": {"type": "string"}}, "required": ["type", "name", "description", "content"]}),
    Tool(name="list_memories", description="List memory summaries.",
         inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string"}, "limit": {"type": "integer", "default": 50}}}),
    Tool(name="delete_memory", description="Soft or hard delete a memory.",
         inputSchema={"type": "object", "properties": {"id": {"type": "string"}, "hard": {"type": "boolean"}}, "required": ["id"]}),
    Tool(name="promote_memory", description="Change importance or scope.",
         inputSchema={"type": "object", "properties": {"id": {"type": "string"}, "importance": {"type": "integer"}, "make_global": {"type": "boolean"}}, "required": ["id"]}),
    Tool(name="ingest_session", description="Ingest transcript for auto extraction.",
         inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}, "project_id": {"type": "string"}, "transcript_path": {"type": "string"}}, "required": ["session_id", "transcript_path"]}),
]

_DISPATCH = {
    "search_memory": handle_search_memory, "save_memory": handle_save_memory,
    "list_memories": handle_list_memories, "delete_memory": handle_delete_memory,
    "promote_memory": handle_promote_memory, "ingest_session": handle_ingest_session,
}


RESOURCE_GUIDE = "memory://orchestrator/guide"
RESOURCE_RECENT = "memory://recent"
RESOURCE_PROJECT_PREFIX = "memory://project/"
RESOURCE_MIME = "text/markdown"


def list_memory_resources() -> list[Resource]:
    return [
        Resource(
            name="Memory Orchestrator MCP guide",
            uri=RESOURCE_GUIDE,
            description=(
                "Read-only guide for memory-orchestrator. Writes are available through "
                "the MCP tool save_memory on this server, not resources/templates."
            ),
            mimeType=RESOURCE_MIME,
        ),
        Resource(
            name="Recent memories",
            uri=RESOURCE_RECENT,
            description=(
                "Read-only summary of recent memories. To write memories, call "
                "the save_memory tool from this MCP server."
            ),
            mimeType=RESOURCE_MIME,
        ),
    ]


def list_memory_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            name="Project memories",
            uriTemplate="memory://project/{slug}",
            description=(
                "Read-only summary of memories for a project slug. To write memories, call "
                "the save_memory tool from this MCP server with project_id."
            ),
            mimeType=RESOURCE_MIME,
        )
    ]


async def handle_read_memory_resource(
    *, session: AsyncSession, project_uuid: uuid.UUID, uri: str, **_
) -> str:
    repo = MemoryRepository(session)
    uri_text = str(uri)
    if uri_text == RESOURCE_GUIDE:
        return _memory_resource_guide()
    if uri_text == RESOURCE_RECENT:
        mems = await repo.list(project_ids=[project_uuid, GLOBAL_PROJECT_ID], limit=12)
        return _format_memory_resource(
            title="Recent Memories",
            mems=mems,
            empty="No recent memories found for the current project/global scope.",
        )
    if uri_text.startswith(RESOURCE_PROJECT_PREFIX):
        slug = unquote(uri_text.removeprefix(RESOURCE_PROJECT_PREFIX))
        if not slug:
            return "Project slug is required. Example: memory://project/my-project"
        if slug == "all":
            mems = await repo.list(limit=25)
        else:
            pid = await repo.slug_to_id(slug)
            mems = await repo.list(project_id=pid, limit=25) if pid else []
        return _format_memory_resource(
            title=f"Project Memories: {slug}",
            mems=mems,
            empty=f"No memories found for project `{slug}`.",
        )
    raise ValueError(f"Unknown memory resource URI: {uri_text}")


def _memory_resource_guide() -> str:
    return "\n".join(
        [
            "# Memory Orchestrator MCP",
            "",
            "This server exposes memories mainly as MCP tools.",
            "",
            "Use these tools:",
            "- `search_memory` to retrieve relevant memories.",
            "- `list_memories` to inspect memory summaries.",
            "- `save_memory` to write memories.",
            "- `promote_memory` to change importance or scope.",
            "- `delete_memory` to remove memories.",
            "",
            "Call the `save_memory` tool from this `memory-orchestrator` MCP server. Some "
            "clients may display that as `memory-orchestrator.save_memory`, but the tool "
            "name exposed by this server is `save_memory`.",
            "",
            "Resources are read-only discovery/context surfaces. Do not infer that writing is "
            "unavailable because resources/templates are read-only; write by calling "
            "the `save_memory` tool.",
        ]
    )


def _format_memory_resource(*, title: str, mems: list[Memory], empty: str) -> str:
    lines = [
        f"# {title}",
        "",
        "Read-only resource. To write memories, call the `save_memory` tool from this MCP server.",
        "",
    ]
    if not mems:
        lines.append(empty)
        return "\n".join(lines)
    for m in mems:
        lines.append(f"## [{m.type}] {m.name}")
        lines.append(f"- Description: {m.description}")
        lines.append(f"- Project ID: {m.project_id}")
        lines.append(f"- Source client: {m.source_client}")
        lines.append(f"- Importance: {m.importance}")
        if m.why:
            lines.append(f"- Why: {m.why}")
        if m.how_to_apply:
            lines.append(f"- How to apply: {m.how_to_apply}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _flog(msg: str) -> None:
    import os

    _log = os.path.expanduser("~/.claude/memory-orchestrator/mcp_debug.log")
    os.makedirs(os.path.dirname(_log), exist_ok=True)
    with open(_log, "a", encoding="utf-8") as f:
        f.write(f"{isoformat_utc(utc_now())} {msg}\n")


async def run_stdio_server() -> None:
    _flog("run_stdio_server: start")
    settings = get_settings()
    engine = create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    app = Server("memory-orchestrator")
    _flog("run_stdio_server: Server created")

    @app.list_tools()
    async def _list_tools() -> list[Tool]:
        return _TOOLS

    @app.list_resources()
    async def _list_resources() -> list[Resource]:
        return list_memory_resources()

    @app.list_resource_templates()
    async def _list_resource_templates() -> list[ResourceTemplate]:
        return list_memory_resource_templates()

    @app.read_resource()
    async def _read_resource(uri) -> str:
        cwd = (
            os.environ.get("CODEX_PROJECT_DIR")
            or os.environ.get("CLAUDE_PROJECT_DIR")
            or os.getcwd()
        )
        slug = detect_project_id(cwd)
        async with maker() as s:
            repo = MemoryRepository(s)
            project_uuid = await repo.ensure_project(slug, cwd)
            return await handle_read_memory_resource(
                session=s,
                project_uuid=project_uuid,
                uri=str(uri),
            )

    @app.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        import json
        import uuid as _uuid

        call_id = _uuid.uuid4().hex[:8]
        args_log = json.dumps({k: v for k, v in arguments.items() if k != 'content'}, ensure_ascii=False)[:200]
        _flog(f"[{call_id}] START tool={name} args={args_log}")
        cwd = (
            os.environ.get("CODEX_PROJECT_DIR")
            or os.environ.get("CLAUDE_PROJECT_DIR")
            or os.getcwd()
        )
        slug = detect_project_id(cwd)
        _flog(f"[{call_id}] slug={slug}")
        async with maker() as s:
            repo = MemoryRepository(s)
            project_uuid = await repo.ensure_project(slug, cwd)
            _flog(f"[{call_id}] project_uuid={project_uuid}")
            handler = _DISPATCH.get(name)
            if not handler:
                _flog(f"[{call_id}] ERROR unknown tool")
                return [TextContent(type="text", text=f'{{"error":"unknown tool {name}"}}')]
            try:
                result = await handler(session=s, project_uuid=project_uuid, args=arguments, cwd=cwd)
                await s.commit()
                _flog(f"[{call_id}] OK result={type(result).__name__}")
            except Exception as e:
                _flog(f"[{call_id}] ERROR {e!r}")
                raise
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())
