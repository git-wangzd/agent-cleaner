"""Pi（earendil-works/pi）终端 AI Agent 会话扫描。

存储位置（官方文档，本机已确认目录结构）：
  ~/.pi/agent/sessions/             会话，按工作目录组织：sessions/<工作目录>/*.jsonl
  环境变量：
    PI_CODING_AGENT_DIR             覆盖配置目录（默认 ~/.pi/agent）
    PI_CODING_AGENT_SESSION_DIR     覆盖会话存储目录（优先级高于默认）

不列附属数据：~/.pi/agent 下其余为配置/凭证（settings.json、auth.json、bin），不应清理。
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Session
from .base import Agent


class PiAgent(Agent):
    id = "pi"
    display = "Pi"
    storage_hint = "~/.pi/agent/sessions (PI_CODING_AGENT_DIR 可覆盖)"
    env_var = "PI_CODING_AGENT_DIR"  # 官方支持：覆盖配置目录

    def __init__(self) -> None:
        root = self.resolve_root(self.home_dir() / ".pi" / "agent")
        self.root = root
        env_session = os.environ.get("PI_CODING_AGENT_SESSION_DIR")
        self.sessions_dir = Path(env_session) if env_session else (root / "sessions")

    def detect(self) -> bool:
        return self.sessions_dir.is_dir()

    def storage_root(self) -> str | None:
        return str(self.sessions_dir) if self.sessions_dir.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if not self.sessions_dir.is_dir():
            return out
        for f in sorted(self.sessions_dir.rglob("*.jsonl")):
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            rel = f.relative_to(self.sessions_dir)
            # 会话按工作目录组织，工作目录名 = 项目
            project = rel.parts[0] if len(rel.parts) > 1 else ""
            out.append(
                Session(
                    agent=self.id,
                    name=str(rel.parent / f.stem),
                    path=str(f),
                    size=self.file_size(f),
                    modified=mtime,
                    is_dir=False,
                    project=project,
                )
            )
        return out
