"""Codex CLI 会话扫描。

存储位置（Windows: %USERPROFILE%\\.codex，可用 CODEX_HOME 覆盖）：
  - 会话:    ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
  - 已归档:  ~/.codex/archived_sessions/...
  - 历史:    ~/.codex/history.jsonl
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Session
from .base import Agent


class CodexAgent(Agent):
    id = "codex"
    display = "Codex CLI"
    storage_hint = "~/.codex/sessions (CODEX_HOME 可覆盖)"

    def __init__(self) -> None:
        home = self.resolve_root(Path(os.environ.get("CODEX_HOME") or (self.home_dir() / ".codex")))
        self.root = home
        self.sessions_dir = home / "sessions"
        self.archived_dir = home / "archived_sessions"

    def detect(self) -> bool:
        return self.sessions_dir.is_dir() or self.archived_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def _scan_jsonl_dir(self, base: Path, prefix: str) -> list[Session]:
        """扫描一个目录树下所有 rollout-*.jsonl，一个文件 = 一次会话。"""
        out: list[Session] = []
        if not base.is_dir():
            return out
        for f in sorted(base.rglob("*.jsonl")):
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            rel = f.relative_to(base)
            out.append(
                Session(
                    agent=self.id,
                    name=f"{prefix} {rel.parent / f.stem}",
                    path=str(f),
                    size=self.file_size(f),
                    modified=mtime,
                    is_dir=False,
                )
            )
        return out

    def scan(self) -> list[Session]:
        out = self._scan_jsonl_dir(self.sessions_dir, "会话")
        out += self._scan_jsonl_dir(self.archived_dir, "归档")

        # history.jsonl 单独作为一个条目
        hf = self.root / "history.jsonl"
        if hf.is_file():
            out.append(
                Session(
                    agent=self.id,
                    name="命令历史 history.jsonl",
                    path=str(hf),
                    size=self.file_size(hf),
                    modified=hf.stat().st_mtime,
                    is_dir=False,
                )
            )

        # 附属数据：日志目录
        logs = self.root / "logs"
        if logs.is_dir():
            size = self.dir_size(logs)
            if size > 0:
                out.append(
                    Session(
                        agent=self.id,
                        name="日志 logs",
                        path=str(logs),
                        size=size,
                        modified=logs.stat().st_mtime,
                        is_dir=True,
                        kind="aux",
                    )
                )
        return out
