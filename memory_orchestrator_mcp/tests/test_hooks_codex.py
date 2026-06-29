import json
import runpy
import sys
from unittest.mock import patch


def _load_hook(path: str) -> dict:
    return runpy.run_path(path, run_name="hook_under_test")


def test_user_prompt_submit_reads_codex_cwd_from_stdin(monkeypatch, tmp_path, capsys):
    module = _load_hook("hooks/user_prompt_submit.py")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", ["user_prompt_submit.py", "--client", "codex"])
    monkeypatch.setattr(sys, "stdin", _FakeStdin(json.dumps({"cwd": str(tmp_path)})))
    module["main"].__globals__["_read_token"] = lambda cwd: "tok-123"

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = "remember 中文".encode()
        assert module["main"]() == 0

    request = urlopen.call_args.args[0]
    assert "client=codex" in request.full_url
    assert "project_slug" not in request.full_url
    assert request.get_header("Authorization") == "Bearer tok-123"
    assert json.loads(capsys.readouterr().out) == {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "remember 中文",
        }
    }


def test_user_prompt_submit_keeps_claude_plain_stdout(monkeypatch, tmp_path, capsys):
    module = _load_hook("hooks/user_prompt_submit.py")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("MO_CLIENT", raising=False)
    monkeypatch.setattr(sys, "argv", ["user_prompt_submit.py"])
    monkeypatch.setattr(sys, "stdin", _FakeStdin(""))
    module["main"].__globals__["_read_token"] = lambda cwd: "tok-xyz"

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
    module = _load_hook("hooks/stop.py")
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
    module["main"].__globals__["_read_token"] = lambda cwd: "tok-123"

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
        assert module["main"]() == 0

    request = urlopen.call_args.args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert body["session_id"] == "codex-session"
    assert "project_slug" not in body
    assert request.get_header("Authorization") == "Bearer tok-123"
    assert (codex_home / "memory-orchestrator" / "stop-codex-session.json").exists()


def test_user_prompt_submit_base_url_from_mcp_json(monkeypatch, tmp_path):
    """_read_base_url reads MO_HTTP_BASE_URL from .mcp.json and overrides --base-url."""
    mcp_json = tmp_path / ".mcp.json"
    mcp_json.write_text(
        json.dumps({"mcpServers": {"memory-orchestrator": {"env": {"MO_HTTP_BASE_URL": "http://mcp-server:9999"}}}}),
        encoding="utf-8",
    )
    module = _load_hook("hooks/user_prompt_submit.py")
    monkeypatch.setattr(sys, "argv", ["user_prompt_submit.py", "--client", "claude", "--base-url", "http://wrong:1111"])
    monkeypatch.delenv("MO_HTTP_BASE_URL", raising=False)
    monkeypatch.setattr(sys, "stdin", _FakeStdin(json.dumps({"cwd": str(tmp_path)})))
    module["main"].__globals__["_read_token"] = lambda cwd: ""

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = b""
        module["main"]()

    request = urlopen.call_args.args[0]
    assert request.full_url.startswith("http://mcp-server:9999/"), request.full_url


def test_user_prompt_submit_base_url_falls_back_to_arg(monkeypatch, tmp_path):
    """Without .mcp.json, --base-url arg is used."""
    module = _load_hook("hooks/user_prompt_submit.py")
    monkeypatch.setattr(sys, "argv", ["user_prompt_submit.py", "--client", "claude", "--base-url", "http://fallback:7777"])
    monkeypatch.delenv("MO_HTTP_BASE_URL", raising=False)
    monkeypatch.setattr(sys, "stdin", _FakeStdin(json.dumps({"cwd": str(tmp_path)})))
    module["main"].__globals__["_read_token"] = lambda cwd: ""

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = b""
        module["main"]()

    request = urlopen.call_args.args[0]
    assert request.full_url.startswith("http://fallback:7777/"), request.full_url


def test_stop_base_url_from_mcp_json(monkeypatch, tmp_path):
    """Stop hook reads MO_HTTP_BASE_URL from .mcp.json."""
    mcp_json = tmp_path / ".mcp.json"
    mcp_json.write_text(
        json.dumps({"mcpServers": {"memory-orchestrator": {"env": {"MO_HTTP_BASE_URL": "http://mcp-stop:8888"}}}}),
        encoding="utf-8",
    )
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('{"role":"user"}\n', encoding="utf-8")
    module = _load_hook("hooks/stop.py")
    monkeypatch.setattr(sys, "argv", ["stop.py", "--client", "claude", "--base-url", "http://wrong:1111"])
    monkeypatch.delenv("MO_HTTP_BASE_URL", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdin", _FakeStdin(json.dumps({
        "session_id": "s1", "transcript_path": str(transcript), "cwd": str(tmp_path),
    })))
    module["main"].__globals__["_read_token"] = lambda cwd: ""

    with patch.object(module["urllib"].request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
        module["main"]()

    request = urlopen.call_args.args[0]
    assert request.full_url.startswith("http://mcp-stop:8888/"), request.full_url


class _FakeStdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text
