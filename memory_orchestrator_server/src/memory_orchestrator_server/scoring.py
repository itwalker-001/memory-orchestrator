import math
from datetime import datetime
from typing import TypedDict

from memory_orchestrator_server.time_utils import to_utc, utc_now


class ScoredItem(TypedDict):
    name: str
    importance: int
    tokens: int
    updated_at: datetime


def recency_decay(updated_at: datetime, half_life_days: float = 60.0) -> float:
    now = utc_now()
    updated_at = to_utc(updated_at)
    age = (now - updated_at).total_seconds() / 86400.0
    return math.exp(-age / half_life_days)


def hybrid_score(
    cosine_sim: float,
    importance: int,
    updated_at: datetime,
    *,
    cosine_weight: float = 0.6,
    importance_weight: float = 0.3,
    recency_weight: float = 0.1,
    half_life_days: float = 60.0,
    type_boost: float = 1.0,
) -> float:
    importance_norm = (importance - 1) / 4.0
    base = (
        cosine_weight * cosine_sim
        + importance_weight * importance_norm
        + recency_weight * recency_decay(updated_at, half_life_days)
    )
    return base * type_boost


def truncate_by_budget(items: list[dict], budget: int) -> list[dict]:
    sorted_items = sorted(
        items,
        key=lambda i: (-i["importance"], -recency_decay(i["updated_at"])),
    )
    kept = []
    used = 0
    for item in sorted_items:
        if used + item["tokens"] <= budget:
            kept.append(item)
            used += item["tokens"]
    return kept
