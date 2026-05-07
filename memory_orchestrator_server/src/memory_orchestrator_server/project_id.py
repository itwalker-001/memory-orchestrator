from __future__ import annotations
import hashlib
import re
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


def _find_git_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _read_remote_origin(git_root: Path) -> str | None:
    config = git_root / ".git" / "config"
    if not config.exists():
        return None
    try:
        text = config.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    in_origin = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == '[remote "origin"]':
            in_origin = True
            continue
        if in_origin:
            if stripped.startswith("["):
                break
            if stripped.startswith("url"):
                parts = stripped.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return None



def detect_project_id(cwd: str | Path) -> str:
    cwd = Path(cwd)
    git_root = _find_git_root(cwd)
    if git_root is not None:
        remote = _read_remote_origin(git_root)
        if remote:
            normalized = normalize_git_remote(remote)
            if normalized:
                return normalized
        short = hashlib.sha256(str(git_root.resolve()).encode("utf-8")).hexdigest()[:8]
        return f"local:{git_root.name}-{short}"
    short = hashlib.sha256(str(cwd.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"local:{cwd.name}-{short}"


def project_id_from_path(path: str | Path) -> str:
    p = Path(path)
    short = hashlib.sha256(str(p.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"local:{short}"
