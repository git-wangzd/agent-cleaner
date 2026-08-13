"""扫描与清理模块的单元测试。

用 pytest（或 python -m unittest）运行：
  python -m unittest discover -s tests -v

测试通过 monkeypatch 把各 Agent 的目录定位指到临时目录，
不触碰真实用户数据。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import shutil
import tempfile
import os

from agent_cleaner import models
from agent_cleaner.agents.claude import ClaudeAgent
from agent_cleaner.agents.codex import CodexAgent
from agent_cleaner.agents.continue_agent import ContinueAgent
from agent_cleaner.agents.cursor import CursorAgent
from agent_cleaner.agents.gemini import GeminiAgent
from agent_cleaner.agents.kimi import KimiAgent
from agent_cleaner.agents.lingma import LingmaAgent
from agent_cleaner.agents.marscode import MarsCodeAgent
from agent_cleaner.agents.opencode import OpenCodeAgent
from agent_cleaner.agents.qwen import QwenAgent
from agent_cleaner.agents.trae import TraeAgent
from agent_cleaner.agents.windsurf import WindsurfAgent
from agent_cleaner.cleaner import filter_by_days, merge_selected, preview
from agent_cleaner.models import AgentReport, Session, human_size
from agent_cleaner.scanner import scan_all, summary_line
from agent_cleaner.trash import _parse_sqlite_path
from agent_cleaner.utils import open_in_file_manager, reveal_target


def make_session(path: Path, content: str = "x" * 10) -> Path:
    """在临时目录下造一个会话文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class HumanSizeTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(2048), "2.0 KB")
        self.assertEqual(human_size(5 * 1024 * 1024), "5.0 MB")


class BasePatchTest(unittest.TestCase):
    """把 Agent 的 home/appdata/local_share 指到 tmp 下，并隔离 config.json 与环境变量。

    Agent 路径解析现在走 resolve_root（config 覆盖 > 环境变量 > 默认路径），
    因此除了 monkeypatch 目录方法，还必须隔离 APPDATA（config 读取）和
    清空各 Agent 的数据目录环境变量，否则会被真实用户配置干扰。
    """

    _ENV_VARS = (
        "APPDATA",
        "CLAUDE_CONFIG_DIR",
        "QWEN_HOME",
        "CODEX_HOME",
        "CONTINUE_GLOBAL_DIR",
        "XDG_DATA_HOME",
    )

    def setUp(self):
        import tempfile

        from agent_cleaner.agents import base

        self.tmp = Path(tempfile.mkdtemp(prefix="agent_cleaner_test_"))
        self._env_backup = {k: os.environ.get(k) for k in self._ENV_VARS}
        os.environ["APPDATA"] = str(self.tmp / "appdata")  # 隔离真实 config.json
        for k in self._ENV_VARS:
            if k != "APPDATA":
                os.environ.pop(k, None)  # 清空真实环境变量
        self._patches = []
        for attr in ("home_dir", "appdata_dir", "local_share_dir"):
            # 用 __dict__ 保存 staticmethod 描述符本身；
            # getattr 会解包描述符返回底层函数，恢复时会破坏 staticmethod 语义
            orig = base.Agent.__dict__[attr]
            self._patches.append((base.Agent, attr, orig))
            setattr(
                base.Agent,
                attr,
                staticmethod(lambda _self=self, _a=attr: self.tmp if _a == "home_dir" else (
                    self.tmp / "appdata" if _a == "appdata_dir" else self.tmp / "local_share"
                )),
            )

    def tearDown(self):
        import shutil

        from agent_cleaner.agents import base

        for cls, attr, orig in self._patches:
            setattr(cls, attr, orig)
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)


class ClaudeScanTest(BasePatchTest):
    def test_old_and_new_layout(self):
        make_session(self.tmp / ".claude" / "projects" / "myproj" / "2026-08-01.jsonl")
        make_session(self.tmp / ".claude" / "sessions" / "otherproj" / "abc.jsonl")

        agent = ClaudeAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 2)
        self.assertTrue(any(not s.is_dir and "myproj" in s.name for s in sessions))
        self.assertTrue(any(s.is_dir and "otherproj" in s.name for s in sessions))


class CodexScanTest(BasePatchTest):
    def test_rollout_files(self):
        make_session(self.tmp / ".codex" / "sessions" / "2026" / "08" / "01" / "rollout-a.jsonl")
        make_session(self.tmp / ".codex" / "sessions" / "2026" / "08" / "02" / "rollout-b.jsonl")

        agent = CodexAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 2)
        self.assertTrue(all(s.is_dir is False for s in sessions))


class CursorScanTest(BasePatchTest):
    def test_workspaces(self):
        ws = self.tmp / "appdata" / "Cursor" / "User" / "workspaceStorage" / "abc123"
        ws.mkdir(parents=True)
        make_session(ws / "state.vscdb", "sqlite-bytes")

        agent = CursorAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 1)
        self.assertTrue(sessions[0].is_dir)


class WindsurfScanTest(BasePatchTest):
    def test_workspaces(self):
        ws = self.tmp / "appdata" / "Windsurf" / "User" / "workspaceStorage" / "hash9"
        ws.mkdir(parents=True)
        make_session(ws / "state.vscdb", "sqlite-bytes")

        agent = WindsurfAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 1)
        self.assertTrue(sessions[0].is_dir)


class GeminiScanTest(BasePatchTest):
    def test_chats(self):
        make_session(self.tmp / ".gemini" / "tmp" / "abc" / "chats" / "1.json", '{"x":1}')

        agent = GeminiAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 1)


class ContinueScanTest(BasePatchTest):
    def test_sessions(self):
        make_session(self.tmp / ".continue" / "sessions" / "uuid-1.json", "{}")
        make_session(self.tmp / ".continue" / "sessions" / "uuid-2.json", "{}")
        # 索引文件不应被列入
        make_session(self.tmp / ".continue" / "sessions" / "sessions.json", "[]")

        agent = ContinueAgent()
        sessions = agent.scan()
        self.assertEqual(len(sessions), 2)


class OpenCodeScanTest(BasePatchTest):
    def test_session_json(self):
        make_session(
            self.tmp / "local_share" / "opencode" / "storage" / "session" / "projA" / "sid1.json",
            '{"id":"sid1"}',
        )

        agent = OpenCodeAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].agent, "opencode")
        self.assertFalse(sessions[0].path.startswith("sqlite://"))

    def test_new_sqlite_db(self):
        """新版：opencode.db SQLite 应能扫出会话，path 用 sqlite:// 标记。"""
        db = self.tmp / "local_share" / "opencode" / "opencode.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db))
        con.executescript(
            """
            CREATE TABLE project (id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE session (id TEXT PRIMARY KEY, project_id TEXT, title TEXT,
                                  slug TEXT, directory TEXT, time_updated REAL);
            CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT);
            CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, data TEXT);
            INSERT INTO project VALUES ('proj1', 'my-app');
            INSERT INTO session VALUES ('sess-1', 'proj1', '修复登录bug', 'fix-login', '/repo', 1750000000);
            INSERT INTO message VALUES ('m1', 'sess-1', 'hello');
            INSERT INTO part VALUES ('p1', 'm1', 'sess-1', 'xxxx');
            """
        )
        con.commit()
        con.close()

        agent = OpenCodeAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertTrue(s.path.startswith("sqlite://"))
        self.assertIn("my-app", s.name)
        self.assertIn("修复登录bug", s.name)
        self.assertEqual(s.size, 9)  # message(5) + part(4)


class OpenCodeDeletePathTest(unittest.TestCase):
    def test_parse_sqlite_path(self):
        db, sid = _parse_sqlite_path("sqlite://C:/x/opencode.db#abc123")
        self.assertEqual(db, Path("C:/x/opencode.db"))
        self.assertEqual(sid, "abc123")

    def test_parse_plain_path(self):
        self.assertIsNone(_parse_sqlite_path("C:/x/file.jsonl"))

    def test_parse_malformed(self):
        self.assertIsNone(_parse_sqlite_path("sqlite://C:/x/opencode.db"))


class CursorTranscriptsTest(BasePatchTest):
    def test_legacy_transcripts(self):
        """旧版：~/.cursor/projects/*/*/agent-transcripts/*.json 应被扫出。"""
        make_session(
            self.tmp / ".cursor" / "projects" / "demo" / "hash1" / "agent-transcripts" / "conv-1.json",
            "{}",
        )
        make_session(
            self.tmp / ".cursor" / "projects" / "demo" / "hash1" / "agent-transcripts" / "conv-2.json",
            "{}",
        )

        agent = CursorAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 2)
        self.assertTrue(all(not s.is_dir for s in sessions))
        self.assertTrue(all("旧会话" in s.name for s in sessions))


class UtilsTest(unittest.TestCase):
    def test_reveal_target_dir(self):
        self.assertEqual(Path(reveal_target("/x/y/dir", True)), Path("/x/y/dir"))

    def test_reveal_target_file(self):
        self.assertEqual(Path(reveal_target("/x/y/file.jsonl", False)), Path("/x/y"))

    def test_open_missing_path_returns_false(self):
        # 路径不存在时不尝试打开，直接返回 False
        self.assertFalse(open_in_file_manager("/nonexistent/xyz/123"))


class StorageRootTest(BasePatchTest):
    """各 Agent 的 storage_root() 应返回真实存储根目录。"""

    def test_claude(self):
        make_session(self.tmp / ".claude" / "projects" / "p" / "a.jsonl")
        self.assertTrue(ClaudeAgent().storage_root().endswith(".claude"))

    def test_opencode(self):
        db = self.tmp / "local_share" / "opencode" / "opencode.db"
        db.parent.mkdir(parents=True)
        db.write_text("x")
        self.assertTrue(OpenCodeAgent().storage_root().endswith("opencode"))

    def test_cursor(self):
        ws = self.tmp / "appdata" / "Cursor" / "User" / "workspaceStorage" / "h"
        ws.mkdir(parents=True)
        (ws / "state.vscdb").write_text("x")
        self.assertTrue(CursorAgent().storage_root().endswith("workspaceStorage"))

    def test_scan_all_fills_storage_root(self):
        make_session(self.tmp / ".claude" / "projects" / "p" / "a.jsonl")
        reports = scan_all()
        claude = next(r for r in reports if r.agent == "claude")
        self.assertTrue(claude.storage_root.endswith(".claude"))


class ScannerTest(BasePatchTest):
    def test_scan_all_and_summary(self):
        make_session(self.tmp / ".claude" / "projects" / "p" / "a.jsonl")
        reports = scan_all()
        self.assertTrue(any(r.agent == "claude" for r in reports))
        line = summary_line(reports)
        self.assertIn("1 个会话", line)


class PreviewTest(unittest.TestCase):
    def test_preview(self):
        s = Session(agent="claude", name="demo", path="/x/y.jsonl", size=1024, modified=0, is_dir=False)
        text = preview([s])
        self.assertIn("1 个会话", text)
        self.assertIn("demo", text)


class AuxDataTest(BasePatchTest):
    """附属数据（kind="aux"）的扫描与分组统计。"""

    def test_claude_cache_is_aux(self):
        make_session(self.tmp / ".claude" / "cache" / "c1", "x")
        make_session(self.tmp / ".claude" / "projects" / "p" / "a.jsonl")

        agent = ClaudeAgent()
        sessions = agent.scan()
        aux = [s for s in sessions if s.kind == "aux"]
        self.assertEqual(len(aux), 1)
        self.assertEqual(aux[0].name, "缓存 cache")

    def test_codex_logs_is_aux(self):
        make_session(self.tmp / ".codex" / "logs" / "codex.log", "x")
        make_session(self.tmp / ".codex" / "sessions" / "2026" / "08" / "01" / "rollout-a.jsonl")

        agent = CodexAgent()
        sessions = agent.scan()
        self.assertTrue(any(s.kind == "aux" and "logs" in s.name for s in sessions))

    def test_opencode_aux_dirs(self):
        for sub in ("tool-output", "snapshot", "log"):
            make_session(self.tmp / "local_share" / "opencode" / sub / "f", "x")

        agent = OpenCodeAgent()
        sessions = agent.scan()
        aux_names = {s.name for s in sessions if s.kind == "aux"}
        self.assertEqual(aux_names, {"工具输出 tool-output", "快照 snapshot", "日志 log"})

    def test_report_grouping(self):
        r = AgentReport(
            agent="x",
            display="X",
            storage_path="~/.x",
            sessions=[
                Session(agent="x", name="s1", path="/a", size=100, modified=0, is_dir=False),
                Session(agent="x", name="aux1", path="/b", size=50, modified=0, is_dir=False, kind="aux"),
            ],
        )
        self.assertEqual(len(r.session_sessions), 1)
        self.assertEqual(len(r.aux_sessions), 1)
        self.assertEqual(r.session_size, 100)
        self.assertEqual(r.aux_size, 50)
        self.assertEqual(r.total_size, 150)

    def test_merge_selected_includes_aux(self):
        from agent_cleaner.cleaner import merge_selected

        aux = Session(agent="claude", name="aux1", path="/c/cache", size=10, modified=0, is_dir=True, kind="aux")
        r = AgentReport(
            agent="claude",
            display="Claude Code",
            storage_path="~/.claude",
            sessions=[aux],
        )
        out = merge_selected([r], checked_agents={"claude"}, checked_paths=set())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "aux")


class DomesticCliTest(BasePatchTest):
    """国内 CLI（Qwen/通义灵码/Kimi/Trae/MarsCode）扫描。"""

    def test_qwen_chats(self):
        make_session(self.tmp / ".qwen" / "projects" / "myproj" / "chats" / "uuid-1.jsonl")
        make_session(self.tmp / ".qwen" / "projects" / "myproj" / "chats" / "uuid-2.jsonl")

        agent = QwenAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 2)
        self.assertTrue(all(not s.is_dir for s in sessions))

    def test_qwen_debug_is_aux(self):
        make_session(self.tmp / ".qwen" / "debug" / "log.txt", "x")
        make_session(self.tmp / ".qwen" / "projects" / "p" / "chats" / "a.jsonl")

        agent = QwenAgent()
        sessions = agent.scan()
        self.assertTrue(any(s.kind == "aux" and "debug" in s.name for s in sessions))

    def test_lingma_projects_and_aux(self):
        make_session(self.tmp / ".lingma" / "index" / "chat" / "v4" / "demo_abc" / "index_meta.json", "{}")
        make_session(self.tmp / ".lingma" / "cache" / "c1", "x")

        agent = LingmaAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertTrue(any(not s.kind == "aux" and "会话" in s.name for s in sessions))
        self.assertTrue(any(s.kind == "aux" and "cache" in s.name for s in sessions))

    def test_kimi_sessions_dir(self):
        make_session(self.tmp / ".kimi" / "sessions" / "abc.jsonl")
        agent = KimiAgent()
        self.assertTrue(agent.detect())
        self.assertEqual(len(agent.scan()), 1)

    def test_kimi_no_sessions_returns_empty(self):
        # 目录存在但没有明确会话结构 → 返回空，不误扫
        (self.tmp / ".kimi").mkdir(parents=True)
        (self.tmp / ".kimi" / "auth.json").write_text("{}", encoding="utf-8")
        agent = KimiAgent()
        self.assertTrue(agent.detect())
        self.assertEqual(agent.scan(), [])

    def test_marscode_no_dir_not_detected(self):
        agent = MarsCodeAgent()
        self.assertFalse(agent.detect())

    def test_trae_workspaces(self):
        ws = self.tmp / "appdata" / "Trae" / "User" / "workspaceStorage" / "hash1"
        ws.mkdir(parents=True)
        (ws / "state.vscdb").write_text("sqlite", encoding="utf-8")

        agent = TraeAgent()
        self.assertTrue(agent.detect())
        sessions = agent.scan()
        self.assertEqual(len(sessions), 1)
        self.assertTrue(sessions[0].is_dir)


class RegistryTest(unittest.TestCase):
    def test_all_agents_count(self):
        from agent_cleaner.registry import all_agents

        agents = all_agents()
        ids = {a.id for a in agents}
        # 8 个原有 + 5 个国内 = 13
        self.assertEqual(len(ids), 13)
        self.assertIn("qwen", ids)
        self.assertIn("kimi", ids)
        self.assertIn("lingma", ids)
        self.assertIn("trae", ids)
        self.assertIn("marscode", ids)


class EnvVarTest(unittest.TestCase):
    """Agent 官方环境变量支持（环境变量 > 默认路径；config 覆盖最高）。"""

    def setUp(self):
        import tempfile

        self._tmp = Path(tempfile.mkdtemp(prefix="envvar_test_"))
        self._saved = {
            k: os.environ.get(k)
            for k in ("APPDATA", "CLAUDE_CONFIG_DIR", "QWEN_HOME", "XDG_DATA_HOME")
        }
        os.environ["APPDATA"] = str(self._tmp / "appdata")  # 隔离 config.json

    def tearDown(self):
        import shutil

        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_claude_env_var(self):
        from agent_cleaner import config

        os.environ["CLAUDE_CONFIG_DIR"] = str(self._tmp / "claude-data")
        agent = ClaudeAgent()
        self.assertEqual(str(agent.root), os.environ["CLAUDE_CONFIG_DIR"])

    def test_qwen_env_var(self):
        os.environ["QWEN_HOME"] = str(self._tmp / "qwen-data")
        agent = QwenAgent()
        self.assertEqual(str(agent.root), os.environ["QWEN_HOME"])

    def test_config_override_beats_env(self):
        from agent_cleaner import config

        custom = str(self._tmp / "custom")
        config.set_agent_path("claude", custom)
        os.environ["CLAUDE_CONFIG_DIR"] = str(self._tmp / "env")
        agent = ClaudeAgent()
        self.assertEqual(str(agent.root), custom)
        config.set_agent_path("claude", None)

    def test_xdg_data_home(self):
        from agent_cleaner.agents.base import Agent

        os.environ["XDG_DATA_HOME"] = str(self._tmp / "xdg-data")
        self.assertEqual(str(Agent.local_share_dir()), os.environ["XDG_DATA_HOME"])

    def test_default_when_no_env(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        agent = ClaudeAgent()
        self.assertEqual(agent.root, agent.home_dir() / ".claude")


class ConfigTest(unittest.TestCase):
    """配置模块：读写与 Agent 路径覆盖。"""

    def setUp(self):
        import tempfile

        self._tmp = Path(tempfile.mkdtemp(prefix="config_test_"))
        self._old_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = str(self._tmp)

    def tearDown(self):
        import shutil

        if self._old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._old_appdata
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_roundtrip(self):
        from agent_cleaner import config

        self.assertEqual(config.load_config(), {})
        config.set_agent_path("claude", "D:/data/claude")
        self.assertEqual(config.get_agent_path("claude"), "D:/data/claude")
        # 清除覆盖
        config.set_agent_path("claude", None)
        self.assertIsNone(config.get_agent_path("claude"))

    def test_agent_root_override(self):
        from agent_cleaner import config

        custom = str(self._tmp / "my-claude")
        config.set_agent_path("claude", custom)
        agent = ClaudeAgent()
        self.assertEqual(str(agent.root), custom)

    def test_agent_root_default_when_no_override(self):
        agent = ClaudeAgent()
        self.assertEqual(agent.root, agent.home_dir() / ".claude")


class FilterByDaysTest(unittest.TestCase):
    """时间筛选（保留最近 N 天）：只保留更早的旧会话。"""

    def test_none_returns_all(self):
        s = [make_session_obj("x", "/a"), make_session_obj("x", "/b")]
        self.assertEqual(filter_by_days(s, None), s)

    def test_keeps_only_old_sessions(self):
        import time

        now = time.time()
        day = 86400
        sessions = [
            Session(agent="x", name="recent", path="/r", size=1, modified=now - 1 * day, is_dir=False),
            Session(agent="x", name="old", path="/o", size=1, modified=now - 10 * day, is_dir=False),
            Session(agent="x", name="unknown", path="/u", size=1, modified=0, is_dir=False),
        ]
        out = filter_by_days(sessions, 7)
        names = {s.name for s in out}
        # 1 天前的被过滤；10 天前的和未知时间的保留
        self.assertEqual(names, {"old", "unknown"})

    def test_aux_also_filtered(self):
        import time

        now = time.time()
        day = 86400
        aux = Session(agent="x", name="aux-old", path="/c", size=1, modified=now - 30 * day, is_dir=True, kind="aux")
        aux_recent = Session(agent="x", name="aux-new", path="/d", size=1, modified=now - 1 * day, is_dir=True, kind="aux")
        out = filter_by_days([aux, aux_recent], 7)
        self.assertEqual([s.name for s in out], ["aux-old"])


class ProgressCallbackTest(unittest.TestCase):
    """clean() 的进度回调：每删一个会话调用一次，done 从 1 递增。"""

    def _make_sessions(self, tmp: Path, n: int) -> list[Session]:
        out = []
        for i in range(n):
            p = tmp / f"s{i}.jsonl"
            p.write_text("x" * 10, encoding="utf-8")
            out.append(Session(agent="test", name=f"s{i}", path=str(p), size=10, modified=0, is_dir=False))
        return out

    def test_progress_calls_sequence(self):
        tmp = Path(tempfile.mkdtemp(prefix="progress_test_"))
        try:
            from agent_cleaner.cleaner import clean

            sessions = self._make_sessions(tmp, 3)
            calls: list[tuple[int, int, str]] = []
            result = clean(sessions, permanent=True, progress=lambda d, t, n: calls.append((d, t, n)))

            self.assertEqual(len(result.ok), 3)
            self.assertEqual(calls, [(1, 3, "s0"), (2, 3, "s1"), (3, 3, "s2")])
            self.assertFalse((tmp / "s0.jsonl").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_progress_optional(self):
        """不传 progress 时行为不变。"""
        tmp = Path(tempfile.mkdtemp(prefix="progress_test_"))
        try:
            from agent_cleaner.cleaner import clean

            sessions = self._make_sessions(tmp, 1)
            result = clean(sessions, permanent=True)
            self.assertEqual(len(result.ok), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class BatchFailureTest(unittest.TestCase):
    """批量删除中单个会话失败不应中断整体。"""

    def test_failed_session_does_not_stop_batch(self):
        tmp = Path(tempfile.mkdtemp(prefix="batch_test_"))
        try:
            from agent_cleaner.cleaner import clean

            good = tmp / "good.jsonl"
            good.write_text("x", encoding="utf-8")
            sessions = [
                Session(agent="test", name="good", path=str(good), size=1, modified=0, is_dir=False),
                # 不存在的路径 → 删除会失败（TrashError）
                Session(agent="test", name="missing", path=str(tmp / "not_exist.jsonl"), size=1, modified=0, is_dir=False),
            ]
            result = clean(sessions, permanent=True)
            self.assertEqual(len(result.ok), 1)        # 正常的那个成功
            self.assertEqual(len(result.failed), 1)    # 失败的被记录而不是中断
            self.assertIn("missing", result.failed[0])
            self.assertFalse(good.exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SqliteMissingTableTest(BasePatchTest):
    """OpenCode DB 缺少部分关联表时，删除会话不应报 no such table。"""

    def test_delete_with_partial_tables(self):
        from agent_cleaner.trash import delete_session

        db = self.tmp / "local_share" / "opencode" / "opencode.db"
        db.parent.mkdir(parents=True)
        con = sqlite3.connect(str(db))
        con.executescript(
            """
            CREATE TABLE session (id TEXT PRIMARY KEY, project_id TEXT);
            INSERT INTO session VALUES ('sess-1', 'p1');
            """
        )
        con.commit()
        con.close()

        s = Session(agent="opencode", name="t", path=f"sqlite://{db}#sess-1", size=1, modified=0, is_dir=False)
        delete_session(s)  # 关联表都不存在，也不应抛错

        con = sqlite3.connect(str(db))
        self.assertEqual(con.execute("SELECT COUNT(*) FROM session").fetchone()[0], 0)
        con.close()


def make_session_obj(agent: str, path: str, size: int = 100) -> Session:
    return Session(agent=agent, name=path.split("/")[-1], path=path, size=size, modified=0, is_dir=False)


class MergeSelectedTest(unittest.TestCase):
    """Agent 级勾选 + 会话级勾选的合并与去重。"""

    def setUp(self):
        self.reports = [
            AgentReport(
                agent="claude",
                display="Claude Code",
                storage_path="~/.claude",
                sessions=[
                    make_session_obj("claude", "/c/1.jsonl", 10),
                    make_session_obj("claude", "/c/2.jsonl", 20),
                ],
            ),
            AgentReport(
                agent="codex",
                display="Codex CLI",
                storage_path="~/.codex",
                sessions=[
                    make_session_obj("codex", "/x/1.jsonl", 30),
                ],
            ),
        ]

    def test_agent_level_check(self):
        out = merge_selected(self.reports, checked_agents={"claude"}, checked_paths=set())
        self.assertEqual(len(out), 2)
        self.assertEqual({s.path for s in out}, {"/c/1.jsonl", "/c/2.jsonl"})

    def test_session_level_check(self):
        out = merge_selected(self.reports, checked_agents=set(), checked_paths={"/x/1.jsonl"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].path, "/x/1.jsonl")

    def test_merge_both_and_dedup(self):
        # codex 整 Agent + claude 的单个会话；再额外勾选 codex 已有的会话，应去重
        out = merge_selected(self.reports, checked_agents={"codex"}, checked_paths={"/c/1.jsonl", "/x/1.jsonl"})
        self.assertEqual(len(out), 2)
        self.assertEqual({s.path for s in out}, {"/c/1.jsonl", "/x/1.jsonl"})

    def test_nothing_selected(self):
        out = merge_selected(self.reports, checked_agents=set(), checked_paths=set())
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
