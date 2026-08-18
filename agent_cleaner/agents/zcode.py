"""ZCode（智谱 Z.ai）会话扫描。

存储位置（依据官方文档 + 第三方实测，db v0.14.8；本机未安装，待验证）：
  ~/.zcode/cli/db/db.sqlite   （SQLite：session / model_usage / tool_usage 表）
  环境变量：ZCODE_STORAGE_DIR 可覆盖整个数据根目录

session 表除 id/directory 外列名未完全确认，用 PRAGMA 防御式探测，
缺列/缺表时返回空列表而非崩溃。会话 path 用 "sqlite://<db>#<session_id>"
标记，删除走 trash 的通用 SQLite 逻辑。
附属数据：cli/exec/（终端输出缓存，官方 FAQ 确认可整删、不自动清理）。
config.json / credentials / memories 等配置与记忆文件绝不列入。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Session
from .base import Agent

# session 表候选列（存在才用）：标题列、时间列
_TITLE_COLS = ("title", "slug")
_TIME_COLS = ("updated_at", "created_at", "time_updated")


class ZCodeAgent(Agent):
    id = "zcode"
    display = "ZCode"
    storage_hint = "~/.zcode"
    env_var = "ZCODE_STORAGE_DIR"

    def __init__(self) -> None:
        self.root = self.resolve_root(self.home_dir() / ".zcode")
        self.db_path = self.root / "cli" / "db" / "db.sqlite"
        self.exec_dir = self.root / "cli" / "exec"

    def detect(self) -> bool:
        return self.db_path.is_file()

    def storage_root(self) -> str | None:
        return str(self.root) if self.root.is_dir() else None

    def scan(self) -> list[Session]:
        out: list[Session] = []
        if self.db_path.is_file():
            out += self._scan_sqlite()
        # 附属数据：终端输出缓存（官方确认可整删，ZCode 会自动重建）
        d = self.exec_dir
        if d.is_dir():
            size = self.dir_size(d)
            if size:
                try:
                    mtime = d.stat().st_mtime
                except OSError:
                    mtime = 0
                out.append(
                    Session(
                        agent=self.id,
                        name="终端输出缓存 exec",
                        path=str(d),
                        size=size,
                        modified=mtime,
                        is_dir=True,
                        kind="aux",
                    )
                )
        return out

    def _scan_sqlite(self) -> list[Session]:
        """从 db.sqlite 读会话；防御式探测列名，缺关键列时返回空。"""
        out: list[Session] = []
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            return out
        try:
            cur = con.cursor()
            try:
                cols = {r[1] for r in cur.execute("PRAGMA table_info(session)")}
            except sqlite3.Error:
                return out
            if not {"id", "directory"} <= cols:
                return out
            title_col = next((c for c in _TITLE_COLS if c in cols), None)
            time_col = next((c for c in _TIME_COLS if c in cols), None)
            sel = ["id", "directory"]
            if title_col:
                sel.append(title_col)
            if time_col:
                sel.append(time_col)
            sql = f"SELECT {', '.join(sel)} FROM session ORDER BY {time_col or 'id'}"
            try:
                rows = cur.execute(sql).fetchall()
            except sqlite3.Error:
                return out
            for row in rows:
                sid, directory = row[0], row[1]
                title = row[2] if title_col else None
                ts = row[3] if time_col else None
                try:
                    ts = float(ts or 0)
                except (TypeError, ValueError):
                    ts = 0  # TEXT 时间列（版本差异）回退 0，不崩溃
                if ts > 1e12:  # 毫秒转秒
                    ts /= 1000.0
                project = Path(directory).name if directory else ""
                label = title or sid[:8]
                if project:
                    label = f"{project}: {label}"
                out.append(
                    Session(
                        agent=self.id,
                        name=label[:120],
                        path=f"sqlite://{self.db_path}#{sid}",
                        size=0,  # session 表无大小数据源
                        modified=ts,
                        is_dir=False,
                        project=project,
                    )
                )
        finally:
            con.close()
        return out
