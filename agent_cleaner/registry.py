"""Agent 注册表：集中管理支持的 Agent 列表。"""

from __future__ import annotations

from .agents.base import Agent
from .agents.atomcode import AtomCodeAgent
from .agents.claude import ClaudeAgent
from .agents.cline import ClineAgent
from .agents.codex import CodexAgent
from .agents.continue_agent import ContinueAgent
from .agents.cursor import CursorAgent
from .agents.gemini import GeminiAgent
from .agents.kimi import KimiAgent
from .agents.lingma import LingmaAgent
from .agents.marscode import MarsCodeAgent
from .agents.mimocode import MimoCodeAgent
from .agents.opencode import OpenCodeAgent
from .agents.pi import PiAgent
from .agents.qwen import QwenAgent
from .agents.trae import TraeAgent
from .agents.windsurf import WindsurfAgent


def all_agents() -> list[Agent]:
    """返回全部支持的 Agent 实例（按显示名排序）。"""
    agents = [
        AtomCodeAgent(),
        ClaudeAgent(),
        ClineAgent(),
        CodexAgent(),
        ContinueAgent(),
        CursorAgent(),
        GeminiAgent(),
        KimiAgent(),
        LingmaAgent(),
        MarsCodeAgent(),
        MimoCodeAgent(),
        OpenCodeAgent(),
        PiAgent(),
        QwenAgent(),
        TraeAgent(),
        WindsurfAgent(),
    ]
    return sorted(agents, key=lambda a: a.display)


def find_agent(agent_id: str) -> Agent | None:
    """按 id 查找 Agent，找不到返回 None。"""
    for a in all_agents():
        if a.id == agent_id:
            return a
    return None
