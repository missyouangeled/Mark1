# 贾维斯中枢 Mark2 升级体系规范

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：标准操作规范（SOP）
- 版本：v1.0（基于 OpenClaw 三次升级实战总结）

## 用途

本规范定义 Mark2 中枢升级的**严格流程**。任何一次版本升级都必须遵循本规范，不得跳步。规范的目标不是"不出问题"（不现实），而是"出了问题能快速发现、准确定位、完整恢复"。

规范基于以下三次实战升级的血泪教训：

| 升级编号 | 版本跳跃 | 核心问题 | 规范来源 |
|---|---|---|---|
| #1 | 2026.5.20→2026.5.22 | systemd PATH 丢失、gateway 找不到 CLI | 第 2/3/5 章 |
| #2 | 2026.5.22→2026.6.5 | Control UI 黑屏（变量冲突）、infos-handle 路由错误、LiteLLM config schema 错误 | 第 2/4/5 章 |
| #3 | 2026.6.5→2026.6.6 | 静态文件路径限制（assets/ 子目录）、Rolldown 模块拆分导致 chat marker 注入失效 | 第 1/2/3/5 章 |

---

## 第〇章：故障处理五步闭环流程（Troubleshooting SOP）

> ⚠️ **这是所有故障处理的铁律，不得跳步。**
> 升级后**任何**失效、异常、报错、回归问题，一律按此流程执行。

### 流程总览

```
Step 1: 联网搜索 → Step 2: 审查问题 → Step 3: 修复 → Step 4: 烟测 → Step 5: 审查结果
                                                                        ↑                    ↓
                                                                        └── 有问题就回到 Step 1 ──┘
```

循环终止条件：**Step 5 确认完全没问题**。只要还有任何残留问题，就继续循环。

### Step 1：联网搜索相关信息

**做什么**：
- 用版本号 + 错误关键词搜索（如"OpenClaw 2026.6.6 static files 404"）
- 搜索 OpenClaw GitHub Issues / Changelog / Release Notes
- 搜索上游构建工具（Rolldown/Vite）相关变更
- 搜索同类用户的报障帖子

**为什么先搜索**：
- 很多问题是已知的，别人可能已经修过
- 避免在错误方向浪费时间
- 可能发现官方有 breaking change 说明

**搜索优先级**：
1. OpenClaw GitHub Releases（查看版本 changelog）
2. OpenClaw GitHub Issues（搜索相同报错）
3. 搜索引擎（版本号 + 错误信息）
4. dist 目录 diff（对比新旧版本的文件结构变化）

### Step 2：审查问题

**做什么**：
- 确认问题的**准确范围**：是什么坏了、什么还正常
- 确认问题的**根因**：是配置错误、代码变化、还是依赖问题
- 区分**新问题** vs **历史回归**：对比升级记录看是否旧病复发
- 对比新旧版本的 **dist/ 目录结构 diff**：文件是否增减、改名、拆分
- 检查 **HTTP 可达性**：哪些路径 200、哪些 404
- 检查 **服务状态**：所有 systemd unit 的 LoadState/ActiveState/UnitFileState

**输出物**：
- 一句话根因描述
- 受影响范围清单（哪些功能坏了）
- 未受影响范围清单（哪些还正常，避免过度修复）

### Step 3：修复

**做什么**：
- 针对根因做最小化修复（不要顺便改不相关的东西）
- 如果涉及路径/配置变化，必须同步更新所有引用该路径的脚本
- 如果上游 API/结构有 breaking change，优先对齐上游新规范，不做 hack

**修复原则**：
- 先修 Critical（核心功能不可用），再修 High（用户体验受损），最后修 Medium/Low
- 每个修复都应该是可回滚的（改什么记什么）
- 修复代码后立即执行 `node --check` 或 Python 语法检查

### Step 4：烟测（Smoke Test）

**做什么**：
- 对修复的每一项做最小验证：能跑了、不报错了、功能正常了
- 运行完整自检：`python3 scripts/openclaw-post-upgrade-self-check.py --force --print-human`
- 如果涉及 Control UI：浏览器实际打开页面，确认能加载、品牌正常、模型可选
- 历史回归点专项验证：对比升级记录中的旧问题是否也被重新触发

### Step 5：审查结果

**做什么**：
- 自检是否**全部 PASS**（除已知限制外）
- 有没有引入**新问题**（修复一个问题同时制造另一个）
- 用户实际使用场景是否正常

**判断标准**：
- 全部 required 项 PASS → 闭环结束
- 还有 FAIL → 回到 Step 1，重新搜索、审查、修复
- 不确定某项是否正常 → 先验证，再判断

### 循环案例：升级 #3 中的实际应用

```
[问题] 升级后自检发现 live_control_ui_markers FAIL
  → Step 1: 搜索 "OpenClaw 2026.6.6 Rolldown module splitting"
  → Step 2: 审查发现 dist/ 结构从单体 bundle 变为多 chunk，chatRunning 不再在 index-*.js 中
  → Step 3: （此轮判定为 Medium 优先级，先修 Critical 的静态文件 404）
  → Step 4: 静态文件修复后验证 HTTP 200，自检 25/26 PASS
  → Step 5: 审查确认 chatRunning marker 失效是架构级变化导致，不是配置错误
             需单独设计模块级注入方案（新建子任务）
             核心功能全部正常 → 此轮闭环，chatRunning 标记为已知限制
```

---

## 补丁注入项说明

升级过程中涉及的几个自定义前端补丁的功能说明：

### JarvisProjectYieldedHistoryReply

**作用**：当后台分身（sub-agent / sessions_spawn）返回结果时，把 yield 状态的 tool result 消息**投影为正常聊天回复气泡**。

**工作方式**：
1. 扫描消息历史中最后一条用户消息之后的所有消息
2. 如果用户消息后面没有正常的 assistant 回复
3. 则检查 tool result 消息是否包含 `{"status":"yielded","message":"..."}` 格式的 payload
4. 如果找到，提取 message 内容，生成一个假的 assistant 消息气泡嵌入聊天流

**失效影响**：
- 分身产出的「已移交」结果**不会自动显示为聊天回复气泡**
- 用户可能在聊天界面看不到分身已完成的工作
- 核心消息**不会丢失**——tool result 本身仍在消息流中，只是不渲染为格式化的 assistant 回复
- 属于**UX 增强层**，不影响系统核心功能

### JarvisShouldShowPendingReadingIndicator

**作用**：判断是否需要显示「等待阅读」指示器。当 session 有 active run 或刚结束，且最后一条用户消息后面只有 tool 消息而没有 assistant 可见回复时，显示一个视觉提示。

**失效影响**：
- 失去「还有内容在处理中 / 等待阅读」的视觉提示
- 消息仍然正常流式传输，只是不显示 pending 指示器
- 属于**UX 增强层**，不影响消息投递和显示

### 总结

| 补丁项 | 类型 | 失效影响 | 严重级别 |
|---|---|---|---|
| JarvisProjectYieldedHistoryReply | 分身产出投影 | 分身结果不自动渲染为聊天气泡 | 🟡 Medium |
| JarvisShouldShowPendingReadingIndicator | 等待阅读指示器 | 失去 pending 视觉提示 | 🟢 Low |
| Branding 覆写（标题/logo/infos-handle） | 品牌 + 健康状态 | 页面标题恢复默认，健康面板打不开 | 🟠 High |

---

## 第一章：升级前必做（Pre-Upgrade）

### 1.1 版本信息收集

```bash
# 当前版本
openclaw --version
npm list -g openclaw | grep openclaw

# 最新可用版本
npm view openclaw version

# 如已有目标版本，获取其变更
npm view openclaw@<target-version> dependencies --json
```

### 1.2 完整备份（不可跳过）

建立带时间戳的备份目录：

```bash
mkdir -p tmp/upgrade-backups/YYYY-MM-DD-X.YtoZ.Z/

# 最小备份集
cp ~/.openclaw/openclaw.json          tmp/upgrade-backups/.../openclaw.json.bak
cp <npm-root>/openclaw/package.json   tmp/upgrade-backups/.../package.json.bak
cp -r ~/.local/state/openclaw         tmp/upgrade-backups/.../state-backup/
cp -r ~/.local/share/openclaw         tmp/upgrade-backups/.../share-backup/
```

### 1.3 配置完整性预检

逐一检查以下项目：

```bash
# 1. Provider API key 是否全部到位
# 2. LiteLLM models 是否为数组格式 [{id, name, input}]
# 3. imageModel 指向的 provider 和 model 是否匹配
# 4. agents.defaults.model 指向的 provider 是否有 apiKey
```

### 1.4 已知问题点预检

针对历史故障做专项扫描：

| 检查项 | 命令 / 方法 | 通过标准 |
|---|---|---|
| systemd PATH | `grep -c "Environment=PATH=%h/.npm-global/bin" ~/.config/systemd/user/openclaw-*.service` | 所有 service 均含 PATH |
| Branding 变量冲突 | `grep -n 'let i\b\|var i\b' <dist>/control-ui/jarvis-branding-override.js` | 无输出 |
| infos-handle 路由 | `grep -c "127.0.0.1:18788" <dist>/control-ui/jarvis-branding-override.js` | >0 |
| LiteLLM models | 确认是数组，每项含 id/name/input | JSON 格式正确 |
| Timer UnitFileState | `systemctl --user show <timer> -p UnitFileState` | enabled |
| Gateway 服务状态 | `systemctl --user is-active openclaw-gateway` | active |
| 磁盘空间 | `df -h / /mnt/data` | 剩余 ≥ 10% |

### 1.5 依赖版本差异分析

```bash
npm view openclaw@<target> dependencies --json > /tmp/new-deps.json
cat <backup>/package.json.bak | python3 -c "import json,sys; ..." > /tmp/old-deps.json
diff /tmp/old-deps.json /tmp/new-deps.json
```

依赖有变化 ≠ 一定有问题，但需要提高警惕。依赖全不变 ≠ 一定没问题（#3 升级就是案例——依赖全不变但构建工具链变化导致产出结构完全不同）。

**v2026.6.6 后新增**：除了依赖 diff，还应关注 `dist/control-ui/` 目录结构变化（如 Rolldown 模块拆分、静态文件服务规则变化）。

---

## 第二章：执行升级（Upgrade）

### 2.1 升级命令

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
npm update -g openclaw
openclaw --version  # 确认新版本号
```

### 2.2 Gateway 重启

```bash
systemctl --user restart openclaw-gateway
sleep 8
systemctl --user is-active openclaw-gateway
```

⚠️ 重启 Gateway 会中断当前会话。如果正在通过当前会话操作，需提前告知用户。

### 2.3 重启后即时检查

| 检查项 | 命令 |
|---|---|
| Gateway 进程 | `systemctl --user is-active openclaw-gateway` |
| 端口监听 | `ss -tlnp \| grep -E "18788\|18789\|18790"` |
| sidecar 服务 | `systemctl --user is-active openclaw-infos-handle-sidecar` |
| 统一代理 | `systemctl --user is-active openclaw-unified-proxy` |

---

## 第三章：升级后验证（Post-Upgrade Validation）

### 3.1 标准自检

```bash
python3 scripts/openclaw-post-upgrade-self-check.py --force --print-human
```

必须全部 PASS（除已知限制外）。如果任何 required 项 FAIL，禁止继续后续步骤，必须先修复。

### 3.2 历史问题点回归

升级后必须逐项验证前几次升级的修复是否仍然有效：

| 历史问题 | 验证方法 | 升级 # |
|---|---|---|
| systemd PATH 丢失 | 检查所有 openclaw-*.service 含 `%h/.npm-global/bin` | #1 |
| Control UI 黑屏 | 访问 `/__openclaw__/control-ui/assets/jarvis-branding-override.js` 返回 200；branding override 正确加载 | #2 |
| infos-handle 路由错误 | override 中 infosHandle 路径为 18788 或 `/v1/...`，不直连 18790 | #2 |
| LiteLLM config schema | openclaw.json 中 litellm.models 为数组且每项含 id/name/input | #2 |
| 静态文件 404 | 所有品牌文件从 `assets/` 子目录可访问（HTTP 200） | #3 |

### 3.3 功能烟测

```bash
# 模型连通性
curl -s -o /dev/null -w "%{http_code}" "https://api.deepseek.com/v1/models" --connect-timeout 5

# infos-handle 查询
curl -s "http://127.0.0.1:18788/v1/query/snapshot.summary?format=json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok'))"

# broker 重建
python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-snapshot-dock

# 最小回归测试套件
python3 scripts/test-frontstage-broker.py
python3 scripts/test-openclaw-infos-handle.py
python3 scripts/test-infos-handle-frontstage-callers.py
```

### 3.4 Watcher 体系验证

| Service / Timer | 期望状态 |
|---|---|
| openclaw-frontstage-guardian.timer | enabled + active |
| openclaw-health-collector.timer | enabled + active |
| openclaw-task-scheduler.timer | enabled + active |
| openclaw-lifecycle-maintainer.timer | enabled + active |
| openclaw-resume-watch.timer | disabled（用户明确要求不启用，见 2026-06-15） |
| openclaw-infos-handle-sidecar.service | active + running |
| openclaw-unified-proxy.service | active + running |

---

## 第四章：故障分类与修复手册

### 4.1 故障严重级别

| 级别 | 定义 | 示例 | 处理策略 |
|---|---|---|---|
| 🔴 Critical | Gateway 无法启动或核心功能不可用 | Gateway 拒绝启动、所有模型调用失败 | 立即回滚或修复，阻塞所有其他操作 |
| 🟠 High | 关键补丁失效，影响用户体验 | Control UI 黑屏、品牌标识丢失 | 优先修复，可接受临时 workaround |
| 🟡 Medium | 辅助功能受损 | chat marker 注入失效、timer disabled | 排期修复，不阻塞正式使用 |
| 🟢 Low | 非功能性变化 | 日志格式变化、非关键路径性能退化 | 记录备查 |

### 4.2 常见故障快速修复

#### Gateway 拒绝启动

**症状**：`systemctl --user status openclaw-gateway` 显示 failed，日志含 `Error:`。

**排查顺序**：
1. `journalctl --user -u openclaw-gateway --since "5 minutes ago" -n 50`
2. 检查 `~/.openclaw/openclaw.json` JSON 格式是否合法
3. 检查 LiteLLM models 是否为数组格式
4. 独立端口烟测：`openclaw gateway start --port 18799` 查看原始错误

**快速回滚**：
```bash
npm install -g openclaw@<previous-version>
systemctl --user restart openclaw-gateway
```

#### Control UI 黑屏 / 打不开

**症状**：访问 Control UI 页面白屏或无限加载。

**排查顺序**：
1. 检查 `jarvis-branding-override.js` 是否可访问（HTTP 200）
2. `node --check <dist>/control-ui/assets/index-*.js` 验证 JS 语法
3. 检查 branding override 是否有变量冲突（如 `let i`）
4. 运行 `python3 scripts/openclaw-control-ui-emergency.py --check --print-human`

#### 静态文件 404

**v2026.6.6+ 特有**：非 HTML 文件必须放在 `assets/` 子目录。

**修复**：
```bash
# 将品牌文件复制到 assets/
cp <dist>/control-ui/jarvis-branding-override.js <dist>/control-ui/assets/
cp <dist>/control-ui/jarvis-frontstage-snapshot.json <dist>/control-ui/assets/
# 更新 index.html 引用
sed -i 's|src="./jarvis-branding-override.js|src="./assets/jarvis-branding-override.js|g' <dist>/control-ui/index.html
```

#### systemd PATH 丢失

**症状**：`journalctl` 显示 `FileNotFoundError: No such file or directory: 'openclaw'`。

**修复**：在每个 `~/.config/systemd/user/openclaw-*.service` 的 `[Service]` 段添加：
```ini
Environment=PATH=%h/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
```

---

## 第五章：升级后收尾（Post-Upgrade Wrap-Up）

### 5.1 文档更新清单

每次升级完成后必须更新以下文件：

| 文件 | 更新内容 | 优先级 |
|---|---|---|
| `docs/通用-OpenClaw-升级记录.md` | 追加本次升级完整记录 | 🔴 必须 |
| `docs/通用-OpenClaw-补丁变更流水.md` | 记录代码变更（用 `scripts/openclaw-change-log.py capture`） | 🔴 必须 |
| `docs/通用-OpenClaw-补丁注册表.md` | 如有新补丁，登记注册 | 🟠 如有 |
| `docs/通用-OpenClaw-非正式修改备忘录.md` | 临时/手工修改（用 `scripts/openclaw-change-log.py memo`） | 🟡 如有 |
| `docs/通用-OpenClaw-升级后自检清单.md` | 如有新检查项，追加 | 🟡 如有 |
| `docs/通用-OpenClaw-补丁重建清单.md` | 如需更新重建步骤 | 🟡 如有 |

### 5.2 Git 提交规范

```bash
git add <changed-files>
git commit -m "fix: 适配 OpenClaw X.Y.Z <简短描述>

<详细说明变更内容和原因>

已知限制：
- <如有>"
```

### 5.3 清理备份

升级成功且稳定运行 7 天后，可清理旧备份：

```bash
# 建议保留最近 3 次升级备份
ls -t tmp/upgrade-backups/ | tail -n +4 | xargs -I {} rm -rf tmp/upgrade-backups/{}
```

---

## 附录 A：升级 Command Sequence（懒人包）

以下是一键式升级命令序列，适用于标准场景。复杂场景仍需按章节分步执行。

```bash
#!/bin/bash
# Mark2 标准升级流程
# 用法：bash scripts/mark2-upgrade.sh

set -euo pipefail

WORKSPACE=~/".openclaw/workspace"
BACKUP_DIR="$WORKSPACE/tmp/upgrade-backups/$(date +%Y-%m-%d)-upgrade"
export PATH="$HOME/.npm-global/bin:$PATH"

echo "=== Step 0: 备份 ==="
mkdir -p "$BACKUP_DIR"
cp ~/.openclaw/openclaw.json "$BACKUP_DIR/"
cp "$(npm root -g)/openclaw/package.json" "$BACKUP_DIR/"
cp -r ~/.local/state/openclaw "$BACKUP_DIR/state-backup/" 2>/dev/null || true

echo "=== Step 1: 升级前自检 ==="
python3 "$WORKSPACE/scripts/openclaw-post-upgrade-self-check.py" --print-human

echo "=== Step 2: 执行升级 ==="
npm update -g openclaw
openclaw --version

echo "=== Step 3: 重启 Gateway ==="
systemctl --user restart openclaw-gateway
sleep 8
systemctl --user is-active openclaw-gateway

echo "=== Step 4: 打补丁 ==="
python3 "$WORKSPACE/scripts/apply-openclaw-control-ui-branding.py"
python3 "$WORKSPACE/scripts/apply-openclaw-session-model-selector-fix.py"

echo "=== Step 5: 升级后自检 ==="
python3 "$WORKSPACE/scripts/openclaw-post-upgrade-self-check.py" --force --print-human

echo "=== 升级完成 ==="
```

## 附录 B：版本兼容性矩阵

| 版本 | Gateway 静态文件规则 | 构建工具 | 已知补丁影响 |
|---|---|---|---|
| ≤ 2026.5.22 | control-ui/ 根目录所有文件可访问 | 单体 bundle | chatRunning 注入在 index-*.js |
| 2026.6.5 | control-ui/ 根目录所有文件可访问 | 单体 bundle（但结构变化） | OA/fj 函数重命名 |
| 2026.6.6+ | 仅 assets/ 子目录提供非 HTML 文件 | Rolldown 模块拆分 | chatRunning 注入失效，品牌文件须放 assets/ |

---

> **📌 本规范随升级经验持续更新。每次升级后如发现新故障模式或有效修复方法，必须追加到本文件对应章节。**
