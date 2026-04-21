import hashlib
import re
import subprocess
from pathlib import Path


_SSH_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?/?$")
_HTTP_RE = re.compile(r"^https?://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$")


def normalize_git_remote(remote: str) -> str | None:
    if not remote:
        return None
    remote = remote.strip()
    m = _SSH_RE.match(remote)
    if m:
        host, path = m.group(1), m.group(2)
    else:
        m = _HTTP_RE.match(remote)
        if not m:
            return None
        host, path = m.group(1), m.group(2)
    return f"{host.lower()}/{path.lower()}"


def project_id_from_path(path: str) -> str:
    h = hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()
    return f"local:{h[:12]}"


def detect_project_id(cwd: str | Path) -> str:
    cwd = Path(cwd)
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            normalized = normalize_git_remote(result.stdout.strip())
            if normalized:
                return normalized
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return project_id_from_path(str(cwd))
