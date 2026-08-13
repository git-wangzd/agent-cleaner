"""Gemini CLI 会话扫描。

存储位置：
  ~/.gemini/tmp/<project_hash>/chats/*.json
  Windows: %USERPROFILE%\\.gemini\\tmp\\<project_hash>\\chats\\
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent


class GeminiAgent(Agent):
    id = "gemini"
    display = "Gemini CLI"
    storage_hint = "~/.gemini/tmp/<project_hash>/chats"

    def __init__(self) -> None:
        self.tmp_dir = self.resolve_root(self.home_dir() / ".gemini" / "tmp")

    def detect(self) -> bool:
        return self.tmp_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.tmp_dir) if self.tmp_dir.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if not self.tmp_dir.is_dir():
            return out
        for proj in sorted(p for p in self.tmp_dir.iterdir() if p.is_dir()):
            chats = proj / "chats"
            if not chats.is_dir():
                continue
            for f in sorted(chats.glob("*.json")):
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                out.append(
                    Session(
                        agent=self.id,
                        name=f"{proj.name[:8]}… / {f.stem}",
                        path=str(f),
                        size=self.file_size(f),
                        modified=mtime,
                        is_dir=False,
                        project=proj.name,
                    )
                )
        return out
