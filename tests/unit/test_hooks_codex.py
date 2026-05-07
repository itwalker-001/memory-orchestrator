import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch


def _load_hook(path: str) -> dict:
    return runpy.run_path(path, run_name="hook_under_test")


def test_user_prompt_submit_reads_codex_cwd_from_stdin(monkeypatch, tmp_path, capsys):
    module = _load_hook("src/memory_orchestrator_mcp/hooks/user_prompt_submit.py")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", ["user_prompt_submit.py", "--client", "codex"])
    monkeypatch.setattr(sys, "stdin", _FakeStdin(json.dumps({"cwd": str(tmp_path)})))
    module["main"].__globals__["_detect_project_id"] = lambda cwd: f"pid:{Path(cwd).name}"

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = "remember 中文".encode()
        assert module["main"]() == 0

    requested = urlopen.call_args.args[0].full_url
    assert "project_slug=pid%3A" in requested
    assert json.loads(capsys.readouterr().out) == {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "remember 中文",
        }
    }


def test_user_prompt_submit_keeps_claude_plain_stdout(monkeypatch, tmp_path, capsys):
    module = _load_hook("src/memory_orchestrator_mcp/hooks/user_prompt_submit.py")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("MO_CLIENT", raising=False)
    monkeypatch.setattr(sys, "argv", ["user_prompt_submit.py"])
    monkeypatch.setattr(sys, "stdin", _FakeStdin(""))
    module["main"].__globals__["_detect_project_id"] = lambda cwd: "github.com/a/b"

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = "plain 中文".encode()
        assert module["main"]() == 0

    assert capsys.readouterr().out == "plain 中文"


def test_stop_reads_codex_cwd_and_state_dir(monkeypatch, tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text('{"role":"user","content":"hello"}\n', encoding="utf-8")
    codex_home = tmp_path / "codex-home"
    codex_cwd = tmp_path / "repo"
    codex_cwd.mkdir()
    module = _load_hook("src/memory_orchestrator_mcp/hooks/stop.py")
    monkeypatch.setattr(sys, "argv", ["stop.py", "--client", "codex"])
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(
        sys,
        "stdin",
        _FakeStdin(
            json.dumps(
                {
                    "session_id": "codex-session",
                    "transcript_path": str(transcript),
                    "cwd": str(codex_cwd),
                }
            )
        ),
    )
    module["main"].__globals__["_detect_project_id"] = lambda cwd: f"pid:{Path(cwd).name}"

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
        assert module["main"]() == 0

    body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
    assert body["session_id"] == "codex-session"
    assert body["project_slug"] == "pid:repo"
    assert (codex_home / "memory-orchestrator" / "stop-codex-session.json").exists()


class _FakeStdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text
