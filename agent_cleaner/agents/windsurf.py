"""Windsurf 会话扫描（结构与 Cursor 相同，目录名不同）。"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent


class WindsurfAgent(Agent):
    id = "windsurf"
    display = "Windsurf"
    storage_hint = "%APPDATA%\\Windsurf\\User\\workspaceStorage"

    def __init__(self) -> None:
        override = self.config_override()
        base = Path(override) if override else self._base_dir()
        self.workspaces_dir = base / "User" / "workspaceStorage"

    def _base_dir(self) -> Path:
        ap = self.appdata_dir()
        if ap != self.home_dir():
            return ap / "Windsurf"
        cfg = self.home_dir() / ".config" / "Windsurf"
        if cfg.is_dir():
            return cfg
        mac = self.home_dir() / "Library" / "Application Support" / "Windsurf"
        return mac

    def detect(self) -> bool:
        return self.workspaces_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.workspaces_dir) if self.workspaces_dir.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if not self.workspaces_dir.is_dir():
            return out
        for ws in sorted(p for p in self.workspaces_dir.iterdir() if p.is_dir()):
            size = self.dir_size(ws)
            if size == 0:
                continue
            out.append(
                Session(
                    agent=self.id,
                    name=f"工作区 {ws.name}",
                    path=str(ws),
                    size=size,
                    modified=ws.stat().st_mtime,
                    is_dir=True,
                    project=ws.name,
                )
            )

        # 附属数据：Electron 缓存/日志
        base = self._base_dir()
        for sub in ("Code Cache", "GPUCache", "CachedData", "logs"):
            d = base / sub
            if not d.is_dir():
                continue
            size = self.dir_size(d)
            if size == 0:
                continue
            try:
                mtime = d.stat().st_mtime
            except OSError:
                mtime = 0
            out.append(
                Session(
                    agent=self.id,
                    name=f"缓存 {sub}",
                    path=str(d),
                    size=size,
                    modified=mtime,
                    is_dir=True,
                    kind="aux",
                )
            )
        return out
