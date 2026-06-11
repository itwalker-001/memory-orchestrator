#!/usr/bin/env python3
"""UserPromptSubmit hook: pre-inject memories into the active coding agent."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
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


def _normalize_remote(remote: str) -> str | None:
    if not remote:
        return None
    remote = remote.strip()
    ssh = re.match(r"^git@([^:]+):(.+?)(?:\.git)?/?$", remote)
    if ssh:
        return f"{ssh.group(1).lower()}/{ssh.group(2).lower()}"
    http = re.match(r"^https?://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$", remote)
    if http:
        return f"{http.group(1).lower()}/{http.group(2).lower()}"
    return None


def _detect_project_id(cwd: str) -> str:
    p = Path(cwd).resolve()
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=1,
        )
        if out.returncode == 0:
            norm = _normalize_remote(out.stdout.strip())
            if norm:
                return norm
        # git repo but no remote — find git root for stable name
        root_out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=1,
        )
        if root_out.returncode == 0:
            p = Path(root_out.stdout.strip())
    except Exception:
        pass
    short = hashlib.sha256(str(p).encode()).hexdigest()[:8]
    return f"local:{p.name}-{short}"


def main() -> int:
    event = _read_event()
    cwd = _event_cwd(event)
    project_id = _detect_project_id(cwd)
    url = f"{_base_url()}/context?project_slug={urllib.parse.quote(project_id)}&client={_client_name()}"
    try:
        req = urllib.request.Request(url)
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
