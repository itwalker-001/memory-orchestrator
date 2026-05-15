import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from memory_orchestrator_server.http_app import create_app
from memory_orchestrator_server.repository import MemoryRepository
from memory_orchestrator_server.models import GLOBAL_PROJECT_ID

FAKE_EMB = [1.0] + [0.0] * 511
EMB_PATCH = "memory_orchestrator_server.mcp_core.embed_one"


def _app(engine):
    return create_app(engine_override=engine, skip_embedder=True)


# ── /mcp/tools/call ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_unknown_tool_returns_404(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/mcp/tools/call", json={
            "name": "nonexistent_tool",
            "project_slug": "github.com/a/b",
        })
    assert r.status_code == 404
    assert "unknown tool" in r.json()["detail"]


@pytest.mark.asyncio
async def test_mcp_save_memory_via_http(engine):
    with patch(EMB_PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
            r = await c.post("/mcp/tools/call", json={
                "name": "save_memory",
                "project_slug": "github.com/a/b",
                "arguments": {
                    "type": "feedback",
                    "name": "http-test",
                    "description": "saved via http bridge",
                    "content": "mcp over http works",
                },
            })
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["action"] == "created"
    assert "id" in result


@pytest.mark.asyncio
async def test_mcp_save_user_type_goes_to_global(engine, session):
    with patch(EMB_PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
            r = await c.post("/mcp/tools/call", json={
                "name": "save_memory",
                "project_slug": "github.com/a/b",
                "arguments": {
                    "type": "user",
                    "name": "user-via-http",
                    "description": "user memory routed to global",
                    "content": "user type always global",
                },
            })
    assert r.status_code == 200
    mem_id = r.json()["result"]["id"]

    from sqlalchemy import select
    from memory_orchestrator_server.models import Memory
    row = (await session.execute(select(Memory).where(Memory.id == mem_id))).scalar_one()
    assert row.project_id == GLOBAL_PROJECT_ID


@pytest.mark.asyncio
async def test_mcp_list_memories_via_http(engine, session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/list/test")
    await repo.save(type="feedback", name="listed", description="d", content="c",
                    project_id=project_uuid, source="explicit")
    await session.commit()

    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/mcp/tools/call", json={
            "name": "list_memories",
            "project_slug": "github.com/list/test",
            "arguments": {},
        })
    assert r.status_code == 200
    items = r.json()["result"]
    assert any(m["name"] == "listed" for m in items)


@pytest.mark.asyncio
async def test_mcp_delete_memory_via_http(engine, session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/del/test")
    m = await repo.save(type="feedback", name="to-delete", description="d", content="c",
                        project_id=project_uuid, source="explicit")
    await session.commit()

    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/mcp/tools/call", json={
            "name": "delete_memory",
            "project_slug": "github.com/del/test",
            "arguments": {"id": str(m.id)},
        })
    assert r.status_code == 200
    assert r.json()["result"]["deleted"] is True


@pytest.mark.asyncio
async def test_mcp_search_memory_via_http(engine, session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/search/test")
    await repo.save(type="feedback", name="searchable", description="d", content="c",
                    project_id=project_uuid, source="explicit",
                    embedding=FAKE_EMB)
    await session.commit()

    with patch(EMB_PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
            r = await c.post("/mcp/tools/call", json={
                "name": "search_memory",
                "project_slug": "github.com/search/test",
                "arguments": {"query": "searchable content", "top_k": 5},
            })
    assert r.status_code == 200
    results = r.json()["result"]
    assert any(item["name"] == "searchable" for item in results)


# ── /mcp/resources/read ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_read_guide_resource(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/mcp/resources/read", json={
            "uri": "memory://orchestrator/guide",
            "project_slug": "github.com/a/b",
        })
    assert r.status_code == 200
    content = r.json()["result"]
    assert "save_memory" in content
    assert "search_memory" in content


@pytest.mark.asyncio
async def test_mcp_read_recent_resource(engine, session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="recent-test", description="d",
                    content="recent resource test", project_id="*", source="explicit")
    await session.commit()

    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/mcp/resources/read", json={
            "uri": "memory://recent",
            "project_slug": "github.com/a/b",
        })
    assert r.status_code == 200
    content = r.json()["result"]
    assert "recent-test" in content


@pytest.mark.asyncio
async def test_mcp_read_project_resource(engine, session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/proj/resource")
    await repo.save(type="project", name="proj-resource-mem", description="d",
                    content="project resource content", project_id=project_uuid, source="explicit")
    await session.commit()

    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/mcp/resources/read", json={
            "uri": "memory://project/github.com/proj/resource",
            "project_slug": "github.com/proj/resource",
        })
    assert r.status_code == 200
    content = r.json()["result"]
    assert "proj-resource-mem" in content


@pytest.mark.asyncio
async def test_mcp_read_unknown_resource_returns_500(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/mcp/resources/read", json={
            "uri": "memory://unknown/whatever",
            "project_slug": "github.com/a/b",
        })
    assert r.status_code == 404
    assert "Unknown memory resource URI" in r.json()["detail"]
