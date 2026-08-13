"""核心数据结构定义。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Session:
    """一个可清理的条目（单个文件或一个目录）。

    kind: "session"=会话数据；"aux"=附属数据（缓存/日志等，删除风险更高）。
    """

    agent: str        # Agent 标识，如 "claude"
    name: str         # 会话名（用户可读，如 "myproject-2026-08-01"）
    path: str         # 文件或目录的绝对路径
    size: int         # 占用字节数
    modified: float   # 最后修改时间戳（epoch 秒）
    is_dir: bool      # True=整个目录，False=单个文件
    kind: str = "session"  # "session" 或 "aux"
    project: str = ""  # 所属项目名（无项目概念的 Agent 为空字符串）

    def size_human(self) -> str:
        """把字节数格式化成可读字符串，如 1.5 MB。"""
        return human_size(self.size)

    def modified_human(self) -> str:
        """把时间戳格式化成 'YYYY-MM-DD HH:MM'。"""
        import datetime
        dt = datetime.datetime.fromtimestamp(self.modified)
        return dt.strftime("%Y-%m-%d %H:%M")


@dataclass
class AgentReport:
    """一个 Agent 的扫描结果汇总。"""

    agent: str                 # Agent 标识
    display: str               # Agent 显示名，如 "Claude Code"
    storage_path: str          # 存储位置说明（界面展示用）
    storage_root: str = ""     # 存储根目录的真实绝对路径（右键"打开路径"用）
    sessions: list[Session] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(s.size for s in self.sessions)

    @property
    def session_sessions(self) -> list[Session]:
        """纯会话（kind != "aux"）。"""
        return [s for s in self.sessions if s.kind != "aux"]

    @property
    def aux_sessions(self) -> list[Session]:
        """附属数据（缓存/日志等）。"""
        return [s for s in self.sessions if s.kind == "aux"]

    @property
    def session_size(self) -> int:
        return sum(s.size for s in self.session_sessions)

    @property
    def aux_size(self) -> int:
        return sum(s.size for s in self.aux_sessions)

    @property
    def exists(self) -> bool:
        return bool(self.sessions) or Path(self.storage_path).exists()


def human_size(num: int) -> str:
    """把字节数格式化成可读字符串。"""
    if num < 0:
        return "未知"
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def dir_size(path: Path) -> int:
    """递归计算目录总大小（字节）；失败时返回 0。"""
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total
