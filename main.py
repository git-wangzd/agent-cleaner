#!/usr/bin/env python3
"""Agent 会话清理工具 — 程序入口。

用法：
  python main.py          启动图形界面
  python main.py --list   仅打印扫描结果（无 GUI 环境 / 调试用）
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="跨平台 Agent 会话清理工具")
    parser.add_argument("--list", action="store_true", help="仅打印扫描结果，不启动界面")
    args = parser.parse_args()

    if args.list:
        from agent_cleaner.models import human_size
        from agent_cleaner.scanner import scan_all, summary_line

        reports = scan_all()
        print(summary_line(reports))
        for r in reports:
            print(f"\n[{r.display}] 会话数 {len(r.sessions)}  总大小 {human_size(r.total_size)}")
            for s in r.sessions:
                print(f"  {s.size_human():>10}  {s.modified_human()}  {s.name}  ->  {s.path}")
        return 0

    from agent_cleaner.app import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
