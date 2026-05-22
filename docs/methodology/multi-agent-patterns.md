# 多 Agent 架构模式（改编自 Agent Skills for Context Engineering）

> 来源：muratcankoylan/agent-skills-for-context-engineering
> 与现有 supervisor/subagent 体系整合，不是重建。

---

## 为什么用多 Agent

**唯一理由：上下文隔离。** 当一个 agent 的上下文窗口装不下所有任务相关信息时，把工作分到多个干净上下文中。

不是为了让 agent"扮演不同角色"——那是拟人化，浪费 token。

---

## 三种架构模式

### 模式 1：Supervisor / Orchestrator（我们在用）

```
用户 → Supervisor → [Specialist A, Specialist B, Specialist C] → 聚合 → 输出
```

**用在哪**：任务可清晰分解、需要多领域协调、需要人可介入时。

**代价**：
- Supervisor 自己的上下文会成为瓶颈
- Supervisor 挂了，所有人都挂
- **电话游戏问题**：Supervisor 转述子 agent 响应时会丢失信息

**电话游戏的修复**：
用 `forward_message` 让子 agent 直接回用户，绕过 Supervisor 的转述层。
我们已有：监工 → frontstage broker → chat.inject，本质上就是这条通路。

### 模式 2：Peer-to-Peer / Swarm

```
Agent A ↔ Agent B ↔ Agent C ↔ Agent D
```

去掉中央控制，agent 通过显式移交协议互相通信。

**用在哪**：任务需要灵活探索、不适合提前固定分解、需求动态出现时。

**我们不太适用**：我们的场景是以用户为核心的单线推进，不是 swarm 探索。

### 模式 3：Hierarchical

```
策略层 (定目标) → 规划层 (拆任务) → 执行层 (干细活)
```

**用在哪**：项目有清晰层级结构、需要不同抽象层次的规划。

**与我们**：这就是我们「方法论脑暴设计 → 任务拆解 → 分身执行」三层，已经在上层做了。

---

## 成本现实

| 架构 | Token 倍数 |
|------|-----------|
| 单 agent 聊天 | 1x |
| 单 agent + 工具 | ~4x |
| **多 agent 系统** | **~15x** |

> 这不是夸大。supervisor 提示词 + 协调消息 + 结果聚合 + 错误重试 + 共识轮次，加起来就是这个数。
> 预算时按 15x 算，低于这个就当赚了。

---

## 与我们的监工系统对照

| Superpowers 术语 | 我们的实现 |
|------------------|-----------|
| Supervisor/Orchestrator | `main-supervisor-lite`（监工分身） |
| Workers/Specialists | `sessions_spawn(mode:"run", context:"isolated")` 任务分身 |
| Forward message (绕过转述) | 监工 → frontstage broker → chat.inject |
| Context isolation | 每个分身 `context:"isolated"` |
| Filesystem coordination | workspace 共享文件系统 |

---

## 关键失败模式与对策

### 1. Supervisor 瓶颈
Supervisor 的上下文压力随 worker 数量非线性增长。5+ worker 时，supervisor 花在处理摘要上的 token 比重超过 worker 干活的。

→ **对策**：限制每个 supervisor 的 worker 数在 3-5 个。超过就加第二层 supervisor 或分批顺序执行（具体分批规则见 `superpowers-adapted.md` 的分批执行规则节）。

### 2. Sycophantic 共识
Agent 在辩论模式中倾向于达成"大家都同意"的答案，而非正确的答案。LLM 有天然的趋同偏见。

→ **对策**：审查时指定对抗角色，要求在允许收敛之前必须先提出分歧。

### 3. Agent 膨胀
超过 3-5 个 agent 后，新增的 agent 带来的收益递减，协调开销递增（每加一个 agent，通信通道呈二次方增长）。

→ **对策**：从最小可行 agent 数量开始，只在有明确的上下文隔离收益时才加。

### 4. 错误传播
一个 agent 的幻觉变成下一个 agent 的"事实"。下游 agent 无法区分上游输出是真还是幻。

→ **对策**：两级审查（规格 + 质量）就是为了防止这个。不要信任未经验证的上游输出。

### 5. 过度分解
把任务拆得太细，协调开销比任务本身还大。一个 10 步 pipeline 配 10 个 agent，花在移交上的 token 比实际干活还多。

→ **对策**：只在子任务真正受益于独立上下文时才分解。2-5 分钟的粒度是黄金标准。

### 6. 电话游戏
信息在 agent 间传递时，每转述一次就丢一层细节。

→ **对策**：需要多个 agent 访问的共享状态走文件系统，不走消息中转。

---

## 对我们最实用的三条

1. **少即是多**：不要因为"这里可以拆"就拆分身。每个分身增加成本，只在单上下文装不下时才拆
2. **按 15x 做心理预算**：多 agent 就是贵的，不要惊讶
3. **防传播**：两级审查不是在浪费时间——是在截断错误传播链

## 关联文档

- `superpowers-adapted.md`：工程方法论阶段③分身执行与监工配合
- `context-optimization.md`：上下文分区策略·拆分身判断标准
- `context-degradation.md`：multi-agent 场景下的退化诊断（错误传播、sycophantic 共识）
