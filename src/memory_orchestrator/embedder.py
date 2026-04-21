from __future__ import annotations
import asyncio
from functools import lru_cache
from fastembed import TextEmbedding

from memory_orchestrator.config import get_settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=get_settings().embed_model)


async def embed_one(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_sync, text)


def _embed_sync(text: str) -> list[float]:
    vectors = list(_model().embed([text]))
    return vectors[0].tolist()


async def embed_batch(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_batch_sync, texts)


def _embed_batch_sync(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _model().embed(texts)]


def ensure_loaded() -> None:
    """启动时调用,强制首次加载模型,暴露加载失败。"""
    _model()
    _embed_sync("probe")
