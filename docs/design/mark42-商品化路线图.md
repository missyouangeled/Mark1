# Mark42 商品化路线图 — 从原型到可售卖产品

> 评估日期：2026-06-16（首次）→ 2026-06-17（校准）
> 评估基础：完整代码审查 + 实际运行测试 + 与设计文档对照
> 当前阶段：原型后期 / Alpha 早期（功能完成度 ~55% → 阶段1推进中）
>
> 代号理念重申：Mark42 战甲 — 拆开每把刀独立可用，拼起来是一套完整的甲

---

## 一、逐项诊断 & 应对方案

### 🟡 A. 铠甲智能压缩（Armor smart-compress）— LLM 链路已通，缺自动注入

**现状**（2026-06-17 校准）：`_llm_analyze()` 已实现 DeepSeek API 调用，`armor_compress()` 已走 LLM→启发式回退链路，上次压缩用 heuristic-classify。**唯一缺口：压缩后未自动注入 memory-index 到系统提示词**。

**已修复**：LLM API 调用、prompt 模板、response_format json_object、回退策略。
**仍缺失**：压缩后把 memory-index 追加为系统提示词（走 Gateway sessions API）。

**应对方案**：
1. 新增 `armor_llm_compress()` 函数：读取当前活跃会话 jsonl → 截取最近 N 轮 → 调 LLM（用 `openclaw agent` 或直接调 Gateway API）→ 产出 memory-index.json
2. Prompt 模板已写好（设计文档第 2.4 节），直接套用
3. 注入逻辑：压缩完成后把 memory-index 追加为系统提示词（走 Gateway sessions API）
4. 回退策略：LLM 不可用时回退到 heuristic
5. 工作量：2-3 天

---

### 🟠 B. Loop 引擎实际调度 — daemon 已实现但从未运行

**现状**（2026-06-17 校准）：`engine_daemon()` 已完整实现（broker 扫描 + Loop 到期执行），`engine_run_loop()` 各模板（context-guard / health-watch / model-fallback / task-watch）均有实际逻辑。但当前 20 个 Loop（8 killed + 12 registered）全部 cycle 0，daemon 从未被真正启动过。

**仍待做**：清理 12 个无意义的 registered Loop（重复注册），只留 3 个核心模板 Loop，然后通过 assemble 真启动拉起 engine_daemon。

**应对方案**：
1. 补全 `_execute_loop_cycle()`：
   - `context-guard`：调 `armor_check()` → 判断阈值 → 如需压缩则调 `armor_llm_compress()`
   - `health-watch`：调系统命令 → 判断阈值 → 写 broker 事件
   - `memory-index`：扫描 daily 文件 → 更新 INDEX.md
   - `task-watch`：读 scratch 状态 → 判断 isStale → 通知
2. 新增 `engine_daemon()` 模式：用 `select`/`signal` 驱动的持续守护进程，不依赖外部 timer
3. 让它和现有的健康采集器 timer 解耦（不要两个东西抢同一件事）
4. 工作量：3-5 天

---

### 🟠 C. 三模块联动 — 部分已通，缺标准化桥接

**现状**（2026-06-17 校准）：Heavy `heavy_start()` 在 context_aware 模式下已实际调用 `armor_compress()`（THRESHOLD_ALERT 时触发压缩）。Armor `armor_compress()` 末尾已 emit `armor.compress` broker 事件。Engine `engine_daemon()` 已扫描 broker 事件并响应 compaction.advised / context_monitor.alert。

**仍缺失**：事件类型不统一（`armor.compress` vs `mark42.armor.compress.done`），Engine 收到事件后的响应缺乏标准化（只是 print + broker emit，没做实际调度决策）。

**应对方案**：
1. 标准化事件桥接：每个模块完成关键动作后调 `_append_broker()` 写入事件
2. Armor `armor_llm_compress()` 完成后 → emit `mark42.armor.compress.done`
3. Engine `_execute_loop_cycle()` 中 scan broker events → 匹配到事件 → 触发决策
4. Heavy `_start()` 加 `--context-aware` 实际逻辑：调 `armor_check()` → 如果 >70% → 先调 Engine 触发 context-guard → 等压缩完成 → 再开工
5. 工作量：3-5 天

---

### 🟡 D. Frontstage / Control UI 集成 — 战甲状态不可见

**现状**：`status` 命令只在终端打印，Mark42 状态完全不推送到 Control UI。

**应对方案**：
1. 利用现有 `frontstage-broker.py` 的管道：Engine 状态变化 → emit broker event → frontstage-broker 重建视图 → 推送到 dashboard
2. 新增一个小的 branding 补丁：dashboard 底部加一个「🦾 Mark42 战甲状态」卡片（等侧边栏/API 稳定后再做）
3. 短期最简方案：`mark42.py status --json` 输出 JSON，Control UI 通过 infos-handle sidecar 拉取
4. 工作量：1-2 天

---

### 🟡 E. assemble 一键启动 — 假启动（待修复）

**现状**（2026-06-17 校准）：仍未修复。`mark42.py assemble` 只打印状态，不真正拉起子进程。

**应对方案**：
1. `assemble` 改为实际启动 Armor 守护 mode + Engine daemon（非阻塞，fork 子进程）
2. 加入健康检查：启动后 3 秒内检查子进程是否存活
3. 加入优雅关闭：SIGTERM / SIGINT 时关闭所有子进程
4. 工作量：1 天

---

### 🟠 H. heavy_execute 假执行 [已修复 2026-06-30]

**现状**（2026-06-30 全面审查发现）：`heavy_execute` 写好脚本 + 入队 + 状态为 running,**但从不自动调 bash 执行**。脚本里还是 `# TODO: replace with actual file operation` 占位。这与设计 4.2 “Heavy 战甲自动分批 + 后台执行” 不符。

**修复**（已 commit）：
1. `heavy_execute()` 新增 `execute_now=False` 默认参数 → 默认仅入队不启动
2. `cli.py` 加 `--execute-now` flag → 显式传才真启 bash 后台进程
3. 启动后记录 PID + logPath 到 status.json
4. 不传 `--command` → 脚本默认 no-op（仅 echo 列出文件）
5. broker 事件多一个 `heavy.batch.started` (区分 queued vs started)
6. 加 6 个新测试覆盖 dry-run / execute_now / no-op / 真启 / Popen 异常 / execute_all
7. 测试数 127 → 133，整体覆盖 39.1% → 40.1%

**为防“AI 忘状态误触”**：默认 dry-run 是护栏，不是建议 — 不传 `--execute-now` 永远不会跳到子进程

---

### 🟠 F. 上下文 97.7% — 铠甲只检测不行动

**现状**：当前正在运行的 Mark42 `status` 直接报 🔴 97.7%。但铠甲只是检测到了，完全没有触发任何压缩/处理。这正好是 Armor 核心能力缺失的直接体现。

**应对方案**：此问题随 A 项（LLM 压缩）和 B 项（Loop 调度）修复后自动解决。短期内，建议手动跑一次 `/compact`。

---

### ⬜ G. Loop 模板系统 — 有定义、无热加载（低优先级）

**现状**（2026-06-17 校准）：`engine_run_loop()` 已有 if/elif 分支路由到各模板的实际逻辑（context-guard / health-watch / model-fallback / task-watch），已不是纯打印。但模板定义仍在 `engine_templates()` 中硬编码，未移到 `config.py` 的 `LOOP_TEMPLATES` dict。

**应对方案**：
1. 把模板定义从打印文本移到 `config.py` 中的 `LOOP_TEMPLATES` dict
2. `engine_start()` 接收 `--template` 时从 dict 查找 → 注入对应 observe/decide/act/verify 逻辑
3. 支持 `--template-file` 从外部 YAML/JSON 加载自定义模板（热加载）
4. 工作量：2 天

---

## 二、离商品的差距（按优先级排列）

### 产品基础层

| # | 缺口 | 严重度 | 说明 |
|---|------|:---:|------|
| 1 | **核心功能未闭环** | 🔴 | 上面 A/B/C 三项修完才叫"能用" |
| 2 | **零测试** | 🔴 | 无单元测试、无集成测试、无回归测试。代码改动后无法验证是否破坏已有功能 |
| 3 | **无安装器** | 🟡 | 没有 pip install / deb / docker / 一键脚本 |
| 4 | **无配置向导** | 🟡 | 用户不知道怎么配 context window 大小、阈值、Loop 参数 |
| 5 | **错误处理粗糙** | 🟡 | 大部分函数只有 print + return，没有 try/except、没有 rollback、没有 graceful degradation |

### 用户体验层

| # | 缺口 | 严重度 | 说明 |
|---|------|:---:|------|
| 6 | **无图形界面** | 🟡 | CLI 只能给开发者用。需要有 Control UI 集成、TUI dashboard、或独立 Web UI |
| 7 | **无用户文档** | 🟡 | 设计文档是给开发者看的，不是给用户看的。需要 Quick Start + 概念介绍 + 场景教程 |
| 8 | **状态不透明** | 🟡 | 用户不知道铠甲在干什么。需要日志查看器、历史出手记录、压缩前后对比 |

### 商业化层

| # | 缺口 | 严重度 | 说明 |
|---|------|:---:|------|
| 9 | **无定价/商业模式** | 🟠 | 开源？闭源？SaaS？一次性买断？每设备 license？ |
| 10 | **无安全隔离** | 🟠 | Mark42 直接操作 OpenClaw 的 session 文件、broker 状态。作为商品必须有沙箱 |
| 11 | **无许可证/法律框架** | 🟠 | 需要用户协议、隐私政策、免责声明（操作可能会删文件、改配置） |
| 12 | **无 CI/CD + 发布管道** | 🟠 | 没有自动构建、版本管理、changelog、release notes |
| 13 | **无用户验证** | 🔴 | 至今只有点点一个人在 Mark1 上用过。需要至少 3-5 个早期用户真实跑过并反馈 |
| 14 | **无性能基准** | 🟠 | 不知道铠甲守护模式吃多少 CPU/内存，Loop 轮询对 Gateway 的影响有多大 |

---

## 1.5、2026-06-30 全面审查发现的 12 个问题

> 全面审查报告: `docs/design/mark42-全面审查-20260630.md` (237 行)
> 审查范围: 21 个模块 / 9802 行 Python / 127 测试 / 真生产状态

| # | 问题 | 严重度 | 状态 |
|---|------|:---:|:---:|
| H | heavy_execute 假执行 | 🔴 | ✅ **已修复** (上面 H 项) |
| I | broker 文件临界 9.99MB | 🟠 | ✅ **已修** (logs.py: `<=` 改为 `<`,留安全余量) |
| J | actions.jsonl 不记 preBytes/postBytes | 🟠 | ✅ **已修** (armor.py: action_entry 移到 compact 之后,同步 index 真值) |
| K | 文档说"4 守护"、实际 2 daemon+bootstrap+watchdog | 🟠 | ✅ **已修** (watchdog 加 4 Loop 检查 + 文档同步) |
| L | engine.py 死代码 | 🟡 | ⏳ 可选 |
| M | compress_queue 测试 3 优先级断言无效 | 🟡 | ⏳ 可选 |
| N | utils.py 死 import / 死函数 | 🟡 | ⏳ 可选 |
| O | event 命名与设计 6.1 不一致 | 🟡 | ⏳ 可选 |
| P | heavy.py batch_size 公式对单文件不友好 | 🟡 | ⏳ 可选 |
| Q | heavy.py `.keep` 命名反了 | 🟡 | ⏳ 可选 |
| R | cli.py assemble 重复 import | 🟡 | ⏳ 可选 |
| S | `_find_active_session` 排除后缀不一致 | 🟡 | ⏳ 可选 |

**修复优先级**（本次决定）：
- 🔴 1  已修 (H)
- 🟠 3  已修 (I/J/K) ← 2026-06-30 10:05
- 🟡 3  已修 (2/3/4) ← 2026-06-30 10:18 (fcntl 锁 + watchdog log + bytesStatus)
- 🟡 5  仍待修 (L/M/N/O/P/Q/R/S) - 8 个里 3 个
- L/M/N/O/P/Q/R/S 抽空修 (5 个)

---

## 1.6、2026-06-30 I/J/K 修复详情

### 🟠 I 修复: broker 阈值 `<=` 改 `<`

**问题**：`rotate_broker_events` 条件是 `if size_mb <= MAX_BROKER_EVENTS_MB: return ...`,**10MB 临界不裁**。

**修复**（`scripts/mark42_modules/logs.py`）：
- `size_mb <= MAX_BROKER_EVENTS_MB` → `size_mb < MAX_BROKER_EVENTS_MB`
- 10MB 临界状态会立即触发裁剪,留安全余量

### 🟠 J 修复: actions.jsonl 加 preBytes/postBytes/bytesSaved/effective 字段

**问题**：P0 修复把 `preCompactBytes/postCompactBytes/bytesSaved/compressionEffective` 写在 `memory-index.json` 里,**actions.jsonl 仍然只有 `preCompressUsage`**,无法审计“压缩是不是真截短了”。

**修复**（`scripts/mark42_modules/armor.py`）：
1. `action_entry` 写**移到 compact 之后** (原 写于函数入口,那时 preCompactBytes 还没填 = 一直 None)
2. 同步从 `index` 拿 `preCompactBytes/postCompactBytes/bytesSaved/compressionEffective/compactTriggered/compactMethod/compactError`
3. **顺手修 P0 隐藏 bug**:`preCompactBytes` 在 4 个分支(成功/未变小/失败/无 active session)全都补上,避免有效位不完整
4. 加 2 个新测试:`test_actions_log_includes_bytes_fields_when_compact_succeeds` + `test_actions_log_marks_effective_false_when_no_bytes_saved`

### 🟠 K 修复: 文档与实际不一致 + watchdog 加 4 Loop 检查

**问题**：文档说"4 守护服务",实际是 2 daemon (armor-guard + engine-daemon) + 1 bootstrap (oneshot) + 1 watchdog (oneshot+timer),**没有独立 memory-index / task-watch service**。

**修夏**（`tools/mark42-watchdog/mark42-watchdog.sh`）：
1. watchdog 第 2 步加 4 Loop 状态检查,调 `mark42.py status --json` 读 `engine.activeLoops/totalLoops/loops[*].status`
2. 不一致时 `notify_alert` 推 dashboard (1 小时去重)
3. 也调 alert 补 `loops-check-error` / `loops-missing` / `loops-degraded` 三种
4. 文档同步：上面 K 行的状态由"⏳ 待修"改为"✅ **已修**"
5. 加服务门槛：`mark42-watchdog` 由 2 daemon 检查升为 2 daemon + 4 Loop 检查,覆盖面更准

### 测试增量

| 阶段 | 测试数 |
|---|---|
| 修 I/J/K 前 | 133 |
| 修后 | **135** (+2 J 修复) |
| 覆盖 | 40.1% → 40.4% (估) |

### 未做(下次会话)

- 🟡 L~S (8 个小问题)
- Phase 2 推进 (压缩子模块+logs 单测,目标 50% 覆盖)

---

## 三、商品化路径（四个阶段）

### 阶段 1：内测可用（1-2 周）「先让自己真正用上」

```
目标：Mark42 在 Mark1 上实际跑起来，三个模块全部闭环

具体任务：
├── ✅ 铠甲 LLM 压缩（A 项—LLM 链路已通，走 broker 管道可用）
├── ✅ Loop 调度器实际运行（B 项—daemon 验证通过，3 个核心 Loop 循环正常）
├── ✅ 三模块事件联动（C 项—标准化协议 mark42.armor/engine/heavy.* 已闭环）
├── ✅ assemble 真启动（E 项—fork armor guard + engine daemon，优雅关闭）
├── ✅ 清理 20 个假 Loop → 3 个真模板（context-guard / health-watch / task-watch）
├── ✅ status --json（D 项—JSON 输出可用，daemon 定期写入 broker views）
├── ⏳ 至少 3 天连续守护运行不出致命错误
├── ⏳ 每次压缩记录 + 效果对比
└── ⏳ 解决 task-watch-2 自动创建问题（daemon 扫描 broker 事件残留）
```

**进度**（2026-06-17 08:15）：A/B/C/D/E 五项核心缺口已补齐。`assemble` 真正启动双守护进程。三模块事件协议标准化。`status --json` 可被外部消费。

---

### 阶段 2：早期用户验证（2-3 周）「找 3-5 个人用」

```
目标：验证「别人也能装、也能用」

具体任务：
├── 写 Quick Start 文档（一页纸，5 分钟装完）
├── 制作一键安装脚本（bash install.sh）
├── Mark42 配置向导（交互式 mark42.py --init）
├── 添加基本的 try/except + 错误提示
├── 找 3-5 个早期用户（OpenClaw 社区 / 朋友）
├── 收集反馈 → 修复 → 迭代
└── 记录每次失败和修复（留作 FAQ 素材）
```

**产出**：至少 3 个人能自己装上并理解 Mark42 是什么。

---

### 阶段 3：产品化打磨（3-4 周）「看起来像个产品」

```
目标：从"点点自用工具"变成"任何人能买的东西"

具体任务：
├── TUI dashboard（类似 htop 的战甲面板）
├── Control UI 状态卡片（通过 frontstage-broker 集成）
├── 用户文档站（docs.mark42.ai 或 GitHub Pages）
├── 自动化测试（pytest 覆盖核心模块）
├── CI/CD（GitHub Actions 自动测试 + 发版）
├── 性能调优（守护模式 CPU/内存占用报告）
├── 错误自愈（常见失败自动回滚 + 降级）
└── 安全审计（不写/不读外部文件，所有操作限定在 ~/.local/state/openclaw/mark42/）
```

**产出**：有 UI、有文档、有测试、有 CI/CD。

---

### 阶段 4：商业化发布（2-4 周）「开卖」

```
目标：有人愿意付钱

具体任务：
├── 定价方案：
│   ├── 免费版：基础监控 + 手动压缩（L1 极简模式）
│   ├── Pro 版：LLM 智能压缩 + Loop 自动化 + Control UI 集成（$9/月或 $79/年）
│   └── Team 版：多机管理 + 自定义 Loop 模板 + 优先支持（$29/月）
├── 许可协议（基于 MIT + Commons Clause，或完全闭源）
├── 支付集成（Stripe / 爱发电 / Gumroad）
├── 激活码/许可证管理
├── 发布 announcement（OpenClaw 社区 / Reddit / V2EX / 少数派）
├── Demo 视频（3 分钟展示核心价值）
└── 用户反馈 + 持续迭代
```

**产出**：一个有人愿意付钱的产品。

---

## 四、技术架构的长期方向

### 4.1 多模型支持

当前 Mark42 紧耦合 OpenClaw（依赖 Gateway RPC、session jsonl、broker 管道）。长期应抽象出一层 Provider Interface：

```
mark42_core/          # 核心逻辑（与平台无关）
├── armor.py
├── engine.py
├── heavy.py
└── providers/        # 平台适配层
    ├── openclaw.py   # 当前实现
    ├── openai.py     # 直接调 OpenAI API
    └── local.py      # 纯本地模式
```

这样 Mark42 可以独立于 OpenClaw 存在，卖给只用 ChatGPT/Claude 的用户。

### 4.2 插件体系

Loop 模板应该是可扩展的：

```bash
# 用户自己写一个 Loop 插件
mark42.py engine --install-plugin my-custom-loop.yml
```

模板市场（类似 VS Code 扩展）：社区贡献常见场景的 Loop 模板（代码审查、SEO 监控、定时备份……）。

### 4.3 多人协作

```yaml
# Mark42 多用户场景
Team Dashboard → 看到所有成员的上下文健康状态
  ├── 队长可以手动触发压缩
  ├── 查看团队整体的 Loop 执行统计
  └── 自定义团队级模板共享
```

### 4.4 数据驱动优化

```python
# 根据历史数据自动调优
class ArmorOptimizer:
    """分析过去 30 天压缩记录，自动调整阈值"""
    - 如果过去 30 天 85% 阈值下从未错过关键信息 → 提升到 90%
    - 如果某类退化（Lost-in-Middle）频繁出现 → 降低触发阈值
    - 如果 LLM 压缩质量持续 >95% → 增加压缩频率
```

---

## 五、一句话总结（投资人版）

> Mark42 是一个让 AI 助手不再「聊着聊着就忘了」的上下文管理引擎。
> 它能独立运行，也能和其他 AI 平台集成。
> 当前处于原型后期，核心架构已就绪，3 个模块中 2 个需要补齐核心逻辑（预计 2 周内闭环）。
> 目标市场：所有重度使用 AI 对话的开发者、创作者、团队。
> 商业模式：Freemium（基础功能免费，智能压缩 + 自动化 Pro 版 $9/月）。

---

## 六、当前状态（2026-06-29 审计）

> 本节为 2026-06-29 文档审计追加，反映今天（编写路径 / 测试体系 Phase 1 收尾）的现状。

**阶段 1 状态**：**未完全达成**，但已超预期推进：

- ✅ 三模块闭环（铠甲 + 引擎 + 重型）均能独立运行
- ✅ assemble 真实启动 daemon
- ✅ 5 个 Loop 模板全部上线（上下文守护 / 健康监控 / 模型 fallback / 任务 watch / 记忆索引）
- ✅ LLM 智能压缩可路径走（smart_crusher + lhm_text_compressor）
- ✅ **测试体系**：111 个测试 / 37.8% 覆盖（[Phase 2 路线](./mark42-Phase2路线-20260629.md) 提升至 50%+）
- ⚠️ 部分 Loop `cycle 0`（守护未耗时运行验证）
- ⚠️ armor.py 存在真 bug 已被修复（见 [Phase 1 收官](./mark42-测试体系-Phase1收官-20260629.md)）

**阶段 2 / 3 / 4**：未启动。

**补充详细路线**：见 [`mark42-Phase2路线-20260629.md`](./mark42-Phase2路线-20260629.md)（覆盖走向 50% 覆盖 + 集成测试 + CI）

---

*本文档将随 Mark42 开发进展持续更新。下次评估时间：阶段 1 完成后。*

---

## 1.7、2026-06-30 10:18 修 3 个 🟡 详情

### 🟡2 修复: I 修复原子性 + fcntl 锁

**问题**：`rotate_broker_events` 读 + 写 不是原子操作, armor-guard / engine-daemon 多个进程并发 append broker, 裁的瞬间可能丢中间事件。

**修夏**（`scripts/mark42_modules/logs.py`）：
- 加 `import fcntl`
- 用独立 `.lock` 文件, 避免锁住业务读路径
- `LOCK_EX | LOCK_NB`: 独占 + 非阻塞 (另一进程占锁就返 "跳过", 不死等)
- 锁范围覆盖: 读 size + 读 lines + 写 kept
- 3 个新测试: concurrent lock skip / lock released / lock path 是 .lock 后缀

### 🟡3 修复: K 修复 4 Loop 异常 watchdog.log 留痕

**问题**：4 Loop 挂掉时 `notify_alert` 推 dashboard, 但 watchdog.log 不记录 → 本地 audit gap。

**修夏**（`tools/mark42-watchdog/mark42-watchdog.sh`）：
- 4 处 `notify_alert` 前都加 `log()`:
  - `loops-check-error` → log "⚠️ 4 Loop 检查出错: $loops_check"
  - `loops-missing` → log "⚠️ 4 Loop 状态: $active/$total (expected: $total)"
  - `loops-degraded` → log "⚠️ Loop 状态不为 registered: $bad_loops"
  - 无输出 → log "⚠️ 4 Loop 检查无输出"

### 🟡4 修复: J dry_run 模式 preBytes=null 加语义标记

**问题**：dry_run 写 actions.jsonl 时 preBytes=null, reader 困惑 "是没统计?还是 dry_run 不写?"

**修夏**（`scripts/mark42_modules/armor.py`）：
- 加 `bytesStatus` 字段, 4 个值:
  - `captured`: 压缩完成, 字段有真值
  - `skipped-dry-run`: dry_run 模式, 没真压缩, 字段为 null 是预期
  - `not-attempted`: 上下文 < THRESHOLD_WARN, 未尝试 compact
  - `error`: compact 报错 (没产生 postBytes)
- 2 个新测试: bytesStatus='captured' on success / bytesStatus='skipped-dry-run' on dry_run

### 真生产端到端验证

| 修 | 验证 |
|---|---|
| 🟡2 | rotate_broker_events 正常 (9MB 不裁), 锁机制 in 测试 |
| 🟡3 | watchdog.log 新增 `⚠️ 4 Loop 状态: 3/4 (expected: 4)` |
| 🟡4 | dry_run 写 actions.jsonl 含 `bytesStatus=skipped-dry-run` |

### 累计指标

| 项 | 修 🔴 后 | 修 1.6 后 | 修 3 🟡 后 |
|---|---|---|---|
| 测试数 | 133 | 141 | **146** |
| 整体覆盖 | 40.1% | 40.8% | **41.5%** |
| 时间 | 38.5s | 39.75s | 38.7s |

### 未做 (留 Phase 2)

- 🟡 L/M/N/O/P/Q/R/S (8 个里 5 个)
- 阶段 2 推进 (压缩子模块+logs 单测,目标 50% 覆盖)
