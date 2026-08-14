# 🧹 Agent 会话清理工具

> [English](README.en.md) | 中文

![CI](https://github.com/git-wangzd/agent-cleaner/actions/workflows/build.yml/badge.svg)
![Version](https://img.shields.io/badge/version-1.1.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

跨平台桌面 GUI 工具：扫描并清理各 AI Agent 在本机累积的会话与缓存数据，**默认删除进回收站（可恢复）**。

纯 Python 标准库 + Tkinter 实现，零第三方依赖。

## ✨ 特性

- 🖥️ 跨平台桌面程序（Windows / macOS / Linux）
- 🤖 支持 **16 个主流 AI Agent**（见下表）
- 🗑️ 默认删除进回收站（可恢复）；永久删除需双重确认
- 🧹 会话与附属数据（缓存/日志）分组清理，附属数据默认不勾选
- ⏱️ 时间筛选：只看超过 7 / 30 / 90 天未活动的旧会话
- 📂 项目筛选 + 🔍 会话搜索：按项目 / 关键词快速定位
- 🚀 一键清理：弹窗选择天数（默认 30 天），一次清掉所有 Agent 的旧会话
- 🔁 反选：快速翻转勾选状态
- ⚙️ 自定义路径：环境变量自动识别 + 设置界面手动配置（目录选择器）
- 📊 后台线程扫描 / 清理 + 实时进度，界面不卡顿
- 📜 清理历史：设置里可查看/清空每次清理的摘要记录
- 🔍 双击会话查看详情；右键打开存储目录
- 🔄 启动 / 手动检查更新（GitHub Releases）
- 📦 三平台自动构建与发布（GitHub Actions）

## 📸 截图

![主界面](docs/screenshots/main.png)

## 🚀 快速开始

### 方式一：下载安装包

从 [GitHub Releases](https://github.com/git-wangzd/agent-cleaner/releases) 下载对应平台的安装包（Windows / macOS / Linux），解压即可运行，无需安装 Python。安装包按平台命名：`agent-cleaner-windows.exe` / `agent-cleaner-macos` / `agent-cleaner-linux`，按文件名中的平台标识认领。

### 方式二：源码运行（需要 Python 3.10+）

```bash
python main.py          # 启动图形界面
python main.py --list   # 命令行模式：只打印扫描结果
# 无头清理（可配 cron / 任务计划程序定期执行）：
python main.py --clean 30                    # 清理超过 30 天未活动的旧会话（进回收站）
python main.py --clean 30 --permanent --yes  # 永久删除（必须显式 --yes，否则拒绝执行）
python main.py --clean 30 --quiet            # 静默模式，不打印过程信息
```

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

## 📖 使用指南

1. 启动后自动扫描本机所有 Agent
2. 勾选要清理的 Agent（整包）或勾选单个会话（可用时间 / 项目筛选 + 搜索定位）
3. 点「清理到回收站」（可恢复）或「永久删除」（双重确认）
4. 进度条实时显示，完成后自动重新扫描

### 常用操作

| 操作 | 说明 |
|---|---|
| 时间筛选 | 顶部下拉选 7/30/90 天，只显示更早未活动的旧会话 |
| 一键清理 | 选好天数后点「一键清理」，一次清掉所有 Agent 的旧会话 |
| 项目筛选 / 搜索 | 会话列表标题栏按项目过滤、按关键词搜索 |
| 查看详情 | 双击会话行弹元数据详情 |
| 打开路径 | 右键 Agent / 会话行 → 打开存储目录 |
| 设置 | 顶部「设置」按钮：路径覆盖、大文件阈值 |

## 🛡️ 安全说明

- 默认删除进回收站，可恢复；永久删除有双重确认
- 附属数据（缓存/日志）默认不勾选
- 清理 OpenCode / MimoCode 会话会操作其 SQLite 数据库，请先退出对应 Agent
- `downloads` / `backups` / 记忆文件等可能含用户数据的目录**不会被列入**

## ❓ 常见问题（FAQ）

**Q：删除的会话能恢复吗？**
A：默认「清理到回收站」可恢复；「永久删除」不可恢复（有双重确认）。

**Q：清理会话会删除我的配置吗？**
A：不会。只清理会话与缓存数据；`settings.json`、`auth`、记忆文件等配置类文件不会被列入。

**Q：Agent 的数据目录不在默认位置怎么办？**
A：两种方式：① Agent 官方环境变量（如 `CLAUDE_CONFIG_DIR`）会被自动识别；② 打开「设置」，用目录选择器指定真实路径。

**Q：清理 OpenCode / MimoCode 需要注意什么？**
A：先退出对应 Agent 再清理——它们的会话在 SQLite 数据库里，占用中删除会失败（工具会提示）。

**Q：会话很多时确认弹窗会不会很大？**
A：不会，弹窗只提示数量与预计释放空间。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request：

```bash
python -m unittest discover -s tests   # 运行单元测试（75 个）
python smoke_test.py                    # GUI 冒烟测试
```

- 新增 Agent 支持：参考 `agent_cleaner/agents/` 下现有扫描器实现
- 请保持代码风格一致（Python 标准库、中文注释、类型注解）

## 📜 更新日志

### v1.0.0（2026-08-13）

- 支持 16 个 Agent（含 Claude Code / Codex / Cursor / OpenCode / Qwen / AtomCode / MimoCode 等）
- 会话与附属数据分组清理、时间/项目筛选、搜索、一键清理、反选
- 自定义路径配置（环境变量 + 设置界面）、会话详情、右键打开路径
- 后台线程扫描/清理、实时进度、错误日志、更新检查
- 三平台自动构建与发布（GitHub Actions）、75 个单元测试

## 📄 License

[MIT](LICENSE)
