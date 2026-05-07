import uuid
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from memory_orchestrator.http_app import create_app
from memory_orchestrator.repository import MemoryRepository

FAKE_EMB = [1.0] + [0.0] * 511
EMB_PATCH = "memory_orchestrator_server.embedder.embed_one"


def _app(engine):
    return create_app(engine_override=engine, skip_embedder=True)


# ── hooks router ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_healthz_returns_ok(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


@pytest.mark.asyncio
async def test_context_returns_markdown(engine, session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="role", description="Go dev",
                    content="Go dev new to Python", project_id="*", source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/context", params={"project_id": "github.com/a/b", "budget_tokens": 2000})
    assert r.status_code == 200
    assert "Go dev" in r.text


@pytest.mark.asyncio
async def test_context_accepts_project_slug_param(engine, session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="slug-role", description="slug test",
                    content="slug param works", project_id="*", source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/context", params={"project_slug": "github.com/slug/test"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_context_missing_project_returns_422(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/context")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_stats_returns_counts(engine, session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="u", description="x", content="x",
                    project_id="*", source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/stats", params={"project_id": "*"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["by_type"]["user"] == 1


@pytest.mark.asyncio
async def test_stats_no_filter_returns_all(engine, session):
    repo = MemoryRepository(session)
    await repo.save(type="user", name="u1", description="x", content="x",
                    project_id="*", source="explicit")
    await repo.save(type="feedback", name="f1", description="x", content="x",
                    project_id="*", source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/stats")
    assert r.status_code == 200
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_ingest_returns_202_accepted(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/ingest", json={
            "session_id": "test-session-001",
            "project_slug": "github.com/a/b",
            "transcript_path": "/nonexistent/path.jsonl",
            "client": "claude",
        })
    assert r.status_code == 202
    assert r.json()["accepted"] is True


# ── UI router: projects ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_projects_lists_all(engine, session):
    repo = MemoryRepository(session)
    await repo.ensure_project("github.com/proj/one")
    await repo.ensure_project("github.com/proj/two")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/projects")
    assert r.status_code == 200
    slugs = [p["slug"] for p in r.json()]
    assert "github.com/proj/one" in slugs
    assert "github.com/proj/two" in slugs


@pytest.mark.asyncio
async def test_projects_hide_empty(engine, session):
    repo = MemoryRepository(session)
    await repo.ensure_project("github.com/empty/proj")
    pid = await repo.ensure_project("github.com/full/proj")
    await repo.save(type="user", name="x", description="d", content="c",
                    project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/projects", params={"hide_empty": "true"})
    assert r.status_code == 200
    slugs = [p["slug"] for p in r.json()]
    assert "github.com/full/proj" in slugs
    assert "github.com/empty/proj" not in slugs


# ── UI router: memories CRUD ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memories_api_returns_source_client(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/source/client")
    await repo.save(type="project", name="source", description="from claude",
                    content="x", project_id=pid, source="explicit", source_client="claude")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/memories")
    assert r.status_code == 200
    assert r.json()[0]["source_client"] == "claude"


@pytest.mark.asyncio
async def test_memories_filter_by_type(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/filter/type")
    await repo.save(type="user", name="u", description="d", content="c",
                    project_id=pid, source="explicit")
    await repo.save(type="feedback", name="f", description="d", content="c",
                    project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/memories", params={"type": "user"})
    assert r.status_code == 200
    assert all(m["type"] == "user" for m in r.json())


@pytest.mark.asyncio
async def test_memories_filter_by_project(engine, session):
    repo = MemoryRepository(session)
    pid_a = await repo.ensure_project("github.com/filter/proj-a")
    pid_b = await repo.ensure_project("github.com/filter/proj-b")
    await repo.save(type="project", name="in-a", description="d", content="c",
                    project_id=pid_a, source="explicit")
    await repo.save(type="project", name="in-b", description="d", content="c",
                    project_id=pid_b, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/memories", params={"project_slug": "github.com/filter/proj-a"})
    assert r.status_code == 200
    names = [m["name"] for m in r.json()]
    assert "in-a" in names
    assert "in-b" not in names


@pytest.mark.asyncio
async def test_memories_text_search(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/search/text")
    await repo.save(type="user", name="needle", description="unique-kw", content="c",
                    project_id=pid, source="explicit")
    await repo.save(type="user", name="haystack", description="other", content="c",
                    project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/memories", params={"q": "unique-kw"})
    assert r.status_code == 200
    assert any(m["name"] == "needle" for m in r.json())


@pytest.mark.asyncio
async def test_create_memory(engine, session):
    repo = MemoryRepository(session)
    await repo.ensure_project("*")
    await session.commit()
    with patch(EMB_PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
            r = await c.post("/api/memories", json={
                "type": "user", "name": "new-mem", "description": "d", "content": "c",
            })
    assert r.status_code == 201
    assert r.json()["action"] == "created"


@pytest.mark.asyncio
async def test_create_memory_invalid_type(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/memories", json={
            "type": "bogus", "name": "x", "description": "d", "content": "c",
        })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_memory_unknown_project_returns_404(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/memories", json={
            "type": "project", "name": "x", "description": "d", "content": "c",
            "project_id": "github.com/no/such",
        })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_memory_soft(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/del/soft")
    m = await repo.save(type="feedback", name="del-me", description="d", content="c",
                        project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.delete(f"/api/memories/{m.id}")
    assert r.status_code == 204
    # No longer appears in listing
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r2 = await c.get("/api/memories")
    assert all(item["id"] != str(m.id) for item in r2.json())


@pytest.mark.asyncio
async def test_delete_memory_hard(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/del/hard")
    m = await repo.save(type="feedback", name="hard-del", description="d", content="c",
                        project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.delete(f"/api/memories/{m.id}", params={"hard": "true"})
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_memory_not_found(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.delete(f"/api/memories/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_memory_updates_fields(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/patch/mem")
    m = await repo.save(type="feedback", name="original", description="old-desc",
                        content="old-content", project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.patch(f"/api/memories/{m.id}", json={"name": "updated", "description": "new-desc"})
    assert r.status_code == 200
    assert r.json()["saved"] == 2


@pytest.mark.asyncio
async def test_patch_memory_content_re_embeds(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/patch/embed")
    m = await repo.save(type="feedback", name="emb", description="d",
                        content="old", project_id=pid, source="explicit")
    await session.commit()
    with patch(EMB_PATCH, new=AsyncMock(return_value=FAKE_EMB)) as mock_emb:
        async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
            r = await c.patch(f"/api/memories/{m.id}", json={"content": "new content"})
    assert r.status_code == 200
    mock_emb.assert_awaited_once()


@pytest.mark.asyncio
async def test_patch_memory_empty_body_returns_zero(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/patch/empty")
    m = await repo.save(type="feedback", name="x", description="d", content="c",
                        project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.patch(f"/api/memories/{m.id}", json={})
    assert r.status_code == 200
    assert r.json()["saved"] == 0


@pytest.mark.asyncio
async def test_patch_memory_not_found(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.patch(f"/api/memories/{uuid.uuid4()}", json={"name": "x"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_clone_memory(engine, session):
    repo = MemoryRepository(session)
    src_pid = await repo.ensure_project("github.com/clone/src")
    dst_pid = await repo.ensure_project("github.com/clone/dst")
    m = await repo.save(type="project", name="to-clone", description="d", content="c",
                        project_id=src_pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post(f"/api/memories/{m.id}/clone",
                         params={"project_slug": "github.com/clone/dst"})
    assert r.status_code == 201
    assert r.json()["action"] == "cloned"
    new_id = r.json()["id"]
    assert new_id != str(m.id)


@pytest.mark.asyncio
async def test_clone_memory_not_found(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post(f"/api/memories/{uuid.uuid4()}/clone",
                         params={"project_slug": "github.com/x"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_move_memory(engine, session):
    repo = MemoryRepository(session)
    src_pid = await repo.ensure_project("github.com/move/src")
    await repo.ensure_project("github.com/move/dst")
    m = await repo.save(type="project", name="to-move", description="d", content="c",
                        project_id=src_pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.patch(f"/api/memories/{m.id}/move",
                          params={"project_slug": "github.com/move/dst"})
    assert r.status_code == 200
    assert r.json()["moved"] is True


@pytest.mark.asyncio
async def test_move_memory_not_found(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.patch(f"/api/memories/{uuid.uuid4()}/move",
                          params={"project_slug": "github.com/x"})
    assert r.status_code == 404


# ── UI router: settings ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_settings_returns_defaults(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "dup_threshold" in data
    assert "search_top_k" in data
    assert data.get("extraction_api_key") in ("", "***")  # real key never returned


@pytest.mark.asyncio
async def test_patch_settings_persists(engine, session):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.patch("/api/settings", json={"search_top_k": "12", "dup_threshold": "0.88"})
    assert r.status_code == 200
    assert r.json()["saved"] == 2
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r2 = await c.get("/api/settings")
    assert r2.json()["search_top_k"] == "12"
    assert r2.json()["dup_threshold"] == "0.88"


@pytest.mark.asyncio
async def test_patch_settings_empty_body_returns_zero(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.patch("/api/settings", json={})
    assert r.status_code == 200
    assert r.json()["saved"] == 0


# ── UI router: batch ops ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_delete(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/batch/del")
    m1 = await repo.save(type="project", name="b1", description="d", content="c",
                         project_id=pid, source="explicit")
    m2 = await repo.save(type="project", name="b2", description="d", content="c",
                         project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/memories/batch-delete", json={"ids": [str(m1.id), str(m2.id)]})
    assert r.status_code == 200
    assert r.json()["deleted"] == 2


@pytest.mark.asyncio
async def test_batch_move(engine, session):
    repo = MemoryRepository(session)
    src = await repo.ensure_project("github.com/batch/move-src")
    await repo.ensure_project("github.com/batch/move-dst")
    m1 = await repo.save(type="project", name="mv1", description="d", content="c",
                         project_id=src, source="explicit")
    m2 = await repo.save(type="project", name="mv2", description="d", content="c",
                         project_id=src, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/memories/batch-move",
                         json={"ids": [str(m1.id), str(m2.id)],
                               "project_slug": "github.com/batch/move-dst"})
    assert r.status_code == 200
    assert r.json()["moved"] == 2


@pytest.mark.asyncio
async def test_batch_move_unknown_project_returns_404(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/memories/batch-move",
                         json={"ids": [], "project_slug": "github.com/no/such"})
    assert r.status_code == 404


# ── UI router: export & duplicates ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_memories(engine, session):
    repo = MemoryRepository(session)
    pid = await repo.ensure_project("github.com/export/test")
    await repo.save(type="user", name="exp-mem", description="d", content="export content",
                    project_id=pid, source="explicit")
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/export")
    assert r.status_code == 200
    assert any(m["name"] == "exp-mem" for m in r.json())
    assert all("id" not in m for m in r.json())   # export omits id


@pytest.mark.asyncio
async def test_duplicates_uses_settings_and_filters(engine, session):
    repo = MemoryRepository(session)
    await repo.set_settings({"dup_threshold": "0.93"})
    await repo.save(type="project", name="a", description="same", content="alpha content",
                    project_id="github.com/a/b", source="explicit", embedding=[1.0] + [0.0] * 511)
    await repo.save(type="project", name="b", description="same-ish", content="beta content",
                    project_id="github.com/a/b", source="explicit", embedding=[1.0, 0.3] + [0.0] * 510)
    await repo.save(type="feedback", name="c", description="same-ish", content="wrong type",
                    project_id="github.com/a/b", source="explicit", embedding=[1.0, 0.3] + [0.0] * 510)
    await repo.save(type="project", name="d", description="same-ish", content="wrong project",
                    project_id="github.com/x/y", source="explicit", embedding=[1.0, 0.3] + [0.0] * 510)
    await session.commit()
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/duplicates",
                        params={"project_slug": "github.com/a/b", "type": "project"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert {data[0]["name1"], data[0]["name2"]} == {"a", "b"}


# ── UI router: misc ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timezone_returns_offset(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.get("/api/timezone")
    assert r.status_code == 200
    data = r.json()
    assert "offset_minutes" in data
    assert "label" in data
