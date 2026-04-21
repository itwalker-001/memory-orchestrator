import pytest
from memory_orchestrator.repository import MemoryRepository


@pytest.mark.asyncio
async def test_save_and_get_roundtrip(session):
    repo = MemoryRepository(session)
    saved = await repo.save(
        type="user",
        name="role",
        description="data scientist focused on observability",
        content="full content here",
        project_id="*",
        source="explicit",
    )
    assert saved.id is not None
    fetched = await repo.get(saved.id)
    assert fetched.name == "role"


@pytest.mark.asyncio
async def test_list_filters_by_project(session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="g", description="x", content="x", project_id="*", source="explicit")
    await repo.save(type="project", name="p", description="x", content="x", project_id="github.com/a/b", source="explicit")
    items = await repo.list(project_id="github.com/a/b")
    assert [m.name for m in items] == ["p"]


@pytest.mark.asyncio
async def test_delete_soft_supersedes_self(session):
    repo = MemoryRepository(session)
    saved = await repo.save(type="user", name="x", description="x", content="x", project_id="*", source="explicit")
    await repo.delete(saved.id, hard=False)
    after = await repo.list(project_id="*")
    assert after == []
    # record still exists
    raw = await repo.get(saved.id, include_superseded=True)
    assert raw.superseded_by == raw.id
