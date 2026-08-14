"""Tkinter 图形界面。

布局：
  顶部：扫描按钮 + 总览
  上半：各 Agent 汇总表（标题栏带全选/清空；点击行查看其会话）
  下半：会话列表（标题栏带全选/清空；第一列点击勾选）
  底部：状态栏 + 清理到回收站 / 永久删除
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cleaner import (
    CleanResult,
    clean,
    filter_by_days,
    filter_by_project,
    filter_by_search,
    merge_selected,
    preview,
    quick_clean_target,
)
from . import __version__, config
from .history import clear_history, read_history
from .logs import get_logger
from .models import AgentReport, Session, human_size
from .registry import all_agents
from .scanner import scan_all, summary_line
from .updater import check_latest, download_url, is_newer
from .utils import ToolTip, open_in_file_manager, reveal_target

CHECK = "✅"        # 已勾选（大号符号，比 ☑ 更醒目）
UNCHECK = "⬜"      # 未勾选（大号方框，比 ☐ 更醒目）
CHECKED_TAG = "checked"          # 勾选行的 tag（背景高亮）
CHECKED_BG = "#e6f4ea"           # 勾选行背景色（浅绿）
BIG_TAG = "big"                  # 大文件行 tag（红色前景）
BIG_FG = "#cc0000"               # 大文件行文字色


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Agent 会话清理工具 v{__version__}")
        self.geometry("1000x720")
        self.minsize(820, 560)

        self.reports: list[AgentReport] = []
        self.sessions: list[Session] = []        # 当前选中 Agent 的会话
        self.checked_paths: set[str] = set()     # 已勾选会话的路径集合
        self.checked_agents: set[str] = set()    # 已勾选"清理整个 Agent"的 id 集合
        self.control_buttons: list[ttk.Button] = []  # 清理期间需要禁用的按钮
        self.filter_days: int | None = None      # 时间筛选：None=全部，N=只显示 N 天前的旧会话
        self.project_filter = "全部项目"          # 项目筛选：当前 Agent 的项目名
        self.search_text = ""                    # 会话搜索关键词

        self._build_ui()
        # 工作线程 → 主线程 的消息队列（Tk 只能在主线程操作）
        self._msg_queue: queue.Queue = queue.Queue()
        self._poll_ui_queue()
        self.after(200, self.do_scan)  # 启动后自动扫描一次
        self.after(1500, self._check_update)  # 延迟检查新版本（不阻塞启动）

    # ---------- 界面搭建 ----------

    def _build_ui(self) -> None:
        # 全局样式：加大行高，让复选框字符更饱满
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=28)

        # 顶部工具栏
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        self.btn_scan = ttk.Button(top, text="重新扫描", command=self.do_scan)
        self.btn_scan.pack(side="left")
        self.lbl_summary = ttk.Label(top, text="正在扫描…")
        self.lbl_summary.pack(side="left", padx=12)
        # 时间筛选：只显示 N 天前未活动的旧会话（默认全部）
        ttk.Label(top, text="只显示未活动超过:").pack(side="left", padx=(12, 2))
        self.cmb_filter = ttk.Combobox(top, values=["全部", "7 天", "30 天", "90 天"], state="readonly", width=8)
        self.cmb_filter.set("全部")
        self.cmb_filter.pack(side="left")
        self.cmb_filter.bind("<<ComboboxSelected>>", self._on_filter_change)
        ToolTip(
            self.cmb_filter,
            "按会话最后活动时间筛选，只看 N 天前没用过的旧会话\n（例如选\"30 天\"= 只列出 30 天前没动过的，最近的会话被隐藏）\nAgent 表的会话数与总大小会同步变化",
        )
        ttk.Button(top, text="设置", command=self._open_settings).pack(side="left", padx=(12, 0))
        self.btn_quick = ttk.Button(top, text="一键清理", command=self._quick_clean)
        self.btn_quick.pack(side="left", padx=(6, 0))
        self.control_buttons.append(self.btn_quick)
        ttk.Button(top, text="检查更新", command=lambda: self._check_update(manual=True)).pack(side="left", padx=(6, 0))

        # 上下分割
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=10)

        # ---- 上半：Agent 汇总表 ----
        top_frame = ttk.LabelFrame(paned, text="检测到的 Agent（点击查看其会话）", padding=4)
        # Agent 级选择：全选/清空
        top_bar = ttk.Frame(top_frame)
        top_bar.pack(fill="x", pady=(0, 4))
        b1 = ttk.Button(top_bar, text="全选", command=self._check_all_agents)
        b1.pack(side="left")
        b2 = ttk.Button(top_bar, text="反选", command=self._invert_agents)
        b2.pack(side="left", padx=(4, 0))
        self.control_buttons += [b1, b2]
        cols = ("check", "agent", "sessions", "aux", "size", "storage")
        self.tree_agents = ttk.Treeview(top_frame, columns=cols, show="headings", height=5)
        headers = (("check", 34, ""), ("agent", 150, "Agent"), ("sessions", 55, "会话"), ("aux", 55, "附属"), ("size", 105, "总大小"), ("storage", 220, "存储位置"))
        for cid, w, txt in headers:
            align = "center" if cid in ("check", "sessions", "aux") else "w"
            self.tree_agents.heading(cid, text=txt, anchor=align)
            self.tree_agents.column(cid, width=w, anchor=align)
        self.tree_agents.tag_configure(CHECKED_TAG, background=CHECKED_BG)
        sb1 = ttk.Scrollbar(top_frame, command=self.tree_agents.yview)
        self.tree_agents.configure(yscrollcommand=sb1.set)
        self.tree_agents.pack(side="left", fill="both", expand=True)
        sb1.pack(side="right", fill="y")
        self.tree_agents.bind("<<TreeviewSelect>>", self._on_agent_select)
        self.tree_agents.bind("<Button-1>", self._on_agent_click)
        self.tree_agents.bind("<Button-3>", self._agent_menu)
        self.tree_agents.bind("<Button-2>", self._agent_menu)  # macOS 右键
        paned.add(top_frame, weight=1)

        # ---- 下半：会话列表（可勾选） ----
        sess_frame = ttk.LabelFrame(paned, text="会话列表（点击第一列勾选/取消）", padding=4)
        # 会话级选择：全选/清空
        sess_bar = ttk.Frame(sess_frame)
        sess_bar.pack(fill="x", pady=(0, 4))
        b3 = ttk.Button(sess_bar, text="全选", command=self._check_all_sessions)
        b3.pack(side="left")
        b4 = ttk.Button(sess_bar, text="反选", command=self._invert_sessions)
        b4.pack(side="left", padx=(4, 0))
        self.control_buttons += [b3, b4]
        # 项目筛选
        ttk.Label(sess_bar, text="项目:").pack(side="left", padx=(12, 2))
        self.cmb_project = ttk.Combobox(sess_bar, state="readonly", width=18)
        self.cmb_project.pack(side="left")
        self.cmb_project.bind("<<ComboboxSelected>>", self._on_project_change)
        # 会话搜索（按名称/项目即输即滤）
        ttk.Label(sess_bar, text="搜索:").pack(side="left", padx=(12, 2))
        self.ent_search = ttk.Entry(sess_bar, width=16)
        self.ent_search.pack(side="left")
        self.ent_search.bind("<KeyRelease>", self._on_search_change)
        cols2 = ("check", "kind", "name", "size", "modified")
        self.tree_sessions = ttk.Treeview(sess_frame, columns=cols2, show="headings")
        for cid, w, txt in (("check", 34, ""), ("kind", 52, "类型"), ("name", 370, "会话"), ("size", 100, "大小"), ("modified", 150, "最后活动")):
            align = "center" if cid in ("check", "kind") else "w"
            self.tree_sessions.heading(cid, text=txt, anchor=align)
            self.tree_sessions.column(cid, width=w, anchor=align)
        self.tree_sessions.tag_configure(CHECKED_TAG, background=CHECKED_BG)
        self.tree_sessions.tag_configure(BIG_TAG, foreground=BIG_FG)
        sb2 = ttk.Scrollbar(sess_frame, command=self.tree_sessions.yview)
        self.tree_sessions.configure(yscrollcommand=sb2.set)
        self.tree_sessions.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.tree_sessions.bind("<Button-1>", self._on_session_click)
        self.tree_sessions.bind("<Double-1>", self._session_detail)
        self.tree_sessions.bind("<Button-3>", self._session_menu)
        self.tree_sessions.bind("<Button-2>", self._session_menu)  # macOS 右键
        paned.add(sess_frame, weight=3)

        # ---- 底部操作栏 ----
        bottom = ttk.Frame(self, padding=(10, 8))
        bottom.pack(fill="x")
        self.lbl_status = ttk.Label(bottom, text="就绪")
        self.lbl_status.pack(side="left")
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=180)
        self.progress.pack(side="left", padx=12)
        b5 = ttk.Button(bottom, text="清理到回收站", command=lambda: self._do_clean(permanent=False))
        b5.pack(side="right")
        b6 = ttk.Button(bottom, text="永久删除", command=lambda: self._do_clean(permanent=True))
        b6.pack(side="right", padx=6)
        self.control_buttons += [b5, b6]

    # ---------- 弹窗辅助 ----------

    def _center_window(self, win: tk.Toplevel) -> None:
        """把 Toplevel 弹窗居中显示在主窗口中央。"""
        win.update_idletasks()
        x = self.winfo_rootx() + max((self.winfo_width() - win.winfo_width()) // 2, 0)
        y = self.winfo_rooty() + max((self.winfo_height() - win.winfo_height()) // 2, 0)
        win.geometry(f"+{x}+{y}")

    # ---------- 线程通信 ----------

    def _poll_ui_queue(self) -> None:
        """主线程轮询工作线程消息队列（Tk 只能在主线程操作，线程里禁止调 after）。"""
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                kind = msg[0]
                if kind == "status":
                    self.lbl_status.config(text=msg[1])
                elif kind == "scan_done":
                    self._on_scan_done(msg[1])
                elif kind == "scan_error":
                    self._on_scan_error(msg[1])
                elif kind == "clean_progress":
                    self._on_progress(msg[1], msg[2], msg[3])
                elif kind == "clean_done":
                    self._on_clean_done(msg[1])
                elif kind == "clean_error":
                    self._on_clean_error(msg[1])
                elif kind == "update_result":
                    self._on_update_result(msg[1], msg[2], msg[3])
        except queue.Empty:
            pass
        self.after(50, self._poll_ui_queue)  # 继续轮询

    # ---------- 扫描 ----------

    def do_scan(self) -> None:
        """后台线程扫描：界面保持响应，状态栏逐 Agent 显示进度；保留旧数据直到完成。"""
        self.btn_scan.state(["disabled"])
        self.btn_quick.state(["disabled"])
        self.lbl_status.config(text="正在扫描…")

        def worker() -> None:
            def on_progress(agent_display: str) -> None:
                self._msg_queue.put(("status", f"正在扫描 {agent_display} …"))

            try:
                reports = scan_all(progress=on_progress)
                self._msg_queue.put(("scan_done", reports))
            except Exception as e:  # 扫描失败不应崩溃
                get_logger().error("扫描出错: %s", e)
                self._msg_queue.put(("scan_error", e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self, reports: list[AgentReport]) -> None:
        """扫描线程完成（主线程）：清勾选、刷新界面、恢复按钮。"""
        # 扫描后清空所有勾选，避免残留勾选导致误删
        self.checked_agents.clear()
        self.checked_paths.clear()
        self.reports = reports
        self._refresh_agents()
        self.lbl_summary.config(text=summary_line(reports))
        self.lbl_status.config(text=f"扫描完成 {summary_line(reports)}")
        self.btn_scan.state(["!disabled"])
        self.btn_quick.state(["!disabled"])

    def _on_scan_error(self, exc: Exception) -> None:
        """扫描线程异常（主线程）：提示并恢复按钮。"""
        self.lbl_status.config(text=f"扫描出错: {exc}")
        self.btn_scan.state(["!disabled"])
        self.btn_quick.state(["!disabled"])

    def _refresh_agents(self) -> None:
        self.tree_agents.delete(*self.tree_agents.get_children())
        # 先收集行数据，再按显示的总大小降序排列（占用最大的 Agent 排最前）
        rows: list[tuple[int, AgentReport, int, int, int]] = []
        for r in self.reports:
            shown = self._filter_sessions(r.sessions)
            session_n = len([s for s in shown if s.kind != "aux"])
            aux_n = len([s for s in shown if s.kind == "aux"])
            size = sum(s.size for s in shown)
            rows.append((size, r, session_n, aux_n, size))
        rows.sort(key=lambda t: t[0], reverse=True)
        for _size, r, session_n, aux_n, size in rows:
            checked = r.agent in self.checked_agents
            mark = CHECK if checked else UNCHECK
            tags = (CHECKED_TAG,) if checked else ()
            self.tree_agents.insert("", "end", iid=r.agent, values=(mark, r.display, session_n, aux_n, human_size(size), r.storage_path), tags=tags)
        # 默认选中第一个有会话的 Agent
        first = next((r.agent for r in self.reports if r.sessions), None)
        if first:
            self.tree_agents.selection_set(first)
            self._show_sessions(first)

    def _on_agent_select(self, _event=None) -> None:
        sel = self.tree_agents.selection()
        if sel:
            self._show_sessions(sel[0])

    def _on_agent_click(self, event) -> None:
        """点击 Agent 表第一列时，切换"清理整个 Agent"的勾选。"""
        row = self.tree_agents.identify_row(event.y)
        col = self.tree_agents.identify_column(event.x)
        if not row or col != "#1":
            return
        if row in self.checked_agents:
            self.checked_agents.discard(row)
            self.tree_agents.set(row, "check", UNCHECK)
            self.tree_agents.item(row, tags=())
        else:
            self.checked_agents.add(row)
            self.tree_agents.set(row, "check", CHECK)
            self.tree_agents.item(row, tags=(CHECKED_TAG,))
        self._update_status()

    def _show_sessions(self, agent_id: str) -> None:
        self.checked_paths.clear()
        self.tree_sessions.delete(*self.tree_sessions.get_children())
        report = next((r for r in self.reports if r.agent == agent_id), None)
        self.sessions = self._filter_sessions(report.sessions) if report else []
        self._refresh_project_options()
        self.sessions = self._filter_by_project(self.sessions)
        self.sessions = self._filter_by_search(self.sessions)
        # 会话在前、附属数据在后，组内按大小降序（大文件优先）；超阈值标红
        big_threshold = config.get_big_file_mb() * 1024 * 1024
        for s in sorted(self.sessions, key=lambda x: (x.kind == "aux", -x.size)):
            checked = s.path in self.checked_paths
            mark = CHECK if checked else UNCHECK
            is_big = s.size >= big_threshold
            if checked:
                tags = (CHECKED_TAG, BIG_TAG) if is_big else (CHECKED_TAG,)
            else:
                tags = (BIG_TAG,) if is_big else ()
            kind_label = "附属" if s.kind == "aux" else "会话"
            self.tree_sessions.insert("", "end", iid=s.path, values=(mark, kind_label, s.name, s.size_human(), s.modified_human()), tags=tags)

    # ---------- 勾选 ----------

    def _on_session_click(self, event) -> None:
        """点击第一列时切换勾选状态。"""
        row = self.tree_sessions.identify_row(event.y)
        col = self.tree_sessions.identify_column(event.x)
        if not row or col != "#1":
            return
        if row in self.checked_paths:
            self.checked_paths.discard(row)
            self.tree_sessions.set(row, "check", UNCHECK)
            self.tree_sessions.item(row, tags=())
        else:
            self.checked_paths.add(row)
            self.tree_sessions.set(row, "check", CHECK)
            self.tree_sessions.item(row, tags=(CHECKED_TAG,))
        self._update_status()

    def _check_all_agents(self) -> None:
        """全选 Agent：勾选所有 Agent（其全部会话都会纳入清理）。"""
        for r in self.reports:
            self.checked_agents.add(r.agent)
            self.tree_agents.set(r.agent, "check", CHECK)
            self.tree_agents.item(r.agent, tags=(CHECKED_TAG,))
        self._update_status()

    def _invert_agents(self) -> None:
        """反选 Agent：已勾选的取消，未勾选的勾选。"""
        for item in self.tree_agents.get_children():
            if item in self.checked_agents:
                self.checked_agents.discard(item)
                self.tree_agents.set(item, "check", UNCHECK)
                self.tree_agents.item(item, tags=())
            else:
                self.checked_agents.add(item)
                self.tree_agents.set(item, "check", CHECK)
                self.tree_agents.item(item, tags=(CHECKED_TAG,))
        self._update_status()

    def _check_all_sessions(self) -> None:
        """全选会话：勾选当前 Agent 列表里的全部会话。"""
        for s in self.sessions:
            self.checked_paths.add(s.path)
            self.tree_sessions.set(s.path, "check", CHECK)
            self.tree_sessions.item(s.path, tags=(CHECKED_TAG,))
        self._update_status()

    def _invert_sessions(self) -> None:
        """反选会话：已勾选的取消，未勾选的勾选（当前列表内，保持大文件标红）。"""
        big_threshold = config.get_big_file_mb() * 1024 * 1024
        for s in self.sessions:
            is_big = s.size >= big_threshold
            if s.path in self.checked_paths:
                self.checked_paths.discard(s.path)
                self.tree_sessions.set(s.path, "check", UNCHECK)
                self.tree_sessions.item(s.path, tags=(BIG_TAG,) if is_big else ())
            else:
                self.checked_paths.add(s.path)
                self.tree_sessions.set(s.path, "check", CHECK)
                tags = (CHECKED_TAG, BIG_TAG) if is_big else (CHECKED_TAG,)
                self.tree_sessions.item(s.path, tags=tags)
        self._update_status()

    def _selected_sessions(self) -> list[Session]:
        """合并 Agent 级与会话级勾选，返回去重后的待清理会话。"""
        return merge_selected(self.reports, self.checked_agents, self.checked_paths)

    def _update_status(self) -> None:
        selected = self._selected_sessions()
        total = sum(s.size for s in selected)
        self.lbl_status.config(text=f"已选 {len(selected)} 个会话，共 {human_size(total)}")

    # ---------- 时间筛选 ----------

    def _filter_sessions(self, sessions: list[Session]) -> list[Session]:
        """按当前筛选条件返回会话子集（None=全部，N=只保留 N 天前没活动的旧会话）。"""
        return filter_by_days(sessions, self.filter_days)

    def _on_filter_change(self, _event=None) -> None:
        """筛选下拉变化：刷新 Agent 统计与当前会话列表（联动）。"""
        text = self.cmb_filter.get()
        self.filter_days = int(text.split()[0]) if text != "全部" else None
        sel = self.tree_agents.selection()
        self._refresh_agents()
        if sel:
            self.tree_agents.selection_set(sel[0])
            self._show_sessions(sel[0])
        self._update_status()

    # ---------- 会话详情 ----------

    def _session_detail(self, event) -> None:
        """双击会话行：弹出元数据详情框（标题/项目/时间/大小/路径）。"""
        row = self.tree_sessions.identify_row(event.y)
        if not row:
            return
        session = next((s for s in self.sessions if s.path == row), None)
        if not session:
            return
        self._show_detail_dialog(session)

    def _show_detail_dialog(self, session: Session) -> None:
        """展示一个会话的元数据详情（不解析消息正文）。"""
        win = tk.Toplevel(self)
        win.title("会话详情")
        win.transient(self)
        win.resizable(False, False)
        rows = [
            ("Agent", session.agent),
            ("名称", session.name),
            ("类型", "附属数据" if session.kind == "aux" else "会话"),
            ("大小", session.size_human()),
            ("最后活动", session.modified_human()),
            ("路径", session.path),
        ]
        for i, (k, v) in enumerate(rows):
            ttk.Label(win, text=f"{k}:", font=("TkDefaultFont", 10, "bold")).grid(
                row=i, column=0, sticky="ne", padx=12, pady=5
            )
            ttk.Label(win, text=v, wraplength=480, justify="left").grid(
                row=i, column=1, sticky="w", padx=(0, 12), pady=5
            )
        ttk.Button(win, text="关闭", command=win.destroy).grid(
            row=len(rows), column=0, columnspan=2, pady=12
        )
        self._center_window(win)

    # ---------- 版本检查 ----------

    def _check_update(self, manual: bool = False) -> None:
        """检查更新：启动自动（manual=False，仅新版本时提示）或手动按钮触发。

        结果经消息队列回主线程处理（避免线程里调 Tk）。
        """
        repo = config.get_update_repo()
        if not repo:
            if manual:
                messagebox.showinfo("检查更新", "未配置更新检查仓库：请到设置中填写 GitHub 仓库（owner/repo）。")
            return

        def worker() -> None:
            latest = check_latest(repo)
            if latest is None:
                self._msg_queue.put(("update_result", None, "error", manual))
            elif is_newer(latest, __version__):
                self._msg_queue.put(("update_result", latest, "new", manual))
            else:
                self._msg_queue.put(("update_result", None, "current", manual))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_result(self, latest, status: str, manual: bool) -> None:
        """更新检查结果（主线程）：新版本/已最新/检查失败。"""
        if status == "new":
            url = download_url(config.get_update_repo(), latest)
            messagebox.showinfo(
                "发现新版本",
                f"当前版本：{__version__}\n最新版本：{latest}\n\n"
                f"下载地址：{url}\n\n请打开上面的地址下载对应平台安装包。",
            )
        elif manual:  # 手动检查时才提示"已最新/失败"，自动检查保持静默
            if status == "current":
                messagebox.showinfo("检查更新", f"已是最新版本（{__version__}）。")
            else:
                messagebox.showwarning("检查更新", "检查失败：无法访问 GitHub Releases（网络问题？）。")

    # ---------- 设置对话框 ----------

    def _open_settings(self) -> None:
        """设置对话框：查看/编辑每个 Agent 的数据路径覆盖（即时保存，关闭时重扫）。"""
        win = tk.Toplevel(self)
        win.title("设置 - Agent 数据路径")
        win.transient(self)
        win.geometry("600x520")

        ttk.Label(
            win,
            text="为每个 Agent 指定数据目录（留空 = 使用默认路径 / 环境变量路径）",
        ).pack(padx=12, pady=(10, 4), anchor="w")
        ttk.Label(
            win,
            text="点\"浏览\"选择目录、\"清除\"恢复默认；修改即时保存，关闭后自动重新扫描",
            foreground="#666666",
        ).pack(padx=12, pady=(0, 6), anchor="w")

        # 大文件标红阈值（MB）
        thr_row = ttk.Frame(win)
        thr_row.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(thr_row, text="大文件标红阈值 (MB):").pack(side="left")
        thr_var = tk.StringVar(value=str(config.get_big_file_mb()))
        ttk.Entry(thr_row, textvariable=thr_var, width=8).pack(side="left", padx=(4, 0))
        ttk.Button(thr_row, text="查看清理记录", command=self._show_history).pack(side="right")

        # 滚动区（Agent 数量多时窗口放不下）
        canvas = tk.Canvas(win, highlightthickness=0)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas)
        frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0))
        sb.pack(side="right", fill="y")

        entries: dict[str, tk.StringVar] = {}

        def choose_dir(agent_id: str, var: tk.StringVar) -> None:
            """目录选择器选中后立即保存该 Agent 的覆盖路径。"""
            d = filedialog.askdirectory(
                parent=win,
                title=f"选择 {agent_id} 的数据目录",
                initialdir=var.get() or str(Path.home()),
            )
            if d:
                var.set(d)
                config.set_agent_path(agent_id, d)  # 即时保存

        def clear_path(agent_id: str, var: tk.StringVar) -> None:
            """清空覆盖路径（恢复默认/环境变量），即时生效。"""
            var.set("")
            config.set_agent_path(agent_id, None)

        def popup_menu(event, agent_id: str, var: tk.StringVar) -> None:
            menu = tk.Menu(win, tearoff=0)
            menu.add_command(label="选择目录…", command=lambda: choose_dir(agent_id, var))
            menu.add_command(label="清空路径", command=lambda: clear_path(agent_id, var))
            menu.tk_popup(event.x_root, event.y_root)
            menu.grab_release()

        for agent in all_agents():
            row = ttk.Frame(frame)
            row.pack(fill="x", padx=6, pady=3)
            ttk.Label(row, text=f"{agent.display} ({agent.id})", width=22).pack(side="left")
            var = tk.StringVar(value=config.get_agent_path(agent.id) or "")
            entries[agent.id] = var
            entry = ttk.Entry(row, textvariable=var)
            entry.pack(side="left", fill="x", expand=True)
            entry.bind("<Double-1>", lambda _e, a=agent.id, v=var: choose_dir(a, v))
            entry.bind("<Button-3>", lambda e, a=agent.id, v=var: popup_menu(e, a, v))
            entry.bind("<Button-2>", lambda e, a=agent.id, v=var: popup_menu(e, a, v))
            ttk.Button(
                row, text="浏览", width=5,
                command=lambda a=agent.id, v=var: choose_dir(a, v),
            ).pack(side="left", padx=(4, 2))
            ttk.Button(
                row, text="清除", width=5,
                command=lambda a=agent.id, v=var: clear_path(a, v),
            ).pack(side="left")

        def on_close() -> None:
            """关闭：手打的路径落盘 + 阈值/备份目录保存 + 重新扫描。"""
            for aid, var in entries.items():
                val = var.get().strip()
                config.set_agent_path(aid, val or None)
            try:
                config.set_big_file_mb(int(thr_var.get().strip() or 10))
            except ValueError:
                pass
            win.destroy()
            self.do_scan()

        # 修改即时保存：点右上角 X 关闭时落盘手打路径并重新扫描
        win.protocol("WM_DELETE_WINDOW", on_close)
        self._center_window(win)

    def _show_history(self) -> None:
        """查看清理记录：列出最近记录（新的在前）+ 清空按钮。"""
        win = tk.Toplevel(self)
        win.title("清理记录")
        win.transient(self)
        win.geometry("560x420")
        win.resizable(False, False)

        ttk.Label(win, text="最近清理记录（只记摘要，不含具体路径）：").pack(padx=12, pady=(10, 4), anchor="w")
        txt = tk.Text(win, height=14, state="disabled", wrap="none")
        txt.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        sb = ttk.Scrollbar(win, command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.configure(yscrollcommand=sb.set)

        def refresh() -> None:
            entries = read_history(limit=50)
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            if not entries:
                txt.insert("1.0", "还没有任何清理记录。")
            for e in entries:
                mode = "永久删除" if e.get("mode") == "permanent" else "回收站"
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("ts", 0)))
                agents = "、".join(e.get("agents", [])[:8]) or "—"
                txt.insert("end", f"{ts}  {mode}  成功 {e.get('count', 0)} 个  约释放 {human_size(e.get('freed', 0))}  [{agents}]\n")
            txt.configure(state="disabled")

        refresh()
        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(btns, text="清空记录", command=lambda: (clear_history(), refresh())).pack(side="right")
        ttk.Button(btns, text="关闭", command=win.destroy).pack(side="right", padx=(0, 8))

        self._center_window(win)

    # ---------- 项目筛选 ----------

    def _refresh_project_options(self) -> None:
        """根据当前 Agent 的会话刷新项目下拉选项，保持或回退当前选择。"""
        projects = sorted({s.project for s in self.sessions if s.project})
        values = ["全部项目"] + projects
        self.cmb_project.configure(values=values)
        if self.project_filter not in values:
            self.project_filter = "全部项目"
        self.cmb_project.set(self.project_filter)

    def _filter_by_project(self, sessions: list[Session]) -> list[Session]:
        """按项目过滤（"全部项目"不过滤）。"""
        return filter_by_project(sessions, self.project_filter)

    def _on_project_change(self, _event=None) -> None:
        """项目下拉变化：重新显示当前 Agent 的会话（叠加项目过滤）。"""
        self.project_filter = self.cmb_project.get()
        sel = self.tree_agents.selection()
        if sel:
            self._show_sessions(sel[0])
        self._update_status()

    # ---------- 搜索 ----------

    def _filter_by_search(self, sessions: list[Session]) -> list[Session]:
        """按关键词过滤会话（匹配名称或项目，不区分大小写）。"""
        return filter_by_search(sessions, self.search_text)

    def _on_search_change(self, _event=None) -> None:
        """搜索框输入变化：实时过滤当前会话列表。"""
        self.search_text = self.ent_search.get()
        sel = self.tree_agents.selection()
        if sel:
            self._show_sessions(sel[0])
        self._update_status()

    # ---------- 右键菜单 ----------

    def _agent_menu(self, event) -> None:
        """右键 Agent 行：打开该 Agent 的存储根目录。"""
        row = self.tree_agents.identify_row(event.y)
        if not row:
            return
        report = next((r for r in self.reports if r.agent == row), None)
        if not report or not report.storage_root:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="打开存储目录",
            command=lambda: open_in_file_manager(report.storage_root),
        )
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def _session_menu(self, event) -> None:
        """右键会话行：打开会话所在位置。

        - 普通文件/目录会话 → 所在目录或目录本身
        - OpenCode 新版（sqlite://）会话在数据库里 → 打开其存储根目录
        """
        row = self.tree_sessions.identify_row(event.y)
        if not row:
            return
        session = next((s for s in self.sessions if s.path == row), None)
        if not session:
            return
        if session.path.startswith("sqlite://"):
            report = next((r for r in self.reports if r.agent == session.agent), None)
            target = report.storage_root if report else ""
        else:
            target = reveal_target(session.path, session.is_dir)
        if not target:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="打开所在位置",
            command=lambda: open_in_file_manager(target),
        )
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    # ---------- 清理 ----------

    def _do_clean(self, permanent: bool) -> None:
        selected = self._selected_sessions()
        if not selected:
            messagebox.showinfo("提示", "请先勾选要清理的会话。")
            return

        confirm_title = "永久删除确认" if permanent else "确认清理"
        aux_count = sum(1 for s in selected if s.kind == "aux")
        if permanent:
            # 永久删除：附属数据提示"无法恢复"是合理的
            aux_warn = (
                f"\n\n⚠️ 其中包含 {aux_count} 个附属数据（缓存/日志等），"
                "删除后通常无法恢复，请确认不再需要。"
                if aux_count
                else ""
            )
            ok = messagebox.askyesno(
                confirm_title,
                "⚠️ 永久删除不可恢复！\n\n" + preview(selected) + aux_warn,
            )
            if not ok:
                return
            ok = messagebox.askyesno(confirm_title, "再次确认：确定要永久删除这些会话吗？")
            if not ok:
                return
        else:
            # 回收站模式可恢复，不做"不可恢复"警告，仅中性提示
            aux_note = f"\n\n（含 {aux_count} 个附属数据：缓存/日志等）" if aux_count else ""
            ok = messagebox.askyesno(confirm_title, "以下内容将移入回收站（可恢复）：\n\n" + preview(selected) + aux_note)
            if not ok:
                return

        self._run_clean(selected, permanent)

    def _quick_clean(self) -> None:
        """一键清理：弹窗选择天数，清理所有 Agent 中更早的旧会话（不含附属数据）。

        与顶部时间筛选解耦——顶部筛选只管显示，一键清理的天数在这里单独选（默认 30 天）。
        """
        win = tk.Toplevel(self)
        win.title("一键清理")
        win.transient(self)
        win.geometry("430x210")
        win.resizable(False, False)

        ttk.Label(
            win,
            text="清理所有 Agent 中超过指定天数未活动的旧会话（移入回收站，可恢复）：",
            wraplength=390,
        ).pack(padx=14, pady=(12, 8), anchor="w")

        row = ttk.Frame(win)
        row.pack(fill="x", padx=14, pady=4)
        ttk.Label(row, text="清理超过:").pack(side="left")
        day_var = tk.StringVar(value="30")
        cmb = ttk.Combobox(
            row, textvariable=day_var, values=["7", "30", "90", "180", "365"],
            state="readonly", width=6,
        )
        cmb.pack(side="left", padx=(4, 0))
        ttk.Label(row, text="天未活动的旧会话").pack(side="left")

        # 预估预览：随天数变化实时刷新，让用户先看到规模再决定
        lbl_preview = ttk.Label(win, text="", foreground="#666666")
        lbl_preview.pack(padx=14, pady=4, anchor="w")

        def update_preview(_event=None) -> None:
            try:
                days = int(day_var.get())
            except ValueError:
                return
            target = quick_clean_target(self.reports, days)
            if target:
                total = sum(s.size for s in target)
                lbl_preview.config(text=f"将清理 {len(target)} 个旧会话（约 {human_size(total)}）")
            else:
                lbl_preview.config(text=f"没有超过 {days} 天未活动的旧会话。")

        cmb.bind("<<ComboboxSelected>>", update_preview)
        update_preview()

        def confirm() -> None:
            try:
                days = int(day_var.get())
            except ValueError:
                return
            target = quick_clean_target(self.reports, days)
            if not target:
                messagebox.showinfo("提示", f"没有超过 {days} 天未活动的旧会话。", parent=win)
                return
            total = sum(s.size for s in target)
            ok = messagebox.askyesno(
                "一键清理确认",
                f"将清理所有 Agent 中超过 {days} 天未活动的 {len(target)} 个旧会话（约 {human_size(total)}），\n"
                "移入回收站（可恢复）。",
                parent=win,
            )
            if not ok:
                return
            win.destroy()
            self._run_clean(target, permanent=False)

        btns = ttk.Frame(win)
        btns.pack(side="bottom", fill="x", padx=14, pady=(8, 12))
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right")
        ttk.Button(btns, text="清理", command=confirm).pack(side="right", padx=(0, 6))

        self._center_window(win)
        win.grab_set()

    def _run_clean(self, sessions: list[Session], permanent: bool) -> None:
        """后台线程执行清理（进度条 + 按钮禁用 + 异常兜底），供勾选清理与一键清理复用。"""
        self._set_busy(True)
        self.progress.configure(maximum=len(sessions), value=0)
        self.lbl_status.config(text=f"正在清理 0/{len(sessions)} …")

        def worker() -> None:
            try:
                def on_progress(done: int, total: int, name: str) -> None:
                    self._msg_queue.put(("clean_progress", done, total, name))

                result = clean(sessions, permanent=permanent, progress=on_progress)
                self._msg_queue.put(("clean_done", result))
            except Exception as e:  # 兜底：任何未预期异常都弹窗提示并恢复界面
                self._msg_queue.put(("clean_error", e))

        threading.Thread(target=worker, daemon=True).start()

    # ---------- 清理进度 ----------

    def _on_progress(self, done: int, total: int, name: str) -> None:
        """后台线程每删完一个会话回调一次（经 after 调度回主线程）。"""
        self.progress.configure(maximum=total, value=done)
        short = name if len(name) <= 40 else name[:37] + "…"
        self.lbl_status.config(text=f"正在清理 {done}/{total}：{short}")

    def _on_clean_error(self, exc: Exception) -> None:
        """清理线程抛出未预期异常时的兜底处理（主线程）。"""
        get_logger().error("清理线程异常: %s", exc)
        self._set_busy(False)
        self.progress.configure(value=0)
        self.lbl_status.config(text=f"清理出错: {exc}")
        messagebox.showerror("清理出错", f"清理过程中发生未预期的错误：\n\n{exc}")

    def _on_clean_done(self, result: CleanResult) -> None:
        """清理线程结束后的收尾（主线程）。"""
        self._set_busy(False)
        self.progress.configure(value=0)
        self.lbl_status.config(text=f"已清理 {len(result.ok)} 个，失败 {len(result.failed)} 个，约释放 {human_size(result.freed)}")
        if result.failed:
            shown = result.failed[:20]
            more = f"\n… 共 {len(result.failed)} 条失败" if len(result.failed) > 20 else ""
            messagebox.showwarning("部分失败", "\n".join(shown) + more)
        elif result.ok:
            messagebox.showinfo("完成", result.summary())
        self.do_scan()  # 清理后刷新

    def _set_busy(self, busy: bool) -> None:
        """清理期间禁用所有操作按钮，防止重复点击/误操作。"""
        state = ("disabled",) if busy else ("!disabled",)
        for b in self.control_buttons:
            b.state(state)
        self.btn_scan.state(state)


def main() -> None:
    App().mainloop()
