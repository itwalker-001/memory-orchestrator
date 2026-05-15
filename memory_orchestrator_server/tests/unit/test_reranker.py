import torch
from unittest.mock import MagicMock, patch


def _logit(p: float) -> float:
    import math
    return math.log(p / (1 - p))


def _make_fake_model(probs: list[float]):
    model = MagicMock()
    model.parameters.side_effect = lambda: iter([torch.nn.Parameter(torch.zeros(1))])
    output = MagicMock()
    output.logits = torch.tensor([_logit(p) for p in probs])
    model.return_value = output
    return model


def _make_fake_tokenizer():
    tok = MagicMock()
    tok.side_effect = lambda *a, **kw: {
        "input_ids": torch.zeros(1, 5, dtype=torch.long),
        "attention_mask": torch.ones(1, 5, dtype=torch.long),
    }
    return tok


def test_rerank_scores_returns_scores_per_text():
    probs = [0.9, 0.3, 0.7]
    fake = _make_fake_model(probs)
    with patch("memory_orchestrator_server.reranker._model", return_value=fake), \
         patch("memory_orchestrator_server.reranker._tokenizer", return_value=_make_fake_tokenizer()):
        from memory_orchestrator_server.reranker import rerank_scores
        scores = rerank_scores("my query", ["text a", "text b", "text c"])
    assert len(scores) == 3
    assert abs(scores[0] - 0.9) < 0.01
    assert abs(scores[1] - 0.3) < 0.01
    assert abs(scores[2] - 0.7) < 0.01


def test_rerank_scores_handles_single_text():
    fake = _make_fake_model([0.85])
    with patch("memory_orchestrator_server.reranker._model", return_value=fake), \
         patch("memory_orchestrator_server.reranker._tokenizer", return_value=_make_fake_tokenizer()):
        from memory_orchestrator_server.reranker import rerank_scores
        scores = rerank_scores("query", ["only text"])
    assert len(scores) == 1
    assert abs(scores[0] - 0.85) < 0.01


def test_ensure_loaded_calls_reranker():
    fake = _make_fake_model([0.5])
    with patch("memory_orchestrator_server.reranker._model", return_value=fake), \
         patch("memory_orchestrator_server.reranker._tokenizer", return_value=_make_fake_tokenizer()):
        from memory_orchestrator_server.reranker import ensure_loaded
        ensure_loaded()
