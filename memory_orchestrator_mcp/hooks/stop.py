#!/usr/bin/env python3
"""Stop hook: trigger incremental session ingestion."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_DEFAULT_BASE_URL = "http://localhost:8765"
_COOLDOWN_SEC = 300
_MIN_TURNS = 1


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
        state_dir = _state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        with _log_path().open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _state_file(session_id: str) -> Path:
    return _state_dir() / f"stop-{session_id}.json"


def _read_state(session_id: str) -> dict:
    p = _state_file(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"last_fire_ts": 0, "last_turns": 0}


def _write_state(session_id: str, state: dict) -> None:
    try:
        _state_dir().mkdir(parents=True, exist_ok=True)
        _state_file(session_id).write_text(json.dumps(state))
    except Exception:
        pass


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


def _count_user_turns(transcript_path: str) -> int:
    if not transcript_path or not Path(transcript_path).exists():
        return 0
    count = 0
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("role") == "user" or obj.get("type") == "user":
                    count += 1
    except Exception:
        return 0
    return count


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
            n = _normalize_remote(out.stdout.strip())
            if n:
                return n
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
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except Exception:
        event = {}

    session_id = event.get("session_id") or "unknown"
    transcript_path = event.get("transcript_path") or ""
    cwd = _event_cwd(event)
    project_id = _detect_project_id(cwd)

    state = _read_state(session_id)
    now = time.time()
    turns = _count_user_turns(transcript_path)

    if now - state["last_fire_ts"] < _COOLDOWN_SEC:
        return 0
    if turns - state["last_turns"] < _MIN_TURNS:
        return 0

    body = json.dumps({
        "session_id": session_id,
        "project_slug": project_id,
        "transcript_path": transcript_path,
        "client": _client_name(),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{_base_url()}/ingest",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        _log(f"ingest post failed: {e}")
        return 0

    _write_state(session_id, {"last_fire_ts": now, "last_turns": turns})
    return 0


if __name__ == "__main__":
    sys.exit(main())
