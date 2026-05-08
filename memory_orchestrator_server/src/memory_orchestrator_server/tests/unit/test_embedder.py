from unittest.mock import MagicMock, patch
import pytest


def _make_fake_model(dim: int = 1024):
    import numpy as np
    model = MagicMock()
    def fake_encode(texts, batch_size=1, **kw):
        return {"dense_vecs": np.zeros((len(texts), dim), dtype=float)}
    model.encode.side_effect = fake_encode
    return model


def test_embed_sync_returns_1024_dim():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model()):
        from memory_orchestrator_server.embedder import _embed_sync
        result = _embed_sync("hello world")
    assert len(result) == 1024
    assert isinstance(result[0], float)


def test_embed_batch_returns_list_of_vectors():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model()):
        from memory_orchestrator_server.embedder import _embed_batch_sync
        result = _embed_batch_sync(["hello", "world"])
    assert len(result) == 2
    assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_embed_one_is_async():
    with patch("memory_orchestrator_server.embedder._model", return_value=_make_fake_model()):
        from memory_orchestrator_server import embedder
        result = await embedder.embed_one("test")
    assert len(result) == 1024
