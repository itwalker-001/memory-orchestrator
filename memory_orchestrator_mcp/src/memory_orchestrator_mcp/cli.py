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
    return Path.home() / ".claude" / "settings.json"


def _claude_json_path() -> Path:
    return Path.home() / ".claude.json"


def _read_token_from_settings() -> str:
    import json
    try:
        data = json.loads(_claude_json_path().read_text(encoding="utf-8"))
        return (data.get("mcpServers", {})
                    .get("memory-orchestrator", {})
                    .get("env", {})
                    .get("MO_MCP_TOKEN", ""))
    except Exception:
        return ""


def _update_claude_json_env(**kwargs: str) -> None:
    """Write env vars into ~/.claude.json's memory-orchestrator entry so Claude Code injects them."""
    import json
    p = _claude_json_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        servers = data.get("mcpServers", {})
        if "memory-orchestrator" in servers:
            servers["memory-orchestrator"].setdefault("env", {}).update(kwargs)
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        _flog(f"update_claude_json_env failed: {e!r}")



def _auto_register(base_url: str) -> str:
    """Request a mcp_client token from the server via POST /api/register."""
    import json
    import socket
    import urllib.request
    import urllib.error
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
    except Exception:
        hostname, ip = "unknown", "unknown"
    body = json.dumps({"hostname": hostname, "ip": ip, "client": _client_name()}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/register",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            result = json.loads(resp.read())
            token = result.get("token", "")
            if token:
                _flog(f"auto_register: obtained token for {result.get('name')}")
            return token
    except (urllib.error.URLError, Exception) as e:
        _flog(f"auto_register failed: {e!r}")
        return ""


def _http_headers() -> dict[str, str]:
    # File token is always most recent (written by register/setup)
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


@main.command(name="setup")
@click.option("--base-url", default="http://localhost:8765",
              help="HTTP server URL", show_default=True)
@click.option("--client", type=click.Choice(["claude", "codex"]), default="claude",
              show_default=True)
def setup(base_url: str, client: str) -> None:
    """Configure MCP on this machine: write settings.json + register token.

    Run this once on a new machine after the server is up.
    Then restart Claude Code.
    """
    import json
    import subprocess
    import sys

    base_url = base_url.rstrip("/")
    # memory_orchestrator_mcp/ package dir (3 levels up from this file)
    mcp_dir = str(Path(__file__).parent.parent.parent.resolve()).replace("\\", "/")

    # --- 1. Register MCP server via claude mcp add -------------------------
    import platform
    _shell = platform.system() == "Windows"
    subprocess.run(
        ["claude", "mcp", "remove", "memory-orchestrator", "--scope", "user"],
        capture_output=True, shell=_shell,
    )
    result = subprocess.run(
        [
            "claude", "mcp", "add", "memory-orchestrator",
            "--scope", "user",
            "--",
            "uv", "run", "--no-sync", "--project", mcp_dir,
            "mo-mcp", "serve-mcp", "--client", client,
        ],
        capture_output=True, text=True, shell=_shell,
    )
    if result.returncode != 0:
        click.echo(f"claude mcp add failed: {result.stderr.strip()}", err=True)
        sys.exit(1)
    click.echo(f"[1/3] claude mcp add: ok")

    # --- 2. Write hooks to settings.json -----------------------------------
    settings = _settings_path()
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}

    hook_cmd = lambda name: (
        f"uv run --no-sync --project {mcp_dir} "
        f"python {mcp_dir}/src/memory_orchestrator_mcp/hooks/{name}.py --client {client}"
    )
    data.setdefault("hooks", {})
    data["hooks"]["UserPromptSubmit"] = [{"hooks": [{"type": "command", "command": hook_cmd("user_prompt_submit")}]}]
    data["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": hook_cmd("stop")}]}]

    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _update_claude_json_env(MO_HTTP_BASE_URL=base_url)
    click.echo(f"[2/3] hooks written  (MO_HTTP_BASE_URL={base_url})")

    # --- 3. Register token + write to claude.json env --------------------
    token = _auto_register(base_url)
    if token:
        _update_claude_json_env(MO_MCP_TOKEN=token)
        click.echo(f"[3/3] registered token → written to ~/.claude.json env")
    else:
        click.echo("[3/3] warning: could not reach server to register token.", err=True)
        click.echo(f"      run later:  mo-mcp register --base-url {base_url}", err=True)

    click.echo("")
    click.echo("Done. Open a NEW terminal / restart Claude Code for env vars to take effect.")


@main.command(name="register")
@click.option("--base-url", default=None, help="HTTP server URL (default: MO_HTTP_BASE_URL or http://localhost:8765)")
def register(base_url: str | None) -> None:
    """Register this client with the HTTP server and save the MCP token."""
    url = (base_url or os.environ.get("MO_HTTP_BASE_URL") or "http://localhost:8765").rstrip("/")
    token = _auto_register(url)
    if token:
        _update_claude_json_env(MO_MCP_TOKEN=token, MO_HTTP_BASE_URL=url)
        click.echo(f"Registered. MO_MCP_TOKEN + MO_HTTP_BASE_URL written to ~/.claude.json env.")
    else:
        click.echo("Registration failed. Is the server running?", err=True)


@main.command(name="teardown")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
def teardown(scope: str) -> None:
    """Remove Memory Orchestrator MCP wiring from Claude Code."""
    import json
    import subprocess

    p = _settings_path()
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        changed = False
        for key in ["UserPromptSubmit", "Stop"]:
            if key in data.get("hooks", {}):
                del data["hooks"][key]
                changed = True
        if "memory-orchestrator" in data.get("mcpServers", {}):
            del data["mcpServers"]["memory-orchestrator"]
            changed = True
        if changed:
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            click.echo(f"cleaned {p}")

    import platform
    _shell = platform.system() == "Windows"
    mcp_scope = "user" if scope == "user" else "project"
    try:
        result = subprocess.run(
            ["claude", "mcp", "remove", "memory-orchestrator", "--scope", mcp_scope],
            capture_output=True, text=True, shell=_shell,
        )
        if result.returncode == 0:
            click.echo("mcp remove: ok")
    except FileNotFoundError:
        pass


@main.command(name="doctor")
@click.option("--base-url", default=None, help="HTTP server URL (default: MO_HTTP_BASE_URL or http://localhost:8765)")
def doctor(base_url: str | None) -> None:
    """Check client-side MCP wiring and server reachability."""
    import json
    import urllib.request
    import sys

    ok = True
    url = (base_url or os.environ.get("MO_HTTP_BASE_URL") or "http://localhost:8765").rstrip("/")

    try:
        with urllib.request.urlopen(f"{url}/healthz", timeout=2) as r:
            data = json.loads(r.read())
            click.echo(f"healthz: {data}")
    except Exception as e:
        click.echo(f"healthz: FAIL ({e})")
        ok = False

    p = _settings_path()
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
            mcp = cfg.get("mcpServers", {}).get("memory-orchestrator")
            hooks = cfg.get("hooks", {})
            click.echo(f"claude mcp entry: {'ok' if mcp else 'MISSING'}")
            click.echo(f"claude hooks: {sorted(hooks.keys())}")
            if not mcp:
                ok = False
        except Exception as e:
            click.echo(f"claude settings parse: FAIL ({e})")
            ok = False
    else:
        click.echo("claude settings: NOT FOUND")
        ok = False

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

    token_from_file = bool(_read_token_from_settings())
    token_from_env = bool((os.environ.get("MO_MCP_TOKEN") or "").strip())
    base_url = os.environ.get("MO_HTTP_BASE_URL", "http://localhost:8765").rstrip("/")
    _flog(f"serve-mcp: start base_url={base_url} token_file={token_from_file} token_env={token_from_env}")

    if not token_from_file and not token_from_env:
        _flog("serve-mcp: no token found, attempting auto-register")
        _auto_register(base_url)

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
