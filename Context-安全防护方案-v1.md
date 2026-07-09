# Context 安全防护方案 v1（2026-07-08）

> **目的**：把 OpenClaw 上下文管理"撑爆→compaction→失败→沉默循环"的致命链路，通过**多层防御**大幅降低触发概率。
> **核心问题**：OpenClaw compaction bug（github #43661、#38233）—— 大上下文 + compaction 超时 → 进入沉默失败循环 + 重复发同一条消息 → 会话永不恢复。
> **本方案不写代码**：只列改动 + 验证步骤 + 风险评估。等点点拍板后逐项执行。

---

## 一、问题真实链路（联网核实）

### 1.1 compaction 为什么会超时

三层根因（来源：Towards AI + docs.openclaw.ai + OpenClaw issue tracker）：

| 层 | 根因 |
|---|---|
| L1 | 上下文越长 → LLM 从"计算受限"变成"内存带宽受限" → 推理变慢 |
| L2 | compaction 自身需二次调用 LLM 做 summarization → 叠加在已经很大的上下文上 |
| L3 | OpenClaw 2026.3.2+ 手动/自动两条路径都有 timeout 风险（300s 上限）|

### 1.2 OpenClaw 沉默循环 bug 的真实症状

不是"会话卡死"，而是**沉默循环 + 重复发同一条消息**：
- compaction 超时（~10 分钟）→ 触发 delivery retry
- 同一条消息**重复发 4 次**给用户
- **没有 recovery、没有 fallback、会话无法自我解决**
- 来源：github.com/openclaw/openclaw/issues/43661

### 1.3 为什么 Mark42 改不了这个 bug

- Mark42 armor_compress 走的是 `openclaw sessions compact --max-lines 200 --timeout 180000`（**3 分钟超时，比 OpenClaw 自身 10 分钟短**）
- armor.py:641 `except subprocess.TimeoutExpired` 兜底完善
- **Mark42 已经在设计上绕开这个 bug，但绕不开 OpenClaw 自身的沉默循环**

---

## 二、本方案三道防线

### 防线 1：Session Pruning（**上下文保护第一道**）

**原理**：定期把老 tool result 在内存中替换为短占位符，**不删原文**，只压缩 LLM 视野。
**配置位置**：`openclaw.json` → `agents.defaults.contextPruning`
**官方依据**：docs.openclaw.ai/concepts/session-pruning
**当前状态**：❌ **未启用**（默认仅 Anthropic 插件自动开）
**风险等级**：🟢 **最低**（in-memory，不改 transcript，下次请求重新加载）

```json
"contextPruning": {
  "mode": "cache-ttl",
  "ttl": "10m",
  "keepLastAssistants": 4,
  "softTrimRatio": 0.65,
  "hardClearRatio": 0.88,
  "minPrunableToolChars": 1200,
  "tools": {
    "allow": ["exec", "read", "process", "web_search", "web_fetch", "image"]
  }
}
```

**作用**：
- 65% 软修剪：把老 tool result 替换为短占位符
- 88% 硬清空：彻底清掉（但 transcript 仍保留）
- 不触发 compaction → **从源头避免撑爆**

### 防线 2：Compaction.model 改用更小更快的模型

**原理**：把"贵/慢的主模型做 summarization"换成"便宜/快的 flash 模型"。
**配置位置**：`openclaw.json` → `agents.defaults.compaction.model` 和 `memoryFlush.model`
**官方依据**：docs.openclaw.ai/concepts/compaction
**当前状态**：❌ **未配置**（默认用主模型 MiniMax-M3 做 compaction）
**风险等级**：🟡 **中**（必须先验证候选模型真能用 + 真稳定）

**联网核实的候选模型**：

| 候选 | 类型 | 推荐度 | 理由 |
|---|---|---|---|
| **`litellm/agnes-2.0-flash`** ⭐ | flash | ✅ **强首推** | 已在 fallback 链验证；flash = 快 + 便宜；适合 dense 工作 |
| `minimax/MiniMax-M2.5` | 同厂旧版 | ✅ **次推** | 已在 fallback 链验证；同厂 API 零风险；免费 |
| `taotoken/gpt-5.4` | GPT-5.4 | ⚠️ 慎用 | 第三方代理，未本地实测 |
| `nvidia/*` 系列 | MoE 大模型 | ❌ **禁用** | 太大太慢；你 7-08 09:34 明确说 gemma-4-31b-it "不好用" |

**推荐配置**：

```json
"compaction": {
  "mode": "safeguard",
  "truncateAfterCompaction": true,
  "keepRecentTokens": 25000,         // ← 从 12000 抬到 25000（官方推荐下限）
  "notifyUser": true,
  "maxActiveTranscriptBytes": 3000000,
  "maxHistoryShare": 0.4,
  "model": "litellm/agnes-2.0-flash",  // ← 新增：compaction 用 flash
  "memoryFlush": {
    "enabled": true,
    "model": "litellm/agnes-2.0-flash",  // ← 新增：flush 也用 flash（保留你那段救命 prompt）
    "softThresholdTokens": 32000,
    "prompt": "...",
    "systemPrompt": "..."
  }
}
```

### 防线 3：保留现有 memoryFlush prompt + 提高 keepRecentTokens

**原理**：
1. 保留你那段**救命 3 prompt**（关于 edit vs write 的纪律）—— 它是你精心写的，是资产
2. 把 `keepRecentTokens` 从 12000 抬到 25000（官方推荐下限）—— 保留更多近期上下文
3. `mode: "safeguard"` 保持（OpenClaw 2026.6+ 新默认，更严）

**风险等级**：🟢 **低**（只改一个数值 + 保留全部原有 prompt）

---

## 三、改动前必做（不改配置）

### 检查 1：openclaw.json 当前结构

✅ **已实查**（2026-07-08 09:38）：
- 文件大小 15394 chars
- JSON 解析成功
- `agents.defaults.compaction` 只有一个块（之前"双块"是 grep 误读）
- 子 keys：`['mode', 'truncateAfterCompaction', 'keepRecentTokens', 'notifyUser', 'maxActiveTranscriptBytes', 'memoryFlush', 'maxHistoryShare']`
- **结论**：✅ 无需合并双块，结构干净

### 检查 2：候选模型真实可用性

需跑 1 次轻量 prompt 验证 `litellm/agnes-2.0-flash` 当前延迟和成功率：
```bash
# 在 TTY 跑（不在 WebChat，避免触发 7-07 同款渲染问题）
curl -sS -X POST http://127.0.0.1:18789/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"litellm/agnes-2.0-flash","messages":[{"role":"user","content":"一句话总结：今天天气不错"}],"max_tokens":50}'
```

### 检查 3：备份当前配置（**必做**，防止改坏后无法回退）
```bash
cp /home/missyouangeled/.openclaw/openclaw.json \
   /home/missyouangeled/.openclaw/openclaw.json.bak.20260708-context-safety
```

---

## 四、改动执行步骤（**全部需点点逐项拍板**）

### 步骤 1：启用 Session Pruning
- [ ] 备份 openclaw.json（检查 3 已做）
- [ ] 在 `agents.defaults` 下新增 `contextPruning` 块
- [ ] 跑 `openclaw gateway restart`（如必要）
- [ ] WebChat 发一条测试消息验证渲染未坏
- [ ] 等 10 分钟看 pruning 是否生效（日志应该有 pruning 事件）

### 步骤 2：配置 compaction.model
- [ ] 跑候选模型验证（检查 2）
- [ ] 在 `agents.defaults.compaction` 下新增 `"model": "litellm/agnes-2.0-flash"`
- [ ] 在 `memoryFlush` 下新增 `"model": "litellm/agnes-2.0-flash"`
- [ ] 把 `keepRecentTokens` 从 12000 抬到 25000
- [ ] 跑 `openclaw gateway restart`（如必要）
- [ ] 等下一次自动 compaction 触发（可能要等几小时），看是否成功

### 步骤 3：观察期（7 天）
- [ ] 每天检查 `openclaw logs --limit 100 | grep -E "compaction|pruning"`
- [ ] 看是否还有 timeout / 重复消息 / hang 现象
- [ ] 记录到 `memory/daily/2026-07-XX.md`

---

## 五、改动后必跑的验证清单

```
[ ] 1. openclaw status                                    # gateway 健康
[ ] 2. openclaw logs --limit 20 --no-color | tail -10    # 无新错
[ ] 3. python3 scripts/mark42.py status --json            # armor.usagePercent < 60%
[ ] 4. python3 -m pytest scripts/tests/ -q                # 仍 700 passed
[ ] 5. WebChat 发"渲染测试"短消息                          # 收到纯文字回显
[ ] 6. TTY 跑 cat /home/missyouangeled/.openclaw/openclaw.json | python3 -m json.tool   # 验证 JSON 仍合法
```

**任何一项不通过 → 立即 `cp openclaw.json.bak.20260708-context-safety openclaw.json` 回退**

---

## 六、不在本方案范围的事

- ❌ 不动 Mark42 业务代码（armor.py / engine.py / cli.py）
- ❌ 不推送 GitHub（点点 7-08 08:31 指示）
- ❌ 不修 OpenClaw 源码（#43661 是上游问题，等官方）
- ❌ 不安装 Ollama / 本地模型
- ❌ 不改主模型路由（MiniMax-M3 仍是主模型）

---

## 七、意外发现 + 已有认知

### 7.1 openclaw.json 双 compaction 块的真相

之前看到"两个 compaction 块"是 **grep 工具的伪影**——`truncateAfterCompaction`（是 `compaction` 的子字段）被误判为"第二个块开头"。
**真实情况**：JSON 结构干净，无需合并。

### 7.2 当前已配置的可用小模型（联网核实后）

| 模型 | 作为 compaction.model 推荐？ |
|---|---|
| `litellm/agnes-2.0-flash` | ✅ **首推**（flash = 快 + 已在 fallback 链）|
| `minimax/MiniMax-M2.5` | ✅ 次推（同厂、已验证、免费）|
| `taotoken/gpt-5.4` | ⚠️ 慎用（第三方，未本地实测）|
| `nvidia/*` 系列 | ❌ **禁用**（太大太慢；gemma-4-31b-it 你明确说不好用）|

### 7.3 联网核实来源

- OpenClaw compaction 文档：docs.openclaw.ai/concepts/compaction
- OpenClaw session pruning 文档：docs.openclaw.ai/concepts/session-pruning
- 完整 JSON 模板范例：James Layne YouTube 教程（"How To Fix Your OpenClaw's Memory FOR GOOD"）
- 当前 memory consolidation 共识（2026-04）：OnlyTerp/openclaw-optimization-guide 明确说"memory consolidation is cheap, dense, deterministic work" —— 适合用 flash 模型

---

## 八、本方案文件位置

- **桌面**：`~/Desktop/Context-安全防护方案-v1.md`（点点要求）
- **工作区**：`/home/missyouangeled/.openclaw/workspace/Context-安全防护方案-v1.md`
- **归档日期**：2026-07-08 09:40
- **状态**：📋 **待点点逐项拍板**

---

## 九、一句话总结

> **用 Session Pruning 防止上下文撑爆 + 用 flash 模型做 compaction/memoryFlush 避免主模型超时 + 保留救命 prompt**——三层防御，把 OpenClaw #43661 沉默循环的触发概率从"每次大上下文都可能触发"压到"几乎不可能"。
>
> **不写代码，只改 openclaw.json 中的 3 个键 + 加 1 个键。改完可立即回退。**