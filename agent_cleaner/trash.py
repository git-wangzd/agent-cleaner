"""跨平台删除：默认进回收站（可恢复），支持永久删除。

实现策略（均为 Python 标准库可调用，无需第三方依赖）：
  - Windows: 调用 PowerShell 的 Microsoft.VisualBasic.FileIO（系统自带），
             文件/目录被移入回收站，可从回收站恢复。
  - macOS:   调用 osascript 让 Finder 删除（进入废纸篓）。
  - Linux:   按 XDG Trash 规范把文件移入 ~/.local/share/Trash，
             并写入 .trashinfo 元数据（大多数桌面环境会显示在回收站）。
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .models import Session


class TrashError(Exception):
    """删除失败时抛出。"""


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _run(cmd: list[str]) -> None:
    """运行命令；非零退出码抛 TrashError。"""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if _is_windows() else 0,
        )
    except FileNotFoundError as e:
        raise TrashError(f"找不到命令: {cmd[0]}") from e
    if proc.returncode != 0:
        raise TrashError((proc.stderr or proc.stdout or "").strip()[:500])


def _ps_str(s: str) -> str:
    """PowerShell 单引号字符串内转义：单引号翻倍。"""
    return s.replace("'", "''")


def _trash_windows(path: Path) -> None:
    """Windows：通过 PowerShell 的 VisualBasic.FileIO 移入回收站。"""
    ps = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"[Microsoft.VisualBasic.FileIO.FileSystem]::Delete"
        f"{'Directory' if path.is_dir() else 'File'}("
        f"'{_ps_str(str(path))}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
    )
    _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])


def _trash_macos(path: Path) -> None:
    """macOS：通过 Finder（osascript）删除，进入废纸篓（转义双引号与反斜杠）。"""
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped}"'
    _run(["osascript", "-e", script])


def _trash_linux(path: Path) -> None:
    """Linux：实现 XDG Trash 规范。"""
    trash_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "Trash"
    files_dir = trash_dir / "files"
    info_dir = trash_dir / "info"
    files_dir.mkdir(parents=True, exist_ok=True)
    info_dir.mkdir(parents=True, exist_ok=True)

    name = path.name
    if files_dir.joinpath(name).exists():
        name = f"{name}-{uuid.uuid4().hex[:8]}"

    # 先移动文件，再写元数据（trashinfo 里记录原路径，用于恢复）
    shutil.move(str(path), str(files_dir / name))

    import urllib.parse

    info = (
        "[Trash Info]\n"
        f"Path={urllib.parse.quote(str(path.resolve()), safe='/')}\n"
        f"DeletionDate={time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
    )
    info_file = info_dir / f"{name}.trashinfo"
    try:
        info_file.write_text(info, encoding="utf-8")
    except OSError:
        # 元数据写失败不阻塞删除本身
        pass


def delete_session(session: Session, permanent: bool = False) -> None:
    """删除一个会话。

    默认进入回收站（可恢复）；permanent=True 时直接永久删除。
    session 为 sqlite:// 会话（OpenCode / MimoCode 新版，数据库存储）时走 SQL 删除；
    session 为 OpenCode 旧版文件会话时，联动删除同名 message/part/tool-output 目录。
    """
    # SQLite 会话（不受回收站/永久分支影响）
    if session.path.startswith("sqlite://"):
        _delete_sqlite_session(session)
        return

    path = Path(session.path)
    if not path.exists():
        raise TrashError(f"路径不存在: {path}")

    if permanent:
        if session.is_dir:
            shutil.rmtree(path, ignore_errors=True)
            if path.exists():  # 权限不足/占用时 rmtree 可能残留，静默会误导用户
                raise TrashError(f"删除失败（可能被占用或权限不足）: {path}")
        else:
            try:
                path.unlink()
            except OSError as e:
                raise TrashError(f"删除失败: {path} ({e})") from e
    else:
        if _is_windows():
            _trash_windows(path)
        elif _is_macos():
            _trash_macos(path)
        else:
            _trash_linux(path)

    # OpenCode 会话：json 之外还有 message/part/tool-output 联动目录
    if session.agent == "opencode" and not session.is_dir:
        storage = Path(session.path).parent.parent.parent  # storage/session/<proj>/<id>.json -> storage
        stem = Path(session.path).stem
        proj = Path(session.path).parent.name
        for sub in ("message", "part", "tool-output"):
            extra = storage / sub / proj / stem
            if extra.exists():
                if permanent:
                    shutil.rmtree(extra, ignore_errors=True)
                else:
                    if _is_windows():
                        _trash_windows(extra)
                    elif _is_macos():
                        _trash_macos(extra)
                    else:
                        _trash_linux(extra)


# ---- SQLite 会话删除（OpenCode / MimoCode 新版共用） ----

# 与 session 存在外键关联的表（按 session_id 关联），删除会话时同步清理
_SQLITE_SESSION_TABLES = (
    "part",
    "message",
    "todo",
    "session_message",
    "session_context_epoch",
    "session_input",
    "session_share",
)


def _parse_sqlite_path(path: str) -> tuple[Path, str] | None:
    """把 'sqlite://<db>#<session_id>' 解析成 (db路径, session_id)；格式不符返回 None。"""
    if not path.startswith("sqlite://"):
        return None
    rest = path[len("sqlite://"):]
    if "#" not in rest:
        return None
    db, sid = rest.split("#", 1)
    return Path(db), sid


def _delete_sqlite_session(session: Session) -> None:
    """删除 SQLite 会话数据库（opencode/mimocode 同架构）里的单个会话，并 VACUUM 释放空间。"""
    parsed = _parse_sqlite_path(session.path)
    if parsed is None:
        raise TrashError(f"无法解析 sqlite 会话路径: {session.path}")
    db, sid = parsed
    if not db.is_file():
        raise TrashError(f"数据库不存在: {db}")

    try:
        con = sqlite3.connect(str(db), timeout=8)
    except sqlite3.Error as e:
        raise TrashError(f"无法打开数据库: {e}") from e
    try:
        # 只删除当前数据库实际存在的关联表，避免版本差异导致 no such table
        existing = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in _SQLITE_SESSION_TABLES:
            if table in existing:
                con.execute(f"DELETE FROM {table} WHERE session_id = ?", (sid,))
        cur = con.execute("DELETE FROM session WHERE id = ?", (sid,))
        if cur.rowcount == 0:
            raise TrashError(f"会话不存在（可能已被清理）: {sid}")
        con.commit()
    except sqlite3.Error as e:
        try:
            con.rollback()
        except sqlite3.Error:
            pass
        msg = str(e).lower()
        if "locked" in msg or "busy" in msg:
            raise TrashError("该 Agent 正在运行中（数据库被占用），请先退出后再清理。") from e
        raise TrashError(f"SQLite 删除失败: {e}") from e
    finally:
        con.close()

    # VACUUM 回收磁盘空间（释放删掉的页）；失败不影响已完成的删除
    try:
        con2 = sqlite3.connect(str(db), timeout=8)
        con2.execute("VACUUM")
        con2.close()
    except sqlite3.Error:
        pass


def delete_sessions(
    sessions: list[Session],
    permanent: bool = False,
    progress=None,
) -> tuple[list[str], list[str]]:
    """批量删除；返回 (成功路径列表, 失败原因列表)。

    progress 为可选回调 progress(done, total, name)，每删除一个会话调用一次，
    供界面显示实时进度（done 从 1 开始计数）。
    """
    ok: list[str] = []
    failed: list[str] = []
    total = len(sessions)
    for i, s in enumerate(sessions, 1):
        try:
            delete_session(s, permanent=permanent)
            ok.append(s.path)
        except Exception as e:  # 宽捕获：单个会话失败不应中断整个批量删除
            failed.append(f"{s.name}: {e}")
        if progress is not None:
            progress(i, total, s.name)
    return ok, failed
