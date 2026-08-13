"""版本升级检查：从 GitHub Releases 拉取最新版本（标准库 urllib，无第三方依赖）。

仓库名在 config.json 的 update_repo 字段配置（"owner/repo" 格式）；留空则不检查。
"""

from __future__ import annotations

import json
import urllib.request

from . import __version__


def check_latest(repo: str, timeout: float = 8.0) -> str | None:
    """查询 GitHub Releases 最新版本号（如 "v1.0.0"）；查询失败返回 None。"""
    if not repo or "/" not in repo:
        return None
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("tag_name")
    except Exception:
        return None


def is_newer(remote: str, local: str) -> bool:
    """比较版本号（支持 v 前缀与数字段）：remote 是否比 local 新。"""

    def parts(v: str) -> list[int]:
        return [int(x) for x in v.lstrip("vV").replace("-", ".").split(".") if x.isdigit()]

    rp, lp = parts(remote), parts(local)
    for r, l in zip(rp, lp):
        if r != l:
            return r > l
    return len(rp) > len(lp)


def update_available(repo: str) -> str | None:
    """综合入口：仓库配置了且远程有新版本时返回最新版本号，否则返回 None。"""
    latest = check_latest(repo)
    if latest and is_newer(latest, __version__):
        return latest
    return None
