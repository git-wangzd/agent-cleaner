"""MimoCode（小米 MiMo Code）会话扫描。

存储位置（本机实测确认，与 OpenCode 新版同架构）：
  ~/.local/share/mimocode/mimocode.db   （SQLite：session/project/message/part 等表）
  环境变量：MIMOCODE_HOME 可覆盖整个数据目录

会话 path 用 "sqlite://<db>#<session_id>" 标记，删除走 trash 的通用 SQLite 逻辑。
附属数据：log/、snapshot/。memory/（记忆文件）是重要数据，不列入。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Session
from .base import Agent


class MimoCodeAgent(Agent):
    id = "mimocode"
    display = "MimoCode"
    storage_hint = "~/.local/share/mimocode"
    env_var = "MIMOCODE_HOME"

    def __init__(self) -> None:
        self.root = self.resolve_root(self.local_share_dir() / "mimocode")
        self.db_path = self.root / "mimocode.db"

    def detect(self) -> bool:
        return self.db_path.is_file()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if self.db_path.is_file():
            out += self._scan_sqlite()

        # 附属数据：日志 / 快照（memory/ 记忆文件不列入）
        for sub, label in (("log", "日志 log"), ("snapshot", "快照 snapshot")):
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

    def _scan_sqlite(self) -> list[Session]:
        """从 mimocode.db 读会话（表结构与 OpenCode 同架构）。"""
        out: list[Session] = []
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            return out
        try:
            cur = con.cursor()
            rows = cur.execute(
                "SELECT s.id, s.title, s.slug, s.directory, s.time_updated, p.name "
                "FROM session s LEFT JOIN project p ON s.project_id = p.id "
                "ORDER BY s.time_updated"
            ).fetchall()
            size_sql = (
                "SELECT COALESCE((SELECT SUM(LENGTH(data)) FROM message WHERE session_id=?),0)"
                " + COALESCE((SELECT SUM(LENGTH(data)) FROM part WHERE session_id=?),0)"
            )
            for sid, title, slug, directory, updated, proj_name in rows:
                size = 0
                try:
                    size = int(cur.execute(size_sql, (sid, sid)).fetchone()[0] or 0)
                except sqlite3.Error:
                    pass
                ts = updated or 0
                if ts > 1e12:  # 毫秒转秒
                    ts /= 1000.0
                project = proj_name or (Path(directory).name if directory else "")
                label = title or slug or sid[:8]
                if project:
                    label = f"{project}: {label}"
                out.append(
                    Session(
                        agent=self.id,
                        name=label[:120],
                        path=f"sqlite://{self.db_path}#{sid}",
                        size=size,
                        modified=float(ts),
                        is_dir=False,
                        project=project,
                    )
                )
        finally:
            con.close()
        return out
