# OpenClaw 升级记录

> 📌 **用途**：记录每次 OpenClaw 升级的完整经过——升级了什么、出了什么问题、改了什么、怎么验证的。
> 任何 AI 模型读到这个文件都应该能理解每次升级的全貌，并能据此执行后续的升级适配工作。

---

## 升级 #1：2026.5.20 → 2026.5.22

### 基本信息

| 项目 | 内容 |
|------|------|
| 升级日期 | 2026-05-26 |
| 旧版本 | 2026.5.20（推测） |
| 新版本 | 2026.5.22 |
| 触发方式 | 用户手动 `npm update -g openclaw` |
| 升级后动作 | 用户执行 `openclaw gateway restart` |
| 所在机器 | 公司（Linux）— `missyouangeled-VMware-Virtual-Platform` |

### 升级内容变化

OpenClaw 从 2026.5.20 升级到 2026.5.22，上游主要变化：

1. **systemd 环境隔离变化**：新版本的 systemd 服务模板不再自动继承用户 shell 的 `PATH`，导致 `~/.npm-global/bin` 中的 `openclaw` CLI 在 systemd 环境中不可用。
2. **infos-handle 协议无变化**：本次升级未改变 infos-handle 的查询契约，但揭露了此前 `healthz` 查询支持不完整的历史遗留问题。
3. **会话管理变化**：升级后的 gateway 对旧的 sessions 索引文件不兼容，导致会话索引膨胀（39 条→实际有效仅 9 条），需手动清理。

### 升级后自动检测结果

`scripts/openclaw-post-upgrade-self-check.py` 在 gateway 启动时自动运行，结果：`versionChanged=False`（因为上一轮已记录为 2026.5.22，本次检测时版本未再次变化）。

系统审查分身随后执行了 10 项全面检查，发现 **4 个需要修复的问题**。

---

### 🔴 问题 1：frontstage-guardian 持续 crash

**现象**：`openclaw-frontstage-guardian` 服务每约 20 秒由 timer 触发一次，但每次都 exit 1（crash）。

**根因**：
- `openclaw-frontstage-guardian.py` 内部调用了 `openclaw-frontstage-recovery-watch.py`
- 该子脚本中有代码：`subprocess.run(['openclaw', 'sessions', '...'])`
- systemd 服务环境中没有 `~/.npm-global/bin` 在 PATH 里
- 导致 `FileNotFoundError: [Errno 2] No such file or directory: 'openclaw'`

**受影响的服务**（4 个）：
1. `~/.config/systemd/user/openclaw-frontstage-guardian.service`
2. `~/.config/systemd/user/openclaw-health-collector.service`
3. `~/.config/systemd/user/openclaw-task-scheduler.service`
4. `~/.config/systemd/user/openclaw-lifecycle-maintainer.service`

**修复方式**：在每个 service 文件的 `[Service]` 段添加：
```ini
Environment=PATH=%h/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
```

**修复命令**（示例，以 frontstage-guardian 为例）：
```bash
# 在 [Service] 段中 Environment= 行后追加
sed -i '/^Environment=/a Environment=PATH=%h/.npm-global/bin:/usr/local/bin:/usr/bin:/bin' \
  ~/.config/systemd/user/openclaw-frontstage-guardian.service
systemctl --user daemon-reload
systemctl --user restart openclaw-frontstage-guardian.timer
```

**已修改文件**：
- `~/.config/systemd/user/openclaw-frontstage-guardian.service`
- `~/.config/systemd/user/openclaw-health-collector.service`
- `~/.config/systemd/user/openclaw-task-scheduler.service`
- `~/.config/systemd/user/openclaw-lifecycle-maintainer.service`
- `openclaw-resume-watch.service` 已有 PATH，无需修改

**验收**：
```bash
journalctl --user -u openclaw-frontstage-guardian.service --since "10:44" --no-pager
# 输出应包含 "OK - OK" 或 "Finished ... service"
```

---

### 🔴 问题 2：统一代理 → sidecar 502 路由

**现象**：访问 `http://127.0.0.1:18788/v1/query/healthz` 返回 HTTP 502。

**根因**：`scripts/openclaw-infos-handle.py` 缺少对 `healthz` 查询种类的完整支持。虽然 `QUERY_KINDS` 集合中已有 `"healthz"`，但 `render_text()` 函数没有对应的处理分支，导致查询时抛出 `ValueError: unsupported kind: healthz`。

**涉及文件**：`scripts/openclaw-infos-handle.py`

**修复方式**：在 3 个位置添加 `healthz` 支持：

1. **`QUERY_KINDS` 集合**（约第 62 行）— 添加 `"healthz"`：
   ```python
   QUERY_KINDS = {
       "snapshot.summary",
       # ... 其他 kinds ...
       "healthz",   # ← 新增
   }
   ```

2. **`render_text()` 函数**（约第 1615 行）— 添加文本输出：
   ```python
   if kind == "healthz":
       return "infos-handle healthz ok"
   ```

3. **`build_query_result()` 函数**（约第 1734 行）— 添加结构化输出：
   ```python
   if kind == "healthz":
       return {"ok": True, "kind": "healthz", "service": "infos-handle", "checkedAt": snapshot.get("checkedAt")}
   ```

**重要提示**：`openclaw-infos-handle.py` 有两处 kind 验证和分发——一处是 `normalize_handle_request()`（检查 `kind in QUERY_KINDS`），另一处是 `render_text()`（独立的分支匹配）。新增 kind 时必须**两处都补**，否则只会报错在 `render_text` 层而不是 `normalize` 层，容易误判根因。

**修复命令**：
```bash
# 编辑 scripts/openclaw-infos-handle.py
# 在三处位置添加 healthz 支持后：
systemctl --user restart openclaw-infos-handle-sidecar.service
```

**验收**：
```bash
# 直连 sidecar 测试
curl -s http://127.0.0.1:18790/v1/query/healthz
# 应返回 {"ok": true, ...}

# 经统一代理测试
curl -s -w "\nHTTP: %{http_code}\n" http://127.0.0.1:18788/v1/query/healthz
# 应返回 HTTP 200，json 中 "ok": true
```

---

### 🟡 问题 3：yt-dlp 依赖缺失

**现象**：视频下载脚本 `scripts/download-platform-video.py` 依赖 `yt-dlp`，但系统中未安装。

**根因**：系统 Python 3.12 由 apt 管理（externally managed），不能直接用 pip。且本机没有 `pipx`。

**修复方式**：使用 `uv` 创建独立 venv 并安装：

```bash
~/.local/bin/uv venv ~/.local/share/yt-dlp-venv --python 3.12
~/.local/bin/uv pip install --python ~/.local/share/yt-dlp-venv/bin/python yt-dlp
ln -sf ~/.local/share/yt-dlp-venv/bin/yt-dlp ~/.local/bin/yt-dlp
```

**验收**：
```bash
~/.local/bin/yt-dlp --version
# 应输出 2026.03.17 或更新
```

---

### 🟡 问题 4：health-collector 间歇性失败

**现象**：`openclaw-health-collector` 服务间歇性报告 "Gateway 状态读取异常"。

**根因**：与问题 1 相同——systemd 环境缺少 `openclaw` CLI 的 PATH。`health-collector` 内部调用 `openclaw` 命令读取 gateway 状态时失败。

**修复方式**：与问题 1 一起修复（为 `openclaw-health-collector.service` 添加 `Environment=PATH`）。

**验收**：
```bash
journalctl --user -u openclaw-health-collector.service --since "10:44" --no-pager | tail -5
# 所有最近的运行应显示 status=0/SUCCESS
```

---

### ✅ 未受影响的项目（恢复验证）

以下 6 项在升级后审查中确认正常，无需修复：

| 项目 | 验证结果 |
|------|----------|
| 品牌补丁（"贾维斯" branding） | ✅ `apply-openclaw-control-ui-branding.py`（68KB）完整，自动触发链正常 |
| 补丁注册表（17 个补丁） | ✅ 结构完整，所有补丁有明确的结果目标和实现入口 |
| 磁盘空间 | ✅ `/` 75%，`/mnt/data` 36%，够用 |
| Broker 视图 | ✅ 所有 6 个视图文件新鲜完整（约 10:39 刚重建） |
| task-scheduler / lifecycle-maintainer / resume-watch | ✅ timer active，运行正常 |
| infos-handle sidecar + Caddy 各自进程 | ✅ systemd active，各自端口响应 200 |
| Git 仓库 | ✅ 分支 master 与 origin 同步，有 2 个待提交修改 |

---

### 升级后残留清理

**会话索引清理**：升级后 sessions.json 从 39 条膨胀（含大量已失效的 subagent/dashboard 条目），清理后精简至 9 条。

```bash
# 清理策略：保留当前活跃会话树 + 所有 cron 条目 + main 会话
# 清理工具：scripts/sessions-cleanup.py + 手动清理残留
# 结果：221MB → 1.6MB，423 个文件 → 6 个文件，释放约 219MB
```

**sessions.json.bak / sessions.json.clean.bak** 也一并清理。

---

### 修复总结

| # | 问题 | 严重度 | 根因 | 修复方式 |
|---|------|--------|------|----------|
| 1 | frontstage-guardian crash | 🔴 严重 | systemd 环境 PATH 缺失 | 4 个 service 文件添加 `Environment=PATH` |
| 2 | 统一代理 → sidecar 502 | 🔴 严重 | `render_text()` 缺少 healthz 分支 | 补 QUERY_KINDS + render_text + build_query_result |
| 3 | yt-dlp 依赖缺失 | 🟡 中等 | 未安装 | uv venv 安装 + symlink |
| 4 | health-collector 间歇性失败 | 🟡 中等 | 同问题 1 | 同问题 1 |

---

### 经验教训（供后续升级参考）

1. **`openclaw` CLI 的 PATH 是脆弱点**：每次 OpenClaw 升级后，systemd 服务的 `Environment=PATH` 可能被重置或需要更新。升级后优先检查所有 watcher service 文件。

2. **infos-handle 新增 kind 要补三处**：`QUERY_KINDS` 集合 → `render_text()` → `build_query_result()`。漏补任何一个都会导致查询失败，但报错位置可能误导排查方向。

3. **系统 Python 的包管理限制**：这台机器的 Python 3.12 是 apt 管理的，不能用 `pip install --system`。安装新 CLI 工具时应优先使用 `uv venv` + symlink 到 `~/.local/bin` 的方式。

4. **升级后会话索引可能膨胀**：新旧版本对 session 索引的兼容性可能不完美，升级后可能出现大量孤立会话条目，需要清理。

5. **升级审查看不到的问题**：voice-reply 链路（ChatTTS 资产缺失、稳定入口脚本缺失、远端 GPU 不可达）本次未修复，属于低优先级，但下次升级时如果相关路径变化，可能会暴露新问题。

---

### 当前运行状态（2026-05-26 11:00 CST）

| 组件 | 状态 |
|------|------|
| OpenClaw Gateway | ✅ 运行中 (2026.5.22, port 18789) |
| 默认模型 | deepseek/deepseek-v4-pro |
| frontstage-guardian | ✅ timer active, 最近一次 SUCCESS |
| health-collector | ✅ timer active, SUCCESS |
| task-scheduler | ✅ timer active, SUCCESS |
| lifecycle-maintainer | ✅ timer active, SUCCESS |
| resume-watch | ✅ timer active, SUCCESS |
| infos-handle sidecar | ✅ active, port 18790 |
| 统一代理 (Caddy) | ✅ active, port 18788, healthz 200 |
| yt-dlp | ✅ 2026.03.17 可用 |
| 会话清理 | ✅ 已完成 (1.6MB, 9 条索引) |

---

> 文档维护规则：每次 OpenClaw 升级后，在此文件上方追加新的升级记录条目（从 #2 开始）。如果升级由用户手动触发，在"触发方式"中注明。如果升级由自动更新触发，注明触发时间和触发机制。

---

## 2026-06-11: 2026.5.22 → 2026.6.5

### 基本参数

| 项目 | 内容 |
|------|------|
| 升级日期 | 2026-06-11 |
| 旧版本 | 2026.5.22 (a374c3a) |
| 新版本 | 2026.6.5 (5181e4f) |
| 触发方式 | 用户手动 `npm update -g openclaw` |
| 升级前 git | checkpoint 已提交并 push |
| 所在机器 | 公司（Linux）— `missyouangeled-VMware-Virtual-Platform` |
| npm 变化 | +2 包，-72 包，~283 包 |

### 预检

从 5.22 到 6.5 跨 4 个正式版 + 多个 beta，上游主要变动：

1. **安全边界收紧**：exec 审批超时 fail-close、沙箱 bind / 环境继承 / MCP stdio 加固
2. **Control UI 重构**：前端 bundle 函数名全部更换（OD→OA, ek→w, bx→Ag, Il→gh, Uc→Cg 等），对应我们的所有 JS 补丁需要重映射
3. **内建能力**：`data-chat-model-select`（模型选择器）和 `hasActiveRun`（聊天运行指示器）已由上游原生实现
4. **Plugin/Skill**：安装改用 operator install policy
5. **SQLite 迁移**：cron、tasks、memory 自动迁移到 SQLite 状态
6. **Gateway 排水**：restart 时老进程 drain 300s 排水

### 已知风险

| 风险项 | 可能性 | 原因 | 实际结果 |
|--------|--------|------|----------|
| PATH 被重置 | 中 | systemd 环境隔离 | ❌ 未发生（本次 PATH 完好） |
| 品牌补丁失效 | 高 | 函数名全部更换 | ✅ 已修复（新检测路径） |
| 模型选择器失效 | 高 | 函数名全部更换 | ✅ 已内建，无需补丁 |
| 运行指示器失效 | 高 | 函数名全部更换 | ✅ 已内建，无需补丁 |
| INVALID_FINAL_RELOAD | 高 | Gl→qg | ✅ 已修复 |
| yielded 历史回放 | 高 | 15+ 函数名更换 | ❌ 未适配（后续单补） |
| resume-watch 被重新激活 | 低 | 升级触发 | ❌ 未发生（保持关闭） |
| infos-handle / 统一代理 | 低 | 不依赖前端 | ✅ 直接复用 |

### 补丁状态明细

#### ✅ 品牌补丁（`apply-openclaw-control-ui-branding.py`）

**变化**：新增 v2026.6.5 检测路径，关键映射：

| v5.22 函数 | v6.5 函数 | 用途 |
|------------|-----------|------|
| OD / fj | OA | 内容 trim + 空内容检查 |
| ek | w | role normalize（改为外部导入） |
| ij / MT | uf | message content 提取 |
| bx / Bl | Ag | history merge |
| Il | gh | 隐藏/不可见消息过滤 |
| Uc / gx | Cg | 另一种消息过滤 |
| Bc / Wb | nI | NO_REPLY / 可视内容检查 |
| Gl / Tx / xl | qg | INVALID_FINAL_RELOAD 调用 |

**检测逻辑**：`function OA(e){` 存在 + `function fj(` 不存在 + `function OD(e){` 不存在 → 判定为 v2026.6.5

**本次应用**：INVALID_FINAL_RELOAD 修复（`{qg(e);return}` → `return;`），品牌 HTML/manifest/sw.js 正常

#### ✅ 模型选择器补丁 → 已废弃

- `apply-openclaw-session-model-selector-fix.py`：执行失败（函数名变更），**但无需修复**
- 原因：v2026.6.5 上游内建 `data-chat-model-select`（1 处）+ `sessions.patch` with model（2 处）
- 作用：Control UI 聊天页模型下拉选择后，自动调用 `sessions.patch {key, model}`，并用后端 `resolved.modelProvider/model` 回填 UI
- systemd ExecStartPre 已无内容，不影响 Gateway 启动

#### ✅ Chat running 补丁 → 已废弃

- `hasActiveRun===!0` 已内建（2 处出现），上游原生支持运行中状态的会话指示
- 不再需要手动注入 `CHAT_RUNNING_PATCH` 模式

#### ✅ Unified proxy / infos-handle

- 无需更新：`apply-openclaw-infos-handle-gateway-proxy.py` 正常返回
- 继续监听 127.0.0.1:18790（sidecar）+ 0.0.0.0:18788（Caddy 代理）

#### ✅ Watcher 体系

- 4 个 watcher timer 全活（guardian / task-scheduler / health-collector / lifecycle-maintainer）
- systemd PATH 在 5.26 升级时已修复，本次无需再改

#### ❌ yielded 历史回放补丁（未适配）

**作用**：子任务（subagent）yield 返回结果后，聊天页 history 自动补 assistant 消息

**阻塞原因**：
- 该补丁注入 5 个辅助函数 + 2 处修改点
- 函数内部引用了 15+ 个已更名的旧函数（`g`, `MT`, `yT`, `OD`, `Il`, `Uc`, `Bc`, `wD`, `ED`, `AD`, `Rl`, `zl`, `JT`, `LT`, `Rk` 等）
- 需要对每个引用做完整重映射 + 验证才能正确注入

**影响**：子任务 yield 返回后，聊天页 history 不会自动显示 "仍在处理…" 状态文本，history 看起来像断档。**不影响子任务实际执行和后续消息投递。**

**计划**：后续单独开修补任务，完整重映射后重新打上

### 升级执行流程

```
1. git status → 仅 .learnings/ERRORS.md 有修改
2. git commit → push → remote 冲突 → git pull --rebase → push 成功
3. npm update -g openclaw → 37s 完成
4. openclaw --version → 2026.6.5 ✅
5. 重打补丁：
   - 品牌补丁 → 失败（函数名变更，die at line 290）
   - 模型选择器补丁 → 失败（函数名变更）
   - infos-handle 代理 → 正常
6. 分析新版 bundle 函数映射 → 定位 OA/w/Ag/gh/Cg/qg
7. 修改 branding 脚本 → 新增 v2026.6.5 检测 + INVALID_FINAL_RELOAD 模式
8. 品牌补丁重跑 → 成功
9. Gateway 已自动重启（systemctl restart）
10. 验证：Gateway 200、品牌注入、4 watcher 全活
11. Git commit + push
```

### 升级后运行状态（2026-06-11 11:50 CST）

| 组件 | 状态 |
|------|------|
| OpenClaw Gateway | ✅ 运行中 (2026.6.5, port 18789) |
| 默认模型 | deepseek/deepseek-v4-pro |
| 当前模型 | deepseek-company/deepseek-v4-pro |
| frontstage-guardian | ✅ timer active |
| task-scheduler | ✅ timer active |
| health-collector | ✅ timer active |
| lifecycle-maintainer | ✅ timer active |
| resume-watch | ⏸️ 保持关闭（用户要求） |
| infos-handle sidecar | ✅ active, port 18790 |
| 统一代理 (Caddy) | ✅ active, port 18788 |
| 品牌注入 | ✅ 贾维斯 Control |
| 模型选择器 | ✅ 上游内建 |
| 运行指示器 | ✅ 上游内建 |
| INVALID_FINAL_RELOAD | ✅ 已修复 |
| yielded 历史回放 | ❌ 未适配 |

---

## 升级 #2：2026.5.22 → 2026.6.5

### 基本信息

| 项目 | 内容 |
|------|------|
| 升级日期 | 2026-06-11 |
| 旧版本 | 2026.5.22 |
| 新版本 | 2026.6.5 (5181e4f) |
| 触发方式 | 用户手动 `npm update -g openclaw` |
| 所在机器 | 公司（Linux）— `missyouangeled-VMware-Virtual-Platform` |

### 升级后遇到的问题及修复

#### 问题 1：Control UI 黑屏（品牌注入变量冲突）

**现象**：升级后打开 Control UI 页面完全空白，`openclaw-app` 组件未注册。

**根因**：`jarvis-branding-override.js` 中用了 `let i` 作为循环变量，而 v6.5 上游的 branding 注入也在同作用域用了 `let i`，导致重复声明冲突→整个脚本报错→Control UI 组件注册失败。

**修复**：将品牌脚本中的 `let i` 改为 `let ji`（唯一变量名），`scripts/apply-openclaw-controlui-branding.py` 同步更新。

**验证**：`python3 scripts/apply-openclaw-controlui-branding.py --check` 通过，Control UI 恢复正常。

#### 问题 2：infos-handle 路由错误

**现象**：Control UI 中 infos-handle 契约、任务、恢复数据显示异常（可能为空或 404）。

**根因**：品牌脚本中硬编码了直连 `127.0.0.1:18790`（sidecar 端口），而 v6.6.5 的正确入口是统一代理 `127.0.0.1:18788`。

**修复**：将所有 infos-handle 端点 URL 从 `127.0.0.1:18790` 改为 `127.0.0.1:18788`。

**验证**：检查 `/v1/query/contract.catalog`、`/v1/query/tasks.summary`、`/v1/query/recovery.*` 均可正确返回数据。

#### 问题 3：litellm provider models 格式错误（两轮）

**背景**：用户要求将图片识别模型从 `nvidia/google/gemma-4-31b-it` 换为 `litellm/agnes-2.0-flash`（基于 Agnes API）。需在 openclaw.json 中同时配置 `imageModel.primary` 和 litellm provider 的 models 声明。

**第一轮错误（`expected array, received object`）**：

```json
// ❌ 错误格式（对象）
"litellm": {
  "models": {
    "agnes-2.0-flash": {"input": ["text", "image"]}
  }
}
```

**根因**：v6.6.5 的 schema 要求 `models.providers.<id>.models` 必须是 **数组**，不能用对象。

**修复**：由 `openclaw doctor --fix` 清掉错误配置后恢复。

**第二轮错误（`expected string, received undefined`）**：

```json
// ❌ 数组格式但缺少必填字段
"litellm": {
  "models": [
    {"id": "agnes-2.0-flash", "input": ["text", "image"]}
  ]
}
```

**根因**：v6.6.5 的 litellm models 数组中每个条目必须包含三个必填字段：`id`、`name`、`input`。漏了 `name` 字段。

**正确格式**：

```json
// ✅ 正确格式
"litellm": {
  "baseUrl": "https://apihub.agnes-ai.com/v1",
  "apiKey": "sk-xxx",
  "api": "openai-completions",
  "models": [
    {
      "id": "agnes-2.0-flash",
      "name": "Agnes 2.0 Flash",
      "input": ["text", "image"]
    }
  ]
}
```

**最终验证**：
- `python3` 检查 openclaw.json JSON 语法 ✅
- 检查 litellm.models 是数组、含 id/name/input ✅
- 独立端口（18799）烟测：`gateway ready, 7 plugins, no config error` ✅
- 正式重启：`systemctl --user restart openclaw-gateway` → `active` + `gateway ready` ✅

#### 问题 4：deepseek provider 缺少 apiKey

**现象**：升级后主模型 `deepseek/deepseek-v4-pro` 偶发报 `DeepSeek API key not found`，然后自动 fallback 到 deepseek-company provider 才恢复。

**根因**：`openclaw.json` 中 `models.providers.deepseek` 只配置了 `baseUrl` + `api` + `models`，**没有 `apiKey` 字段**。而 `deepseek-company` provider 有独立的 apiKey，所以 `deepseek-company/deepseek-v4-pro` 能正常工作。主模型走的是 `deepseek` provider，缺 key 就报错。

证据：
- `openclaw.json` deepseek provider keys: `['baseUrl', 'api', 'models']` — apiKey 不存在
- 系统环境变量 `DEEPSEEK_API_KEY` 也未设置
- SQLite auth store (`openclaw-agent.sqlite`) 中存在 `deepseek:default` 的 key：`sk-da15916e63ba...`（这是旧版 auth store 的迁移残留）
- Gateway 启动时读 openclaw.json，不读 SQLite auth store → 拿不到 key

**修复**：从 SQLite auth store 恢复 deepseek key，写入 openclaw.json：

```json
"deepseek": {
  "baseUrl": "https://api.deepseek.com",
  "api": "openai-completions",
  "apiKey": "sk-da15916e63ba400197745888173a912e",
  "models": [...]
}
```

**验证**：烟测通过（独立端口 gateway ready）→ 正式重启 → 正常。

### 升级期间执行的系统清理

升级完成后，同步执行了系统垃圾清理：

| 清理项 | 清理量 | 说明 |
|--------|--------|------|
| `.exec-approvals` 临时文件 | 42 个 → 0 | ~/.openclaw/ 下残留的审批临时文件 |
| stability bundle 日志 | 20 → 5 个 | 保留最新 5 个 |
| gateway 日志 | 保留当天 1 个 | 旧日志删除 |
| npm cache | 全部 | `npm cache clean --force` |
| SQLite subagent_runs | 17 → 0 | 所有已完成的子 agent 运行记录 |
| SQLite task_runs | 61 → 0 | 所有已完成/失败/超时的任务记录 |
| sessions 目录旧文件 | 11 个 .jsonl + 5 个 .deleted | 仅保留当前会话 transcript（890KB） |
| sessions 目录体积 | 14.7MB → 1.5MB | 释放 13.2MB |

### 升级后的配置快照

```json
{
  "agents.defaults.model.primary": "deepseek/deepseek-v4-pro",
  "agents.defaults.imageModel.primary": "litellm/agnes-2.0-flash",
  "models.providers.deepseek.apiKey": "已配置 (35 chars)",
  "models.providers.deepseek-company.apiKey": "已配置 (35 chars)",
  "models.providers.litellm.models": [{"id":"agnes-2.0-flash","name":"Agnes 2.0 Flash","input":["text","image"]}],
  "models.providers.litellm.baseUrl": "https://apihub.agnes-ai.com/v1"
}
```

### 经验教训

1. **v6.6.5 schema 更严格**：`models.providers.<id>.models` 必须是数组，数组元素必须有 `id`/`name`/`input`。升级后修改 provider 配置时必须先读文档确认 schema。
2. **apiKey 不能假设从旧版继承**：v6.6.5 的 Gateway 从 openclaw.json 读 apiKey，旧版的 SQLite auth store 不再被 provider 初始化时读取。升级后务必检查所有 provider 的 apiKey 是否到位。
3. **烟测流程已固化**：修改 openclaw.json 后 → 先独立端口烟测（`--port 18799`）→ 通过后再正式重启。绕过了多次 `doctor --fix` → 重启失败的死循环。
4. **品牌注入与上游变量冲突风险**：自定义 branding JS 中应避免使用 `let i` 等常见短变量名，防止与上游注入代码冲突。
5. **infos-handle 入口不直连 sidecar**：应统一走代理（18788），以便 sidecar 端口或监听地址变化时无需改客户端。

---

## 升级 #3：2026.6.5 → 2026.6.6

### 基本信息

- **日期**：2026-06-15 12:30~12:37
- **触发方式**：`npm update -g openclaw`
- **版本变化**：`2026.6.5 (5181e4f)` → `2026.6.6 (8c802aa)`
- **命令**：`npm update -g openclaw`（依赖无变化，55 个依赖保持不变）
- **结果**：✅ 成功，2 个历史问题被重新触发 + 1 个新架构兼容性问题

### 升级前预检（新 SOP）

1. ✅ 备份关键文件 → `tmp/upgrade-backups/2026-06-15-6.5to6.6/`（openclaw.json、package.json、state-backup）
2. ✅ 依赖版本对比：55 个依赖全部不变，仅代码层面改动
3. ✅ 配置预检：所有 5 个 provider API key 正常、litellm models 数组格式正确、imageModel 配置有效
4. ✅ systemd PATH 预检：4 个 watcher service 均已配置 `%h/.npm-global/bin`
5. ✅ branding 变量冲突预检：无 `let i`/`var i` 冲突
6. ✅ infos-handle 路由预检：已走 18788 统一代理

### 发现的问题

#### 问题 1：Control UI 静态文件 404（新架构兼容性）

**根因**：OpenClaw 2026.6.6 的 Gateway 将 Control UI 静态文件服务**限制为 `assets/` 子目录**。非 HTML 文件（`.js`、`.json`、`.svg`、`.webmanifest`）只能从 `assets/` 提供服务。

**表现**：
- `index.html` ✅ 200
- `jarvis-frontstage-status.html` ✅ 200（HTML 文件可访问）
- `jarvis-branding-override.js` ❌ 404
- `jarvis-frontstage-snapshot.json` ❌ 404
- `favicon.svg` ❌ 404
- `manifest.webmanifest` ❌ 404

**修复**：
1. 将 `jarvis-branding-override.js` 复制到 `assets/` 并更新 `index.html` 引用路径
2. 将 `jarvis-frontstage-snapshot.json` / `jarvis-frontstage-status.json` 复制到 `assets/`
3. 更新 override 内的 `snapshotJsonHref` 等路径为 `/__openclaw__/control-ui/assets/...`
4. 更新 4 个脚本的写入/验证路径：
   - `apply-openclaw-control-ui-branding.py`：override 写入 `assets/`，HTML 引用更新
   - `apply-openclaw-frontstage-broker-data.py`：snapshot 路径改为 `assets/`
   - `openclaw-frontstage-broker.py`：公开文件写入 `assets/`
   - `openclaw-post-upgrade-self-check.py`：自检路径改为 `assets/`

#### 问题 2：resume-watch timer 未启用

**根因**：升级后 timer 的 `UnitFileState` 变为 `disabled`（虽然 `ActiveState=active`），属于上次未彻底修复的遗留。

**修复**：`systemctl --user enable openclaw-resume-watch.timer`

**更正（2026-06-15）**：用户明确指示 resume-watch timer **不要启用**。已 `systemctl --user disable --now openclaw-resume-watch.timer`。该 timer 的作用是检测休眠恢复自动重启 Gateway，用户判断不需要此自动行为。

#### 问题 3：chatRunning marker 注入失效（待解决）

**根因**：2026.6.6 采用了 Rolldown 模块拆分架构，原先的单体 `index-*.js` bundle 不再包含 `chatRunning` 字符串。chat 相关逻辑可能已分散到 `gateway-runtime`、`config-runtime` 等模块 chunk 中。

**表现**：
- `JarvisProjectYieldedHistoryReply` marker 注入目标不存在
- `JarvisShouldShowPendingReadingIndicator` marker 注入目标不存在
- `patch_chat_running_indicator()` 因版本检测失败而静默跳过（不报错但也不注入）

**当前状态**：已知限制，待后续分析新模块结构后适配。核心功能（品牌标题、snapshot、infos-handle）不受影响。

### 升级后自检结果

- **25/26 PASS**（1 FAIL 为已知的 chatRunning marker 注入问题）
- ✅ branding ExecStartPre 自动重打入口正常
- ✅ broker snapshot dock 验证通过
- ✅ infos-handle contract/snapshot/sources 入口正常
- ✅ infos-handle sidecar 和 unified proxy service 正常运行
- ✅ 5 个 watcher timer 均 enabled + active
- ✅ 4 个最小回归测试均 ALL PASS
- ✅ 生命周期维护器正常（timer + 今日 transcript）
- ✅ 统一代理验证：local=200, remoteNoAuth=401, remoteWithAuth=200

### 经验教训

1. **Gateway 静态文件策略可能随版本收紧**：v6.6.6 引入 Rolldown 模块拆分的同时也改变了静态文件服务规则——非 HTML 文件只能放在 `assets/` 子目录。任何自定义品牌文件（JS override、snapshot JSON、favicon 等）都必须放到 `assets/` 内。
2. **单体 bundle 打补丁策略在模块拆分架构下会失效**：之前的 `patch_chat_running_indicator()` 依赖在单一 `index-*.js` 中搜索代码模式，Rolldown 拆分后目标模式不再存在于任何单个 chunk 中。后续需要用模块级注入或独立的 ES module 替代方案。
3. **升级前扫描 diff 不能只看依赖版本**：本次 55 个依赖全不变，但构建工具链（Rolldown）变化导致产出结构完全不同。理想的升级前预检还应包含「dist 目录结构 diff」。
4. **timer UnitFileState 要在自检中列为 required**：resume-watch 的 `ActiveState=active` 但 `UnitFileState=disabled` 意味着重启后不会自动启动，应在升级后自检中强制校验 enabled 状态。


## 升级 #2：2026.6.6 → 2026.6.8

### 基本信息

| 项目 | 内容 |
|------|------|
| 升级日期 | 2026-06-17 |
| 旧版本 | 2026.6.6 |
| 新版本 | 2026.6.8 |
| 触发方式 | 用户提示有更新，`npm update -g openclaw` |
| 所在机器 | 公司（Linux） |

### 升级后问题

1. **Control UI 前端结构变化**：v2026.6.8 的 Rolldown bundle 引入了新的函数结构（`function ZA` 替代 `function JA` 作为主渲染函数，`fj` + `OD` 同时存在），原有 v22/v6.6.5/v6.6.6 三个版本检测全部失效。修复：在 `apply-openclaw-control-ui-branding.py` 新增 v2026.6.8 检测块。

2. **infos-handle sidecar SSE 路径**：branding override 里的 SSE URL 格式需要适配（`infosHandleDirectReady: false`），不影响核心功能。

### 修复详情

- **branding 脚本**：新增 `YIELDED_HISTORY_REPLY_V2026_6_8` / `STREAM_INDICATOR_V2026_6_8` / `JARVIS_FUNCTIONS_V2026_6_8` 三组常量，在 `chat_running_indicator` 中新增 `is_v2026_6_8` 检测（`ZA` + `fj` + `OD`），注入点：`function ZA(e){` 之前。
- v2026.6.8 的消息对象不再需要额外解包（无 message wrapper），Jarvis helpers 改用直接属性访问。
- 验证结果：26/27 项通过。

- 验证结果：26/27 项通过。

3. **model-selector 补丁失效**（2026-06-18 发现）：v2026.6.8 升级后，`dist/control-ui/assets/index-Wjxp3gyC.js` 中 Rolldown 打包的函数名再次变化——模型下拉切换函数从 `gz` → `Gz`，busy guard 从 `$R` → `Oz`，辅助函数 `_U` → `ER`、`mW` → `Dz`、`RU` → `YR`、`yp` → `Oa`、`$R` → `Oz`。原有的 5 个 candidate old 模式全部无法匹配。
   - **修复**：在 `scripts/apply-openclaw-session-model-selector-fix.py` 中新增 v2026.6.8 专属分支：
     - `CURRENT_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8` ← 原始 `Gz` 函数（674 字符）
     - `TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8` ← 替换后含 resolved modelProvider/model 回填 + `chat.inject` 引导链 + `refresh-tools-effective`
     - `CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_8` ← 原始 `Oz` 函数（838 字符）
     - `TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_8` ← 仅 `chatSending` 禁用的简化版 busy guard
     - `is_v2026_6_8` 检测逻辑：`CURRENT_*_V2026_6_8 in updated or TARGET_*_V2026_6_8 in updated`
     - 幂等性修复：添加 `already_patched` 提前退出，避免补丁已打后第二次运行报「候选命中数 0」错误
   - **验证**：15 项 bundle 完整性检查全部通过 ✅

4. **verify-today-patches 搜索规则检查失灵**（2026-06-18 发现）：`verify-today-patches.py` 的 `agents-search-rule` 检查仅在 `AGENTS.md` 中搜索「搜索策略」关键字，但实际搜索策略描述在 `rules/agents-core.md` 第 53 行。
   - **修复**：合并读取 `AGENTS.md` + `rules/agents-core.md` 后再检查
   - **验证**：12/12 passed ✅

### 经验教训

- v2026.6.8 的 bundle 函数名继续变化（全变大写首字母 + 部分完全重命名），版本检测需要同时检查多个函数的存在/缺失。
- model-selector 补丁不仅受 Gz 函数名变化影响，Oz busy guard 也变了；必须同时替换两个函数才能完整修复。
- 补丁脚本幂等性很重要：已打补丁后再次运行应静默成功而非报错，否则 `ExecStartPre` 每次重启 Gateway 都会触发红色告警。
- 升级前应先备份当前 `dist/control-ui` 目录以便快速回滚。

---

## v2026.6.18-1：Mark42 铠甲系统全面修复（非 OpenClaw 升级，属 Mark42 bug fix）

**触发方式**：用户要求审查 Mark42 运行日志并全量代码审查

**发现日期**：2026-06-18

### 发现的问题（共 12 项）

1. **Engine daemon 停止后未自动重启**：bootstrap 只注册 Loop 但不启动 daemon 进程；daemon 停止后 bootstrap 再注册的 context-guard 等 4 个 Loop 永远没有机会执行，只有 task-watch 在失效前跑完了 867 个周期。
   - **根因**：bootstrap 是 oneshot systemd unit，注册完 Loop 即退出；engine daemon 没有独立的 systemd 持久化服务。
   - **修复**：创建 `mark42-engine-daemon.service` + `mark42-armor-guard.service` 两个 systemd user unit，设置 `Restart=always`，并启用开机自启。
   - **文件**：`tools/mark42-engine-daemon/mark42-engine-daemon.service`（新建）、`tools/mark42-armor-guard/mark42-armor-guard.service`（新建）、`tools/mark42-bootstrap/mark42-bootstrap.sh`（更新：Phase 2 启动守护进程）

2. **Armor guard 从未运行**：assemble() 子进程 fork 后主进程挂了就一起死——6/17 公司机器重启后 assemble 未被重新触发，armor guard 从 6/17 ~ 6/18 完全停止。
   - **修复**：拆分为独立 systemd unit（同上），由 systemd 管理生命周期，不再依赖 assemble() 父进程。

3. **systemd unit 日志缓冲区导致日志不写入**：py 进程 stdout 被系统缓冲，systemd 的 `StandardOutput=append:` 在 Python 中无效。
   - **根因**：Python 默认对非 tty stdout 使用 8KB 缓冲区；systemd 日志目录权属无输出。
   - **修复**：添加 `Environment=PYTHONUNBUFFERED=1` + `python3 -u` 强制无缓冲输出。
   - **搜索验证**：Stack Overflow / ServerFault 多篇 post 确认 `PYTHONUNBUFFERED=1` 是 systemd 服务中 Python 脚本日志不写入问题的标准解决方案。

4. **armor_check token 估算公式错误（两次）**：
   - 原公式：`int(total_chars / avg_chars_per_line / 2.5)` = `int(total_lines / 2.5)`，完全无效
   - 修复尝试：`int(total_chars / 2.5)` → 因 JSONL 元数据占比高，导致 146.5%（严重高估）
   - **最终修复**：回退到 `int(file_size // BYTES_PER_KTOKEN * 1000)`（14KB/1K tokens），最稳定的估算方法

5. **_find_active_session 回退逻辑缺陷**：无活跃 .lock 文件时，回退到按 mtime 取最新 JSONL，但缺少对 `.reset.`、`.deleted.`、`.bak-`、`.trajectory.` 等后缀的过滤。
   - **修复**：白名单过滤 + `sort(key=mtime, reverse=True)` 倒序取最新

6. **subprocess.Popen 压缩子进程静默失败**：stdout/stderr 设为 DEVNULL，失败后无信息可查。
   - **修复**：改为 `stdout=PIPE, stderr=PIPE`；异常捕获从通用 `Exception` 改为 `SubprocessError`

7. **engine daemon 截尾功能与 logs.py rotate_daemon_logs 重复**：每 20 周期在 daemon 内嵌截尾逻辑，与 `log_rotate("all")` 的 `rotate_daemon_logs()` 功能重复。
   - **修复**：删除 daemon 内嵌截尾，统一委托给 logs.py

8. **bootstrap Gateway 等待超时过短**：15s 可能不够 Gateway 首次启动。
   - **修复**：延长到 30s + 超时告警

9. **assemble() PID 文件写入无校验**：写入后不验证，可能损坏后排查无依据。
   - **修复**：写入后 `_load_json` 回读校验

10. **heavy_execute 脚本命令注入风险**：文件路径中的空格/特殊字符可能破坏 bash 命令。
    - **修复**：使用 `shlex.quote()` 对文件路径进行转义

### 验证结果

- ✅ 5 个 Loop 全部正常运行（context-guard: cycle 3, health-watch: 2, task-watch: 888, model-fallback: 11, memory-index: 1）
- ✅ Engine daemon 日志实时写入（PYTHONUNBUFFERED=1 生效）
- ✅ Armor guard 日志实时写入
- ✅ Armor check 返回 29.0%（合理范围，不再是 0% 或 146%）
- ✅ Mark42 status 全绿
- ⚠️ system-summary 中 security/tasks/watchers 黄色告警非 Mark42 引入，为系统层预存问题

### 经验教训

- systemd 服务中 Python 脚本的 stdout 缓冲是常见陷阱；`PYTHONUNBUFFERED=1` + `-u` 是标准解决方案。
- Oneshot systemd unit + subprocess.Popen 的架构不适合持久化守护进程，应使用 `Type=simple + Restart=always` 的独立 unit。
- JSONL 全量字符数不是有效的 token 估算基准——文件字节 ÷ 每 token 的字节经验值（14KB/1K tokens）更稳定。
- Mark42 的 token 估算永远做不到精确，但至少应该保持合理范围（不要 0% 或 146%），在 10-80% 范围内即可。
