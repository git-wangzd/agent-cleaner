"""AtomCode（AtomGit 的 AI 编码助手）会话扫描。

存储位置（本机实测确认）：
  ~/.atomcode/sessions/<会话id>/<uuid>.jsonl
  每个会话一个目录（含 jsonl + meta/lease/rewind 附属文件），目录粒度清理最干净。
  环境变量：ATOMCODE_HOME 可覆盖整个数据目录。

保守边界：配置/凭证/记忆（auth.toml、config.toml、memory.md、plugins、bin 等）不列入。
附属数据：cache/、logs/。
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent


class AtomCodeAgent(Agent):
    id = "atomcode"
    display = "AtomCode"
    storage_hint = "~/.atomcode/sessions (ATOMCODE_HOME 可覆盖)"
    env_var = "ATOMCODE_HOME"

    def __init__(self) -> None:
        self.root = self.resolve_root(self.home_dir() / ".atomcode")
        self.sessions_dir = self.root / "sessions"

    def detect(self) -> bool:
        return self.sessions_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []

        # 会话：sessions/<会话id>/ 目录（含 jsonl 的才算会话）
        if self.sessions_dir.is_dir():
            for sdir in sorted(p for p in self.sessions_dir.iterdir() if p.is_dir()):
                if not list(sdir.glob("*.jsonl")):
                    continue
                size = self.dir_size(sdir)
                if size == 0:
                    continue
                try:
                    mtime = sdir.stat().st_mtime
                except OSError:
                    mtime = 0
                out.append(
                    Session(
                        agent=self.id,
                        name=f"会话 {sdir.name[:16]}",
                        path=str(sdir),
                        size=size,
                        modified=mtime,
                        is_dir=True,
                    )
                )

        # 附属数据：缓存 / 日志
        for sub, label in (("cache", "缓存 cache"), ("logs", "日志 logs")):
            d = self.root / sub
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
                    name=label,
                    path=str(d),
                    size=size,
                    modified=mtime,
                    is_dir=True,
                    kind="aux",
                )
            )
        return out
