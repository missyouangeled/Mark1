# Changelog

Mark42 模块化智能铠甲系统的所有重要变更记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.4.0] - 2026-07-20

### 新增
- 🔧 GitHub Actions CI（`mark42-ci.yml`）：多 Python 版本测试 + coverage 门禁 50% + lint 检查
- 🔧 GitHub Actions 自动发版（`mark42-release.yml`）：tag 触发 -> 测试 -> CHANGELOG -> Release
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
