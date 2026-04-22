import pytest
from httpx import AsyncClient, ASGITransport
from memory_orchestrator.http_app import create_app
from memory_orchestrator.repository import MemoryRepository


@pytest.mark.asyncio
async def test_healthz_returns_ok(engine):
    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["db"] == "ok"


@pytest.mark.asyncio
async def test_context_returns_markdown(engine, session):
    repo = MemoryRepository(session)
    await repo.save(
        type="user", name="role", description="Go dev",
        content="Go dev new to Python", project_id="*", source="explicit",
    )
    await session.commit()
    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/context", params={"project_id": "github.com/a/b", "budget_tokens": 2000})
        assert r.status_code == 200
        body = r.text
        assert "Go dev" in body


@pytest.mark.asyncio
async def test_stats_returns_counts(engine, session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="u", description="x", content="x",
                    project_id="*", source="explicit")
    await session.commit()
    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/stats", params={"project_id": "*"})
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["by_type"]["user"] == 1
