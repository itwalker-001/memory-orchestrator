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
    assert saved.source_client == "claude"
    fetched = await repo.get(saved.id)
    assert fetched.name == "role"
    assert fetched.source_client == "claude"


@pytest.mark.asyncio
async def test_save_records_source_client(session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/source/client")
    saved = await repo.save(
        type="project",
        name="codex-source",
        description="saved from codex",
        content="full content here",
        project_id=pid,
        source="explicit",
        source_client="codex",
    )

    assert saved.source_client == "codex"


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


@pytest.mark.asyncio
async def test_vector_search_returns_scored_results(session):
    repo = MemoryRepository(session)
    v1 = [1.0] + [0.0] * 511
    v2 = [0.0, 1.0] + [0.0] * 510
    await repo.save(
        type="user", name="first", description="x", content="x",
        project_id="*", source="explicit", embedding=v1,
    )
    await repo.save(
        type="user", name="second", description="x", content="x",
        project_id="*", source="explicit", embedding=v2,
    )
    hits = await repo.search(query_embedding=v1, project_ids=["*"], top_k=2)
    assert len(hits) == 2
    assert hits[0].memory.name == "first"
    assert hits[0].score > hits[1].score


@pytest.mark.asyncio
async def test_vector_search_filters_project(session):
    repo = MemoryRepository(session)
    v = [1.0] + [0.0] * 511
    await repo.save(type="user", name="g", description="x", content="x",
                    project_id="*", source="explicit", embedding=v)
    await repo.save(type="project", name="p", description="x", content="x",
                    project_id="github.com/a/b", source="explicit", embedding=v)
    hits = await repo.search(query_embedding=v, project_ids=["github.com/a/b"], top_k=5)
    assert [h.memory.name for h in hits] == ["p"]


@pytest.mark.asyncio
async def test_vector_search_updates_hit_count(session):
    repo = MemoryRepository(session)
    v = [1.0] + [0.0] * 511
    saved = await repo.save(
        type="user", name="x", description="x", content="x",
        project_id="*", source="explicit", embedding=v,
    )
    await repo.search(query_embedding=v, project_ids=["*"], top_k=1, record_hits=True)
    after = await repo.get(saved.id)
    assert after.hit_count == 1
    assert after.last_hit_at is not None


@pytest.mark.asyncio
async def test_build_context_includes_global_user(session):
    repo = MemoryRepository(session)
    await repo.save(
        type="user", name="role", description="senior Go dev",
        content="senior Go dev, new to Python", project_id="*", source="explicit",
    )
    md = await repo.build_context(project_id="github.com/a/b", budget_tokens=2000)
    assert "role" in md
    assert "senior Go dev" in md


@pytest.mark.asyncio
async def test_build_context_scopes_project_memories(session):
    repo = MemoryRepository(session)
    await repo.save(
        type="feedback", name="no-mocks", description="integration tests no mocks",
        content="tests must hit real DB", why="past incident", how_to_apply="all test work",
        project_id="github.com/a/b", source="explicit", importance=5,
    )
    await repo.save(
        type="feedback", name="other", description="other project rule",
        content="x", why="x", how_to_apply="x",
        project_id="github.com/c/d", source="explicit", importance=5,
    )
    md = await repo.build_context(project_id="github.com/a/b", budget_tokens=2000)
    assert "no-mocks" in md
    assert "other" not in md
