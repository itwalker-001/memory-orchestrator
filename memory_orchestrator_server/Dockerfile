# Build context: memory_orchestrator_server/
#
# App image: frontend assets + project source + entry points.
# Base image is built separately with scripts/build_base.sh.

ARG BASE_IMAGE=memory-orchestrator-server-base:latest

# ── Stage 0: frontend build ───────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

# ── Stage 1: app — project source + entry points ──────────────────────────────
FROM ${BASE_IMAGE}

COPY . /app/memory_orchestrator_server/
COPY --from=frontend-builder /frontend/dist \
  /app/memory_orchestrator_server/frontend/dist/

RUN uv pip install --system --no-cache --no-deps /app/memory_orchestrator_server/ \
 && python -m compileall -q /app/memory_orchestrator_server

ENV MO_HTTP_PORT=8765
ENV MO_HTTP_HOST=0.0.0.0
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1
EXPOSE 8765
CMD ["mo-server", "serve-http"]
