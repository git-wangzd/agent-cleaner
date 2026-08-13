"""Cline（VS Code 扩展）会话扫描。

存储位置（VS Code 的 globalStorage，按扩展 ID）：
  Windows: %APPDATA%\\Code\\User\\globalStorage\\saoudrizwan.claude-dev\\tasks\\<task-id>\\
  macOS:   ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/
  Linux:   ~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/
  Insiders / VSCodium 需替换 "Code" 为对应目录名。

每个任务目录 = 一次会话，粒度 = 任务。
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent

# 常见 VS Code 系编辑器的 globalStorage 父目录名（Windows 下在 APPDATA 下）
_EDITORS = ("Code", "Code - Insiders", "VSCodium")


class ClineAgent(Agent):
    id = "cline"
    display = "Cline"
    storage_hint = "%APPDATA%\\Code\\User\\globalStorage\\saoudrizwan.claude-dev"

    def __init__(self) -> None:
        override = self.config_override()
        self.root = Path(override) if override else self._find_root()

    def _find_root(self) -> Path | None:
        """在常见编辑器的 globalStorage 下找 saoudrizwan.claude-dev 目录。"""
        ap = self.appdata_dir()
        if ap != self.home_dir():
            # Windows: %APPDATA%\<Editor>\User\globalStorage\<ext>
            for editor in _EDITORS:
                p = ap / editor / "User" / "globalStorage" / "saoudrizwan.claude-dev"
                if p.is_dir():
                    return p
        # Linux
        for editor in _EDITORS:
            p = self.home_dir() / ".config" / editor / "User" / "globalStorage" / "saoudrizwan.claude-dev"
            if p.is_dir():
                return p
        # macOS
        mac = self.home_dir() / "Library" / "Application Support"
        for editor in _EDITORS:
            p = mac / editor / "User" / "globalStorage" / "saoudrizwan.claude-dev"
            if p.is_dir():
                return p
        return None

    def detect(self) -> bool:
        return self.root is not None

    def storage_root(self) -> str | None:
        return str(self.root) if self.root else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if self.root is None:
            return out
        tasks_dir = self.root / "tasks"
        if not tasks_dir.is_dir():
            return out
        for task in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
            size = self.dir_size(task)
            if size == 0:
                continue
            out.append(
                Session(
                    agent=self.id,
                    name=f"任务 {task.name[:16]}…",
                    path=str(task),
                    size=size,
                    modified=task.stat().st_mtime,
                    is_dir=True,
                )
            )

        # 附属数据：工作区快照（shadow git 仓库，可能很大）
        ck = self.root / "checkpoints"
        if ck.is_dir():
            size = self.dir_size(ck)
            if size > 0:
                out.append(
                    Session(
                        agent=self.id,
                        name="工作区快照 checkpoints",
                        path=str(ck),
                        size=size,
                        modified=ck.stat().st_mtime,
                        is_dir=True,
                        kind="aux",
                    )
                )
        return out
