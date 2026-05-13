import uuid

import pytest

from memory_orchestrator_server.auth_tokens import hash_token
from memory_orchestrator_server.models import ApiToken
from memory_orchestrator_server.routers.ui import make_ui_router


class _DummyMaker:
    pass


def test_tokens_route_body_model_is_fully_resolved() -> None:
    router = make_ui_router(maker=_DummyMaker())
    route = next(
        r
        for r in router.routes
        if getattr(r, "path", None) == "/api/tokens" and "POST" in getattr(r, "methods", [])
    )
    field = route.dependant.body_params[0]

    assert "ForwardRef" not in repr(field._type_adapter)


def test_tokens_reset_route_exists() -> None:
    router = make_ui_router(maker=_DummyMaker())

    route = next(
        r
        for r in router.routes
        if getattr(r, "path", None) == "/api/tokens/{token_id}/reset"
        and "POST" in getattr(r, "methods", [])
    )

    assert "ForwardRef" not in repr(route.dependant.path_params[0]._type_adapter)


class _FakeSession:
    def __init__(self, token: ApiToken):
        self.token = token
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, _model, token_id):
        return self.token if self.token.id == token_id else None

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_tokens_reset_handler_rotates_token_hash() -> None:
    token_id = uuid.uuid4()
    token = ApiToken(id=token_id, name="admin", kind="ui_admin", token_hash=hash_token("old-token"))
    session = _FakeSession(token)

    router = make_ui_router(maker=lambda: session)
    route = next(
        r
        for r in router.routes
        if getattr(r, "path", None) == "/api/tokens/{token_id}/reset"
        and "POST" in getattr(r, "methods", [])
    )

    response = await route.endpoint(token_id, authorization="Bearer other-token", mo_ui_session=None)
    body = response.body.decode("utf-8")

    assert session.committed is True
    assert f'"id":"{token_id}"' in body
    assert '"action":"rotated"' in body
    assert token.token_hash != hash_token("old-token")
