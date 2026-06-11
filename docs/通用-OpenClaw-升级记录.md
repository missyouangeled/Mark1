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

### 升级过程
- npm update -g openclaw: 新增2包，删除72包，变更283包
- 升级前 git checkpoint 已提交
- 新 gateway 排水重启（老进程 drain 300s），重启用 `systemctl --user restart`

### 上游变化
- 安全边界收紧：exec 审批超时 fail-close、沙箱 bind/环境继承/MCP stdio 加固
- Plugin/Skill 安装改用 operator install policy
- Agent/Codex runtime 恢复更稳健
- 新增 `data-chat-model-select` 内建模型选择器（不再需要我们的补丁）
- 新增 `hasActiveRun` 内建聊天运行指示器
- SQLite 状态迁移（cron、tasks、memory）

### 补丁适配
- **品牌补丁**: 函数名更新（fj/OD→OA, ek→w, bx→Ag, Il→gh, Uc→Cg, Gl/Tx→qg），新增 v2026.6.5 检测路径
- **INVALID_FINAL_RELOAD**: 函数名 Gl→qg，模式已更新
- **模型选择器补丁**: 上游已内建，跳过
- **Chat running 补丁**: 上游 hasActiveRun 已内建，跳过
- **Resume-watch**: 保持关闭（升级后未重新激活）
- **Unified proxy / infos-handle**: 无需更新，直接复用

### 验证
- Gateway v2026.6.5 正常运行
- Control UI 可访问 (200)
- 品牌注入生效（贾维斯 Control）
- 4 个 watcher timer 全部 active
