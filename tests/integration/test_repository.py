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


@pytest.mark.asyncio
async def test_find_duplicates_by_embedding(session):
    repo = MemoryRepository(session)
    v1 = [1.0] + [0.0] * 511
    # v1_near: [1.0, 0.3, 0, 0, ...] — cosine with v1 = 1/sqrt(1.09) ≈ 0.958 > 0.92
    v1_near = [1.0, 0.3] + [0.0] * 510
    await repo.save(
        type="user", name="a", description="x", content="x",
        project_id="*", source="explicit", embedding=v1,
    )
    dups = await repo.find_duplicates(
        type="user", project_id="*", embedding=v1_near, threshold=0.92
    )
    assert len(dups) == 1
    assert dups[0].name == "a"


@pytest.mark.asyncio
async def test_find_duplicates_respects_threshold(session):
    repo = MemoryRepository(session)
    v = [1.0] + [0.0] * 511
    orthogonal = [0.0, 1.0] + [0.0] * 510  # cosine with v = 0, below any positive threshold
    await repo.save(
        type="user", name="a", description="x", content="x",
        project_id="*", source="explicit", embedding=v,
    )
    dups = await repo.find_duplicates(
        type="user", project_id="*", embedding=orthogonal, threshold=0.92
    )
    assert dups == []
