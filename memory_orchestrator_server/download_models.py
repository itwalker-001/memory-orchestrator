"""
Download BAAI/bge-m3 and BAAI/bge-reranker-v2-m3 from ModelScope
into memory_orchestrator_server/models/
"""
from pathlib import Path
from modelscope import snapshot_download

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

MODELS = [
    "BAAI/bge-m3",
    "BAAI/bge-reranker-v2-m3",
]

for model_id in MODELS:
    dest = MODELS_DIR / model_id.replace("/", "/")
    if dest.exists() and any(dest.iterdir()):
        print(f"[skip] {model_id} already at {dest}")
        continue
    print(f"\n[download] {model_id} → {dest}")
    path = snapshot_download(model_id, cache_dir=str(MODELS_DIR))
    print(f"[done]  {model_id} → {path}")

print("\nAll models ready.")
