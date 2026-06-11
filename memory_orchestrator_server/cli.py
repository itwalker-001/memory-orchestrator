from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
import click

from memory_orchestrator_server.config import get_settings


def _preflight_database() -> None:
    from memory_orchestrator_server.db_check import check_database_dsn, format_database_startup_error

    settings = get_settings()
    try:
        database_created = asyncio.run(check_database_dsn(settings.db_dsn))
    except Exception as exc:
        click.echo(format_database_startup_error(settings.db_dsn, exc), err=True)
        sys.exit(1)
    if database_created:
        click.echo("Database did not exist and was created automatically; continuing with the target database.")


@click.group()
def main() -> None:
    """Memory Orchestrator server CLI."""


@main.command(name="serve-http")
def serve_http() -> None:
    """Run HTTP API."""
    import logging.config
    import uvicorn
    from memory_orchestrator_server.http_app import create_app

    _preflight_database()
    settings = get_settings()

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(exist_ok=True)
    log_file = str(log_dir / "http.log")

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "default"},
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file,
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
                "formatter": "default",
            },
        },
        "root": {"handlers": ["console", "file"], "level": settings.log_level},
        "loggers": {
            "uvicorn": {"handlers": ["console", "file"], "level": settings.log_level, "propagate": False},
            "uvicorn.access": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
            "python_multipart": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
            "multipart": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        },
    })

    uvicorn.run(
        create_app(),
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
        log_config=None,
    )


@main.command()
def doctor() -> None:
    """Check DB connectivity and HTTP service health."""
    import urllib.request
    ok = True
    settings = get_settings()
    import re
    safe_dsn = re.sub(r"://[^@]+@", "://*:*@", settings.db_dsn)
    click.echo(f"config: db_dsn={safe_dsn}")
    click.echo(f"config: http_port={settings.http_port}")
    try:
        with urllib.request.urlopen(f"http://localhost:{settings.http_port}/healthz", timeout=1) as r:
            data = json.loads(r.read())
            click.echo(f"healthz: {data}")
    except Exception as e:
        click.echo(f"healthz: FAIL ({e})")
        ok = False
    sys.exit(0 if ok else 1)


@main.command(name="migrate-embeddings")
@click.option("--batch-size", default=32, show_default=True)
def migrate_embeddings(batch_size: int) -> None:
    """Re-embed all memories using the current embed_model."""
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from memory_orchestrator_server.embedder import embed_batch
    from memory_orchestrator_server.models import Memory, SystemSetting
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    settings = get_settings()

    async def _run() -> None:
        engine = create_async_engine(settings.db_dsn)
        maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with maker() as session:
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == "embed_migration_offset")
            )
            row = result.scalar_one_or_none()
            offset = int(row.value) if row else 0

            total_result = await session.execute(
                select(Memory).where(Memory.superseded_by.is_(None)).order_by(Memory.id)
            )
            all_mems = list(total_result.scalars().all())
            total = len(all_mems)
            click.echo(f"Total memories: {total}, starting from offset {offset}")

            processed = 0
            for i in range(offset, total, batch_size):
                batch = all_mems[i : i + batch_size]
                texts = [f"{m.name} {m.description} {m.content or ''}" for m in batch]
                vecs = await embed_batch(texts)
                for m, vec in zip(batch, vecs):
                    await session.execute(
                        sa_update(Memory).where(Memory.id == m.id).values(embedding=vec)
                    )
                processed += len(batch)
                new_offset = i + len(batch)
                await session.execute(
                    pg_insert(SystemSetting)
                    .values(key="embed_migration_offset", value=str(new_offset), updated_at=__import__("datetime").datetime.utcnow())
                    .on_conflict_do_update(
                        index_elements=["key"],
                        set_={"value": str(new_offset), "updated_at": __import__("datetime").datetime.utcnow()},
                    )
                )
                await session.commit()
                click.echo(f"  [{processed}/{total}] re-embedded")

            await session.execute(
                pg_insert(SystemSetting)
                .values(key="embed_migration_offset", value="0", updated_at=__import__("datetime").datetime.utcnow())
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={"value": "0", "updated_at": __import__("datetime").datetime.utcnow()},
                )
            )
            await session.commit()
        await engine.dispose()
        click.echo("Migration complete.")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# token subcommands
# ---------------------------------------------------------------------------

@main.group()
def token() -> None:
    """Manage API tokens (ui_admin / mcp_client)."""


@token.command(name="create")
@click.option("--kind", type=click.Choice(["ui_admin", "mcp_client"]), required=True)
@click.option("--name", required=True, help="Human-readable label for this token.")
def token_create(kind: str, name: str) -> None:
    """Create a new API token and print it (shown only once)."""
    import hashlib
    import secrets
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from memory_orchestrator_server.models import ApiToken
    from memory_orchestrator_server.auth_tokens import encrypt_token

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token_encrypted = encrypt_token(raw)

    action = "created"

    async def _create() -> None:
        nonlocal action
        from sqlalchemy import select
        engine = create_async_engine(get_settings().db_dsn)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            existing = (await session.execute(
                select(ApiToken).where(
                    ApiToken.name == name,
                    ApiToken.kind == kind,
                    ApiToken.revoked_at.is_(None),
                ).limit(1)
            )).scalars().first()
            if existing is not None:
                existing.token_hash = token_hash
                existing.token_encrypted = token_encrypted
                action = "rotated"
            else:
                session.add(ApiToken(name=name, kind=kind, token_hash=token_hash,
                                     token_encrypted=token_encrypted))
            await session.commit()
        await engine.dispose()

    asyncio.run(_create())
    click.echo(f"Token {action}  kind={kind}  name={name}")
    click.echo(f"Token value (save this — shown only once):")
    click.echo(f"  {raw}")


@token.command(name="list")
def token_list() -> None:
    """List all active (non-revoked) API tokens."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from memory_orchestrator_server.models import ApiToken

    async def _list() -> list[ApiToken]:
        engine = create_async_engine(get_settings().db_dsn)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            rows = (await session.execute(
                select(ApiToken).where(ApiToken.revoked_at.is_(None)).order_by(ApiToken.created_at)
            )).scalars().all()
        await engine.dispose()
        return rows

    rows = asyncio.run(_list())
    if not rows:
        click.echo("No active tokens.")
        return
    click.echo(f"{'ID':<36}  {'KIND':<12}  {'NAME'}")
    click.echo("-" * 70)
    for t in rows:
        click.echo(f"{t.id}  {t.kind:<12}  {t.name}")


@token.command(name="revoke")
@click.argument("token_id")
def token_revoke(token_id: str) -> None:
    """Revoke an API token by ID."""
    import uuid
    from datetime import datetime, timezone
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from memory_orchestrator_server.models import ApiToken

    async def _revoke() -> bool:
        engine = create_async_engine(get_settings().db_dsn)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            row = (await session.execute(
                select(ApiToken).where(ApiToken.id == uuid.UUID(token_id))
            )).scalar_one_or_none()
            if row is None:
                await engine.dispose()
                return False
            row.revoked_at = datetime.now(timezone.utc)
            await session.commit()
        await engine.dispose()
        return True

    found = asyncio.run(_revoke())
    if found:
        click.echo(f"Token {token_id} revoked.")
    else:
        click.echo(f"Token {token_id} not found.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
