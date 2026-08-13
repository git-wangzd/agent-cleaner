"""Trae（字节 AI IDE）会话扫描。

Trae 是 VS Code 的 fork，存储结构与 Cursor/Windsurf 同构（推断，本机未安装验证）：
  Windows: %APPDATA%\\Trae\\User\\workspaceStorage\\<hash>\\state.vscdb
  macOS:   ~/Library/Application Support/Trae/User/workspaceStorage/<hash>/state.vscdb
  Linux:   ~/.config/Trae/User/workspaceStorage/<hash>/state.vscdb
旧版转录目录推断为 ~/.trae/projects（通常不存在，不影响）。

复用 CursorAgent 的实现，仅覆盖应用目录名。
"""

from __future__ import annotations

from .cursor import CursorAgent


class TraeAgent(CursorAgent):
    id = "trae"
    display = "Trae"
    storage_hint = "%APPDATA%\\Trae\\User\\workspaceStorage"
    app_dir_name = "Trae"

    def __init__(self) -> None:
        super().__init__()
        # 旧版转录路径与 Cursor 不同（推断）；通常不存在则扫描为空，安全
        self.transcripts_root = self.home_dir() / ".trae" / "projects"
