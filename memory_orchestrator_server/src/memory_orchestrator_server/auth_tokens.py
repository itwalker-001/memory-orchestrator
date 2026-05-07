from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memory_orchestrator_server.models import ApiToken
from memory_orchestrator_server.time_utils import utc_now

TOKEN_KIND_MCP = "mcp_client"
TOKEN_KIND_UI = "ui_admin"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix):].strip()
    return token or None


def env_token_for_kind(kind: str) -> str | None:
    if kind == TOKEN_KIND_MCP:
        token = os.environ.get("MO_MCP_TOKEN") or os.environ.get("MO_SERVER_TOKEN")
    elif kind == TOKEN_KIND_UI:
        token = os.environ.get("MO_UI_TOKEN")
    else:
        token = None
    return (token or "").strip() or None


async def require_token_kind(
    *,
    session: AsyncSession,
    kind: str,
    authorization: str | None,
) -> ApiToken | None:
    token = bearer_token(authorization)
    configured_env_token = env_token_for_kind(kind)
    db_has_tokens = await _db_has_tokens(session)

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


async def _db_has_tokens(session: AsyncSession) -> bool:
    result = await session.execute(
        select(ApiToken.id).where(ApiToken.revoked_at.is_(None)).limit(1)
    )
    return result.scalar_one_or_none() is not None


def auth_dependency(*, maker: async_sessionmaker, kind: str):
    async def _require(authorization: str | None = Header(default=None)) -> None:
        async with maker() as session:
            await require_token_kind(session=session, kind=kind, authorization=authorization)
            await session.commit()
    return _require
