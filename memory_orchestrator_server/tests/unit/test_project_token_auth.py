from memory_orchestrator_server.auth_tokens import TOKEN_KIND_PROJECT


def test_token_kind_project_constant():
    assert TOKEN_KIND_PROJECT == "project_token"
