from __future__ import annotations
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from memory_orchestrator.config import get_settings
from memory_orchestrator.embedder import embed_one
from memory_orchestrator.models import Session as SessionRow
from memory_orchestrator.repository import MemoryRepository


def read_transcript_incremental(path: str, offset: int) -> tuple[list[dict], int]:
    """Read new lines from a JSONL transcript starting at offset, return (parsed objects, new offset)."""
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
    project_id: str,
    transcript_path: str,
) -> IngestResult:
    settings = get_settings()

    row = await db.get(SessionRow, session_id)
    if row is None:
        row = SessionRow(session_id=session_id, project_id=project_id, status="pending")
        db.add(row)
        await db.flush()

    lines, new_offset = read_transcript_incremental(transcript_path, row.last_offset)
    if not lines:
        row.status = "done"
        row.last_ingested_at = datetime.now(timezone.utc)
        await db.commit()
        return IngestResult(extracted=0, saved=0, skipped=0)

    chunk = _render_chunk(lines)

    client = AsyncAnthropic(
        base_url=settings.anthropic_base_url or None,
        api_key=settings.anthropic_auth_token or None,
    )
    try:
        resp = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=2048,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_extraction_prompt(chunk, project_id)}],
        )
        raw = resp.content[0].text if resp.content else ""
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)[:500]
        await db.commit()
        raise

    candidates = parse_extraction_response(raw)

    repo = MemoryRepository(db)
    saved = 0
    skipped = 0
    try:
        for cand in candidates:
            embedding = await embed_one(cand["content"])
            pid = cand.get("project_id") or (project_id if cand["type"] != "user" else "*")
            dups = await repo.find_duplicates(
                type=cand["type"],
                project_id=pid,
                embedding=embedding,
            )
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
                project_id=pid,
                source="auto_extracted",
                embedding=embedding,
            )
            saved += 1
    except Exception as e:
        row.status = "failed"
        row.last_error = str(e)[:500]
        await db.commit()
        raise

    row.last_offset = new_offset
    row.last_ingested_at = datetime.now(timezone.utc)
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
