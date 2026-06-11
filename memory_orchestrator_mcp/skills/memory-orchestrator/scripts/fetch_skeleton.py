#!/usr/bin/env python3
"""Step 1 — Fetch the live skeleton tree.

Reads MO_HTTP_BASE_URL / MO_MCP_TOKEN from .mcp.json
(mcpServers.memory-orchestrator.env), GETs {base}/mcp/skeleton, and flattens
the nested tree to "path  ::  prompt_hint" lines so the caller can route a
memory to the node whose prompt_hint best matches its content.

Stdlib only. Run: py fetch_skeleton.py [path/to/.mcp.json]
"""
import json, sys, urllib.request, urllib.error

# Windows consoles default to GBK; force UTF-8 so CJK prompt_hints render.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def load_env(mcp_json_path):
    with open(mcp_json_path, encoding="utf-8") as f:
        cfg = json.load(f)
    env = cfg["mcpServers"]["memory-orchestrator"]["env"]
    base = env.get("MO_HTTP_BASE_URL", "").rstrip("/")
    token = env.get("MO_MCP_TOKEN", "")
    if not base or not token:
        sys.exit("missing MO_HTTP_BASE_URL / MO_MCP_TOKEN in .mcp.json")
    return base, token


def fetch_skeleton(base, token):
    req = urllib.request.Request(
        f"{base}/mcp/skeleton",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"connection failed: {e.reason}")


def flatten(nodes, prefix=""):
    """Yield (path, prompt_hint, node) for every node, depth-first."""
    for n in nodes or []:
        path = f"{prefix}/{n['name']}" if prefix else n["name"]
        yield path, (n.get("prompt_hint") or "").strip(), n
        yield from flatten(n.get("children"), path)


def main():
    mcp_json = sys.argv[1] if len(sys.argv) > 1 else ".mcp.json"
    base, token = load_env(mcp_json)
    doc = fetch_skeleton(base, token)
    print("project_id:", doc.get("project_id"))
    print("-" * 60)
    for path, hint, node in flatten(doc.get("skeleton")):
        tags = node.get("tags") or []
        print(f"{path}\n    hint: {hint or '(empty)'}\n    tags: {', '.join(tags) if tags else '(none)'}")


if __name__ == "__main__":
    main()
