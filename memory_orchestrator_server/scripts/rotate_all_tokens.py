"""One-shot: rotate every non-revoked API token in place.

Keeps each token's id / kind / name / project_id binding; regenerates the raw
value and rewrites token_hash + token_encrypted. Prints each new raw once.
Run inside the app container so encrypt_token uses the container's Fernet key.
"""
import asyncio
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.models import ApiToken
from memory_orchestrator_server.auth_tokens import encrypt_token


async def _run() -> None:
    engine = create_async_engine(get_settings().db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    rotated = []
    async with maker() as s:
        rows = (await s.execute(
            select(ApiToken).where(ApiToken.revoked_at.is_(None)).order_by(ApiToken.created_at)
        )).scalars().all()
        for t in rows:
            raw = secrets.token_urlsafe(32)
            t.token_hash = hashlib.sha256(raw.encode()).hexdigest()
            t.token_encrypted = encrypt_token(raw)
            rotated.append((str(t.id), t.kind, t.name, str(t.project_id) if t.project_id else "-", raw))
        await s.commit()
    await engine.dispose()

    print(f"{'KIND':<14}{'NAME':<24}{'PROJECT_ID':<38}TOKEN")
    print("-" * 120)
    for _id, kind, name, pid, raw in rotated:
        print(f"{kind:<14}{name:<24}{pid:<38}{raw}")
    print(f"\nRotated {len(rotated)} tokens.")


if __name__ == "__main__":
    asyncio.run(_run())
