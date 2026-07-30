# Changelog

Mark42 模块化智能铠甲系统的所有重要变更记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 修复
- 🧪 **测试全线崩溃修复**：conftest.py 残留 27 处旧导入路径 `mark42_modules`，
  收集阶段崩溃导致全部用例 ERROR。统一改为 `mark42`，恢复 1318 passed。
- 🔒 **armor compact 锁 fd 健壮性**：`_try_acquire_compact_lock` 的 `os.open`
  在标准流被上层关闭时（如 pytest fd 捕获）会拿到 fd 0/1/2 并误关。
  改用 `fcntl.F_DUPFD` 重定位到 >=3 + `/dev/null` 补位低位 slot。
- 🐛 **逻辑修复**：
  - armor.py 删除「连续压缩无效检测」里的死代码空循环（读 actions_log 后 `pass` 不做事）
  - consciousness.py 的 `assessment` 结果纳入返回值（原先计算后丢弃）

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

## [2.8.1] - 2026-07-29

### 新增
- 📦 **安装器修复**：同步 scripts/mark42_modules/ -> mark42-pkg/mark42/（44->75 文件）
  - 新增 audit/ interfaces/ plugins/ 三个子包
  - pyproject.toml 添加 loop_templates.yaml 到 package-data
  - CLI 添加 `--version` 参数
  - `pip install -e .` 验证成功, `mark42 --version` -> v2.7.0
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
- 🏗️ **cli.py 拆分为 cli/ 包**（1426行 -> 4 个文件）：
  - `cli/__init__.py`：包入口 + re-export
  - `cli/assemble.py`（394行）：assemble 进程管理
  - `cli/status.py`（236行）：状态面板
  - `cli/parser.py`（798行）：argparse + 命令分发

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
- 🔒 `shell=True` 3 处清零（governance.py + cli.py）
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
