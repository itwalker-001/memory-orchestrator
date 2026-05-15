from pathlib import Path

from memory_orchestrator_server.db_check import REQUIRED_COLUMNS
from memory_orchestrator_server import models


_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_schema_no_longer_requires_memory_links() -> None:
    assert "memory_links" not in REQUIRED_COLUMNS
    assert not hasattr(models, "MemoryLink")


def test_migration_scripts_no_longer_reference_memory_links() -> None:
    for rel_path in [
        "alembic/versions/0001_initial.py",
        "alembic/versions/0010_age_extension.py",
        "tests/integration/conftest.py",
    ]:
        text = (_ROOT / rel_path).read_text(encoding="utf-8")
        assert "memory_links" not in text
