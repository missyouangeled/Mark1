# Mark42 模块化智能铠甲系统 — 初步设计

> 设计日期：2026-06-15（原始设计） / 2026-06-29（资产对齐更新）
> 代号：Mark42
> 原则：每一块拆开能独立战斗，拼在一起是完整战甲 —— 就像钢铁侠 Mark42

---

## 〇、当前实际资产（2026-06-29）

> 本文档为 2026-06-15 原始设计，架构哲学仍适用。
> 代码状态以 `scripts/mark42_modules/` 为准。**设计 = 代码 +1**。

### 代码体量

- **22 个模块** / **9526 行** Python
- **1 个 CLI 入口** `scripts/mark42.py`
- **111 个测试** / **37.8% 覆盖**（待 Phase 2 提升至 50%+）
- 四个守护服务（armor-guard / engine-daemon / memory-index / task-watch）

### 模块清单（按职责分组）

| 分类 | 模块 | 说明 |
|:---|:---|:---|
| **核心三模块** | `armor.py` | 上下文铠甲（LLM 智能分析 + 启发式压压） |
|  | `engine.py` | 循环引擎（Loop 编排 + daemon 守护） |
|  | `heavy.py` | 重型战甲（大任务拆 + 后台跑 + 隔离执行） |
| **压缩子系统** | `algo_scheduler.py` | 算法调度器（决定 LLM/规则） |
|  | `smart_crusher.py` | 智能压缩调度 |
|  | `text_compressor.py` | 文本压缩（同义词 + 填充词） |
|  | `code_compressor.py` | 代码压缩（去注 + AST） |
|  | `diff_compressor.py` | git diff 压缩 |
|  | `llm_text_compressor.py` | LLM 语义压缩（同步 + 异步） |
|  | `compression_algorithms.py` | RAGRanker |
|  | `compress_queue.py` | 压缩线程队列 |
|  | `compaction_diag.py` | 压缩诊断 + 修复 |
|  | `pii_redactor.py` | PII 脱敏 |
|  | `log_deduplicator.py` | 日志去重 |
| **支撑模块** | `cli.py` | argparse + status dashboard |
|  | `config.py` | XDG 路径 + 配置初始化 |
|  | `utils.py` | JSON 加载、文件锁 |
|  | `logs.py` | 日志轮转 |
| **性能 / 调试** | `perf_bench.py` | 性能基准 |
| **原型期脚本** | `test_day4_integration.py` | Day 4 集成脚本（保留供调试） |

> **怎么说**：Mark42 从 2026-06-15 原始设计到现在，**多了 16 个模块**。
> 设计哲学（三层架构 / 独立可用 / 事件总线）未变。

---

## 零、战甲哲学（Mark42 之魂）

### 设计初衷

一开始改造 Mark1 时就想做成战甲那样：

> **通用接口，每一块可以拆下来单独可用，拼在一起也可以用。**
> 设备再简陋，可以删掉很多模块，只留下对话模块，也一样使用。
> 设备很好，可以在 Mark1 的基础上添加很多新装备。

这就是 Mark42 的灵魂，四条铁律：

1. **通用接口**：所有模块走同一套事件总线（Broker），同一个 CLI 入口（`mark42.py`），同一个状态目录（`~/.local/state/openclaw/mark42/`）
2. **独立可用**：每个模块有自己的子命令、自己的状态文件、自己的守护模式。不依赖任何其他模块就能跑
3. **弹性伸缩**：设备穷只跑 `chat`，设备好挂满所有装备。接口不变，挂载配置驱动
4. **代码通用性**：Mark42 项目代码不得混入特定机器/特定人的定制配置。定制通过外部脚本/配置文件（如 bootstrap.sh、systemd unit）调用 Mark42 CLI 实现，Mark42 本体保持纯净可分发

### 层级模型

```
┌─────────────────────────────────────────────┐
│  L3 重装模式 ─ 云端 / 好设备                  │
│  对话 + 铠甲 + 引擎 + 战甲 + 视觉 + 语音 + ... │
├─────────────────────────────────────────────┤
│  L2 标准模式 ─ Mark1 当前                     │
│  对话 + 铠甲 + 引擎 + 战甲                     │
├─────────────────────────────────────────────┤
│  L1 极简模式 ─ 树莓派 / 旧手机                 │
│  只要对话，别的都能关                           │
└─────────────────────────────────────────────┘
```

每往上一层，挂的装备可以更多——但接口不变，下层代码不需要改一行。

---

## 一、概念总览

### 1.1 核心理念

当前 OpenClaw 里已经有三个看起来很分散的能力：

| 现有资产 | 做了什么 | 核心模式 |
|---------|---------|---------|
| Context Monitor + Session Watcher | 检测上下文是否快炸了 | **感知** |
| Supervisor + Task Scheduler + Guardian | 自动盯任务、补位、回报 | **决策** |
| Heavy Task Start/Finish + Preflight + Scratch | 大工程安全开工、隔离执行、收尾 | **执行** |

这三块本质上是同一个闭环（Loop）在不同层次上的体现：

```
感知 → 决策 → 执行 → 验证 → 回到感知
```

Mark42 就是把这三块做成**可独立运行、可插拔组合**的标准化模块。每个模块有自己的 CLI、状态文件、事件输出。任意两个可以对接，三个全接就是完整闭环。

### 1.2 三模块定义

```
┌─────────────────────────────────────────────────────────┐
│                    Mark42 系统架构                        │
│                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   │
│  │  🛡️ 模块A   │   │  🔄 模块B   │   │  ⚙️ 模块C   │   │
│  │  上下文铠甲  │   │  循环引擎    │   │  重型战甲    │   │
│  │  Context    │◄──│  Loop       │──►│  Heavy Task │   │
│  │  Armor      │   │  Engine     │   │  Suit       │   │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   │
│         │                 │                 │           │
│         ▼                 ▼                 ▼           │
│  ┌─────────────────────────────────────────────────┐   │
│  │              共享事件总线（Broker）               │   │
│  │         ~/.local/state/openclaw/broker/          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │             Mark42 统一入口 / CLI                  │   │
│  │     scripts/mark42.py <module> <action> [opts]   │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 二、模块A：上下文铠甲 (Context Armor)

### 2.1 定位

**「别让上下文在你眼皮底下悄悄炸掉」**

现有 context-monitor 只会报警，不会出手。上下文铠甲补上"智能出手"这一环。

### 2.2 独立运行模式

```bash
# 查看当前上下文健康度
python3 scripts/mark42.py armor --check

# 触发智能压缩（生成记忆索引 → 注入 → 触发 /compact）
python3 scripts/mark42.py armor --compress

# 持续守护模式（每 5 分钟自检，超阈值自动出手）
python3 scripts/mark42.py armor --guard
```

### 2.3 核心能力

```
┌────────────────────────────────────────────┐
│           上下文铠甲 — 内部流程              │
│                                            │
│  ① 检测（复用 context-monitor）             │
│     每 5min 或事件触发                      │
│     ├── <70% → 静默记录                    │
│     ├── 70-85% → 🟡 准备出手               │
│     ├── 85-95% → 🟠 自动压缩               │
│     └── >95% → 🔴 紧急分区                 │
│                                            │
│  ② 诊断（复用 context-degradation.md）      │
│     判定当前是哪种退化：                     │
│     ├── Lost-in-Middle → 关键信息移到首尾   │
│     ├── Poisoning → 截断污染点              │
│     ├── Distraction → 标记无关区            │
│     ├── Confusion → 任务上下文隔离           │
│     └── Clash → 版本/数据冲突标注           │
│                                            │
│  ③ 出手                                     │
│     根据诊断结果选择策略：                    │
│     ├── 智能压缩：生成「记忆索引」注入系统提示 │
│     ├── 污染截断：标记截断点，新建干净上下文   │
│     ├── 分区卸载：把老内容导出到外部 scratch   │
│     └── 紧急重置：保底方案                    │
│                                            │
│  ④ 记录                                     │
│     每次出手写入 armor-actions.jsonl，       │
│     记录：触发原因 / 策略 / 丢掉了什么        │
└────────────────────────────────────────────┘
```

### 2.4 「记忆索引」机制（核心创新）

当触发压缩时，不直接 `/compact`，而是先跑一轮信息提取：

```
当前上下文 → Armor 分析 → 产出 memory-index.json:

{
  "session_id": "xxx",
  "compacted_at": "2026-06-15T17:45:00+08",
  "preserved": {
    "user_preferences": [
      "用户要求回复只用中文",
      "默认图生模型: litellm/agnes-image-2.1-flash",
      "DeepSeek fallback 已配置"
    ],
    "active_decisions": [
      "正在设计 Mark42 系统",
      "模块A/B/C 架构已确认"
    ],
    "task_state": {
      "current": "编写 Mark42 初步设计文档",
      "progress": "模块A 已完成，正在写模块B"
    }
  },
  "discarded": {
    "idle_chat": "关于天气的闲聊（2轮）",
    "dead_ends": "尝试用 web_fetch 抓取 cursorai.art 文档，返回为空",
    "completed_subtasks": [
      "搜索 'AI agent most requested features' — 已完成，结论已纳入设计"
    ]
  },
  "degradation_detected": "lost-in-middle",
  "strategy_used": "smart-compress"
}
```

这份索引在下轮开始时注入系统提示词，让后续对话带着"记忆摘要"继续，而不是从零开始。

### 2.5 状态文件

```
~/.local/state/openclaw/mark42/armor/
├── status.json          # 当前健康状态
├── memory-index.json    # 最新一次压缩的记忆索引
├── actions.jsonl        # 出手记录（带时间戳）
└── history/             # 历史 memory-index 存档（可回滚）
```

---

## 三、模块B：循环引擎 (Loop Engine)

### 3.1 定位

**「别再让我盯着屏幕等结果」**

现有的 Supervisor + Task Scheduler + Guardian 已经有 Loop 雏形了，但各自为战。循环引擎把它们统一成标准化的 Loop 控制面。

### 3.2 Loop 是什么

```
         ┌──────────────────────┐
         │    Loop Engine        │
         │                      │
    ┌────┴────┐                 │
    │ Observe │◄────────────────┤
    └────┬────┘                 │
         │                      │
    ┌────┴────┐                 │
    │ Decide  │                 │
    └────┬────┘                 │
         │                      │
    ┌────┴────┐                 │
    │  Act    │                 │
    └────┬────┘                 │
         │                      │
    ┌────┴────┐                 │
    │ Verify  │─────────────────┘
    └─────────┘    （回到 Observe）
```

每个 Loop 周期 = Observe → Decide → Act → Verify。可以嵌套（大 Loop 套小 Loop），可以并行（多个独立 Loop 同时跑）。

### 3.3 独立运行模式

```bash
# 查看当前所有活跃 Loop
python3 scripts/mark42.py engine --list

# 启动一个 Loop
python3 scripts/mark42.py engine --start \
  --task "监控 context-monitor 状态，超过70%触发 armor --compress" \
  --every 300s \
  --max-cycles 100

# 启动带验证的 Loop
python3 scripts/mark42.py engine --start \
  --task "下载抖音视频" \
  --observe "python3 scripts/download-platform-video.py --list-only ..." \
  --decide "根据候选列表选第一个有效URL" \
  --act "python3 scripts/download-platform-video.py --pick first ..." \
  --verify "ffprobe 校验 + 文件大小检查" \
  --on-fail "retry" \
  --max-retries 3
```

### 3.4 Loop 模板库

预定义常见 Loop 模式，开箱即用：

```yaml
# 模板: context-guard
# 描述: 持续监控上下文健康 + 自动出手
context-guard:
  observe: mark42.py armor --check
  decide:
    - if usage > 85% → trigger compress
    - if degradation detected → trigger diagnose + fix
  act: mark42.py armor --compress
  verify: mark42.py armor --check（确认使用率下降）
  schedule: every 5min

# 模板: heavy-task-watch
# 描述: 大工程执行 + 全程护航
heavy-task-watch:
  observe: heavy-task status
  decide:
    - if task stalled → alert
    - if task done → trigger verify
  act: notify frontstage
  verify: 输出文件存在 + 非空

# 模板: model-fallback
# 描述: 模型调用失败自动切换
model-fallback:
  observe: 检测 API 错误
  decide: if 401/429/5xx → fallback to next model
  act: 切换模型 + 重试请求
  verify: 新模型正常返回
```

### 3.5 与现有组件的对应关系

| 现有组件 | Mark42 中的角色 |
|---------|----------------|
| `supervisor-status.py` | Loop 状态管理 |
| `task-scheduler.py` | Loop 调度器 |
| `frontstage-guardian.py` | Observe 层（部分） |
| `health-collector.py` | Observe 层（系统级） |
| `supervisor-subagent.py` | Act 层（spawn/kill/notify） |

**迁移策略**：不改现有组件，Loop Engine 作为上层编排器调用它们。现有 timer 继续跑，Loop Engine 通过 broker 事件和它们联动。

---

## 四、模块C：重型战甲 (Heavy Task Suit)

### 4.1 定位

**「大工程不卡主线程、不炸上下文、不掉结果」**

现有的 heavy-task-start/finish/preflight 已经是成熟方案了。重型战甲把它们标准化，并加入与上下文铠甲 + 循环引擎的对接。

### 4.2 独立运行模式

```bash
# 开工前预检
python3 scripts/mark42.py heavy --preflight /path/to/project

# 开工（自动建 scratch + 冲突扫描 + 预检）
python3 scripts/mark42.py heavy --start /path/to/project \
  --task-name "batch-rename-assets"

# 收工（校验 + 清理 scratch）
python3 scripts/mark42.py heavy --finish --task-name "batch-rename-assets"

# 带上下文感知的开工（新能力）
python3 scripts/mark42.py heavy --start /path/to/project \
  --task-name "mass-refactor" \
  --context-aware    # 开工前先检查当前会话上下文余量
```

### 4.3 上下文感知的新增能力

重型战甲本身不动上下文，但它**知道自己执行前上下文还剩多少空间**。与铠甲对接后：

```
⚙️ Heavy Task Suit 接到任务
    │
    ├── ① Preflight：文件量 / 内存 / 磁盘 / failed units
    │
    ├── ② 查铠甲：当前上下文使用率？
    │       ├── <50% → 直接在前台启动
    │       ├── 50-70% → 卸后台执行（spawn sub-agent）
    │       └── >70% → 先触发铠甲压缩，再卸后台
    │
    ├── ③ 执行：后台分身 + scratch 隔离
    │       ├── 每个子任务 output → scratch/<task-name>/outputs/
    │       ├── 错误日志 → scratch/<task-name>/errors/
    │       └── 状态文件 → scratch/<task-name>/status.json
    │
    ├── ④ 监控：透过 Loop Engine 的 task-watch 模板
    │       ├── 卡住超时 → 通知前台
    │       ├── 正常完成 → 自动校验
    │       └── 异常退出 → 保留现场 + 通知前台
    │
    └── ⑤ 收尾：校验 → 清理 scratch（保留 .keep 标记的重要输出）
```

### 4.4 子任务上下文隔离

大工程最怕的是子任务把上下文污染了。重型战甲的核心创新是**每个子任务在独立上下文中运行**：

```
主会话（你的聊天）
    │ 上下文: 轻量，只保留"任务目标 + 进度摘要"
    │
    ├── 子任务1 → 后台分身1（隔离上下文，只管文件1-100）
    ├── 子任务2 → 后台分身2（隔离上下文，只管文件101-200）
    ├── ...
    └── 子任务N → 后台分身N
            │
            ▼
    每个分身完成后只回报结果摘要（<500 tokens），
    不把执行过程带回主会话
```

---

## 五、组合模式（Mark42 完整战甲）

### 5.1 三层联动

当三个模块全部激活，形成完整闭环：

```
┌──────────────────────────────────────────────────────────┐
│              Mark42 Full Assembly 联动图                   │
│                                                          │
│   🛡️ Context Armor                  🔄 Loop Engine       │
│   ┌─────────────────┐              ┌─────────────────┐   │
│   │ 检测: 上下文 72%  │──broker──►│ 收到 armor:warn │   │
│   │ 诊断: distraction│              │ 决策: 触发压缩   │   │
│   │ 出手: 智能压缩   │◄─broker────│ 指令 armor --compress│
│   │ 产出: memory-idx │              │                  │   │
│   └────────┬────────┘              └────────┬─────────┘   │
│            │                                │             │
│            │  压缩后上下文降至 45%            │             │
│            │                                │             │
│            ▼                                ▼             │
│   ⚙️ Heavy Task Suit                                    │
│   ┌─────────────────────────────────────────────────┐    │
│   │ 用户：「把这些文件全改名」                        │    │
│   │                                                  │    │
│   │ ① 查铠甲：上下文 45%，空间充足 → 可前台启动      │    │
│   │ ② 预检：114 文件，3.2GB，内存 OK               │    │
│   │ ③ 但文件太多，决定卸后台（避免后续撑爆）         │    │
│   │ ④ 子任务分批 → 5 个后台分身                      │    │
│   │ ⑤ 通过 Loop Engine 的 task-watch 监控            │    │
│   │ ⑥ 每完成一批 → Loop Engine 通知前台              │    │
│   │ ⑦ 全部完成 → 校验 → 收尾                         │    │
│   └─────────────────────────────────────────────────┘    │
│                                                          │
│   整个过程中，Loop Engine 持续运行：                       │
│   - 每 30s：检查子任务是否卡住                            │
│   - 每 5min：检查上下文是否又涨上去了                      │
│   - 有异常：自动决策 + 通知前台                            │
└──────────────────────────────────────────────────────────┘
```

### 5.2 统一入口

```bash
# 一键启动完整战甲（开发中）
python3 scripts/mark42.py assemble

# 等同于同时启动：
#   mark42.py armor --guard &
#   mark42.py engine --daemon &
# （Heavy Task Suit 按需激活）
```

### 5.3 组合模式的规则

| 场景 | Armor | Engine | Heavy | 行为 |
|------|:-----:|:-----:|:-----:|------|
| 日常聊天 | 🟢 守护 | 🟡 待命 | ⚪ 休眠 | 只监控上下文，不出手 |
| 上下文接近 70% | 🟠 出手 | 🟢 协调 | ⚪ 休眠 | 铠甲压缩，引擎通知 |
| 用户发起大工程 | 🟢 守护 | 🟢 监控 | 🟢 执行 | 铠甲评估空间，重型开工 |
| 大工程 + 上下文告警 | 🟠 出手 | 🟢 协调 | 🟢 执行 | 先压缩 → 再分批 → 引擎护航 |
| 模型调用失败 | ⚪ | 🟢 Fallback | ⚪ | 引擎自动切换模型 |

---

## 六、数据流与事件总线

### 6.1 事件标准格式

三个模块通过统一的 Broker 事件通信：

```json
{
  "ts": "2026-06-15T17:45:00+08",
  "source": "mark42.armor",
  "event": "context.warn",
  "level": "warn",
  "data": {
    "usagePercent": 73.5,
    "degradation": null,
    "sessionKey": "agent:main:dashboard:xxx"
  },
  "suggestedAction": "compress"
}
```

### 6.2 事件类型表

> 【2026-06-30 O 修】event 命名空间两种风格都接受:
> - **内部事件**：`{view}.{module}.{action}` 简洁形式 (例: `armor.compress`、`engine.health.warn`、`heavy.task.done`)
> - **跨模块桥接事件**：`mark42.{module}.{action}.{detail}` 加前缀 (例: `mark42.engine.bridge.heavy_started` 表明是 engine 主动桥接 heavy 事件)
> 这样设计: 内部调试只看本地, 跨模块提醒看带 mark42. 前缀
> 本表以内部事件为准 (例: `heavy.task.done` 不是 `heavy.task.finished`)

| source | event | 含义 | 谁响应 |
|--------|-------|------|--------|
| `armor` | `context.ok` | 上下文正常 | — |
| `armor` | `context.warn` | 接近阈值 | Engine 决策 |
| `armor` | `context.critical` | 紧急 | Engine 强制出手 |
| `armor` | `degradation.*` | 检测到退化 | Engine + Armor 联调 |
| `armor` | `compress.done` | 压缩完成 | Heavy 可以安全启动 |
| `engine` | `loop.*.started` | Loop 启动 | — |
| `engine` | `loop.*.action` | Loop 执行动作 | Heavy 按需响应 |
| `engine` | `loop.*.completed` | Loop 完成 | 通知前台 |
| `heavy` | `task.preflight` | 预检结果 | Engine 评估上下文空间 |
| `heavy` | `task.progress` | 任务进度 | Engine 推前台 |
| `heavy` | `task.done` | 任务完成 | Engine 触发校验 |

### 6.3 状态依赖图

```
Heavy Task 启动前：
  ① 检查 Armor 状态（上下文够不够）
  ② 检查 Engine 状态（有没有空闲 Loop 槽位）
  ③ 两个都 OK → 启动

Armor 准备压缩前：
  ① 检查 Engine 是否有活跃的 Heavy Task 在跑
  ② 如果有 → 通知 Heavy 暂停子任务派发
  ③ 压缩完成 → 通知 Heavy 恢复
```

---

## 七、实现路线图

### 阶段 1：原型（1-2 周）

**目标**：三个模块能独立跑起来

- [ ] `scripts/mark42.py` — 统一 CLI 入口骨架
- [ ] **Armor**：把 `context-monitor.py` 包装成 Armor 子命令
  - [ ] `--check` 复用现有逻辑
  - [ ] `--compress` 新增：调 LLM 生成 memory-index.json
  - [ ] `--guard` 新增：守护模式循环
- [ ] **Engine**：Loop 核心引擎
  - [ ] Loop 定义（observe/decide/act/verify）
  - [ ] `--start` 启动 Loop
  - [ ] `--list` 查看活跃 Loop
  - [ ] `--kill` 终止 Loop
  - [ ] 模板系统（context-guard / task-watch / model-fallback）
- [ ] **Heavy**：包装现有 heavy-task 脚本
  - [ ] `--preflight` / `--start` / `--finish`
  - [ ] `--context-aware` 模式（启动前查 Armor）

### 阶段 2：联动（2-3 周）

**目标**：两个模块能协同工作

- [ ] Armor ↔ Engine：上下文告警 → Engine 自动决策 → 触发压缩
- [ ] Heavy ↔ Armor：大工程启动前自动检查上下文空间
- [ ] Engine ↔ Heavy：task-watch 模板监控子任务
- [ ] Frontstage 集成：Engine 状态变化推送到 Control UI

### 阶段 3：完整战甲（3-4 周）

**目标**：三个模块全联动 + 一键 assemble

- [ ] `mark42.py assemble` — 一键启动完整守护
- [ ] 智能压缩提示器（memory-index 自动生成）
- [ ] Control UI 看板：装甲状态总览
- [ ] Loop 模板热加载（不用重启就能加新模板）

### 阶段 4：打磨（持续）

- [ ] Loop 成功率统计 + 自优化
- [ ] 压缩质量评估（压缩前后关键信息保留率）
- [ ] 性能调优（减少误报、降低轮询开销）

---

## 八、一句话总结

| 模块 | 一句话 | 解决什么问题 |
|------|--------|-------------|
| 🛡️ Armor | 上下文快炸了？我先压一下，压之前告诉你要留什么 | 智能上下文管理 |
| 🔄 Engine | 重复的事别让我盯着，我给你画个圈让它自己转 | Loop 自动化 |
| ⚙️ Heavy | 大活拆碎、后台跑、不卡主线程 | 大工程隔离执行 |

**拆开**：每个都是独立命令行工具  
**拼上**：通过 Broker 事件总线和 Engine 的 Loop 编排，形成完整闭环

---

## 附录：当前资产复用表

| Mark42 能力 | 复用什么 | 新增什么 |
|------------|---------|---------|
| Armor `--check` | `context-monitor.py` | 包装为 mark42 子命令 |
| Armor `--compress` | `context-optimization.md` 策略 | memory-index 自动生成 |
| Armor `--guard` | `context-monitor.py` timer | 守护循环逻辑 |
| Engine `--start` | `supervisor-subagent.py` | Loop 编排引擎 |
| Engine 模板 | `supervisor-status.py` / `task-scheduler.py` | 模板化配置 |
| Engine `--list` | `task-scheduler.py` | 统一 Loop 状态视图 |
| Heavy `--start` | `heavy-task-start.py` | `--context-aware` 模式 |
| Heavy `--finish` | `heavy-task-finish.py` | 上下文后验证 |
| 事件总线 | `frontstage-broker.py` | mark42 事件标准化 |
| Frontstage 通知 | `supervisor-subagent.py send-frontstage` | Armor 事件推送 |

---

## 附录：开发规范

### 更新日志

每次代码/功能变动后，**必须**在 `docs/design/mark42-更新日志.md` 顶部追加一条记录。

**格式（按日期倒序）**：

```
## YYYY-MM-DD — vX.Y 简短标题

**背景**：为什么改（一句话）

**新增/改进**：
- 具体改动 1
- 具体改动 2

**修复的 bug**：
- bug 描述 → 修复方式

**验证**：
- 烟测/手动测试结果
- 关键指标（如 Loop 数、LLM 状态）

**修改文件**：
- path/to/file.py — 改动说明
```

**规则**：
- 每次修改都要追记，不可跳过
- 日期放最前，倒序排列（最新的在最上面）
- 不要合并多天的改动到一条
- 版本号按 `major.minor` 递增（阶段1=2.x，阶段2=3.x，阶段3=4.x，阶段4=5.x）

### 版本号规则

| 阶段 | 大版本号 | 含义 |
|:---|:---|------|
| 原型 | 1.x | 点点自用 |
| 内测可用 | 2.x | 阶段1，自己稳定跑 |
| 可安装分发 | 3.x | 阶段2，别人也能装 |
| 产品化打磨 | 4.x | 阶段3，有 UI/文档/测试 |
| 商业化发布 | 5.x | 阶段4，开卖 |

### 代码审查流程

1. **编译检查**：逐个模块 import，确认无语法错误
2. **第一轮烟测**：所有 CLI 命令 + 手动运行 Loop + daemon 启动
3. **审查问题**：分析烟测失败项，定位根因
4. **修复**：最小改动原则
5. **第二轮烟测**：确认修复有效 + 无新增回归
6. **交付**：更新日志 + 更新路线图诊断标记

### 模块修改原则

- 改动 `armor.py` / `engine.py` / `cli.py` → 必须同步更新 `商品化路线图.md` 诊断标记
- 改动 `loops.json` 结构 → 必须确保 `engine.py` 中 `_load_loops()` 兼容新旧格式
- 新增事件类型 → 遵循命名空间（见 6.2）
- 任何涉及 API key / 外部请求的改动 → 必须有 try/except 静默失败回退
