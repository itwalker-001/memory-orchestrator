import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from memory_orchestrator_server.http_app import create_app

EMB_PATCH = "memory_orchestrator_server.embedder.embed_one"
FAKE_EMB = [0.0] * 1024


def _app(engine):
    return create_app(engine_override=engine, skip_embedder=True)


@pytest.mark.asyncio
async def test_create_project_seeds_skeleton(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/projects", json={"slug": "test-proj", "display_name": "Test Project"})
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == "test-proj"
        project_id = data["id"]

        r2 = await c.get(f"/api/projects/{project_id}/skeleton")
        assert r2.status_code == 200
        tree = r2.json()
        assert len(tree) == 11
        assert tree[0]["name"] == "项目概况"
        assert tree[0]["is_builtin"] is True
        assert tree[0]["children"] == []


@pytest.mark.asyncio
async def test_patch_skeleton_node_prompt_hint(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/projects", json={"slug": "proj-patch", "display_name": "P"})
        project_id = r.json()["id"]
        tree = (await c.get(f"/api/projects/{project_id}/skeleton")).json()
        node_id = tree[0]["id"]

        r2 = await c.patch(f"/api/skeleton-nodes/{node_id}", json={"prompt_hint": "test hint"})
        assert r2.status_code == 200

        tree2 = (await c.get(f"/api/projects/{project_id}/skeleton")).json()
        assert tree2[0]["prompt_hint"] == "test hint"


@pytest.mark.asyncio
async def test_delete_builtin_node_forbidden(engine):
    async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
        r = await c.post("/api/projects", json={"slug": "proj-del", "display_name": "D"})
        project_id = r.json()["id"]
        tree = (await c.get(f"/api/projects/{project_id}/skeleton")).json()
        node_id = tree[0]["id"]

        r2 = await c.delete(f"/api/skeleton-nodes/{node_id}")
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_add_remove_memory_from_node(engine):
    with patch(EMB_PATCH, new=AsyncMock(return_value=FAKE_EMB)):
        async with AsyncClient(transport=ASGITransport(_app(engine)), base_url="http://t") as c:
            r = await c.post("/api/projects", json={"slug": "proj-mem", "display_name": "M"})
            project_id = r.json()["id"]
            tree = (await c.get(f"/api/projects/{project_id}/skeleton")).json()
            node_id = tree[0]["id"]

            rm = await c.post("/api/memories", json={
                "type": "project", "name": "test mem", "description": "d",
                "content": "c", "why": "w", "how_to_apply": "h", "project_id": project_id,
            })
            memory_id = rm.json()["id"]

            r2 = await c.post(f"/api/skeleton-nodes/{node_id}/memories", json={"memory_id": memory_id})
            assert r2.status_code == 201

            r3 = await c.get(f"/api/skeleton-nodes/{node_id}/memories")
            assert any(m["id"] == memory_id for m in r3.json())

            r4 = await c.delete(f"/api/skeleton-nodes/{node_id}/memories/{memory_id}")
            assert r4.status_code == 204
