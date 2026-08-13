"""跨平台系统小工具。"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk


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


class ToolTip:
    """简单悬停提示（Tkinter 没有原生 tooltip，自己实现一个轻量的）。"""

    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)  # 无边框小窗
        tip.wm_geometry(f"+{x}+{y}")
        ttk.Label(tip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1, padding=4).pack()
        self._tip = tip

    def _hide(self, _event=None) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
