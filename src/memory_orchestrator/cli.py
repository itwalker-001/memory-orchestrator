from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
import click

from memory_orchestrator.config import get_settings


@click.group()
def main() -> None:
    """Memory Orchestrator CLI."""


@main.command()
def serve() -> None:
    """Run HTTP API and MCP stdio server concurrently."""
    import uvicorn
    from memory_orchestrator.http_app import create_app
    from memory_orchestrator.mcp_server import run_stdio_server

    settings = get_settings()
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=settings.http_port, log_level=settings.log_level.lower())

    async def _main() -> None:
        server = uvicorn.Server(config)
        http_task = asyncio.create_task(server.serve())
        mcp_task = asyncio.create_task(run_stdio_server())
        done, pending = await asyncio.wait({http_task, mcp_task}, return_when=asyncio.FIRST_EXCEPTION)
        for p in pending:
            p.cancel()
        for d in done:
            d.result()

    asyncio.run(_main())


@main.command(name="serve-http")
def serve_http() -> None:
    """Run only HTTP API."""
    import logging.config
    import uvicorn
    from memory_orchestrator.http_app import create_app
    settings = get_settings()

    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = str(log_dir / "http.log")

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "default"},
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file,
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
                "formatter": "default",
            },
        },
        "root": {"handlers": ["console", "file"], "level": settings.log_level},
        "loggers": {
            "uvicorn": {"handlers": ["console", "file"], "level": settings.log_level, "propagate": False},
            "uvicorn.access": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
        },
    })

    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=settings.http_port,
        log_level=settings.log_level.lower(),
        log_config=None,
    )


@main.command(name="serve-mcp")
def serve_mcp() -> None:
    """Run only MCP stdio server."""
    from memory_orchestrator.mcp_server import run_stdio_server
    asyncio.run(run_stdio_server())


@main.command()
def doctor() -> None:
    """Check DB, embedder, and Claude settings wiring."""
    import urllib.request
    ok = True
    settings = get_settings()
    click.echo(f"config: db_dsn={settings.db_dsn}")
    click.echo(f"config: http_port={settings.http_port}")
    try:
        with urllib.request.urlopen(f"http://localhost:{settings.http_port}/healthz", timeout=1) as r:
            data = json.loads(r.read())
            click.echo(f"healthz: {data}")
    except Exception as e:
        click.echo(f"healthz: FAIL ({e})")
        ok = False
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            cfg = json.loads(settings_path.read_text(encoding="utf-8"))
            mcp = cfg.get("mcpServers", {}).get("memory-orchestrator")
            hooks = cfg.get("hooks", {})
            click.echo(f"claude mcp entry: {'ok' if mcp else 'MISSING'}")
            click.echo(f"claude hooks: {sorted(hooks.keys())}")
            if not mcp:
                ok = False
        except Exception as e:
            click.echo(f"settings parse: FAIL ({e})")
            ok = False
    else:
        click.echo("claude settings: NOT FOUND")
        ok = False
    sys.exit(0 if ok else 1)


@main.command(name="setup")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
def install_hooks(scope: str) -> None:
    """Wire hooks, mcpServers, and skill into Claude settings.json."""
    path = (Path.home() if scope == "user" else Path.cwd()) / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    hooks_dir = (Path(__file__).parent.parent.parent / "hooks").resolve()
    cfg.setdefault("hooks", {})
    project_dir = (Path(__file__).parent.parent.parent).resolve().as_posix()
    ups = (hooks_dir / "user_prompt_submit.py").as_posix()
    stp = (hooks_dir / "stop.py").as_posix()
    cfg["hooks"]["UserPromptSubmit"] = [{"hooks": [{"type": "command", "command": f"uv run --no-sync --project {project_dir} python {ups}"}]}]
    cfg["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": f"uv run --no-sync --project {project_dir} python {stp}"}]}]

    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"wrote {path}")

    # Register MCP server via claude CLI
    import subprocess as _sp
    mcp_scope = "user" if scope == "user" else "project"
    result = _sp.run(
        ["claude", "mcp", "add", "--scope", mcp_scope, "memory-orchestrator",
         "--", "uv", "run", "--no-sync", "--project", project_dir, "mo", "serve-mcp"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        click.echo(f"mcp: {result.stdout.strip()}")
    else:
        click.echo(f"mcp add failed (run manually): claude mcp add --scope {mcp_scope} memory-orchestrator -- uv run --no-sync --project {project_dir} mo serve-mcp")

    # install skill into ~/.claude/skills/memory-orchestrator/
    skill_src = (Path(__file__).parent.parent.parent / "skills" / "memory-orchestrator" / "SKILL.md").resolve()
    skill_dst = Path.home() / ".claude" / "skills" / "memory-orchestrator" / "SKILL.md"
    if skill_src.exists():
        skill_dst.parent.mkdir(parents=True, exist_ok=True)
        skill_dst.write_bytes(skill_src.read_bytes())
        click.echo(f"installed skill → {skill_dst}")
    else:
        click.echo("skill file not found, skipping")


@main.command(name="teardown")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
def uninstall_hooks(scope: str) -> None:
    """Remove hooks, mcpServers entry, and skill from Claude settings.json."""
    path = (Path.home() if scope == "user" else Path.cwd()) / ".claude" / "settings.json"
    if not path.exists():
        click.echo("nothing to remove")
        return
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for key in ("UserPromptSubmit", "Stop"):
        cfg.get("hooks", {}).pop(key, None)
    cfg.get("mcpServers", {}).pop("memory-orchestrator", None)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"cleaned {path}")


if __name__ == "__main__":
    main()
