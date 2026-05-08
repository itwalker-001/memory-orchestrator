from __future__ import annotations
from functools import lru_cache


@lru_cache(maxsize=1)
def _reranker():
    from FlagEmbedding import FlagReranker
    from memory_orchestrator_server.config import get_settings
    return FlagReranker(get_settings().rerank_model, use_fp16=True)


def rerank_scores(query: str, texts: list[str]) -> list[float]:
    """Score (query, text) pairs. Returns scores in same order as texts."""
    if not texts:
        return []
    pairs = [(query, t) for t in texts]
    scores = _reranker().compute_score(pairs, normalize=True)
    if isinstance(scores, (int, float)):
        return [float(scores)]
    return [float(s) for s in scores]


def ensure_loaded() -> None:
    _reranker()
