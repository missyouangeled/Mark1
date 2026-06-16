# Mark42 商品化路线图 — 从原型到可售卖产品

> 评估日期：2026-06-16
> 评估基础：完整代码审查 + 实际运行测试 + 与设计文档对照
> 当前阶段：原型后期 / Alpha 早期（功能完成度 ~30%）
>
> 代号理念重申：Mark42 战甲 — 拆开每把刀独立可用，拼起来是一套完整的甲

---

## 一、逐项诊断 & 应对方案

### 🔴 A. 铠甲智能压缩（Armor smart-compress）— 核心能力缺失

**现状**：`--compress` 只用启发式规则（文件大小估算），不走 LLM 生成 memory-index.json。设计文档里最核心的创新——LLM 驱动的记忆摘要+自动注入——完全没有实现。

**原因**：`armor_compress()` 函数存在，但内部是 `"memory-index": {"method": "heuristic-classify"}`，没有调 LLM API。

**应对方案**：
1. 新增 `armor_llm_compress()` 函数：读取当前活跃会话 jsonl → 截取最近 N 轮 → 调 LLM（用 `openclaw agent` 或直接调 Gateway API）→ 产出 memory-index.json
2. Prompt 模板已写好（设计文档第 2.4 节），直接套用
3. 注入逻辑：压缩完成后把 memory-index 追加为系统提示词（走 Gateway sessions API）
4. 回退策略：LLM 不可用时回退到 heuristic
5. 工作量：2-3 天

---

### 🔴 B. Loop 引擎实际调度 — 8 个 Loop 全在假死

**现状**：`engine_list()` 显示 8 个 Loop（4 个 killed + 4 个 registered），但 `engine.py` 只有一个 `engine_daemon_oneshot()` 做单次检查——没有真正的 Loop 调度器在运行。

**原因**：Loop 核心执行逻辑 `_execute_loop_cycle()` 函数体是空的（只有注释）。Loop 注册到 JSON 但从不执行。

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

### 🔴 C. 三模块联动 — 设计有、代码无

**现状**：设计文档第 5.1 节画了完整联动图（Armor ↔ Engine ↔ Heavy），但实际代码中，三个模块是各调各的，没有任何事件驱动的桥接。

**具体缺口**：
- Heavy `--context-aware` 参数定义了，但只打印一条建议，不真的调 Armor 或 Engine
- Armor 压缩完成后不 emit `compress.done` 事件
- Engine 收到 `armor:warn` 事件后不做决策

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

### 🟡 E. assemble 一键启动 — 假启动

**现状**：`mark42.py assemble` 只打印「⚙️ 战甲已启动！」，不会真正拉起任何守护进程。

**应对方案**：
1. `assemble` 改为实际启动 Armor 守护 mode + Engine daemon（非阻塞，fork 子进程）
2. 加入健康检查：启动后 3 秒内检查子进程是否存活
3. 加入优雅关闭：SIGTERM / SIGINT 时关闭所有子进程
4. 工作量：1 天

---

### 🟠 F. 上下文 97.7% — 铠甲只检测不行动

**现状**：当前正在运行的 Mark42 `status` 直接报 🔴 97.7%。但铠甲只是检测到了，完全没有触发任何压缩/处理。这正好是 Armor 核心能力缺失的直接体现。

**应对方案**：此问题随 A 项（LLM 压缩）和 B 项（Loop 调度）修复后自动解决。短期内，建议手动跑一次 `/compact`。

---

### ⬜ G. Loop 模板系统 — 有定义、无热加载

**现状**：模板在 `engine_templates()` 中硬编码打印，不在 Loop 注册时实际路由到模板逻辑。

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

## 三、商品化路径（四个阶段）

### 阶段 1：内测可用（1-2 周）「先让自己真正用上」

```
目标：Mark42 在 Mark1 上实际跑起来，三个模块全部闭环

具体任务：
├── ✅ 铠甲 LLM 压缩（A 项）
├── ✅ Loop 调度器实际运行（B 项）
├── ✅ 三模块事件联动（C 项）
├── ✅ assemble 真启动（E 项）
├── ✅ 清理 8 个假 Loop，只留 3 个真模板
├── ✅ 至少 3 天连续守护运行不出致命错误
└── ✅ 每次压缩记录 + 效果对比
```

**产出**：Mark42 在你自己的 Mark1 上能稳定跑了。

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

*本文档将随 Mark42 开发进展持续更新。下次评估时间：阶段 1 完成后。*
