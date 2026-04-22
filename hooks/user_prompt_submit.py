#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: pre-inject memories into system prompt."""
from __future__ import annotations
import hashlib
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_DEFAULT_PORT = int(os.environ.get("MO_HTTP_PORT", "8765"))
_TIMEOUT = 2.0
_LOG_PATH = Path.home() / ".claude" / "memory-orchestrator" / "hook.log"


def _log(msg: str) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


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
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=1,
        )
        if out.returncode == 0:
            norm = _normalize_remote(out.stdout.strip())
            if norm:
                return norm
    except Exception:
        pass
    h = hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()
    return f"local:{h[:12]}"


def main() -> int:
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    project_id = _detect_project_id(cwd)
    url = f"http://localhost:{_DEFAULT_PORT}/context?project_id={urllib.parse.quote(project_id)}&budget_tokens=1500"
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
        sys.stdout.write(body)
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
