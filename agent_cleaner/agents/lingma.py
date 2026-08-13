"""通义灵码（Tongyi Lingma）会话扫描（路径已在本机实测确认）。

存储位置：
  会话数据：~/.lingma/index/chat/v4/<项目>_<hash>/  （Bleve 二进制索引，
            每项目一个目录，无法拆成单条会话 → 目录粒度）
  附属数据：~/.lingma/cache、logs、tmp
  Windows: %USERPROFILE%\\.lingma\\

保守边界：index/ 下其他子目录（completion/git/graph/memory_* 等）不列入，
避免误删索引导致功能异常。
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent


class LingmaAgent(Agent):
    id = "lingma"
    display = "通义灵码"
    storage_hint = "~/.lingma/index/chat"

    def __init__(self) -> None:
        self.root = self.resolve_root(self.home_dir() / ".lingma")
        self.chat_dir = self.root / "index" / "chat"

    def detect(self) -> bool:
        return self.root.is_dir()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []

        # 会话：index/chat/v4/<项目>/（二进制索引，目录粒度）
        v4 = self.chat_dir / "v4"
        if v4.is_dir():
            for proj in sorted(p for p in v4.iterdir() if p.is_dir()):
                size = self.dir_size(proj)
                if size == 0:
                    continue
                try:
                    mtime = proj.stat().st_mtime
                except OSError:
                    mtime = 0
                out.append(
                    Session(
                        agent=self.id,
                        name=f"会话 {proj.name[:40]}",
                        path=str(proj),
                        size=size,
                        modified=mtime,
                        is_dir=True,
                    )
                )

        # 附属数据：cache / logs / tmp
        for sub, label in (("cache", "缓存 cache"), ("logs", "日志 logs"), ("tmp", "临时 tmp")):
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
