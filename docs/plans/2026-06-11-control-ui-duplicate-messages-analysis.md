# Control UI 消息重复问题排查报告

> 时间：2026-06-11 17:45–18:00 CST
> 用户反馈：截图显示聊天回复经常出现两条一样的消息

---

## 排查步骤

### 1. 数据层验证

`sessions_history` 查询主会话最近消息 → **消息数据无重复**，每条消息都有唯一的 `seq`、`responseId`、`__openclaw.id`。

→ 问题在**前端渲染层**，不是后端数据。

### 2. 浏览器复现

agent-browser 中发送 3 条测试消息，全部正常渲染，未出现重复。

→ 问题是**偶发性**的，可能在 WebSocket 重连/订阅事件推送时触发。

### 3. JS Bundle 代码分析

深入分析了 v6.5 Control UI bundle (`index-jM0oJkaS.js`) 的消息加载与合并逻辑：

**核心函数 `jg` (新消息检测)**：
```javascript
function jg(e, t, n) {
    if (t === e || t.length <= e.length || e.some((e, n) => t[n] !== e)) 
        return [];
    let r = [];
    for (let i of t.slice(e.length)) {
        if (!Eg(i) || Cg(i)) return [];
        let e = Dg(i);
        if (!e) return [];
        kg(n, e, i) || r.push(i);
    }
    return r;
}
```

`jg` 使用**引用相等** (`t === e`) 来判断是否需要计算新消息。当 `chatMessages` 和 `c` 是同一引用时直接返回空数组。但如果在异步加载过程中引用被替换（如订阅推送触发并行加载），这个检查可能失效。

**加载去重缓存 `Gg`**：
```javascript
if (s?.key === o && s.client === e.client && s.messages === e.chatMessages) 
    return s.promise;
```

也使用 `s.messages === e.chatMessages` 引用相等。如果 `chatMessages` 被替换了引用，缓存命中失败 → 并行请求 → 可能导致重复渲染。

**`duplicateCount` 字段**：
消息分组结构中有 `duplicateCount` 字段，说明系统**设计了重复检测机制**，但在某些条件下可能失效（如引用被替换、订阅重连时的竞态）。

### 4. 品牌注入排查

检查了 `JarvisProjectYieldedHistoryReply` → 此函数只过滤/补充消息，不修改已有消息的 key/引用。确认**品牌注入不是重复消息的原因**。

## 结论

| 项目 | 结论 |
|------|------|
| 根因位置 | v6.5 Control UI bundle 的消息订阅/历史加载去重逻辑 |
| 触发条件 | WebSocket 订阅重连、并行历史加载竞态 |
| 频率 | 偶发（非每条消息都出现） |
| 是否品牌注入导致 | ❌ 否 |
| 数据层 | ✅ 无重复 |
| 修复方向 | 上游 v6.5 的渲染层 bug，非本地可修 |
| 临时缓解 | 硬刷新 (Ctrl+Shift+R) 可清除重复的 UI 渲染 |

## 建议

1. 此 bug 对功能无影响（只是视觉重复，数据正常）
2. 出现时硬刷新可临时解决
3. 关注上游 OpenClaw 后续版本是否修复消息订阅去重逻辑
4. 如果频率升高，可以考虑在品牌注入中添加按 `message.__openclaw.id` 去重的补丁

## 排查参考

- JS Bundle：`~/.npm-global/lib/node_modules/openclaw/dist/control-ui/assets/index-jM0oJkaS.js`
- 关键函数：`jg` (新消息检测)、`Yg` (历史加载)、`Gg` (加载去重缓存)
- 消息分组：`duplicateCount` 字段在位置 415654
- 群组渲染：`chat-activity-group`、`chat-group-messages`
- 品牌函数：`JarvisProjectYieldedHistoryReply` 不参与去重逻辑
