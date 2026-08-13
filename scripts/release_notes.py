#!/usr/bin/env python3
"""从 CHANGELOG.md 提取指定版本的更新内容，供 GitHub Release body 使用。

用法：
  python scripts/release_notes.py v1.0.1            # 打印该版本正文
  python scripts/release_notes.py v1.0.1 > notes.md

约定：CHANGELOG.md 中版本标题为 `## v1.0.1`（可带日期后缀），
提取到下一个 `## ` 标题或文件结尾为止。找不到版本时退出码非零。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^##\s+", re.MULTILINE)


def extract_notes(path: Path, version: str) -> str | None:
    """按版本号提取更新内容；版本不存在返回 None。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if re.match(rf"^##\s+\[?{re.escape(version)}\]?(?:\s+[-–—]\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$", line):
            start = i
            break
    if start is None:
        return None
    notes: list[str] = []
    for line in lines[start + 1:]:
        if HEADING.match(line):
            break
        notes.append(line)
    return "\n".join(notes).strip()


def main() -> int:
    if len(sys.argv) != 2:
        print(f"用法: {sys.argv[0]} <版本号，如 v1.0.1>", file=sys.stderr)
        return 2
    version = sys.argv[1]
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    notes = extract_notes(changelog, version)
    if notes is None:
        print(f"CHANGELOG.md 中未找到版本 {version} 的条目", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
