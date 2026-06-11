#!/usr/bin/env python3
"""Step 2b — Create a skeleton node when none fits.

Companion to fetch_skeleton.py. Reads MO_HTTP_BASE_URL / MO_MCP_TOKEN from
.mcp.json (mcpServers.memory-orchestrator.env), then POSTs to {base}/mcp/skeleton
to create (or reuse) a node. Idempotent: same name+parent returns the existing
node_id; a non-empty prompt_hint/description backfills a previously-blank node.

Stdlib only. Run:
  py create_skeleton_node.py --name 前端技术栈 --parent 技术栈 \
      --hint "记录前端框架、UI库、状态管理、构建工具的选型与版本" \
      [--desc "..."] [--mcp-json path/to/.mcp.json]
"""
import argparse, json, sys, urllib.request, urllib.error

# Windows consoles default to GBK; force UTF-8 so CJK renders.
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


def create_node(base, token, name, parent_name, prompt_hint, description):
    body = {"name": name}
    if parent_name:
        body["parent_name"] = parent_name
    if prompt_hint:
        body["prompt_hint"] = prompt_hint
    if description:
        body["description"] = description
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/mcp/skeleton",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"connection failed: {e.reason}")


def main():
    ap = argparse.ArgumentParser(description="Create or reuse a skeleton node.")
    ap.add_argument("--name", required=True, help="New node's name.")
    ap.add_argument("--parent", default="", help="Parent node's name; omit for a top-level node.")
    ap.add_argument("--hint", default="", help="prompt_hint — primary routing signal; always set this.")
    ap.add_argument("--desc", default="", help="Optional longer description of the node's scope.")
    ap.add_argument("--mcp-json", default=".mcp.json", help="Path to .mcp.json (default: ./.mcp.json).")
    args = ap.parse_args()

    if not args.hint:
        print("warning: --hint is empty; the node will be hard to route into later.", file=sys.stderr)

    base, token = load_env(args.mcp_json)
    res = create_node(base, token, args.name, args.parent, args.hint, args.desc)
    print("project_id:", res.get("project_id"))
    print("node_id:   ", res.get("node_id"))
    print(f"node '{args.name}'" + (f" under '{args.parent}'" if args.parent else " (top-level)") + " ready.")


if __name__ == "__main__":
    main()
