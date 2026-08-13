"""生成应用图标 assets/icon.ico（垃圾桶 + 绿色 ✓）。

仅生成期使用（需要 Pillow）：python scripts/make_icon.py
生成的 .ico 已提交到仓库，运行时不需要 Pillow。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"


def main() -> None:
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 垃圾桶提手
    d.rounded_rectangle([86, 36, 170, 62], radius=12, outline="#5c5c5c", width=10)
    # 桶盖
    d.rounded_rectangle([36, 62, 220, 88], radius=8, fill="#5c5c5c")
    # 桶身（梯形）
    d.polygon([(44, 88), (212, 88), (194, 226), (62, 226)], fill="#7d7d7d")
    # 桶身条纹（装饰）
    d.rectangle([84, 88, 102, 226], fill="#5c5c5c")
    d.rectangle([154, 88, 172, 226], fill="#5c5c5c")
    # 绿色 ✓（桶身上）
    d.line([(66, 146), (94, 176), (152, 106)], fill="#2ecc40", width=20, joint="curve")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"生成 {OUT}")


if __name__ == "__main__":
    main()
