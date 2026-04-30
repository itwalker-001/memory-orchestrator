import json
import tomllib

from click.testing import CliRunner

from memory_orchestrator.client_adapters import install_codex, teardown_codex
from memory_orchestrator.cli import main


def test_install_codex_writes_mcp_hooks_and_agent_instructions(tmp_path):
    project_dir = tmp_path / "memory orchestrator"
    project_dir.mkdir()
    (project_dir / "hooks").mkdir()
    (project_dir / "hooks" / "user_prompt_submit.py").write_text("", encoding="utf-8")
    (project_dir / "hooks" / "stop.py").write_text("", encoding="utf-8")
    (project_dir / "agents").mkdir()
    (project_dir / "agents" / "memory-orchestrator.AGENTS.md").write_text(
        "Memory Orchestrator instructions", encoding="utf-8"
    )

    codex_dir = tmp_path / "codex-home"
    home = codex_dir
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text(
        'model = "gpt-5"\n\n[features]\nother_flag = true\n',
        encoding="utf-8",
    )

    result = install_codex(home=home, project_dir=project_dir, scope="user")

    cfg = tomllib.loads((codex_dir / "config.toml").read_text(encoding="utf-8"))
    assert cfg["features"]["other_flag"] is True
    assert cfg["features"]["codex_hooks"] is True
    mcp = cfg["mcp_servers"]["memory-orchestrator"]
    assert mcp["command"] == "uv"
    assert mcp["env"]["MO_CLIENT"] == "codex"
    assert mcp["args"] == [
        "run",
        "--no-sync",
        "--project",
        str(project_dir.resolve()),
        "mo",
        "serve-mcp",
    ]

    hooks = json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8"))
    user_hook = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    stop_hook = hooks["hooks"]["Stop"][0]["hooks"][0]
    assert user_hook["type"] == "command"
    assert "user_prompt_submit.py" in user_hook["command"]
    assert "--client codex" in user_hook["command"]
    assert f'"{project_dir.resolve()}"' in user_hook["command"]
    assert stop_hook["type"] == "command"
    assert "stop.py" in stop_hook["command"]
    assert "--client codex" in stop_hook["command"]
    assert (codex_dir / "AGENTS.md").read_text(encoding="utf-8") == (
        "Memory Orchestrator instructions"
    )
    assert result.config_path == codex_dir / "config.toml"
    assert result.hooks_path == codex_dir / "hooks.json"


def test_teardown_codex_removes_managed_entries_without_disabling_other_hooks(tmp_path):
    project_dir = tmp_path / "memory-orchestrator"
    project_dir.mkdir()
    codex_dir = tmp_path / "codex-home"
    home = codex_dir
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text(
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
    (codex_dir / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "uv run --project X python user_prompt_submit.py",
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
                                    "command": "uv run --project X python stop.py",
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

    teardown_codex(home=home, project_dir=project_dir, scope="user")

    cfg = tomllib.loads((codex_dir / "config.toml").read_text(encoding="utf-8"))
    assert "memory-orchestrator" not in cfg.get("mcp_servers", {})
    assert cfg["mcp_servers"]["keep-me"]["command"] == "node"
    assert cfg["features"]["codex_hooks"] is True

    hooks = json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["hooks"]["UserPromptSubmit"] == [
        {"hooks": [{"type": "command", "command": "other"}]}
    ]
    assert "Stop" not in hooks["hooks"]


def test_cli_setup_codex_uses_adapter(monkeypatch, tmp_path):
    calls = []

    def fake_install_codex(*, home, project_dir, scope):
        calls.append((home, project_dir, scope))

        class Result:
            config_path = tmp_path / "config.toml"
            hooks_path = tmp_path / "hooks.json"
            agents_path = tmp_path / "AGENTS.md"

        return Result()

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr("memory_orchestrator.cli.install_codex", fake_install_codex)

    result = CliRunner().invoke(main, ["setup", "--client", "codex", "--scope", "user"])

    assert result.exit_code == 0
    assert calls
    assert calls[0][2] == "user"
    assert "codex config" in result.output


def test_cli_teardown_codex_uses_adapter(monkeypatch, tmp_path):
    calls = []

    def fake_teardown_codex(*, home, project_dir, scope):
        calls.append((home, project_dir, scope))

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr("memory_orchestrator.cli.teardown_codex", fake_teardown_codex)

    result = CliRunner().invoke(main, ["teardown", "--client", "codex", "--scope", "user"])

    assert result.exit_code == 0
    assert calls
    assert calls[0][2] == "user"
    assert "codex cleaned" in result.output
