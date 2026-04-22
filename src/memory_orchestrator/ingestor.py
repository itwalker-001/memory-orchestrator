from __future__ import annotations
import json
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
