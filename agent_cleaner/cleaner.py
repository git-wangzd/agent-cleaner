"""清理执行层：提供 dry-run 预览与真实删除的统一入口。

GUI / CLI 只调用本模块的接口，不直接操作文件系统。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import AgentReport, Session, human_size
from .trash import delete_sessions
from .logs import get_logger


def filter_by_days(sessions: list[Session], days: int | None) -> list[Session]:
    """按最后活动时间过滤会话（"保留最近 N 天"的旧会话筛选）。

    - days=None: 返回全部
    - days=N:    只保留 N 天前没有活动的旧会话
    - modified 为 0（未知时间）的会话保留，避免被误隐藏
    """
    if not days:
        return sessions
    cutoff = time.time() - days * 86400
    return [s for s in sessions if not s.modified or s.modified < cutoff]


def filter_by_project(sessions: list[Session], project: str | None) -> list[Session]:
    """按项目过滤会话；project 为空或"全部项目"时不过滤。"""
    if not project or project == "全部项目":
        return sessions
    return [s for s in sessions if s.project == project]


def filter_by_search(sessions: list[Session], keyword: str) -> list[Session]:
    """按关键词过滤会话（匹配名称或项目，不区分大小写）；关键词为空不过滤。"""
    kw = (keyword or "").strip().lower()
    if not kw:
        return sessions
    return [s for s in sessions if kw in s.name.lower() or kw in s.project.lower()]


def quick_clean_target(reports: list[AgentReport], days: int) -> list[Session]:
    """一键清理的目标：所有 Agent 中超过 days 天未活动的会话（不含附属数据）。"""
    target: list[Session] = []
    for r in reports:
        target += [s for s in filter_by_days(r.sessions, days) if s.kind != "aux"]
    return target


def merge_selected(
    reports: list[AgentReport],
    checked_agents: set[str],
    checked_paths: set[str],
) -> list[Session]:
    """合并勾选结果：勾选的 Agent（全部会话）+ 单独勾选的会话，按路径去重。

    - checked_agents: 勾选了"清理整个 Agent"的 Agent id 集合
    - checked_paths:  会话级别单独勾选的路径集合
    """
    seen: set[str] = set()
    out: list[Session] = []
    for r in reports:
        for s in r.sessions:
            if r.agent in checked_agents or s.path in checked_paths:
                if s.path not in seen:
                    seen.add(s.path)
                    out.append(s)
    return out


@dataclass
class CleanResult:
    """一次清理的结果汇总。"""

    permanent: bool = False
    ok: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def freed(self) -> int:
        return 0  # 删除前无法精确统计，由调用方传入预估

    def summary(self) -> str:
        mode = "永久删除" if self.permanent else "已移入回收站"
        head = f"{mode}完成：成功 {len(self.ok)} 个"
        if self.failed:
            head += f"，失败 {len(self.failed)} 个"
        lines = [head]
        lines += [f"  ✓ {p}" for p in self.ok[:10]]
        if len(self.ok) > 10:
            lines.append(f"  … 共 {len(self.ok)} 个成功")
        lines += [f"  ✗ {f}" for f in self.failed]
        return "\n".join(lines)


def preview(sessions: list[Session]) -> str:
    """dry-run 预览：列出将删除的内容和预计释放空间，不真正删除。"""
    if not sessions:
        return "没有选中任何会话。"
    total = sum(s.size for s in sessions)
    lines = [f"将清理 {len(sessions)} 个会话，预计释放 {human_size(total)}："]
    for s in sessions:
        lines.append(f"  - [{s.agent}] {s.name} ({s.size_human()}, 最后活动 {s.modified_human()})")
    return "\n".join(lines)


def clean(sessions: list[Session], permanent: bool = False, progress=None) -> CleanResult:
    """执行清理。sessions 为空时直接返回空结果。

    progress 为可选回调 progress(done, total, name)，每删除一个会话调用一次。
    """
    if not sessions:
        return CleanResult(permanent=permanent)
    ok, failed = delete_sessions(sessions, permanent=permanent, progress=progress)
    if failed:
        get_logger().warning("批量清理失败 %d/%d 个", len(failed), len(sessions))
        for msg in failed:
            get_logger().warning("  %s", msg)
    return CleanResult(permanent=permanent, ok=ok, failed=failed)
