# 更新日志

所有重要变更按版本记录。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
GitHub Release 的正文由 `scripts/release_notes.py` 从本文件按版本提取，无需跳转查看。

## v1.2.0 - 2026-08-18

### 新增
- 支持 ZCode（智谱 Z.ai）：会话（`~/.zcode/cli/db/db.sqlite`，SQLite）与终端输出缓存
  （`~/.zcode/cli/exec`，官方确认可整删），Agent 总数 16 → 17。
- ZCode 会话删除走通用 SQLite 逻辑，同步清理 model_usage / tool_usage 关联数据。

### 测试
- 新增 ZCode 扫描（含防御式列探测）、环境变量覆盖、SQLite 关联删除的单元测试。

## v1.1.0 - 2026-08-14

### 新增
- 无头清理 CLI：`python main.py --clean <天数> [--permanent --yes] [--quiet]`，
  可配合 cron / 任务计划程序定期清理旧会话；永久删除必须显式 `--yes` 才会执行。
- 清理历史：每次清理成功记录摘要（时间 / 回收站或永久 / 数量 / 释放空间 / 涉及 Agent），
  设置对话框内可查看与清空；不记录具体路径，避免历史文件成为隐私泄露点。

### 改进
- 一键清理改为独立弹窗选择天数（默认 30 天），不再依赖顶部时间筛选控件，
  弹窗内实时预览将清理的会话数与释放空间。
- Agent 汇总表按占用空间降序排列（吃空间最多的排最前）；存储位置列缩窄，完整路径见详情/右键。

### 测试
- 新增清理历史读写、无头清理 CLI 的单元测试（84 个用例）。

## v1.0.1 - 2026-08-13

### 修复
- 一键清理按钮点击无反应：`_quick_clean` 调用了不存在的方法 `_filter_days`，
  异常被 Tkinter 静默吞掉，界面无任何提示。改为直接读取时间筛选属性。

### 改进
- 构建产物按平台命名：`agent-cleaner-windows.exe` / `agent-cleaner-macos` /
  `agent-cleaner-linux`，三平台包不再同名互相覆盖。
- 检测到新版本时，更新提示直接给出下载地址，无需跳转 GitHub Releases 页面。
- Release 重发（重打同名 tag）时自动删除旧 Release，避免残留旧命名资产。

### 文档
- 更新主界面截图；移除 README 截图占位说明与「配置」章节（设置界面已覆盖）。

## v1.0.0 - 2026-08-13

### 新增
- 首个正式版本，支持 16 个 AI Agent（Claude Code / Codex / Cursor / Windsurf /
  OpenCode / Gemini / Continue / Cline / Qwen / Kimi / 通义灵码 / Trae / MarsCode /
  Pi / AtomCode / MimoCode）的本地会话与缓存扫描、清理。
- 会话与附属数据（缓存/日志）分组清理，附属数据默认不勾选；默认删除进回收站（可恢复），
  永久删除有双重确认。
- 时间筛选（7/30/90 天）、项目筛选、会话搜索、一键清理、反选。
- 自定义路径配置（Agent 官方环境变量自动识别 + 设置界面目录选择器）。
- 双击会话查看详情；右键打开存储目录。
- 后台线程扫描/清理、实时进度、错误日志、启动/手动检查更新。
- 三平台自动构建与发布（GitHub Actions）、75 个单元测试。
