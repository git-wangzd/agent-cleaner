"""GUI 冒烟测试：验证勾选逻辑与字符渲染（临时诊断脚本，验证后可删）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tkinter import font as tkfont

from agent_cleaner.app import App


def main() -> None:
    app = App()
    app.update()
    app.do_scan()
    app.update()
    print("== reports ==")
    print([(r.agent, len(r.sessions)) for r in app.reports])

    print("== 全选 Agent 前 ==")
    print("checked_agents:", app.checked_agents)
    app._check_all_agents()
    app.update()
    print("== 全选 Agent 后 ==")
    print("checked_agents:", app.checked_agents)
    for r in app.reports:
        print("  ", r.agent, "mark=", repr(app.tree_agents.set(r.agent, "check")),
              "tags=", app.tree_agents.item(r.agent, "tags"))

    print("== 会话全选 ==")
    print("sessions 当前数量:", len(app.sessions))
    app._check_all_sessions()
    app.update()
    print("checked_paths 数量:", len(app.checked_paths))
    print("状态栏:", app.lbl_status.cget("text"))

    print("== 字符渲染宽度（TkDefaultFont）==")
    f = tkfont.Font(root=app, font="TkDefaultFont")
    for ch in ["☐", "☑", "□", "■", "✓", "⬜", "✅", "◻", "◼"]:
        print(f"  {ch!r} (U+{ord(ch):04X}) width={f.measure(ch)}")

    app._check_none_agents()
    app._check_none_sessions()

    # 异常兜底：替换弹窗避免阻塞，验证按钮/进度条被恢复
    import agent_cleaner.app as appmod

    appmod.messagebox.showerror = lambda *a, **k: None
    app._set_busy(True)
    app._on_clean_error(RuntimeError("模拟清理错误"))
    print("== 异常兜底后 ==")
    print("btn_scan state:", app.btn_scan.state())
    print("状态栏:", app.lbl_status.cget("text"))

    # 详情框：验证双击弹窗不抛异常（创建后立即销毁）
    appmod.messagebox = type("MB", (), {"showinfo": lambda *a, **k: None})()
    if app.sessions:
        app._show_detail_dialog(app.sessions[0])
        print("== 详情框 ==")
        print("详情框创建成功（已销毁）")
    for w in list(app.winfo_children()):
        w.destroy()

    # 设置对话框：验证打开不抛异常
    app._open_settings()
    print("== 设置对话框 ==")
    print("设置对话框打开成功（已销毁）")
    for w in list(app.winfo_children()):
        w.destroy()

    app.destroy()


if __name__ == "__main__":
    main()
