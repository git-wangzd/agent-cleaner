"""版本升级检查：从 GitHub Releases 拉取最新版本（标准库 urllib，无第三方依赖）。

仓库名默认写死在 config.DEFAULT_UPDATE_REPO，可用 config.json 的 update_repo 字段覆盖。
支持两种格式："owner/repo" 或完整 GitHub 地址（https://github.com/owner/repo）。
"""

from __future__ import annotations

import json
import re
import urllib.request


def _parse_repo(repo: str) -> str | None:
    """把仓库名解析为 owner/repo 格式。

    支持："owner/repo"、"https://github.com/owner/repo"（含 .git 后缀）。
    无法解析时返回 None。
    """
    repo = (repo or "").strip().rstrip("/")
    if not repo:
        return None
    m = re.match(r"^https?://(?:www\.)?github\.com/([^/]+/[^/]+?)(?:\.git)?$", repo)
    if m:
        return m.group(1)
    if "/" in repo and not repo.startswith(("http://", "https://")):
        return repo
    return None


def check_latest(repo: str, timeout: float = 8.0) -> str | None:
    """查询 GitHub Releases 最新版本号（如 "v1.0.0"）；查询失败返回 None。

    repo 支持 "owner/repo" 或完整 GitHub 地址。
    """
    parsed = _parse_repo(repo)
    if not parsed:
        return None
    url = f"https://api.github.com/repos/{parsed}/releases/latest"
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
