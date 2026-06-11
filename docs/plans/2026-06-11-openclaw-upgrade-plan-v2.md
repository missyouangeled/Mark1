# OpenClaw 升级方案 v2：2026.5.22 → 2026.6.5

> 起草时间：2026-06-11 17:05 CST
> 起草原因：上午 5.22→6.5 升级后 Control UI 多次黑屏，用户已恢复 VM 快照 3 次。
> 本次升级将吸取上午失败教训，在升级记录基础上补充 Control UI 逐步验证 + 每步回退策略。
>
> ⚠️ 前置条件：当前系统已是 5.22 快照状态，npm 版本 5.22，品牌补丁在位，watcher 全活。

---

## 🔥 根因发现（2026-06-11 17:15）

**Control UI 黑屏根因**：品牌脚本 `JARVIS_FUNCTIONS_V2026_6_5` 中 `JarvisShouldShowPendingReadingIndicator` 函数，同一个 `for` 循环块内有两处 `let i` 声明：

```javascript
let i=uf(t);if(!i||!i.role)continue;...  // 第一次
let i=typeof t.timestamp=='number'?...   // 第二次 — SyntaxError!
```

→ 导致整个 JS bundle 解析失败 → Control UI 黑屏。

**修复**：第二个改名为 `let ti`，已提交 `b7231be`。

---

## 执行进度

| 步骤 | 状态 | 说明 |
|------|------|------|
| 阶段0 checkpoint | ✅ | Git commit `04a22b1` |
| 阶段1 npm 升级 | ✅ | v2026.5.22 → v2026.6.5 |
| 阶段2 Gateway 重启 | ✅ | 排水卡住→kill -9 强杀后重启 |
| 阶段3 品牌补丁 | ✅ | 修复 `let i` → `let ti`，`node --check` 通过 |
| 阶段3 去重问题 | ✅ | 初次打补丁时去重检测跳过了修复→重新 npm install → 重打补丁 |
| 阶段4 Gateway 再次重启 | ✅ | active, healthz 200 |
| 阶段5 浏览器实操验收 | ⏳ 待执行 | agent-browser 打开 Control UI + 硬刷新 |
| 阶段6 全量烟测 | ⏳ 待执行 | |

**关键修复 commit**：`b7231be` — `fix: 修复 v6.5 品牌补丁 let i 重声明导致 Control UI 黑屏`

---

## 上午失败根因分析

升级记录（#2，2026-06-11）里列了哪些已修，但 **遗漏了 Ctrl+Shift+R 后黑屏这个致命问题**。当时补丁打好后看 HTTP 200 和品牌注入就收工了，没有：

1. 清除浏览器缓存后重新打开 Control UI 验证
2. 检查 JS bundle 语法错误（`index-XXX.js` 补丁注入后是否仍合法）
3. 验证模型下拉选择器在升级后是否真的内建可用
4. 验证「贾维斯 Control」品牌标题 + favicon 在硬刷新后仍正常

### 黑屏最可能的根因

根据上次升级记录提到的 INVALID_FINAL_RELOAD 修复（`{qg(e);return}` → `return;`）——**如果这个修复在某个 bundle 版本上不完整，Ctrl+Shift+R 可能触发 JS 错误并导致整个 UI 崩溃。**

其次可能是 branding 补丁打完后 `index-XXX.js` 产生了语法错误（之前 6.2 发生过——重复变量声明导致 SyntaxError）。

---

## 升级步骤

### 阶段 0：升级前 checkpoint

```bash
# 0.1 确认当前版本
openclaw --version
npm ls -g openclaw

# 0.2 确认 gateway 正常
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18789/healthz

# 0.3 保存当前 Control UI 资产（对比用）
cp -r ~/.npm-global/lib/node_modules/openclaw/dist/control-ui \
  ~/.npm-global/lib/node_modules/openclaw/dist/control-ui.v522.bak

# 0.4 git commit + push 当前工作区
cd ~/.openclaw/workspace && git add -A && git commit -m "checkpoint: pre-upgrade 5.22→6.5" && git push
```

**验收**：版本显示 5.22、healthz 200、git push 成功。

### 阶段 1：执行 npm 升级

```bash
npm update -g openclaw
openclaw --version
```

**验证**：`openclaw --version` 应显示 `2026.6.5`。
**回退**：若失败，`npm install -g openclaw@2026.5.22` + 恢复快照。

### 阶段 2：Gateway 重启 + 基础连通性

```bash
openclaw gateway restart
sleep 5

# 验证
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18789/healthz
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18788/
```

**验收**：healthz 200 + unified proxy 200。
**回退**：若不通，检查 `systemctl --user status openclaw-gateway`；必要时回退 npm 版本。

### 阶段 3：品牌补丁重打

```bash
python3 scripts/apply-openclaw-control-ui-branding.py
```

**手动验证补丁结果**：

```bash
# 3.1 确认品牌标记注入
grep -c "jarvis\|贾维斯\|J.A.R.V.I.S" \
  ~/.npm-global/lib/node_modules/openclaw/dist/control-ui/index.html

# 3.2 确认 bundle 文件有 .bak 备份
ls ~/.npm-global/lib/node_modules/openclaw/dist/control-ui/assets/index-*.js.bak

# 3.3 JS 语法检查——这是关键！上午漏掉的
JS_FILE=$(find ~/.npm-global/lib/node_modules/openclaw/dist/control-ui/assets -name "index-*.js" ! -name "*.bak" | head -1)
node --check "$JS_FILE"

# 3.4 确认 INVALID_FINAL_RELOAD 修复存在（{qg(e);return} → return;）
grep -c "qg(e);return" "$JS_FILE"
# 应该返回 0（已被替换掉）

# 3.5 确认没有重复变量声明（上次黑屏根因之一）
node -e "require('$JS_FILE')" 2>&1 | head -5
# 可能报 module not found 但不应报 SyntaxError
```

**验收**：branding grep ≥ 3 处、node --check 通过、qg(e);return = 0。
**回退**：如果 node --check 失败 → 脚本恢复了 .bak 吗？如果没有，从 control-ui.v522.bak 恢复 → 手工分析 bundle 差异 → 修改 branding 脚本。

### 阶段 4：模型选择器验证

**上午记录说「已内建，无需补丁」——这次必须明确验证。**

```bash
# 4.1 确认 data-chat-model-select 在 bundle 中存在
JS_FILE=$(find ~/.npm-global/lib/node_modules/openclaw/dist/control-ui/assets -name "index-*.js" ! -name "*.bak" | head -1)
grep -c "data-chat-model-select" "$JS_FILE"

# 4.2 确认 sessions.patch + model 调用模式存在
grep -c "sessions.*patch.*model\|patch.*key.*model" "$JS_FILE" 2>/dev/null
```

**验收**：data-chat-model-select ≥ 1，sessions.patch+model ≥ 1。
**回退**：若不内建或模式不对 → 考虑写简易补丁或跳过（非 Control UI 核心功能）。

### 阶段 5：Watcher 体系验证

```bash
# 5.1 PATH 检查（上次升级的坑）
for s in frontstage-guardian health-collector task-scheduler lifecycle-maintainer; do
  echo -n "$s: "
  grep "Environment=PATH" ~/.config/systemd/user/openclaw-$s.service 2>/dev/null && echo "OK" || echo "MISSING!"
done

# 5.2 timer 活性
systemctl --user list-timers --no-pager | grep openclaw

# 5.3 最近一次运行状态
for s in frontstage-guardian health-collector task-scheduler lifecycle-maintainer; do
  result=$(systemctl --user show openclaw-$s.service -p Result 2>/dev/null | cut -d= -f2)
  echo "$s: $result"
done
```

**验收**：所有 PATH 在位、timer active、Result=success。
**回退**：PATH 缺失时手动补（sed 添加 Environment=PATH=...），不要跳过。

### 阶段 6：infos-handle / 统一代理验证

```bash
# sidecar
curl -s http://127.0.0.1:18790/healthz

# 代理
curl -s http://127.0.0.1:18788/v1/query/healthz

# 进程
pgrep -a -f "infos-handle"
pgrep -a caddy
```

**验收**：sidecar healthz ok、代理 200、进程存在。

### 阶段 7：Control UI 浏览器实际验证 ⚠️ 关键！

**这是上午完全漏掉的一步。补丁打完后必须用浏览器实操验证。**

```bash
# 7.1 确认 Control UI 页面可加载
curl -s http://127.0.0.1:18789/ | head -c 200

# 7.2 用 agent-browser 实际打开
agent-browser --session upgrade-check close 2>/dev/null
agent-browser --session upgrade-check --args "--no-sandbox" open "http://127.0.0.1:18789/" 2>/dev/null
sleep 3
agent-browser --session upgrade-check eval "document.title" 2>/dev/null

# 7.3 检查 console 是否有 JS 错误
agent-browser --session upgrade-check eval \
  "(()=>{const e=window.__errors__||[];return e.length?e.slice(-5).map(x=>x.message||x):'no errors'})()" 2>/dev/null

# 7.4 强制硬刷新模拟 Ctrl+Shift+R
agent-browser --session upgrade-check eval "location.reload(true)" 2>/dev/null
sleep 4
agent-browser --session upgrade-check eval "document.title" 2>/dev/null
```

**验收**：
- 页面标题应含「贾维斯」
- 无 JS console 错误
- 硬刷新后页面仍正常渲染（标题不变）

**回退到 5.22**：如果这一步任一失败 → **停止** → 报告具体错误 → 恢复快照。

### 阶段 8：模型选择器实际功能验证

```bash
# 8.1 用 API 验证模型切换功能（不走 UI 直接测底层）
openclaw gateway call sessions.patch --json \
  --params '{"key":"agent:main:main","model":"github-copilot/gpt-5.5"}' \
  --timeout 30000 2>&1 | python3 -c "import json,sys;d=json.load(sys.stdin);print('OK' if d.get('resolved') else 'FAIL')"

# 8.2 切回原模型
openclaw gateway call sessions.patch --json \
  --params '{"key":"agent:main:main","model":"deepseek-company/deepseek-v4-pro"}' \
  --timeout 30000 2>&1 | python3 -c "import json,sys;d=json.load(sys.stdin);print('OK' if d.get('resolved') else 'FAIL')"
```

### 阶段 9：烟测 — 发送消息

**经过浏览器实际验证后，试着在 Control UI 里发一条消息确认主会话链路通畅。**

```bash
# 通过 API 发测试消息（不依赖 UI）
openclaw gateway call sessions.send --params '{"sessionKey":"agent:main:main","message":"系统自检：升级到2026.6.5完成，请回复确认收到。"}' --timeout 60000 2>&1
```

**验收**：消息发送成功，AI 回复正常。
**回退**：如果发送失败 → 检查 gateway 日志 `journalctl --user -u openclaw-gateway --since "5 min ago" --no-pager | tail -50`。

---

## 最终收尾

```bash
# 提交升级记录
cd ~/.openclaw/workspace
git add -A && git commit -m "upgrade: 5.22→6.5 complete with full verification" && git push

# 系统总览
python3 scripts/openclaw-system-summary.py --print-human
```

---

## 总结：本次升级 vs 上午的区别

| 步骤 | 上午 | 本次 |
|------|------|------|
| branding 补丁 | 打完后核对 grep 就过了 | ✅ 加 node --check 语法验证 |
| INVALID_FINAL_RELOAD | 修了但不验证 | ✅ grep -c qg(e);return 必须 = 0 |
| 浏览器验证 | ❌ 没做 | ✅ agent-browser 实操 + 硬刷新 |
| JS console 错误 | ❌ 没查 | ✅ 检查 window.__errors__ |
| 模型选择器 | 认为内建 = 可用 | ✅ API 实测 sessions.patch |
| 每步回退策略 | 无 | ✅ 每步注明验收标准 + 回退命令 |

---

## 风险评级

| 风险 | 可能性 | 严重度 | 应对 |
|------|--------|--------|------|
| bundle 补丁语法错误 | 中 | 🔴 黑屏 | JS 文件名变化→脚本检测逻辑可能 miss → node --check 兜底 |
| branding 补丁不匹配 v6.5 bundle | 低 | 🟡 品牌丢失 | 升级记录已验证 OA/w/Ag/gh/Cg/qg 映射 |
| PATH 环境变量被重置 | 低 | 🟡 watcher 挂 | 5.26 修复后未再现 |
| 会话索引膨胀 | 低 | 🟡 磁盘 | 上次已处理，本次预估不大 |
