import uuid as _uuid
import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch
from memory_orchestrator_server.models import Memory
from memory_orchestrator_server.mcp_core import (
    handle_delete_memory,
    handle_list_memories,
    handle_promote_memory,
    handle_read_memory_resource,
    handle_save_memory,
    handle_search_memory,
)
from memory_orchestrator_server.mcp_contract import (
    list_memory_resource_templates,
    list_memory_resources,
)
from memory_orchestrator_server.repository import MemoryRepository

FAKE_EMB = [1.0] + [0.0] * 1023
PATCH = "memory_orchestrator_server.mcp_core.embed_one"


# ── save / search ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_then_search(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/b")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        saved = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "user", "name": "role", "description": "data scientist",
                  "content": "data scientist focused on observability"},
        )
        assert saved["action"] == "created"
        results = await handle_search_memory(
            session=session, project_uuid=project_uuid,
            args={"query": "data scientist", "top_k": 3},
        )
    assert len(results) >= 1
    assert results[0]["name"] == "role"


@pytest.mark.asyncio
async def test_save_conflict_returns_conflicts(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/conflicts")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
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
async def test_save_user_type_goes_to_global_project(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/user-global")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        saved = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "user", "name": "user-mem", "description": "d", "content": "c"},
        )
    row = await session.execute(select(Memory).where(Memory.id == _uuid.UUID(saved["id"])))
    assert row.scalar_one().project_id == GLOBAL_PROJECT_ID


@pytest.mark.asyncio
async def test_save_ignores_project_id_arg(session):
    # The token-bound project is authoritative: a stray project_id arg must NOT
    # redirect the save (and must not auto-create the other project).
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/explicit")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        saved = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "project", "name": "cross", "description": "d", "content": "c",
                  "project_id": "github.com/a/other"},
        )
    row = await session.execute(select(Memory).where(Memory.id == _uuid.UUID(saved["id"])))
    assert row.scalar_one().project_id == project_uuid


@pytest.mark.asyncio
async def test_save_replace_id_merges(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/replace")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        original = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "feedback", "name": "old", "description": "old-d", "content": "old-c"},
        )
        merged = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "feedback", "name": "new", "description": "new-d", "content": "new-c",
                  "replace_id": original["id"]},
        )
    assert merged["action"] == "merged"


@pytest.mark.asyncio
async def test_search_scope_all_crosses_projects(session):
    repo = MemoryRepository(session)
    proj_a = await repo.ensure_project("github.com/x/search-a")
    proj_b = await repo.ensure_project("github.com/x/search-b")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        await handle_save_memory(
            session=session, project_uuid=proj_a,
            args={"type": "project", "name": "mem-a", "description": "d", "content": "c"},
        )
        await handle_save_memory(
            session=session, project_uuid=proj_b,
            args={"type": "project", "name": "mem-b", "description": "d", "content": "c"},
        )
        results = await handle_search_memory(
            session=session, project_uuid=proj_a,
            args={"query": "c", "project_id": "all", "top_k": 10},
        )
    names = {r["name"] for r in results}
    assert "mem-a" in names
    assert "mem-b" in names


# ── list ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_memories_returns_summaries(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/list")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
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


@pytest.mark.asyncio
async def test_list_scope_all_crosses_projects(session):
    repo = MemoryRepository(session)
    proj_a = await repo.ensure_project("github.com/x/list-a")
    proj_b = await repo.ensure_project("github.com/x/list-b")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        await handle_save_memory(
            session=session, project_uuid=proj_a,
            args={"type": "project", "name": "la", "description": "d", "content": "c"},
        )
        await handle_save_memory(
            session=session, project_uuid=proj_b,
            args={"type": "project", "name": "lb", "description": "d", "content": "c"},
        )
    items = await handle_list_memories(
        session=session, project_uuid=proj_a,
        args={"project_id": "all", "limit": 50},
    )
    names = {i["name"] for i in items}
    assert "la" in names
    assert "lb" in names


# ── delete ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_memory_soft(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/del-soft")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        saved = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "feedback", "name": "to-soft-del", "description": "d", "content": "c"},
        )
    result = await handle_delete_memory(session=session, args={"id": saved["id"]})
    assert result == {"deleted": True}
    # soft-deleted: superseded_by is set, so list no longer shows it
    items = await handle_list_memories(
        session=session, project_uuid=project_uuid,
        args={"limit": 50},
    )
    assert all(i["name"] != "to-soft-del" for i in items)


@pytest.mark.asyncio
async def test_delete_memory_hard(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/del-hard")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        saved = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "feedback", "name": "to-hard-del", "description": "d", "content": "c"},
        )
    result = await handle_delete_memory(session=session, args={"id": saved["id"], "hard": True})
    assert result == {"deleted": True}
    row = await session.execute(select(Memory).where(Memory.id == _uuid.UUID(saved["id"])))
    assert row.scalar_one_or_none() is None


# ── promote ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_promote_memory_importance(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/promote-imp")
    with patch(PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        saved = await handle_save_memory(
            session=session, project_uuid=project_uuid,
            args={"type": "feedback", "name": "low", "description": "d", "content": "c", "importance": 1},
        )
    result = await handle_promote_memory(session=session, args={"id": saved["id"], "importance": 5})
    assert result["updated"] is True
    assert "importance" in result["changes"]
    row = await session.execute(select(Memory).where(Memory.id == _uuid.UUID(saved["id"])))
    assert row.scalar_one().importance == 5



# ── resources ─────────────────────────────────────────────────────────────────

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


def test_read_guide_resource_contains_all_tools():
    from memory_orchestrator_server.mcp_server import _memory_resource_guide
    guide = _memory_resource_guide()
    for tool in ("save_memory", "search_memory", "list_memories", "promote_memory", "delete_memory"):
        assert tool in guide


@pytest.mark.asyncio
async def test_read_recent_memory_resource_points_to_tools(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/resources")
    await repo.save(
        type="project", name="mcp resource discovery",
        description="surface tool guidance through resources",
        content="Models should call save_memory for writes.",
        project_id=project_uuid, source="test", source_client="codex",
    )
    text = await handle_read_memory_resource(
        session=session, project_uuid=project_uuid, uri="memory://recent",
    )
    assert "save_memory" in text
    assert "tool from this MCP server" in text
    assert "mcp resource discovery" in text
    assert "codex" in text


@pytest.mark.asyncio
async def test_read_project_resource_by_slug(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("slug-test-proj")
    await repo.save(
        type="project", name="slug-mem", description="d",
        content="c", project_id=project_uuid, source="test", source_client="claude",
    )
    text = await handle_read_memory_resource(
        session=session, project_uuid=project_uuid,
        uri="memory://project/slug-test-proj",
    )
    assert "slug-mem" in text
    assert "save_memory" in text


@pytest.mark.asyncio
async def test_read_project_resource_all(session):
    repo = MemoryRepository(session)
    proj_a = await repo.ensure_project("github.com/x/res-all-a")
    proj_b = await repo.ensure_project("github.com/x/res-all-b")
    await repo.save(type="project", name="res-a", description="d", content="c",
                    project_id=proj_a, source="test", source_client="claude")
    await repo.save(type="project", name="res-b", description="d", content="c",
                    project_id=proj_b, source="test", source_client="claude")
    text = await handle_read_memory_resource(
        session=session, project_uuid=proj_a, uri="memory://project/all",
    )
    assert "res-a" in text
    assert "res-b" in text


@pytest.mark.asyncio
async def test_read_unknown_resource_raises(session):
    repo = MemoryRepository(session)
    project_uuid = await repo.ensure_project("github.com/a/err")
    with pytest.raises(ValueError, match="Unknown memory resource URI"):
        await handle_read_memory_resource(
            session=session, project_uuid=project_uuid,
            uri="memory://unknown/whatever",
        )
