from __future__ import annotations
import asyncio
from functools import lru_cache


@lru_cache(maxsize=1)
def _model():
    from FlagEmbedding import BGEM3FlagModel
    from memory_orchestrator_server.config import get_settings
    return BGEM3FlagModel(get_settings().embed_model, use_fp16=True)


async def embed_one(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_sync, text)


def _embed_sync(text: str) -> list[float]:
    vecs = _model().encode([text], batch_size=1)["dense_vecs"]
    return vecs[0].tolist()


async def embed_batch(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_batch_sync, texts)


def _embed_batch_sync(texts: list[str]) -> list[list[float]]:
    vecs = _model().encode(texts, batch_size=32)["dense_vecs"]
    return [v.tolist() for v in vecs]


def ensure_loaded() -> None:
    _model()
    _embed_sync("probe")
