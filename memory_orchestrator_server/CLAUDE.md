# CLAUDE.md — memory_orchestrator_server

Developer guidance for the server package. Run all commands from `memory_orchestrator_server/`.

## Commands

```bash
uv sync                                          # Install dependencies
uv run alembic upgrade head                      # Apply DB migrations
uv run python download_models.py                 # Download BGE-M3 + reranker via ModelScope

uv run mo-server serve-http                      # Start HTTP server on port 8765
uv run mo-server migrate-embeddings              # Re-embed all memories after model change

uv run mo-server token create --kind ui_admin --name admin
uv run mo-server token list
uv run mo-server token revoke <token-id>
# project_token: create via UI (http://localhost:8765/ui → Admin → Tokens) or POST /api/register

# Wire a project (run from the project directory, not from here):
#   mo-mcp setup --base-url http://127.0.0.1:8765 --project-token <token>
#   mo-mcp doctor

uv run pytest                                    # All tests
uv run pytest tests/unit/                        # No DB required
uv run pytest tests/integration/                 # Needs Postgres on port 5433

cd frontend && npm run build                     # Rebuild SPA
```

## Architecture

```
HTTP request
    │
    ├── /healthz, /context, /hooks/ingest  →  routers/hooks.py
    ├── /mcp/tools/*, /mcp/resources/*     →  routers/mcp.py  →  mcp_core.py
    └── /ui/*, /api/*                      →  routers/ui.py
                                                     │
                                               repository.py
                                                     │
                                       PostgreSQL + pgvector + Apache AGE
```

## Key modules

| File | Role |
|---|---|
| `cli.py` | `mo-server` entry point; `serve-http`, `doctor`, `token`, `migrate-embeddings` |
| `http_app.py` | FastAPI app factory; mounts routers; SPA static fallback |
| `config.py` | Pydantic Settings; all `MO_*` env vars |
| `models.py` | SQLAlchemy ORM: `Project`, `Memory`, `Session`, `SystemSetting`, `ApiToken`, `ProjectSkeletonNode`, `SkeletonNodeMemory` |
| `repository.py` | All DB operations; settings cache (60 s TTL) |
| `auth_tokens.py` | Token validation; FastAPI dependency; env-var fallback |
| `ingestor.py` | Parse transcript JSON lines → LLM extraction → structured memories |
| `embedder.py` | BGE-M3 via `transformers.AutoModel`; CLS token + L2 norm; lazy-loaded |
| `reranker.py` | BGE-reranker-v2-m3 cross-encoder; sigmoid scores |
| `scoring.py` | `hybrid_score()` = cosine + importance + recency decay; `truncate_by_budget()` |
| `mcp_core.py` | MCP tool implementations: search, save, list, delete, promote, ingest |
| `mcp_contract.py` | Tool/resource schema definitions (MCP protocol contracts) |
| `graph.py` | Apache AGE vertex/edge ops + LLM relation extraction |
| `project_id.py` | Project slug/UUID resolution from cwd |
| `db_check.py` | DB connectivity preflight; auto-create DB if missing |

## Data model

- `projects` — slug → UUID.
- `memories` — `type` ∈ {user, feedback, project, reference}; `embedding vector(1024)`; `superseded_by` for soft-delete chain.
- `system_settings` — key-value; cached 60 s; editable at runtime without restart.
- `sessions` — ingestion progress per session (`last_offset`, `status` ∈ pending/done/failed).
- `api_tokens` — SHA256-hashed bearer tokens; `kind` ∈ {ui_admin, project_token}; `project_id` FK required for project_token; `enabled` flag.
- `project_skeleton_nodes` — knowledge tree nodes; `parent_id` self-FK for hierarchy; `tags` ARRAY; `sort_order`; `is_builtin` flag for default nodes.
- `skeleton_node_memories` — junction table linking nodes to memories (many-to-many).

## Authentication

- `/ui/*` and `/api/*` require `ui_admin` token (or `MO_UI_TOKEN` env var).
- `/mcp/*` requires `project_token` bound to a project (or `MO_MCP_TOKEN` env var).
- No token rows → auth disabled (open access).
- `project_token` is created via the UI (Admin → Tokens) or `POST /api/register` (localhost-only).

## Runtime config (system_settings)

Editable via UI → Settings or direct DB. No restart needed.

| Key | Purpose |
|---|---|
| `hook_budget_tokens` | Max tokens injected per UserPromptSubmit |
| `hook_cooldown_sec` | Min seconds between Stop hook ingestions |
| `hook_min_turns` | Min user turns before Stop hook fires |
| `search_top_k` | Candidate count for vector search |
| `dup_threshold` | Cosine threshold for duplicate detection |
| `extraction_base_url` | LLM extraction endpoint (OpenAI-compatible) |
| `extraction_model` | Model used for extraction (default: `gpt-4o-mini`) |
| `embed_model` | HuggingFace embedding model path |
| `embed_dim` | Embedding vector dimension (default: 1024) |
| `rerank_enabled` | Enable BGE reranker after vector search |
| `rerank_model` | HuggingFace reranker model path |
| `graph_enabled` | Enable Apache AGE graph reasoning |
| `graph_hop_depth` | Max hops in graph traversal |

## Tests

```
tests/
  unit/
    test_client_adapters.py       Codex installer (no DB)
    test_client_rules.py          Config rule parsing
    test_container_config.py      Env var loading
    test_embedder.py              Embedding generation
    test_ingestor.py              Transcript parsing + extraction
    test_ingestor_prompts.py      LLM prompt templates
    test_memory_links_removed.py  Supersession chain
    test_package_boundaries.py    Import isolation enforcement
    test_reranker.py              Reranker scores
    test_scoring.py               Hybrid scoring
    test_time_utils.py            UTC helpers
    test_ui_tokens_schema.py      Token validation schemas
  integration/
    test_http_app.py              FastAPI lifecycle + health
    test_mcp_http.py              MCP HTTP bridge endpoints
    test_mcp_tools.py             MCP tool handlers (search/save/etc.)
    test_repository.py            Repository queries + transactions
    conftest.py                   Async fixtures; test DB setup
```

Override test DB with `MO_TEST_DB_DSN` (default port 5433, DB `memory_orchestrator_test`).

## Database

PostgreSQL 16 + pgvector + Apache AGE on port 5433 (5432 in local dev without Docker override).

```bash
# Local dev — create DB and enable extensions manually, then:
uv run alembic upgrade head

# New migration:
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## Frontend

Built with Vite; output lands in `frontend/dist/`, which is bundled into the package via
`pyproject.toml` `package-data`. The FastAPI app serves `frontend/dist/` as a SPA fallback.

```bash
cd frontend
npm install
npm run build   # production build → dist/
npm run dev     # dev server with HMR (separate from FastAPI)
```

### i18n (multi-language) — required for all user-facing text

The SPA ships English + Chinese. **Never hardcode user-facing strings** (toasts,
labels, placeholders, button text, error messages). Always go through `t()`.

- `src/useLocale.js` — `const { t } = useLocale()`. `t('English key', { var })` looks
  up the current locale and interpolates `{var}` placeholders. Default locale is `en`.
- `src/locales/en.json` and `src/locales/zh.json` — the English string itself is the
  key. Add the **same key to both files** whenever you introduce new copy; a missing
  key silently falls back to the raw key string.
- Non-component modules (e.g. `src/api.js`) can import `useLocale` at module scope —
  `t` reads the live `lang` ref on each call, so it stays reactive to language switches.
- After adding copy, verify both languages render (toggle via the EN/中 header button).

## Docker

Docker files live in this directory (`Dockerfile`, `Dockerfile.base`); compose and DB image
live at the repository root. Run `./scripts/build.sh` from the repo root — not from here.

See root `CLAUDE.md` or `README.md` for full Docker workflow.
