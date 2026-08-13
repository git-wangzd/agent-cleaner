"""生成 README 截图：启动 GUI → 等待异步扫描完成 → 截取主窗口 → 保存 PNG。

仅生成期使用（Windows，需要 Pillow）：python scripts/screenshot.py
输出：docs/screenshots/main.png
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import ImageGrab

from agent_cleaner.app import App

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots" / "main.png"


def main() -> None:
    app = App()
    app.update()

    # 等待异步扫描完成（btn_scan 恢复可用，最长 20 秒）
    deadline = time.time() + 20
    while time.time() < deadline:
        app.update()
        if "disabled" not in app.btn_scan.state():
            break
        time.sleep(0.05)
    app.update()
    app.update_idletasks()

    # 置顶并聚焦，避免截图被其他窗口遮挡（确保截到的是工具自身）
    app.lift()
    app.attributes("-topmost", True)
    app.focus_force()
    app.update()
    time.sleep(0.6)  # 等窗口置顶渲染完成

    # 计算主窗口的屏幕坐标并截取
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    w = app.winfo_width()
    h = app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    app.attributes("-topmost", False)  # 取消置顶

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"截图保存: {OUT} ({img.size[0]}x{img.size[1]})")
    app.destroy()


if __name__ == "__main__":
    main()
