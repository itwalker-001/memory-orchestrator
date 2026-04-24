import pytest
from unittest.mock import AsyncMock, patch
from memory_orchestrator.mcp_server import handle_search_memory, handle_save_memory, handle_list_memories


@pytest.mark.asyncio
async def test_save_then_search(session):
    fake_emb = [1.0] + [0.0] * 511
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        saved = await handle_save_memory(
            session=session,
            current_project_id="github.com/a/b",
            args={"type": "user", "name": "role", "description": "data scientist",
                  "content": "data scientist focused on observability"},
        )
        assert saved["action"] == "created"
        results = await handle_search_memory(
            session=session,
            current_project_id="github.com/a/b",
            args={"query": "data scientist", "top_k": 3},
        )
        assert len(results) >= 1
        assert results[0]["name"] == "role"


@pytest.mark.asyncio
async def test_save_conflict_returns_conflicts(session):
    fake_emb = [1.0] + [0.0] * 511
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        await handle_save_memory(
            session=session, current_project_id="*",
            args={"type": "user", "name": "a", "description": "x", "content": "x"},
        )
        result = await handle_save_memory(
            session=session, current_project_id="*",
            args={"type": "user", "name": "b", "description": "x", "content": "x"},
        )
        assert "conflicts" in result
        assert len(result["conflicts"]) == 1


@pytest.mark.asyncio
async def test_list_memories_returns_summaries(session):
    fake_emb = [1.0] + [0.0] * 511
    with patch("memory_orchestrator.mcp_server.embed_one", new=AsyncMock(return_value=fake_emb)):
        await handle_save_memory(
            session=session, current_project_id="*",
            args={"type": "user", "name": "x", "description": "d", "content": "c"},
        )
    items = await handle_list_memories(
        session=session, current_project_id="*",
        args={"type": ["user"], "limit": 10},
    )
    assert len(items) == 1
    assert items[0]["name"] == "x"
    assert "content" not in items[0]
