"""清理历史：每次清理成功后的摘要记录。

存 <配置目录>/history.jsonl（JSON Lines），只记录元信息（时间/模式/数量/释放空间/
涉及的 Agent id），不记录具体路径——历史文件本身不应成为隐私泄露点。
GUI 设置里可查看最近记录并清空。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .config import config_dir

MAX_ENTRIES = 200  # 保留最近 200 条，防止历史文件无限增长


def history_path() -> Path:
    """历史文件路径：<配置目录>/history.jsonl。"""
    return config_dir() / "history.jsonl"


def record_clean(mode: str, count: int, freed: int, agents: list[str]) -> None:
    """追加一条清理记录（新记录在文件尾部）。

    mode: "trash"（回收站）或 "permanent"（永久删除）
    agents: 本次涉及的 Agent id 列表（内部去重排序）
    """
    entry = {
        "ts": int(time.time()),
        "mode": mode,
        "count": count,
        "freed": freed,
        "agents": sorted(set(agents)),
    }
    p = history_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _trim(p)
    except OSError:
        pass  # 历史记录失败不影响清理本身


def read_history(limit: int = 20) -> list[dict]:
    """读取最近 limit 条记录（新的在前）；文件不存在/损坏时返回空列表。"""
    p = history_path()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))


def clear_history() -> None:
    """清空历史记录文件。"""
    try:
        history_path().unlink(missing_ok=True)
    except OSError:
        pass


def _trim(p: Path) -> None:
    """只保留最近 MAX_ENTRIES 行，防止历史文件无限增长。"""
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= MAX_ENTRIES:
        return
    try:
        p.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n", encoding="utf-8")
    except OSError:
        pass
