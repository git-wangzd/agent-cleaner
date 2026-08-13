"""扫描汇总：遍历所有 Agent，收集会话列表。"""

from __future__ import annotations

from .models import AgentReport
from .registry import all_agents


def scan_all() -> list[AgentReport]:
    """扫描全部 Agent，返回每个 Agent 的报告（只包含实际存在的）。

    只读操作，不会删除任何东西。
    """
    reports: list[AgentReport] = []
    for agent in all_agents():
        try:
            detected = agent.detect()
        except Exception:
            detected = False
        if not detected:
            continue
        try:
            sessions = agent.scan()
        except Exception:
            sessions = []
        try:
            storage_root = agent.storage_root() or ""
        except Exception:
            storage_root = ""
        reports.append(
            AgentReport(
                agent=agent.id,
                display=agent.display,
                storage_path=agent.storage_hint,
                storage_root=storage_root,
                sessions=sessions,
            )
        )
    return reports


def summary_line(reports: list[AgentReport]) -> str:
    """生成一行总览文字，如 '共 3 个 Agent，12 个会话，共 1.2 GB'。"""
    total_sessions = sum(len(r.sessions) for r in reports)
    total_size = sum(r.total_size for r in reports)
    from .models import human_size

    return f"发现 {len(reports)} 个 Agent、{total_sessions} 个会话，共 {human_size(total_size)}"
