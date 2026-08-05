# Changelog

Mark42 模块化智能铠甲系统的所有重要变更记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.8.2] - 2026-08-05

> 41 次提交 · 259 文件变更 · +8228/-1540 行 · 3 天工作量（8-03 —— 8-05）
> 门禁终检：**1975 passed / 25 skipped / 0 failed · mypy 0 issues · ruff All checks passed**
> CI：8 步门禁含 `禁止 cast/type:ignore 伪清零` 守卫 · pre-commit hook 双层 · SBOM 生成

### 8-04：armor_compress 重构 + P1 批次修复（8 次提交）

- **armor_compress 三轮拆分**：680 行函数拆为 5 个子功能 + 常量提模块级，补齐 43 个单测
- **aware/naive datetime 相减 bug**：冷却期检查混用 `datetime.now()` 和 `fromisoformat(aware)` 抛 TypeError 被 except 吃掉 → 冷却期形同虚设
- **版本号 2.8.1 → 2.8.2**
- **P1 修复批次**：隐私回退/异常真实性/数据完整性/scheduler large 桶安全策略/Loop 事务锁与状态机真实性/熔断器单探针/Heavy 状态机与 CLI 退出码语义/systemd 整条部署链契约 + watchdog/installer 失败传播

### 8-05 上午：审查方案 P1/P2/P3 全部清零（24 次提交）

- **成本时区 bug**：cost_tracker 用 UTC 落盘但按本地日期查，早班时段（00:00–08:00）日报恒为 0。新增 `_local_date()` 统一换算
- **P2-15 compact 锁 unlink 竞态**：`_release_compact_lock()` 无条件删除，被他人接管的锁会被误删。加 token 比对 + inode 校验，发现 inode 会被复用，两重缺一不可
- **P2-16 openclaw.json 路径硬编码**：4 处，其中 3 处是模块级常量（import 时固化），`OPENCLAW_CONFIG` 环境变量与 TOML 全部无效。建 `get_openclaw_config_path()` 作为全仓唯一入口，刻意不缓存
- **P1-5 context-safety apply**：原流程先把新配置写进正式文件再 validate，失败只塞返回值，无效配置原地留着。改为先校验后替换 + 失败回滚 + 默认 dry-run。发现 `flock()` 不可重入（差点锁死），预校验不能把环境问题当非法
- **P2-6 并发整份覆盖**：compaction_apply 和 context_safety_apply 在锁外读快照，并发时拿陈旧整份覆盖，静默吃掉别人刚写的字段。发现仓里已有正确原语但没人用，统一走 `patch_openclaw_config()`
- **P2-7 TOML 双轨制**：TOML 里 `warn=11` 运行时还是 70，向导让用户填的东西全是废的。建 `get_effective_config()` + 来源追踪
- **P3-2 撤销 4 项过期 skip**：问题被其他修复顺带治好，标记没人回来撤，套件显示为绿但实际没覆盖
- **P3-3 原子写故障注入修复**：`os.kill` 写在写函数调用之前，子进程压根没进写流程，旧测试从未验证过原子性。5 个真实注入点 + after_replace 覆盖
- **P3-5 静默异常**：6 处，其中两处静默削弱系统能力——armor 压缩计数分母偏小使升级告警条件永不满足；llm_rate 成功率虚高
- **P3-6 未来 schema 降级**：schema 99 被改写成 2 写回磁盘，新版配置被旧版程序读一次就永久降级
- **mypy 174→0 分五轮，捞出 8 个真 bug**：
  - `audit/checker.py` 导入**不存在的** `get_llm_provider`，宽泛 except 吃掉 ImportError —— 审计的 LLM 语义对比能力**从未真正工作过**
  - `assemble_restart(agent=...)` 真实签名零参，调用即 TypeError
  - `status_dashboard(all_agents=...)` 同类
  - `perf_bench._warmup` 标注与全部 3 个调用点不符
  - PID 非整数导致 `os.kill()` 抛 TypeError 逃逸 except，`assemble --status` 崩溃
  - 混沌实验 monkeypatch 零参函数替换有参的真实签名，验证韧性的实验自己成了故障源
  - JSON 顶层非对象导致全仓状态读取崩溃
  - 两处退出码契约漏洞
  - 全仓 cast 0 处，type:ignore 仍为原有 1 处
- **CI 门禁**：GitHub Actions 8 步 + pre-commit hook，含禁止 cast/type:ignore 伪清零守卫，门禁有效性已实测

### 8-05 中午：全系统审查 + 3 项真实缺陷修复（5 次提交）

> 正式审查结论：**0 项假死**（cycle 真在推进，四 Loop 无一超自身周期 3 倍）

- **consciousness revalidate 谎报成功**：读协议 0/10 全败但 rc=0。根因：model.yaml 仍指向被 7-28 退出的 agnes 旧域名（apihub.agnes-ai.com 解析到 Teredo 保留段不可路由），配置没跟上决策。切火山方舟后恢复 9/10 通过
- **--config 显示"上下文窗口 0K"** 与 `armor --check` 报 1000000 自相矛盾
- **幽灵任务**：status 说 t1 在跑，heavy --finish 说不存在（scratchPath 字段只写不读）
- **合并 status_dashboard 双重实现**，消除双份维护隐患，幽灵任务 CLI 也可见
- **僵尸日志陷阱**：/mnt/data 日志 22 天未更新为僵尸副本，真实日志在 ~/.local/state。已归档 + 加 README

### 8-05 下午：JSON 静默丢盘修复（1 次提交）

- **`_save_json` 入口强制 str→Path 归一化**：调用方传入 str 时 `path.parent` 抛 AttributeError，被 `@safe_call(default=None)` **静默吞掉** —— 调用方以为保存成功，实际零字节落盘，08-05 09:24 真实发生两次。防回归 3 项，回退验证有效（摘掉归一化即 3 项转红，其中 atomic_overwrite 报 `{'v':1} != {'v':2}` 精准还原"不报错但数据没更新"的原症状）

### 工程体系

- **三元门禁**（CI 必过）：ruff 零告警 · mypy 零错误 · 全量测试零失败
- **元守卫**：禁止 `cast`/`type:ignore` 伪清零 · 测试文件数下限（防删测试换绿）
- **SBOM 生成**：`scripts/generate-sbom.sh` 追踪所有 Python 依赖 + 许可证
- **pre-commit hook**：`ruff check` + `mypy` 本地提交前拦截
- **全量 1975 测试 0 失败**，测试行数 2.88 万 > 源码 2.42 万（1.19:1）
- **40 份旧文档（18161 行）从桌面目录抢救入库**，获得版本保护
- **dev-portal 生成器**原被 .gitignore 整目录排除，修正为只排除产物

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
- 📋 **Audit 系统**：6 类 compact 后核对（tokens / sections / names / rules / headroom / artifacts）
  - `compact 审计` 子命令，输出审计报告 JSON
- 🧮 **动态阈值**：`compaction_diag_config` 新增 `dynamic_threshold` 模式
  - 按压缩率 % 自动调整触发阈值
  - `--tune-compaction` 子命令自动校准基线
- 🌐 **中文 hook**：`compaction-notifier` 全新中文 hook 取代英文默认
- 🧪 **测试大规模补齐**：全量 1622 项 0 失败
  - 新增 100+ 项针对原子写入、旧配置迁移、环境变量覆盖、版本一致性、PII 脱敏、熔断器、混沌实验、adapter 注册表的测试
  - 测试文件 76 个 > 源码 70 个（测试行数 2.7 万 > 源码 2.3 万）
- 🧪 **mypy 治理**：48 项
- 🧪 **CI 门禁**：GitHub Actions 7 步流水线含 ruff + mypy + pytest + 测试文件下限守卫

### 变更
- 🔧 **配置写入升级**：`context_safety_apply` 和 `compaction_apply` 统一走 `patch_openclaw_config()` 原语
  （锁内重读 + 字段级 patch + 原子写 + 校验 + 回滚）

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

## [2.7.0] - 2026-07-27

### 新增
- 🧠 **核心位注册表**：模块注册、三态自检(🟢🟡🔴)、动态装配。8 核心位定义覆盖 main_consciousness / armor_consciousness / memory_vector / code_analysis / log_classification / anomaly_detection / degraded_decision / advisor
- 🔌 **ArcLock 通用适配层**：10 大扩展点（config / module / loop / memory / safety / site / store / deploy / process / compile），`不配即用，按需扩展` 设计哲学
- 🔄 **混沌引擎**：主动注入延迟、错误模拟、资源耗尽三类故障
- ⚡ **熔断器**：防止级联故障
- 🗃️ **集群管理器**：核心位集群思维 —— 1 critical + 3 degradable + 4 optional
- 🧪 **测试补齐**：全量 1340 项 0 失败

## [2.6.0] - 2026-07-21

### 新增
- 🤖 **自主意识层**：Agent 自我状态感知、故障检测、降级决策
- 📊 **模块健康监控**：8 模块健康度实时监控
- ⬇️ **降级响应契约**：故障时自动降级行为
- 🔗 **LLM Provider 统一接口**：可插拔 LLM 后端
- 🐞 **错误档案**：结构化的错误记录与分析
- ✅ **v3 核心 8 模块测试补齐**：全量 967 项 0 失败

## [2.5.1] - 2026-07-21

### 修复
- 🔧 测试修复：全量 561 项 0 失败

## [2.5.0] - 2026-07-20

### 新增
- 🏗️ **重型战甲 Systemd 服务化**：完整守护进程生命周期
- 🔄 **循环引擎**：多个 Loop 并行执行引擎
- 📝 **审计系统**：压缩后审计核对
- 🧪 **测试补齐**：全量 482 项 0 失败

## [2.4.0] - 2026-07-20

### 新增
- 🛡️ **上下文铠甲**：AlgoScheduler 调度多算法策略、SmartCrusher 智能压缩切换、PII 脱敏日志
- 🧪 **全量 319 项 0 失败**

## [2.3.0] - 2026-07-19

### 新增
- 📦 **Mark42 原型**：OpenClaw 守卫三件套（armor / engine / heavy）
- 🧪 **首批 100+ 测试**

## [2.2.0] - 2026-07-10

### 新增
- 📚 **记忆召回体系**：5 层架构（L1 关键词 → L2 规则 → L2.5 Embedding 语义）
- 🏛️ **架构原则**：召回即用、召回与推断分离、不装 Agentic RAG

## [2.1.0] - 2026-06-22

### 新增
- 🔄 **OpenClaw 集成**：compaction hook、config 补丁、watchdog 联动
- 🧪 **测试框架**：pytest + mock 体系

## [2.0.0] - 2026-06-10

### 新增
- ⚙️ **模块化铠甲体系**：分层加载（核心层 → 域规则层 → 操作模板层）
- 📝 **启动流程规范**：BOOT_INDEX.md 分层加载，每会话只执行一次

## [1.0.0] - 2026-03-31

### 新增
- 🎯 **Mark42 项目启动**：首个提交，OpenClaw 智能铠甲系统概念验证