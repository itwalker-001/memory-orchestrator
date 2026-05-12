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
