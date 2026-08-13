"""Agent 扫描基类：定义统一接口 + 跨平台路径工具。"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Session


def _first_env(*names: str) -> str | None:
    """按顺序取第一个非空的环境变量。"""
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return None


class Agent:
    """所有 Agent 扫描器的基类。

    子类需实现：
      - id:       唯一标识（小写英文）
      - display:  界面显示名
      - scan():   返回该 Agent 的会话列表
    """

    id = "agent"
    display = "Agent"
    storage_hint = ""  # 存储位置的说明文字（界面展示用）
    env_var: str | None = None  # Agent 官方支持的数据目录环境变量（如 CLAUDE_CONFIG_DIR）

    # ---- 跨平台路径工具 ----

    @staticmethod
    def home_dir() -> Path:
        """用户主目录：优先 USERPROFILE（Windows），回退 HOME。"""
        return Path(_first_env("USERPROFILE", "HOME") or str(Path.home()))

    @staticmethod
    def appdata_dir() -> Path:
        """应用数据目录：Windows 用 APPDATA，其他平台回退 home。"""
        val = _first_env("APPDATA", "XDG_CONFIG_HOME", "HOME")
        if val:
            return Path(val)
        return Agent.home_dir()

    @staticmethod
    def local_share_dir() -> Path:
        """数据目录：遵循 XDG_DATA_HOME（opencode 等使用），未设置时回退 ~/.local/share。"""
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            return Path(xdg)
        return Agent.home_dir() / ".local" / "share"

    @staticmethod
    def dir_size(path: Path) -> int:
        """递归计算目录大小。"""
        from ..models import dir_size

        return dir_size(path)

    @staticmethod
    def file_size(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return 0

    # ---- 子类需实现 ----

    def config_override(self) -> Path | None:
        """从 config.json 读取该 Agent 的自定义数据路径（若有）。"""
        try:
            from ..config import get_agent_path

            p = get_agent_path(self.id)
            return Path(p) if p else None
        except Exception:
            return None

    def resolve_root(self, default: Path) -> Path:
        """返回数据根目录，优先级：用户配置覆盖 > Agent 官方环境变量 > 默认路径。"""
        override = self.config_override()
        if override:
            return override
        if self.env_var:
            env_val = os.environ.get(self.env_var)
            if env_val:
                return Path(env_val)
        return default

    def detect(self) -> bool:
        """存储根目录是否存在（快速探测）。"""
        raise NotImplementedError

    def storage_root(self) -> str | None:
        """返回存储根目录的真实绝对路径（右键"打开路径"用）；不存在返回 None。"""
        return None

    def scan(self) -> list[Session]:
        """返回该 Agent 找到的所有会话。"""
        raise NotImplementedError
