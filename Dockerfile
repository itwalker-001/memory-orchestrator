FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY frontend/dist/ frontend/dist/

RUN pip install --no-cache-dir -e .

ENV HF_HUB_OFFLINE=1
ENV MO_HTTP_PORT=8765

# pre-download embedding model at build time
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-zh-v1.5')" || true

EXPOSE 8765

CMD ["mo", "serve-http"]
