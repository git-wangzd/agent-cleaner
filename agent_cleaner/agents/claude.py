"""Claude Code 会话扫描。

存储位置（Windows 同 Linux 惯例，在用户主目录下）：
  - 旧版会话: ~/.claude/projects/<项目目录名>/*.jsonl
  - 新版会话: ~/.claude/sessions/<项目>/*.jsonl (+ 同名 .summary)
  - 相关缓存: ~/.claude/backups、cache、downloads（不清理，避免误伤）
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent


class ClaudeAgent(Agent):
    id = "claude"
    display = "Claude Code"
    storage_hint = "~/.claude/projects 与 ~/.claude/sessions"
    env_var = "CLAUDE_CONFIG_DIR"  # 官方支持：改配置/会话数据目录

    def __init__(self) -> None:
        self.root = self.resolve_root(self.home_dir() / ".claude")
        self.projects_dir = self.root / "projects"
        self.sessions_dir = self.root / "sessions"

    def detect(self) -> bool:
        return self.projects_dir.is_dir() or self.sessions_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []

        # 旧版结构：projects/<目录>/xxx.jsonl，一个文件 = 一次会话
        if self.projects_dir.is_dir():
            for proj_dir in sorted(p for p in self.projects_dir.iterdir() if p.is_dir()):
                for f in sorted(proj_dir.glob("*.jsonl")):
                    out.append(
                        Session(
                            agent=self.id,
                            name=f"{proj_dir.name} / {f.stem}",
                            path=str(f),
                            size=self.file_size(f),
                            modified=f.stat().st_mtime,
                            is_dir=False,
                            project=proj_dir.name,
                        )
                    )

        # 新版结构：sessions/<项目>/xxx.jsonl（整个项目目录作为一个条目，避免拆散 summary）
        if self.sessions_dir.is_dir():
            for proj_dir in sorted(p for p in self.sessions_dir.iterdir() if p.is_dir()):
                size = self.dir_size(proj_dir)
                if size == 0:
                    continue
                mtime = proj_dir.stat().st_mtime
                out.append(
                    Session(
                        agent=self.id,
                        name=f"项目: {proj_dir.name}",
                        path=str(proj_dir),
                        size=size,
                        modified=mtime,
                        is_dir=True,
                        project=proj_dir.name,
                    )
                )

        # 附属数据：缓存目录（保守边界：downloads/backups 不列入，避免误删用户文件）
        self._append_aux(out, self.root / "cache", "缓存 cache")
        return out

    def _append_aux(self, out: list[Session], path: Path, label: str) -> None:
        """把存在且非空的附属数据目录加进列表（kind="aux"）。"""
        if not path.is_dir():
            return
        size = self.dir_size(path)
        if size == 0:
            return
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        out.append(
            Session(
                agent=self.id,
                name=label,
                path=str(path),
                size=size,
                modified=mtime,
                is_dir=True,
                kind="aux",
            )
        )
