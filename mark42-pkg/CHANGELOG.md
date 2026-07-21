# Changelog

Mark42 模块化智能铠甲系统的所有重要变更记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
