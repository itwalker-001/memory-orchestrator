import ast
from pathlib import Path


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for file in path.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


def test_mcp_client_package_does_not_import_server_dependencies():
    package = Path("src/memory_orchestrator_mcp")
    assert package.exists()

    imports = _imports(package)
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
    package = Path("src/memory_orchestrator_server")
    assert package.exists()

    imports = _imports(package)
    forbidden = {
        "memory_orchestrator_mcp",
    }

    offenders = sorted(
        module
        for module in imports
        for forbidden_module in forbidden
        if module == forbidden_module or module.startswith(f"{forbidden_module}.")
    )
    assert offenders == []
