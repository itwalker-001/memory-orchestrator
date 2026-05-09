from __future__ import annotations
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
import click

from memory_orchestrator_server.client_adapters import install_codex, teardown_codex
from memory_orchestrator_server.client_rules import (
    install_client_from_rule,
    load_client_rule,
    teardown_client_from_rule,
)
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


@main.command()
def serve() -> None:
    """Run HTTP API and MCP stdio server concurrently."""
    import uvicorn
    from memory_orchestrator_server.http_app import create_app
    from memory_orchestrator_server.mcp_server import run_stdio_server

    _preflight_database()
    settings = get_settings()
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=settings.http_port, log_level=settings.log_level.lower())

    async def _main() -> None:
        server = uvicorn.Server(config)
        http_task = asyncio.create_task(server.serve())
        mcp_task = asyncio.create_task(run_stdio_server())
        done, pending = await asyncio.wait({http_task, mcp_task}, return_when=asyncio.FIRST_EXCEPTION)
        for p in pending:
            p.cancel()
        for d in done:
            d.result()

    asyncio.run(_main())


@main.command(name="serve-http")
def serve_http() -> None:
    """Run only HTTP API."""
    import logging.config
    import uvicorn
    from memory_orchestrator_server.http_app import create_app

    _preflight_database()
    settings = get_settings()

    log_dir = Path(__file__).parent.parent.parent.parent / "logs"
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
        host="127.0.0.1",
        port=settings.http_port,
        log_level=settings.log_level.lower(),
        log_config=None,
    )


@main.command(name="serve-mcp")
@click.option("--client", type=click.Choice(["claude", "codex"]), default=None,
              help="Override MO_CLIENT env var.")
def serve_mcp(client: str | None) -> None:
    """Run only MCP stdio server."""
    if client:
        os.environ["MO_CLIENT"] = client
    from memory_orchestrator_server.mcp_server import run_stdio_server
    asyncio.run(run_stdio_server())


@main.command()
@click.option("--client", type=click.Choice(["claude", "codex", "all"]), default="claude")
def doctor(client: str) -> None:
    """Check DB, embedder, and client settings wiring."""
    import urllib.request
    ok = True
    settings = get_settings()
    click.echo(f"config: db_dsn={settings.db_dsn}")
    click.echo(f"config: http_port={settings.http_port}")
    try:
        with urllib.request.urlopen(f"http://localhost:{settings.http_port}/healthz", timeout=1) as r:
            data = json.loads(r.read())
            click.echo(f"healthz: {data}")
    except Exception as e:
        click.echo(f"healthz: FAIL ({e})")
        ok = False
    if client in {"claude", "all"}:
        settings_path = Path.home() / ".claude" / "settings.json"
        if settings_path.exists():
            try:
                cfg = json.loads(settings_path.read_text(encoding="utf-8"))
                mcp = cfg.get("mcpServers", {}).get("memory-orchestrator")
                hooks = cfg.get("hooks", {})
                click.echo(f"claude mcp entry: {'ok' if mcp else 'MISSING'}")
                click.echo(f"claude hooks: {sorted(hooks.keys())}")
                if not mcp:
                    ok = False
            except Exception as e:
                click.echo(f"claude settings parse: FAIL ({e})")
                ok = False
        else:
            click.echo("claude settings: NOT FOUND")
            ok = False
    if client in {"codex", "all"}:
        codex_dir = _codex_home()
        codex_cfg = codex_dir / "config.toml"
        codex_hooks = codex_dir / "hooks.json"
        if codex_cfg.exists():
            try:
                import tomllib
                cfg = tomllib.loads(codex_cfg.read_text(encoding="utf-8"))
                mcp = cfg.get("mcp_servers", {}).get("memory-orchestrator")
                features = cfg.get("features", {})
                click.echo(f"codex mcp entry: {'ok' if mcp else 'MISSING'}")
                click.echo(f"codex hooks feature: {'ok' if features.get('codex_hooks') else 'MISSING'}")
                if not mcp:
                    ok = False
            except Exception as e:
                click.echo(f"codex config parse: FAIL ({e})")
                ok = False
        else:
            click.echo("codex config: NOT FOUND")
            ok = False
        click.echo(f"codex hooks file: {'ok' if codex_hooks.exists() else 'MISSING'}")
        if not codex_hooks.exists():
            ok = False
    sys.exit(0 if ok else 1)


@main.command(name="migrate-embeddings")
@click.option("--batch-size", default=32, show_default=True)
def migrate_embeddings(batch_size: int) -> None:
    """Re-embed all memories using the current embed_model."""
    import asyncio
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
                texts = [
                    f"{m.name} {m.description} {m.content or ''}"
                    for m in batch
                ]
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


@main.command(name="setup")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
@click.option("--client", type=click.Choice(["claude", "codex", "all"]), default="claude")
def install_hooks(scope: str, client: str) -> None:
    """Wire hooks, mcp servers, and instructions into supported clients."""
    if client in {"claude", "all"}:
        _install_claude(scope)
    if client in {"codex", "all"}:
        project_dir = Path(__file__).parent.parent.parent.parent.resolve()
        result = install_codex(home=_codex_home(), project_dir=project_dir, scope=scope)
        click.echo(f"codex config: {result.config_path}")
        click.echo(f"codex hooks: {result.hooks_path}")
        click.echo(f"codex instructions: {result.agents_path}")


def _install_claude(scope: str) -> None:
    project_dir = Path(__file__).parent.parent.parent.parent.resolve()
    target_home = Path.home() / ".claude" if scope == "user" else Path.cwd() / ".claude"
    install_result = install_client_from_rule(
        rule=load_client_rule("claude"),
        target_home=target_home,
        project_dir=project_dir,
        scope=scope,
    )
    click.echo(f"wrote {install_result.config_path}")

    # Auto-create a mcp_client token and inject it so stdio MCP can authenticate.
    if install_result.config_path:
        _create_and_inject_mcp_token(install_result.config_path)
        click.echo("injected MO_MCP_TOKEN into mcpServers.memory-orchestrator.env")

    mcp_scope = "user" if scope == "user" else "project"
    server_dir = str(project_dir / "memory_orchestrator_server").replace("\\", "/")
    try:
        mcp_result = subprocess.run(
            ["claude", "mcp", "add", "--scope", mcp_scope, "memory-orchestrator",
             "--", "uv", "run", "--no-sync", "--project", server_dir,
             "mo-server", "serve-mcp", "--client", "claude"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        mcp_result = None
    if mcp_result is not None and mcp_result.returncode == 0:
        click.echo(f"mcp: {mcp_result.stdout.strip()}")
    else:
        click.echo(
            f"mcp add failed (run manually): claude mcp add --scope {mcp_scope} memory-orchestrator "
            f"-- uv run --no-sync --project {server_dir} mo-server serve-mcp --client claude"
        )
    if install_result.instructions_path:
        click.echo(f"installed skill → {install_result.instructions_path}")


@main.command(name="teardown")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
@click.option("--client", type=click.Choice(["claude", "codex", "all"]), default="claude")
def uninstall_hooks(scope: str, client: str) -> None:
    """Remove Memory Orchestrator wiring from supported clients."""
    if client in {"claude", "all"}:
        _teardown_claude(scope)
    if client in {"codex", "all"}:
        project_dir = Path(__file__).parent.parent.parent.parent.resolve()
        teardown_codex(home=_codex_home(), project_dir=project_dir, scope=scope)
        click.echo("codex cleaned")


def _teardown_claude(scope: str) -> None:
    project_dir = Path(__file__).parent.parent.parent.parent.resolve()
    target_home = Path.home() / ".claude" if scope == "user" else Path.cwd() / ".claude"
    teardown_client_from_rule(
        rule=load_client_rule("claude"),
        target_home=target_home,
        project_dir=project_dir,
        scope=scope,
    )
    click.echo(f"cleaned {target_home / 'settings.json'}")


def _create_and_inject_mcp_token(settings_path: Path) -> None:
    """Create a fresh mcp_client token in the DB and write it to settings.json.

    Token hash is one-way; we always generate a new token on each setup run so
    the plaintext is available to inject.  Previous tokens remain valid.
    """
    import hashlib
    import secrets
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from memory_orchestrator_server.models import ApiToken

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()

    async def _insert() -> None:
        engine = create_async_engine(get_settings().db_dsn)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(ApiToken(name="setup-auto", kind="mcp_client", token_hash=token_hash))
            await session.commit()
        await engine.dispose()

    try:
        asyncio.run(_insert())
    except Exception as exc:
        click.echo(f"  warning: could not create mcp_client token: {exc}", err=True)
        return

    data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    (data.setdefault("mcpServers", {})
         .setdefault("memory-orchestrator", {})
         .setdefault("env", {}))["MO_MCP_TOKEN"] = raw
    settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".codex"


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

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()

    async def _create() -> None:
        engine = create_async_engine(get_settings().db_dsn)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(ApiToken(name=name, kind=kind, token_hash=token_hash))
            await session.commit()
        await engine.dispose()

    asyncio.run(_create())
    click.echo(f"Token created  kind={kind}  name={name}")
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
