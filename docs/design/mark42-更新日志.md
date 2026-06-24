# Mark42 更新日志

> 每次代码/功能变动后追加一条，按日期倒序。
> 格式：日期 → 版本 → 标题 → 变更清单 → 验证结果。

---

## 2026-06-18 — v2.3.1 LLM 压缩链路修复

**背景**：铠甲 LLM 压缩需指定 provider/模型。先切到公司 DeepSeek，后改为 MiniMax M3（DeepSeek 留给主会话）。

### 变更清单

| # | 类型 | 内容 |
|:---|:---:|------|
| A | fix | armor.py:168 `_llm_analyze()` provider → `"minimax"`，默认模型 → `"MiniMax-M3"` |
| B | fix | cli.py:30 `assemble()` 补全 import `_now_iso, _save_json, _load_json`（之前漏 import 导致启动报错 NameError） |
| C | fix | config.json `llmProvider: deepseek` → `minimax`，`llmAnalyze: deepseek-v4-pro` → `MiniMax-M3` |

### 验证

- API key 查找链路：minimax → apiKey ✅
- assemble 启动：守护双进程正常拉起 ✅
- 烟测：18/18 全通过 ✅

### 修改文件

- scripts/mark42_modules/armor.py — provider + 默认模型名
- scripts/mark42_modules/cli.py — assemble() 补 import
- ~/.local/state/openclaw/mark42/config.json — llmProvider/llmAnalyze

---

## 2026-06-17 — v2.3.0 工程管理正式化

**背景**：工程越来越大，需要正式化流程。校准版本号为语义化版本 v2.3.0，整理文档体系，创建烟测脚本。

### 变更清单

| # | 类型 | 内容 |
|:---|:---:|------|
| D | chore | 版本号校准：v2.3 → v2.3.0（Semantic Versioning） |
| D | chore | 文档重组：context-loop-heavy.md → 架构设计.md；审查报告归入 审查报告/ 子目录 |
| D | chore | 新增 mark42-工程管理方案.md：版本号/分支/Git/质量门禁/每周检查 |
| D | chore | mark42-文档目录.md 新增路径速查表 + 工程管理方案入口 |
| D | chore | 修缮 mark42-运维日志.md（由 3天守护日志 改名，通用化为长期运维日志） |
| C | chore | 日志迁移到数据盘 /mnt/data/openclaw/mark42/logs/，新增 daemon 日志自动截尾（≤50MB） |
| C | chore | 清理旧日志目录 armor/daemon-logs/（已停止写入，残留 9.9KB） |
| B | feat | 创建 scripts/mark42-tests.py：8 模块导入 + 语法 + CLI + 配置文件 + 日志路径 + 守护启停 |
| A | fix | status_dashboard JSON 输出补上 version 字段 |
| A | fix | status --json 现在从 config.json 读取版本号 |

### 验证

- 烟测：python3 scripts/mark42-tests.py --full → **24/24 全通过**
- 守护启停：双守护启动 → 心跳正常 → stderr 干净 → 优雅关闭零残留
- 语法：compileall 零错误
- 版本号：config.json → 2.3.0，status --json → version: 2.3.0

### 修改文件

- scripts/mark42_modules/config.py — 版本号 2.3 → 2.3.0；新增 LOG_DIR/DATA_ROOT/MAX_DAEMON_LOG_MB/MAX_DAEMON_LOG_LINES
- scripts/mark42_modules/cli.py — status_dashboard 加 version 字段；assemble 日志输出到 LOG_DIR；_trim_daemon_logs()
- scripts/mark42_modules/engine.py — daemon 每 20 tick 检查日志大小自动截尾
- scripts/mark42_modules/logs.py — log_rotate 加 rotate_daemon_logs()
- scripts/mark42-tests.py — 新建
- docs/design/ — 5 个文件改名/新增

---

## 2026-06-17 — v2.2 阶段 1 核心缺口补齐

**背景**：Mark42 商品化路线图阶段 1（内测可用）A~E 五项诊断缺口需要全部补齐。经过完整代码审查 → 第一轮烟测 → 发现 bug → 修复 → 第二轮烟测 → 全绿通过。

### 新增/改进

| 项 | 模块 | 内容 |
|:---:|------|------|
| A | armor | LLM 压缩链路闭环：`_read_session_tail` 解嵌套 OpenClaw JSONL 格式（`{"type":"message","message":{"role":"user"}}`），读取消息从 0→60 条；`_llm_analyze` 中 `content` 数组提取修复 |
| B | engine | 清理 loops.json：23 个历史垃圾 → 3 个核心模板（context-guard / health-watch / task-watch） |
| C | armor+engine | 三模块事件桥接标准化：协议命名空间 `mark42.armor.compress.done` / `mark42.engine.loop.completed` / `mark42.engine.bridge.armor_compress_seen` / `mark42.engine.bridge.heavy_started` |
| D | cli | `status_dashboard(json_mode=True)` 纯 JSON 输出 + `--json` CLI 标志；engine daemon 每 10 次循环写入 `broker/views/mark42-status.json` |
| E | cli | `assemble()` 重写：`subprocess.Popen` fork armor-guard + engine-daemon，PID 文件 + 3 秒健康检查 + SIGTERM 优雅关闭 |

### 修复的 bug

1. **`_read_session_tail` 返回 0 条消息**：OpenClaw JSONL 外层是 `{"type":"message","message":{"role":"user","content":[...]}}`，原先在外层找 `"role"` 找不到
2. **`_classify_messages` content 提取失败**：OpenClaw content 是 `[{type:"text",text:"..."}]` 数组格式，原先当字符串处理
3. **`task-watch` 在无活跃任务时 `UnboundLocalError`**：`pending`/`failed` 变量未初始化
4. **daemon 无条件创建 watch Loop**：检测到 `heavy.task.started` 后未验证任务文件是否真实存在；已加守卫（文件存在 + 24h 内）
5. **`task-watch-2` 残留**：由已不存在的 `test-exec-demo` Heavy 任务触发创建；已手工清理 + 守卫防止复发

### 验证

- 第一轮烟测：9/9 全部通过（发现上述 5 个 bug）
- 第二轮烟测：16/16 全部通过（修复后零失败）
- LLM 压缩：DeepSeek V4 Pro 正确分析上下文 → `memory-index.json` 的 `modelGenerated: true`，策略从 `heuristic-classify` 升级为 `llm-analyze`
- assemble：fork 双守护进程启动 → 健康检查 → SIGTERM 优雅关闭，全程正常

### 修改文件

- `scripts/mark42_modules/armor.py` — 解嵌套 JSONL + content 数组提取 + 事件 emit
- `scripts/mark42_modules/engine.py` — 事件桥接 + Heavy watch 守卫 + mark42-status.json 写入 + BROKER_DIR 导入
- `scripts/mark42_modules/cli.py` — assemble 重写 + status --json
- `docs/design/mark42-商品化路线图.md` — 诊断标记 + 进度更新
- `~/.local/state/openclaw/mark42/armor/loops.json` — 清理 23→3

### 当前状态

- 版本：2.2
- 循环：3/3 活跃（context-guard cycle 3、health-watch cycle 3、task-watch cycle 5）
- Broker 事件：130 行 / 41.6KB
- Memory 索引：llm-analyze（`modelGenerated: true`）

---

## 2026-06-17 #2 — v2.3 daemon 持久化 + 资源泄漏 + 信号隔离修复

**背景**：v2.2 assemble 首次真跑后发现 6 个问题。逐行审查 3172 行代码 → 联网搜索最佳实践 → 修复 → 烟测全绿通过。

### 修复的 bug

1. **CLI 手动 `engine --run` 执行后 cycle/lastRun 不持久化**：上一版修复 isuue 时让 `engine_run_loop()` 不再自己 `_save_loops`，但忘了给 CLI 手动路径留 `persist=True` 入口。加 `persist` 参数，daemon 传 `False`，CLI 默认 `True`
2. **daemon 的 loops 修改被丢弃（cycle 永远不递增）**：`engine_run_loop()` 内部自己 `_load_loops()` 了独立副本，daemon 传入的 `loops` dict 从未被改动。加 `_loops` 可选参数，daemon 传当前 `loops` 引用
3. **`assemble()` 每次启动泄漏 4 个文件句柄**：`open("a")` 返回的 stdout/stderr file object 在父进程中永不 `.close()`。合并为单 log fd（stdout+stderr 汇入同一文件），优雅关闭时 close，加 `start_new_session=True` 防止 Ctrl+C 穿透
4. **daemon broker 主循环内 `armor_compress()` 可能阻塞 45 秒**：LLM API 调用在 daemon tick 循环中，会卡住所有其他 Loop。改为 `subprocess.Popen` 异步启动压缩子进程
5. **`flock` 锁文件用 `"w"` 模式打开**：每次 truncate 已有内容，丢失元数据。改为 `"a"` 模式
6. **子进程未设置 `start_new_session`**：Ctrl+C 从父终端可能同时命中父进程和子进程。所有 `Popen` 加了 `start_new_session=True`

### 验证

- 烟测：6/6 全部通过（fd 泄漏 4→4 零泄漏、daemon tick 正常、cycle 递增 6→7→8、CLI 手动 run 持久化、assemble 优雅关闭无残留、导入验证）
- 无残留进程、无泄漏 fd

### 修改文件

- `scripts/mark42_modules/engine.py` — `engine_run_loop` 加 `persist`+`_loops` 参数；daemon 传 `persist=False, _loops=loops`；broker 压缩改为异步子进程；flock lock 文件 `"a"` 模式
- `scripts/mark42_modules/cli.py` — assemble 合并 stdout+stderr 为单 log fd；`start_new_session=True`；优雅关闭 close log fd；children 元组从 2→3 含 log_fd

### 当前状态

- 版本：2.3
- 循环：3/3 活跃（context-guard cycle 4、health-watch cycle 3、task-watch cycle 8）
- fd 泄漏：已消灭
- daemon 持久化：cycle 递增正确

---

*日志文件创建于 2026-06-17。此前所有开发记录分散在 `商品化路线图.md` 和各模块注释中。*

---

## 2026-06-17 #3 — v2.3 全线审查 + 红色项/黄色项修复

**背景**：完成 Mark42 全线审查（8 模块 / ~3200 行），对照设计文档 + 联网最佳实践，输出审查报告 `mark42-全线审查报告-20260617.md`。发现 12 个问题：🔴2 / 🟡7 / 🔵3。本轮全部红色+黄色修复。

### 修复的问题

| # | 等级 | 位置 | 问题 | 修复方式 |
|:---|:---:|------|------|------|
| B1 | 🔴 | engine.py | daemon 无心跳检测 | 每 tick 写 `daemon-heartbeat.json`（lastTick/cycle/loops）；assemble `proc.wait()` → 非阻塞轮询 `os.kill(pid,0)` + 30s 间隔 |
| D1 | 🔴 | config.py | 版本号 2.2 | `mark42_init()` 写入 `"version": "2.3"` |
| A1 | 🟡 | armor.py | token 估算精度低（BPT 常数偏大） | 前 100 行采样 → `avg_chars_per_line / 2.5` 动态校准；回退保留原固定估算 |
| C1 | 🟡 | heavy.py | 文件扫描规则 3 处重复 | 抽取 `_list_project_files()` 到 utils.py，`_SKIP_PATTERNS` 统一，preflight/detect/start 共用 |
| B3 | 🟡 | engine.py | health-watch df/free 解析脆弱 | 改用 `shutil.disk_usage()` + `/proc/meminfo`，不再依赖外部命令输出格式 |
| C3 | 🟡 | heavy.py | batch_size magic number | 加注释说明 200 分母是经验校准值 |
| B2 | 🟡 | engine.py | Loop 模板编号逻辑边界 | 同名活跃 Loop 提示 "将被覆盖"，加固边界 |
| C2 | 🟡 | heavy.py | execute 脚本 TODO 占位 | `heavy_execute` 新增 `command` 参数，`{f}` 替换为文件路径；CLI 加 `--command` |
| — | 🟡 | utils/config | `_load_json/_save_json` 重复 | **保留不动**：config.py 本地副本是防循环导入的架构决策 |

### 审查关键发现

- **设计一致性**：代码与 `mark42-context-loop-heavy.md` 设计文档无结构性偏离
- **事件总线**：文件追加 JSONL 符合单机轻量系统实践；Linux `O_APPEND` 写入 <4KB 时原子安全
- **信号隔离**：`start_new_session=True` 正确防止 SIGINT 穿透；SIGTERM 通过 `os.kill` 逐子进程发送
- **模块评分**：Armor 9 / Engine 8 / Heavy 7 / Config 9 / Utils 8 / CLI 8 / Logs 9 / CompactionDiag 8

### 验证

- 烟测：assemble 启动双守护 → 心跳文件 30s 写入 → SIGTERM 优雅关闭 → 零残留 ✅
- 语法：全部 6 个修改文件通过 `ast.parse` ✅
- 公共函数：`_list_project_files` 在 heavy 三处统一调用

---

## 2026-06-24 下午 · Session Fence 冲突修复 + 阶段 1 完整落地

### 13:49 Session Fence 故障 ⚠️ → 14:30 修复 ✅

**故障**：`Agent failed before reply: session file changed while embedded prompt lock was released`

**根因**：`armor.py:413-427` 用 `open(active_session, "a")` + `write()` 直接向 active session 注入 `/compact` 命令。
但 OpenClaw 用 `sessionFileFenceKey` + `fenceGeneration` + fingerprint 机制保护 active session，
外部进程写入会触发 `EmbeddedAttemptSessionTakeoverError`——
因为 OpenClaw 进程内的 `ownedSessionFileWrites` map（`globalThis` 单例）不会记录外部进程写入。

**路径评估**：
- ❌ 路径 A（lock file + owner flag）：`isOpenClawSessionOwnerArgv` 会拒绝非 OpenClaw 进程
- ❌ 路径 B（HTTP/Unix socket IPC）：OpenClaw 未暴露 IPC server
- ✅ 路径 C（合规 CLI 通道）：`openclaw agent --message "/compact" --session-key agent:main:main`

**修复**：
- `armor.py:413-435` 重写：移除 `open(active_session, "a")`，改用 `subprocess.run(["openclaw", "agent", "--message", "/compact", "--session-key", "agent:main:main", "--timeout", "120", "--json"])`
- 新增 `scripts/mark42_modules/session_fence_safe.py` 提供：
  - `trigger_compact_via_cli()`：合规 CLI 触发压缩
  - `write_shadow_note()` / `append_shadow_log()`：shadow 文件写入（绝对不碰 active session）
  - `fence_self_check()`：模块导入时自检，4 项检查全绿
- 新增 `scripts/mark42_modules/test_session_fence.py` 专项测试 4 项全绿

### 阶段 1 Day 2: PII 脱敏 ✅

新增 `scripts/mark42_modules/pii_redactor.py`：
- 13 种 PII 类型：email / 中国手机 / 身份证 / 信用卡 (Luhn) / OpenAI key / GitHub token / Anthropic key / JWT / IPv4 / 敏感路径 / URL with token / 弱中文姓名
- Luhn 算法验证信用卡号真伪
- 支持字符串 + dict/list 递归脱敏
- `local IP` (127.x / 0.0.0.0) 不误伤
- **13/13 单元测试全绿**

### 阶段 1 Day 3: 算法调度策略 ✅

新增 `scripts/mark42_modules/algo_scheduler.py`：
- 大小分层：tiny (skip) / small (1KB-10KB) / medium (10KB-100KB) / large (>100KB review)
- 内容类型分流：JSON → SmartCrusher；纯文本 → 保留
- 安全护栏：
  - 压缩率 < 10% → 视为无效，回退原文
  - 压缩后 > 原文 80% → 视为失败，回退原文
  - 错误 → fail-safe 永远返回原文
- 大内容自动启用 PII 脱敏
- **10/10 单元测试全绿**

### 烟测最终结果 (mark42-tests.py)

| 模块 | 测试 | 状态 |
|------|------|------|
| 模块导入 | 12 个模块 | ✅ 全绿 |
| 语法检查 | compileall | ✅ 零错误 |
| CLI 入口 | mark42.py --help / status | ✅ v2.3.0 |
| 关键文件 | config.json / loops.json (5 Loop) | ✅ |
| 日志路径 | 5 个状态目录 | ✅ |
| Day 1 压缩 | SmartCrusher 单元测试 | ✅ |
| Day 2 PII | PIIRedactor 13 个测试 | ✅ |
| Day 3 调度 | Scheduler 10 个测试 | ✅ |
| Session Fence | 4 个 fence 安全测试 | ✅ |
| **总计** | **26 通过 / 0 失败** | **✅ 全绿** |

### 关键修复要点 (供未来参考)

1. **绝对禁止** `open(active_session, "a")` 直接写入 — 必触发 fence 冲突
2. **合法通道**：CLI (`openclaw agent --message <cmd>`) / shadow 文件 / system event
3. **PII 脱敏**：LLM 调用前必走 `redact_pii()`，默认启用
4. **压缩护栏**：低压缩率 / 失败率都回退原文
5. **fail-safe 原则**：所有压缩/脱敏错误都返回原文，永不让错误传播到 LLM

---

## 2026-06-24 下午 · 阶段 1 Day 4 完成：算法调度器接入 armor ✅

### 改造目标
把 Day 1-3 写的 `algo_scheduler` / `pii_redactor` 真正接到 `armor_pre_compact_hook` 主流程，
不再让 Day 1-3 的代码是"孤立模块"。

### 代码改动

**`scripts/mark42_modules/config.py`**
- 新增 `ALGO_USE_SCHEDULER`（默认 true）— 总开关
- 新增 `ALGO_PII_ENABLED`（默认 true）— PII 总开关
- 新增 `ALGO_FAIL_SAFE`（默认 true）— 出错回退原文

**`scripts/mark42_modules/armor.py`**
- import 调度器（`_SCHEDULER_AVAILABLE` 自检）
- `armor_pre_compact_hook` 拆成两条路径：
  - `_hook_via_scheduler()` — 新路径（默认）：PII + 大小分层 + 护栏 + fail-safe
  - `_hook_direct_smartcrush()` — 旧路径（`MARK42_ALGO_USE_SCHEDULER=false` 退回）
- 新增 stats 字段：
  - `mode` — `"scheduler"` 或 `"direct"`
  - `piiRedactions` — 脱敏命中数
  - `decisionsByBucket` — `{tiny/small/medium/large}` 分布
  - `fallbackCount` — 护栏回退次数

**`scripts/mark42_modules/test_day4_integration.py`** （新文件）
- 7 个集成场景：调度器路径 / dry_run / 大小分层 / 降级 / fail-safe / 双重门 / 端到端
- 7/7 全绿

**`scripts/mark42-tests.py`**
- 新增 `test_day4_integration()` 钩子（带 env 注入）

### 行为变化

**之前**（Day 1-3）：
- `armor_pre_compact_hook` 直接调 `smartcrush()`
- 无 PII 脱敏 → 敏感信息直接送 LLM
- 无大小分层 → 小内容也压（浪费时间）
- 无护栏 → 压缩率低时仍强制写入
- 错误时崩溃 → armor 守护退出

**现在**（Day 4）：
- 默认走 `algo_scheduler.process()` — 自动按内容大小分层
- 中型以上内容**自动 PII 脱敏**（邮箱/手机/身份证/信用卡/API key 等 13 种）
- 压缩率 < 10% → 自动回退原文
- 压后 > 原文 80% → 自动回退原文
- 任何错误 → fail-safe 静默回退，armor 守护不退出
- `MARK42_ALGO_USE_SCHEDCRUSHER=false` 可一键退回旧路径

### 烟测最终 (mark42-tests.py)

| 模块 | 测试 | 状态 |
|------|------|------|
| 模块导入 | 12 个模块 | ✅ 全绿 |
| 语法检查 | compileall | ✅ 零错误 |
| CLI 入口 | mark42.py --help / status | ✅ v2.3.0 |
| 关键文件 | config.json / loops.json (5 Loop) | ✅ |
| 日志路径 | 5 个状态目录 | ✅ |
| Day 1 压缩 | SmartCrusher 单元测试 | ✅ |
| Day 2 PII | PIIRedactor 13 个测试 | ✅ |
| Day 3 调度 | Scheduler 10 个测试 | ✅ |
| Session Fence | 4 个 fence 安全测试 | ✅ |
| **Day 4 集成** | **7 个集成场景** | ✅ |
| **总计** | **27 通过 / 0 失败** | **✅ 全绿** |
