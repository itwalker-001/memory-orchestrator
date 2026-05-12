from pathlib import Path

from click.testing import CliRunner

from memory_orchestrator_server import cli
from memory_orchestrator_server.config import Settings


_SERVER_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _SERVER_ROOT.parent


def test_base_dockerfile_builds_heavy_runtime_layer() -> None:
    dockerfile = (_SERVER_ROOT / "Dockerfile.base").read_text(encoding="utf-8")

    assert "FROM astral/uv:python3.13-bookworm-slim" in dockerfile
    assert "http://mirrors.aliyun.com" in dockerfile
    assert "apt-get install -y --no-install-recommends build-essential" in dockerfile
    assert "UV_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple" in dockerfile
    assert "COPY pyproject.toml uv.lock ./" in dockerfile
    assert "uv export --frozen --no-dev --no-emit-project --no-hashes" in dockerfile
    assert "UV_HTTP_TIMEOUT=300" in dockerfile
    assert "uv pip install --system -r /tmp/requirements.txt" in dockerfile
    assert "COPY download_models.py ./" in dockerfile
    assert "RUN python download_models.py" in dockerfile
    assert "MO_EMBED_MODEL=/app/memory_orchestrator_server/models/BAAI/bge-m3" in dockerfile
    assert "MO_RERANK_MODEL=/app/memory_orchestrator_server/models/BAAI/bge-reranker-v2-m3" in dockerfile


def test_app_dockerfile_uses_prebuilt_base_image() -> None:
    dockerfile = (_SERVER_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG BASE_IMAGE=memory-orchestrator-server-base:latest" in dockerfile
    assert "FROM ${BASE_IMAGE}" in dockerfile
    assert "/app/memory_orchestrator_server/frontend/dist/" in dockerfile
    assert "uv pip install --system --no-cache --no-deps /app/memory_orchestrator_server/" in dockerfile
    assert "python -m compileall -q /app/memory_orchestrator_server" in dockerfile
    assert "/app/memory_orchestrator_server/memory_orchestrator_server" not in dockerfile
    assert "download_models.py" not in dockerfile
    assert "uv export" not in dockerfile
    assert "apt-get install" not in dockerfile


def test_build_script_deploys_stack_and_prints_admin_token() -> None:
    script = (_REPO_ROOT / "scripts" / "build.sh").read_text(encoding="utf-8")

    assert (_REPO_ROOT / "scripts" / "build.sh").exists()
    assert not (_REPO_ROOT / "scripts" / "build_base.sh").exists()
    assert not (_SERVER_ROOT / "scripts" / "build_base.sh").exists()
    assert 'script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"' in script
    assert 'server_root="$repo_root/memory_orchestrator_server"' in script
    assert 'cd "$server_root"' in script
    assert "Dockerfile.base" in script
    assert "pyproject.toml" in script
    assert "uv.lock" in script
    assert "download_models.py" in script
    assert "sha256sum" in script
    assert "memory-orchestrator-server-base" in script
    assert "memory-orchestrator-db" in script
    assert "MO_BASE_IMAGE=" in script
    assert "MO_DB_IMAGE=" in script
    assert "Dockerfile.db" in script
    assert "docker-compose" in script
    assert "up -d --build" in script
    assert "mo-server token create --kind ui_admin" in script
    assert "ADMIN TOKEN" in script


def test_compose_publishes_database_port_for_host_access() -> None:
    compose = (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "MO_DB_PORT" in compose
    assert '"${MO_DB_PORT:-15432}:5432"' in compose
    assert "${MO_PGDATA:-./data/postgres}:/var/lib/postgresql/data" in compose


def test_compose_lives_at_repo_root_and_builds_server_context() -> None:
    compose = (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert not (_SERVER_ROOT / "docker-compose.yml").exists()
    assert (_REPO_ROOT / ".env").exists()
    assert not (_SERVER_ROOT / ".env").exists()
    assert "context: ./memory_orchestrator_server" in compose
    assert "dockerfile: Dockerfile" in compose


def test_compose_builds_database_image_from_server_dockerfile() -> None:
    compose = (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (_REPO_ROOT / "Dockerfile.db").read_text(encoding="utf-8")

    assert (_REPO_ROOT / "Dockerfile.db").exists()
    assert not (_SERVER_ROOT / "Dockerfile.db").exists()
    assert "image: ${MO_DB_IMAGE:-memory-orchestrator-db:latest}" in compose
    assert "context: ." in compose
    assert "dockerfile: Dockerfile.db" in compose
    assert "SOCKS5_PROXY: ${SOCKS5_PROXY:-socks5h://172.16.10.30:1080}" in compose
    assert "http://mirrors.aliyun.com" in dockerfile
    assert "apt-get update" in dockerfile


def test_compose_passes_base_image_to_app_builds() -> None:
    compose = (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "BASE_IMAGE: ${MO_BASE_IMAGE:-memory-orchestrator-server-base:latest}" in compose


def test_http_host_is_configurable_for_container_binding(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(
            db_dsn="postgresql+asyncpg://postgres:pw@db:5432/memory_orchestrator",
            http_host="0.0.0.0",
            http_port=8765,
        ),
    )
    monkeypatch.setattr(cli, "_preflight_database", lambda: None)
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: captured.update(kwargs))

    result = CliRunner().invoke(cli.main, ["serve-http"])

    assert result.exit_code == 0
    assert captured["host"] == "0.0.0.0"
