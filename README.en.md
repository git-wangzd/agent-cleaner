# 🧹 Agent Session Cleaner

> [中文](README.md) | English

A cross-platform desktop GUI tool to scan and clean up session and cache data accumulated by various AI agents. **Deletion goes to the recycle bin / trash by default (recoverable).**

Built with pure Python standard library + Tkinter, zero third-party dependencies.

## ✨ Features

- 🖥️ Cross-platform desktop app (Windows / macOS / Linux)
- 🤖 Supports **16 mainstream AI agents** (see below)
- 🗑️ Deletion goes to recycle bin by default (recoverable); permanent deletion requires double confirmation
- 🧹 Sessions and auxiliary data (cache/logs) cleaned separately; auxiliary data unchecked by default
- ⏱️ Time filter: show only sessions inactive for 7 / 30 / 90+ days
- 📂 Project filter + 🔍 session search: quickly locate by project / keyword
- 🚀 One-click cleanup: clear old sessions of all agents by day range
- 🔁 Invert selection: quickly flip checkbox states
- ⚙️ Custom paths: auto-detect official env vars + manual config in settings UI (directory picker)
- 📊 Background-thread scanning / cleaning with real-time progress; UI never freezes
- 🔍 Double-click a session for details; right-click to open its storage folder
- 🔄 Update check on startup / manually (GitHub Releases)
- 📦 Three-platform auto builds (GitHub Actions)

## 🤖 Supported Agents

| Agent | Storage location (Windows) |
|---|---|
| Claude Code | `%USERPROFILE%\.claude\projects` + `sessions` |
| Codex CLI | `%USERPROFILE%\.codex\sessions` |
| Cursor | `%APPDATA%\Cursor\User\workspaceStorage` |
| Windsurf | `%APPDATA%\Windsurf\User\workspaceStorage` |
| OpenCode | `%USERPROFILE%\.local\share\opencode` (SQLite / files) |
| Gemini CLI | `%USERPROFILE%\.gemini\tmp` |
| Continue | `%USERPROFILE%\.continue\sessions` |
| Cline | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev` |
| Qwen Code | `%USERPROFILE%\.qwen\projects` |
| Kimi CLI | `%USERPROFILE%\.kimi` |
| Tongyi Lingma | `%USERPROFILE%\.lingma\index\chat` |
| Trae | `%APPDATA%\Trae\User\workspaceStorage` |
| MarsCode CLI | `%USERPROFILE%\.marscode` |
| Pi | `%USERPROFILE%\.pi\agent\sessions` |
| AtomCode | `%USERPROFILE%\.atomcode\sessions` |
| MimoCode | `%USERPROFILE%\.local\share\mimocode` (SQLite) |

## 📥 Installation & Run

### Download binaries
Get the installer for your platform from [GitHub Releases](https://github.com/git-wangzd/agent-cleaner/releases) (Windows / macOS / Linux) and run it.

### Run from source (requires Python 3.10+)

```bash
python main.py          # launch the GUI
python main.py --list   # CLI mode: print scan results only
```

## 📖 Usage

1. Launch the app; all agents are scanned automatically
2. Check an agent (whole package) or individual sessions (use time/project filters + search to locate)
3. Click "Move to recycle bin" (recoverable) or "Delete permanently" (double confirmation)
4. Progress is shown in real time; the list refreshes automatically when done

## ⚙️ Configuration

Config file: `%APPDATA%\agent-cleaner\config.json` (Linux/macOS: `~/.config/agent-cleaner/config.json`):

```json
{
  "agent_paths": {
    "kimi": "D:/my/kimi-data"
  },
  "big_file_mb": 10
}
```

- **agent_paths**: override an agent's data directory (or use the directory picker in Settings)
- **big_file_mb**: big-file highlight threshold (default 10 MB, adjustable in Settings)
- Official env vars of agents (e.g. `CLAUDE_CONFIG_DIR`, `QWEN_HOME`, `ATOMCODE_HOME`) are auto-detected

## 🛡️ Safety

- Deletion goes to the recycle bin by default (recoverable); permanent deletion requires double confirmation
- Auxiliary data (cache/logs) is unchecked by default
- Cleaning OpenCode / MimoCode sessions manipulates their SQLite databases — quit the corresponding agent first
- Directories that may contain user data (`downloads` / `backups` / memory files) are **never** listed

## 🧪 Development

```bash
python -m unittest discover -s tests   # unit tests (74)
python smoke_test.py                    # GUI smoke test
```

## 📄 License

[MIT](LICENSE)

---

**v1.0.0**: 16 agents supported, complete cleanup ecosystem, 74 unit tests, three-platform auto build & release.
