"""Kimi CLI 会话扫描。

⚠️ 路径为推断（~/.kimi），本机未安装、官方文档暂不可达，待验证。
安全策略：
  - 只在目录存在时显示该 Agent；
  - 只扫描明确的会话子目录（sessions/history/conversations）下的 *.jsonl；
  - 找不到明确会话结构时返回空列表，绝不把整个数据目录（可能含登录凭证）
    列为可清理项。
若实际路径不同，可用自定义路径配置（config.json）覆盖。
"""

from __future__ import annotations

from pathlib import Path

from ..models import Session
from .base import Agent

# 候选的会话子目录名（推断）
_CANDIDATE_DIRS = ("sessions", "history", "conversations")


class KimiAgent(Agent):
    id = "kimi"
    display = "Kimi CLI"
    storage_hint = "~/.kimi（推断路径，可用配置覆盖）"

    def __init__(self) -> None:
        self.root = self.resolve_root(self.home_dir() / ".kimi")

    def detect(self) -> bool:
        return self.root.is_dir()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if not self.root.is_dir():
            return out
        for sub in _CANDIDATE_DIRS:
            base = self.root / sub
            if not base.is_dir():
                continue
            for f in sorted(base.rglob("*.jsonl")):
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                rel = f.relative_to(self.root)
                out.append(
                    Session(
                        agent=self.id,
                        name=str(rel.parent / f.stem),
                        path=str(f),
                        size=self.file_size(f),
                        modified=mtime,
                        is_dir=False,
                    )
                )
        return out
