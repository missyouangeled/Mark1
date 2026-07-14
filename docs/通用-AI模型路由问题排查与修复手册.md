# AI 模型路由问题排查与修复手册

> 最后更新：2026-06-22
> 触发原因：个人 DeepSeek 持续被误扣费，排查发现多层配置泄漏

---

## 一、快速诊断命令

```bash
# 1. 看当前所有会话在用哪个模型
openclaw status | grep -A5 "Model selection"

# 2. 看所有 session 的模型分布
openclaw sessions list --json | python3 -c "
import json, sys; d=json.load(sys.stdin)
for s in d['sessions']:
    print(f\"  {s['key'][:50]:50s}  {s.get('modelProvider','?')}/{s.get('model','?')}\")
"

# 3. 查个人 DeepSeek 余额
python3 -c "
import json, urllib.request
with open(openclaw.json) as f: cfg=json.load(f)
key=cfg['models']['providers']['deepseek-company']['apiKey']
req=urllib.request.Request('https://api.deepseek.com/v1/user/balance')
req.add_header('Authorization', f'Bearer {key}')
print(urllib.request.urlopen(req,timeout=10).read().decode())
"

# 4. 看 cron 定时任务用哪个模型
openclaw cron list --json | python3 -c "
import json, sys; jobs=json.load(sys.stdin)
for j in jobs if isinstance(jobs,list) else jobs.get('jobs',[]):
    print(f\"  {j.get('name','?')[:30]:30s}  model={j.get('payload',{}).get('model','?')}\")
"
```

---

## 二、模型路由的三个层级（从高到低优先级）

| 优先级 | 位置 | 字段 | 说明 |
|--------|------|------|------|
| 🔴 最高 | `sessions.json` | `modelOverride` | 当前会话钉死的模型（UI 选择器写入） |
| 🟡 中 | `agents.defaults.model.primary` | `primary` | 新会话默认模型 |
| 🟢 最低 | `agents.list[*].model.primary` | `primary` | 子 agent（dashboard/coder/researcher）默认模型 |

**关键规则：** `modelOverride` 不为 null 时，上面的 primary 全部失效。

---

## 三、今日修复清单（2026-06-22）

### 修复 1：agents.list 三个 agent 用的还是 V4 Pro

**文件：** `~/.openclaw/openclaw.json`

**根因：** 只改了 `agents.defaults.model.primary`，没改 `agents.list[*].model.primary`。
子 agent（dashboard/coder/researcher）每次启动都走 V4 Pro，持续扣费。

**修复：**
```json
"agents": {
  "defaults": { "model": { "primary": "minimax/MiniMax-M3", "fallbacks": ["litellm/agnes-2.0-flash"] } },
  "list": [
    { "id": "main",       "model": { "primary": "minimax/MiniMax-M3", "fallbacks": ["litellm/agnes-2.0-flash"] } },
    { "id": "researcher", "model": { "primary": "minimax/MiniMax-M3", "fallbacks": ["litellm/agnes-2.0-flash"] } },
    { "id": "coder",      "model": { "primary": "minimax/MiniMax-M3", "fallbacks": ["litellm/agnes-2.0-flash"] } }
  ]
}
```

---

### 修复 2：主会话被 modelOverride 钉死在 V4 Pro

**文件：** `~/.openclaw/agents/main/sessions/sessions.json`

**根因：** sH 函数每次触发都写 `modelOverride=deepseek-v4-pro`，即使你改了 defaults 也没用。

**修复：**
```json
"agent:main:main": {
  "modelOverride": null,
  "providerOverride": null,
  "model": "MiniMax-M3",
  "modelProvider": "minimax"
}
```

> ⚠️ 手动改完立即被 sH 覆盖。只在网关重启且用户未操作时有效。

---

### 修复 3：sH 函数——模型选择列表失控

**文件：** `~/.npm-global/lib/node_modules/openclaw/dist/control-ui/assets/index-ogWrBZIb.js`

**原始问题链：**
1. 旧版 sH 没有 HB 早退 → 模型没变也触发 sessions.patch
2. sessions.patch 写入 modelOverride → 钉死 session
3. 同时注入 3 条 chat.inject（含 300 字系统指令 + 7 个启动文件列表）→ 每次切模型多 8K tokens
4. 切换大量子会话时，sH 批量触发 → 每条子会话都写入 V4 Pro → 持续扣费

**修复后 sH 函数（完整代码）：**
```javascript
async function sH(e,t){
  if(!e.client||!e.connected)return!1;
  if(HB(e)===t)return!0;  // 早退：模型没变不触发
  
  let n=e.sessionKey,r=e.chatModelOverrides[n];
  cV(e,null);
  e.chatModelOverrides={...e.chatModelOverrides,[n]:Oa(t)};
  let i=e.client,a={},
      o=()=>{if(e.chatModelSwitchPromises?.[n]===a.current){
        let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}
      },
      s=(async()=>{
        try{
          let s=await i.request(`sessions.patch`,{key:n,...ny(e,n),model:t||null}),
              c=typeof s?.resolved?.modelProvider===`string`?s.resolved.modelProvider.trim():``,
              l=typeof s?.resolved?.model===`string`?s.resolved.model.trim():``,
              u=t?c&&l?`${c}/${l}`:t:null;
          e.chatModelOverrides={...e.chatModelOverrides,[n]:u?Oa(u):null};
          let d=e.sessionsResult;
          if(d&&s?.entry)e.sessionsResult={...d,sessions:d.sessions.map(
            e=>e.key===n||s.key&&e.key===s.key?{...e,...s.entry,key:e.key}:e)};
          // 只注入 1 条轻量 boot 消息
          try{await i.request(`chat.inject`,{sessionKey:n,
            message:`[system-boot] 模型已切换至 ${c||t}，请按 BOOT_INDEX.md 执行启动流程（只执行一次）。`,
            label:`system-boot`})}catch{};
          await e.onSlashAction?.(`refresh-tools-effective`),UV(e),await dV(e);
          return!0
        }catch(t){
          return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},
            cV(e,`Failed to set model: ${String(t)}`),!1
        }finally{o()}
      })();
  return a.current=s,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:s},s
}
```

**关键改动 vs 原始版：**
| 项 | 原始 | 修复后 |
|----|------|--------|
| 早退判断 | ❌ 无 | `if(HB(e)===t)return!0` |
| chat.inject 数 | 3 条（含 system-loading/system-boot/system-ready） | 1 条（轻量 system-boot） |
| modelOverride 写入 | 写 sessions.patch model | 同（保留 UI 选择权） |

---

### 修复 4：toolResult 无限制 → 大 dump 进上下文

**文件：** `~/.openclaw/openclaw.json`

```json
"agents": {
  "defaults": {
    "contextLimits": {
      "toolResultMaxChars": 8000,
      "memoryGetMaxChars": 4000,
      "memoryGetDefaultLines": 200
    },
    "imageMaxDimensionPx": 800
  }
}
```

---

### 修复 5：DeepSeek 价格配置过期

**文件：** `~/.openclaw/openclaw.json`

DeepSeek 2026-04-25 永久降价，cache hit 从 $0.145/M → $0.014/M（降 90%）。

```json
"models": {
  "providers": {
    "deepseek-company": {
      "models": [{
        "id": "deepseek-v4-pro",
        "cost": { "input": 1.74, "output": 3.48, "cacheRead": 0.014, "cacheWrite": 0.014 }
      }]
    }
  }
}
```

---

### 修复 6：resume-watch 每 5 分钟误重启 gateway

**根因：** `openclaw-resume-watch.timer` 检测 gap > 600s 就重启，但误判频繁。

**修复：** 永久 disable + mask
```bash
systemctl --user disable --now openclaw-resume-watch.timer
systemctl --user mask openclaw-resume-watch.timer
systemctl --user mask openclaw-resume-watch.service
```

---

### 修复 7：BOOT_INDEX 防重复触发

**文件：** `~/.openclaw/workspace/BOOT_INDEX.md`

在顶部加了一行：
```markdown
> **🛑 防重复：如果你在本会话中已经执行过本加载流程，不要再重复执行。每会话只执行一次。**
```

---

## 四、上下文文件精简

| 文件 | 改前 | 改后 | 节省 |
|------|------|------|------|
| PLANS.md | 150KB | 1.5KB | -99% |
| TOOLS.md | 55KB | 3KB | -95% |
| PROJECT_INDEX.md | 135 行 | 17 行 | -87% |
| WORKSPACE_INDEX.md | 110 行 | 32 行 | -71% |
| ACTIVE_RULES.md | 118 行 | 43 行 | -64% |
| SKILL_CATALOG.md | 132 行 | 70 行 | -47% |
| **总计** | **249KB** | **35KB** | **-86%** |

---

## 五、如果以后再遇到「模型不对劲 / 扣费异常」

### 排查流程

1. **`openclaw status`** → 看当前会话模型和 Reason
2. **检查 sessions.json** → `agent:main:main.modelOverride` 是否为空
3. **检查 openclaw.json** → `agents.defaults.model.primary` + `agents.list[].model.primary`
4. **检查 sH 函数** → bundle 里 `chat.inject` 是否 > 1（旧 bug）
5. **查余额** → DeepSeek API `/v1/user/balance`
6. **检查 cron** → cron 任务是否还在用 V4 Pro
7. **检查 timer** → `systemctl --user list-timers` 看 resume-watch

### 快速修复

```bash
# 清空主会话 modelOverride
python3 << 'PYEOF'
import json
sp = '/home/missyouangeled/.openclaw/agents/main/sessions/sessions.json'
with open(sp) as f: d = json.load(f)
d['agent:main:main']['modelOverride'] = None
d['agent:main:main']['model'] = 'MiniMax-M3'
d['agent:main:main']['modelProvider'] = 'minimax'
with open(sp, 'w') as f: json.dump(d, f, indent=2)
PYEOF

# 重启
systemctl --user restart openclaw-gateway.service
```

---

## 六、当前终极配置（2026-06-22 终态）

| 场景 | 模型 |
|------|------|
| 新会话默认 | minimax/MiniMax-M3（免费） |
| 子 agent（dashboard/coder/researcher） | minimax/MiniMax-M3 |
| 当前会话（由 UI 选择列表决定） | 用户自选 |
| 个人 DeepSeek（deepseek-company） | 仅手动选择时使用 |
| 个人 DeepSeek | 仅手动选择时使用 |
| 所有 cron 定时任务 | minimax/MiniMax-M3 |
| resume-watch | 已永久 disable |

---

*本手册由 2026-06-22 模型路由大排查自动生成，后续如有更新请追加日期标记。*


---

## 6. multimodal 模型 input 字段配置规范(2026-07-14 12:37 加)

**踩过的坑**:MiniMax-M3 是原生多模态模型(支持 text/image/video),但 OpenClaw `~/.openclaw/openclaw.json` 里 `minimax` provider 的 `MiniMax-M3` 模型定义 `input` 字段只声明了 `["text"]`,导致:
- image 工具调用失败,错误 `Model does not support images: ... input: text`
- 会话元数据写 `capabilities=none`
- 即使联网确认 M3 是多模态,OpenClaw 工具链仍拒绝

**修法**(对任何 multimodal 模型都适用):

```json
{
  "id": "MiniMax-M3",
  "name": "MiniMax-M3",
  "input": ["text", "image", "video"],   // ← 必须显式声明
  "reasoning": true,
  "contextWindow": 1000000,
  "maxTokens": 65536
}
```

**对照 NVIDIA 已配对的多模态模型**(可参考):

| 模型 | input 字段 |
|---|---|
| nvidia/nemotron-nano-12b-v2-vl | `["text", "image"]` |
| google/gemma-4-31b-it | `["text", "image"]` |
| **minimax/MiniMax-M3(本手册钉死的修复)** | `["text", "image", "video"]` |

**诊断步骤**(image 工具失败时):
1. 错误信息里有 `Model does not support images: ... input: <字段>`
2. 打开 `~/.openclaw/openclaw.json`,找该模型的 input 字段
3. 如果是 `["text"]`,改为 `["text", "image"]`(多模态加)
4. `openclaw config validate` 验证
5. **重启 gateway 或新开会话**才能生效(会话级能力缓存)

**注意事项**:
- 改配置前必须 **cp 备份** `~/.openclaw/openclaw.json`
- 不确定模型是否支持 multimodal 时,先查官方文档,不要凭印象加
- 改完不 restart gateway 是最安全的(避免 CASE-20260706-003)
- 验证时建议在 Control UI 新开会话发图,不在主会话 restart

