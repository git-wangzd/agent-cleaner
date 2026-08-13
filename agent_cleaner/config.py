"""配置模块：%APPDATA%\\agent-cleaner\\config.json（Linux/macOS 用 XDG_CONFIG_HOME）。

配置结构：
{
  "agent_paths": {
    "claude": "D:/data/claude",   # 覆盖某个 Agent 的数据根目录
    "kimi":   "C:/my/kimi-data"   # 路径推断不准确的 Agent 用这里纠正
  }
}
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def config_dir() -> Path:
    """配置目录：Windows 用 APPDATA，其他平台用 XDG_CONFIG_HOME 或 ~/.config。"""
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "agent-cleaner"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    """读取配置；文件不存在或损坏时返回空 dict。"""
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    """写入配置（自动创建目录）。"""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def set_agent_path(agent_id: str, path: str | None) -> None:
    """设置/清除某个 Agent 的自定义数据路径。path=None 表示清除覆盖。"""
    cfg = load_config()
    paths = cfg.setdefault("agent_paths", {})
    if path:
        paths[agent_id] = path
    else:
        paths.pop(agent_id, None)
    save_config(cfg)


def get_agent_path(agent_id: str) -> str | None:
    """读取某个 Agent 的自定义数据路径（无覆盖返回 None）。"""
    return load_config().get("agent_paths", {}).get(agent_id)


def get_big_file_mb() -> int:
    """大文件标红阈值（MB），默认 10。"""
    try:
        return int(load_config().get("big_file_mb", 10))
    except (TypeError, ValueError):
        return 10


def set_big_file_mb(mb: int) -> None:
    """设置大文件标红阈值（MB）。"""
    cfg = load_config()
    cfg["big_file_mb"] = int(mb)
    save_config(cfg)


def get_update_repo() -> str:
    """版本检查的 GitHub 仓库（owner/repo）；空 = 不检查。"""
    return load_config().get("update_repo", "")


def set_update_repo(repo: str) -> None:
    """设置版本检查仓库；空字符串表示关闭检查。"""
    cfg = load_config()
    if repo:
        cfg["update_repo"] = repo
    else:
        cfg.pop("update_repo", None)
    save_config(cfg)
