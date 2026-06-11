from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import Cookie, Header, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memory_orchestrator_server.models import ApiToken
from memory_orchestrator_server.time_utils import utc_now

TOKEN_KIND_UI = "ui_admin"
TOKEN_KIND_PROJECT = "project_token"
UI_SESSION_TTL = 1800  # 30 minutes; refreshed on every authenticated request

_PKG_ROOT = Path(__file__).parent  # memory_orchestrator_server/


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── Reversible token encryption (for UI reveal/copy) ────────────────────────────
# Authentication still relies on the SHA256 hash (one-way). This stores a second,
# decryptable copy so the UI can show the original token on demand. Losing the key
# only means existing ciphertexts can't be decrypted — the tokens themselves stay
# valid because auth uses the hash.

def _persist_generated_key(key: str) -> None:
    """Append a freshly generated key to the package .env so it survives restarts."""
    env_path = _PKG_ROOT / ".env"
    try:
        line = f"MO_TOKEN_SECRET_KEY={key}\n"
        if env_path.exists():
            existing = env_path.read_text(encoding="utf-8")
            prefix = "" if existing.endswith("\n") or existing == "" else "\n"
            env_path.write_text(existing + prefix + line, encoding="utf-8")
        else:
            env_path.write_text(line, encoding="utf-8")
    except OSError:
        # Non-fatal: encryption still works this run, just not persisted.
        pass


@lru_cache(maxsize=1)
def _get_token_cipher():
    """Return a Fernet cipher, generating+persisting a key on first use if unset."""
    from cryptography.fernet import Fernet
    from memory_orchestrator_server.config import get_settings

    key = (get_settings().token_secret_key or "").strip() or os.environ.get("MO_TOKEN_SECRET_KEY", "").strip()
    if not key:
        key = Fernet.generate_key().decode("utf-8")
        _persist_generated_key(key)
        os.environ["MO_TOKEN_SECRET_KEY"] = key
    return Fernet(key.encode("utf-8"))


def encrypt_token(raw: str) -> str | None:
    """Encrypt a raw token for later reveal. Returns None if encryption is unavailable."""
    try:
        return _get_token_cipher().encrypt(raw.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def decrypt_token(blob: str | None) -> str | None:
    """Decrypt a stored ciphertext back to the raw token, or None if unavailable/invalid."""
    if not blob:
        return None
    try:
        return _get_token_cipher().decrypt(blob.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix):].strip()
    return token or None


def env_token_for_kind(kind: str) -> str | None:
    if kind == TOKEN_KIND_PROJECT:
        token = os.environ.get("MO_MCP_TOKEN")
    elif kind == TOKEN_KIND_UI:
        token = os.environ.get("MO_UI_TOKEN")
    else:
        token = None
    return (token or "").strip() or None


async def check_token_valid(session: AsyncSession, kind: str, token: str) -> bool:
    """Return True if token is valid for kind (env or DB). No side effects."""
    env = env_token_for_kind(kind)
    if env and hmac.compare_digest(token, env):
        return True
    h = hash_token(token)
    result = await session.execute(
        select(ApiToken).where(
            ApiToken.kind == kind,
            ApiToken.token_hash == h,
            ApiToken.revoked_at.is_(None),
            ApiToken.enabled.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None


async def require_token_kind(
    *,
    session: AsyncSession,
    kind: str,
    authorization: str | None,
    cookie_token: str | None = None,
) -> ApiToken | None:
    token = bearer_token(authorization) or (cookie_token or "").strip() or None
    configured_env_token = env_token_for_kind(kind)
    db_has_tokens = await _db_has_tokens(session, kind)

    if configured_env_token or db_has_tokens:
        if not token:
            raise HTTPException(status_code=401, detail="missing bearer token")
    else:
        return None

    if configured_env_token and token and hmac.compare_digest(token, configured_env_token):
        return None

    token_hash = hash_token(token or "")
    result = await session.execute(
        select(ApiToken).where(
            ApiToken.kind == kind,
            ApiToken.token_hash == token_hash,
            ApiToken.revoked_at.is_(None),
            ApiToken.enabled.is_(True),
        )
    )
    api_token = result.scalar_one_or_none()
    if not api_token:
        raise HTTPException(status_code=401, detail="invalid token")

    await session.execute(
        update(ApiToken)
        .where(ApiToken.id == api_token.id)
        .values(last_used_at=utc_now())
        .execution_options(synchronize_session=False)
    )
    return api_token


async def _db_has_tokens(session: AsyncSession, kind: str) -> bool:
    result = await session.execute(
        select(ApiToken.id).where(
            ApiToken.kind == kind,
            ApiToken.revoked_at.is_(None),
            ApiToken.enabled.is_(True),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def resolve_project_token(
    *,
    session: AsyncSession,
    authorization: str | None,
) -> tuple[ApiToken | None, uuid.UUID | None]:
    """Validate a project_token Bearer token. Returns (token_row_or_None, project_uuid) or raises 401.

    If MO_MCP_TOKEN env var matches, returns (None, None); caller must resolve project from request body.
    """
    import hmac as _hmac

    raw = bearer_token(authorization)
    if not raw:
        raise HTTPException(status_code=401, detail="missing bearer token")

    env_tok = env_token_for_kind(TOKEN_KIND_PROJECT)
    if env_tok and _hmac.compare_digest(raw, env_tok):
        return None, None

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


def auth_dependency(*, maker: async_sessionmaker, kind: str):
    if kind == TOKEN_KIND_UI:
        async def _require(
            response: Response,
            authorization: str | None = Header(default=None),
            mo_ui_session: str | None = Cookie(default=None),
        ) -> None:
            async with maker() as session:
                await require_token_kind(
                    session=session, kind=kind,
                    authorization=authorization,
                    cookie_token=mo_ui_session,
                )
                await session.commit()
            # Refresh cookie expiry on every authenticated request
            if mo_ui_session and not bearer_token(authorization):
                response.set_cookie(
                    key="mo_ui_session",
                    value=mo_ui_session,
                    httponly=True,
                    samesite="strict",
                    path="/",
                    max_age=UI_SESSION_TTL,
                )
        return _require
    else:
        async def _require(authorization: str | None = Header(default=None)) -> None:  # type: ignore[misc]
            async with maker() as session:
                await require_token_kind(session=session, kind=kind, authorization=authorization)
                await session.commit()
        return _require
