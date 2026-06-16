# Mark42 上下文压缩效果分析与优化方案

> 分析日期：2026-06-16
> 触发原因：用户反馈压缩前后对话回复有等待延迟，希望减少压缩次数

---

## 一、现状统计

### 1.1 当前会话环境

| 指标 | 数值 |
|------|------|
| 模型 | deepseek-company/deepseek-v4-pro |
| 上下文窗口 | 131,072 tokens（约 128K） |
| 当前活跃 JSONL | 1,023 KB（约 71,000 tokens） |
| 今天产生的 session 文件 | 23 个（总计约 18 MB） |
| 最新 session 宽度 | ~900KB-1MB 时触发压缩后换新 session |

### 1.2 当前 OpenClaw 压缩配置

```json
{
  "compaction": {
    "mode": "safeguard",
    "truncateAfterCompaction": true,
    "keepRecentTokens": 25000,
    "notifyUser": true,
    "maxActiveTranscriptBytes": 600000
  }
}
```

| 配置项 | 当前值 | 作用 |
|--------|--------|------|
| mode | `safeguard` | 压缩前先做质量校验 |
| truncateAfterCompaction | true | 压缩后创建新 fragment session |
| keepRecentTokens | 25,000 | 保留最近 25K tokens 不压缩 |
| notifyUser | true | 压缩开始/完成时通知 |
| maxActiveTranscriptBytes | 600,000（约 586KB） | JSONL 超此值时触发压缩 |
| memoryFlush | 未启用 | **关键缺失** |

### 1.3 Mark42 Armor 阈值

| 阈值 | 百分比 | 约等于 tokens（128K 窗口） |
|------|--------|--------------------------|
| WARN | 70% | ~90K |
| ALERT | 85% | ~109K |
| CRIT | 95% | ~122K |

### 1.4 关键发现

1. **`maxActiveTranscriptBytes` 设得太低（~586KB）** — 今天短短一个半小时内产生了 23 个 session 碎片，每个都在 800KB-1MB 时就触发压缩换新
2. **`memoryFlush` 完全没启用** — 压缩前不做记忆写入，导致压缩后可能丢失重要上下文
3. **`keepRecentTokens=25000` 偏高** — 保留了约 19% 的窗口空间作为"最近不压缩"，意味着压缩更频繁
4. **Mark42 Armor 和 OpenClaw 内置压缩完全独立** — 两套系统各自为政，但只有 OpenClaw 的压缩真正导致回话中断

---

## 二、压缩导致延迟的根本原因

### 2.1 OpenClaw 压缩流程时序

```
用户发送消息
  → 上下文组装（从 JSONL 重建）
  → 检测到 contextTokens > contextWindow - reserveTokens
  → 🔒 加 session 写锁（等待最长 60s）
  → 触发 LLM 生成压缩摘要（调用模型，3-15s）
  → 写入 compaction entry → 创建 successor JSONL
  → 🔓 释放锁
  → 用压缩后上下文重新发起模型请求
  → 用户等到回复
```

**这段流程在用户发消息→等到回复之间发生，用户感知到的就是"卡住不动了"。**

### 2.2 当前延迟的主要贡献因素

| 因素 | 贡献 | 说明 |
|------|------|------|
| LLM 压缩摘要生成 | 3-15秒 | 用 DeepSeek V4 Pro 生成压缩摘要 |
| safeguard 质量校验 | +2-5秒 | mode=safeguard 有额外校验 |
| truncateAfterCompaction | +1-3秒 | 需要重建 successor JSONL |
| memoryFlush 未启用 | 无此开销 | 但如果启用也需要额外模型调用 |
| session 碎片化 | 多次触发 | 23 个 session 碎片 = 频繁重新加载 |

### 2.3 为什么今天特别频繁

`maxActiveTranscriptBytes=600000`（~586KB）针对的是**单文件 JSONL 大小**，而 `keepRecentTokens=25000` 约等于 25000 × 14bytes/token = ~350KB。所以：

- 当 JSONL 到 586KB 时触发压缩
- 压缩后最近 25K tokens（~350KB）被保留不压缩
- 实际压缩的只有 ~236KB 的内容
- 压缩完很快又到 586KB 阈值

**这是一个"压不彻底 → 很快又压"的循环。**

---

## 三、业界最佳实践（联网调研汇总）

### 3.1 Manus（头部 AI Agent 公司）
- **Dual-form tool results**：工具结果保存完整版和压缩版两份，策略性切换
- **Context offloading**：分层操作空间（函数调用 → sandbox utils → packages/APIs），文件系统状态管理替代向量索引
- **Context isolation**：最小化子代理分工（planner/knowledge/executor）

### 3.2 OpenClaw 推荐的 8 种技术
1. **Pre-Compaction Memory Flush**：压缩前静默写入 MEMORY.md（这是最关键的一项）
2. Tool Result Guard：防止孤儿 tool call 污染转录
3. 提供独立的压缩专用模型（如 ollama/qwen3:8b）
4. 事件驱动+增量压缩（而非全量重建）
5. 工作区文件作为持久化外存

### 3.3 Jetson Research（JetBrains 论文）
- 混合方法在成本降低上表现最优
- 纯 LLM 压缩精度最高但延迟最高
- 纯规则/启发式成本最低但质量不稳定
- **预压缩（提前做，不等最后时刻）是降低延迟的最有效手段**

### 3.4 关键结论
> **减少压缩频率 ≠ 减少压缩等待时间**。真正降低等待时间的策略是：**让压缩不在用户等待时发生**。

---

## 四、可落地方案（分级）

### 🟢 L1：立即可做（不改代码，只改配置）

改动 2 个配置文件，无代码变更，无风险。

**1. 提高 `maxActiveTranscriptBytes`**（减少压缩频率）

```
当前：600000 (~586KB)  →  建议：2000000 (~2MB)  或  3000000 (~3MB)
```

理由：128K 上下文窗口下，一个完整会话在压缩前大约能容纳 1.5-2.5MB JSONL。586KB 阈值太低了，相当于每次只用到一半就压。

**操作**：直接修改 `openclaw.json` → `agents.defaults.compaction.maxActiveTranscriptBytes`

**2. 提升 `keepRecentTokens`**（让每次压缩压得更彻底）

```
当前：25000  →  建议：40000 或 50000
```

理由：keepRecentTokens 越大，压缩保留的"近期尾巴"越短（不对，是越少需要压缩的内容）。但结合 truncateAfterCompaction，保留的尾巴越多 = 下一个 session 起点越大 = 越快再次触发压缩。

**更好的做法**：降低到 `keepRecentTokens: 10000`，让压缩更彻底，同时开放更大 `maxActiveTranscriptBytes`

**3. 开启 `memoryFlush`**（防止压缩丢记忆）

```json
{
  "memoryFlush": {
    "enabled": true,
    "softThresholdTokens": 32000,
    "prompt": "将关键决策、任务状态、偏好变更写入 memory/daily/YYYY-MM-DD.md。日常闲聊跳过。若无值得保留：输出 NO_FLUSH",
    "systemPrompt": "只持久化对后续会话有延续价值的信息。简洁。"
  }
}
```

### 🟡 L2：OpenClaw 配置优化（中等改动，显著效果）

**4. 指定独立压缩模型**（降低主模型负载）

```json
{
  "compaction": {
    "model": "deepseek-company/deepseek-v4-pro"
  }
}
```

如果当前就是主模型做压缩，那就不是瓶颈。如果有更便宜/更快的模型，用那个做压缩可以省钱但不降延迟。

**5. 配置 session pruning**（从源头减少 token 数）

```json
{
  "contextPruning": {
    "mode": "cache-ttl",
    "ttl": "10m",
    "keepLastAssistants": 4,
    "softTrimRatio": 0.65,
    "hardClearRatio": 0.88,
    "minPrunableToolChars": 1200
  }
}
```

pruning 在每次请求前修剪工具结果（内存操作，不写盘），比 compaction 轻量得多。可以减少触发 compaction 的需要。

### 🔵 L3：Mark42 增强（改 Mark42 代码，更主动的预压缩）

**6. Mark42 预压缩机制**

当前 Mark42 Armor 的 `armor_compress()` 做的只是"生成记忆索引"，并没有真正参与 OpenClaw 的压缩流程。可以增强为：

- 检测到上下文逼近 WARN 阈值（70%）→ 主动触发 `armor_compress()` 做预分析
- 通过 broker 事件通知 watcher 体系"即将需要压缩"
- 如果上下文余量 > 40% 时提前做一轮压缩，就不要等到用户发消息时才被动触发

**7. 上下文增长速率监测**

在 Mark42 Armor 中加一个速率指标：每分钟 token 增长量。根据速率预测"距离下次压缩还有多少时间/消息"，提前预警。

---

## 五、推荐实施顺序

| 优先级 | 方案 | 预期效果 | 实施难度 |
|--------|------|---------|---------|
| 🥇 立刻 | 调高 `maxActiveTranscriptBytes` → 2-3MB | 压缩频率降低 60-70% | 改一行配置 |
| 🥇 立刻 | 启用 `memoryFlush` | 压缩后不丢记忆 | 加 6 行配置 |
| 🥇 立刻 | 降低 `keepRecentTokens` → 10000 | 压缩更彻底，减少碎片 | 改一行配置 |
| 🥈 今天 | 启用 session pruning | 每轮 token 更少 → 压缩间隔更长 | 加 5 行配置 |
| 🥉 后续 | Mark42 预压缩 + 速率监测 | 主动预防，不等被动触发 | 改 armor.py + cli.py |

---

## 六、具体操作（供执行）

### 步骤 1：备份当前配置

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak.20260616
```

### 步骤 2：修改 compaction 配置

将 `openclaw.json` 中的 compaction 段改为：

```json
"compaction": {
  "mode": "safeguard",
  "truncateAfterCompaction": true,
  "keepRecentTokens": 15000,
  "notifyUser": true,
  "maxActiveTranscriptBytes": 2500000,
  "memoryFlush": {
    "enabled": true,
    "softThresholdTokens": 32000,
    "prompt": "NO_REPLY\n将关键决策、任务状态、偏好变更、新增规则写入 memory/daily/YYYY-MM-DD.md。日常闲聊跳过。若无值得保留：什么都不写。",
    "systemPrompt": "只持久化对后续会话有延续价值的信息。简洁，不废话。"
  }
}
```

### 步骤 3：添加 session pruning

在同级添加：

```json
"contextPruning": {
  "mode": "cache-ttl",
  "ttl": "15m",
  "keepLastAssistants": 4,
  "softTrimRatio": 0.65,
  "hardClearRatio": 0.88,
  "minPrunableToolChars": 1200
}
```

### 步骤 4：重启 Gateway 生效

```bash
openclaw gateway restart
```

---

## 七、预期效果

| 指标 | 当前 | 优化后 |
|------|------|--------|
| 压缩触发频率 | 每 3-5 分钟一次 | 每 15-25 分钟一次 |
| 每次压缩等待 | 8-20 秒 | 5-12 秒（pruning 减少 token 量） |
| session 碎片数/小时 | ~15 个 | ~3-4 个 |
| 压缩后记忆保留 | ❌ 依赖压缩摘要质量 | ✅ memoryFlush 确保写入磁盘 |

---

*本报告由 Mark42 Armor 上下文分析生成。具体执行需经用户确认。*
