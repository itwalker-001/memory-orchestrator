import math
from datetime import datetime, timedelta, timezone
from memory_orchestrator_server.scoring import hybrid_score, recency_decay, truncate_by_budget


def test_recency_decay_now_is_one():
    assert abs(recency_decay(datetime.now(timezone.utc)) - 1.0) < 1e-6


def test_recency_decay_60_days():
    t = datetime.now(timezone.utc) - timedelta(days=60)
    assert abs(recency_decay(t) - math.exp(-1)) < 1e-3


def test_hybrid_score_weights():
    s = hybrid_score(
        cosine_sim=0.8,
        importance=5,
        updated_at=datetime.now(timezone.utc),
    )
    expected = 0.6 * 0.8 + 0.3 * 1.0 + 0.1 * 1.0
    assert abs(s - expected) < 1e-6


def test_truncate_respects_budget():
    items = [
        {"name": "a", "importance": 5, "tokens": 400, "updated_at": datetime.now(timezone.utc)},
        {"name": "b", "importance": 3, "tokens": 400, "updated_at": datetime.now(timezone.utc)},
        {"name": "c", "importance": 4, "tokens": 400, "updated_at": datetime.now(timezone.utc)},
    ]
    kept = truncate_by_budget(items, budget=900)
    names = [i["name"] for i in kept]
    assert names == ["a", "c"]
