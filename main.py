#!/usr/bin/env python3
"""Agent 会话清理工具 — 程序入口。

用法：
  python main.py          启动图形界面
  python main.py --list   仅打印扫描结果（无 GUI 环境 / 调试用）
  python main.py --clean 30 [--permanent --yes] [--quiet]
                          无头清理：清理超过 30 天未活动的旧会话（默认进回收站），
                          可配合 cron / 任务计划程序定期执行
"""

from __future__ import annotations

import argparse
import sys


def run_clean_cli(days: int, permanent: bool = False, yes: bool = False, quiet: bool = False) -> int:
    """无头清理入口：扫描 → 计算旧会话 → 清理 → 返回退出码。

    - days: 清理超过 N 天未活动的旧会话（不含附属数据）
    - permanent: 永久删除（默认进回收站，可恢复）；必须配合 yes=True 才会执行
    - yes: 显式确认永久删除（防止脚本误删）
    - quiet: 不打印过程信息

    退出码：0=成功（含无可清理项）；1=永久删除缺少 --yes；2=清理有失败或出错。
    """
    from agent_cleaner.cleaner import clean, quick_clean_target
    from agent_cleaner.models import human_size
    from agent_cleaner.scanner import scan_all

    if permanent and not yes:
        print("永久删除不可恢复，需要显式确认：请加 --yes 参数。", file=sys.stderr)
        return 1
    try:
        reports = scan_all()
        target = quick_clean_target(reports, days)
        if not target:
            if not quiet:
                print(f"没有超过 {days} 天未活动的旧会话。")
            return 0
        total = sum(s.size for s in target)
        mode = "永久删除" if permanent else "移入回收站"
        if not quiet:
            print(f"将{mode} {len(target)} 个超过 {days} 天未活动的旧会话（约 {human_size(total)}）")
        result = clean(target, permanent=permanent)
        if not quiet:
            print(result.summary())
        return 0 if not result.failed else 2
    except Exception as e:  # 兜底：扫描/清理异常也返回非零退出码
        print(f"清理出错: {e}", file=sys.stderr)
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="跨平台 AI Agent 会话清理工具")
    parser.add_argument("--list", action="store_true", help="仅打印扫描结果，不启动界面")
    parser.add_argument("--clean", type=int, metavar="DAYS", help="无头清理：清理超过 DAYS 天未活动的旧会话（默认进回收站，不含附属数据）")
    parser.add_argument("--permanent", action="store_true", help="配合 --clean：永久删除（需 --yes 确认）")
    parser.add_argument("--yes", action="store_true", help="配合 --permanent：确认永久删除")
    parser.add_argument("--quiet", action="store_true", help="配合 --clean：不打印过程信息")
    args = parser.parse_args()

    if args.clean is not None:
        return run_clean_cli(args.clean, permanent=args.permanent, yes=args.yes, quiet=args.quiet)

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
