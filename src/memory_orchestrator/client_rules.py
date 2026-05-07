from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuleInstallResult:
    config_path: Path | None
    hooks_path: Path | None
    instructions_path: Path | None


def load_client_rule(client: str, *, rules_dir: Path | None = None) -> dict[str, Any]:
    base = rules_dir or Path(__file__).parent.parent / "memory_orchestrator_mcp" / "client_rules"
    path = base / f"{client}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("client") != client:
        raise ValueError(f"client rule mismatch for {client}")
    return data


def install_client_from_rule(
    *,
    rule: dict[str, Any],
    target_home: Path,
    project_dir: Path,
    scope: str,
) -> RuleInstallResult:
    target_dir = _target_dir(rule=rule, target_home=target_home, project_dir=project_dir, scope=scope)
    target_dir.mkdir(parents=True, exist_ok=True)
    project_dir = project_dir.resolve()
    variables = _variables(rule=rule, project_dir=project_dir, scope=scope)

    config_path = _install_config(rule, target_dir, variables)
    hooks_path = _install_hooks(rule, target_dir, variables)
    instructions_path = _install_instructions(rule, target_dir, project_dir)
    return RuleInstallResult(
        config_path=config_path,
        hooks_path=hooks_path,
        instructions_path=instructions_path,
    )


def teardown_client_from_rule(
    *,
    rule: dict[str, Any],
    target_home: Path,
    project_dir: Path,
    scope: str,
) -> None:
    target_dir = _target_dir(rule=rule, target_home=target_home, project_dir=project_dir, scope=scope)
    config = rule.get("config")
    if isinstance(config, dict):
        _teardown_config(config, target_dir)
    hooks = rule.get("hooks")
    if isinstance(hooks, dict):
        _teardown_hooks(hooks, target_dir)


def _install_config(rule: dict[str, Any], target_dir: Path, variables: dict[str, str]) -> Path | None:
    config = rule.get("config")
    if not isinstance(config, dict):
        return None
    path = target_dir / str(config["path"])
    data = _read_config(path, str(config["format"]))
    for patch in config.get("patches", []):
        _set_nested(data, tuple(patch["path"]), _render_value(patch["value"], variables))
    _write_config(path, str(config["format"]), data)
    return path


def _install_hooks(rule: dict[str, Any], target_dir: Path, variables: dict[str, str]) -> Path | None:
    hooks = rule.get("hooks")
    if not isinstance(hooks, dict):
        return None
    path = target_dir / str(hooks["path"])
    data = _read_json_object(path)
    data.setdefault("hooks", {})
    for event_name, event_rule in hooks.get("events", {}).items():
        command = _render_command(event_rule["command"], variables)
        data["hooks"][event_name] = [
            {
                "hooks": [
                    {
                        "type": event_rule.get("type", "command"),
                        "command": command,
                    }
                ]
            }
        ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _install_instructions(
    rule: dict[str, Any],
    target_dir: Path,
    project_dir: Path,
) -> Path | None:
    instructions = rule.get("instructions")
    if not isinstance(instructions, dict):
        return None
    src = project_dir / str(instructions["source"])
    dst = target_dir / str(instructions["destination"])
    if not src.exists():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def _teardown_config(config: dict[str, Any], target_dir: Path) -> None:
    path = target_dir / str(config["path"])
    if not path.exists():
        return
    data = _read_config(path, str(config["format"]))
    for managed_path in config.get("managed_paths", []):
        _pop_nested(data, tuple(managed_path))
    _write_config(path, str(config["format"]), data)


def _teardown_hooks(hooks: dict[str, Any], target_dir: Path) -> None:
    path = target_dir / str(hooks["path"])
    if not path.exists():
        return
    data = _read_json_object(path)
    hook_map = data.get("hooks")
    if not isinstance(hook_map, dict):
        return
    for event_name, event_rule in hooks.get("events", {}).items():
        entries = hook_map.get(event_name)
        if not isinstance(entries, list):
            continue
        marker_parts = _hook_marker_parts(event_rule)
        kept = [entry for entry in entries if not _entry_contains_any(entry, marker_parts)]
        if kept:
            hook_map[event_name] = kept
        else:
            hook_map.pop(event_name, None)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _target_dir(*, rule: dict[str, Any], target_home: Path, project_dir: Path, scope: str) -> Path:
    if scope == "project":
        return project_dir / f".{rule['client']}"
    return target_home


def _variables(*, rule: dict[str, Any], project_dir: Path, scope: str) -> dict[str, str]:
    return {
        "client": str(rule["client"]),
        "project_dir": str(project_dir),
        "scope": scope,
    }


def _render_value(value: Any, variables: dict[str, str]) -> Any:
    if _looks_like_command_object(value):
        rendered = dict(value)
        rendered["command"] = _render_command(rendered["command"], variables)
        return {
            key: _render_value(item, variables) if key != "command" else item
            for key, item in rendered.items()
        }
    if isinstance(value, str):
        return value.format(**variables)
    if isinstance(value, list):
        return [_render_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, variables) for key, item in value.items()}
    return value


def _looks_like_command_object(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("type", "command") == "command"
        and isinstance(value.get("command"), list)
    )


def _render_command(command: list[str] | str, variables: dict[str, str]) -> str:
    if isinstance(command, str):
        return command.format(**variables)
    rendered = [_render_value(part, variables) for part in command]
    return subprocess.list2cmdline([str(part) for part in rendered])


def _hook_marker_parts(event_rule: dict[str, Any]) -> list[str]:
    command = event_rule.get("command")
    if isinstance(command, list):
        return [
            str(part).split("/")[-1]
            for part in command
            if str(part).endswith(".py") or str(part) in {"--client", "codex", "claude"}
        ]
    return [str(command)]


def _entry_contains_any(entry: Any, parts: list[str]) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    for hook in hooks:
        if not isinstance(hook, dict):
            continue
        command = str(hook.get("command", ""))
        if any(part and part in command for part in parts):
            return True
    return False


def _read_config(path: Path, fmt: str) -> dict[str, Any]:
    if fmt == "json":
        return _read_json_object(path)
    if fmt == "toml":
        return _read_toml_object(path)
    raise ValueError(f"unsupported config format: {fmt}")


def _write_config(path: Path, fmt: str, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return
    if fmt == "toml":
        path.write_text(_dump_toml(data), encoding="utf-8")
        return
    raise ValueError(f"unsupported config format: {fmt}")


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_toml_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    import tomllib

    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}


def _set_nested(data: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    current = data
    for key in keys[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[keys[-1]] = value


def _pop_nested(data: dict[str, Any], keys: tuple[str, ...]) -> None:
    current = data
    for key in keys[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            return
        current = child
    current.pop(keys[-1], None)


def _dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    scalar_items = {k: v for k, v in data.items() if not isinstance(v, dict)}
    table_items = {k: v for k, v in data.items() if isinstance(v, dict)}

    for key, value in scalar_items.items():
        lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    if scalar_items and table_items:
        lines.append("")

    first_table = True
    for key, value in table_items.items():
        if not first_table:
            lines.append("")
        _dump_table(lines, [key], value)
        first_table = False
    return "\n".join(lines).rstrip() + "\n"


def _dump_table(lines: list[str], path: list[str], table: dict[str, Any]) -> None:
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    nested = {k: v for k, v in table.items() if isinstance(v, dict)}
    if scalars:
        lines.append("[" + ".".join(_toml_key(p) for p in path) + "]")
        for key, value in scalars.items():
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    for key, value in nested.items():
        if scalars:
            lines.append("")
        _dump_table(lines, [*path, key], value)


def _toml_key(key: str) -> str:
    if key.replace("_", "").replace("-", "").isalnum():
        return key
    return json.dumps(key)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)
