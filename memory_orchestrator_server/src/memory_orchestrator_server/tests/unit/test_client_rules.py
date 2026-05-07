import json
import tomllib
from unittest.mock import patch

from click.testing import CliRunner

from memory_orchestrator_server.cli import main
from memory_orchestrator_server.client_rules import (
    RuleInstallResult,
    install_client_from_rule,
    load_client_rule,
    teardown_client_from_rule,
)


def test_load_client_rule_reads_physical_rule_file():
    rule = load_client_rule("codex")

    assert rule["client"] == "codex"
    assert rule["config"]["path"] == "config.toml"
    assert rule["hooks"]["path"] == "hooks.json"


def test_install_codex_from_rule_writes_config_hooks_and_instructions(tmp_path):
    project_dir = tmp_path / "memory orchestrator"
    project_dir.mkdir()
    (project_dir / "src" / "memory_orchestrator_mcp" / "agents").mkdir(parents=True)
    (project_dir / "src" / "memory_orchestrator_mcp" / "agents" / "memory-orchestrator.AGENTS.md").write_text(
        "Codex instructions", encoding="utf-8"
    )
    target_home = tmp_path / "codex-home"
    target_home.mkdir()
    (target_home / "config.toml").write_text(
        'model = "gpt-5"\n\n[features]\nother_flag = true\n',
        encoding="utf-8",
    )

    result = install_client_from_rule(
        rule=load_client_rule("codex"),
        target_home=target_home,
        project_dir=project_dir,
        scope="user",
    )

    assert isinstance(result, RuleInstallResult)
    cfg = tomllib.loads((target_home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["features"]["other_flag"] is True
    assert cfg["features"]["codex_hooks"] is True
    assert cfg["mcp_servers"]["memory-orchestrator"]["env"]["MO_CLIENT"] == "codex"
    hooks = json.loads((target_home / "hooks.json").read_text(encoding="utf-8"))
    user_command = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "user_prompt_submit.py" in user_command
    assert "--client codex" in user_command
    assert f'"{project_dir.resolve()}"' in user_command
    assert (target_home / "AGENTS.md").read_text(encoding="utf-8") == "Codex instructions"
    assert result.config_path == target_home / "config.toml"
    assert result.hooks_path == target_home / "hooks.json"
    assert result.instructions_path == target_home / "AGENTS.md"


def test_teardown_codex_from_rule_removes_only_managed_entries(tmp_path):
    project_dir = tmp_path / "memory-orchestrator"
    project_dir.mkdir()
    target_home = tmp_path / "codex-home"
    target_home.mkdir()
    (target_home / "config.toml").write_text(
        "\n".join(
            [
                "[features]",
                "codex_hooks = true",
                "",
                "[mcp_servers.memory-orchestrator]",
                'command = "uv"',
                'args = ["run"]',
                "",
                "[mcp_servers.keep-me]",
                'command = "node"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (target_home / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "uv run --project X python user_prompt_submit.py --client codex",
                                }
                            ]
                        },
                        {"hooks": [{"type": "command", "command": "other"}]},
                    ],
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "uv run --project X python stop.py --client codex",
                                }
                            ]
                        }
                    ],
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    teardown_client_from_rule(
        rule=load_client_rule("codex"),
        target_home=target_home,
        project_dir=project_dir,
        scope="user",
    )

    cfg = tomllib.loads((target_home / "config.toml").read_text(encoding="utf-8"))
    assert "memory-orchestrator" not in cfg["mcp_servers"]
    assert cfg["mcp_servers"]["keep-me"]["command"] == "node"
    hooks = json.loads((target_home / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["hooks"]["UserPromptSubmit"] == [
        {"hooks": [{"type": "command", "command": "other"}]}
    ]
    assert "Stop" not in hooks["hooks"]


def test_install_claude_from_rule_writes_settings_and_skill(tmp_path):
    project_dir = tmp_path / "memory orchestrator"
    project_dir.mkdir()
    (project_dir / "src" / "memory_orchestrator_mcp" / "skills" / "memory-orchestrator").mkdir(parents=True)
    (project_dir / "src" / "memory_orchestrator_mcp" / "skills" / "memory-orchestrator" / "SKILL.md").write_text(
        "Claude skill", encoding="utf-8"
    )
    target_home = tmp_path / "claude-home"
    target_home.mkdir()

    result = install_client_from_rule(
        rule=load_client_rule("claude"),
        target_home=target_home,
        project_dir=project_dir,
        scope="user",
    )

    cfg = json.loads((target_home / "settings.json").read_text(encoding="utf-8"))
    assert "UserPromptSubmit" in cfg["hooks"]
    user_command = cfg["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "user_prompt_submit.py" in user_command
    assert "--client claude" in user_command
    assert cfg["mcpServers"]["memory-orchestrator"]["env"]["MO_CLIENT"] == "claude"
    assert (
        target_home / "skills" / "memory-orchestrator" / "SKILL.md"
    ).read_text(encoding="utf-8") == "Claude skill"
    assert result.config_path == target_home / "settings.json"
    assert result.hooks_path is None


def test_teardown_claude_from_rule_removes_hooks_and_mcp(tmp_path):
    project_dir = tmp_path / "memory-orchestrator"
    project_dir.mkdir()
    target_home = tmp_path / "claude-home"
    target_home.mkdir()
    (target_home / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "ours"}]}],
                    "Stop": [{"hooks": [{"type": "command", "command": "ours"}]}],
                    "Other": [{"hooks": [{"type": "command", "command": "keep"}]}],
                },
                "mcpServers": {
                    "memory-orchestrator": {"command": "uv"},
                    "keep-me": {"command": "node"},
                },
            }
        ),
        encoding="utf-8",
    )

    teardown_client_from_rule(
        rule=load_client_rule("claude"),
        target_home=target_home,
        project_dir=project_dir,
        scope="user",
    )

    cfg = json.loads((target_home / "settings.json").read_text(encoding="utf-8"))
    assert "UserPromptSubmit" not in cfg["hooks"]
    assert "Stop" not in cfg["hooks"]
    assert cfg["hooks"]["Other"][0]["hooks"][0]["command"] == "keep"
    assert "memory-orchestrator" not in cfg["mcpServers"]
    assert cfg["mcpServers"]["keep-me"]["command"] == "node"


def test_cli_setup_claude_survives_missing_claude_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    with patch("memory_orchestrator_server.cli.subprocess.run", side_effect=FileNotFoundError):
        result = CliRunner().invoke(main, ["setup", "--client", "claude", "--scope", "user"])

    assert result.exit_code == 0
    assert "mcp add failed" in result.output
    assert (tmp_path / ".claude" / "settings.json").exists()
