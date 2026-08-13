# 🧹 Agent 会话清理工具

> [English](README.en.md) | 中文

跨平台桌面 GUI 工具：扫描并清理各 AI Agent 在本机累积的会话与缓存数据，**默认删除进回收站（可恢复）**。

纯 Python 标准库 + Tkinter 实现，零第三方依赖。

## ✨ 特性

- 🖥️ 跨平台桌面程序（Windows / macOS / Linux）
- 🤖 支持 **16 个主流 AI Agent**（见下表）
- 🗑️ 默认删除进回收站（可恢复）；永久删除需双重确认
- 🧹 会话与附属数据（缓存/日志）分组清理，附属数据默认不勾选
- ⏱️ 时间筛选：只看超过 7 / 30 / 90 天未活动的旧会话
- 📂 项目筛选 + 🔍 会话搜索：按项目 / 关键词快速定位
- 🚀 一键清理：按天数一次清掉所有 Agent 的旧会话
- 🔁 反选：快速翻转勾选状态
- ⚙️ 自定义路径：环境变量自动识别 + 设置界面手动配置（目录选择器）
- 📊 后台线程扫描 / 清理 + 实时进度，界面不卡顿
- 🔍 双击会话查看详情；右键打开存储目录
- 🔄 启动 / 手动检查更新（GitHub Releases）
- 📦 三平台自动构建（GitHub Actions）

## 🤖 支持的 Agent

| Agent | 存储位置（Windows） |
|---|---|
| Claude Code | `%USERPROFILE%\.claude\projects` + `sessions` |
| Codex CLI | `%USERPROFILE%\.codex\sessions` |
| Cursor | `%APPDATA%\Cursor\User\workspaceStorage` |
| Windsurf | `%APPDATA%\Windsurf\User\workspaceStorage` |
| OpenCode | `%USERPROFILE%\.local\share\opencode`（SQLite / 文件） |
| Gemini CLI | `%USERPROFILE%\.gemini\tmp` |
| Continue | `%USERPROFILE%\.continue\sessions` |
| Cline | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev` |
| Qwen Code | `%USERPROFILE%\.qwen\projects` |
| Kimi CLI | `%USERPROFILE%\.kimi` |
| 通义灵码 | `%USERPROFILE%\.lingma\index\chat` |
| Trae | `%APPDATA%\Trae\User\workspaceStorage` |
| MarsCode CLI | `%USERPROFILE%\.marscode` |
| Pi | `%USERPROFILE%\.pi\agent\sessions` |
| AtomCode | `%USERPROFILE%\.atomcode\sessions` |
| MimoCode | `%USERPROFILE%\.local\share\mimocode`（SQLite） |

## 📥 安装与运行

### 下载安装包
从 [GitHub Releases](https://github.com/git-wangzd/agent-cleaner/releases) 下载对应平台的安装包（Windows / macOS / Linux），解压即可运行。

### 源码运行（需要 Python 3.10+）

```bash
python main.py          # 启动图形界面
python main.py --list   # 命令行模式：只打印扫描结果
```

## 📖 使用流程

1. 启动后自动扫描本机所有 Agent
2. 勾选要清理的 Agent（整包）或勾选单个会话（可用时间 / 项目筛选 + 搜索定位）
3. 点「清理到回收站」（可恢复）或「永久删除」（双重确认）
4. 进度条实时显示，完成后自动重新扫描

## ⚙️ 配置

配置文件位于 `%APPDATA%\agent-cleaner\config.json`（Linux/macOS 为 `~/.config/agent-cleaner/config.json`）：

```json
{
  "agent_paths": {
    "kimi": "D:/my/kimi-data"
  },
  "big_file_mb": 10
}
```

- **agent_paths**：覆盖某个 Agent 的数据目录（也可在设置界面用目录选择器配置）
- **big_file_mb**：大文件标红阈值（默认 10 MB，设置界面可改）
- Agent 官方环境变量（如 `CLAUDE_CONFIG_DIR`、`QWEN_HOME`、`ATOMCODE_HOME` 等）会自动识别

## 🛡️ 安全说明

- 默认删除进回收站，可恢复；永久删除有双重确认
- 附属数据（缓存/日志）默认不勾选
- 清理 OpenCode / MimoCode 会话会操作其 SQLite 数据库，请先退出对应 Agent
- `downloads` / `backups` / 记忆文件等可能含用户数据的目录**不会被列入**

## 🧪 开发

```bash
python -m unittest discover -s tests   # 单元测试（74 个）
python smoke_test.py                    # GUI 冒烟测试
```

## 📄 License

[MIT](LICENSE)

---

**v1.0.0**：16 个 Agent 支持、完整清理生态、74 个单元测试、三平台自动构建与发布。
