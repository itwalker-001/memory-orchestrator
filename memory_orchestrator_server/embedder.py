from __future__ import annotations
import asyncio
from functools import lru_cache


@lru_cache(maxsize=1)
def _tokenizer():
    from transformers import AutoTokenizer
    from memory_orchestrator_server.config import get_settings
    return AutoTokenizer.from_pretrained(get_settings().embed_model, local_files_only=True)


@lru_cache(maxsize=1)
def _model():
    import torch
    from transformers import AutoModel
    from memory_orchestrator_server.config import get_settings
    m = AutoModel.from_pretrained(get_settings().embed_model, local_files_only=True)
    m.eval()
    if torch.cuda.is_available():
        m = m.half().cuda()
    return m


def _embed_sync(texts: list[str]) -> list[list[float]]:
    import torch
    tok = _tokenizer()
    model = _model()
    inputs = tok(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model(**inputs)
    # CLS token + L2 norm — standard BGE dense retrieval
    vecs = out.last_hidden_state[:, 0]
    vecs = torch.nn.functional.normalize(vecs, p=2, dim=1)
    return vecs.cpu().float().numpy().tolist()


async def embed_one(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    return (await loop.run_in_executor(None, _embed_sync, [text]))[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_sync, texts)


def ensure_loaded() -> None:
    _tokenizer()
    _model()
    _embed_sync(["probe"])
