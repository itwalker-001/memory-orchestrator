from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

REQUIRED_EXTENSIONS = {"pgcrypto", "vector"}
REQUIRED_COLUMNS: Mapping[str, set[str]] = {
    "projects": {"id", "slug", "display_name"},
    "memories": {"id", "project_id", "type", "name", "embedding"},
    "sessions": {"session_id", "project_id", "status"},
    "system_settings": {"key", "value", "updated_at"},
}


class DatabaseCheckError(RuntimeError):
    """Raised when PostgreSQL is reachable but the app schema is not ready."""


class DatabaseCreateError(RuntimeError):
    """Raised when the target database is missing and cannot be created."""


def mask_dsn(dsn: str) -> str:
    try:
        url = make_url(dsn)
    except Exception:
        return dsn
    if url.password is None:
        return str(url)
    return str(url.set(password="***"))


def maintenance_dsn_for(dsn: str) -> str:
    url = make_url(dsn)
    return url.set(database="postgres").render_as_string(hide_password=False)


def format_database_startup_error(dsn: str, exc: BaseException) -> str:
    return "\n".join(
        [
            "Database startup check failed. Service was not started.",
            f"Target DSN: {mask_dsn(dsn)}",
            f"Maintenance DSN: {mask_dsn(maintenance_dsn_for(dsn))}",
            f"Error: {exc}",
            "",
            "Check:",
            "1. PostgreSQL is running, and host/port/user/password match MO_DB_DSN.",
            "2. Startup first connects to the 'postgres' maintenance database to verify/create the target database, then reconnects to the target database.",
            "3. The configured user has CREATE DATABASE permission.",
            "4. pgvector is installed, then run migrations: uv run alembic upgrade head",
            "5. To change the connection string, set MO_DB_DSN=postgresql+asyncpg://... in .env.",
        ]
    )


async def ensure_database_exists(dsn: str) -> bool:
    url = make_url(dsn)
    database = url.database
    if not database:
        raise DatabaseCreateError("MO_DB_DSN does not include a database name.")

    maintenance_dsn = maintenance_dsn_for(dsn)
    maintenance_engine = create_async_engine(maintenance_dsn, isolation_level="AUTOCOMMIT")
    try:
        async with maintenance_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            if database == "postgres":
                return False

            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :database"),
                {"database": database},
            )
            if exists:
                return False

            quoted_database = await conn.scalar(
                text("SELECT quote_ident(:database)"),
                {"database": database},
            )
            await conn.execute(text(f"CREATE DATABASE {quoted_database}"))
            return True
    except Exception as exc:
        raise DatabaseCreateError(
            f"Could not verify/create database {database!r} via the 'postgres' maintenance database: {exc}"
        ) from exc
    finally:
        await maintenance_engine.dispose()


async def check_database_ready(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

        extension_rows = await conn.execute(
            text(
                "SELECT extname FROM pg_extension "
                "WHERE extname IN ('pgcrypto', 'vector')"
            )
        )
        extensions = set(extension_rows.scalars().all())
        missing_extensions = sorted(REQUIRED_EXTENSIONS - extensions)
        if missing_extensions:
            raise DatabaseCheckError(
                "Missing PostgreSQL extensions: "
                + ", ".join(missing_extensions)
                + ". Install pgvector, then run: uv run alembic upgrade head."
            )

        column_rows = await conn.execute(
            text(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'projects',
                    'memories',
                    'sessions',
                    'system_settings'
                  )
                """
            )
        )
        found: dict[str, set[str]] = {}
        for table_name, column_name in column_rows:
            found.setdefault(table_name, set()).add(column_name)

        missing_tables = sorted(table for table in REQUIRED_COLUMNS if table not in found)
        if missing_tables:
            raise DatabaseCheckError(
                "Missing database tables: "
                + ", ".join(missing_tables)
                + ". Run: uv run alembic upgrade head."
            )

        missing_columns = {
            table: sorted(columns - found[table])
            for table, columns in REQUIRED_COLUMNS.items()
            if columns - found[table]
        }
        if missing_columns:
            details = "; ".join(
                f"{table}: {', '.join(columns)}"
                for table, columns in sorted(missing_columns.items())
            )
            raise DatabaseCheckError(
                "Database schema is incomplete; missing columns: "
                + details
                + ". Run: uv run alembic upgrade head."
            )


async def check_database_dsn(dsn: str) -> bool:
    database_created = await ensure_database_exists(dsn)
    engine = create_async_engine(dsn)
    try:
        await check_database_ready(engine)
    finally:
        await engine.dispose()
    return database_created
