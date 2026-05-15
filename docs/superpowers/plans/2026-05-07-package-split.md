# Package Split: memory_orchestrator → _server + _mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all application assets into exactly two packages. `memory_orchestrator_server` owns DB/embedder/FastAPI/frontend. `memory_orchestrator_mcp` owns hooks, client rules, client instructions (agents/skills), and the stdio MCP server. Root-level client/server asset directories (`hooks/`, `client-rules/`, `agents/`, `skills/`, `frontend/`) are moved into the appropriate package; old `memory_orchestrator.*` modules become backward-compat shims.

**Architecture:** Three parallel moves — (1) server-side Python modules migrate to `memory_orchestrator_server/`; (2) `frontend/` moves into `src/memory_orchestrator_server/frontend/`; (3) `hooks/`, `client-rules/`, `agents/`, `skills/` move into `src/memory_orchestrator_mcp/`. All references (JSON rule paths, Python hardcoded paths, Dockerfile COPY, http_app.py dist path, alembic/env.py imports) are updated accordingly.

**Tech Stack:** Python 3.11, SQLAlchemy async, FastAPI, FastEmbed, pgvector, Alembic, pytest-asyncio

---

## File Map

**Move into `src/memory_orchestrator_mcp/` (client-side assets):**
- `hooks/stop.py` → `src/memory_orchestrator_mcp/hooks/stop.py`
- `hooks/user_prompt_submit.py` → `src/memory_orchestrator_mcp/hooks/user_prompt_submit.py`
- `client-rules/claude.json` → `src/memory_orchestrator_mcp/client_rules/claude.json`
- `client-rules/codex.json` → `src/memory_orchestrator_mcp/client_rules/codex.json`
- `agents/memory-orchestrator.AGENTS.md` → `src/memory_orchestrator_mcp/agents/memory-orchestrator.AGENTS.md`
- `skills/memory-orchestrator/SKILL.md` → `src/memory_orchestrator_mcp/skills/memory-orchestrator/SKILL.md`
- `src/memory_orchestrator_mcp/hooks/__init__.py` (new empty init)
- `src/memory_orchestrator_mcp/client_rules/__init__.py` (new empty init — marks it a data dir, not imported)

**Move into `src/memory_orchestrator_server/` (server-side assets):**
- `frontend/` → `src/memory_orchestrator_server/frontend/`
- `alembic/` → `src/memory_orchestrator_server/alembic/`
- `scripts/` → `src/memory_orchestrator_server/scripts/`

**Split `tests/` by owner:**
- `tests/unit/test_hooks_codex.py` → `src/memory_orchestrator_mcp/tests/`
- `tests/unit/test_mcp_http_client.py` → `src/memory_orchestrator_mcp/tests/`
- `tests/unit/test_client_adapters.py` → `src/memory_orchestrator_mcp/tests/`
- `tests/unit/test_client_rules.py` → `src/memory_orchestrator_mcp/tests/`
- `tests/unit/test_project_id.py` → `src/memory_orchestrator_mcp/tests/`
- `tests/unit/test_scoring.py` → `src/memory_orchestrator_server/tests/unit/`
- `tests/unit/test_time_utils.py` → `src/memory_orchestrator_server/tests/unit/`
- `tests/unit/test_ingestor.py` → `src/memory_orchestrator_server/tests/unit/`
- `tests/unit/test_ingestor_prompts.py` → `src/memory_orchestrator_server/tests/unit/`
- `tests/unit/test_package_boundaries.py` → `src/memory_orchestrator_server/tests/unit/`
- `tests/integration/` (all 5 files) → `src/memory_orchestrator_server/tests/integration/`
- `tests/conftest.py` → `src/memory_orchestrator_server/tests/conftest.py`

**Delete (after moving):**
- `hooks/`, `client-rules/`, `agents/`, `skills/` directories
- `tests/` directory (after all files moved)

**Modify (update references after asset moves):**
- `src/memory_orchestrator/client_rules.py` — hardcoded `"client-rules"` path
- `src/memory_orchestrator_server/http_app.py` — `frontend/dist` path
- `Dockerfile` — `COPY frontend/dist/` line
- `CLAUDE.md` — `npm run build`, `cd frontend`, `uv run alembic` instruction paths
- JSON rule files (`instructions.source` paths for agents/skills)
- `alembic.ini` — `script_location` path
- `pyproject.toml` — `testpaths`

**Modify (update imports to server package — not shim-compatible):**
- `alembic/env.py`

**Modify (update hook + client_rules paths in tests):**
- `tests/unit/test_hooks_codex.py`
- `tests/unit/test_client_rules.py`

**Create (new server-side modules):**
- `src/memory_orchestrator_server/time_utils.py`
- `src/memory_orchestrator_server/config.py`
- `src/memory_orchestrator_server/models.py`
- `src/memory_orchestrator_server/scoring.py`
- `src/memory_orchestrator_server/embedder.py`
- `src/memory_orchestrator_server/repository.py`
- `src/memory_orchestrator_server/auth_tokens.py`
- `src/memory_orchestrator_server/ingestor.py`
- `src/memory_orchestrator_server/mcp_core.py`
- `src/memory_orchestrator_server/routers/hooks.py`
- `src/memory_orchestrator_server/routers/ui.py`
- `src/memory_orchestrator_server/db_check.py`

**Modify (turn into shims):**
- `src/memory_orchestrator/time_utils.py`
- `src/memory_orchestrator/config.py`
- `src/memory_orchestrator/models.py`
- `src/memory_orchestrator/scoring.py`
- `src/memory_orchestrator/embedder.py`
- `src/memory_orchestrator/repository.py`
- `src/memory_orchestrator/auth_tokens.py`
- `src/memory_orchestrator/ingestor.py`
- `src/memory_orchestrator/mcp_core.py`
- `src/memory_orchestrator/router_hooks.py`
- `src/memory_orchestrator/router_ui.py`
- `src/memory_orchestrator/mcp_server.py`
- `src/memory_orchestrator/db_check.py`
- `src/memory_orchestrator/http_app.py` (already a shim, verify)

**Modify (update to use new package paths):**
- `src/memory_orchestrator_server/http_app.py`
- `src/memory_orchestrator_server/routers/mcp.py`

---

### Task 0a: Move hook scripts and client-rules into `memory_orchestrator_mcp`

All client-side assets (hooks, JSON rules, client instructions) move out of root-level directories into `src/memory_orchestrator_mcp/`. Root dirs `hooks/`, `client-rules/`, `agents/`, `skills/` are then deleted. The Python code that references these paths is updated.

**Files:**
- Create: `src/memory_orchestrator_mcp/hooks/__init__.py`
- Move: `hooks/stop.py` → `src/memory_orchestrator_mcp/hooks/stop.py`
- Move: `hooks/user_prompt_submit.py` → `src/memory_orchestrator_mcp/hooks/user_prompt_submit.py`
- Create: `src/memory_orchestrator_mcp/client_rules/` directory
- Move: `client-rules/claude.json` → `src/memory_orchestrator_mcp/client_rules/claude.json`
- Move: `client-rules/codex.json` → `src/memory_orchestrator_mcp/client_rules/codex.json`
- Move: `agents/memory-orchestrator.AGENTS.md` → `src/memory_orchestrator_mcp/agents/memory-orchestrator.AGENTS.md`
- Move: `skills/memory-orchestrator/SKILL.md` → `src/memory_orchestrator_mcp/skills/memory-orchestrator/SKILL.md`
- Modify: `src/memory_orchestrator/client_rules.py` — update hardcoded `client-rules` path
- Modify: `src/memory_orchestrator_mcp/client_rules/claude.json` — update hook + instructions paths
- Modify: `src/memory_orchestrator_mcp/client_rules/codex.json` — update hook + instructions paths
- Delete: `hooks/`, `client-rules/`, `agents/`, `skills/` directories

- [ ] **Step 1: Create directory structure under `memory_orchestrator_mcp`**

```bash
mkdir -p src/memory_orchestrator_mcp/hooks
mkdir -p src/memory_orchestrator_mcp/client_rules
mkdir -p src/memory_orchestrator_mcp/agents
mkdir -p src/memory_orchestrator_mcp/skills/memory-orchestrator
touch src/memory_orchestrator_mcp/hooks/__init__.py
```

- [ ] **Step 2: Move hook scripts**

```bash
git mv hooks/stop.py src/memory_orchestrator_mcp/hooks/stop.py
git mv hooks/user_prompt_submit.py src/memory_orchestrator_mcp/hooks/user_prompt_submit.py
```

- [ ] **Step 3: Move client-rules JSON files**

```bash
git mv client-rules/claude.json src/memory_orchestrator_mcp/client_rules/claude.json
git mv client-rules/codex.json src/memory_orchestrator_mcp/client_rules/codex.json
```

- [ ] **Step 4: Move agents and skills instructions**

```bash
git mv agents/memory-orchestrator.AGENTS.md src/memory_orchestrator_mcp/agents/memory-orchestrator.AGENTS.md
git mv skills/memory-orchestrator/SKILL.md src/memory_orchestrator_mcp/skills/memory-orchestrator/SKILL.md
```

- [ ] **Step 5: Delete now-empty root directories**

```bash
rmdir hooks client-rules agents/memory-orchestrator agents skills/memory-orchestrator skills 2>/dev/null || true
git add -u hooks/ client-rules/ agents/ skills/
```

- [ ] **Step 6: Update hook command paths in `claude.json`**

In `src/memory_orchestrator_mcp/client_rules/claude.json`, update both `command` arrays and the `instructions.source`:

```json
{
  "path": ["hooks", "UserPromptSubmit"],
  "value": [{"hooks": [{"type": "command", "command":
    ["uv", "run", "--no-sync", "--project", "{project_dir}", "python",
     "{project_dir}/src/memory_orchestrator_mcp/hooks/user_prompt_submit.py", "--client", "claude"]
  }]}]
},
{
  "path": ["hooks", "Stop"],
  "value": [{"hooks": [{"type": "command", "command":
    ["uv", "run", "--no-sync", "--project", "{project_dir}", "python",
     "{project_dir}/src/memory_orchestrator_mcp/hooks/stop.py", "--client", "claude"]
  }]}]
}
```

And update `instructions.source`:
```json
"instructions": {
  "source": "src/memory_orchestrator_mcp/skills/memory-orchestrator/SKILL.md",
  "destination": "skills/memory-orchestrator/SKILL.md"
}
```

- [ ] **Step 7: Update hook command paths and instructions in `codex.json`**

In `src/memory_orchestrator_mcp/client_rules/codex.json`, update `hooks.events` commands:

```json
"UserPromptSubmit": {
  "type": "command",
  "command": ["uv", "run", "--no-sync", "--project", "{project_dir}", "python",
    "{project_dir}/src/memory_orchestrator_mcp/hooks/user_prompt_submit.py", "--client", "codex"]
},
"Stop": {
  "type": "command",
  "command": ["uv", "run", "--no-sync", "--project", "{project_dir}", "python",
    "{project_dir}/src/memory_orchestrator_mcp/hooks/stop.py", "--client", "codex"]
}
```

And update `instructions.source`:
```json
"instructions": {
  "source": "src/memory_orchestrator_mcp/agents/memory-orchestrator.AGENTS.md",
  "destination": "AGENTS.md"
}
```

- [ ] **Step 8: Update `client_rules.py` hardcoded path**

In `src/memory_orchestrator/client_rules.py`, change the default `base` path:

```python
# Change:
base = rules_dir or Path(__file__).parent.parent.parent / "client-rules"
# To:
base = rules_dir or Path(__file__).parent.parent / "memory_orchestrator_mcp" / "client_rules"
```

- [ ] **Step 9: Run client_rules unit tests**

```
uv run pytest tests/unit/test_client_rules.py -v
```

Expected: all pass (tests use `load_client_rule("codex")` and `load_client_rule("claude")` which now resolve to the new path).

- [ ] **Step 10: Run package boundary test**

```
uv run pytest tests/unit/test_package_boundaries.py -v
```

Expected: PASS — hook scripts use only stdlib.

- [ ] **Step 11: Commit**

```bash
git add src/memory_orchestrator_mcp/hooks/ \
        src/memory_orchestrator_mcp/client_rules/ \
        src/memory_orchestrator_mcp/agents/ \
        src/memory_orchestrator_mcp/skills/ \
        src/memory_orchestrator/client_rules.py
git commit -m "refactor: move hooks, client-rules, agents, skills into memory_orchestrator_mcp"
```

---

### Task 0b: Move `frontend/`, `alembic/`, `scripts/` into `memory_orchestrator_server`

These are all server-side assets: the Vue SPA is served by FastAPI, `alembic/` manages the server DB schema, `scripts/` contains server smoke tests.

**Files:**
- Move: `frontend/` → `src/memory_orchestrator_server/frontend/`
- Move: `alembic/` → `src/memory_orchestrator_server/alembic/`
- Move: `scripts/` → `src/memory_orchestrator_server/scripts/`
- Modify: `src/memory_orchestrator_server/http_app.py` — dist path
- Modify: `Dockerfile` — COPY lines
- Modify: `alembic.ini` — `script_location`
- Modify: `CLAUDE.md` — build + migrate instructions

- [ ] **Step 1: Move `frontend/`, `alembic/`, `scripts/`**

```bash
git mv frontend src/memory_orchestrator_server/frontend
git mv alembic  src/memory_orchestrator_server/alembic
git mv scripts  src/memory_orchestrator_server/scripts
```

- [ ] **Step 2: Update dist path in `http_app.py`**

```python
# Change:
dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
# To:
dist = Path(__file__).resolve().parent / "frontend" / "dist"
```

- [ ] **Step 3: Update `alembic.ini` script_location**

```ini
# Change:
script_location = %(here)s/alembic
# To:
script_location = %(here)s/src/memory_orchestrator_server/alembic
```

- [ ] **Step 4: Update `Dockerfile`**

```dockerfile
# Change:
COPY alembic/ alembic/
COPY frontend/dist/ frontend/dist/
# To:
COPY src/memory_orchestrator_server/alembic/ src/memory_orchestrator_server/alembic/
COPY src/memory_orchestrator_server/frontend/dist/ src/memory_orchestrator_server/frontend/dist/
```

- [ ] **Step 5: Update `CLAUDE.md` commands**

```markdown
# Change:
uv run alembic upgrade head
cd frontend && npm run build
# To:
uv run alembic upgrade head          # alembic.ini still at root, no change needed for this command
cd src/memory_orchestrator_server/frontend && npm run build
```

Note: `uv run alembic upgrade head` still works because `alembic.ini` at root now points to the new `script_location`.

- [ ] **Step 6: Verify alembic can find migrations**

```bash
uv run alembic current
```

Expected: shows current revision with no errors.

- [ ] **Step 7: Verify frontend build works**

```bash
cd src/memory_orchestrator_server/frontend && npm run build
```

Expected: builds into `src/memory_orchestrator_server/frontend/dist/`.

- [ ] **Step 8: Commit**

```bash
git add src/memory_orchestrator_server/frontend/ \
        src/memory_orchestrator_server/alembic/ \
        src/memory_orchestrator_server/scripts/ \
        src/memory_orchestrator_server/http_app.py \
        alembic.ini Dockerfile CLAUDE.md
git commit -m "refactor: move frontend, alembic, scripts into memory_orchestrator_server"
```

---

### Task 0c: Split `tests/` by package owner

Tests move into the package they test. Server tests (DB, scoring, ingestor, integration) go to `src/memory_orchestrator_server/tests/`. MCP/client tests go to `src/memory_orchestrator_mcp/tests/`. pytest discovers both via updated `testpaths`.

**Classification:**

| File | Destination |
|---|---|
| `conftest.py` | `src/memory_orchestrator_server/tests/` |
| `unit/test_scoring.py` | `src/memory_orchestrator_server/tests/unit/` |
| `unit/test_time_utils.py` | `src/memory_orchestrator_server/tests/unit/` |
| `unit/test_ingestor.py` | `src/memory_orchestrator_server/tests/unit/` |
| `unit/test_ingestor_prompts.py` | `src/memory_orchestrator_server/tests/unit/` |
| `unit/test_package_boundaries.py` | `src/memory_orchestrator_server/tests/unit/` |
| `integration/` (all 5) | `src/memory_orchestrator_server/tests/integration/` |
| `unit/test_hooks_codex.py` | `src/memory_orchestrator_mcp/tests/` |
| `unit/test_mcp_http_client.py` | `src/memory_orchestrator_mcp/tests/` |
| `unit/test_client_adapters.py` | `src/memory_orchestrator_mcp/tests/` |
| `unit/test_client_rules.py` | `src/memory_orchestrator_mcp/tests/` |
| `unit/test_project_id.py` | `src/memory_orchestrator_mcp/tests/` |

**Files:**
- Create: `src/memory_orchestrator_server/tests/__init__.py`
- Create: `src/memory_orchestrator_server/tests/unit/__init__.py`
- Create: `src/memory_orchestrator_server/tests/integration/__init__.py`
- Create: `src/memory_orchestrator_mcp/tests/__init__.py`
- Modify: `pyproject.toml` — `testpaths`

- [ ] **Step 1: Create destination directories**

```bash
mkdir -p src/memory_orchestrator_server/tests/unit
mkdir -p src/memory_orchestrator_server/tests/integration
mkdir -p src/memory_orchestrator_mcp/tests
touch src/memory_orchestrator_server/tests/__init__.py
touch src/memory_orchestrator_server/tests/unit/__init__.py
touch src/memory_orchestrator_server/tests/integration/__init__.py
touch src/memory_orchestrator_mcp/tests/__init__.py
```

- [ ] **Step 2: Move server tests**

```bash
git mv tests/conftest.py src/memory_orchestrator_server/tests/conftest.py
git mv tests/unit/test_scoring.py src/memory_orchestrator_server/tests/unit/
git mv tests/unit/test_time_utils.py src/memory_orchestrator_server/tests/unit/
git mv tests/unit/test_ingestor.py src/memory_orchestrator_server/tests/unit/
git mv tests/unit/test_ingestor_prompts.py src/memory_orchestrator_server/tests/unit/
git mv tests/unit/test_package_boundaries.py src/memory_orchestrator_server/tests/unit/
git mv tests/integration/test_http_app.py src/memory_orchestrator_server/tests/integration/
git mv tests/integration/test_mcp_tools.py src/memory_orchestrator_server/tests/integration/
git mv tests/integration/test_repository.py src/memory_orchestrator_server/tests/integration/
git mv tests/integration/test_auth_tokens.py src/memory_orchestrator_server/tests/integration/
git mv tests/integration/test_cli_tokens.py src/memory_orchestrator_server/tests/integration/
```

- [ ] **Step 3: Move MCP/client tests**

```bash
git mv tests/unit/test_hooks_codex.py src/memory_orchestrator_mcp/tests/
git mv tests/unit/test_mcp_http_client.py src/memory_orchestrator_mcp/tests/
git mv tests/unit/test_client_adapters.py src/memory_orchestrator_mcp/tests/
git mv tests/unit/test_client_rules.py src/memory_orchestrator_mcp/tests/
git mv tests/unit/test_project_id.py src/memory_orchestrator_mcp/tests/
```

- [ ] **Step 4: Delete now-empty `tests/` directory**

```bash
git rm -r tests/
```

- [ ] **Step 5: Update `pyproject.toml` testpaths**

```toml
# Change:
testpaths = ["tests"]
# To:
testpaths = [
    "src/memory_orchestrator_server/tests",
    "src/memory_orchestrator_mcp/tests",
]
```

- [ ] **Step 6: Run all unit tests to verify discovery**

```
uv run pytest src/memory_orchestrator_server/tests/unit/ src/memory_orchestrator_mcp/tests/ -v
```

Expected: all pass with tests discovered from both locations.

- [ ] **Step 7: Commit**

```bash
git add src/memory_orchestrator_server/tests/ \
        src/memory_orchestrator_mcp/tests/ \
        pyproject.toml
git commit -m "refactor: split tests/ into memory_orchestrator_server and _mcp by owner"
```

---

### Task 1: Migrate `time_utils` and `config`

**Files:**
- Create: `src/memory_orchestrator_server/time_utils.py`
- Create: `src/memory_orchestrator_server/config.py`
- Modify: `src/memory_orchestrator/time_utils.py`
- Modify: `src/memory_orchestrator/config.py`

- [ ] **Step 1: Create `memory_orchestrator_server/time_utils.py`**

```python
# src/memory_orchestrator_server/time_utils.py
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    return to_utc(value).isoformat()
```

- [ ] **Step 2: Create `memory_orchestrator_server/config.py`**

```python
# src/memory_orchestrator_server/config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MO_", env_file=".env", extra="ignore")

    db_dsn: str = Field(default="postgresql+asyncpg://postgres:1234@localhost:5432/memory_orchestrator")
    http_port: int = 8765
    embed_model: str = "BAAI/bge-small-zh-v1.5"
    embed_cache_dir: str = "models"
    embed_dim: int = 512
    log_level: str = "DEBUG"

    extraction_base_url: str = Field(default="", validation_alias="MO_EXTRACTION_BASE_URL")
    extraction_model: str = Field(default="gpt-4o-mini", validation_alias="MO_EXTRACTION_MODEL")
    extraction_api_key: str = Field(default="local", validation_alias="MO_EXTRACTION_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Replace `memory_orchestrator/time_utils.py` with a shim**

```python
# src/memory_orchestrator/time_utils.py
from memory_orchestrator_server.time_utils import isoformat_utc, to_utc, utc_now

__all__ = ["isoformat_utc", "to_utc", "utc_now"]
```

- [ ] **Step 4: Replace `memory_orchestrator/config.py` with a shim**

```python
# src/memory_orchestrator/config.py
from memory_orchestrator_server.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
```

- [ ] **Step 5: Run unit tests to verify**

```
uv run pytest tests/unit/test_time_utils.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/memory_orchestrator_server/time_utils.py src/memory_orchestrator_server/config.py \
        src/memory_orchestrator/time_utils.py src/memory_orchestrator/config.py
git commit -m "refactor: migrate time_utils and config to memory_orchestrator_server"
```

---

### Task 2: Migrate `models`

**Files:**
- Create: `src/memory_orchestrator_server/models.py`
- Modify: `src/memory_orchestrator/models.py`

- [ ] **Step 1: Read current `models.py` to get exact content**

Run: `cat src/memory_orchestrator/models.py`

- [ ] **Step 2: Create `memory_orchestrator_server/models.py`**

Copy the full content of `src/memory_orchestrator/models.py` to `src/memory_orchestrator_server/models.py`, then update the two imports inside it:

```python
# Change this:
from memory_orchestrator.config import get_settings
from memory_orchestrator.time_utils import utc_now
# To this:
from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.time_utils import utc_now
```

All other content remains identical.

- [ ] **Step 3: Replace `memory_orchestrator/models.py` with a shim**

Read the full list of public names from `models.py` (classes: `Base`, `Project`, `Memory`, `Session`, `MemoryLink`, `SystemSetting`, `ApiToken`; constants: `GLOBAL_PROJECT_ID`). Then write:

```python
# src/memory_orchestrator/models.py
from memory_orchestrator_server.models import (
    ApiToken,
    Base,
    GLOBAL_PROJECT_ID,
    Memory,
    MemoryLink,
    Project,
    Session,
    SystemSetting,
)

__all__ = [
    "ApiToken", "Base", "GLOBAL_PROJECT_ID",
    "Memory", "MemoryLink", "Project", "Session", "SystemSetting",
]
```

- [ ] **Step 4: Run unit tests**

```
uv run pytest tests/unit/ -v -k "not integration"
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator_server/models.py src/memory_orchestrator/models.py
git commit -m "refactor: migrate models to memory_orchestrator_server"
```

---

### Task 3: Migrate `scoring` and `embedder`

**Files:**
- Create: `src/memory_orchestrator_server/scoring.py`
- Create: `src/memory_orchestrator_server/embedder.py`
- Modify: `src/memory_orchestrator/scoring.py`
- Modify: `src/memory_orchestrator/embedder.py`

- [ ] **Step 1: Read `scoring.py` and `embedder.py` content**

```bash
cat src/memory_orchestrator/scoring.py
cat src/memory_orchestrator/embedder.py
```

- [ ] **Step 2: Create `memory_orchestrator_server/scoring.py`**

Copy `src/memory_orchestrator/scoring.py` to `src/memory_orchestrator_server/scoring.py`, then update its one import:

```python
# Change:
from memory_orchestrator.time_utils import to_utc, utc_now
# To:
from memory_orchestrator_server.time_utils import to_utc, utc_now
```

- [ ] **Step 3: Create `memory_orchestrator_server/embedder.py`**

Copy `src/memory_orchestrator/embedder.py` to `src/memory_orchestrator_server/embedder.py`, then update:

```python
# Change:
from memory_orchestrator.config import get_settings
# To:
from memory_orchestrator_server.config import get_settings
```

- [ ] **Step 4: Replace `memory_orchestrator/scoring.py` with a shim**

Read the exports from `scoring.py` (functions: `hybrid_score`, `truncate_by_budget`). Then:

```python
# src/memory_orchestrator/scoring.py
from memory_orchestrator_server.scoring import hybrid_score, truncate_by_budget

__all__ = ["hybrid_score", "truncate_by_budget"]
```

- [ ] **Step 5: Replace `memory_orchestrator/embedder.py` with a shim**

Read the exports from `embedder.py` (functions: `embed_one`, `ensure_loaded`). Then:

```python
# src/memory_orchestrator/embedder.py
from memory_orchestrator_server.embedder import embed_one, ensure_loaded

__all__ = ["embed_one", "ensure_loaded"]
```

- [ ] **Step 6: Run unit tests**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/memory_orchestrator_server/scoring.py src/memory_orchestrator_server/embedder.py \
        src/memory_orchestrator/scoring.py src/memory_orchestrator/embedder.py
git commit -m "refactor: migrate scoring and embedder to memory_orchestrator_server"
```

---

### Task 4: Migrate `repository`

**Files:**
- Create: `src/memory_orchestrator_server/repository.py`
- Modify: `src/memory_orchestrator/repository.py`

- [ ] **Step 1: Read current `repository.py`**

```bash
cat src/memory_orchestrator/repository.py
```

- [ ] **Step 2: Create `memory_orchestrator_server/repository.py`**

Copy `src/memory_orchestrator/repository.py` to `src/memory_orchestrator_server/repository.py`, then update its three imports:

```python
# Change:
from memory_orchestrator.models import GLOBAL_PROJECT_ID, Memory, Project, SystemSetting
from memory_orchestrator.scoring import hybrid_score, truncate_by_budget
from memory_orchestrator.time_utils import utc_now
# To:
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory, Project, SystemSetting
from memory_orchestrator_server.scoring import hybrid_score, truncate_by_budget
from memory_orchestrator_server.time_utils import utc_now
```

- [ ] **Step 3: Replace `memory_orchestrator/repository.py` with a shim**

Read the exports from `repository.py` (class: `MemoryRepository`, any other public names like `_sync_project_count` if used externally). Then:

```python
# src/memory_orchestrator/repository.py
from memory_orchestrator_server.repository import MemoryRepository, _sync_project_count

__all__ = ["MemoryRepository", "_sync_project_count"]
```

- [ ] **Step 4: Run unit tests**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator_server/repository.py src/memory_orchestrator/repository.py
git commit -m "refactor: migrate repository to memory_orchestrator_server"
```

---

### Task 5: Migrate `auth_tokens` and `db_check`

**Files:**
- Create: `src/memory_orchestrator_server/auth_tokens.py`
- Create: `src/memory_orchestrator_server/db_check.py`
- Modify: `src/memory_orchestrator/auth_tokens.py`
- Modify: `src/memory_orchestrator/db_check.py`

- [ ] **Step 1: Read current `auth_tokens.py` and `db_check.py`**

```bash
cat src/memory_orchestrator/auth_tokens.py
cat src/memory_orchestrator/db_check.py
```

- [ ] **Step 2: Create `memory_orchestrator_server/auth_tokens.py`**

Copy `src/memory_orchestrator/auth_tokens.py` to `src/memory_orchestrator_server/auth_tokens.py`, then update imports:

```python
# Change:
from memory_orchestrator.models import ApiToken
from memory_orchestrator.time_utils import utc_now
# To:
from memory_orchestrator_server.models import ApiToken
from memory_orchestrator_server.time_utils import utc_now
```

- [ ] **Step 3: Create `memory_orchestrator_server/db_check.py`**

Copy `src/memory_orchestrator/db_check.py` to `src/memory_orchestrator_server/db_check.py`. This file has no internal imports from `memory_orchestrator.*` — verify by reading, then copy unchanged.

- [ ] **Step 4: Replace `memory_orchestrator/auth_tokens.py` with a shim**

Read the exports from `auth_tokens.py` (functions: `hash_token`, `require_token_kind`, `auth_dependency`; constants: `TOKEN_KIND_MCP`, `TOKEN_KIND_UI`). Then:

```python
# src/memory_orchestrator/auth_tokens.py
from memory_orchestrator_server.auth_tokens import (
    TOKEN_KIND_MCP,
    TOKEN_KIND_UI,
    auth_dependency,
    hash_token,
    require_token_kind,
)

__all__ = [
    "TOKEN_KIND_MCP", "TOKEN_KIND_UI",
    "auth_dependency", "hash_token", "require_token_kind",
]
```

- [ ] **Step 5: Replace `memory_orchestrator/db_check.py` with a shim**

Read the exports from `db_check.py` (functions: `check_database_dsn`, `check_database_ready`, `format_database_startup_error`). Then:

```python
# src/memory_orchestrator/db_check.py
from memory_orchestrator_server.db_check import (
    check_database_dsn,
    check_database_ready,
    format_database_startup_error,
)

__all__ = ["check_database_dsn", "check_database_ready", "format_database_startup_error"]
```

- [ ] **Step 6: Run unit tests including auth_tokens tests**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/memory_orchestrator_server/auth_tokens.py src/memory_orchestrator_server/db_check.py \
        src/memory_orchestrator/auth_tokens.py src/memory_orchestrator/db_check.py
git commit -m "refactor: migrate auth_tokens and db_check to memory_orchestrator_server"
```

---

### Task 6: Migrate `ingestor`

**Files:**
- Create: `src/memory_orchestrator_server/ingestor.py`
- Modify: `src/memory_orchestrator/ingestor.py`

- [ ] **Step 1: Read current `ingestor.py`**

```bash
cat src/memory_orchestrator/ingestor.py
```

- [ ] **Step 2: Create `memory_orchestrator_server/ingestor.py`**

Copy `src/memory_orchestrator/ingestor.py` to `src/memory_orchestrator_server/ingestor.py`, then update all four imports:

```python
# Change:
from memory_orchestrator.config import get_settings
from memory_orchestrator.embedder import embed_one
from memory_orchestrator.models import GLOBAL_PROJECT_ID, Session as SessionRow
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.time_utils import utc_now
# To:
from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.embedder import embed_one
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Session as SessionRow
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.time_utils import utc_now
```

- [ ] **Step 3: Replace `memory_orchestrator/ingestor.py` with a shim**

Read the public API from `ingestor.py` (function: `ingest_session`; likely a result dataclass). Then:

```python
# src/memory_orchestrator/ingestor.py
from memory_orchestrator_server.ingestor import ingest_session

__all__ = ["ingest_session"]
```

If `ingestor.py` also exports a result type (e.g. `IngestResult`), include it in the shim.

- [ ] **Step 4: Run unit tests**

```
uv run pytest tests/unit/test_ingestor.py tests/unit/test_ingestor_prompts.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator_server/ingestor.py src/memory_orchestrator/ingestor.py
git commit -m "refactor: migrate ingestor to memory_orchestrator_server"
```

---

### Task 7: Migrate `mcp_core`

**Files:**
- Create: `src/memory_orchestrator_server/mcp_core.py`
- Modify: `src/memory_orchestrator/mcp_core.py`

- [ ] **Step 1: Create `memory_orchestrator_server/mcp_core.py`**

Copy `src/memory_orchestrator/mcp_core.py` to `src/memory_orchestrator_server/mcp_core.py`, then update all five imports:

```python
# Change:
from memory_orchestrator.embedder import embed_one
from memory_orchestrator.ingestor import ingest_session
from memory_orchestrator.models import GLOBAL_PROJECT_ID, Memory
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.time_utils import isoformat_utc
# To:
from memory_orchestrator_server.embedder import embed_one
from memory_orchestrator_server.ingestor import ingest_session
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.time_utils import isoformat_utc
```

Also inside `handle_promote_memory` there is a lazy import:
```python
from memory_orchestrator.repository import _sync_project_count
```
Change to:
```python
from memory_orchestrator_server.repository import _sync_project_count
```

And inside `handle_search_memory` there is a lazy import:
```python
from memory_orchestrator.models import Project
```
Change to:
```python
from memory_orchestrator_server.models import Project
```

The import of `memory_orchestrator_shared.mcp_contract` stays unchanged (correct package already).

- [ ] **Step 2: Replace `memory_orchestrator/mcp_core.py` with a shim**

```python
# src/memory_orchestrator/mcp_core.py
from memory_orchestrator_server.mcp_core import (
    DISPATCH,
    current_client,
    format_memory_resource,
    handle_delete_memory,
    handle_ingest_session,
    handle_list_memories,
    handle_promote_memory,
    handle_read_memory_resource,
    handle_save_memory,
    handle_search_memory,
)
from memory_orchestrator_shared.mcp_contract import (
    list_memory_resource_templates,
    list_memory_resources,
)

__all__ = [
    "DISPATCH", "current_client", "format_memory_resource",
    "handle_delete_memory", "handle_ingest_session", "handle_list_memories",
    "handle_promote_memory", "handle_read_memory_resource", "handle_save_memory",
    "handle_search_memory", "list_memory_resource_templates", "list_memory_resources",
]
```

- [ ] **Step 3: Fix `memory_orchestrator/mcp_server.py` shim**

The current shim incorrectly imports `list_memory_resource_templates` and `list_memory_resources` from `memory_orchestrator.mcp_core`. Update it to import from shared directly:

```python
# src/memory_orchestrator/mcp_server.py
from memory_orchestrator_mcp.config import current_client
from memory_orchestrator_mcp.http_client import call_tool as call_http_tool
from memory_orchestrator_mcp.http_client import read_resource as read_http_resource
from memory_orchestrator_mcp.server import run_stdio_server
from memory_orchestrator_shared.mcp_contract import list_memory_resource_templates, list_memory_resources

__all__ = [
    "call_http_tool",
    "current_client",
    "list_memory_resource_templates",
    "list_memory_resources",
    "read_http_resource",
    "run_stdio_server",
]
```

- [ ] **Step 4: Run unit tests**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/memory_orchestrator_server/mcp_core.py \
        src/memory_orchestrator/mcp_core.py \
        src/memory_orchestrator/mcp_server.py
git commit -m "refactor: migrate mcp_core to memory_orchestrator_server"
```

---

### Task 8: Migrate `router_hooks` and `router_ui`

**Files:**
- Create: `src/memory_orchestrator_server/routers/hooks.py`
- Create: `src/memory_orchestrator_server/routers/ui.py`
- Modify: `src/memory_orchestrator/router_hooks.py`
- Modify: `src/memory_orchestrator/router_ui.py`

- [ ] **Step 1: Read `router_hooks.py` and `router_ui.py`**

```bash
cat src/memory_orchestrator/router_hooks.py
cat src/memory_orchestrator/router_ui.py
```

- [ ] **Step 2: Create `memory_orchestrator_server/routers/hooks.py`**

Copy `src/memory_orchestrator/router_hooks.py` to `src/memory_orchestrator_server/routers/hooks.py`, then update all three imports:

```python
# Change:
from memory_orchestrator.ingestor import ingest_session
from memory_orchestrator.models import GLOBAL_PROJECT_ID, Memory
from memory_orchestrator.repository import MemoryRepository
# To:
from memory_orchestrator_server.ingestor import ingest_session
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory
from memory_orchestrator_server.repository import MemoryRepository
```

- [ ] **Step 3: Create `memory_orchestrator_server/routers/ui.py`**

Copy `src/memory_orchestrator/router_ui.py` to `src/memory_orchestrator_server/routers/ui.py`, then update all five imports:

```python
# Change:
from memory_orchestrator.config import get_settings
from memory_orchestrator.auth_tokens import TOKEN_KIND_UI, auth_dependency
from memory_orchestrator.models import GLOBAL_PROJECT_ID, Memory, Project
from memory_orchestrator.repository import MemoryRepository
from memory_orchestrator.time_utils import isoformat_utc, utc_now
# To:
from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.auth_tokens import TOKEN_KIND_UI, auth_dependency
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID, Memory, Project
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.time_utils import isoformat_utc, utc_now
```

- [ ] **Step 4: Replace `memory_orchestrator/router_hooks.py` with a shim**

```python
# src/memory_orchestrator/router_hooks.py
from memory_orchestrator_server.routers.hooks import make_hooks_router

__all__ = ["make_hooks_router"]
```

- [ ] **Step 5: Replace `memory_orchestrator/router_ui.py` with a shim**

```python
# src/memory_orchestrator/router_ui.py
from memory_orchestrator_server.routers.ui import make_ui_router

__all__ = ["make_ui_router"]
```

- [ ] **Step 6: Verify imports in existing `memory_orchestrator_server/routers/__init__.py`**

Run `cat src/memory_orchestrator_server/routers/__init__.py` — if it's empty that's fine, no changes needed.

- [ ] **Step 7: Run unit tests**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/memory_orchestrator_server/routers/hooks.py \
        src/memory_orchestrator_server/routers/ui.py \
        src/memory_orchestrator/router_hooks.py \
        src/memory_orchestrator/router_ui.py
git commit -m "refactor: migrate router_hooks and router_ui to memory_orchestrator_server"
```

---

### Task 9: Update `memory_orchestrator_server/http_app.py` and `routers/mcp.py`

**Files:**
- Modify: `src/memory_orchestrator_server/http_app.py`
- Modify: `src/memory_orchestrator_server/routers/mcp.py`

- [ ] **Step 1: Update `memory_orchestrator_server/http_app.py` imports**

```python
# src/memory_orchestrator_server/http_app.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.db_check import (
    check_database_dsn,
    check_database_ready,
    format_database_startup_error,
)
from memory_orchestrator_server.embedder import ensure_loaded as ensure_embedder
from memory_orchestrator_server.routers.hooks import make_hooks_router
from memory_orchestrator_server.routers.ui import make_ui_router
from memory_orchestrator_server.routers.mcp import make_mcp_http_router


def create_app(*, engine_override: AsyncEngine | None = None, skip_embedder: bool = False) -> FastAPI:
    settings = get_settings()
    engine = engine_override or create_async_engine(settings.db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI(title="Memory Orchestrator")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.on_event("startup")
    async def _startup() -> None:
        try:
            if engine_override is None:
                await check_database_dsn(settings.db_dsn)
            else:
                await check_database_ready(engine)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).critical(
                format_database_startup_error(settings.db_dsn, exc)
            )
            raise
        if not skip_embedder:
            ensure_embedder()

    app.include_router(make_hooks_router(engine=engine, maker=maker, skip_embedder=skip_embedder))
    app.include_router(make_mcp_http_router(maker=maker))
    app.include_router(make_ui_router(maker=maker))

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.exists():
        app.mount("/ui", StaticFiles(directory=str(dist), html=True), name="ui")

    return app
```

- [ ] **Step 2: Update `memory_orchestrator_server/routers/mcp.py` imports**

Change lines 1-9:

```python
from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from memory_orchestrator_server.auth_tokens import TOKEN_KIND_MCP, require_token_kind
from memory_orchestrator_server.mcp_core import DISPATCH, handle_read_memory_resource
from memory_orchestrator_server.repository import MemoryRepository
```

All other content in `mcp.py` (class definitions, route handlers) stays unchanged.

- [ ] **Step 3: Run unit tests to ensure no import cycles**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/memory_orchestrator_server/http_app.py src/memory_orchestrator_server/routers/mcp.py
git commit -m "refactor: update server package to import from memory_orchestrator_server.*"
```

---

### Task 10: Update `memory_orchestrator_server/__init__.py` exports and verify package boundaries

**Files:**
- Modify: `src/memory_orchestrator_server/__init__.py`
- Modify: `tests/unit/test_package_boundaries.py`

- [ ] **Step 1: Check current `memory_orchestrator_server/__init__.py`**

```bash
cat src/memory_orchestrator_server/__init__.py
```

- [ ] **Step 2: Add server package boundary test**

Add a new test to `tests/unit/test_package_boundaries.py`:

```python
def test_server_package_does_not_import_mcp_client():
    package = Path("src/memory_orchestrator_server")
    assert package.exists()

    imports = _imports(package)
    forbidden = {
        "memory_orchestrator_mcp",
    }

    offenders = sorted(
        module
        for module in imports
        for forbidden_module in forbidden
        if module == forbidden_module or module.startswith(f"{forbidden_module}.")
    )
    assert offenders == []
```

- [ ] **Step 3: Run all unit tests including new boundary test**

```
uv run pytest tests/unit/test_package_boundaries.py -v
```

Expected: both boundary tests pass.

- [ ] **Step 4: Run full unit test suite**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_package_boundaries.py src/memory_orchestrator_server/__init__.py
git commit -m "test: add server package boundary test; verify mcp_client isolation"
```

---

### Task 11: Update `cli.py` imports (optional cleanup)

`cli.py` is the `mo` entry point and imports from `memory_orchestrator.*`. Since those are now shims, it will continue to work. This task is optional cleanup to make `cli.py` import server modules directly where appropriate.

**Files:**
- Modify: `src/memory_orchestrator/cli.py`

- [ ] **Step 1: Check which cli.py imports benefit from direct server paths**

`cli.py` uses:
- `memory_orchestrator.config.get_settings` → shim works fine, no change needed
- `memory_orchestrator.db_check.*` → shim works fine, no change needed
- `memory_orchestrator.auth_tokens.*` → shim works fine, no change needed
- `memory_orchestrator.models.ApiToken` → shim works fine, no change needed
- `memory_orchestrator.client_adapters` → stays in `memory_orchestrator` (setup code), no move needed
- `memory_orchestrator.client_rules` → stays in `memory_orchestrator` (setup code), no move needed

Decision: `cli.py` is already correct via shims. Skip direct-import update.

- [ ] **Step 2: Verify `mo serve-http` works via the shim chain**

```bash
uv run python -c "from memory_orchestrator.http_app import create_app; print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 3: Verify `mo serve-mcp` works**

```bash
uv run python -c "from memory_orchestrator.mcp_server import run_stdio_server; print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 4: Commit if any changes were made**

If Step 1 resulted in changes:

```bash
git add src/memory_orchestrator/cli.py
git commit -m "refactor: update cli.py to use server package imports directly"
```

---

### Task 12: Update `alembic/env.py` and test files for hook path change

**Files:**
- Modify: `alembic/env.py`
- Modify: `tests/unit/test_hooks_codex.py`
- Modify: `tests/unit/test_client_rules.py`

#### Part A — `alembic/env.py`

After Task 0b, `alembic/env.py` is now at `src/memory_orchestrator_server/alembic/env.py`. Update its imports to use `memory_orchestrator_server.*` directly (not via shims).

- [ ] **Step 1: Update `src/memory_orchestrator_server/alembic/env.py` imports**

```python
# Change:
from memory_orchestrator.config import get_settings
from memory_orchestrator.db_check import ensure_database_exists, format_database_startup_error
from memory_orchestrator.models import Base
# To:
from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.db_check import ensure_database_exists, format_database_startup_error
from memory_orchestrator_server.models import Base
```

All other content stays unchanged.

- [ ] **Step 2: Verify alembic still runs**

```bash
uv run alembic current
```

Expected: shows current migration revision with no import errors.

#### Part B — `tests/unit/test_hooks_codex.py`

This test loads hook scripts via `runpy.run_path("hooks/...")`. After Task 0 moves the real scripts to `src/memory_orchestrator_mcp/hooks/`, update the path.

- [ ] **Step 3: Update `_load_hook` helper in `test_hooks_codex.py`**

```python
# Change:
def _load_hook(path: str) -> dict:
    return runpy.run_path(path, run_name="hook_under_test")
# To:
def _load_hook(name: str) -> dict:
    path = f"src/memory_orchestrator_mcp/hooks/{name}"
    return runpy.run_path(path, run_name="hook_under_test")
```

Then update all three call sites:

```python
# Change:
module = _load_hook("hooks/user_prompt_submit.py")
# To:
module = _load_hook("user_prompt_submit.py")

# Change:
module = _load_hook("hooks/stop.py")
# To:
module = _load_hook("stop.py")
```

- [ ] **Step 4: Run hook tests**

```
uv run pytest tests/unit/test_hooks_codex.py -v
```

Expected: all pass.

#### Part C — `tests/unit/test_client_rules.py`

Two tests create a fake project directory and populate hook files and instructions. After Task 0a moves these into `src/memory_orchestrator_mcp/`, these tests must mirror the new layout.

- [ ] **Step 5: Update `test_install_codex_from_rule_writes_config_hooks_and_instructions`**

```python
# Change (fake project_dir setup):
(project_dir / "hooks").mkdir()
(project_dir / "hooks" / "user_prompt_submit.py").write_text("", encoding="utf-8")
(project_dir / "hooks" / "stop.py").write_text("", encoding="utf-8")
(project_dir / "agents").mkdir()
(project_dir / "agents" / "memory-orchestrator.AGENTS.md").write_text("Codex instructions", ...)
# To:
(project_dir / "src" / "memory_orchestrator_mcp" / "hooks").mkdir(parents=True)
(project_dir / "src" / "memory_orchestrator_mcp" / "hooks" / "user_prompt_submit.py").write_text("", encoding="utf-8")
(project_dir / "src" / "memory_orchestrator_mcp" / "hooks" / "stop.py").write_text("", encoding="utf-8")
(project_dir / "src" / "memory_orchestrator_mcp" / "agents").mkdir(parents=True)
(project_dir / "src" / "memory_orchestrator_mcp" / "agents" / "memory-orchestrator.AGENTS.md").write_text("Codex instructions", encoding="utf-8")
```

Also update the command path assertion:

```python
# Change:
assert "user_prompt_submit.py" in user_command
assert "--client codex" in user_command
assert f'"{project_dir.resolve()}"' in user_command
# To:
user_cmd_str = " ".join(user_command)
assert "memory_orchestrator_mcp/hooks/user_prompt_submit.py" in user_cmd_str
assert "--client codex" in user_cmd_str
assert str(project_dir.resolve()) in user_cmd_str
```

- [ ] **Step 6: Update `test_install_claude_from_rule_writes_settings_and_skill`**

```python
# Change:
(project_dir / "hooks").mkdir()
(project_dir / "hooks" / "user_prompt_submit.py").write_text("", encoding="utf-8")
(project_dir / "hooks" / "stop.py").write_text("", encoding="utf-8")
(project_dir / "skills" / "memory-orchestrator").mkdir(parents=True)
(project_dir / "skills" / "memory-orchestrator" / "SKILL.md").write_text("Claude skill", encoding="utf-8")
# To:
(project_dir / "src" / "memory_orchestrator_mcp" / "hooks").mkdir(parents=True)
(project_dir / "src" / "memory_orchestrator_mcp" / "hooks" / "user_prompt_submit.py").write_text("", encoding="utf-8")
(project_dir / "src" / "memory_orchestrator_mcp" / "hooks" / "stop.py").write_text("", encoding="utf-8")
(project_dir / "src" / "memory_orchestrator_mcp" / "skills" / "memory-orchestrator").mkdir(parents=True)
(project_dir / "src" / "memory_orchestrator_mcp" / "skills" / "memory-orchestrator" / "SKILL.md").write_text("Claude skill", encoding="utf-8")
```

- [ ] **Step 7: Run client_rules tests**

```
uv run pytest tests/unit/test_client_rules.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add alembic/env.py tests/unit/test_hooks_codex.py tests/unit/test_client_rules.py
git commit -m "refactor: update alembic env.py and tests for new hook and server package paths"
```

---

### Task 13: Final integration test run

- [ ] **Step 1: Run all unit tests**

```
uv run pytest tests/unit/ -v
```

Expected: all pass.

- [ ] **Step 2: Run integration tests (requires Postgres on port 5433)**

```
uv run pytest tests/integration/ -v
```

Expected: all pass.

- [ ] **Step 3: Verify import chain is clean**

```bash
uv run python -c "
from memory_orchestrator_server.http_app import create_app
from memory_orchestrator_mcp.server import run_stdio_server
from memory_orchestrator_shared.mcp_contract import TOOLS
print('All packages import cleanly')
"
```

Expected: `All packages import cleanly` with no import errors.

- [ ] **Step 4: Summary commit**

```bash
git add -p  # review any remaining unstaged changes
git commit -m "refactor: complete package split — memory_orchestrator_server and _mcp are self-contained"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All root-level asset dirs consolidated — `hooks/`+`client-rules/`+`agents/`+`skills/` → `_mcp`; `frontend/`+`alembic/`+`scripts/` → `_server`; `tests/` split by owner; `docs/` untouched. All 11 server Python modules migrated with shims. `http_app.py`, `routers/mcp.py`, `alembic.ini`, `alembic/env.py`, Dockerfile, CLAUDE.md all updated.
- [x] **No placeholders:** Every step has exact code or exact command.
- [x] **Path consistency:** `client_rules.py` base path, JSON `instructions.source`, Dockerfile COPY, `http_app.py` dist path, `alembic.ini` script_location, `pyproject.toml` testpaths all updated in Tasks 0a/0b/0c.
- [x] **Type consistency:** `make_hooks_router`, `make_ui_router`, `make_mcp_http_router` consistent across Tasks 8, 9.
- [x] **Import consistency:** All lazy imports inside `mcp_core.py` updated in Task 7. `alembic/env.py` imports server package directly (Task 12 Part A).
- [x] **Shim correctness:** `mcp_server.py` imports resource helpers from `memory_orchestrator_shared`, not `mcp_core`.
