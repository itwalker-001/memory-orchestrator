from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memory_orchestrator_server.client_rules import (
    install_client_from_rule,
    load_client_rule,
    teardown_client_from_rule,
)


@dataclass(frozen=True)
class CodexInstallResult:
    config_path: Path
    hooks_path: Path
    agents_path: Path


def install_codex(*, home: Path, project_dir: Path, scope: str) -> CodexInstallResult:
    """Install Codex MCP, hooks, and persistent instructions."""
    result = install_client_from_rule(
        rule=load_client_rule("codex"),
        target_home=home,
        project_dir=project_dir,
        scope=scope,
    )
    if result.config_path is None or result.hooks_path is None or result.instructions_path is None:
        raise RuntimeError("codex rule did not produce all expected paths")
    return CodexInstallResult(
        config_path=result.config_path,
        hooks_path=result.hooks_path,
        agents_path=result.instructions_path,
    )


def teardown_codex(*, home: Path, project_dir: Path, scope: str) -> None:
    """Remove Memory Orchestrator entries from Codex config files."""
    teardown_client_from_rule(
        rule=load_client_rule("codex"),
        target_home=home,
        project_dir=project_dir,
        scope=scope,
    )
