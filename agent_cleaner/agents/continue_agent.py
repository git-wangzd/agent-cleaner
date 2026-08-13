"""Continue（VS Code 扩展）会话扫描。

存储位置：
  ~/.continue/sessions/<uuid>.json   （每个文件 = 一次会话）
  ~/.continue/sessions/sessions.json （索引文件，不清理）
  Windows: %USERPROFILE%\\.continue\\sessions\\
  可用 CONTINUE_GLOBAL_DIR 环境变量覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Session
from .base import Agent


class ContinueAgent(Agent):
    id = "continue"
    display = "Continue"
    storage_hint = "~/.continue/sessions"

    def __init__(self) -> None:
        home = self.resolve_root(Path(os.environ.get("CONTINUE_GLOBAL_DIR") or (self.home_dir() / ".continue")))
        self.sessions_dir = home / "sessions"

    def detect(self) -> bool:
        return self.sessions_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.sessions_dir) if self.sessions_dir.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if not self.sessions_dir.is_dir():
            return out
        for f in sorted(self.sessions_dir.glob("*.json")):
            if f.name == "sessions.json":  # 索引文件，跳过
                continue
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            out.append(
                Session(
                    agent=self.id,
                    name=f.stem,
                    path=str(f),
                    size=self.file_size(f),
                    modified=mtime,
                    is_dir=False,
                )
            )
        return out
