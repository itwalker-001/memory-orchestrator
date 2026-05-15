import pytest
import torch
from unittest.mock import MagicMock, patch


def _make_fake_model(batch: int = 1):
    model = MagicMock()
    model.parameters.side_effect = lambda: iter([torch.nn.Parameter(torch.zeros(1))])
    output = MagicMock()
    output.last_hidden_state = torch.zeros(batch, 5, 1024)
    model.return_value = output
    return model


def _make_fake_tokenizer(batch: int = 1):
    tok = MagicMock()
    tok.side_effect = lambda *a, **kw: {
        "input_ids": torch.zeros(batch, 5, dtype=torch.long),
        "attention_mask": torch.ones(batch, 5, dtype=torch.long),
    }
    return tok


def test_embed_sync_returns_1024_dim():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model(1)), \
         patch("memory_orchestrator_server.embedder._tokenizer", return_value=_make_fake_tokenizer(1)):
        from memory_orchestrator_server.embedder import _embed_sync
        result = _embed_sync(["hello world"])
    assert len(result) == 1
    assert len(result[0]) == 1024
    assert isinstance(result[0][0], float)


def test_embed_batch_returns_list_of_vectors():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model(2)), \
         patch("memory_orchestrator_server.embedder._tokenizer", return_value=_make_fake_tokenizer(2)):
        from memory_orchestrator_server.embedder import _embed_sync
        result = _embed_sync(["hello", "world"])
    assert len(result) == 2
    assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_embed_one_is_async():
    with patch("memory_orchestrator_server.embedder._embed_sync", return_value=[[0.1] * 1024]):
        from memory_orchestrator_server import embedder
        result = await embedder.embed_one("test")
    assert len(result) == 1024
