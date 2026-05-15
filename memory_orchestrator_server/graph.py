"""Apache AGE graph integration — vertex/edge management and traversal.

All public functions silently no-op when the session factory has not been
initialised (tests) or when a graph operation fails.  Each function runs in
its own short-lived session so failures never abort the caller's transaction.
"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Literal, Sequence

from pydantic import BaseModel
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

_GRAPH = "memory_graph"
_maker: "async_sessionmaker[AsyncSession] | None" = None


def init(maker: "async_sessionmaker[AsyncSession]") -> None:
    global _maker
    _maker = maker


async def _exec(cypher: str) -> list:
    """Open a dedicated session, run one Cypher statement, return rows."""
    if _maker is None:
        return []
    try:
        async with _maker() as session:
            async with session.begin():
                await session.execute(text("LOAD 'age'"))
                await session.execute(
                    text('SET LOCAL search_path = ag_catalog, "$user", public')
                )
                result = await session.execute(text(cypher))
                return list(result)
    except Exception:
        logger.debug("graph op failed: %.120s", cypher, exc_info=True)
        return []


async def ensure_vertex(memory_id: uuid.UUID, memory_type: str) -> None:
    """Upsert a Memory vertex."""
    mid = str(memory_id)
    mtype = memory_type.replace("'", "\\'")
    await _exec(
        f"SELECT * FROM cypher('{_GRAPH}', $$ "
        f"MERGE (m:Memory {{id: '{mid}', type: '{mtype}'}}) RETURN m "
        f"$$) AS (v agtype)"
    )


async def delete_vertex(memory_id: uuid.UUID) -> None:
    """Delete a Memory vertex and all its edges."""
    mid = str(memory_id)
    await _exec(
        f"SELECT * FROM cypher('{_GRAPH}', $$ "
        f"MATCH (m:Memory {{id: '{mid}'}}) DETACH DELETE m RETURN 1 "
        f"$$) AS (v agtype)"
    )


_VALID_REL_TYPES = {"REFINES", "CONTRADICTS", "SUPPORTS", "SUPERSEDES", "RELATES_TO"}

_RELATION_SYSTEM_PROMPT = """\
Analyze semantic relationships between a NEW memory and EXISTING memories.

Relationship types (pick the most specific):
- REFINES: new adds detail or nuance to existing
- CONTRADICTS: new conflicts with existing
- SUPPORTS: new reinforces or corroborates existing
- SUPERSEDES: new replaces or updates existing
- RELATES_TO: general semantic connection

Use exact IDs from the list. Only include high-confidence relationships.\
"""

RelType = Literal["REFINES", "CONTRADICTS", "SUPPORTS", "SUPERSEDES", "RELATES_TO"]


class _Relation(BaseModel):
    tgt: str
    type: RelType = "RELATES_TO"


class _RelationList(BaseModel):
    relations: list[_Relation]


async def add_relation(
    src_id: uuid.UUID,
    tgt_id: uuid.UUID,
    rel_type: str = "RELATES_TO",
) -> None:
    """Upsert a directed edge between two Memory vertices, updating rel_type."""
    src = str(src_id)
    tgt = str(tgt_id)
    rtype = rel_type.upper().replace("'", "\\'")
    if rtype not in _VALID_REL_TYPES:
        rtype = "RELATES_TO"
    # MERGE on the label only (one edge per pair); SET updates the type property.
    await _exec(
        f"SELECT * FROM cypher('{_GRAPH}', $$ "
        f"MATCH (a:Memory {{id: '{src}'}}), (b:Memory {{id: '{tgt}'}}) "
        f"MERGE (a)-[r:RELATES_TO]->(b) "
        f"SET r.rel_type = '{rtype}' "
        f"RETURN r "
        f"$$) AS (r agtype)"
    )


async def extract_relations(
    new_id: uuid.UUID,
    new_text: str,
    candidates: list[tuple[uuid.UUID, str]],
    cfg: dict[str, str],
) -> None:
    """Use PydanticAI to classify relations from new memory to candidates, then save edges.

    candidates: list of (memory_id, descriptive_text) tuples.
    Falls back to generic RELATES_TO edges when extraction_base_url is unset.
    """
    if not candidates or _maker is None:
        return

    from memory_orchestrator_server.config import get_settings
    settings = get_settings()
    base_url = cfg.get("extraction_base_url") or settings.extraction_base_url or None
    model_name = cfg.get("extraction_model") or settings.extraction_model
    api_key = cfg.get("extraction_api_key") or settings.extraction_api_key or "local"

    if not base_url:
        for cid, _ in candidates:
            await add_relation(new_id, cid)
        return

    existing_lines = "\n".join(
        f"ID={cid} | {desc[:200]}" for cid, desc in candidates
    )
    user_prompt = (
        f"NEW MEMORY:\n{new_text[:500]}\n\n"
        f"EXISTING MEMORIES:\n{existing_lines}"
    )

    try:
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(base_url=base_url, api_key=api_key)
        agent: Agent[None, _RelationList] = Agent(
            model=OpenAIChatModel(model_name, provider=provider),
            output_type=_RelationList,
            system_prompt=_RELATION_SYSTEM_PROMPT,
        )
        result = await agent.run(user_prompt)
        relations = result.output.relations
    except Exception:
        logger.debug("graph.extract_relations LLM failed", exc_info=True)
        for cid, _ in candidates:
            await add_relation(new_id, cid)
        return

    candidate_map = {str(cid): cid for cid, _ in candidates}
    seen: set[uuid.UUID] = set()
    for rel in relations:
        tgt_str = rel.tgt
        if tgt_str not in candidate_map:
            continue
        tgt_id = candidate_map[tgt_str]
        seen.add(tgt_id)
        await add_relation(new_id, tgt_id, rel.type)

    # Candidates not mentioned by LLM get a generic RELATES_TO
    for cid, _ in candidates:
        if cid not in seen:
            await add_relation(new_id, cid)


async def expand_ids(
    seed_ids: Sequence[uuid.UUID],
    hop_depth: int = 1,
) -> set[uuid.UUID]:
    """Return IDs of Memory vertices reachable within hop_depth steps from seeds."""
    if not seed_ids or _maker is None:
        return set()
    seeds_str = ", ".join(f"'{sid}'" for sid in seed_ids)
    seed_set = {str(sid) for sid in seed_ids}
    hop = max(1, min(hop_depth, 5))
    rows = await _exec(
        f"SELECT nid::text FROM cypher('{_GRAPH}', $$ "
        f"MATCH (s:Memory)-[*1..{hop}]-(n:Memory) "
        f"WHERE s.id IN [{seeds_str}] "
        f"RETURN DISTINCT n.id "
        f"$$) AS (nid agtype)"
    )
    result: set[uuid.UUID] = set()
    for row in rows:
        raw = str(row[0])
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        if raw in seed_set:
            continue
        try:
            result.add(uuid.UUID(raw))
        except ValueError:
            pass
    return result
