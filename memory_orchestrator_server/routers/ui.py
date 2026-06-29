from __future__ import annotations
import json
import uuid
from pathlib import Path
import httpx
from fastapi import APIRouter, Body, Cookie, Depends, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import async_sessionmaker

from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.models import Memory, Project, ProjectSkeletonNode
from memory_orchestrator_server.repository import MemoryRepository, _sync_project_count
from memory_orchestrator_server.time_utils import isoformat_utc, utc_now

_DEFAULTS_FILE = Path(__file__).parent.parent / "settings_defaults.json"
SETTINGS_SEED: dict[str, str] = json.loads(_DEFAULTS_FILE.read_text())

SETTINGS_KEYS = [
    "extraction_base_url",
    "extraction_model",
    "extraction_api_key",
    "embed_model",
    "embed_dim",
    "hook_cooldown_sec",
    "hook_min_turns",
    "hook_budget_tokens",
    "search_top_k",
    "search_min_score",
    "dup_threshold",
    "db_dsn",
    "http_port",
    "rerank_enabled",
    "rerank_model",
    "score_cosine_weight",
    "score_importance_weight",
    "score_recency_weight",
    "score_recency_half_life",
    "score_rerank_blend",
    "bm25_enabled",
    "score_bm25_weight",
    "score_type_feedback",
    "score_type_project",
    "score_type_user",
    "score_type_reference",
]


class MemoryCreate(BaseModel):
    type: str
    name: str
    description: str
    content: str
    why: str | None = None
    how_to_apply: str | None = None
    importance: int = 3
    project_id: str | None = None
    source_client: str = "claude"


class MemoryPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    why: str | None = None
    how_to_apply: str | None = None
    importance: int | None = None


class SettingsPatch(BaseModel):
    extraction_base_url: str | None = None
    extraction_model: str | None = None
    extraction_api_key: str | None = None
    embed_model: str | None = None
    embed_dim: str | None = None
    hook_cooldown_sec: str | None = None
    hook_min_turns: str | None = None
    hook_budget_tokens: str | None = None
    search_top_k: str | None = None
    search_min_score: str | None = None
    dup_threshold: str | None = None
    db_dsn: str | None = None
    http_port: str | None = None
    rerank_enabled: str | None = None
    rerank_model: str | None = None
    score_cosine_weight: str | None = None
    score_importance_weight: str | None = None
    score_recency_weight: str | None = None
    score_recency_half_life: str | None = None
    score_rerank_blend: str | None = None
    bm25_enabled: str | None = None
    score_bm25_weight: str | None = None
    score_type_feedback: str | None = None
    score_type_project: str | None = None
    score_type_user: str | None = None
    score_type_reference: str | None = None


class BatchDeleteBody(BaseModel):
    ids: list[uuid.UUID]


class BatchMoveBody(BaseModel):
    ids: list[uuid.UUID]
    project_slug: str


class TokenCreate(BaseModel):
    kind: str
    name: str
    project_id: uuid.UUID | None = None


class TokenPatch(BaseModel):
    enabled: bool | None = None
    name: str | None = None


class ProjectCreate(BaseModel):
    slug: str
    display_name: str


class ProjectPatch(BaseModel):
    display_name: str


class SkeletonNodeCreate(BaseModel):
    project_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None = None
    description: str | None = None
    prompt_hint: str | None = None
    tags: list[str] | None = None


class SkeletonNodePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt_hint: str | None = None
    tags: list[str] | None = None


class SkeletonNodeReorder(BaseModel):
    project_id: uuid.UUID
    ordered_ids: list[uuid.UUID]


class NodeMemoryAdd(BaseModel):
    memory_id: uuid.UUID


def _latest_mcp_wheel(downloads_dir: Path) -> Path | None:
    """Return the wheel with the highest version in downloads_dir, or None."""
    wheels = [p for p in downloads_dir.glob("memory_orchestrator_mcp-*.whl") if p.is_file()]
    if not wheels:
        return None

    def _ver(p: Path) -> tuple:
        try:
            return tuple(int(x) for x in p.stem.split("-")[1].split("."))
        except Exception:
            return (0,)

    return max(wheels, key=_ver)


def _new_token_pair() -> tuple[str, str, str | None]:
    import secrets
    from memory_orchestrator_server.auth_tokens import hash_token, encrypt_token

    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw), encrypt_token(raw)


def make_ui_router(*, maker: async_sessionmaker) -> APIRouter:
    from memory_orchestrator_server.auth_tokens import (
        TOKEN_KIND_UI,
        UI_SESSION_TTL,
        auth_dependency,
        check_token_valid,
        _db_has_tokens,
        env_token_for_kind,
    )

    outer = APIRouter()
    public = APIRouter(prefix="/api", tags=["Auth"])
    _auth_dep = auth_dependency(maker=maker, kind=TOKEN_KIND_UI)
    router = APIRouter(prefix="/api", dependencies=[Depends(_auth_dep)])

    # ── Public: login / logout ────────────────────────────────────────────────

    @public.post("/login", status_code=200)
    async def login(body: dict = Body(...)) -> JSONResponse:
        token = str(body.get("token") or "").strip()
        async with maker() as s:
            env_tok = env_token_for_kind(TOKEN_KIND_UI)
            db_has = await _db_has_tokens(s, TOKEN_KIND_UI)
            auth_required = bool(env_tok or db_has)
            if auth_required:
                if not token:
                    raise HTTPException(status_code=401, detail="token required")
                if not await check_token_valid(s, TOKEN_KIND_UI, token):
                    raise HTTPException(status_code=401, detail="invalid token")
        response = JSONResponse(content={"ok": True})
        if token:
            response.set_cookie(
                key="mo_ui_session",
                value=token,
                httponly=True,
                samesite="strict",
                path="/",
                max_age=UI_SESSION_TTL,
            )
        return response

    @public.post("/logout", status_code=200)
    async def logout() -> JSONResponse:
        response = JSONResponse(content={"ok": True})
        response.delete_cookie(key="mo_ui_session", path="/", samesite="strict")
        return response

    @public.get("/mcp-package", tags=["Downloads"], summary="Latest MCP client package version")
    async def mcp_package_info() -> dict:
        d = Path(get_settings().downloads_dir)
        latest = _latest_mcp_wheel(d)
        if not latest:
            raise HTTPException(status_code=404, detail="no MCP package available on this server")
        version = latest.stem.split("-")[1]
        return {"version": version, "filename": latest.name, "size": latest.stat().st_size}

    @public.get("/mcp-package/wheel", tags=["Downloads"], summary="Download latest MCP client wheel")
    async def download_mcp_wheel() -> FileResponse:
        d = Path(get_settings().downloads_dir).resolve()
        latest = _latest_mcp_wheel(d)
        if not latest:
            raise HTTPException(status_code=404, detail="no MCP package available on this server")
        return FileResponse(latest.resolve(), filename=latest.name, media_type="application/octet-stream")

    # ── Token management (protected) ─────────────────────────────────────────

    @router.get("/tokens", tags=["Tokens"], summary="List tokens")
    async def list_tokens() -> list[dict]:
        from memory_orchestrator_server.models import ApiToken

        async with maker() as s:
            result = await s.execute(select(ApiToken).where(ApiToken.revoked_at.is_(None)).order_by(ApiToken.created_at))
            rows = result.scalars().all()
        return [
            {
                "id": str(t.id),
                "name": t.name,
                "kind": t.kind,
                "enabled": t.enabled,
                "project_id": str(t.project_id) if t.project_id else None,
                "created_at": isoformat_utc(t.created_at),
                "last_used_at": isoformat_utc(t.last_used_at) if t.last_used_at else None,
                "revealable": bool(t.token_encrypted),
            }
            for t in rows
        ]

    @router.post("/tokens", status_code=201, tags=["Tokens"], summary="Create token")
    async def create_token(body: TokenCreate = Body(...)) -> dict:
        from memory_orchestrator_server.auth_tokens import TOKEN_KIND_PROJECT
        from memory_orchestrator_server.models import ApiToken

        if body.kind not in ("ui_admin", TOKEN_KIND_PROJECT):
            raise HTTPException(status_code=422, detail="kind must be ui_admin or project_token")
        if body.kind == TOKEN_KIND_PROJECT and not body.project_id:
            raise HTTPException(status_code=422, detail="project_id required for project_token")

        raw, token_hash, token_encrypted = _new_token_pair()
        async with maker() as s:
            t = ApiToken(
                name=body.name,
                kind=body.kind,
                token_hash=token_hash,
                token_encrypted=token_encrypted,
                project_id=body.project_id,
            )
            s.add(t)
            await s.commit()
            await s.refresh(t)
        return {
            "id": str(t.id),
            "name": t.name,
            "kind": t.kind,
            "token": raw,
            "project_id": str(t.project_id) if t.project_id else None,
            "created_at": isoformat_utc(t.created_at),
        }

    @router.post("/tokens/{token_id}/reset", status_code=200, tags=["Tokens"], summary="Reset token value")
    async def reset_token(
        token_id: uuid.UUID,
        authorization: str | None = Header(default=None),
        mo_ui_session: str | None = Cookie(default=None),
    ) -> JSONResponse:
        from memory_orchestrator_server.auth_tokens import bearer_token, hash_token
        from memory_orchestrator_server.models import ApiToken

        raw, token_hash, token_encrypted = _new_token_pair()
        current_hash = hash_token(bearer_token(authorization) or (mo_ui_session or ""))
        refresh_session = False
        async with maker() as s:
            tok = await s.get(ApiToken, token_id)
            if not tok or tok.revoked_at is not None:
                raise HTTPException(status_code=404, detail="not found")
            refresh_session = tok.kind == TOKEN_KIND_UI and tok.token_hash == current_hash
            tok.token_hash = token_hash
            tok.token_encrypted = token_encrypted
            await s.commit()
        response = JSONResponse(content={"id": str(token_id), "token": raw, "action": "rotated"})
        if refresh_session:
            response.set_cookie(
                key="mo_ui_session",
                value=raw,
                httponly=True,
                samesite="strict",
                path="/",
                max_age=UI_SESSION_TTL,
            )
        return response

    @router.post("/tokens/{token_id}/reveal", status_code=200, tags=["Tokens"], summary="Reveal token value")
    async def reveal_token(token_id: uuid.UUID) -> dict:
        from memory_orchestrator_server.auth_tokens import decrypt_token
        from memory_orchestrator_server.models import ApiToken

        async with maker() as s:
            tok = await s.get(ApiToken, token_id)
            if not tok or tok.revoked_at is not None:
                raise HTTPException(status_code=404, detail="not found")
            raw = decrypt_token(tok.token_encrypted)
            if raw is None:
                raise HTTPException(
                    status_code=409,
                    detail="token cannot be revealed (created before encryption was enabled, or key unavailable)",
                )
        return {"id": str(token_id), "token": raw}

    @router.patch("/tokens/{token_id}", status_code=200, tags=["Tokens"], summary="Enable/disable token")
    async def patch_token(token_id: uuid.UUID, body: TokenPatch = Body(...)) -> dict:
        from memory_orchestrator_server.models import ApiToken

        async with maker() as s:
            tok = await s.get(ApiToken, token_id)
            if not tok or tok.revoked_at is not None:
                raise HTTPException(status_code=404, detail="not found")
            if body.enabled is not None:
                tok.enabled = body.enabled
            if body.name is not None:
                tok.name = body.name
            await s.commit()
        return {"ok": True}

    @router.delete("/tokens/{token_id}", status_code=200, tags=["Tokens"], summary="Revoke token")
    async def revoke_token(token_id: uuid.UUID) -> dict:
        from memory_orchestrator_server.models import ApiToken

        async with maker() as s:
            tok = await s.get(ApiToken, token_id)
            if not tok or tok.revoked_at is not None:
                raise HTTPException(status_code=404, detail="not found")
            tok.revoked_at = utc_now()
            await s.commit()
        return {"ok": True}

    @router.get("/timezone", tags=["System"], summary="Server timezone")
    async def timezone() -> dict:
        import datetime

        tz = datetime.datetime.now().astimezone().tzname()
        offset = datetime.datetime.now().astimezone().utcoffset()
        total_seconds = int(offset.total_seconds())
        hours, remainder = divmod(abs(total_seconds), 3600)
        minutes = remainder // 60
        sign = "+" if total_seconds >= 0 else "-"
        iana = str(datetime.datetime.now().astimezone().tzinfo)
        return {"name": tz, "iana": iana, "offset_minutes": total_seconds // 60, "label": f"UTC{sign}{hours:02d}:{minutes:02d}"}

    def _project_dict(p: Project) -> dict:
        return {
            "id": str(p.id),
            "slug": p.slug,
            "display_name": p.display_name,
            "memory_count": p.memory_count,
            "root_paths": list(p.root_paths) if p.root_paths else [],
            "first_seen_at": isoformat_utc(p.first_seen_at) if p.first_seen_at else None,
            "last_active_at": isoformat_utc(p.last_active_at) if p.last_active_at else None,
        }

    @router.get("/projects", tags=["Projects"], summary="List projects")
    async def projects(hide_empty: bool = False) -> list[dict]:
        async with maker() as s:
            stmt = select(Project).order_by(Project.memory_count.desc())
            if hide_empty:
                stmt = stmt.where(Project.memory_count > 0)
            result = await s.execute(stmt)
            return [_project_dict(p) for p in result.scalars().all()]

    @router.get("/projects/{project_id}", tags=["Projects"], summary="Get project")
    async def get_project(project_id: uuid.UUID) -> dict:
        async with maker() as s:
            p = await s.get(Project, project_id)
            if not p:
                raise HTTPException(status_code=404, detail="project not found")
            return _project_dict(p)

    @router.get("/downloads", tags=["Downloads"], summary="List downloadable client artifacts")
    async def list_downloads() -> list[dict]:
        d = Path(get_settings().downloads_dir)
        if not d.is_dir():
            return []
        files = []
        for p in sorted(d.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                files.append({"name": p.name, "size": p.stat().st_size})
        return files

    @router.get("/downloads/{filename}", tags=["Downloads"], summary="Download a client artifact")
    async def download_file(filename: str) -> FileResponse:
        d = Path(get_settings().downloads_dir).resolve()
        target = (d / filename).resolve()
        # Path-traversal guard: the resolved target must stay inside downloads_dir.
        if d not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(target, filename=target.name, media_type="application/octet-stream")

    @router.get("/stats", tags=["System"], summary="Memory stats")
    async def stats(project_slug: str | None = None) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            stmt = select(Memory.type, func.count()).where(Memory.superseded_by.is_(None))
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                if pid:
                    stmt = stmt.where(Memory.project_id == pid)
            stmt = stmt.group_by(Memory.type)
            result = await s.execute(stmt)
            by_type = {row[0]: row[1] for row in result.all()}
            return {"total": sum(by_type.values()), "by_type": by_type}

    @router.get("/recall-test", tags=["Memories"], summary="Recall test (semantic search dry-run)")
    async def recall_test(
        query: str,
        project_slug: str | None = None,
        type: str | None = None,
        top_k: int | None = None,
    ) -> dict:
        """Simulate the MCP ``search_memory`` recall path for a query, without side
        effects. Delegates to the same ``mcp_core.search_memories`` the live tool
        uses (identical scope resolution + vector + hybrid scoring), but passes
        ``record_hits=False`` so testing does not bump hit counts. Returns ranked
        hits with score + cosine similarity so recall quality can be inspected from
        the UI. ``top_k`` defaults to the ``search_top_k`` setting to match the live
        tool; ``project_slug="all"`` searches every project."""
        from memory_orchestrator_server.mcp_core import search_memories

        q = (query or "").strip()
        if not q:
            raise HTTPException(status_code=422, detail="query required")
        if top_k is not None:
            top_k = max(1, min(50, top_k))
        types = [type] if type else None
        async with maker() as s:
            hits = await search_memories(
                session=s,
                query=q,
                scope_slug=project_slug,
                types=types,
                top_k=top_k,
                record_hits=False,
            )
            return {
                "query": q,
                "project_slug": project_slug,
                "top_k": top_k,
                "hits": [
                    {
                        "id": str(h.memory.id),
                        "type": h.memory.type,
                        "name": h.memory.name,
                        "description": h.memory.description,
                        "content": h.memory.content,
                        "importance": h.memory.importance,
                        "hit_count": h.memory.hit_count,
                        "source_client": h.memory.source_client,
                        "project_id": str(h.memory.project_id),
                        "score": round(h.score, 4),
                        "cosine_sim": round(h.cosine_sim, 4),
                    }
                    for h in hits
                ],
            }

    @router.get("/memories", tags=["Memories"], summary="List / search memories")
    async def memories(project_slug: str | None = None, type: str | None = None, q: str | None = None, limit: int = 100, sort_by: str = "time", sort_desc: bool = True) -> list[dict]:
        async with maker() as s:
            repo = MemoryRepository(s)
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                mems = await repo.list(project_ids=[pid] if pid else [], type=type, q=q, limit=limit, sort_by=sort_by, sort_desc=sort_desc)
            else:
                mems = await repo.list(type=type, q=q, limit=limit, sort_by=sort_by, sort_desc=sort_desc)
            result = []
            for m in mems:
                d = {
                    "id": str(m.id),
                    "type": m.type,
                    "name": m.name,
                    "description": m.description,
                    "content": m.content,
                    "importance": m.importance,
                    "hit_count": m.hit_count,
                    "source_client": m.source_client,
                    "last_hit_at": isoformat_utc(m.last_hit_at) if m.last_hit_at else None,
                    "project_id": str(m.project_id),
                    "updated_at": isoformat_utc(m.updated_at),
                }
                if m.why:
                    d["why"] = m.why
                if m.how_to_apply:
                    d["how_to_apply"] = m.how_to_apply
                result.append(d)
            return result

    @router.post("/memories", status_code=201, tags=["Memories"], summary="Create memory")
    async def create_memory(body: MemoryCreate = Body(...)) -> dict:
        from memory_orchestrator_server.embedder import embed_one

        if body.type not in ("user", "feedback", "project", "reference"):
            raise HTTPException(status_code=422, detail=f"invalid type: {body.type}")
        async with maker() as s:
            repo = MemoryRepository(s)
            if not body.project_id:
                raise HTTPException(status_code=422, detail="project_id required")
            pid = await repo._resolve_project_ref(body.project_id)
            if not pid:
                raise HTTPException(status_code=404, detail=f"project not found: {body.project_id}")
            embedding = await embed_one(body.content)
            m = await repo.save(
                type=body.type,
                name=body.name,
                description=body.description,
                content=body.content,
                why=body.why or None,
                how_to_apply=body.how_to_apply or None,
                importance=max(1, min(5, body.importance)),
                project_id=pid,
                source="ui",
                embedding=embedding,
                source_client=body.source_client if body.source_client in {"claude", "codex"} else "claude",
            )
            await s.commit()
        return {"id": str(m.id), "action": "created"}

    @router.get("/memories/{memory_id}", tags=["Memories"], summary="Get memory")
    async def get_memory(memory_id: uuid.UUID) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            m = await repo.get(memory_id)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            return {
                "id": str(m.id),
                "type": m.type,
                "name": m.name,
                "description": m.description,
                "content": m.content,
                "why": m.why,
                "how_to_apply": m.how_to_apply,
                "importance": m.importance,
                "hit_count": m.hit_count,
                "source_client": m.source_client,
                "last_hit_at": isoformat_utc(m.last_hit_at) if m.last_hit_at else None,
                "project_id": str(m.project_id),
                "created_at": isoformat_utc(m.created_at),
                "updated_at": isoformat_utc(m.updated_at),
            }

    @router.delete("/memories/{memory_id}", status_code=204, tags=["Memories"], summary="Soft-delete memory")
    async def delete_memory(memory_id: uuid.UUID, hard: bool = False) -> None:
        async with maker() as s:
            repo = MemoryRepository(s)
            m = await repo.get(memory_id, include_superseded=True)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            await repo.delete(memory_id, hard=hard)
            await s.commit()

    @router.patch("/memories/{memory_id}", status_code=200, tags=["Memories"], summary="Update memory")
    async def patch_memory(memory_id: uuid.UUID, body: MemoryPatch = Body(...)) -> dict:
        from memory_orchestrator_server.embedder import embed_one

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            return {"saved": 0}
        async with maker() as s:
            m = await s.get(Memory, memory_id)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            for k, v in updates.items():
                setattr(m, k, v)
            m.updated_at = utc_now()
            if "content" in updates:
                m.embedding = await embed_one(updates["content"])
            if "importance" in updates:
                m.importance = max(1, min(5, updates["importance"]))
            await s.commit()
        return {"saved": len(updates)}

    @router.post("/memories/{memory_id}/clone", status_code=201, tags=["Memories"], summary="Clone memory to project")
    async def clone_memory(memory_id: uuid.UUID, project_slug: str) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            src = await repo.get(memory_id)
            if not src:
                raise HTTPException(status_code=404, detail="not found")
            target_uuid = await repo.slug_to_id(project_slug)
            if not target_uuid:
                raise HTTPException(status_code=404, detail=f"project not found: {project_slug}")
            new_m = await repo.save(
                type=src.type,
                name=src.name,
                description=src.description,
                content=src.content,
                why=src.why,
                how_to_apply=src.how_to_apply,
                importance=src.importance,
                project_id=target_uuid,
                source="ui",
                source_client=src.source_client or "claude",
                embedding=src.embedding,
            )
            await s.commit()
        return {"id": str(new_m.id), "action": "cloned"}

    @router.patch("/memories/{memory_id}/move", status_code=200, tags=["Memories"], summary="Move memory to project")
    async def move_memory(memory_id: uuid.UUID, project_slug: str) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            m = await repo.get(memory_id)
            if not m:
                raise HTTPException(status_code=404, detail="not found")
            target_uuid = await repo.slug_to_id(project_slug)
            if not target_uuid:
                raise HTTPException(status_code=404, detail=f"project not found: {project_slug}")
            old_uuid = m.project_id
            await s.execute(sa_update(Memory).where(Memory.id == memory_id).values(project_id=target_uuid))
            if old_uuid != target_uuid:
                await s.execute(_sync_project_count(old_uuid))
                await s.execute(_sync_project_count(target_uuid))
            await s.commit()
        return {"moved": True, "project_slug": project_slug}

    @router.get("/settings", tags=["Settings"], summary="Get settings")
    async def get_settings_endpoint() -> dict:
        s = get_settings()
        defaults = {
            **SETTINGS_SEED,
            "extraction_base_url": s.extraction_base_url,
            "extraction_model": s.extraction_model,
            "extraction_api_key": s.extraction_api_key,
            "embed_model": s.embed_model,
            "embed_dim": str(s.embed_dim),
        }
        async with maker() as session:
            repo = MemoryRepository(session)
            overrides = await repo.get_settings()
        merged = {**defaults, **{k: v for k, v in overrides.items() if k in SETTINGS_KEYS}}
        merged["extraction_api_key"] = "***" if merged.get("extraction_api_key") else ""
        return merged

    @router.patch("/settings", status_code=200, tags=["Settings"], summary="Update settings")
    async def patch_settings(body: SettingsPatch = Body(...)) -> dict:
        updates = {k: v for k, v in body.model_dump().items() if v is not None and v != "***"}
        if not updates:
            return {"saved": 0}
        async with maker() as session:
            repo = MemoryRepository(session)
            await repo.set_settings(updates)
            await session.commit()
        return {"saved": len(updates)}

    @router.post("/memories/batch-delete", status_code=200, tags=["Memories"], summary="Batch soft-delete")
    async def batch_delete(body: BatchDeleteBody = Body(...)) -> dict:
        deleted = 0
        async with maker() as s:
            repo = MemoryRepository(s)
            for mid in body.ids:
                m = await repo.get(mid, include_superseded=True)
                if m:
                    await repo.delete(mid, hard=False)
                    deleted += 1
            await s.commit()
        return {"deleted": deleted}

    @router.post("/memories/batch-move", status_code=200, tags=["Memories"], summary="Batch move")
    async def batch_move(body: BatchMoveBody = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            target_uuid = await repo.slug_to_id(body.project_slug)
            if not target_uuid:
                raise HTTPException(status_code=404, detail=f"project not found: {body.project_slug}")
            affected: set = set()
            moved = 0
            for mid in body.ids:
                m = await repo.get(mid)
                if not m:
                    continue
                affected.add(m.project_id)
                await s.execute(sa_update(Memory).where(Memory.id == mid).values(project_id=target_uuid))
                moved += 1
            affected.add(target_uuid)
            for pid in affected:
                await s.execute(_sync_project_count(pid))
            await s.commit()
        return {"moved": moved, "project_slug": body.project_slug}

    @router.get("/export", tags=["Memories"], summary="Export / backup")
    async def export_memories(project_slug: str | None = None, type: str | None = None, q: str | None = None) -> list[dict]:
        async with maker() as s:
            repo = MemoryRepository(s)
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                mems = await repo.list(project_ids=[pid] if pid else [], type=type, q=q, limit=10000, sort_by="time", sort_desc=True)
            else:
                mems = await repo.list(type=type, q=q, limit=10000, sort_by="time", sort_desc=True)
            proj_result = await s.execute(select(Project))
            slug_map = {p.id: p.slug for p in proj_result.scalars().all()}
            result = []
            for m in mems:
                d = {
                    "type": m.type,
                    "name": m.name,
                    "description": m.description,
                    "content": m.content,
                    "importance": m.importance,
                    "source_client": m.source_client,
                    "project_slug": slug_map.get(m.project_id, "*"),
                }
                if m.why:
                    d["why"] = m.why
                if m.how_to_apply:
                    d["how_to_apply"] = m.how_to_apply
                result.append(d)
            return result

    @router.get("/models", tags=["Settings"], summary="Discover available models")
    async def list_models(base_url: str, x_api_key: str | None = Header(default=None)) -> list[str]:
        api_key = x_api_key or ""
        if not api_key:
            async with maker() as s:
                repo = MemoryRepository(s)
                cfg = await repo.get_settings()
                api_key = cfg.get("extraction_api_key", "") or get_settings().extraction_api_key
        url = base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                ct = r.headers.get("content-type", "")
                if "json" not in ct:
                    raise HTTPException(status_code=502, detail=f"Non-JSON response from {url} (content-type: {ct}). Check base_url — it should include /v1 (e.g. https://api.example.com/v1)")
                data = r.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
        return sorted(models)

    @router.get("/duplicates", tags=["Memories"], summary="Scan duplicates")
    async def find_duplicates(
        threshold: float | None = None,
        project_slug: str | None = None,
        type: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        from sqlalchemy import text

        async with maker() as s:
            repo = MemoryRepository(s)
            cfg = await repo.get_settings()
            effective_threshold = threshold
            if effective_threshold is None:
                effective_threshold = float(cfg.get("dup_threshold") or 0.92)
            params: dict = {"threshold": effective_threshold, "limit": limit}
            filters = []
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                if not pid:
                    return []
                filters.append("m1.project_id = :project_id AND m2.project_id = :project_id")
                params["project_id"] = pid
            if type:
                filters.append("m1.type = :type AND m2.type = :type")
                params["type"] = type
            where_extra = f" AND {' AND '.join(filters)}" if filters else ""
            result = await s.execute(
                text(f"""
                SELECT
                    m1.id AS id1, m1.type AS type1, m1.name AS name1,
                    m1.description AS desc1, m1.content AS content1, m1.project_id AS pid1,
                    m2.id AS id2, m2.type AS type2, m2.name AS name2,
                    m2.description AS desc2, m2.content AS content2, m2.project_id AS pid2,
                    1 - (m1.embedding <=> m2.embedding) AS similarity
                FROM memories m1
                JOIN memories m2 ON m1.id < m2.id AND m1.project_id = m2.project_id
                WHERE m1.superseded_by IS NULL
                  AND m2.superseded_by IS NULL
                  AND m1.embedding IS NOT NULL
                  AND m2.embedding IS NOT NULL
                  {where_extra}
                  AND 1 - (m1.embedding <=> m2.embedding) >= :threshold
                ORDER BY similarity DESC
                LIMIT :limit
            """),
                params,
            )
            rows = result.fetchall()
            proj_result = await s.execute(select(Project))
            slug_map = {p.id: p.slug for p in proj_result.scalars().all()}
        pairs = []
        for row in rows:
            pairs.append(
                {
                    "id1": str(row.id1),
                    "type1": row.type1,
                    "name1": row.name1,
                    "description1": row.desc1,
                    "content1": row.content1,
                    "project_slug1": slug_map.get(row.pid1, "*"),
                    "id2": str(row.id2),
                    "type2": row.type2,
                    "name2": row.name2,
                    "description2": row.desc2,
                    "content2": row.content2,
                    "project_slug2": slug_map.get(row.pid2, "*"),
                    "similarity": round(float(row.similarity), 3),
                }
            )
        return pairs

    @router.get("/conflicts", tags=["Memories"], summary="Scan conflicts")
    async def find_conflicts(
        min_sim: float = 0.50,
        project_slug: str | None = None,
        type: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        from sqlalchemy import text

        async with maker() as s:
            repo = MemoryRepository(s)
            cfg = await repo.get_settings()
            dup_threshold = float(cfg.get("dup_threshold") or 0.92)
            max_sim = dup_threshold - 0.01
            params: dict = {"min_sim": min_sim, "max_sim": max_sim, "limit": limit}
            filters = []
            if project_slug:
                pid = await repo.slug_to_id(project_slug)
                if not pid:
                    return []
                filters.append("m1.project_id = :project_id AND m2.project_id = :project_id")
                params["project_id"] = pid
            if type:
                filters.append("m1.type = :type AND m2.type = :type")
                params["type"] = type
            where_extra = f" AND {' AND '.join(filters)}" if filters else ""
            result = await s.execute(
                text(f"""
                SELECT
                    m1.id AS id1, m1.type AS type1, m1.name AS name1,
                    m1.description AS desc1, m1.content AS content1, m1.project_id AS pid1,
                    m2.id AS id2, m2.type AS type2, m2.name AS name2,
                    m2.description AS desc2, m2.content AS content2, m2.project_id AS pid2,
                    1 - (m1.embedding <=> m2.embedding) AS similarity
                FROM memories m1
                JOIN memories m2 ON m1.id < m2.id AND m1.project_id = m2.project_id
                WHERE m1.superseded_by IS NULL
                  AND m2.superseded_by IS NULL
                  AND m1.embedding IS NOT NULL
                  AND m2.embedding IS NOT NULL
                  {where_extra}
                  AND 1 - (m1.embedding <=> m2.embedding) >= :min_sim
                  AND 1 - (m1.embedding <=> m2.embedding) < :max_sim
                ORDER BY similarity DESC
                LIMIT :limit
            """),
                params,
            )
            rows = result.fetchall()
            proj_result = await s.execute(select(Project))
            slug_map = {p.id: p.slug for p in proj_result.scalars().all()}
        pairs = []
        for row in rows:
            pairs.append(
                {
                    "id1": str(row.id1),
                    "type1": row.type1,
                    "name1": row.name1,
                    "description1": row.desc1,
                    "content1": row.content1,
                    "project_slug1": slug_map.get(row.pid1, "*"),
                    "id2": str(row.id2),
                    "type2": row.type2,
                    "name2": row.name2,
                    "description2": row.desc2,
                    "content2": row.content2,
                    "project_slug2": slug_map.get(row.pid2, "*"),
                    "similarity": round(float(row.similarity), 3),
                }
            )
        return pairs

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
        from memory_orchestrator_server.auth_tokens import TOKEN_KIND_PROJECT, encrypt_token
        from memory_orchestrator_server.models import ApiToken
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

            existing = (
                await s.execute(
                    select(ApiToken).where(
                        ApiToken.name == name,
                        ApiToken.kind == TOKEN_KIND_PROJECT,
                        ApiToken.project_id == project_uuid,
                        ApiToken.revoked_at.is_(None),
                        ApiToken.enabled.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if existing is not None and not force:
                return {"token": "", "name": name, "project_slug": project_slug, "already_registered": True}

            raw = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw.encode()).hexdigest()
            token_encrypted = encrypt_token(raw)

            if existing is not None:
                existing.token_hash = token_hash
                existing.token_encrypted = token_encrypted
            else:
                s.add(ApiToken(name=name, kind=TOKEN_KIND_PROJECT, token_hash=token_hash, token_encrypted=token_encrypted, project_id=project_uuid))
            await s.commit()

        return {"token": raw, "name": name, "project_slug": project_slug, "already_registered": False}

    # ── Projects ─────────────────────────────────────────────────────────────

    @router.post("/projects", status_code=201, tags=["Projects"], summary="Create project")
    async def create_project(body: ProjectCreate = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            project_id = await repo.create_project_with_skeleton(body.slug, body.display_name)
            await s.commit()
            proj = await s.get(Project, project_id)
        return {
            "id": str(proj.id),
            "slug": proj.slug,
            "display_name": proj.display_name,
            "memory_count": proj.memory_count,
        }

    @router.patch("/projects/{project_id}", status_code=200, tags=["Projects"], summary="Update project")
    async def update_project(project_id: uuid.UUID, body: ProjectPatch = Body(...)) -> dict:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="display_name required")
        async with maker() as s:
            proj = await s.get(Project, project_id)
            if not proj:
                raise HTTPException(status_code=404, detail="project not found")
            proj.display_name = name
            await s.commit()
        return _project_dict(proj)

    @router.delete("/projects/{project_id}", status_code=204, tags=["Projects"], summary="Delete project")
    async def delete_project(project_id: uuid.UUID) -> None:
        from memory_orchestrator_server.models import Session
        from sqlalchemy import delete as sa_delete

        async with maker() as s:
            proj = await s.get(Project, project_id)
            if not proj:
                raise HTTPException(status_code=404, detail="project not found")
            # Remove child rows that lack DB-level cascade before deleting the project.
            # (skeleton nodes cascade via ondelete=CASCADE; sessions/memories do not.)
            await s.execute(sa_delete(Session).where(Session.project_id == project_id))
            await s.execute(sa_delete(Memory).where(Memory.project_id == project_id))
            await s.delete(proj)
            await s.commit()

    # ── Skeleton nodes ────────────────────────────────────────────────────────

    @router.get("/projects/{project_id}/skeleton", tags=["Skeleton"], summary="Get project skeleton tree")
    async def get_skeleton(project_id: uuid.UUID) -> list:
        async with maker() as s:
            repo = MemoryRepository(s)
            return await repo.get_skeleton_tree(project_id)

    @router.patch("/skeleton-nodes/{node_id}", status_code=200, tags=["Skeleton"], summary="Update node")
    async def patch_skeleton_node(node_id: uuid.UUID, body: SkeletonNodePatch = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            ok = await repo.patch_skeleton_node(
                node_id,
                name=body.name,
                description=body.description,
                prompt_hint=body.prompt_hint,
                tags=body.tags,
            )
            if not ok:
                raise HTTPException(status_code=404, detail="node not found")
            await s.commit()
        return {"ok": True}

    @router.post("/skeleton-nodes", status_code=201, tags=["Skeleton"], summary="Create node")
    async def create_skeleton_node(body: SkeletonNodeCreate = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            node = await repo.create_skeleton_node(
                project_id=body.project_id,
                name=body.name,
                parent_id=body.parent_id,
                description=body.description or "",
                prompt_hint=body.prompt_hint or "",
                tags=body.tags or [],
            )
            await s.commit()
        return node

    @router.post("/skeleton-nodes/reorder", status_code=200, tags=["Skeleton"], summary="Reorder sibling nodes")
    async def reorder_skeleton_nodes(body: SkeletonNodeReorder = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            await repo.reorder_skeleton_nodes(body.project_id, body.ordered_ids)
            await s.commit()
        return {"ok": True}

    @router.delete("/skeleton-nodes/{node_id}", status_code=204, tags=["Skeleton"], summary="Delete node")
    async def delete_skeleton_node(node_id: uuid.UUID) -> None:
        async with maker() as s:
            repo = MemoryRepository(s)
            ok = await repo.delete_skeleton_node(node_id)
            await s.commit()
        if not ok:
            raise HTTPException(status_code=409, detail="cannot delete builtin node or node not found")

    @router.post("/skeleton-nodes/{node_id}/memories", status_code=201, tags=["Skeleton"], summary="Link memory to node")
    async def add_memory_to_node(node_id: uuid.UUID, body: NodeMemoryAdd = Body(...)) -> dict:
        async with maker() as s:
            repo = MemoryRepository(s)
            await repo.add_memory_to_node(node_id, body.memory_id)
            await s.commit()
        return {"ok": True}

    @router.get("/skeleton-nodes/{node_id}/memories", tags=["Skeleton"], summary="List node memories (subtree)")
    async def get_node_memories(node_id: uuid.UUID) -> list:
        async with maker() as s:
            repo = MemoryRepository(s)
            mems = await repo.get_node_memories(node_id)
        result = []
        for m in mems:
            d = {
                "id": str(m.id),
                "type": m.type,
                "name": m.name,
                "description": m.description,
                "importance": m.importance,
                "hit_count": m.hit_count,
                "source_client": m.source_client,
                "last_hit_at": isoformat_utc(m.last_hit_at) if m.last_hit_at else None,
                "project_id": str(m.project_id),
                "created_at": isoformat_utc(m.created_at),
            }
            if m.why:
                d["why"] = m.why
            if m.how_to_apply:
                d["how_to_apply"] = m.how_to_apply
            result.append(d)
        return result

    @router.get("/memories/{memory_id}/nodes", tags=["Skeleton"], summary="List nodes linked to a memory")
    async def get_memory_nodes(memory_id: uuid.UUID) -> list:
        async with maker() as s:
            repo = MemoryRepository(s)
            nodes = await repo.get_memory_nodes(memory_id)
            # Build a name→path map per project so we can show the breadcrumb.
            by_id: dict[uuid.UUID, ProjectSkeletonNode] = {}
            for n in nodes:
                if n.project_id not in {x.project_id for x in by_id.values()}:
                    for fn in await repo.get_skeleton_flat(n.project_id):
                        by_id[fn.id] = fn

        def path_of(node: ProjectSkeletonNode) -> list[str]:
            names: list[str] = []
            cur: ProjectSkeletonNode | None = node
            seen: set[uuid.UUID] = set()
            while cur is not None and cur.id not in seen:
                seen.add(cur.id)
                names.append(cur.name)
                cur = by_id.get(cur.parent_id) if cur.parent_id else None
            return list(reversed(names))

        return [
            {
                "id": str(n.id),
                "name": n.name,
                "parent_id": str(n.parent_id) if n.parent_id else None,
                "project_id": str(n.project_id),
                "path": path_of(n),
            }
            for n in nodes
        ]

    @router.delete("/skeleton-nodes/{node_id}/memories/{memory_id}", status_code=204, tags=["Skeleton"], summary="Unlink memory from node")
    async def remove_memory_from_node(node_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        async with maker() as s:
            repo = MemoryRepository(s)
            await repo.remove_memory_from_node(node_id, memory_id)
            await s.commit()

    outer.include_router(public)
    outer.include_router(router)
    return outer
