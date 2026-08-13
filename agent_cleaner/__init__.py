"""Agent 会话清理工具。

跨平台（Windows / macOS / Linux）桌面 GUI 程序，用于扫描并清理
市面上常见 AI Agent（Claude Code、Codex、Cursor、Windsurf、OpenCode、
Gemini CLI、Continue、Cline 等）在本机累积的会话数据。

设计原则：
- 纯标准库，零第三方依赖（GUI 使用 Python 自带的 Tkinter）
- 默认删除进回收站（可恢复），支持永久删除
- 删除前先扫描预览，由用户勾选要清理的会话
"""

__version__ = "0.1.0"
