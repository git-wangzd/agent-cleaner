"""Cursor 会话扫描（兼容新老版本）。

新版（当前）：会话存在 workspaceStorage 的 SQLite (state.vscdb)
  Windows: %APPDATA%\\Cursor\\User\\workspaceStorage\\<hash>\\state.vscdb
  macOS:   ~/Library/Application Support/Cursor/User/workspaceStorage/<hash>/state.vscdb
  Linux:   ~/.config/Cursor/User/workspaceStorage/<hash>/state.vscdb
  无法拆成单个会话，粒度 = 每个 workspace（一个 hash 目录 = 一个项目的工作区数据）

旧版：项目级会话转录（文本文件）
  ~/.cursor/projects/<项目>/*/agent-transcripts/*.json
  粒度 = 单会话文件
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent


class CursorAgent(Agent):
    id = "cursor"
    display = "Cursor"
    storage_hint = "%APPDATA%\\Cursor\\User\\workspaceStorage + ~/.cursor/projects"
    app_dir_name = "Cursor"  # 应用目录名（Trae 等 VS Code fork 通过继承覆盖）

    def __init__(self) -> None:
        override = self.config_override()
        base = Path(override) if override else self._base_dir()
        self.workspaces_dir = base / "User" / "workspaceStorage"
        # 旧版：~/.cursor/projects/<项目>/*/agent-transcripts/
        self.transcripts_root = self.home_dir() / ".cursor" / "projects"

    def _base_dir(self) -> Path:
        # Windows / Linux（APPDATA 与 home 不同 = Windows）
        if self.appdata_dir() != self.home_dir() or not (self.home_dir() / ".config").exists():
            ap = self.appdata_dir()
            if ap != self.home_dir():
                return ap / self.app_dir_name
        # Linux: ~/.config/<App>
        cfg = self.home_dir() / ".config" / self.app_dir_name
        if cfg.is_dir():
            return cfg
        # macOS
        mac = self.home_dir() / "Library" / "Application Support" / self.app_dir_name
        return mac

    def detect(self) -> bool:
        return self.workspaces_dir.is_dir() or self._has_transcripts()

    def storage_root(self) -> str | None:
        for p in (self.workspaces_dir, self.transcripts_root):
            if p.is_dir():
                return str(p)
        return None

    def _has_transcripts(self) -> bool:
        if not self.transcripts_root.is_dir():
            return False
        for proj in self.transcripts_root.iterdir():
            if (proj / "agent-transcripts").is_dir() or any(
                p.is_dir() and (p / "agent-transcripts").is_dir() for p in proj.iterdir()
            ):
                return True
        return False

    def scan(self) -> list[Session]:
        out: list[Session] = []

        # 新版：workspaceStorage（每工作区一个条目）
        if self.workspaces_dir.is_dir():
            for ws in sorted(p for p in self.workspaces_dir.iterdir() if p.is_dir()):
                vscdb = ws / "state.vscdb"
                if not vscdb.is_file():
                    continue
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

        # 旧版：agent-transcripts 转录文件（一个文件 = 一次会话）
        out += self._scan_transcripts()

        # 附属数据：Electron 缓存/日志（Code Cache、GPUCache、CachedData、logs 等）
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

    def _scan_transcripts(self) -> list[Session]:
        out: list[Session] = []
        if not self.transcripts_root.is_dir():
            return out
        for proj in sorted(p for p in self.transcripts_root.iterdir() if p.is_dir()):
            for tdir in sorted(p for p in proj.iterdir() if (p / "agent-transcripts").is_dir()):
                at = tdir / "agent-transcripts"
                for f in sorted(at.glob("*.json")):
                    try:
                        mtime = f.stat().st_mtime
                    except OSError:
                        continue
                    out.append(
                        Session(
                            agent=self.id,
                            name=f"旧会话 {proj.name} / {f.stem}",
                            path=str(f),
                            size=self.file_size(f),
                            modified=mtime,
                            is_dir=False,
                            project=proj.name,
                        )
                    )
        return out
