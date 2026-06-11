# Memory Orchestrator MCP 安装指南

将 `memory-orchestrator-mcp` 客户端安装到本机，并为目标项目接入远程
Memory Orchestrator 服务器。

## 准备信息

开始前，准备好以下三项：

| 项目 | 说明 | 示例 |
|---|---|---|
| 服务器地址 | Memory Orchestrator 服务端 URL | `http://<server-ip>:8765` |
| 项目 token | 在服务器 UI（Admin → Tokens）创建的 `project_token` | `Fc5j...106sQ` |
| wheel 包 | 构建产物 `memory_orchestrator_mcp-<version>-py3-none-any.whl` | `dist/` 目录下 |

> 项目 token 需提前在服务器 UI（Admin → Tokens）创建，并绑定到对应项目。

---

## 1. 安装 / 升级 CLI（全局工具）

用 `uv tool install` 把 wheel 安装为全局命令 `mo-mcp`。`--force` 会覆盖已存在的旧版本。

```powershell
uv tool install --force "<path-to-wheel>\memory_orchestrator_mcp-<version>-py3-none-any.whl"
```

验证安装：

```powershell
uv tool list        # 应显示 memory-orchestrator-mcp v<version>
mo-mcp --help
```

> `mo-mcp` 安装在 `~/.local/bin/mo-mcp`。若提示找不到命令，先执行 `uv tool update-shell` 并重开终端。

---

## 2. 为目标项目接入 MCP

切换到目标项目根目录后运行 `setup`（必须在项目根目录执行——配置写入当前目录的 `.mcp.json` / `.claude/`）。

```powershell
cd <path-to-your-project>

mo-mcp setup `
  --client claude `
  --base-url http://<server-ip>:8765 `
  --project-token <your-project-token>
```

该命令会：

1. 写入 `.mcp.json`（`memory-orchestrator` MCP server + token + 服务器地址）。
2. 写入 `.claude/settings.json` 的 `UserPromptSubmit` 和 `Stop` hooks。
3. 复制 `SKILL.md` 到 `.claude/skills/memory-orchestrator/`。

> 接入 Codex 客户端：把 `--client claude` 换成 `--client codex`。

---

## 3. 验证接入

```powershell
cd <path-to-your-project>
mo-mcp doctor --base-url http://<server-ip>:8765
```

`doctor` 会检查客户端配置是否齐全、服务器是否可达、token 是否有效。

---

## 4. 安全提示

`.mcp.json` 内含项目 token，**不要提交到 git**。在目标项目的 `.gitignore` 中加入：

```
.mcp.json
```

---

## 5. 卸载 / 移除

从项目移除 MCP 接线（保留 CLI）：

```powershell
cd <path-to-your-project>
mo-mcp teardown --client claude
```

完全卸载 CLI 工具：

```powershell
uv tool uninstall memory-orchestrator-mcp
```
