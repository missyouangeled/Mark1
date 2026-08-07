# Changelog

Mark42 模块化智能铠甲系统的所有重要变更记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增 — 方案 44 Phase 0（基线冻结与回归集）

> 上游：`docs/plans/44-Mark42-全功能缺口补全方案-v1.md`
> 基线快照：`docs/plan44/phase0-baseline.json`（机器可读）
> 本阶段**纯数据契约 + 确定性评分**，不含 LLM 调用编排，不引入任何运行时开关。

- 📐 **`mark42/context_state.py`** — 冻结 `ContextState` / `SourceCursor` schema（方案 §4.2）
  - `ContextState`：session_intent / active_task / decisions / constraints / artifacts /
    completed_work / open_questions / next_steps / source_cursor / evidence_refs /
    **inferences（单列，永不与 evidence 混存）** / generated_at
  - `SourceCursor`：session_id + 文件标识 + inode + 字节偏移 + 最后消息 ID +
    观测大小 + 前缀哈希 + 消息条数；任一项不符即失效并**全量回退，禁止猜测续接**
  - `validate_context_state()`：evidence 强制、confidence 边界（含 bool 排除）、
    约束 ID 唯一、supersedes 链引用完整、推断不得自称事实、done 任务不得留在 active
  - `render_memory_index_view()`：把状态渲染成兼容视图，**旧 `memory-index.json` 消费方不受影响**
  - ⚠️ 边界：新增**旁路**能力，不修改也不替代 OpenClaw 官方 compact 流程
- 🔬 **`mark42/audit/probes.py`** — 冻结六类**响应能力**探针 schema（方案 §5）
  - 六维：intent / continuity / decision / artifact / evidence / instruction
  - **与现有 `AUDIT_CATEGORIES` 互不相交**：结构审计答「证据是否存在」，
    探针答「给定证据时模型能否合规响应」，两套分数分别保存（方案 §5.2）
  - `score_deterministic()`：先确定性断言，无断言才标 `skipped` 交 judge；
    保留 raw_response / judge_model / judge_prompt_version（方案 §5.3 禁止只存最终分数）
  - `evaluate_slo()`：总分 ≥24/30，instruction 与 evidence 单项 ≥4，
    约束违规或 hallucination 直接失败
  - `detect_regression()`：连续 3 次均值下降 >10% 触发回归事件
  - ⚠️ `GATE_CANNOT_AUTO_REVERT=True` — gate 模式**不承诺**自动撤销 compact；
    官方 CLI 返回后会话已改变，无官方恢复通道时只能保留证据 + 告警 + 停止升级（方案 §5.4）
  - ⚠️ `ProbeReport.disclaimer` — 报告强制声明：隔离模型调用**不等价于**生产 Agent 行为（方案 §6.2）
- 🧪 **`tests/fixtures/compaction_scenarios.py`** — 4 个冻结场景（`SCENARIO_SET_VERSION=1`）
  - `work_continuity`：目标/决策/文件/下一步齐全，驱动全部六维
  - `constraint_heavy`：5 hard + 1 soft，验证静态存活率
  - `inference_mixed`：事实与推断混杂，验证召回/推断分离
  - `sparse`：几乎无内容，专门钉住 `evidence_absent` 豁免逻辑
- ✅ **175 项新测试**（context_state 70 / probes 45 / scenarios 60），全量 2189 项 0 失败

### 修复

- 🐛 **`SourceCursor` 消息 ID 断裂判定是死分支**（自查发现，P0-SELF-001）：
  首版写成 `if first_message_id and ... and first_message_id == ""`，条件自相矛盾，
  该分支**永远不可能触发**。形态与方案 §17 批评 cross-encoder 的「只有可用性探针、
  实际不接入」完全一致。已改为对照调用方实测值比对，并做**红→绿反向验证**：
  把坏逻辑注回去测试变红（`assert 'ok' == 'message_id_gap'`），还原后变绿。
- 🐛 **`evidence_absent` 豁免**（自查发现，P0-SELF-002）：上游本就没有某维度证据时，
  探针必然低分。若直接计入严格 SLO，会把「上游无数据」误判为「模型能力退化」——
  即 HANDOFF 记录的「比较两端不同源」老毛病。现豁免严格单项判定，但仍如实计入总分。
- 🧹 **清掉 `docs/devportal/generate_fulltext.py` 的 8 个 ruff 错误**（F541×5 / I001 / UP032）：
  随 `e214bd85` 入库的既有技术债，全部纯语法修正、无行为变化。
  方案 §13 门禁第 3 条要求 ruff 全绿，故在 Phase 0 一并清理。


### 重构
- 🔨 **`armor_compress()` 拆分：665 行 → 235 行（-65%）**：该函数长期是全仓最大的
  单体函数，压缩流程的六个阶段（索引构建、事件上报、冷却期检查、已压缩预检、
  平台探测、CLI 调用、收尾审计）全部内联在一个函数体里，最深处嵌套 6 层缩进，
  任何一个阶段都无法独立测试。现拆为主编排器 + 13 个模块级子函数：
  - `_compress_build_index()` — LLM 优先 / 启发式回退的双分支索引构建
  - `_compress_log_events()` — broker 事件上报
  - `_compress_check_cooldown()` — 30 分钟压缩冷却期检查
  - `_compress_check_already_compacted()` — session 已含 compaction 摘要的预检
  - `_compress_run_compact_cli()` — Session Fence 验证 + `openclaw sessions compact` 调用
    + 三分支结果判定（摘要膨胀 / 压缩成功 / 文件未变回退 maxlines）
  - `_compress_write_action_log()` — actions.jsonl 审计写入 + bytesStatus 语义标记
  - `_compress_check_ineffective_escalation()` — 连续 ≥3 次压缩无效的升级报
  - `_compress_audit_hook()` — Post-Compact Audit 异步核对
  - `_try_acquire_compact_lock()` / `_release_compact_lock()` / `_platform_compact_probe()`
    从函数内嵌闭包提到模块级（`_platform_compact_probe` 的 `dry_run` 从闭包捕获
    改为显式参数）
  - `_compact_cooldown_file()` / `_compact_lock_file()` — 路径改为延迟求值函数，
    避免测试 monkeypatch `XDG_STATE` 时路径在 import 期被固化
  - 常量 `COMPACT_COOLDOWN_SEC` / `PLATFORM_PROBE_SEC` / `PLATFORM_PROBE_INTERVAL` /
    `COMPACT_LOCK_TTL_SEC` 提到模块级；`_PLATFORM_PROBE_SKIP_SLEEP` 显式定义为
    模块级 `False`（原先只在函数内 `getattr` 探测，模块级并不存在该属性）
  公开 API `armor_compress(dry_run)` 签名与返回结构完全不变，六个 `skip-*` 动作码
  （`skip` / `skip-cooldown` / `skip-already-compacted` / `skip-platform-handled` /
  `skip-locked`）行为保持一致。

### 修复
- 🔒 **compact 锁与冷却期完全失效（P0，重构副产品）**：`_now_iso()` 产出带时区偏移的
  时间戳（`2026-08-04T16:33:02+08:00`），但锁过期判定和冷却期判定都用 naive 的
  `datetime.now()` 相减，触发
  `TypeError: can't subtract offset-naive and offset-aware datetimes`。
  两处的 `except` 都把异常静默吞掉，后果是：
  1. **compact 锁形同虚设** — 异常后走「锁文件损坏」分支删锁重建，任何时刻
     两个 Mark42 实例都能同时对同一 session 执行 compact；
  2. **30 分钟冷却期形同虚设** — 反复 compact 已压缩过的 session，而 LLM 摘要 +
     结构化元数据会让文件比原文更大（实测膨胀 10KB+）。
  该 bug 在拆分前就存在，是子函数单测（同一进程连抢两次锁应第二次失败）把它暴露出来的。
  修复：新增 `_iso_age_seconds()` 统一处理时间差，按解析结果的 `tzinfo` 决定用
  aware 还是 naive 的当前时间，解析失败返回 `None` 而非抛异常。

### 测试
- ✅ **新增 `tests/test_armor_compress_units.py`（43 个子函数级单测）**：原有
  `test_armor_compress.py` 全是走完整 `armor_compress()` 流程的端到端测试，
  拆分后补齐阶段级覆盖 —— 锁机制 8 个（含 TTL 过期、文件损坏、缺时间戳恢复）、
  平台探测 5 个、索引构建 8 个、冷却期 5 个、已压缩预检 6 个、
  审计日志 5 个（bytesStatus 四态）、无效升级 6 个。
- 🔧 **修正 `test_ineffective_history_triggers_escalation_event`**：该测试连续调用
  `armor_compress()` 两次，原先依赖冷却期 bug 才能穿过第二次调用（属于
  「靠 bug 侥幸通过」）。冷却期真正生效后显式清除冷却标记，模拟两次压缩间隔已超 30 分钟。
- 📊 测试总数 1768 → 1811（+43），Ruff 0 告警。

### 已知待办
- ⚠️ **CI workflow 文件缺失**：2026-08-03 的记录称已补齐 `py3.13` 矩阵、版本一致性检查、
  `build` job 和 `sbom` job，但仓库内 `.github/workflows/` 目录实际不存在，
  只有 `ISSUE_TEMPLATE/`。需要重新落地。

### 修复
- 🛡️ **JSON 状态写入改为原子操作（数据完整性，P0）**：`utils._save_json()` 和
  `config._conf_save_json()` 原本直接 `open(path, "w")` 截断旧文件再写，进程在写入
  途中被 kill -9 / OOM / 断电会在磁盘上留下半截 JSON，下次读取直接解析失败并
  静默返回空字典，Armor/Engine/Heavy 的所有状态都有丢失风险。现改为
  临时文件 + `fsync` + `os.replace()` 原子替换，并保留原文件权限。
  已用真实 `SIGKILL` 故障注入和四进程并发写入验证。
- 🔢 **版本号统一为单一来源（P0）**：新增 `config.get_version()`，优先读
  `importlib.metadata`，源码态回退 `__version__`。修正 `mark42_init()` 硬编码
  `"version": "2.3.0"` 导致 `mark42 status` 在安装 2.8.1 的机器上长期显示 2.3.0 的问题；
  CLI `--version`、status 面板、`mark42 --config` 全部改走统一入口。
- 🔄 **旧配置自动迁移**：新增 `CONFIG_SCHEMA_VERSION` 和 `_migrate_config_if_needed()`。
  旧配置的 `version` 字段挭到 `legacyVersion` 留痕，迁移前自动备份 `.bak`，
  用户自定义的阈值、模型和 daemon 配置一律不动。
- 🌍 **MARK42_* 环境变量真正生效（P1）**：`MARK42_WORKSPACE`、`MARK42_STATE_DIR`、
  `MARK42_LOG_DIR`、`MARK42_MAX_DAEMON_LOG_LINES` 文档和 systemd unit 都声明了，
  但 `config.py` 之前完全不读，导致 unit 里的 `Environment=` 形同虚设。
  现统一优先级：环境变量 > 平台默认。
- 🐍 **Python 3.14 兼容**：`code_compressor.py` 移除已弃用的 `ast.Str`，
  改用 `ast.Constant` + 值类型判定。
- 🧹 **Ruff 零告警**：清理 3 处静默 `except/pass`（改为 `logger.debug` 留痕）、
  2 处未使用 import、2 处 import 排序。
- 🧪 **测试全线崩溃修复**：conftest.py 残留 27 处旧导入路径 `mark42_modules`，
  收集阶段崩溃导致全部用例 ERROR。统一改为 `mark42`。
- 🔒 **armor compact 锁 fd 健壮性**：`_try_acquire_compact_lock` 的 `os.open`
  在标准流被上层关闭时（如 pytest fd 捕获）会拿到 fd 0/1/2 并误关。
  改用 `fcntl.F_DUPFD` 重定位到 >=3 + `/dev/null` 补位低位 slot。
- 🐛 **逻辑修复**：
  - armor.py 删除「连续压缩无效检测」里的死代码空循环（读 actions_log 后 `pass` 不做事）
  - consciousness.py 的 `assessment` 结果纳入返回值（原先计算后丢弃）

### 新增
- ✅ **CI 补齐**：`mark42-ci.yml` 测试矩阵增加 Python 3.13；新增「版本一致性检查」
  （防止版本号再次漂移回 2.3.0）；新增 `build` job 做 wheel/sdist 构建 +
  干净 venv 安装冒烟测试。修正 README 的 CI badge 指向（原指向不存在的 `ci.yml`）。
- 🧪 **25 项回归测试**：`tests/test_atomic_write_and_version.py` 覆盖原子写入、
  序列化失败不损坏旧文件、权限保留、SIGKILL 故障注入、多进程并发、
  版本一致性防回归、配置迁移和环境变量覆盖。测试总数 1712 → 1737。

### 变更
- 🧹 **全量 lint 清零**：mark42/ 91 个 + tests/ 674 个 ruff 问题全部清理，
  CI 门禁 `ruff check mark42/ tests/` 首次真正转绿。
  - 清 21 个未用 import、12 个未用变量、拆 13 处分号多语句
  - 重命名歧义变量、lambda 改 def
  - 安全告警逐处 noqa 注明理由（LLM API urllib / 硬编码系统命令 / 测试数据 / 生成脚本）
  - B023 循环闭包假阳性（同迭代内被 pattern.sub 消费）配置忽略
- 🌍 **`/mnt/data` 路径可移植化**：引入 `config.DATA_MOUNT`
  （`MARK42_DATA_MOUNT` env 覆盖 + XDG_STATE 回退），
  snapshot_reader/engine/heavy 不再写死数据盘路径。Mark42 现可移植到任意机器。

### 新增
- 📋 **商品化文件补齐**：
  - `.github/ISSUE_TEMPLATE/`（bug_report / feature_request / config.yml）
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `ROADMAP.md` / `TROUBLESHOOTING.md` / `MIGRATION.md`
  - `.pre-commit-config.yaml`
  - README 加 badge（CI / Python / License / Version / Tests）+ 文档导航扩展

### 新增 - 方案 44 Phase 3（Hybrid Recall + Cross-Encoder）

- 🔍 **`mark42/audit/memory_retrieval.py`** - Hybrid Recall（§9.2）
  BM25 + Vector 并行召回 -> RRF 融合 -> 去重 -> 截断 -> 可选重排。
  降级链：rerank 失败 -> hybrid -> bm25_only -> empty。
  端到端验证通过。
- 🎯 **`mark42/audit/reranker.py`** - Cross-Encoder Reranker 接口（§9.3）
  Reranker Protocol + QMDReranker 适配器 + NoopReranker 降级。
  方案 §9.1 校正：旧 _rerank_available() 是死探针。

### 新增 - 方案 44 Phase 4（Heavy DAG + 局部重规划）

- 🗺️ **`mark42/heavy_graph.py`** - DAG 依赖图 + 资源预算 + 图校验
- 🔄 **`mark42/heavy_replan.py`** - 局部重规划（retry/skip/replace/split/merge）+ Checkpoint

### 新增 - 方案 44 Phase 5（混沌自动闭环 + 反馈学习）

- 📊 **`mark42/audit/remediation_feedback.py`** - 执行结果回写 + L3->L2 降级 + 有效性追踪
- 🔥 **`mark42/audit/chaos_scheduler.py`** - L0-L3 安全等级 + 自动调度 + 缺陷候选

### 新增 - 方案 44 Phase 6（Shadow 对比 + 回滚演练）

- 📈 **`mark42/audit/shadow_report.py`** - 新旧路径对比 + 趋势汇总
- 🔙 **`mark42/audit/rollback_drill.py`** - 6 项 flag 回滚验证（全部通过）

### 修复（审查发现 + 遗留项）

- `apply_rerank` 把 QMDReranker 对象当裸 Callable 调用 -> TypeError。已适配 Protocol。
- `context_builder.session_intent` 从 userIdentity 取而非会话目标。已改。
- `_build_incremental` 占位逻辑替换为真正的 LLM + merge_patch 合并。
- `snapshot_reader` offset-naive vs offset-aware datetime TypeError。已修。
- `_has_evidence` 白名单漏 0/False。已改真值判定。
- `SourceCursor.MESSAGE_ID_GAP` 死分支。已修。
- `_item_key` 取不到任务主键 -> 两条安全规则静默失效。已修。

### 最终数据

- 2545 项测试 0 失败（基线 2014）
- ruff 全绿 / mypy 89 文件 0 issues
- 30 个模块 import 全成功
- 10 个 ArcLock 锁扣全活
- 回滚演练 6/6 通过
- 所有 feature flag 默认关闭，零行为变化

## [2.8.1] - 2026-07-29

### 新增
- 📦 **安装器修复**：同步 scripts/mark42_modules/ -> mark42-pkg/mark42/（44->75 文件）
  - 新增 audit/ interfaces/ plugins/ 三个子包
  - pyproject.toml 添加 loop_templates.yaml 到 package-data
  - CLI 添加 `--version` 参数
  - `pip install -e .` 验证成功, `mark42 --version` -> Mark42 v2.8.1
- 🧙 **交互式配置向导**：`user_config.py` 新增 `interactive_init()` 函数
  - 5 步引导: 路径 -> 阈值 -> 模型 -> 守护进程 -> 日志
  - CLI `--init` 接入向导，已有配置时提示不覆盖
- 📖 **用户文档三件套**：
  - QUICKSTART.md: 5 分钟快速上手（1.6KB）
  - TUTORIAL.md: 7 章完整教程（5.3KB）含安装/配置/日常/进阶/排障/FAQ
  - INDEX.md: 文档导航 + 命令速查 + 配置速查 + systemd 速查
  - README.md 开头添加快速导航表格和 3 步命令

### 修复
- 🛡️ **错误处理升级**：6 个模块从 print+return 升级为 logging + 异常保护
  - `heavy.py`: +logging, 10 处错误 print -> logger.error + print（用户可见 + 持久记录）
  - `armor.py`: +logging, 9 处警告 print -> logger.warning
  - `engine.py`: +logging, 3 处错误 print -> logger.error + print
  - `compaction_diag.py`: +logging, openclaw.json 写入加 try/except 自动回滚
  - `context_safety.py`: +logging, `_save_openclaw_config()` 加备份 + 写入失败自动回滚
  - `config.py`: +logging
  - 所有 CLI 输出的 print 保留（用户仍可见），仅错误/警告走 logger

### 文档
- 📝 崩坏案例 15: subagent 修改 context_safety.py 导致 gateway.mode 丢失

### 测试
- ✅ 80 个测试全过（heavy 41 + armor 29 + compaction_diag + context_safety + engine + config）

## [2.8.0] - 2026-07-29

### 新增
- 🔒 **Constraint Pinning（约束保护）**：compact 后从 SOUL.md/USER.md/AGENTS.md 提取关键约束，通过 broker 事件 + 临时文件双通道重新注入
  - 新文件: `scripts/mark42_modules/audit/pinning.py` (202 行)
  - `builtin_audit.py` 的 `audit_compact()` 现在在审计完成后自动调用 pinner
  - 灵感来源: arxiv Governance Decay 论文
- 📝 **Artifact Trail（第6类核对）**：从 context-summary 和 daily transcript 提取修改的文件路径
  - `audit/__init__.py`: AUDIT_CATEGORIES 从 5 类增加到 6 类（新增 `artifacts`）
  - `snapshot_reader.py`: 新增 `_extract_artifacts()` 和 `_extract_artifacts_from_transcript()` 方法
- 🎯 **动态阈值系统**：根据上下文窗口大小自动调整阈值
  - `config.py`: 新增 `get_dynamic_thresholds(context_window)` 函数
  - 小窗口(128K): WARN=70 ALERT=85 CRIT=95 (基准)
  - 大窗口(1M): WARN=60 ALERT=75 CRIT=90 (更早介入，context rot 更严重)
  - 中间值线性插值
  - `armor.py` 的 armor_check / armor_compress / bridge_health_monitor 全部改用动态阈值
- 🇨🇳 **中文版 compaction-notifier Hook**：覆盖 OpenClaw 内置的英文通知
  - compact 开始时发: `🧹 正在压缩对话～！一会说～！`
  - compact 结束时发: `✅ 压缩完成（X -> Y tokens），继续聊～！`
  - 纯脚本，不经过模型
  - 位置: `~/.openclaw/hooks/compaction-notifier/`
- 📌 **postCompactionSections 配置**：compact 后自动重新注入 AGENTS.md 的关键段落

### 修复
- 🐛 移除非法的 `compaction.enabled` 字段导致的配置验证失败

### 测试
- 🧪 新增 5 个 SQLite Fallback 测试：正常返回/无 compaction/CLI 错误/超时/命令不存在
- 📊 summary_extractor.py 覆盖率从 72% 提升到 80%+
- 📊 总测试数: 73 个 audit 单元测试 + 163 单测 + 12 集成测试 = 248 全过
- 📊 覆盖率: checker 87% / snapshot_reader 93% / summary_extractor 80%+ / report 90% / pinning 91% / builtin_audit 87%

## [2.7.0] - 2026-07-27

### 新增
- 🔧 **ArcLock 电磁锁扣系统**：9 大 Protocol 接口 + 内置实现 + 注册器 + arclock.yaml 配置
- 🔧 **install.sh 配置向导**：安装后自动初始化 arclock.yaml + 打印配置向导引导
- 🔧 **arclock.yaml.tmpl**：包内模板，安装时自动复制到状态目录
- 📄 **CONFIG-GUIDE.md**：完整配置向导文档（openclaw.json / config.toml / arclock.yaml / systemd / 环境变量）
- 📄 **README.md 重写**：QuickStart 更新为最新功能（含 ArcLock / Consciousness / Breaker / Chaos 等新模块）

### 变更
- 🔄 pyproject.toml package-data 补 templates/*.yaml + templates/*.tmpl

## [2.6.0] - 2026-07-21

### 新增
- 📄 新增 `ARCHITECTURE.md` 五层架构设计文档

### 重构
- 🏗️ **algo_scheduler 解耦**：用注册表模式替代硬 import 6 个压缩器，新增 `register_compressor()` / `unregister_compressor()` API
- 🏗️ **cli.py 拆分为 cli/ 包**（1426行 -> 2 个文件）：
  - `cli/__init__.py`：包入口 + re-export + argparse + 命令分发
  - `cli/status.py`：状态面板

### 新增
- 📝 补全 `__main__.py` / `utils.py` / `cli/__init__.py` docstring
- 🔧 `pyproject.toml` 新增 `[tool.mypy]` 配置段（strict-ish）

### 修复
- 🐛 ruff format 修复 `algo_scheduler.py` / `armor.py` 格式

## [2.5.1] - 2026-07-21

### 新增
- 🧪 新增 2 个测试模块：test_cli.py（18 条）、test_consciousness.py（62 条）
- 🔧 补回 `.github/workflows/ci.yml`（多版本 Python 测试 + lint + pip-audit + 密钥扫描）
- 🔧 补回 `.github/workflows/release.yml`（tag 触发 -> 测试 -> build -> GitHub Release）
- 📦 新增 `.dockerignore`

### 修复
- 🔧 ruff lint 清零：318 -> 0（F405/F403 per-file-ignores + B007/E741/S103 手动修复 + unsafe-fixes 清理 F841）
- 🐛 修复 test_pii_redactor.py 缺失 `import json`（star import 不会带入）
- 🐛 修复 test_llm_text_compressor.py 的 `_clean_llm_output` 未导入 + 相对导入 + `logger.info()` 空调用
- 🐛 修复 test_consciousness.py 的 `SelfCheckResult` 字段名错误 + `CertaintyAssessment.is_certain` 不存在
- 🐛 修复 test_cli.py 的 S110 except-pass noqa 标注位置

### 变更
- 🔄 测试目录统一：合并 `mark42/tests/` 到 `tests/`（消除两套测试并行的问题）
- 🔄 `mark42/tests/` 10 个文件迁移至 `tests/`，删除重复的 test_smart_crusher.py（保留更全面的旧版）
- 🔄 原模块 `_run_tests()` 的 import 路径从 `mark42.tests.` 改为 `tests.`
- 🔄 清理残留文件：cli.py.bak、scripts/refactor_*.py（8 个）、dist/、egg-info/、.ruff_cache/
- 🔄 删除过时文档 docs/refactor-cli-plan.md（CLI 重构已完成）

## [2.5.0] - 2026-07-20

### 新增
- 🧪 测试补全：59 -> 311 用例（+252），覆盖 9 个新模块
  - test_utils.py, test_output_guard.py, test_smart_crusher.py
  - test_circuit_breaker.py, test_error_archive.py
  - test_context_safety.py, test_compaction_diag.py
  - test_heavy.py, test_watchdog.py
- 🔧 ruff lint + format 配置（pyproject.toml），自动修复 651 个问题
- 🐳 Dockerfile 加 HEALTHCHECK（mark42 status --json，60s 间隔）
- 🔧 install.sh 改用 wheel 安装（pip wheel -> pip install *.whl）
- 🔧 MANIFEST.in 确保 templates/*.toml + systemd/*.timer 打包

### 修复
- 🔧 daemon 函数 print -> logger（cli.py 31 处）
- 🔧 Dockerfile 去掉重复代码复制（scripts/mark42_modules/）
- 🔧 docker-build.sh 构建上下文改为 mark42-pkg 自身
- 🔧 pyproject.toml package-data 补 templates/*.toml
- 🔧 CI workflow 清除旧 scripts/mark42_modules/ 路径引用

### 变更
- 🔄 pyproject.toml 加 [tool.ruff] 配置（E/W/F/I/UP/B/S 规则集）

## [2.4.0] - 2026-07-20

### 新增
- 🔧 GitHub Actions CI（`ci.yml`）：多 Python 版本测试 + lint 检查
- 🔧 GitHub Actions 自动发版（`release.yml`）：tag 触发 -> 测试 -> build -> GitHub Release
- 🐳 Docker 镜像支持（`Dockerfile` + `docker-build.sh`）：python3.12-slim 非root
- 🔒 pip-audit 依赖漏洞扫描集成到 CI
- 🔒 硬编码 API key / 路径安全检查集成到 CI
- 📖 README 重写：Quick Start 5 步 + 命令速查表

### 修复
- 🔧 `install.sh`：`pip install` 改用 venv/pipx 方案，解决 `externally-managed-environment`
- 🔧 修复 15 个失败测试（config 模型断言更新 + CLI dispatch + engine 日期过期 + integration 参数适配）
- 🔒 `shell=True` 3 处清零（chaos_engine.py + cli.py）
- 🔒 `mark42-pkg` 中 `/mnt/data` 硬编码清零（config/installer/engine）

### 变更
- 🔄 README 仓库地址改为真实地址 `github.com/missyouangeled/Mark1`
- 🔄 测试模型断言：MiniMax-M3/minimax -> doubao-seed-2.0-pro/volcengine-agent

## [2.3.0] - 2026-07-17

### 新增
- 📦 可安装 Python 包（`pip install .` + `mark42 install`）
- 📦 systemd 服务模板化（占位符渲染，支持任意 Linux 环境）
- 📦 一键安装脚本 `install.sh`
- 📦 `mark42 install` / `mark42 install --uninstall` 命令
- 🧱 新增 `log_setup.py` 统一日志模块（5 级日志，环境变量控制级别）
- 🧱 新增 `installer.py` 安装器模块
- 🧪 完整测试套件（4 个文件，59 个测试，覆盖 armor/config/engine/logs）

### 变更
- 🔄 上下文压缩模式：`--max-lines 200`（截短）→ LLM 摘要模式 + 截短 fallback
- 🔄 WARN 阈值（70%）直接触发压缩，不等 ALERT（85%）
- 🔄 LLM 分析模型：MiniMax-M3（额度耗尽）→ doubao-seed-2.0-pro
- 🔄 LLM 分析超时：60s → 120s
- 🔄 LLM 分析 prompt 精简：40条/200字/8192 → 20条/150字/4096
- 🔄 `print()` → `logging`（521 处替换，保留 cli.py 交互式输出）
- 🔄 裸 `except Exception:` → `except Exception as e:` + `logger.exception()`（42 处）
- 🔄 `shell=True` → `shell=False`（3 处，安全加固）
- 🔄 路径去硬编码：4 处 `openclaw` 裸调 → `shutil.which()` 动态查找
- 🔄 WORKSPACE / openclaw.json 路径 → 环境变量 + 默认值推导
- 🔄 所有模块导入 → 相对导入（`from .xxx import`）

### 修复
- 🐛 armor guard 在 systemd 环境中找不到 `openclaw` CLI（PATH 不继承）
- 🐛 `openclaw sessions compact` 调用使用截短模式而非 LLM 摘要
- 🐛 LLM 分析因 MiniMax 额度耗尽而静默失败（`except Exception:` 吞错误）
- 🐛 context_safety.py 中 `openclaw config validate` 路径硬编码

## [2.2.0] - 2026-07-10

### 新增
- 🧠 意识协议（Consciousness）：读取协议、心跳守护、记忆快照
- 🧯 context-safety 子命令：OpenClaw context 安全基线检查
- 🖥️ 核心位注册表（Core Registry）
- ⚡ 熔断器（Circuit Breaker）
- 🔥 混沌工程（Chaos Engineering）

### 变更
- 📋 CLI 重构：argparse 结构化，所有子命令统一入口
- 📋 模块拆分完成：从单文件 `mark42.py` 拆为 32 个模块

## [2.1.0] - 2026-07-01

### 新增
- 🔄 循环引擎（Engine）：注册、调度、守护进程
- ⚙️ 重型战甲（Heavy）：异步任务队列
- 🧹 日志轮替：历史文件、actions 日志、broker 事件、daemon 日志
- 📊 OpenClaw 压缩配置诊断 & 调优
- 📚 错误档案管理

### 变更
- 📋 配置系统：统一模型配置表 + 运行时 config.json
- 📋 模型路由：支持多用途独立配置（llmAnalyze / llmCompress）

## [2.0.0] - 2026-06-24

### 新增
- 🛡️ 上下文铠甲（Armor）：实时检测 + LLM 驱动记忆索引 + 启发式回退
- 🧠 智能压缩算法：SmartCrusher + 调度器 + PII 脱敏 + 压缩护栏
- 📦 Broker 事件系统：操作记录、轮替、状态追踪
- 🔒 文件锁：防止 daemon 和 CLI 并发写入冲突

### 变更
- 📋 从概念设计进入工程实现
- 📋 Mark42 铠甲分层加载体系建立

## [1.0.0] - 2026-06-20

### 新增
- 🎯 Mark42 概念诞生：模块化智能铠甲系统
- 📐 架构设计：上下文铠甲 + 循环引擎 + 重型战甲
- 📐 设计文档：`docs/design/mark42-context-loop-heavy.md`

---

> 版本号说明：
> - **主版本**：不兼容的 API 变更
> - **次版本**：向后兼容的新功能
> - **修订号**：向后兼容的 bug 修复
