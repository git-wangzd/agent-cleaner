"""OpenCode 会话扫描（兼容新老版本）。

新版（当前官方）：会话存在 SQLite 数据库
  ~/.local/share/opencode/opencode.db
  （session / message / part / project 等表；数据库可能很大，含 WAL 文件）

旧版：会话为文件
  ~/.local/share/opencode/storage/session/<projectID>/<sessionID>.json
  ~/.local/share/opencode/storage/message|part|tool-output/...（联动目录）

会话的 path 约定：
  - 新版:  "sqlite://<db路径>#<session_id>"（cleaner 据此走 SQL 删除）
  - 旧版:  实际 json 文件路径
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Session
from .base import Agent


class OpenCodeAgent(Agent):
    id = "opencode"
    display = "OpenCode"
    storage_hint = "~/.local/share/opencode"

    def __init__(self) -> None:
        self.root = self.resolve_root(self.local_share_dir() / "opencode")
        self.db_path = self.root / "opencode.db"
        self.storage_dir = self.root / "storage"

    def detect(self) -> bool:
        return self.db_path.is_file() or (self.storage_dir / "session").is_dir()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        # 新版：SQLite 数据库
        if self.db_path.is_file():
            out += self._scan_sqlite()
        # 旧版：storage/session 文件（数据库模式之外可能仍残留）
        old = self.storage_dir / "session"
        if old.is_dir():
            out += self._scan_files(old)

        # 附属数据：工具输出 / 快照 / 日志（保守边界；repos 与数据库 WAL 不列入，
        # repos 可能含仓库镜像、WAL 在 opencode 运行中删除会损坏数据库）
        for sub, label in (("tool-output", "工具输出 tool-output"), ("snapshot", "快照 snapshot"), ("log", "日志 log")):
            d = self.root / sub
            if not d.is_dir():
                continue
            size = self.dir_size(d)
            if size == 0:
                continue
            try:
                mtime = d.stat().st_mtime
            except OSError:
                mtime = 0
            out.append(
                Session(
                    agent=self.id,
                    name=label,
                    path=str(d),
                    size=size,
                    modified=mtime,
                    is_dir=True,
                    kind="aux",
                )
            )
        return out

    # ---- 新版：SQLite ----

    def _scan_sqlite(self) -> list[Session]:
        out: list[Session] = []
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            return out
        try:
            cur = con.cursor()
            rows = cur.execute(
                "SELECT s.id, s.project_id, s.title, s.slug, s.directory, "
                "s.time_updated, p.name "
                "FROM session s LEFT JOIN project p ON s.project_id = p.id "
                "ORDER BY s.time_updated"
            ).fetchall()
            size_sql = (
                "SELECT COALESCE((SELECT SUM(LENGTH(data)) FROM message WHERE session_id=?),0)"
                " + COALESCE((SELECT SUM(LENGTH(data)) FROM part WHERE session_id=?),0)"
            )
            for sid, _pid, title, slug, directory, updated, proj_name in rows:
                size = 0
                try:
                    size = int(cur.execute(size_sql, (sid, sid)).fetchone()[0] or 0)
                except sqlite3.Error:
                    pass
                ts = updated or 0
                if ts > 1e12:  # 毫秒转秒
                    ts /= 1000.0
                label = title or slug or sid[:8]
                if proj_name:
                    label = f"{proj_name}: {label}"
                if directory:
                    label = f"{label} · {Path(directory).name}"
                out.append(
                    Session(
                        agent=self.id,
                        name=label[:120],
                        path=f"sqlite://{self.db_path}#{sid}",
                        size=size,
                        modified=float(ts),
                        is_dir=False,
                        project=proj_name or "",
                    )
                )
        finally:
            con.close()
        return out

    # ---- 旧版：文件存储 ----

    def _scan_files(self, session_dir: Path) -> list[Session]:
        out: list[Session] = []
        for proj_dir in sorted(p for p in session_dir.iterdir() if p.is_dir()):
            for f in sorted(proj_dir.glob("*.json")):
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                # 同名的 message/part/tool-output 目录也要一起删，合并计算总大小
                total = self.file_size(f)
                for sub in ("message", "part", "tool-output"):
                    extra = self.storage_dir / sub / proj_dir.name / f.stem
                    if extra.is_dir():
                        total += self.dir_size(extra)
                if total == 0:
                    continue
                out.append(
                    Session(
                        agent=self.id,
                        name=f"{proj_dir.name} / {f.stem}",
                        path=str(f),
                        size=total,
                        modified=mtime,
                        is_dir=False,
                        project=proj_dir.name,
                    )
                )
        return out
