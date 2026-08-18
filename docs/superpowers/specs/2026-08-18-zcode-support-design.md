# 新增 ZCode 支持设计文档

日期：2026-08-18
状态：已批准（2026-08-18）

## 背景

用户要求「新增支持 kimi code 和 zcode」。经确认：

- **Kimi Code**：保持现状。现有 `kimi.py` 已支持旧版 `~/.kimi` 布局，不做改动。
- **ZCode**（智谱 Z.ai 的 Agentic Development Environment / CLI）：新增支持。

本机未安装 ZCode，schema 依据第三方实测（codeburn，db v0.14.8，2026-06-20 验证）+ 官方文档（zcode.z.ai）。扫描器采用防御式列探测，版本差异不崩溃。

## 数据来源（研究结论）

| 数据 | 路径 | 说明 |
|---|---|---|
| 会话 | `~/.zcode/cli/db/db.sqlite` 的 `session` 表 | 列：`id`(PK)、`directory` 必存在；title/created_at/updated_at 等列需探测 |
| 关联表 | `model_usage`、`tool_usage` | 按 `session_id` 关联，删除会话时同步清理 |
| 终端输出缓存 | `~/.zcode/cli/exec/` | 官方 FAQ 确认可整个删除、ZCode 会自动重建、目前不自动清理 → `kind="aux"` |
| 环境变量 | `ZCODE_STORAGE_DIR` | 可重定位整个数据根目录（agentpeek 文档确认） |

**绝不列入**：`~/.zcode/cli/config.json`、`v2/config.json`（含 API Key）、`v2/credentials.json`、`cli/memories/`（记忆文件）、`agents/`/`skills/`/`commands/`（自定义配置）、`cli/log/`（活动日志，token 已脱敏但非官方确认可删）。

## 架构与组件

沿用现有 Agent 扫描器模式（参照 `opencode.py` / `mimocode.py`）：

```
zcode.py (ZCodeAgent) → registry.all_agents() → scanner.scan_all()
  → models.Session(path="sqlite://<db>#<sid>") → trash._delete_sqlite_session()
  → 通用 SQLite 删除（与 OpenCode/MimoCode 共用）
```

### ZCodeAgent（新文件 `agent_cleaner/agents/zcode.py`）

- `id = "zcode"`，`display = "ZCode"`，`storage_hint = "~/.zcode"`
- `env_var = "ZCODE_STORAGE_DIR"`
- `__init__`：`root = self.resolve_root(self.home_dir() / ".zcode")`；`db_path = root / "cli" / "db" / "db.sqlite"`；`exec_dir = root / "cli" / "exec"`
- `detect()`：`db_path.is_file()`
- `storage_root()`：root 存在时返回其路径
- `scan()`：
  1. `_scan_sqlite()`：db 存在时读取会话
  2. aux：`cli/exec/` 目录（`kind="aux"`, `is_dir=True`），大小为 0 跳过

### `_scan_sqlite()` 防御式列探测

1. `PRAGMA table_info(session)` 取实际列名
2. 必须包含 `id`、`directory`，否则返回空（版本不兼容不崩溃）
3. 候选可选列（存在才用）：
   - 标题：`title`、`slug`
   - 时间：`updated_at`、`created_at`、`time_updated`（毫秒转秒，参照 opencode 逻辑 `ts > 1e12`）
4. 会话名：`<directory 目录名>: <title|slug|id前8位>`（参照 opencode 的 label 组装，`directory` 必存在所以一定有项目名）
5. 大小：session 表无已知大小列 → 恒为 0
6. 会话 `path = f"sqlite://{db_path}#{sid}"`

### `trash.py` 改动

`_SQLITE_SESSION_TABLES` 增加 `"model_usage"`、`"tool_usage"`。循环本就按实际存在的表过滤（`sqlite_master` 探测），OpenCode/MimoCode 无这两张表会自动跳过，零风险。

### `registry.py` 改动

导入并注册 `ZCodeAgent()`（display 排序自动生效）。

### 测试（tests/test_scanner.py，沿用 BasePatchTest 模式）

1. `RegistryTest.test_all_agents_count`：16 → 17
2. `test_zcode_detects_db`：构造 `cli/db/db.sqlite` → detect True；无 db → False
3. `test_zcode_scan_sessions`：临时 db 建 `session`（含 id/directory/title/updated_at）+ `model_usage`/`tool_usage` 行 → 扫描出会话（名称、sqlite:// path、project 正确）
4. `test_zcode_scan_aux_exec`：`cli/exec/` 有内容 → 出 aux 条目
5. `test_zcode_missing_columns_no_crash`：db 只有残缺 schema → 返回空不抛异常
6. `test_zcode_trash_deletes_related_rows`：`delete_sessions` 后 model_usage/tool_usage 对应行被清（临时 db 拷贝）
7. 环境变量：`ZCODE_STORAGE_DIR` 覆盖根目录（参照现有 env_var 测试模式）

### CHANGELOG

v1.2.0 新增：ZCode 支持（会话 + 终端输出缓存），Agent 数 16 → 17。

## 风险与边界

- schema 为推断 + 第三方实测，防御式列探测兜底；文档注明「待验证」注释（参照 kimi.py 风格）。
- ZCode 正在运行时删除会锁库 → 通用 trash 逻辑已处理（locked/busy 报「请先退出」）。
- exec 缓存删除不影响会话记录与配置（官方确认）。
- 会话大小显示 0（无大小数据源），可接受——删除仍是安全的。

## 不做的事

- 不改 Kimi Code（保持旧版现状）
- 不扫 ZCode 日志、配置、凭据、记忆
- 不引入任何第三方依赖