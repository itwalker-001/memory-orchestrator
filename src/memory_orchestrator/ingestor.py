from __future__ import annotations
import json
import re
from pathlib import Path


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
        f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
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
