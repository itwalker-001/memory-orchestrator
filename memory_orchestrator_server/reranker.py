from __future__ import annotations
from functools import lru_cache


@lru_cache(maxsize=1)
def _tokenizer():
    from transformers import AutoTokenizer
    from memory_orchestrator_server.config import get_settings
    return AutoTokenizer.from_pretrained(get_settings().rerank_model, local_files_only=True)


@lru_cache(maxsize=1)
def _model():
    import torch
    from transformers import AutoModelForSequenceClassification
    from memory_orchestrator_server.config import get_settings
    m = AutoModelForSequenceClassification.from_pretrained(get_settings().rerank_model, local_files_only=True)
    m.eval()
    if torch.cuda.is_available():
        m = m.half().cuda()
    return m


def rerank_scores(query: str, texts: list[str]) -> list[float]:
    if not texts:
        return []
    import torch
    tok = _tokenizer()
    model = _model()
    pairs = [[query, t] for t in texts]
    inputs = tok(pairs, padding=True, truncation=True, max_length=512, return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits.view(-1).float()
    return torch.sigmoid(logits).cpu().tolist()


def ensure_loaded() -> None:
    _tokenizer()
    _model()
