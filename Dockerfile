FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch — avoids ~2 GB CUDA wheels
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy both packages; mcp first so server's local dependency is already satisfied
COPY memory_orchestrator_mcp/ ./memory_orchestrator_mcp/
COPY memory_orchestrator_server/ ./memory_orchestrator_server/

RUN pip install --no-cache-dir ./memory_orchestrator_mcp \
 && pip install --no-cache-dir ./memory_orchestrator_server

# Models are mounted at runtime (~3.5 GB — not baked into image).
# Download on the host first:  cd memory_orchestrator_server && uv run python download_models.py
ENV MO_EMBED_MODEL=/models/BAAI/bge-m3
ENV MO_RERANK_MODEL=/models/BAAI/bge-reranker-v2-m3
ENV MO_HTTP_PORT=8765
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1

EXPOSE 8765

CMD ["mo-server", "serve-http"]
