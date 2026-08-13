"""Tkinter 图形界面。

布局：
  顶部：扫描按钮 + 总览
  上半：各 Agent 汇总表（标题栏带全选/清空；点击行查看其会话）
  下半：会话列表（标题栏带全选/清空；第一列点击勾选）
  底部：状态栏 + 清理到回收站 / 永久删除
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cleaner import CleanResult, clean, filter_by_days, merge_selected, preview
from . import config
from .models import AgentReport, Session, human_size
from .registry import all_agents
from .scanner import scan_all, summary_line
from .utils import ToolTip, open_in_file_manager, reveal_target

CHECK = "✅"        # 已勾选（大号符号，比 ☑ 更醒目）
UNCHECK = "⬜"      # 未勾选（大号方框，比 ☐ 更醒目）
CHECKED_TAG = "checked"          # 勾选行的 tag（背景高亮）
CHECKED_BG = "#e6f4ea"           # 勾选行背景色（浅绿）


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Agent 会话清理工具")
        self.geometry("1000x720")
        self.minsize(820, 560)

        self.reports: list[AgentReport] = []
        self.sessions: list[Session] = []        # 当前选中 Agent 的会话
        self.checked_paths: set[str] = set()     # 已勾选会话的路径集合
        self.checked_agents: set[str] = set()    # 已勾选"清理整个 Agent"的 id 集合
        self.control_buttons: list[ttk.Button] = []  # 清理期间需要禁用的按钮
        self.filter_days: int | None = None      # 时间筛选：None=全部，N=只显示 N 天前的旧会话

        self._build_ui()
        self.after(200, self.do_scan)  # 启动后自动扫描一次

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
        b2 = ttk.Button(top_bar, text="清空", command=self._check_none_agents)
        b2.pack(side="left", padx=(4, 0))
        self.control_buttons += [b1, b2]
        cols = ("check", "agent", "sessions", "aux", "size", "storage")
        self.tree_agents = ttk.Treeview(top_frame, columns=cols, show="headings", height=5)
        headers = (("check", 34, ""), ("agent", 150, "Agent"), ("sessions", 55, "会话"), ("aux", 55, "附属"), ("size", 105, "总大小"), ("storage", 370, "存储位置"))
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
        b4 = ttk.Button(sess_bar, text="清空", command=self._check_none_sessions)
        b4.pack(side="left", padx=(4, 0))
        self.control_buttons += [b3, b4]
        cols2 = ("check", "kind", "name", "size", "modified")
        self.tree_sessions = ttk.Treeview(sess_frame, columns=cols2, show="headings")
        for cid, w, txt in (("check", 34, ""), ("kind", 52, "类型"), ("name", 370, "会话"), ("size", 100, "大小"), ("modified", 150, "最后活动")):
            align = "center" if cid in ("check", "kind") else "w"
            self.tree_sessions.heading(cid, text=txt, anchor=align)
            self.tree_sessions.column(cid, width=w, anchor=align)
        self.tree_sessions.tag_configure(CHECKED_TAG, background=CHECKED_BG)
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

    # ---------- 扫描 ----------

    def do_scan(self) -> None:
        """重新扫描所有 Agent 并刷新界面。"""
        self.btn_scan.state(["disabled"])
        self.lbl_status.config(text="正在扫描…")
        # 扫描后清空所有勾选，避免残留勾选导致误删
        self.checked_agents.clear()
        self.checked_paths.clear()
        try:
            self.reports = scan_all()
        except Exception as e:  # 扫描失败不应崩溃
            self.lbl_status.config(text=f"扫描出错: {e}")
            self.btn_scan.state(["!disabled"])
            return
        self._refresh_agents()
        self.lbl_summary.config(text=summary_line(self.reports))
        self.lbl_status.config(text=f"扫描完成 {summary_line(self.reports)}")
        self.btn_scan.state(["!disabled"])

    def _refresh_agents(self) -> None:
        self.tree_agents.delete(*self.tree_agents.get_children())
        for r in self.reports:
            checked = r.agent in self.checked_agents
            mark = CHECK if checked else UNCHECK
            tags = (CHECKED_TAG,) if checked else ()
            shown = self._filter_sessions(r.sessions)
            session_n = len([s for s in shown if s.kind != "aux"])
            aux_n = len([s for s in shown if s.kind == "aux"])
            size = sum(s.size for s in shown)
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
        # 会话在前、附属数据在后（附属默认不勾选）
        for s in sorted(self.sessions, key=lambda x: x.kind == "aux"):
            checked = s.path in self.checked_paths
            mark = CHECK if checked else UNCHECK
            tags = (CHECKED_TAG,) if checked else ()
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

    def _check_none_agents(self) -> None:
        """清空 Agent 选择。"""
        self.checked_agents.clear()
        for item in self.tree_agents.get_children():
            self.tree_agents.set(item, "check", UNCHECK)
            self.tree_agents.item(item, tags=())
        self._update_status()

    def _check_all_sessions(self) -> None:
        """全选会话：勾选当前 Agent 列表里的全部会话。"""
        for s in self.sessions:
            self.checked_paths.add(s.path)
            self.tree_sessions.set(s.path, "check", CHECK)
            self.tree_sessions.item(s.path, tags=(CHECKED_TAG,))
        self._update_status()

    def _check_none_sessions(self) -> None:
        """清空会话选择。"""
        self.checked_paths.clear()
        for item in self.tree_sessions.get_children():
            self.tree_sessions.set(item, "check", UNCHECK)
            self.tree_sessions.item(item, tags=())
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
            """关闭：手打的路径落盘 + 重新扫描。"""
            for aid, var in entries.items():
                val = var.get().strip()
                config.set_agent_path(aid, val or None)
            win.destroy()
            self.do_scan()

        # 修改即时保存：点右上角 X 关闭时落盘手打路径并重新扫描
        win.protocol("WM_DELETE_WINDOW", on_close)

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
        aux_warn = (
            f"\n\n⚠️ 其中包含 {aux_count} 个附属数据（缓存/日志等），"
            "删除后通常无法恢复，请确认不再需要。"
            if aux_count
            else ""
        )
        if permanent:
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
            ok = messagebox.askyesno(confirm_title, "以下内容将移入回收站（可恢复）：\n\n" + preview(selected) + aux_warn)
            if not ok:
                return

        # 后台线程执行清理，避免界面卡死；进度经 after() 回主线程更新
        self._set_busy(True)
        self.progress.configure(maximum=len(selected), value=0)
        self.lbl_status.config(text=f"正在清理 0/{len(selected)} …")

        def worker() -> None:
            try:
                def on_progress(done: int, total: int, name: str) -> None:
                    self.after(0, lambda: self._on_progress(done, total, name))

                result = clean(selected, permanent=permanent, progress=on_progress)
                self.after(0, lambda: self._on_clean_done(result))
            except Exception as e:  # 兜底：任何未预期异常都弹窗提示并恢复界面
                self.after(0, lambda: self._on_clean_error(e))

        threading.Thread(target=worker, daemon=True).start()

    # ---------- 清理进度 ----------

    def _on_progress(self, done: int, total: int, name: str) -> None:
        """后台线程每删完一个会话回调一次（经 after 调度回主线程）。"""
        self.progress.configure(maximum=total, value=done)
        short = name if len(name) <= 40 else name[:37] + "…"
        self.lbl_status.config(text=f"正在清理 {done}/{total}：{short}")

    def _on_clean_error(self, exc: Exception) -> None:
        """清理线程抛出未预期异常时的兜底处理（主线程）。"""
        self._set_busy(False)
        self.progress.configure(value=0)
        self.lbl_status.config(text=f"清理出错: {exc}")
        messagebox.showerror("清理出错", f"清理过程中发生未预期的错误：\n\n{exc}")

    def _on_clean_done(self, result: CleanResult) -> None:
        """清理线程结束后的收尾（主线程）。"""
        self._set_busy(False)
        self.progress.configure(value=0)
        self.lbl_status.config(text=f"已清理 {len(result.ok)} 个，失败 {len(result.failed)} 个")
        if result.failed:
            messagebox.showwarning("部分失败", "\n".join(result.failed))
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
