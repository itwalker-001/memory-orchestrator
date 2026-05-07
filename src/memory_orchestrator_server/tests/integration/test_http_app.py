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
async def test_memories_api_returns_source_client(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/source/client")
    await repo.save(
        type="project", name="source", description="from claude",
        content="x", project_id=pid, source="explicit", source_client="claude",
    )
    await session.commit()
    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/memories")
        assert r.status_code == 200
        assert r.json()[0]["source_client"] == "claude"


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


@pytest.mark.asyncio
async def test_duplicates_uses_settings_and_filters(engine, session):
    repo = MemoryRepository(session)
    await repo.set_settings({"dup_threshold": "0.93"})
    await repo.save(
        type="project",
        name="a",
        description="same",
        content="alpha content",
        project_id="github.com/a/b",
        source="explicit",
        embedding=[1.0] + [0.0] * 511,
    )
    await repo.save(
        type="project",
        name="b",
        description="same-ish",
        content="beta content",
        project_id="github.com/a/b",
        source="explicit",
        embedding=[1.0, 0.3] + [0.0] * 510,
    )
    await repo.save(
        type="feedback",
        name="c",
        description="same-ish",
        content="wrong type",
        project_id="github.com/a/b",
        source="explicit",
        embedding=[1.0, 0.3] + [0.0] * 510,
    )
    await repo.save(
        type="project",
        name="d",
        description="same-ish",
        content="wrong project",
        project_id="github.com/x/y",
        source="explicit",
        embedding=[1.0, 0.3] + [0.0] * 510,
    )
    await session.commit()

    app = create_app(engine_override=engine, skip_embedder=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get(
            "/api/duplicates",
            params={"project_slug": "github.com/a/b", "type": "project"},
        )

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert {data[0]["name1"], data[0]["name2"]} == {"a", "b"}
    assert {data[0]["content1"], data[0]["content2"]} == {"alpha content", "beta content"}
