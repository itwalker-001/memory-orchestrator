from unittest.mock import MagicMock, patch


def _make_fake_reranker(scores):
    r = MagicMock()
    r.compute_score.return_value = scores
    return r


def test_rerank_scores_returns_scores_per_text():
    fake = _make_fake_reranker([0.9, 0.3, 0.7])
    with patch("memory_orchestrator_server.reranker._reranker", return_value=fake):
        from memory_orchestrator_server.reranker import rerank_scores
        scores = rerank_scores("my query", ["text a", "text b", "text c"])
    assert len(scores) == 3
    assert scores[0] == 0.9
    assert scores[1] == 0.3
    assert scores[2] == 0.7


def test_rerank_scores_handles_single_text():
    fake = _make_fake_reranker(0.85)
    with patch("memory_orchestrator_server.reranker._reranker", return_value=fake):
        from memory_orchestrator_server.reranker import rerank_scores
        scores = rerank_scores("query", ["only text"])
    assert scores == [0.85]


def test_ensure_loaded_calls_reranker():
    fake = _make_fake_reranker([])
    with patch("memory_orchestrator_server.reranker._reranker", return_value=fake):
        from memory_orchestrator_server.reranker import ensure_loaded
        ensure_loaded()
