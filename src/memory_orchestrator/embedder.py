from __future__ import annotations
import asyncio
import os
from functools import lru_cache
from pathlib import Path

from fastembed import TextEmbedding

from memory_orchestrator.config import get_settings


def _cache_dir() -> Path:
    cache_dir = Path(get_settings().embed_cache_dir).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = Path.cwd() / cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("FASTEMBED_CACHE_PATH", str(cache_dir))
    return cache_dir


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    settings = get_settings()
    os.environ["HF_HUB_OFFLINE"] = "1"
    return TextEmbedding(
        model_name=settings.embed_model,
        cache_dir=str(_cache_dir()),
        local_files_only=True,
    )


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
