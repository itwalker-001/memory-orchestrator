# Skeleton Node + Project Token Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attach memories to a hierarchical skeleton, replace `mcp_client` tokens with project-scoped `project_token`, and move MCP setup from user-level to project-level.

**Architecture:**
- Server: `routers/mcp.py` authenticates via `resolve_project_token` (token carries project UUID); `mcp_core.py:handle_save_memory` attaches memory to skeleton node when `node_name`/`parent_node` args are provided.
- Client: `mo-mcp setup` writes to `.claude/settings.json` in the current project dir (`--scope project` only); `/api/register` accepts `project_slug` and creates a `project_token` bound to that project's UUID.
- DB: migration 0011 already deleted `mcp_client` rows and added `api_tokens.project_id`. No new migration needed.

**Tech Stack:** FastAPI, SQLAlchemy async, Click, `mcp` Python SDK, pgvector/PostgreSQL.

---

## File Map

| File | Change |
|------|--------|
| `memory_orchestrator_server/auth_tokens.py` | Remove `TOKEN_KIND_MCP`; `env_token_for_kind` handles `project_token` |
| `memory_orchestrator_server/routers/mcp.py` | Switch auth to `resolve_project_token`; derive `project_uuid` from token |
| `memory_orchestrator_server/routers/ui.py` | `/api/register` accepts `project_slug`, creates `project_token` |
| `memory_orchestrator_server/mcp_core.py` | `handle_save_memory` supports `node_name` + `parent_node` |
| `memory_orchestrator_mcp/cli.py` | `setup` project-scope only; `_auto_register` sends `project_slug`; `_read_token_from_settings` reads project settings |
| `memory_orchestrator_mcp/hooks/user_prompt_submit.py` | No change (uses env var) |
| `memory_orchestrator_mcp/hooks/stop.py` | No change |
| `memory_orchestrator_mcp/skills/memory-orchestrator/SKILL.md` | Add skeleton guidance section |
| `memory_orchestrator_mcp/agents/memory-orchestrator.AGENTS.md` | Add skeleton guidance section |
| `memory_orchestrator_server/tests/unit/test_ui_tokens_schema.py` | Update token kind assertions |
| `memory_orchestrator_server/tests/integration/test_http_app.py` | Update MCP auth tests |

---

## Task 1 — Server: remove `TOKEN_KIND_MCP`, update `auth_tokens.py`

**Files:**
- Modify: `memory_orchestrator_server/auth_tokens.py`
- Modify: `memory_orchestrator_server/tests/unit/test_ui_tokens_schema.py`

`TOKEN_KIND_MCP = "mcp_client"` is dead (migration 0011 deleted all `mcp_client` rows).
`env_token_for_kind` needs to support `project_token` via `MO_MCP_TOKEN` env var (backward compat for env-based auth).

- [ ] **Step 1: Update `auth_tokens.py`**

Replace the entire top section of `auth_tokens.py`:

```python
TOKEN_KIND_UI = "ui_admin"
TOKEN_KIND_PROJECT = "project_token"
UI_SESSION_TTL = 1800


def env_token_for_kind(kind: str) -> str | None:
    if kind == TOKEN_KIND_PROJECT:
        token = os.environ.get("MO_MCP_TOKEN")
    elif kind == TOKEN_KIND_UI:
        token = os.environ.get("MO_UI_TOKEN")
    else:
        token = None
    return (token or "").strip() or None
```

Remove the `TOKEN_KIND_MCP = "mcp_client"` line entirely.

- [ ] **Step 2: Run unit tests**

```bash
cd memory_orchestrator_server
uv run pytest tests/unit/ -q
```

Expected: all pass (or only failures in token-kind assertions which we fix next).

- [ ] **Step 3: Fix any token-kind assertions in unit tests**

In `tests/unit/test_ui_tokens_schema.py`, replace any `"mcp_client"` literal with `"project_token"`.

- [ ] **Step 4: Run unit tests again**

```bash
uv run pytest tests/unit/ -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd ..
git add memory_orchestrator_server/auth_tokens.py memory_orchestrator_server/tests/unit/test_ui_tokens_schema.py
git commit -m "refactor: remove TOKEN_KIND_MCP, map MO_MCP_TOKEN env to project_token"
```

---

## Task 2 — Server: `routers/mcp.py` — auth via `resolve_project_token`

**Files:**
- Modify: `memory_orchestrator_server/routers/mcp.py`
- Modify: `memory_orchestrator_server/tests/integration/test_http_app.py`

Currently `mcp.py` calls `require_token_kind(kind=TOKEN_KIND_MCP, ...)` which checks `mcp_client` rows (all deleted). Switch to `resolve_project_token` which returns the project UUID from the token.

`McpToolRequest.project_slug` stays for informational/display use, but `project_uuid` is authoritative from the token.

- [ ] **Step 1: Write failing integration test**

In `tests/integration/test_http_app.py`, add:

```python
async def test_mcp_call_tool_requires_project_token(engine):
    """MCP /tools/call must reject mcp_client tokens (deleted) and accept project_token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # No token → 401
        r = await client.post("/mcp/tools/call", json={
            "name": "list_memories", "arguments": {},
            "project_slug": "test-proj", "cwd": "/tmp",
        })
        assert r.status_code == 401
```

- [ ] **Step 2: Run test to confirm it fails (currently passes wrong auth)**

```bash
cd memory_orchestrator_server
uv run pytest tests/integration/test_http_app.py::test_mcp_call_tool_requires_project_token -v
```

- [ ] **Step 3: Rewrite `routers/mcp.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from memory_orchestrator_server.auth_tokens import (
    TOKEN_KIND_PROJECT, resolve_project_token, env_token_for_kind,
    bearer_token, hash_token,
)
from memory_orchestrator_server.models import ApiToken
from memory_orchestrator_server.mcp_core import DISPATCH, handle_read_memory_resource
from memory_orchestrator_server.repository import MemoryRepository
from sqlalchemy import select


class McpToolRequest(BaseModel):
    name: str
    arguments: dict = {}
    project_slug: str = ""          # informational; project is resolved from token
    cwd: str | None = None
    client: str | None = None
    os_user: str | None = None


class McpResourceRequest(BaseModel):
    uri: str
    project_slug: str = ""
    cwd: str | None = None
    client: str | None = None
    os_user: str | None = None


async def _resolve_project_uuid(maker, authorization: str | None):
    """Resolve project UUID from project_token or MO_MCP_TOKEN env fallback."""
    # Try env-based token first (dev / test scenarios)
    env_tok = env_token_for_kind(TOKEN_KIND_PROJECT)
    if env_tok:
        raw = bearer_token(authorization) or ""
        if not raw or raw == env_tok:
            # env token accepted — no project binding; returns None (caller handles)
            return None
    async with maker() as s:
        _, project_uuid = await resolve_project_token(session=s, authorization=authorization)
        return project_uuid


def make_mcp_http_router(*, maker: async_sessionmaker) -> APIRouter:
    router = APIRouter(prefix="/mcp")

    @router.post("/tools/call")
    async def call_tool(
        body: McpToolRequest = Body(...),
        authorization: str | None = Header(default=None),
    ) -> dict:
        handler = DISPATCH.get(body.name)
        if not handler:
            raise HTTPException(status_code=404, detail=f"unknown tool: {body.name}")
        async with maker() as s:
            _, project_uuid = await resolve_project_token(session=s, authorization=authorization)
            repo = MemoryRepository(s)
            result = await handler(
                session=s,
                project_uuid=project_uuid,
                args=body.arguments,
                cwd=body.cwd or "",
                client=body.client,
            )
            await s.commit()
        return {"result": result}

    @router.post("/resources/read")
    async def read_resource(
        body: McpResourceRequest = Body(...),
        authorization: str | None = Header(default=None),
    ) -> dict:
        async with maker() as s:
            _, project_uuid = await resolve_project_token(session=s, authorization=authorization)
            repo = MemoryRepository(s)
            try:
                result = await handle_read_memory_resource(
                    session=s,
                    project_uuid=project_uuid,
                    uri=body.uri,
                )
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            await s.commit()
        return {"result": result}

    return router
```

- [ ] **Step 4: Handle env-token fallback in `resolve_project_token`**

The env-based token (`MO_MCP_TOKEN`) can't have a project binding (no row in DB).
For dev/test, when `MO_MCP_TOKEN` env is set and matches, return the global project UUID as fallback.

Update `auth_tokens.py:resolve_project_token`:

```python
async def resolve_project_token(
    *,
    session: AsyncSession,
    authorization: str | None,
) -> tuple[ApiToken | None, uuid.UUID]:
    """Validate a project_token. Returns (token_row_or_None, project_uuid).
    
    If MO_MCP_TOKEN env var matches, returns (None, GLOBAL_PROJECT_ID) as dev fallback.
    """
    from memory_orchestrator_server.models import GLOBAL_PROJECT_ID
    import hmac as _hmac

    raw = bearer_token(authorization)
    if not raw:
        raise HTTPException(status_code=401, detail="missing bearer token")

    # Env-based fallback for dev/test
    env_tok = env_token_for_kind(TOKEN_KIND_PROJECT)
    if env_tok and _hmac.compare_digest(raw, env_tok):
        return None, GLOBAL_PROJECT_ID

    token_hash = hash_token(raw)
    result = await session.execute(
        select(ApiToken).where(
            ApiToken.kind == TOKEN_KIND_PROJECT,
            ApiToken.token_hash == token_hash,
            ApiToken.revoked_at.is_(None),
            ApiToken.enabled.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=401, detail="invalid project token")
    if not row.project_id:
        raise HTTPException(status_code=401, detail="token has no project binding")
    await session.execute(
        update(ApiToken).where(ApiToken.id == row.id)
        .values(last_used_at=utc_now())
        .execution_options(synchronize_session=False)
    )
    return row, row.project_id
```

Also remove `_db_has_tokens` usage for MCP kind (no longer needed for MCP auth).

- [ ] **Step 5: Run integration tests**

```bash
uv run pytest tests/integration/ -q
```

Fix any failures caused by token kind change.

- [ ] **Step 6: Commit**

```bash
cd ..
git add memory_orchestrator_server/routers/mcp.py memory_orchestrator_server/auth_tokens.py memory_orchestrator_server/tests/integration/test_http_app.py
git commit -m "feat: mcp auth via project_token; project_uuid from token binding"
```

---

## Task 3 — Server: `/api/register` — create `project_token` with `project_slug`

**Files:**
- Modify: `memory_orchestrator_server/routers/ui.py` (the `register_client` function)

Currently `/api/register` creates `mcp_client` tokens (no project binding). Replace with `project_token` creation bound to a specific project (by slug).

New request body: `{"project_slug": "myapp", "name": "hostname(ip)", "hostname": "...", "ip": "...", "force": false}`

- [ ] **Step 1: Replace `register_client` in `routers/ui.py`**

Find the `@public.post("/register", status_code=201)` block and replace entirely:

```python
@public.post("/register", status_code=201)
async def register_client(body: dict = Body(...)) -> dict:
    """Issue a project_token for a remote client (no auth required — localhost only).

    Body: {
      "project_slug": str,     -- required; project to bind the token to
      "name": str,             -- host identifier, e.g. "BK-A-JA183(172.21.170.85)"
      "hostname": str,
      "ip": str,
      "force": bool            -- if false (default) and valid token exists, don't replace
    }
    Returns: {"token": str, "name": str, "project_slug": str, "already_registered": bool}
    """
    import hashlib
    import secrets
    from memory_orchestrator_server.models import ApiToken
    from memory_orchestrator_server.auth_tokens import TOKEN_KIND_PROJECT
    from memory_orchestrator_server.repository import MemoryRepository
    from sqlalchemy import select

    project_slug = str(body.get("project_slug") or "").strip()
    if not project_slug:
        raise HTTPException(status_code=422, detail="project_slug is required")

    hostname = str(body.get("hostname") or "unknown")
    ip = str(body.get("ip") or "")
    name = str(body.get("name") or (f"{hostname}({ip})" if ip else hostname))
    force = bool(body.get("force", False))

    async with maker() as s:
        repo = MemoryRepository(s)
        project_uuid = await repo.ensure_project(project_slug)

        existing = (await s.execute(
            select(ApiToken).where(
                ApiToken.name == name,
                ApiToken.kind == TOKEN_KIND_PROJECT,
                ApiToken.project_id == project_uuid,
                ApiToken.revoked_at.is_(None),
                ApiToken.enabled.is_(True),
            )
        )).scalar_one_or_none()

        if existing is not None and not force:
            return {"token": "", "name": name, "project_slug": project_slug, "already_registered": True}

        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()

        if existing is not None:
            existing.token_hash = token_hash
        else:
            s.add(ApiToken(name=name, kind=TOKEN_KIND_PROJECT, token_hash=token_hash,
                           project_id=project_uuid))
        await s.commit()

    return {"token": raw, "name": name, "project_slug": project_slug, "already_registered": False}
```

- [ ] **Step 2: Run tests**

```bash
cd memory_orchestrator_server
uv run pytest tests/ -q
```

- [ ] **Step 3: Commit**

```bash
cd ..
git add memory_orchestrator_server/routers/ui.py
git commit -m "feat: /api/register creates project_token bound to project_slug"
```

---

## Task 4 — Server: `mcp_core.py` — `save_memory` skeleton node support

**Files:**
- Modify: `memory_orchestrator_server/mcp_core.py`

Add optional `node_name` (leaf node name) and `parent_node` (parent name) to `handle_save_memory`.
After the memory is created, if `node_name` is provided, call `repo.get_or_create_skeleton_node` then `repo.add_memory_to_node`.

- [ ] **Step 1: Write failing unit test**

In `tests/unit/`, add `test_mcp_core_skeleton.py`:

```python
import pytest, uuid
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_save_memory_attaches_to_node():
    """save_memory with node_name should call get_or_create_skeleton_node + add_memory_to_node."""
    from memory_orchestrator_server.mcp_core import handle_save_memory

    project_uuid = uuid.uuid4()
    memory_id = uuid.uuid4()
    node_id = uuid.uuid4()

    mock_memory = MagicMock()
    mock_memory.id = memory_id

    with patch("memory_orchestrator_server.mcp_core.MemoryRepository") as MockRepo, \
         patch("memory_orchestrator_server.mcp_core.embed_one", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1024
        repo_instance = AsyncMock()
        repo_instance.find_duplicates.return_value = []
        repo_instance.save.return_value = mock_memory
        repo_instance.get_settings.return_value = {"dup_threshold": "0.92"}
        repo_instance.get_or_create_skeleton_node.return_value = node_id
        repo_instance.add_memory_to_node.return_value = True
        MockRepo.return_value = repo_instance

        result = await handle_save_memory(
            session=AsyncMock(),
            project_uuid=project_uuid,
            args={
                "type": "project", "name": "test", "description": "desc", "content": "body",
                "node_name": "功能实现", "parent_node": "后端",
            },
        )

    assert result["action"] == "created"
    repo_instance.get_or_create_skeleton_node.assert_called_once_with(
        project_uuid, "功能实现", "后端"
    )
    repo_instance.add_memory_to_node.assert_called_once_with(node_id, memory_id)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd memory_orchestrator_server
uv run pytest tests/unit/test_mcp_core_skeleton.py -v
```

Expected: FAIL — `get_or_create_skeleton_node` not called.

- [ ] **Step 3: Update `handle_save_memory` in `mcp_core.py`**

After the memory is saved (both the `replace_id` path and the new-save path), add skeleton attachment:

```python
async def _attach_to_skeleton(
    repo: MemoryRepository, project_uuid: uuid.UUID, memory_id: uuid.UUID,
    node_name: str | None, parent_node: str | None,
) -> None:
    if not node_name:
        return
    nid = await repo.get_or_create_skeleton_node(project_uuid, node_name, parent_node or None)
    await repo.add_memory_to_node(nid, memory_id)


async def handle_save_memory(
    *, session: AsyncSession, project_uuid: uuid.UUID, args: dict, cwd: str = "",
    client: str | None = None, **_
) -> dict:
    repo = MemoryRepository(session)
    mtype = args["type"]
    scope_slug = args.get("project_id")
    node_name: str | None = args.get("node_name") or None
    parent_node: str | None = args.get("parent_node") or None

    if scope_slug:
        scope_uuid = await repo.ensure_project(scope_slug, cwd or None)
    elif mtype == "user":
        scope_uuid = await repo.ensure_project("*")
    else:
        scope_uuid = project_uuid

    embedding = await embed_one(args["content"])
    replace_id = args.get("replace_id")
    if replace_id:
        await repo.delete(uuid.UUID(replace_id), hard=False)
        m = await repo.save(
            type=mtype, name=args["name"], description=args["description"],
            content=args["content"], why=args.get("why"), how_to_apply=args.get("how_to_apply"),
            importance=int(args.get("importance", 3)), project_id=scope_uuid,
            source="explicit", source_client=current_client(client), embedding=embedding,
        )
        await _attach_to_skeleton(repo, scope_uuid, m.id, node_name, parent_node)
        return {"id": str(m.id), "action": "merged"}

    dups = await repo.find_duplicates(
        type=mtype, project_id=scope_uuid, embedding=embedding,
        threshold=float((await repo.get_settings()).get("dup_threshold") or 0.92),
    )
    if dups:
        return {"action": "conflict", "conflicts": [
            {"id": str(d.id), "name": d.name, "description": d.description} for d in dups
        ]}
    m = await repo.save(
        type=mtype, name=args["name"], description=args["description"],
        content=args["content"], why=args.get("why"), how_to_apply=args.get("how_to_apply"),
        importance=int(args.get("importance", 3)), project_id=scope_uuid,
        source="explicit", embedding=embedding, source_client=current_client(client),
    )
    await _attach_to_skeleton(repo, scope_uuid, m.id, node_name, parent_node)
    return {"id": str(m.id), "action": "created"}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_mcp_core_skeleton.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
cd ..
git add memory_orchestrator_server/mcp_core.py memory_orchestrator_server/tests/unit/test_mcp_core_skeleton.py
git commit -m "feat: save_memory supports node_name/parent_node for skeleton attachment"
```

---

## Task 5 — Client: `cli.py` — project-scope setup only

**Files:**
- Modify: `memory_orchestrator_mcp/cli.py`

Changes:
1. `_auto_register` sends `project_slug`; returns `project_slug` in result
2. `setup` command: remove user-scope path; `claude mcp add --scope project`; write `.claude/settings.json` in CWD; token to `.claude/settings.local.json`
3. `_setup_codex`: no scope change needed (Codex has no scope concept); but should still pass `project_slug`
4. `_read_token_from_settings`: reads project-level `.claude/settings.local.json` then `~/.claude.json` fallback
5. `register` command: add `--project-slug` option
6. `teardown`: `claude mcp remove --scope project`
7. Remove references to `TOKEN_KIND_MCP` / `mcp_client`

- [ ] **Step 1: Update `_auto_register` to send `project_slug`**

```python
def _auto_register(base_url: str, project_slug: str = "", force: bool = False) -> str:
    """Request a project_token from the server via POST /api/register."""
    import json, socket, urllib.request, urllib.error
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
    except Exception:
        hostname, ip = "unknown", "unknown"
    name = f"{hostname}({ip})"
    body = json.dumps({
        "name": name, "hostname": hostname, "ip": ip,
        "project_slug": project_slug, "force": force,
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/register",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            result = json.loads(resp.read())
            token = result.get("token", "")
            if result.get("already_registered") and not force:
                _flog(f"auto_register: server has valid token for {name}/{project_slug}, retrying force=true")
                return _auto_register(base_url, project_slug=project_slug, force=True)
            if token:
                _flog(f"auto_register: obtained token for {result.get('name')} / {result.get('project_slug')}")
            return token
    except (urllib.error.URLError, Exception) as e:
        _flog(f"auto_register failed: {e!r}")
        return ""
```

- [ ] **Step 2: Add `_project_settings_path()` and `_project_local_settings_path()`**

```python
def _project_settings_path(cwd: str | None = None) -> Path:
    """Returns .claude/settings.json in the current project directory."""
    return Path(cwd or os.getcwd()) / ".claude" / "settings.json"

def _project_local_settings_path(cwd: str | None = None) -> Path:
    """Returns .claude/settings.local.json — stores secrets, not committed."""
    return Path(cwd or os.getcwd()) / ".claude" / "settings.local.json"
```

- [ ] **Step 3: Add `_read_token_from_project_settings()` and update `_read_token_from_settings()`**

```python
def _read_token_from_project_settings(cwd: str | None = None) -> str:
    """Read MO_MCP_TOKEN from .claude/settings.local.json in project dir."""
    import json
    try:
        p = _project_local_settings_path(cwd)
        data = json.loads(p.read_text(encoding="utf-8"))
        return (data.get("mcpServers", {})
                    .get("memory-orchestrator", {})
                    .get("env", {})
                    .get("MO_MCP_TOKEN", ""))
    except Exception:
        return ""


def _read_token_from_settings() -> str:
    """Read MO_MCP_TOKEN — checks project local settings first, then ~/.claude.json."""
    token = _read_token_from_project_settings()
    if token:
        return token
    # Legacy fallback: user-level ~/.claude.json
    import json
    try:
        data = json.loads(_claude_json_path().read_text(encoding="utf-8"))
        return (data.get("mcpServers", {})
                    .get("memory-orchestrator", {})
                    .get("env", {})
                    .get("MO_MCP_TOKEN", ""))
    except Exception:
        return ""
```

- [ ] **Step 4: Add `_write_project_local_env()` helper**

```python
def _write_project_local_env(cwd: str | None = None, **kwargs: str) -> None:
    """Write MCP env vars to .claude/settings.local.json (secrets, not committed)."""
    import json
    p = _project_local_settings_path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.setdefault("mcpServers", {}).setdefault("memory-orchestrator", {}).setdefault("env", {}).update(kwargs)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 5: Rewrite `setup` command (Claude path)**

Replace the entire `setup` command:

```python
@main.command(name="setup")
@click.option("--base-url", prompt="Memory Orchestrator server URL", help="e.g. http://172.16.10.124:8765")
@click.option("--client", type=click.Choice(["claude", "codex"]), default="claude", show_default=True)
@click.option("--project-slug", default=None, help="Project slug on the server (default: detected from git remote)")
def setup(base_url: str, client: str, project_slug: str | None) -> None:
    """Configure MCP for this project: write .claude/settings.json + register project_token."""
    import json, subprocess, sys
    import platform

    base_url = base_url.rstrip("/")
    mcp_dir = str(Path(__file__).parent.resolve()).replace("\\", "/")
    cwd = os.getcwd()

    # Detect project slug if not provided
    if not project_slug:
        from memory_orchestrator_mcp.project_id import detect_project_id
        project_slug = detect_project_id(cwd)
        click.echo(f"Detected project slug: {project_slug}")

    if client == "codex":
        _setup_codex(base_url, mcp_dir, project_slug=project_slug)
        return

    # --- Claude project-level setup ---
    _shell = platform.system() == "Windows"

    # 1. Register MCP server at project scope
    subprocess.run(
        ["claude", "mcp", "remove", "memory-orchestrator", "--scope", "project"],
        capture_output=True, shell=_shell,
    )
    result = subprocess.run(
        [
            "claude", "mcp", "add", "memory-orchestrator",
            "--scope", "project",
            "--",
            "uv", "run", "--no-sync", "--project", mcp_dir,
            "mo-mcp", "serve-mcp", "--client", client,
        ],
        capture_output=True, text=True, shell=_shell,
    )
    if result.returncode != 0:
        click.echo(f"claude mcp add failed: {result.stderr.strip()}", err=True)
        sys.exit(1)
    click.echo(f"[1/4] claude mcp add --scope project: ok")

    # 2. Write hooks to project .claude/settings.json
    proj_settings = _project_settings_path(cwd)
    data = json.loads(proj_settings.read_text(encoding="utf-8")) if proj_settings.exists() else {}
    data.setdefault("hooks", {})
    data["hooks"]["UserPromptSubmit"] = [{"hooks": [{"type": "command", "command": _hook_cmd(mcp_dir, "user_prompt_submit", client, base_url)}]}]
    data["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": _hook_cmd(mcp_dir, "stop", client, base_url)}]}]
    proj_settings.parent.mkdir(parents=True, exist_ok=True)
    proj_settings.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"[2/4] hooks written to {proj_settings}")

    # 3. Write MO_HTTP_BASE_URL to project local settings (non-secret but project-specific)
    _write_project_local_env(cwd, MO_HTTP_BASE_URL=base_url)
    click.echo(f"[3/4] MO_HTTP_BASE_URL written to .claude/settings.local.json")

    # 4. Register project_token + write to local settings
    token = _auto_register(base_url, project_slug=project_slug)
    if token:
        _write_project_local_env(cwd, MO_MCP_TOKEN=token)
        click.echo(f"[4/4] project_token registered → written to .claude/settings.local.json")
    else:
        click.echo(f"[4/4] ERROR: registration failed — server unreachable at {base_url}", err=True)
        sys.exit(1)

    # 5. Install SKILL.md
    import shutil
    skill_src = Path(mcp_dir) / "skills" / "memory-orchestrator" / "SKILL.md"
    skill_dst = Path(cwd) / ".claude" / "skills" / "memory-orchestrator" / "SKILL.md"
    if skill_src.exists():
        skill_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, skill_dst)
        click.echo(f"[5/5] SKILL.md installed → {skill_dst}")

    click.echo("")
    click.echo("Done. Open a NEW terminal / restart Claude Code for env vars to take effect.")
    click.echo(f"Add .claude/settings.local.json to .gitignore to keep the token private.")
```

- [ ] **Step 6: Update `_setup_codex` signature to accept `project_slug`**

Add `project_slug: str = ""` parameter to `_setup_codex`, pass it to `_auto_register`:

```python
def _setup_codex(base_url: str, mcp_dir: str, project_slug: str = "") -> None:
    ...
    # In step 3 (register token):
    token = _auto_register(base_url, project_slug=project_slug)
    ...
```

- [ ] **Step 7: Update `teardown` command — `--scope project`**

In the Claude teardown path, change `--scope project` default and remove user-scope:

```python
@main.command(name="teardown")
@click.option("--client", type=click.Choice(["claude", "codex"]), default="claude", show_default=True)
def teardown(client: str) -> None:
    """Remove Memory Orchestrator MCP wiring from this project."""
```

Remove `--scope` option (always project). In the Claude path:
- `claude mcp remove --scope project` (not user)
- Clean `.claude/settings.json` in CWD (not `~/.claude/settings.json`)
- Remove `.claude/settings.local.json` MCP env vars

- [ ] **Step 8: Update `register` command**

```python
@main.command(name="register")
@click.option("--base-url", default=None)
@click.option("--project-slug", default=None, help="Override auto-detected project slug")
@click.option("--force", is_flag=True, default=False)
def register(base_url: str | None, project_slug: str | None, force: bool) -> None:
    """Register/refresh this project's token."""
    cwd = os.getcwd()
    url = (base_url or os.environ.get("MO_HTTP_BASE_URL") or "http://localhost:8765").rstrip("/")
    if not project_slug:
        from memory_orchestrator_mcp.project_id import detect_project_id
        project_slug = detect_project_id(cwd)
    token = _auto_register(url, project_slug=project_slug, force=force)
    if token:
        _write_project_local_env(cwd, MO_MCP_TOKEN=token, MO_HTTP_BASE_URL=url)
        click.echo(f"Registered. Token written to .claude/settings.local.json")
    else:
        click.echo("Registration failed. Is the server running?", err=True)
```

- [ ] **Step 9: Update `serve-mcp` auto-register path**

```python
if not token_from_file and not token_from_env:
    cwd = _cwd()
    from memory_orchestrator_mcp.project_id import detect_project_id
    project_slug = detect_project_id(cwd)
    token = _auto_register(base_url, project_slug=project_slug)
    if not token:
        raise RuntimeError(...)
    os.environ["MO_MCP_TOKEN"] = token
    _write_project_local_env(cwd, MO_MCP_TOKEN=token)
    _flog("serve-mcp: auto-registered project_token saved")
```

- [ ] **Step 10: Run tests**

```bash
cd memory_orchestrator_mcp
uv run pytest -q
```

Fix any failures.

- [ ] **Step 11: Commit**

```bash
cd ..
git add memory_orchestrator_mcp/cli.py
git commit -m "feat: setup writes project-scope config; project_slug required for registration"
```

---

## Task 6 — Client: `serve-mcp` tool schema update

**Files:**
- Modify: `memory_orchestrator_mcp/cli.py` (`_run_stdio_server` tool definitions)

Add `node_name` and `parent_node` to the `save_memory` tool schema in `_run_stdio_server`.

- [ ] **Step 1: Update `save_memory` Tool definition**

In `_run_stdio_server`, replace the `save_memory` Tool:

```python
Tool(name="save_memory",
     description="Write a memory to Memory Orchestrator; returns conflicts if near-duplicate exists.",
     inputSchema={"type": "object", "properties": {
         "type": {"type": "string"},
         "name": {"type": "string"},
         "description": {"type": "string"},
         "content": {"type": "string"},
         "project_id": {"type": "string"},
         "why": {"type": "string"},
         "how_to_apply": {"type": "string"},
         "importance": {"type": "integer"},
         "replace_id": {"type": "string"},
         "node_name": {"type": "string",
                       "description": "Skeleton leaf node name, e.g. '功能实现'"},
         "parent_node": {"type": "string",
                         "description": "Parent node name, e.g. '后端'. Required when node_name is a leaf under a category."},
     }, "required": ["type", "name", "description", "content"]}),
```

- [ ] **Step 2: Run tests**

```bash
cd memory_orchestrator_mcp
uv run pytest -q
```

- [ ] **Step 3: Commit**

```bash
cd ..
git add memory_orchestrator_mcp/cli.py
git commit -m "feat: save_memory MCP schema adds node_name/parent_node"
```

---

## Task 7 — Docs: SKILL.md + AGENTS.md skeleton guidance

**Files:**
- Modify: `memory_orchestrator_mcp/skills/memory-orchestrator/SKILL.md`
- Modify: `memory_orchestrator_mcp/agents/memory-orchestrator.AGENTS.md`

Add a "Skeleton Nodes" section documenting the default tree and when to use `node_name`/`parent_node`.

- [ ] **Step 1: Add skeleton section to `SKILL.md`**

Insert after the `## Memory Types` section:

````markdown
## Skeleton Nodes — Organizing Memories into a Project Tree

Each project has a predefined skeleton tree. When saving a memory, specify `node_name`
(and `parent_node` if the name is ambiguous across categories) to file it in the right place.

### Default Skeleton Tree

```
项目概况 / 技术栈
项目概况 / 项目说明
项目概况 / 架构概览
项目概况 / 外部依赖

需求 / 原始需求
需求 / 需求拆解
需求 / 需求变更
需求 / 待确认

设计 / 架构设计
设计 / 接口设计
设计 / 数据模型
设计 / 原型设计

前端 / 功能实现
前端 / 问题记录
前端 / 优化记录
前端 / 开发经验

后端 / 功能实现
后端 / 问题记录
后端 / 优化记录
后端 / 开发经验

数据库 / 表结构
数据库 / SQL优化
数据库 / 数据迁移
数据库 / 故障记录

测试 / 单元测试
测试 / 集成测试
测试 / 测试技巧
测试 / 缺陷记录

部署 / 环境配置
部署 / Docker部署
部署 / 发布流程
部署 / 故障恢复

决策记录 / 技术选型
决策记录 / 架构决策
决策记录 / 历史原因
决策记录 / 方案对比

经验库 / 开发技巧
经验库 / 调试技巧
经验库 / 测试技巧
经验库 / 常见坑
```

### When to specify `node_name`

Always specify `node_name` + `parent_node` when the memory clearly belongs to a category:

| Signal | node_name | parent_node |
|--------|-----------|-------------|
| Implementing a backend API | 功能实现 | 后端 |
| Fixing a frontend bug | 问题记录 | 前端 |
| Why we chose PostgreSQL | 技术选型 | 决策记录 |
| DB schema change | 表结构 | 数据库 |
| A deployment gotcha | 常见坑 | 经验库 |
| Architecture overview | 架构概览 | 项目概况 |

Omit `node_name` only for `user` type memories (global, no project tree) or when the
memory spans multiple categories.
````

- [ ] **Step 2: Add skeleton section to `AGENTS.md`**

Insert the same skeleton tree (condensed) and the trigger table into the AGENTS.md between
`## Tool Reference` and the existing content.

- [ ] **Step 3: Run mcp tests to ensure no regressions**

```bash
cd memory_orchestrator_mcp
uv run pytest -q
```

- [ ] **Step 4: Commit**

```bash
cd ..
git add memory_orchestrator_mcp/skills/memory-orchestrator/SKILL.md \
        memory_orchestrator_mcp/agents/memory-orchestrator.AGENTS.md
git commit -m "docs: add skeleton node guidance to SKILL.md and AGENTS.md"
```

---

## Task 8 — Final: push + redeploy server

- [ ] **Step 1: Push all commits**

```bash
git push
```

- [ ] **Step 2: Redeploy server**

```bash
./scripts/build.sh
```

- [ ] **Step 3: Re-run project setup**

```bash
cd <your-project-directory>
uv run mo-mcp setup --client claude --base-url http://172.16.10.124:8765
```

- [ ] **Step 4: Verify**

```bash
uv run mo-mcp doctor --base-url http://172.16.10.124:8765
claude mcp list
```

Expected: `memory-orchestrator: ✓ Connected`

---

## Self-Review

**Spec coverage:**
- ✅ Skeleton node support in `save_memory` (Task 4, 6)
- ✅ `node_name` / `parent_node` MCP params (Task 6)
- ✅ SKILL.md skeleton tree + guidance (Task 7)
- ✅ `mcp_client` → `project_token` rename (Task 1, 2, 3)
- ✅ Project-level setup only, no user-level (Task 5)
- ✅ `/api/register` creates `project_token` with `project_slug` (Task 3)
- ✅ `teardown` works at project scope (Task 5 step 7)
- ✅ `register` command accepts `--project-slug` (Task 5 step 8)
- ✅ Token saved to `.claude/settings.local.json` (not committed) (Task 5)

**Gaps checked:**
- `.gitignore` hint: mentioned in `setup` echo, not automated — acceptable
- Codex `_setup_codex` project_slug: handled in Task 5 step 6
- `serve-mcp` auto-register uses `project_slug` from cwd: Task 5 step 9

**Type consistency:**
- `_auto_register(base_url, project_slug, force)` — consistent across Task 5 steps 1, 8, 9
- `_write_project_local_env(cwd, **kwargs)` — consistent across steps 3, 4, 8, 9
- `resolve_project_token` returns `tuple[ApiToken | None, uuid.UUID]` — consistent in Task 2 steps 3, 4
