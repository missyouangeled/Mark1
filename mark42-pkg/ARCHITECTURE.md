# Mark42 架构设计文档

> 模块化智能铠甲系统 - 为 OpenClaw 提供上下文守护与循环引擎。

本文档描述 Mark42 v2.6.0 的五层架构设计、模块职责、数据流和扩展机制。

---

## 1. 设计哲学

Mark42 的核心设计原则只有一句话：

> **召回层只负责找原文，所有综合/推断都留在上层 LLM。**

这意味着 Mark42 不是"更聪明的 AI"，而是"更可靠的守护"。铠甲做的是机械的、确定性的工作--监测、压缩、轮替、预警。凡涉及判断的，交给上层对话中的 LLM。

三个指导原则：

1. **守护而非接管** - 铠甲监测问题并执行预设策略，不替用户做决策
2. **可观测性优先** - 所有自动行为写 broker 事件，可追溯、可复盘
3. **模块解耦** - 每层可独立运行，某层故障不拖垮其他层

---

## 2. 五层架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    L5: 治理层 Governance                  │
│   混沌工程 · 模块健康 · 集群管理 · 熔断器                  │
├─────────────────────────────────────────────────────────┤
│                  L4: 意识层 Consciousness                 │
│   自检 · 确信度评估 · 自动修复 · 主动交流                   │
├─────────────────────────────────────────────────────────┤
│                    L3: 重型战甲 Heavy                     │
│   大工程检测 · 预检 · 分批执行 · scratch 工作区            │
├─────────────────────────────────────────────────────────┤
│                    L2: 循环引擎 Engine                     │
│   Loop 调度 · 模板系统 · daemon 守护                       │
├─────────────────────────────────────────────────────────┤
│                    L1: 上下文铠甲 Armor                    │
│   使用率监测 · 多策略压缩 · 压缩队列 · 守护模式             │
├─────────────────────────────────────────────────────────┤
│                  基础设施层 Infrastructure                 │
│   config · logs · broker 事件总线 · utils · watchdog      │
└─────────────────────────────────────────────────────────┘
```

每层之间通过 **broker 事件总线** 松耦合，不直接调用上层。数据流方向：L1-L3 产生事件 → L4-L5 消费事件做判断。

---

## 3. L1: 上下文铠甲 Armor

**模块文件**: `armor.py` (1016 行)
**CLI**: `mark42 armor --check / --compress / --guard / --queue-stats`

### 职责

监测 OpenClaw 会话的上下文窗口使用率，超阈值时触发多策略压缩。

### 工作流

```
armor_check()  ──→  读取 session JSONL  ──→  估算 token 数
                                                    │
                    ┌───────────────────────────────┘
                    ▼
              usage < 70%?  →─→ 🟢 正常
              usage > 70%?  →─→ 🟠 警告 (broker event)
              usage > 85%?  →─→ 🔴 触发压缩
              usage > 95%?  →─→ 🔴 critical + 紧急压缩
                    │
                    ▼
           armor_compress()
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   algo_scheduler   PII     log_dedup
   (策略调度)     (脱敏)    (去重)
        │
   ┌────┼────┬────┬────┐
   ▼    ▼    ▼    ▼    ▼
 diff  code  text smart  llm_text
 compress crush compress crush  compress
```

### 阈值配置

| 级别 | 默认阈值 | 行为 |
|------|----------|------|
| 🟢 正常 | < 70% | 无操作 |
| 🟠 警告 | ≥ 70% | 写 broker 警告事件 |
| 🔴 告警 | ≥ 85% | 触发自动压缩 |
| 🔴 紧急 | ≥ 95% | 紧急压缩 + 跳过队列 |

阈值可通过环境变量 `MARK42_CTX_WARN_PCT` / `MARK42_CTX_ALERT_PCT` / `MARK42_CTX_CRIT_PCT` 或 config.toml 覆盖。

### 压缩策略

Armor 不自己做压缩，而是委托给 `algo_scheduler`（见 §6）。压缩流水线：

1. **PII 脱敏** (`pii_redactor`) - 去除敏感信息
2. **日志去重** (`log_deduplicator`) - 去除重复日志行
3. **算法调度** (`algo_scheduler`) - 根据内容类型选择最佳压缩器
4. **压缩执行** - diff / code / text / smartcrush / llm_text 五选一

### 守护模式

`armor --guard --interval 300` 以 5 分钟周期循环检查，持续运行。由 `assemble` 统一管理生命周期。

### 压缩队列

高负载时压缩请求入队 `compress_queue.py`，按优先级执行，防止并发压缩冲突。

---

## 4. L2: 循环引擎 Engine

**模块文件**: `engine.py` (596 行)
**CLI**: `mark42 engine --list / --start / --kill / --daemon / --templates`

### 职责

定时执行预设的循环任务（Loop），遵循 **Observe → Decide → Act** 三段式模式。

### Loop 生命周期

```
engine_start()  ──→  注册 Loop (写 loops.json)
                         │
engine_daemon()  ──→  30s 轮询
                         │
              ┌──────────┼──────────┐
              ▼                     ▼
        到达间隔?              maxCycles 达到?
              │                     │
     engine_run_loop()         标记 stopped
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
   Observe  Decide   Act
   (读取)   (判断)   (执行)
```

### 内置模板

| 模板名 | 周期 | 描述 |
|--------|------|------|
| `context-guard` | 300s | 持续监控上下文健康 + 自动压缩 |
| `health-watch` | 600s | 系统健康监控（CPU/内存/磁盘） |
| `model-fallback` | 60s | 监测模型可用性，记录 failover 事件 |
| `task-watch` | 30s | 大工程执行监控 |

### daemon 模式

`engine --daemon --interval 30` 以 30 秒为周期轮询所有注册的 Loop。daemon 通过 `daemon-heartbeat.json` 写心跳，`assemble` 监控心跳超时。

---

## 5. L3: 重型战甲 Heavy

**模块文件**: `heavy.py` (548 行)
**CLI**: `mark42 heavy --detect / --preflight / --start / --execute / --finish / --cleanup`

### 职责

当用户需要处理大量文件（代码迁移、批量重构、大规模分析）时，Heavy 提供分批执行、上下文隔离和进度追踪。

### 工作流

```
heavy_detect()     ──→  自动判断是否"大工程"
                         │
heavy_preflight()  ──→  预检：文件数、总大小、语言分布
                         │
heavy_start()      ──→  创建 scratch/{task_name}/ 工作区
                         │                ├── batches.json (分批计划)
                         │                ├── status.json (状态)
                         │                └── manifest.json (文件清单)
                         │
heavy_execute()    ──→  执行下一批次 (默认 dry-run)
                         │                ├── --execute-now 才真跑
                         │                └── 每批结果写入 status.json
                         │
heavy_finish()     ──→  收工，生成总结
                         │
heavy_cleanup()    ──→  清理 scratch 工作区
```

### 安全机制

- **默认 dry-run** - 不加 `--execute-now` 只预览不执行
- **上下文感知** - 自动检测是否需要上下文隔离（避免污染主会话）
- **scratch 工作区** - 每个任务独立目录，互不干扰
- **.keep 保护** - 标记的目录不会被自动清理

---

## 6. algo_scheduler: 压缩器调度器

**模块文件**: `algo_scheduler.py` (370 行)

### 职责

根据内容特征（大小、类型、结构）自动选择最佳压缩策略。

### 注册表模式

```
_REGISTRY: dict[str, CompressorEntry] = {}
    "smartcrush" → smartcrush()
    "code"       → codecrush()
    "diff"       → diff_compress()
    "log"        → logdedup()
    "text"       → text_compress()
```

调度器在模块加载时通过 `_register_builtin_compressors()` 自动注册 5 个内置压缩器。

### 扩展 API

```python
from mark42.algo_scheduler import register_compressor, get_compressor, list_compressors

# 注册自定义压缩器
def my_compressor(data: str) -> tuple[str, dict]:
    # 压缩逻辑
    return compressed, stats

register_compressor("my_algo", my_compressor)

# 查询
print(list_compressors())       # ['code', 'diff', 'log', 'my_algo', 'smartcrush', 'text']
entry = get_compressor("my_algo")  # CompressorEntry(name="my_algo", func=...)
```

外部插件可以注册自己的压缩器，无需修改 Mark42 源码。

### 调度策略

`SchedulerConfig` 定义内容分类规则和对应的压缩器选择：

| 内容类型 | 检测信号 | 选择 |
|----------|----------|------|
| tiny (<1KB) | size < 1024 | skip (不值得压缩) |
| JSON 大数组 | `[{...}, {...}, ...]` | smartcrush (数组截断) |
| 代码 | `def`/`class`/`import` 密度高 | codecrush |
| 日志 | `[DEBUG]`/`[INFO]` 密度高 | logdedup |
| 普通文本 | 默认 | text_compress |
| 差异内容 | `+`/`-`/`@@` diff 标记 | diff_compress |

---

## 7. L4: 意识层 Consciousness

**模块文件**: `consciousness.py` (924 行)
**CLI**: `mark42 consciousness check / eval / handle / advisor / revalidate`

> ⚠️ **状态: 设计先行** - 代码完整但未经长期生产验证。

### 职责

当 L1-L3 产生异常事件时，意识层做三件事：

1. **自检 (C1)** - `self_check()` 扫描所有子系统状态
2. **确信度评估** - `assess_certainty()` 判断问题是否真实
3. **自动修复** - `handle_issue()` 低风险问题自动修，高风险问用户

### 确信度模型

```
issue → assess_certainty()
            │
     ┌──────┼──────┐
     ▼             ▼
  is_certain    not certain
     │             │
  auto_remediate  dialog (问用户)
```

- `is_certain = True` + 低风险 → 自动修复
- `is_certain = True` + 高风险 → 主动交流（通过 advisor_client）
- `is_certain = False` → 记录到 error_archive，等待人工介入

### Advisor 主动交流

`advisor_client.py` 在确信度不足时向用户发起确认对话，避免 AI 自作主张做高风险操作。

### 强制读协议 (R9)

`verify_read_protocol()` 是一个防降解机制：定期出题测试"是否还记得关键配置文件的内容"，防止模型切换后知识丢失。

---

## 8. L5: 治理层 Governance

**模块文件**: `governance.py` (451 行) + `circuit_breaker.py` + `core_registry.py`

> ⚠️ **状态: 设计先行** - 代码完整但未经生产验证。

### 职责

面向"多模型、多核心"场景的集群治理能力。

### 子模块

#### 混沌工程 (ChaosTester)

预设故障注入场景，测试系统的检测和恢复能力。

```
chaos run --scenario disk_full    → 模拟磁盘满
chaos run --scenario broker_lock  → 模拟 broker 文件锁
chaos run --scenario oom          → 模拟内存不足
```

#### 模块健康监控 (ModuleHealthMonitor)

定期检查各模块的"黄金信号"（延迟、错误率、饱和度），输出红/黄/绿状态。

#### 集群管理 (ClusterManager)

管理多模型集群的故障替换：

```
cluster replace --name primary --source backup
  → 从备份恢复 primary 核心位
  → 写入 broker 事件留痕
```

#### 熔断器 (CircuitBreaker)

当某个核心连续失败超过阈值时自动熔断，防止故障扩散。

状态机：`closed → open (失败超限) → half_open (试探) → closed (恢复)`

#### 核心位注册表 (CoreRegistry)

注册表模式管理所有 AI 模型核心位：

```
cores list     →  列出所有核心位及状态
cores probe    →  探活
cores quarantine --core-id xxx  →  隔离
cores restore --core-id xxx     →  恢复
```

---

## 9. 基础设施层

### Broker 事件总线

所有层的通信通过 broker JSONL 文件，不直接函数调用：

```
~/.local/state/openclaw/broker/
  ├── events.jsonl           # OpenClaw 主事件流
  └── mark42-events.jsonl   # Mark42 事件流
```

事件格式：

```json
{"ts": "2026-07-21T10:30:00Z", "source": "mark42", "type": "context.warn", "data": {"usage": 72}}
```

### 配置系统

三层优先级（高 → 低）：

1. **环境变量** - `MARK42_CTX_WARN_PCT=75`
2. **config.toml** - `~/.config/mark42/config.toml`
3. **内置默认值** - `config.py` 中的常量

### 日志轮替

`logs.py` 自动轮替 OpenClaw 会话日志和 broker 事件文件，超过阈值时保留最新部分。

### Watchdog

`watchdog.py` 独立于 assemble，检查 daemon 是否存活，死亡时自动重启。

### Install / Systemd

`installer.py` 渲染 systemd service 文件，安装为系统服务：

```bash
mark42 install          # 安装 systemd 服务
mark42 install --uninstall  # 卸载
```

---

## 10. assemble: 全甲启动

`assemble` 是 Mark42 的统一入口，fork 子进程拉起所有守护组件：

```
mark42 assemble
    │
    ├── armor --guard --interval 300    (子进程 1)
    ├── engine --daemon --interval 30   (子进程 2)
    └── 监控循环 (父进程)
         ├── 30s 检查子进程存活
         ├── 检查 engine 心跳超时
         └── 子进程死亡 → 退出 + 通知
```

生命周期管理：

| 命令 | 行为 |
|------|------|
| `mark42 assemble` | 启动所有守护组件 |
| `mark42 assemble --status` | 查看 PID 和存活状态 |
| `mark42 assemble --stop` | 优雅停止（SIGTERM → SIGKILL） |
| `mark42 assemble --restart` | 停止 + 重新启动 |

PID 文件：`~/.local/state/openclaw/mark42/armor/assemble.pids`

---

## 11. 数据流总结

```
用户对话
    │
    ▼
OpenClaw 会话 (session JSONL)
    │
    ▼
L1 Armor ──── 检测 usage ≥ 85% ───→ 触发压缩
    │                                    │
    │                         algo_scheduler 选择策略
    │                                    │
    │                         PII → log_dedup → compress
    │                                    │
    │                              写 mark42-events.jsonl
    │
    ├── L2 Engine ──── 30s 轮询 ───→ 执行 Loop (context-guard 等)
    │                                    │
    │                              写 broker 事件
    │
    ├── L3 Heavy ───── 用户触发 ───→ 分批执行大工程
    │                                    │
    │                         scratch/{task}/status.json
    │
    ├── L4 Consciousness ──── 消费异常事件 ───→ 自检/评估/修复
    │
    └── L5 Governance ──── 定期健康检查 ───→ 混沌测试/熔断/替换
```

---

## 12. 目录结构

```
mark42/
├── __init__.py          # 版本号
├── __main__.py          # python -m mark42 入口
├── cli/                 # CLI 包（v2.6.0 拆分）
│   ├── __init__.py      # 包入口 + re-export
│   ├── assemble.py      # assemble 进程管理 (394行)
│   ├── status.py        # 状态面板 (236行)
│   └── parser.py        # argparse + 命令分发 (798行)
├── config.py            # 路径、阈值、环境变量
├── armor.py             # L1: 上下文铠甲
├── engine.py            # L2: 循环引擎
├── heavy.py             # L3: 重型战甲
├── consciousness.py     # L4: 意识层
├── governance.py        # L5: 混沌/模块健康/集群
├── circuit_breaker.py   # L5: 熔断器
├── core_registry.py     # L5: 核心位注册表
├── algo_scheduler.py    # 压缩器调度器（注册表模式）
├── compress_queue.py    # 压缩队列
├── smart_crusher.py     # JSON 结构压缩
├── code_compressor.py   # 代码压缩
├── diff_compressor.py   # 差异压缩
├── text_compressor.py   # 通用文本压缩
├── llm_text_compressor.py # LLM 辅助压缩
├── pii_redactor.py      # PII 脱敏
├── log_deduplicator.py  # 日志去重
├── compaction_diag.py   # 压缩配置诊断
├── context_safety.py    # Context 安全基线
├── error_archive.py     # 错误档案
├── advisor_client.py    # Advisor 主动交流
├── logs.py              # 日志轮替
├── watchdog.py          # 进程看门狗
├── installer.py         # systemd 安装
├── output_guard.py      # 输出截断保护
├── log_setup.py         # 日志初始化
├── log_classifier.py    # 日志分类
├── anomaly_detector.py  # 异常检测
├── code_analyzer.py     # 代码分析
├── llm_provider.py      # LLM 调用封装
├── perf_bench.py        # 性能基准
├── user_config.py       # 用户配置
└── utils.py             # 通用工具
```

---

## 13. 扩展指南

### 添加自定义压缩器

```python
from mark42.algo_scheduler import register_compressor

def my_compressor(data: str) -> tuple[str, dict]:
    """返回 (压缩后数据, 统计信息dict)"""
    compressed = do_something(data)
    stats = {"original_bytes": len(data), "compressed_bytes": len(compressed)}
    return compressed, stats

register_compressor("my_algo", my_compressor)
```

注册后，`algo_scheduler` 会根据 `SchedulerConfig` 的内容分类规则自动选择调用。

### 添加自定义 Loop 模板

在 `engine.py` 的 `engine_templates()` 中添加模板定义，然后在 `engine_run_loop()` 中添加对应的 Observe → Decide → Act 逻辑。

### 添加混沌测试场景

在 `governance.py` 的 `ChaosTester.__init__()` 中添加场景定义，实现注入和验证逻辑。

---

## 14. 当前状态与路线图

### 生产就绪 ✅

- L1 Armor: 上下文监测与压缩
- L2 Engine: 循环调度
- L3 Heavy: 大工程分批执行
- 基础设施: config / logs / broker / watchdog / installer

### 设计先行 ⚠️ 待验证

- L4 Consciousness: 自检/评估/修复流程
- L5 Governance: 混沌工程/模块健康/集群管理
- Advisor 主动交流协议
- 熔断器状态机

### 待办

- [ ] coverage 报告（精确行覆盖率）
- [ ] mypy 实际运行通过
- [ ] L4/L5 模块在真实环境长期验证
- [ ] armor_compress 测试 mock 链路补全

---

*本文档随 Mark42 版本更新。最后更新: v2.6.0 (2026-07-21)*
