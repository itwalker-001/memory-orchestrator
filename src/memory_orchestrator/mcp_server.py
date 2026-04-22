from __future__ import annotations
import uuid
import logging
from typing import Any
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from memory_orchestrator.config import get_settings
from memory_orchestrator.embedder import embed_one, ensure_loaded as ensure_embedder
from memory_orchestrator.models import Memory
from memory_orchestrator.project_id import detect_project_id
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.ingestor import ingest_session

log = logging.getLogger(__name__)


async def handle_search_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> list[dict]:
    repo = MemoryRepository(session)
    query = args["query"]
    top_k = int(args.get("top_k", 8))
    types = args.get("type")
    scope = args.get("project_id")
    if scope == "all":
        project_ids = await _all_project_ids(session, extra=["*"])
    elif scope is None:
        project_ids = [current_project_id, "*"]
    else:
        project_ids = [scope]
    qvec = await embed_one(query)
    hits = await repo.search(query_embedding=qvec, project_ids=project_ids, types=types, top_k=top_k, record_hits=True)
    return [_memory_to_dict(h.memory, score=h.score) for h in hits]


async def handle_save_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    repo = MemoryRepository(session)
    mtype = args["type"]
    scope = args.get("project_id") or (current_project_id if mtype != "user" else "*")
    embedding = await embed_one(args["content"])
    replace_id = args.get("replace_id")
    if replace_id:
        await repo.delete(uuid.UUID(replace_id), hard=False)
        m = await repo.save(
            type=mtype, name=args["name"], description=args["description"],
            content=args["content"], why=args.get("why"), how_to_apply=args.get("how_to_apply"),
            importance=int(args.get("importance", 3)), project_id=scope, source="explicit", embedding=embedding,
        )
        return {"id": str(m.id), "action": "merged"}
    dups = await repo.find_duplicates(type=mtype, project_id=scope, embedding=embedding)
    if dups:
        return {"action": "conflict", "conflicts": [{"id": str(d.id), "name": d.name, "description": d.description} for d in dups]}
    m = await repo.save(
        type=mtype, name=args["name"], description=args["description"],
        content=args["content"], why=args.get("why"), how_to_apply=args.get("how_to_apply"),
        importance=int(args.get("importance", 3)), project_id=scope, source="explicit", embedding=embedding,
    )
    return {"id": str(m.id), "action": "created"}


async def handle_list_memories(*, session: AsyncSession, current_project_id: str, args: dict) -> list[dict]:
    repo = MemoryRepository(session)
    raw_type = args.get("type")
    mtype = (raw_type or [None])[0] if isinstance(raw_type, list) else raw_type
    mems = await repo.list(project_id=args.get("project_id"), type=mtype, limit=int(args.get("limit", 50)))
    return [{"id": str(m.id), "name": m.name, "description": m.description, "type": m.type, "importance": m.importance, "updated_at": m.updated_at.isoformat()} for m in mems]


async def handle_delete_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    repo = MemoryRepository(session)
    await repo.delete(uuid.UUID(args["id"]), hard=bool(args.get("hard", False)))
    return {"deleted": True}


async def handle_promote_memory(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    values: dict = {}
    if "importance" in args:
        values["importance"] = int(args["importance"])
    if args.get("make_global"):
        values["project_id"] = "*"
    if values:
        await session.execute(update(Memory).where(Memory.id == uuid.UUID(args["id"])).values(**values))
        await session.commit()
    return {"updated": True, "changes": list(values.keys())}


async def handle_ingest_session(*, session: AsyncSession, current_project_id: str, args: dict) -> dict:
    result = await ingest_session(
        db=session, session_id=args["session_id"],
        project_id=args.get("project_id") or current_project_id,
        transcript_path=args["transcript_path"],
    )
    return {"extracted": result.extracted, "saved": result.saved, "skipped": result.skipped}


def _memory_to_dict(m, *, score: float | None = None) -> dict:
    d = {"id": str(m.id), "name": m.name, "description": m.description, "content": m.content,
         "type": m.type, "project_id": m.project_id, "importance": m.importance}
    if m.why:
        d["why"] = m.why
    if m.how_to_apply:
        d["how_to_apply"] = m.how_to_apply
    if score is not None:
        d["score"] = round(score, 4)
    return d


async def _all_project_ids(session: AsyncSession, extra: list[str]) -> list[str]:
    from sqlalchemy import select
    from memory_orchestrator.models import Project
    result = await session.execute(select(Project.id))
    ids = [r[0] for r in result.all()]
    return list({*ids, *extra})


_TOOLS: list[Tool] = [
    Tool(name="search_memory", description="Retrieve memories by semantic similarity.",
         inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "project_id": {"type": "string"}, "type": {"type": "array", "items": {"type": "string"}}, "top_k": {"type": "integer", "default": 8}}, "required": ["query"]}),
    Tool(name="save_memory", description="Save a memory; returns conflicts if near-duplicate exists.",
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


async def run_stdio_server() -> None:
    ensure_embedder()
    settings = get_settings()
    engine = create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    app = Server("memory-orchestrator")

    @app.list_tools()
    async def _list_tools() -> list[Tool]:
        return _TOOLS

    @app.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        import os, json
        cwd = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        current_pid = detect_project_id(cwd)
        async with maker() as s:
            handler = _DISPATCH.get(name)
            if not handler:
                return [TextContent(type="text", text=f'{{"error":"unknown tool {name}"}}')]
            result = await handler(session=s, current_project_id=current_pid, args=arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())
