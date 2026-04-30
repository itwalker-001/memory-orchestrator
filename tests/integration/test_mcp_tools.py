import pytest
from unittest.mock import AsyncMock, patch
from memory_orchestrator.mcp_server import (
    handle_list_memories,
    handle_read_memory_resource,
    handle_save_memory,
    handle_search_memory,
    list_memory_resource_templates,
    list_memory_resources,
)
from memory_orchestrator.repository import MemoryRepository


@pytest.mark.asyncio
async def test_save_then_search(session):
    fake_emb = [1.0] + [0.0] * 511
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/b")
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        saved = await handle_save_memory(
            session=session,
            project_uuid=project_uuid,
            args={"type": "user", "name": "role", "description": "data scientist",
                  "content": "data scientist focused on observability"},
        )
        assert saved["action"] == "created"
        results = await handle_search_memory(
            session=session,
            project_uuid=project_uuid,
            args={"query": "data scientist", "top_k": 3},
        )
        assert len(results) >= 1
        assert results[0]["name"] == "role"


@pytest.mark.asyncio
async def test_save_conflict_returns_conflicts(session):
    fake_emb = [1.0] + [0.0] * 511
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/conflicts")
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "user", "name": "a", "description": "x", "content": "x"},
        )
        result = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "user", "name": "b", "description": "x", "content": "x"},
        )
        assert "conflicts" in result
        assert len(result["conflicts"]) == 1


@pytest.mark.asyncio
async def test_list_memories_returns_summaries(session):
    fake_emb = [1.0] + [0.0] * 511
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/list")
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "user", "name": "x", "description": "d", "content": "c"},
        )
    items = await handle_list_memories(
        session=session, project_uuid=project_uuid,
        args={"type": ["user"], "limit": 10},
    )
    assert len(items) == 1
    assert items[0]["name"] == "x"
    assert "content" not in items[0]


def test_lists_memory_resources_and_templates():
    resources = list_memory_resources()
    assert [str(r.uri) for r in resources] == [
        "memory://orchestrator/guide",
        "memory://recent",
    ]
    assert "save_memory" in resources[0].description

    templates = list_memory_resource_templates()
    assert len(templates) == 1
    assert templates[0].uriTemplate == "memory://project/{slug}"
    assert "save_memory" in templates[0].description


@pytest.mark.asyncio
async def test_read_recent_memory_resource_points_to_tools(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/resources")
    await repo.save(
        type="project",
        name="mcp resource discovery",
        description="surface tool guidance through resources",
        content="Models should call save_memory for writes.",
        project_id=project_uuid,
        source="test",
        source_client="codex",
    )

    text = await handle_read_memory_resource(
        session=session,
        project_uuid=project_uuid,
        uri="memory://recent",
    )

    assert "save_memory" in text
    assert "tool from this MCP server" in text
    assert "mcp resource discovery" in text
    assert "codex" in text
