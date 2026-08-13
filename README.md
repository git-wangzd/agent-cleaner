# Agent 会话清理工具 / Agent Session Cleaner

跨平台桌面 GUI 工具：扫描并清理各 AI Agent 在本机累积的会话与缓存数据，默认删除进回收站（可恢复）。

A cross-platform desktop GUI tool to scan and clean up session and cache data accumulated by various AI agents. Deletion goes to the recycle bin / trash by default (recoverable).

## 特性 / Features

- 🖥️ 跨平台桌面程序（Windows / macOS / Linux），纯 Python 标准库 + Tkinter，零第三方依赖
- 🤖 支持 13 个 Agent：Claude Code、Codex CLI、Cursor、Windsurf、OpenCode、Gemini CLI、Continue、Cline、Qwen Code、Kimi CLI、通义灵码、Trae、MarsCode CLI
- 🆕 新老版本存储结构兼容（OpenCode SQLite/文件、Cursor workspaceStorage/转录、Claude projects/sessions 等）
- 🗑️ 默认删除进回收站（可恢复），支持永久删除（双重确认）
- 🧹 会话与附属数据（缓存/日志）分组清理，附属数据默认不勾选 + 加强确认
- ⏱️ 时间筛选：只显示超过 7/30/90 天未活动的旧会话
- ⚙️ 自定义路径配置：`%APPDATA%\agent-cleaner\config.json` 可覆盖/纠正任意 Agent 的数据路径
- 🔍 双击会话查看元数据详情；右键打开存储目录
- 📊 后台线程清理 + 实时进度条，不卡界面

## 运行 / Run

需要 Python 3.10+（自带 Tkinter）：

```bash
python main.py          # 启动图形界面
python main.py --list   # 命令行模式，只打印扫描结果
```

打包为单文件 exe（PyInstaller）：`pyinstaller --onefile --windowed --name agent-cleaner main.py`；或直接下载 CI 构建产物（GitHub Actions 三平台自动构建）。

## 支持的 Agent 与存储位置 / Supported Agents

| Agent | 存储位置（Windows） | 粒度 |
|---|---|---|
| Claude Code | `%USERPROFILE%\.claude\projects` + `sessions` | 单会话 |
| Codex CLI | `%USERPROFILE%\.codex\sessions` + `archived_sessions` | 单会话 |
| Cursor | `%APPDATA%\Cursor\User\workspaceStorage` | 工作区 |
| Windsurf | `%APPDATA%\Windsurf\User\workspaceStorage` | 工作区 |
| OpenCode | `%USERPROFILE%\.local\share\opencode`（SQLite 或文件） | 单会话 |
| Gemini CLI | `%USERPROFILE%\.gemini\tmp` | 单会话 |
| Continue | `%USERPROFILE%\.continue\sessions` | 单会话 |
| Cline | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev` | 单任务 |
| Qwen Code | `%USERPROFILE%\.qwen\projects` | 单会话 |
| Kimi CLI | `%USERPROFILE%\.kimi`（推断路径） | 单会话 |
| 通义灵码 | `%USERPROFILE%\.lingma\index\chat` | 项目目录 |
| Trae | `%APPDATA%\Trae\User\workspaceStorage` | 工作区 |
| MarsCode CLI | `%USERPROFILE%\.marscode`（推断路径） | 单会话 |

> 标注"推断路径"的 Agent 尚未在实际环境验证，可用自定义路径配置（见下）纠正。

## 自定义路径配置 / Custom Path Config

编辑 `%APPDATA%\agent-cleaner\config.json`（Linux/macOS 为 `~/.config/agent-cleaner/config.json`）：

```json
{
  "agent_paths": {
    "kimi": "D:/my/kimi-data",
    "claude": "C:/data/claude"
  }
}
```

## 使用流程 / Usage

1. 启动后自动扫描本机所有 Agent
2. 勾选要清理的 Agent（整包清理）或在会话列表中勾选单个会话
3. 点"清理到回收站"（可恢复）或"永久删除"（不可恢复，双重确认）
4. 进度条实时显示处理进度，完成后自动重新扫描

## 安全说明 / Safety

- 默认删除进回收站，可恢复；永久删除前有双重确认
- 附属数据（缓存/日志等）默认不勾选，清理含附属数据时加强确认
- 清理 OpenCode 会话会直接操作其 SQLite 数据库，请先退出 opencode
- `downloads`/`backups` 等可能含用户文件的目录**不会**被列入

## 开发 / Development

```bash
python -m unittest discover -s tests   # 单元测试
python smoke_test.py                    # GUI 冒烟测试
```

## License

[MIT](LICENSE)
