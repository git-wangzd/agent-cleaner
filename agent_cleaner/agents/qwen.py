"""Qwen Code CLI 会话扫描（路径已在本机实测确认）。

存储位置：
  ~/.qwen/projects/<项目slug>/chats/<uuid>.jsonl   （每个 jsonl = 一次会话）
  ~/.qwen/debug/                                   （附属数据：调试日志）
  Windows: %USERPROFILE%\\.qwen\\
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent


class QwenAgent(Agent):
    id = "qwen"
    display = "Qwen Code"
    storage_hint = "~/.qwen/projects/<项目>/chats"
    env_var = "QWEN_HOME"  # 官方支持（QWENLM/qwen-code PR #2953）：整体移动 ~/.qwen

    def __init__(self) -> None:
        self.root = self.resolve_root(self.home_dir() / ".qwen")
        self.projects_dir = self.root / "projects"

    def detect(self) -> bool:
        return self.projects_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if self.projects_dir.is_dir():
            for proj in sorted(p for p in self.projects_dir.iterdir() if p.is_dir()):
                chats = proj / "chats"
                if not chats.is_dir():
                    continue
                for f in sorted(chats.glob("*.jsonl")):
                    try:
                        mtime = f.stat().st_mtime
                    except OSError:
                        continue
                    out.append(
                        Session(
                            agent=self.id,
                            name=f"{proj.name} / {f.stem[:16]}",
                            path=str(f),
                            size=self.file_size(f),
                            modified=mtime,
                            is_dir=False,
                            project=proj.name,
                        )
                    )

        # 附属数据：调试日志
        dbg = self.root / "debug"
        if dbg.is_dir():
            size = self.dir_size(dbg)
            if size > 0:
                try:
                    mtime = dbg.stat().st_mtime
                except OSError:
                    mtime = 0
                out.append(
                    Session(
                        agent=self.id,
                        name="调试日志 debug",
                        path=str(dbg),
                        size=size,
                        modified=mtime,
                        is_dir=True,
                        kind="aux",
                    )
                )
        return out
