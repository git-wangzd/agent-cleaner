"""跨平台系统小工具。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_in_file_manager(path: str) -> bool:
    """用系统文件管理器打开指定路径（目录或文件）。

    - Windows: os.startfile（资源管理器 / 默认关联程序）
    - macOS:   open 命令
    - Linux:   xdg-open

    路径不存在或打开失败时返回 False。
    """
    if not Path(path).exists():
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
            return True
        subprocess.Popen(["xdg-open", path])
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def reveal_target(session_path: str, is_dir: bool) -> str:
    """计算"打开路径"应打开的目标：
    - 目录会话 → 目录本身
    - 文件会话 → 其所在目录（相当于"在资源管理器中显示位置"）
    """
    p = Path(session_path)
    if is_dir:
        return str(p)
    return str(p.parent if p.parent != Path(".") else p)
