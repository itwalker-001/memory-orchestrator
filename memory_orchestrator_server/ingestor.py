from __future__ import annotations
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.embedder import embed_one
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Session as SessionRow
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.time_utils import utc_now


def read_transcript_incremental(path: str, offset: int) -> tuple[list[dict], int]:
    p = Path(path)
    if not p.exists():
        return [], offset
    lines: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f):
            if i < offset:
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                lines.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    with p.open("rb") as f:
        total = sum(1 for _ in f)
    return lines, total


_VALID_TYPES = {"user", "feedback", "project", "reference"}

EXTRACTION_SYSTEM_PROMPT = """You extract durable memories from a conversation transcript.

Return a JSON array. Each item is an object with fields:
- type: one of "user", "feedback", "project", "reference"
- name: short title (max 60 chars)
- description: one-line hook explaining relevance
- content: the memory body in markdown
- why: required for "feedback" and "project" - the reason/motivation
- how_to_apply: required for "feedback" and "project" - when/how to use it
- importance: integer 1-5, default 3

Rules:
- "user" = facts about the user (role, knowledge, preferences). Scope: global.
- "feedback" = corrections or validated approaches from user. Scope: project unless universal.
- "project" = ongoing work, deadlines, stakeholders specific to this project.
- "reference" = pointers to external systems (dashboards, trackers, URLs).

Only extract memories that will still be useful in a future conversation.
Skip ephemeral task details, code, debug recipes, and anything already in the codebase.
If nothing qualifies, return an empty array.

Output ONLY the JSON array. No prose, no code fence."""


def build_extraction_prompt(transcript_chunk: str, project_id: str) -> str:
    return (
        f"Project: {project_id}\n\n"
        f"Transcript chunk:\n<transcript>\n{transcript_chunk}\n</transcript>\n\n"
        f"Extract memories now."
    )


def parse_extraction_response(raw: str) -> list[dict]:
    text = raw.strip()
    m = re.match(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    validated: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t not in _VALID_TYPES:
            continue
        if not all(item.get(k) for k in ("name", "description", "content")):
            continue
        if t in ("feedback", "project") and not all(item.get(k) for k in ("why", "how_to_apply")):
            continue
        validated.append(item)
    return validated


@dataclass
class IngestResult:
    extracted: int
    saved: int
    skipped: int


async def ingest_session(
    *,
    db: AsyncSession,
    session_id: str,
    project_id: uuid.UUID,
    transcript_path: str,
    source_client: str = "claude",
) -> IngestResult:
    _env = get_settings()
    repo = MemoryRepository(db)
    _cfg = await repo.get_settings()
    extraction_base_url = _cfg.get("extraction_base_url") or _env.extraction_base_url or None
    extraction_model = _cfg.get("extraction_model") or _env.extraction_model
    extraction_api_key = _cfg.get("extraction_api_key") or _env.extraction_api_key or "local"

    row = await db.get(SessionRow, session_id)
    if row is None:
        row = SessionRow(session_id=session_id, project_id=project_id, status="pending")
        db.add(row)
        await db.flush()

    lines, new_offset = read_transcript_incremental(transcript_path, row.last_offset)
    if not lines:
        row.status = "done"
        row.last_ingested_at = utc_now()
        await db.commit()
        return IngestResult(extracted=0, saved=0, skipped=0)

    chunk = _render_chunk(lines)

    try:
        from openai import AsyncOpenAI
        oc = AsyncOpenAI(
            base_url=extraction_base_url,
            api_key=extraction_api_key,
        )
        resp = await oc.chat.completions.create(
            model=extraction_model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_extraction_prompt(chunk, str(project_id))},
            ],
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)[:500]
        await db.commit()
        raise

    candidates = parse_extraction_response(raw)

    saved = 0
    skipped = 0
    try:
        for cand in candidates:
            embedding = await embed_one(cand["content"])
            cand_pid = GLOBAL_PROJECT_ID if cand["type"] == "user" else project_id
            dups = await repo.find_duplicates(type=cand["type"], project_id=cand_pid, embedding=embedding)
            if dups:
                skipped += 1
                continue
            await repo.save(
                type=cand["type"],
                name=cand["name"],
                description=cand["description"],
                content=cand["content"],
                why=cand.get("why"),
                how_to_apply=cand.get("how_to_apply"),
                importance=int(cand.get("importance", 3)),
                project_id=cand_pid,
                source="auto_extracted",
                source_client=source_client,
                embedding=embedding,
            )
            saved += 1
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)[:500]
        await db.commit()
        raise

    row.last_offset = new_offset
    row.last_ingested_at = utc_now()
    row.status = "done"
    row.last_error = None
    await db.commit()

    return IngestResult(extracted=len(candidates), saved=saved, skipped=skipped)


def _render_chunk(lines: list[dict]) -> str:
    out: list[str] = []
    for obj in lines:
        role = obj.get("role") or obj.get("type") or "unknown"
        content = obj.get("content") or obj.get("text") or ""
        if isinstance(content, list):
            content = "\n".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        out.append(f"[{role}] {content}")
    return "\n\n".join(out)
