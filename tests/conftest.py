import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from memory_orchestrator.models import Base

TEST_DSN = os.environ.get(
    "MO_TEST_DB_DSN",
    "postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator_test",
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    # AUTOCOMMIT required for CREATE EXTENSION and DROP/CREATE TABLE outside transactions
    eng = create_async_engine(TEST_DSN, isolation_level="AUTOCOMMIT")
    async with eng.connect() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    transactional_engine = create_async_engine(TEST_DSN)
    maker = async_sessionmaker(transactional_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
        await s.rollback()
    await transactional_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _truncate(engine):
    yield
    async with engine.connect() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE memories, memory_links, sessions, projects CASCADE"
        )
