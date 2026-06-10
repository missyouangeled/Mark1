# Frontstage Guardian 深度分析报告

> 分析时间：2026-06-10 17:55 CST
> 故障率：24.2%（546 次检查，132 次 ERROR，414 次 OK）
> OpenClaw 版本：2026.5.22 (a374c3a)

---

## 一、总览

Guardian 今天被触发 546 次（每 60 秒一次），其中 132 次报 ERROR。132 次错误并非随机分散——它们聚合成 **四个特征鲜明的故障簇**，每个簇对应一个不同的根因。

```
07:00  ████████████████ (16次)  网络断连
08:00  ███████ (7次)           间歇性波动
09:00  ███████████ (11次)      工作负载
10:00  ███ (3次)               正常
11:00  █████████ (9次)         工作负载
12:00  ██████████████████████████████████████████ (43次)  🔴 主要事故
14:00  ███████ (7次)           恢复波动
15:00  ███████████████ (15次)  gateway 重启
16:00  ████████████ (12次)     恢复波动
17:00  █████████ (9次)         正常波动
```

---

## 二、四个根因的完整分析

### 根因 1：12:00 会话压缩风暴（43 次连续错误）🔴🔴🔴

这是今天最严重的事故，Guardian 从 11:30 到 12:50 连续 43 次 ERROR，一次都没恢复。

#### 完整的事件链：

```
① 会话文件膨胀
   你的主 dashboard 会话自凌晨 00:46 开始一直没压缩
   → 积累了 683 条消息
   → 预估 prompt tokens: 123,660（超过 DeepSeek 131,072 窗口的 92%）

② 上下文溢出触发 Precheck
   11:51:48 gateway 检测到溢出
   → compactionAttempts=0（这是第一次触发压缩）
   → 自动启动压缩流程

③ 压缩连续失败 4 次 🔁
   第1次：prompt token count of 50063 exceeds the limit of 12288
          （你配置的 compaction 模型 gpt-4o-mini 最大上下文 12288 tokens，
           但要压缩的消息本身就有 50063 tokens，根本塞不进去）
   第2次：model gpt-4o-mini is not supported via Responses API
          （OpenAI 已经废弃了旧的 Completions API 路由，
           gpt-4o-mini 现在只走 Responses API，但 OpenClaw 还在用旧路由）
   第3次：prompt token count of 50168 exceeds the limit of 12288（同第1次）
   第4次：model gpt-4o-mini is not supported via Responses API（同第2次）

④ 压缩兜底成功但代价巨大
   → 旋转会话文件（rotated active transcript）
   → 截断 40 条 tool result
   → 最终靠暴力截断+旋转勉强通过，而非真正的语义压缩

⑤ 整个过程 gateway 被严重拖垮
   eventLoopUtilization = 1.0（100%，完全饱和）
   eventLoopDelayMax = 11,668ms（事件循环卡了 11.6 秒）
   → guardian 调用 openclaw gateway call chat.history
   → gateway 事件循环正在被压缩+模型调用占满
   → 25 秒子进程超时 → ERROR ❌
```

#### 为什么连续 43 次都失败？

因为这是一个恶性循环：
```
会话膨胀 → 压缩触发 → 压缩失败 → 旋转截断（勉强过）
→ 但新消息继续追加 → 很快又膨胀 → 又触发压缩 → 又失败...
→ 每次压缩都消耗 30-40 秒，其间 gateway 极度不响应
→ guardian 在这期间跑的任何检查都超时
```

#### 对比正常时段：

12:49 之后的所有检查全部恢复 OK（连续 OK 约 300+ 次直到下一个事故），说明一旦压缩完成、会话回到正常大小后，gateway 立即恢复响应。

---

### 根因 2：07:00 网络断连（16 次错误）🟠

日志铁证：`getaddrinfo EAI_AGAIN api.deepseek.com`

DNS 解析失败，DeepSeek API 完全不可达。这发生在早上 7 点，很可能是公司网络在这个时间段有什么维护或切换。

guadian 调用 `openclaw gateway call chat.history` 时，gateway 本身也在处理 DeepSeek 的连接失败和降级逻辑。在这个时间窗口内 gateway 处于「内部正在处理网络故障」的状态，对 guardian 的检查调用响应超时。

---

### 根因 3：15:00 gateway 重启事故（15 次错误）🟠

这是另一个事故：

```
15:07 gateway 收到 SIGTERM → 开始 graceful shutdown
15:10-15:12 尝试 drain 活跃任务
  → active embedded run 超时 (30s) → 被强制 abort
  → 2 个 active task 一直卡在会话文件锁里
  → SessionWriteLockTimeoutError: session file locked (timeout 60000ms)
  → 这是 OpenClaw 已知 bug #86014：嵌入运行的会话文件锁有时不被释放
15:12 强制重启 → 全进程重启 (supervisor restart)
15:12-15:52 gateway 完全重启完成
  → 期间 guardian 的所有检查：gateway 不在线 → gateway call 失败 → ERROR
```

这次事故和 12 点那个不同——12 点是 gateway 还在线但极度缓慢，15 点是 gateway 直接下线重启了。

---

### 根因 4：零星工作负载波动（约 58 次）🟡

分布在 08:00-11:00、14:00、16:00-17:00 各时段。没有明显的连续失败集群，每次通常只有 1-3 次 ERROR 然后自动恢复。这些是 gateway 在正常工作负载下偶尔出现的 `openclaw gateway call` 超时。

**特征**：每段 CPU 消耗约 7-10 秒，说明 guardian 的两个子检查跑完了大半但某个 API 调用慢。正常情况下 7 秒完成，异常时 25 秒超时。

---

## 三、架构层面的问题

### 问题 1：循环依赖——监护者和被监护者用同一条路

```
guardian ──(subprocess)──> openclaw gateway call ──(HTTP/WS)──> gateway
                                                                  │
                                                                  ├── 读取 sessions.json
                                                                  ├── 读取 session jsonl 文件
                                                                  └── 返回结果
```

当 gateway 的 Node.js 事件循环被压缩、模型调用、文件 I/O 阻塞时，`openclaw gateway call` 同样被阻塞。**Guardian 设计的初衷是检测 gateway 是否健康，但它自己的检测通道依赖同一个 gateway**。

这就像一个医生用自己的心跳来测量病人的心跳——两个人的问题混在一起了。

### 问题 2：gpt-4o-mini 压缩配置不可用

日志明确显示两个兼容性问题：
1. **上下文不够**：要压缩的 50k+ tokens 超过了 gpt-4o-mini 的 12k 限制
2. **API 路由过时**：`model gpt-4o-mini is not supported via Responses API`

压缩是 OpenClaw 自动触发的，不是你手动调的。但你当前的 compaction 配置用的是 gpt-4o-mini，而这个模型在当前 OpenClaw 版本下已经不完全兼容了。

### 问题 3：25 秒超时不够弹性

Guardian 的 `subprocess.run(timeout=25)` 是硬编码的。在正常的 7 秒响应时间下这个超时很充裕，但当 gateway 真忙的时候（比如在压缩 50k+ tokens 的会话），25 秒远远不够——压缩本身就需要 30-40 秒。

---

## 四、解决方案

### 方案 A：治本但需要动 OpenClaw 配置（推荐）⭐⭐⭐

**1. 换一个能用的 compaction 模型**

当前 gpt-4o-mini 有两个问题（上下文太小 + API 路由不兼容）。换成 gpt-4o 或 claude-3.5-haiku：
```bash
# 在 openclaw.json 中把 compaction 模型从 gpt-4o-mini 换成：
"compactionModel": "openai/gpt-4o"  
# 或
"compactionModel": "anthropic/claude-3-5-haiku-20241022"
```
gpt-4o 有 128k 上下文，足以容纳压缩 prompt。这样压缩不会再连续失败，12 点那类事故就不会发生。

**2. 给 guardian 增加退避机制**

当连续 N 次（比如 3 次）ERROR 后，应该进入退避模式——停止频繁检查，改为每 5 分钟检查一次，等 gateway 恢复后再回到 60 秒节奏。而不是像 12 点那样在 gateway 忙于压缩时每分钟都去打它。

### 方案 B：guardian 自身解耦（中期优化）⭐⭐

**3. 让 guardian 直接读会话文件，不走 gateway API**

recovery-watch 的核心需求是：
- 读取会话 JSONL 文件
- 读取 sessions.json 索引
- 对比 transcript 和 chat.history

这些文件都在本地磁盘上，guardian 完全可以直接 `json.load()` 读文件，不必走 `openclaw gateway call chat.history` 这个绕了一大圈的路径。

走了 gateway 的问题是：`subprocess(["openclaw", "gateway", "call", ...])` 会启动一个新的 Node.js 进程来调用 gateway 的本地 API，这个初始化本身就有开销，而且还在和 gateway 主进程抢事件循环。

直接读文件：
- 0 网络依赖
- 0 事件循环竞争
- 速度从 7 秒降到 <0.5 秒
- 不与 gateway 抢资源

### 方案 C：短期防御（现在就做）⭐

**4. 给 gateway 加 systemd MemoryHigh 限制**

防止压缩/大文件 I/O 把内存打爆导致 swap thrashing：
```
MemoryHigh=2G
MemoryMax=3G
```
这不会解决压缩失败的问题，但能防止 gateway 在压缩时内存膨胀到触发 swap、进一步拖慢一切。

**5. 调整 guardian 检查频率**

当前：每 60 秒一次，无论 gateway 是什么状态
改成：正常 60 秒，但检测到连续 3 次 ERROR 后自动降频到 300 秒（5 分钟）
等一次 OK 后恢复 60 秒

这能防止 12 点那类"43 次连续 ERROR"——gateway 已经在全力自救，guardian 却每分钟都去打它一下，加重了负担。

---

## 五、优先级建议

| 优先级 | 动作 | 预期效果 |
|--------|------|----------|
| 🔴 高 | 换 compaction 模型 (方案A.1) | 消除 12 点类事故根因 |
| 🟠 中 | guardian 加退避逻辑 (方案A.2/B.5) | 防止 cluster 级连续错误 |
| 🟡 中 | guardian 改直接读文件 (方案B.3) | 根本解耦，降低延迟 |
| 🟢 低 | gateway MemoryHigh 限制 (方案C.4) | 防御性措施 |

你觉得这个方向怎么样？要我先执行哪个方案？
