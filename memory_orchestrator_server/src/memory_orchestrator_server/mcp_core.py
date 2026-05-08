from __future__ import annotations

import os
import uuid
from typing import Any
from urllib.parse import unquote

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator_server.embedder import embed_one
from memory_orchestrator_server.ingestor import ingest_session
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.time_utils import isoformat_utc
from memory_orchestrator_server.mcp_contract import (
    RESOURCE_GUIDE,
    RESOURCE_PROJECT_PREFIX,
    RESOURCE_RECENT,
    TOOLS,
    list_memory_resource_templates,
    list_memory_resources,
    memory_resource_guide,
)


def current_client(client: str | None = None) -> str:
    explicit = (client or "").strip().lower()
    if explicit in {"claude", "codex"}:
        return explicit
    env_client = (os.environ.get("MO_CLIENT") or "").strip().lower()
    if env_client in {"claude", "codex"}:
        return env_client
    return "claude"


async def handle_search_memory(*, session: AsyncSession, project_uuid: uuid.UUID, args: dict, **_) -> list[dict]:
    repo = MemoryRepository(session)
    query = args["query"]
    cfg = await repo.get_settings()
    default_top_k = int(cfg.get("search_top_k") or 3)
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
    hits = await repo.search(
        query_embedding=qvec, project_ids=project_ids, types=types,
        top_k=top_k, record_hits=True, query=query,
    )
    return [_memory_to_dict(h.memory, score=h.score) for h in hits]


async def handle_save_memory(
    *, session: AsyncSession, project_uuid: uuid.UUID, args: dict, cwd: str = "",
    client: str | None = None, **_
) -> dict:
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
            source="explicit", source_client=current_client(client), embedding=embedding,
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
        source_client=current_client(client),
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


async def handle_ingest_session(
    *, session: AsyncSession, project_uuid: uuid.UUID, args: dict,
    client: str | None = None, **_
) -> dict:
    result = await ingest_session(
        db=session,
        session_id=args["session_id"],
        project_id=project_uuid,
        transcript_path=args["transcript_path"],
        source_client=current_client(client),
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


DISPATCH = {
    "search_memory": handle_search_memory,
    "save_memory": handle_save_memory,
    "list_memories": handle_list_memories,
    "delete_memory": handle_delete_memory,
    "promote_memory": handle_promote_memory,
    "ingest_session": handle_ingest_session,
}


async def handle_read_memory_resource(
    *, session: AsyncSession, project_uuid: uuid.UUID, uri: str, **_
) -> str:
    repo = MemoryRepository(session)
    uri_text = str(uri)
    if uri_text == RESOURCE_GUIDE:
        return memory_resource_guide()
    if uri_text == RESOURCE_RECENT:
        mems = await repo.list(project_ids=[project_uuid, GLOBAL_PROJECT_ID], limit=12)
        return format_memory_resource(
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
        return format_memory_resource(
            title=f"Project Memories: {slug}",
            mems=mems,
            empty=f"No memories found for project `{slug}`.",
        )
    raise ValueError(f"Unknown memory resource URI: {uri_text}")


def format_memory_resource(*, title: str, mems: list[Memory], empty: str) -> str:
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
