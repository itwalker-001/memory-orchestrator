import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[5]  # .../memory_orchestrator_server/src/memory_orchestrator_server/tests/unit/ → repo root
_SERVER_SRC = _REPO_ROOT / "memory_orchestrator_server" / "src" / "memory_orchestrator_server"
_MCP_SRC = _REPO_ROOT / "memory_orchestrator_mcp" / "src" / "memory_orchestrator_mcp"


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for file in path.rglob("*.py"):
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


def test_mcp_client_package_does_not_import_server_dependencies():
    assert _MCP_SRC.exists(), f"MCP source not found at {_MCP_SRC}"

    imports = _imports(_MCP_SRC)
    forbidden = {
        "asyncpg",
        "fastembed",
        "pgvector",
        "sqlalchemy",
        "memory_orchestrator_server.models",
        "memory_orchestrator_server.repository",
        "memory_orchestrator_server.embedder",
    }

    offenders = sorted(
        module
        for module in imports
        for forbidden_module in forbidden
        if module == forbidden_module or module.startswith(f"{forbidden_module}.")
    )
    assert offenders == []


def test_server_package_does_not_import_mcp_client():
    assert _SERVER_SRC.exists(), f"Server source not found at {_SERVER_SRC}"

    imports = _imports(_SERVER_SRC)
    forbidden = {"memory_orchestrator_mcp"}

    offenders = sorted(
        module
        for module in imports
        for forbidden_module in forbidden
        if module == forbidden_module or module.startswith(f"{forbidden_module}.")
    )
    assert offenders == []
