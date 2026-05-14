from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import click


def _client_name(client_flag: str | None = None) -> str:
    if client_flag:
        return client_flag
    explicit = os.environ.get("MO_CLIENT", "").strip().lower()
    if explicit in {"codex", "claude"}:
        return explicit
    return "claude"


def _cwd() -> str:
    return (
        os.environ.get("CODEX_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )


def _settings_path() -> Path:
    """Global ~/.claude/settings.json (legacy read-only)."""
    return Path.home() / ".claude" / "settings.json"


def _claude_json_path() -> Path:
    return Path.home() / ".claude.json"


def _project_settings_path(cwd: str | None = None) -> Path:
    """Project-level .claude/settings.json — hooks only (committed)."""
    return Path(cwd or os.getcwd()) / ".claude" / "settings.json"


def _project_local_settings_path(cwd: str | None = None) -> Path:
    """Project-level .mcp.json — primary MCP config (command + env + token, not committed)."""
    return Path(cwd or os.getcwd()) / ".mcp.json"


def _read_token_from_settings() -> str:
    """Read MO_MCP_TOKEN from config files (env var is the primary source when injected by the client).

    Check order:
      1. .mcp.json      — written by setup for both Claude and Codex
      2. ~/.claude.json — legacy user-level fallback
    """
    import json

    def _token_from(data: dict) -> str:
        return (data.get("mcpServers", {})
                    .get("memory-orchestrator", {})
                    .get("env", {})
                    .get("MO_MCP_TOKEN", ""))

    cwd = _cwd()

    # 1. .mcp.json — written by setup (both Claude and Codex)
    try:
        p = _project_local_settings_path(cwd)
        if p.exists():
            token = _token_from(json.loads(p.read_text(encoding="utf-8")))
            if token:
                return token
    except Exception:
        pass

    # 2. ~/.claude.json (legacy)
    try:
        return _token_from(json.loads(_claude_json_path().read_text(encoding="utf-8")))
    except Exception:
        return ""


def _http_headers() -> dict[str, str]:
    token = _read_token_from_settings()
    if not token:
        token = (os.environ.get("MO_MCP_TOKEN") or "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _flog(msg: str) -> None:
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    log = Path.home() / ".claude" / "memory-orchestrator" / "mcp_debug.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"{ts} {msg}\n")


@click.group()
def main() -> None:
    """Memory Orchestrator MCP client CLI."""


def _hook_cmd(mcp_dir: str, name: str, client: str, base_url: str) -> str:
    return (
        f"uv run --no-sync --project {mcp_dir} "
        f"python {mcp_dir}/hooks/{name}.py --client {client} --base-url {base_url}"
    )


_AGENTS_BEGIN = "<!-- memory-orchestrator:begin -->"
_AGENTS_END = "<!-- memory-orchestrator:end -->"


def _install_agents_md(mcp_dir: Path, codex_home: Path) -> None:
    """Merge our AGENTS.md block into ~/.codex/AGENTS.md using section markers."""
    import re
    agents_src = mcp_dir / "agents" / "memory-orchestrator.AGENTS.md"
    if not agents_src.exists():
        return
    agents_dst = codex_home / "AGENTS.md"
    our_content = agents_src.read_text(encoding="utf-8").strip()
    block = f"{_AGENTS_BEGIN}\n{our_content}\n{_AGENTS_END}"
    if agents_dst.exists():
        existing = agents_dst.read_text(encoding="utf-8")
        if _AGENTS_BEGIN in existing:
            new_text = re.sub(
                rf"{re.escape(_AGENTS_BEGIN)}.*?{re.escape(_AGENTS_END)}",
                block,
                existing,
                flags=re.DOTALL,
            )
        else:
            new_text = existing.rstrip("\n") + "\n\n" + block + "\n"
    else:
        new_text = block + "\n"
    agents_dst.write_text(new_text, encoding="utf-8")


def _remove_agents_md(codex_home: Path) -> None:
    """Remove our section from ~/.codex/AGENTS.md; delete file only if it becomes empty."""
    import re
    agents_dst = codex_home / "AGENTS.md"
    if not agents_dst.exists():
        return
    text = agents_dst.read_text(encoding="utf-8")
    if _AGENTS_BEGIN not in text:
        return
    new_text = re.sub(
        rf"\n?{re.escape(_AGENTS_BEGIN)}.*?{re.escape(_AGENTS_END)}\n?",
        "",
        text,
        flags=re.DOTALL,
    ).strip("\n")
    if new_text:
        agents_dst.write_text(new_text + "\n", encoding="utf-8")
    else:
        agents_dst.unlink()
    click.echo(f"removed memory-orchestrator section from {agents_dst}")


def _setup_codex(base_url: str, mcp_dir: str, project_token: str) -> None:
    """Write ~/.codex/config.toml and ~/.codex/hooks.json for Codex."""
    import json
    import re

    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    codex_home.mkdir(parents=True, exist_ok=True)
    config_path = codex_home / "config.toml"
    hooks_path = codex_home / "hooks.json"

    # --- 1. Patch config.toml ---
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""

    text = re.sub(r"(?m)^codex_hooks\s*=.*\n?", "", text)
    if re.search(r"(?m)^\[features\]", text):
        if not re.search(r"(?m)^hooks\s*=", text):
            text = re.sub(r"(?m)^(\[features\])", r"\1\nhooks = true", text)
    else:
        text += "\n[features]\nhooks = true\n"

    filtered, skip = [], False
    for line in text.splitlines(keepends=True):
        if re.match(r"^\[mcp_servers\.memory-orchestrator", line):
            skip = True
        elif re.match(r"^\[", line) and skip:
            skip = False
        if not skip:
            filtered.append(line)
    text = "".join(filtered).rstrip() + "\n"

    text += (
        f"\n[mcp_servers.memory-orchestrator]\n"
        f'command = "uv"\n'
        f'args = ["run", "--no-sync", "--project", "{mcp_dir}", "mo-mcp", "serve-mcp", "--client", "codex"]\n'
        f"\n[mcp_servers.memory-orchestrator.env]\n"
        f'MO_CLIENT = "codex"\n'
        f'MO_HTTP_BASE_URL = "{base_url}"\n'
    )
    config_path.write_text(text, encoding="utf-8")
    click.echo(f"[1/3] config.toml: [features] hooks=true, MCP server updated")

    # --- 2. Write hooks.json ---
    hooks_data = {
        "hooks": {
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": _hook_cmd(mcp_dir, "user_prompt_submit", "codex", base_url)}]}],
            "Stop": [{"hooks": [{"type": "command", "command": _hook_cmd(mcp_dir, "stop", "codex", base_url)}]}],
        }
    }
    hooks_path.write_text(json.dumps(hooks_data, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"[2/3] hooks.json written")

    # --- 3. Write token to .mcp.json (per-project isolation) ---
    import json as _json
    mcp_json = Path(os.getcwd()) / ".mcp.json"
    mcp_data = _json.loads(mcp_json.read_text(encoding="utf-8")) if mcp_json.exists() else {}
    mcp_data.setdefault("mcpServers", {}).setdefault("memory-orchestrator", {}).setdefault("env", {}).update(
        MO_MCP_TOKEN=project_token, MO_HTTP_BASE_URL=base_url,
    )
    mcp_json.write_text(_json.dumps(mcp_data, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"[3/3] token written to .mcp.json (per-project)")

    # --- 4. Install AGENTS.md ---
    _install_agents_md(Path(mcp_dir), codex_home)
    click.echo(f"[4/4] AGENTS.md installed → {codex_home / 'AGENTS.md'}")

    click.echo("")
    click.echo("Done. Restart Codex for changes to take effect.")


@main.command(name="setup")
@click.option("--base-url", prompt="Memory Orchestrator server URL", help="e.g. http://172.16.10.124:8765")
@click.option("--project-token", prompt="Project token (create via UI or mo-server token create)", help="Bearer token bound to this project")
@click.option("--client", type=click.Choice(["claude", "codex"]), default="claude", show_default=True)
def setup(base_url: str, project_token: str, client: str) -> None:
    """Configure MCP for this project: write .claude/settings.json + store project token.

    The project token must be created in advance via the server UI or:
      mo-server token create --kind project_token --project-slug <slug> --name <label>
    """
    import json
    import shutil

    base_url = base_url.rstrip("/")
    project_token = project_token.strip()
    if not project_token:
        click.echo("ERROR: --project-token is required.", err=True)
        sys.exit(1)

    mcp_dir = str(Path(__file__).parent.resolve()).replace("\\", "/")
    cwd = os.getcwd()

    if client == "codex":
        _setup_codex(base_url, mcp_dir, project_token=project_token)
        return

    # --- Claude project-level setup ---
    import platform
    import subprocess
    _shell = platform.system() == "Windows"

    # 1. Register MCP server via claude mcp add --scope project (-e injects env into .mcp.json)
    subprocess.run(
        ["claude", "mcp", "remove", "memory-orchestrator", "--scope", "project"],
        capture_output=True, shell=_shell,
    )
    result = subprocess.run(
        [
            "claude", "mcp", "add", "memory-orchestrator",
            "--scope", "project",
            "-e", f"MO_MCP_TOKEN={project_token}",
            "-e", f"MO_HTTP_BASE_URL={base_url}",
            "--",
            "uv", "run", "--no-sync", "--project", mcp_dir,
            "mo-mcp", "serve-mcp", "--client", client,
        ],
        capture_output=True, text=True, shell=_shell,
    )
    if result.returncode != 0:
        click.echo(f"claude mcp add failed: {result.stderr.strip()}", err=True)
        sys.exit(1)
    click.echo("[1/3] claude mcp add --scope project: ok (.mcp.json updated)")

    # 2. Write hooks to project .claude/settings.json
    proj_settings = _project_settings_path(cwd)
    proj_data = json.loads(proj_settings.read_text(encoding="utf-8")) if proj_settings.exists() else {}
    proj_data.pop("mcpServers", None)
    proj_data.setdefault("hooks", {})
    proj_data["hooks"]["UserPromptSubmit"] = [{"hooks": [{"type": "command", "command": _hook_cmd(mcp_dir, "user_prompt_submit", client, base_url)}]}]
    proj_data["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": _hook_cmd(mcp_dir, "stop", client, base_url)}]}]
    proj_settings.parent.mkdir(parents=True, exist_ok=True)
    proj_settings.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"[2/3] hooks written to {proj_settings}")

    # 3. Install SKILL.md to project .claude/skills/
    skill_src = Path(mcp_dir) / "skills" / "memory-orchestrator" / "SKILL.md"
    skill_dst = Path(cwd) / ".claude" / "skills" / "memory-orchestrator" / "SKILL.md"
    if skill_src.exists():
        skill_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, skill_dst)
        click.echo(f"[3/3] SKILL.md installed → {skill_dst}")

    click.echo("")
    click.echo("Done. Open a NEW terminal / restart Claude Code for changes to take effect.")
    click.echo("Add .mcp.json to .gitignore to keep the token private.")



@main.command(name="teardown")
@click.option("--client", type=click.Choice(["claude", "codex"]), default="claude", show_default=True)
def teardown(client: str) -> None:
    """Remove Memory Orchestrator MCP wiring from this project."""
    import json
    import shutil

    if client == "codex":
        import re
        codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        config_path = codex_home / "config.toml"
        hooks_path = codex_home / "hooks.json"

        if config_path.exists():
            text = config_path.read_text(encoding="utf-8")
            filtered, skip = [], False
            for line in text.splitlines(keepends=True):
                if re.match(r"^\[mcp_servers\.memory-orchestrator", line):
                    skip = True
                elif re.match(r"^\[", line) and skip:
                    skip = False
                if not skip:
                    filtered.append(line)
            new_text = "".join(filtered)
            if new_text != text:
                config_path.write_text(new_text, encoding="utf-8")
                click.echo(f"cleaned {config_path}")

        if hooks_path.exists():
            try:
                hooks_data = json.loads(hooks_path.read_text(encoding="utf-8"))
                changed = False
                for key in ["UserPromptSubmit", "Stop"]:
                    if key in hooks_data.get("hooks", {}):
                        del hooks_data["hooks"][key]
                        changed = True
                if changed:
                    hooks_path.write_text(json.dumps(hooks_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    click.echo(f"cleaned {hooks_path}")
            except Exception as e:
                click.echo(f"hooks.json cleanup failed: {e}", err=True)

        _remove_agents_md(codex_home)

        # Clean .mcp.json token entry (Codex writes token here per-project)
        mcp_json = Path(os.getcwd()) / ".mcp.json"
        if mcp_json.exists():
            try:
                mcp_data = json.loads(mcp_json.read_text(encoding="utf-8"))
                servers = mcp_data.get("mcpServers", {})
                if "memory-orchestrator" in servers:
                    del servers["memory-orchestrator"]
                    if not servers:
                        mcp_data.pop("mcpServers", None)
                    mcp_json.write_text(json.dumps(mcp_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    click.echo(f"cleaned .mcp.json")
            except Exception as e:
                click.echo(f".mcp.json cleanup failed: {e}", err=True)

        click.echo("Done.")
        return

    # --- Claude teardown (project scope) ---
    import platform
    import subprocess
    cwd = os.getcwd()
    _shell = platform.system() == "Windows"

    subprocess.run(
        ["claude", "mcp", "remove", "memory-orchestrator", "--scope", "project"],
        capture_output=True, shell=_shell,
    )
    click.echo("mcp remove: ok")

    proj_settings = _project_settings_path(cwd)
    if proj_settings.exists():
        data = json.loads(proj_settings.read_text(encoding="utf-8"))
        changed = False
        for key in ["UserPromptSubmit", "Stop"]:
            if key in data.get("hooks", {}):
                del data["hooks"][key]
                changed = True
        if "memory-orchestrator" in data.get("mcpServers", {}):
            del data["mcpServers"]["memory-orchestrator"]
            changed = True
        if changed:
            proj_settings.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            click.echo(f"cleaned {proj_settings}")

    # Remove SKILL.md
    skill_dst = Path(cwd) / ".claude" / "skills" / "memory-orchestrator"
    if skill_dst.exists():
        shutil.rmtree(skill_dst)
        click.echo(f"removed {skill_dst}")


@main.command(name="doctor")
@click.option("--base-url", default=None, help="HTTP server URL (default: MO_HTTP_BASE_URL or http://localhost:8765)")
def doctor(base_url: str | None) -> None:
    """Check client-side MCP wiring and server reachability."""
    import json
    import urllib.request

    ok = True
    cwd = os.getcwd()
    url = (base_url or os.environ.get("MO_HTTP_BASE_URL") or "http://localhost:8765").rstrip("/")

    try:
        with urllib.request.urlopen(f"{url}/healthz", timeout=2) as r:
            data = json.loads(r.read())
            click.echo(f"healthz: {data}")
    except Exception as e:
        click.echo(f"healthz: FAIL ({e})")
        ok = False

    # Check .mcp.json for MCP server entry + token
    mcp_json = Path(cwd) / ".mcp.json"
    if mcp_json.exists():
        try:
            cfg = json.loads(mcp_json.read_text(encoding="utf-8"))
            entry = cfg.get("mcpServers", {}).get("memory-orchestrator")
            has_token = bool((entry or {}).get("env", {}).get("MO_MCP_TOKEN"))
            click.echo(f".mcp.json: {'ok' if entry else 'MISSING'}, token: {'ok' if has_token else 'MISSING'}")
            if not entry or not has_token:
                ok = False
        except Exception as e:
            click.echo(f".mcp.json parse: FAIL ({e})")
            ok = False
    else:
        click.echo(f".mcp.json: NOT FOUND (run mo-mcp setup)")
        ok = False

    proj_settings = _project_settings_path(cwd)
    if proj_settings.exists():
        try:
            cfg = json.loads(proj_settings.read_text(encoding="utf-8"))
            hooks = cfg.get("hooks", {})
            click.echo(f"project hooks: {sorted(hooks.keys())}")
        except Exception as e:
            click.echo(f"project settings parse: FAIL ({e})")

    sys.exit(0 if ok else 1)


@main.command(name="serve-mcp")
@click.option("--client", type=click.Choice(["claude", "codex"]), default=None)
def serve_mcp(client: str | None) -> None:
    """Run stdio MCP bridge to remote HTTP server."""
    if client:
        os.environ["MO_CLIENT"] = client
    asyncio.run(_run_stdio_server())


async def _run_stdio_server() -> None:
    import httpx
    import json
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Resource, ResourceTemplate, TextContent, Tool
    from memory_orchestrator_mcp.project_id import detect_project_id

    token_from_file = _read_token_from_settings()
    token_from_env = (os.environ.get("MO_MCP_TOKEN") or "").strip()
    base_url = os.environ.get("MO_HTTP_BASE_URL", "http://localhost:8765").rstrip("/")
    _flog(f"serve-mcp: start base_url={base_url} token_file={bool(token_from_file)} token_env={bool(token_from_env)}")

    if not token_from_file and not token_from_env:
        msg = (
            "MO_MCP_TOKEN is not set.\n"
            f"Run:  mo-mcp setup --client <claude|codex> --base-url {base_url} --project-token <TOKEN>\n"
            "Create a token first via the server UI or: mo-server token create --kind project_token"
        )
        _flog(f"serve-mcp: no token — {msg}")
        raise RuntimeError(msg)

    _tools: list[Tool] = [
        Tool(name="search_memory", description="Retrieve memories by semantic similarity.",
             inputSchema={"type": "object", "properties": {
                 "query": {"type": "string"}, "project_id": {"type": "string"},
                 "type": {"type": "array", "items": {"type": "string"}},
                 "top_k": {"type": "integer", "default": 3},
             }, "required": ["query"]}),
        Tool(name="save_memory", description="Write a memory to Memory Orchestrator; returns conflicts if near-duplicate exists.",
             inputSchema={"type": "object", "properties": {
                 "type": {"type": "string"}, "name": {"type": "string"},
                 "description": {"type": "string"}, "content": {"type": "string"},
                 "project_id": {"type": "string"}, "why": {"type": "string"},
                 "how_to_apply": {"type": "string"}, "importance": {"type": "integer"},
                 "replace_id": {"type": "string"},
                 "node_name": {"type": "string",
                               "description": "Skeleton leaf node name, e.g. '功能实现'"},
                 "parent_node": {"type": "string",
                                 "description": "Parent node name, e.g. '后端'. Required when node_name is ambiguous across categories."},
             }, "required": ["type", "name", "description", "content"]}),
        Tool(name="list_memories", description="List memory summaries.",
             inputSchema={"type": "object", "properties": {
                 "project_id": {"type": "string"}, "type": {"type": "string"},
                 "limit": {"type": "integer", "default": 50},
             }}),
        Tool(name="delete_memory", description="Soft or hard delete a memory.",
             inputSchema={"type": "object", "properties": {
                 "id": {"type": "string"}, "hard": {"type": "boolean"},
             }, "required": ["id"]}),
        Tool(name="promote_memory", description="Change importance or scope.",
             inputSchema={"type": "object", "properties": {
                 "id": {"type": "string"}, "importance": {"type": "integer"},
                 "make_global": {"type": "boolean"},
             }, "required": ["id"]}),
        Tool(name="ingest_session", description="Ingest transcript for auto extraction.",
             inputSchema={"type": "object", "properties": {
                 "session_id": {"type": "string"}, "project_id": {"type": "string"},
                 "transcript_path": {"type": "string"},
             }, "required": ["session_id", "transcript_path"]}),
    ]

    app = Server("memory-orchestrator")

    @app.list_tools()
    async def _list_tools() -> list[Tool]:
        return _tools

    @app.list_resources()
    async def _list_resources() -> list[Resource]:
        return [
            Resource(name="Memory Orchestrator MCP guide", uri="memory://orchestrator/guide",
                     description="Read-only guide.", mimeType="text/markdown"),
            Resource(name="Recent memories", uri="memory://recent",
                     description="Read-only summary of recent memories.", mimeType="text/markdown"),
        ]

    @app.list_resource_templates()
    async def _list_resource_templates() -> list[ResourceTemplate]:
        return [ResourceTemplate(name="Project memories", uriTemplate="memory://project/{slug}",
                                 description="Memories for a project slug.", mimeType="text/markdown")]

    @app.read_resource()
    async def _read_resource(uri) -> str:
        cwd = _cwd()
        slug = detect_project_id(cwd)
        async with httpx.AsyncClient(base_url=base_url, headers=_http_headers(), timeout=30.0, trust_env=False) as client:
            resp = await client.post("/mcp/resources/read", json={
                "uri": str(uri), "project_slug": slug, "cwd": cwd,
                "client": _client_name(),
            })
            resp.raise_for_status()
            return resp.json()["result"]

    @app.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        import uuid
        call_id = uuid.uuid4().hex[:8]
        args_log = json.dumps({k: v for k, v in arguments.items() if k != "content"}, ensure_ascii=False)[:200]
        _flog(f"[{call_id}] START tool={name} args={args_log}")
        try:
            cwd = _cwd()
            slug = detect_project_id(cwd)
            _flog(f"[{call_id}] slug={slug}")
            async with httpx.AsyncClient(
                base_url=base_url, headers=_http_headers(), timeout=30.0, trust_env=False
            ) as client:
                resp = await client.post("/mcp/tools/call", json={
                    "name": name, "arguments": arguments,
                    "project_slug": slug, "cwd": cwd,
                    "client": _client_name(),
                })
                resp.raise_for_status()
                result = resp.json()["result"]
                _flog(f"[{call_id}] OK result={type(result).__name__}")
        except Exception as e:
            _flog(f"[{call_id}] ERROR {type(e).__name__}: {e!r}")
            raise
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    main()
