import asyncio
from logging.config import fileConfig
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from memory_orchestrator.config import get_settings
from memory_orchestrator.db_check import ensure_database_exists, format_database_startup_error
from memory_orchestrator.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().db_dsn)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    database_created = await ensure_database_exists(get_settings().db_dsn)
    if database_created:
        print("Database did not exist and was created automatically; continuing with the target database.")

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


try:
    asyncio.run(run_migrations_online())
except Exception as exc:
    raise SystemExit(format_database_startup_error(get_settings().db_dsn, exc)) from None
