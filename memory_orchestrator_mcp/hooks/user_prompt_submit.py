#!/usr/bin/env python3
"""UserPromptSubmit hook: pre-inject memories into the active coding agent."""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_DEFAULT_BASE_URL = "http://localhost:8765"
_TIMEOUT = 2.0


def _base_url() -> str:
    if "--base-url" in sys.argv:
        idx = sys.argv.index("--base-url")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1].rstrip("/")
    return os.environ.get("MO_HTTP_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _client_name() -> str:
    if "--client" in sys.argv:
        idx = sys.argv.index("--client")
        if idx + 1 < len(sys.argv):
            value = sys.argv[idx + 1].strip().lower()
            if value in {"codex", "claude"}:
                return value
    explicit = os.environ.get("MO_CLIENT", "").strip().lower()
    if explicit in {"codex", "claude"}:
        return explicit
    return "claude"


def _state_dir() -> Path:
    if _client_name() == "codex" and os.environ.get("CODEX_HOME"):
        return Path(os.environ["CODEX_HOME"]) / "memory-orchestrator"
    return Path.home() / f".{_client_name()}" / "memory-orchestrator"


def _log_path() -> Path:
    return _state_dir() / "hook.log"


def _log(msg: str) -> None:
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _write_stdout_text(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()


def _read_event() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return event if isinstance(event, dict) else {}


def _event_cwd(event: dict) -> str:
    for key in ("cwd", "workspace_root", "workspaceRoot", "project_dir", "projectDir"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return (
        os.environ.get("CODEX_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )


def _read_token(cwd: str) -> str:
    """Read the project_token from <cwd>/.mcp.json (written by `mo-mcp setup`).

    The project is resolved server-side from this bearer token, so the hook no longer
    derives a slug from the git remote.
    """
    try:
        p = Path(cwd) / ".mcp.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            tok = (data.get("mcpServers", {})
                       .get("memory-orchestrator", {})
                       .get("env", {})
                       .get("MO_MCP_TOKEN", ""))
            if tok:
                return tok.strip()
    except Exception:
        pass
    return os.environ.get("MO_MCP_TOKEN", "").strip()


def main() -> int:
    event = _read_event()
    cwd = _event_cwd(event)
    token = _read_token(cwd)
    url = f"{_base_url()}/context?client={_client_name()}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        _log(f"context fetch failed: {e}")
        return 0
    except Exception as e:
        _log(f"unexpected hook error: {e}")
        return 0
    if body.strip():
        if _client_name() == "codex":
            _write_stdout_text(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": body,
                        }
                    },
                    ensure_ascii=False,
                )
            )
        else:
            _write_stdout_text(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
