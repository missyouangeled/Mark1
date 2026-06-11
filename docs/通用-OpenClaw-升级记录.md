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
