# 新增 ZCode 支持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 ZCode（智谱 Z.ai）扫描与清理支持：SQLite 会话 + `cli/exec` 终端输出缓存，Agent 总数 16 → 17。

**Architecture:** 新建 `agent_cleaner/agents/zcode.py`（ZCodeAgent，参照 opencode.py/mimocode.py 模式），会话 path 用 `sqlite://<db>#<sid>` 标记走 trash 通用 SQLite 删除；`trash.py` 关联表清单增加 `model_usage`/`tool_usage`；registry 注册后 GUI/CLI 自动生效。

**Tech Stack:** 纯 Python 标准库（sqlite3 / pathlib），unittest。

## Global Constraints

- 零第三方依赖，不新增任何 import 外部库。
- 会话表除 `id`/`directory` 外列名未完全确认 → 必须 PRAGMA 防御式探测，缺列/缺表返回空列表，绝不抛异常（参照 kimi.py「待验证」注释风格）。
- `cli/exec/` 是唯一列入的附属数据（kind="aux"）；config.json / credentials / memories / agents / skills / commands / cli/log 绝不列入。
- 测试必须走 `BasePatchTest` 模式（临时目录），永远不碰真实用户目录；`BasePatchTest._ENV_VARS` 必须加入 `ZCODE_STORAGE_DIR` 隔离真实环境变量。
- 运行测试：`python -m unittest discover -s tests`；提交信息用中文；改版必须同步 CHANGELOG.md。

---

## File Structure

- Create: `agent_cleaner/agents/zcode.py` — ZCodeAgent 扫描器（职责：路径解析 + detect + scan）
- Modify: `agent_cleaner/registry.py` — 注册 ZCodeAgent
- Modify: `agent_cleaner/trash.py` — `_SQLITE_SESSION_TABLES` 增加关联表
- Modify: `tests/test_scanner.py` — 新增 ZCodeScanTest / ZCodeDeleteTest、RegistryTest 计数、_ENV_VARS
- Modify: `CHANGELOG.md`、`README.md`、`README.en.md`、`AGENTS.md` — 文档同步

---

### Task 1: ZCodeAgent 扫描器

**Files:**
- Create: `agent_cleaner/agents/zcode.py`
- Modify: `tests/test_scanner.py`（`_ENV_VARS` 增加 `ZCODE_STORAGE_DIR`；新增 `ZCodeScanTest` 类，放在 `MimoCodeScanTest` 之后；import `ZCodeAgent`）

**Interfaces:**
- Consumes: `Agent` 基类（`resolve_root`/`home_dir`/`dir_size`/`file_size`）、`models.Session`
- Produces: `ZCodeAgent`（`id="zcode"`、`display="ZCode"`、`env_var="ZCODE_STORAGE_DIR"`、`detect()`、`scan()`、`storage_root()`），会话 `path="sqlite://<db>#<sid>"`，aux 会话 `name="终端输出缓存 exec"`、`kind="aux"`

- [ ] **Step 1: 写失败测试** — 在 `tests/test_scanner.py` 的 `_ENV_VARS`（约第 79-90 行）加 `"ZCODE_STORAGE_DIR"`，import 区（约第 31-39 行）加 `from agent_cleaner.agents.zcode import ZCodeAgent`，并在 `MimoCodeScanTest` 类（第 610 行后）后追加：

```python
class ZCodeScanTest(BasePatchTest):
    """ZCode 会话扫描：cli/db/db.sqlite（SQLite，防御式列探测）。"""

    def _make_db(self) -> Path:
        db = self.tmp / ".zcode" / "cli" / "db" / "db.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db))
        con.executescript(
            """
            CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT NOT NULL,
                                  title TEXT, updated_at REAL);
            CREATE TABLE model_usage (id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                                      model_id TEXT, started_at INTEGER);
            CREATE TABLE tool_usage (session_id TEXT NOT NULL, turn_id TEXT,
                                     tool_name TEXT, started_at INTEGER);
            INSERT INTO session VALUES ('sess-1', 'D:/code/myapp', '修bug', 1750000000);
            INSERT INTO model_usage VALUES ('mu1', 'sess-1', 'glm-5.2', 1750000000);
            INSERT INTO tool_usage VALUES ('sess-1', 't1', 'bash', 1750000000);
            """
        )
        con.commit()
        con.close()
        return db

    def test_detect(self):
        self.assertFalse(ZCodeAgent().detect())
        self._make_db()
        self.assertTrue(ZCodeAgent().detect())

    def test_sqlite_sessions(self):
        self._make_db()
        agent = ZCodeAgent()
        sessions = agent.scan()
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertTrue(s.path.startswith("sqlite://"))
        self.assertEqual(s.project, "myapp")      # directory 的目录名
        self.assertIn("myapp", s.name)
        self.assertIn("修bug", s.name)            # title 列
        self.assertEqual(s.size, 0)               # session 表无大小数据源
        self.assertEqual(s.modified, 1750000000)  # updated_at（秒）

    def test_aux_exec(self):
        make_session(self.tmp / ".zcode" / "cli" / "exec" / "abc" / "out.txt", "x")
        agent = ZCodeAgent()
        sessions = agent.scan()
        aux = [s for s in sessions if s.kind == "aux"]
        self.assertEqual(len(aux), 1)
        self.assertEqual(aux[0].name, "终端输出缓存 exec")
        self.assertTrue(aux[0].is_dir)

    def test_missing_columns_no_crash(self):
        # 只有最小列（id/directory）也能扫；时间/标题列缺失用回退值
        db = self.tmp / ".zcode" / "cli" / "db" / "db.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db))
        con.executescript(
            """
            CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT NOT NULL);
            INSERT INTO session VALUES ('sess-2', '/repo/min');
            """
        )
        con.commit()
        con.close()
        sessions = ZCodeAgent().scan()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].project, "min")
        self.assertEqual(sessions[0].modified, 0)

    def test_no_session_table_no_crash(self):
        db = self.tmp / ".zcode" / "cli" / "db" / "db.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db))
        con.execute("CREATE TABLE other (x TEXT)")
        con.commit()
        con.close()
        self.assertEqual(ZCodeAgent().scan(), [])

    def test_env_var_override(self):
        os.environ["ZCODE_STORAGE_DIR"] = str(self.tmp / "zdata")
        agent = ZCodeAgent()
        self.assertEqual(str(agent.root), os.environ["ZCODE_STORAGE_DIR"])
        os.environ.pop("ZCODE_STORAGE_DIR", None)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.test_scanner.ZCodeScanTest -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_cleaner.agents.zcode'`

- [ ] **Step 3: 写实现** — 新建 `agent_cleaner/agents/zcode.py`：

```python
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
                ts = float(ts or 0)
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.test_scanner.ZCodeScanTest -v`
Expected: PASS（6 个测试）

- [ ] **Step 5: 提交**

```bash
git add agent_cleaner/agents/zcode.py tests/test_scanner.py
git commit -m "feat: 新增 ZCode 会话扫描（SQLite + exec 缓存）"
```

---

### Task 2: registry 注册

**Files:**
- Modify: `agent_cleaner/registry.py`（import 区 + `all_agents()` 列表）
- Test: `tests/test_scanner.py` 的 `RegistryTest.test_all_agents_count`（约第 612-621 行）

**Interfaces:**
- Consumes: `ZCodeAgent`（Task 1）
- Produces: `registry.all_agents()` 返回 17 个 Agent，含 `zcode`

- [ ] **Step 1: 写失败测试** — 更新 `RegistryTest.test_all_agents_count`：

```python
        # 原有 16 个 + ZCode = 17
        self.assertEqual(len(ids), 17)
        self.assertIn("zcode", ids)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.test_scanner.RegistryTest -v`
Expected: FAIL — `AssertionError: 16 != 17`

- [ ] **Step 3: 写实现** — `agent_cleaner/registry.py`：

import 区（按字母序，`windsurf` 之后）加：

```python
from .agents.windsurf import WindsurfAgent
from .agents.zcode import ZCodeAgent
```

`all_agents()` 列表（`WindsurfAgent()` 之后）加：

```python
        WindsurfAgent(),
        ZCodeAgent(),
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.test_scanner.RegistryTest -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add agent_cleaner/registry.py tests/test_scanner.py
git commit -m "feat: 注册 ZCodeAgent"
```

---

### Task 3: trash 关联表清理

**Files:**
- Modify: `agent_cleaner/trash.py`（`_SQLITE_SESSION_TABLES`，约第 161-169 行）
- Test: `tests/test_scanner.py` 新增 `ZCodeDeleteTest` 类（放在 `SqliteMissingTableTest` 附近）

**Interfaces:**
- Consumes: `trash.delete_session`、`_SQLITE_SESSION_TABLES`
- Produces: 删除 ZCode 会话时同步删除 `model_usage`/`tool_usage` 关联行

- [ ] **Step 1: 写失败测试** — 在 `tests/test_scanner.py` 的 `SqliteMissingTableTest` 类（约第 986 行）后追加：

```python
class ZCodeDeleteTest(BasePatchTest):
    """ZCode db 删除会话时同步清理 model_usage / tool_usage 关联行。"""

    def test_deletes_related_rows(self):
        from agent_cleaner.trash import delete_session

        db = self.tmp / ".zcode" / "cli" / "db" / "db.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db))
        con.executescript(
            """
            CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT NOT NULL);
            CREATE TABLE model_usage (id TEXT PRIMARY KEY, session_id TEXT NOT NULL);
            CREATE TABLE tool_usage (session_id TEXT NOT NULL, turn_id TEXT);
            INSERT INTO session VALUES ('sess-1', 'D:/code/myapp');
            INSERT INTO model_usage VALUES ('mu1', 'sess-1');
            INSERT INTO tool_usage VALUES ('sess-1', 't1');
            """
        )
        con.commit()
        con.close()

        s = Session(agent="zcode", name="t", path=f"sqlite://{db}#sess-1",
                    size=0, modified=0, is_dir=False)
        delete_session(s)

        con = sqlite3.connect(str(db))
        self.assertEqual(con.execute("SELECT COUNT(*) FROM session").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM model_usage").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM tool_usage").fetchone()[0], 0)
        con.close()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.test_scanner.ZCodeDeleteTest -v`
Expected: FAIL — `AssertionError: 1 != 0`（model_usage 行残留）

- [ ] **Step 3: 写实现** — `agent_cleaner/trash.py` 的 `_SQLITE_SESSION_TABLES`：

```python
_SQLITE_SESSION_TABLES = (
    "part",
    "message",
    "todo",
    "session_message",
    "session_context_epoch",
    "session_input",
    "session_share",
    "model_usage",  # ZCode：token 用量统计
    "tool_usage",   # ZCode：工具调用记录
)
```

（删除循环本就按 `sqlite_master` 过滤实际存在的表，OpenCode/MimoCode 无这两张表会自动跳过。）

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.test_scanner.ZCodeDeleteTest tests.test_scanner.SqliteMissingTableTest -v`
Expected: PASS（两个类都通过）

- [ ] **Step 5: 提交**

```bash
git add agent_cleaner/trash.py tests/test_scanner.py
git commit -m "fix: ZCode 删除会话时同步清理 model_usage/tool_usage 关联行"
```

---

### Task 4: 文档同步

**Files:**
- Modify: `CHANGELOG.md`、`README.md`、`README.en.md`、`AGENTS.md`

**Interfaces:**
- Consumes: 前面任务的最终产物（ZCode 已注册）

- [ ] **Step 1: CHANGELOG.md** — 在 `## v1.1.0` 之前插入：

```markdown
## v1.2.0 - 2026-08-18

### 新增
- 支持 ZCode（智谱 Z.ai）：会话（`~/.zcode/cli/db/db.sqlite`，SQLite）与终端输出缓存
  （`~/.zcode/cli/exec`，官方确认可整删），Agent 总数 16 → 17。
- ZCode 会话删除走通用 SQLite 逻辑，同步清理 model_usage / tool_usage 关联数据。

### 测试
- 新增 ZCode 扫描（含防御式列探测）、环境变量覆盖、SQLite 关联删除的单元测试。
```

- [ ] **Step 2: README.md** — 第 17 行 `16 个` → `17 个`；第 71 行表格 `MimoCode` 行后加：

```markdown
| ZCode | `%USERPROFILE%\.zcode\cli\db\db.sqlite`（SQLite）+ `cli\exec` 缓存 |
```

第 95 行安全说明 `清理 OpenCode / MimoCode 会话会操作其 SQLite 数据库` → 加 ZCode；第 131 行 `16 个` → `17 个`。

- [ ] **Step 3: README.en.md** — 对应同步：第 131 行 `16 agents` → `17 agents`；表格 `MimoCode` 行后加：

```markdown
| ZCode | `%USERPROFILE%\.zcode\cli\db\db.sqlite` (SQLite) + `cli\exec` cache |
```

第 95 行安全说明同步加 ZCode。

- [ ] **Step 4: AGENTS.md** — 第 3 行 `16 个` → `17 个`；第 24 行 `（OpenCode/MimoCode 新版）` → `（OpenCode/MimoCode/ZCode）`。

- [ ] **Step 5: 全量测试 + 提交**

Run: `python -m unittest discover -s tests`
Expected: PASS（原 84 个 + 新增 7 个 = 91 个全过）

```bash
git add CHANGELOG.md README.md README.en.md AGENTS.md
git commit -m "docs: ZCode 支持相关文档同步（CHANGELOG/README/AGENTS）"
```