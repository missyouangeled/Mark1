# 公司（Linux）OpenClaw 维护说明

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 文档类型：本机专用说明

## QMD 使用限制（2026-05-29 确定）

- 本机**禁用 QMD 向量搜索**（`qmd vsearch`），原因：无 GPU，vsearch 需加载 1.2GB LLM 做查询扩展，且删除模型后会自动重下。
- 若误运行 `qmd vsearch`，它会自动从 hf-mirror 下载模型→立即中止并清理残留即可。
- 日常 `memory_search` 走 builtin + github-copilot 引擎，与本限制无关。
- QMD BM25 搜索（`qmd search`）可用，但不作为主引擎。

## 用途

这份说明只面向 **公司 Linux 机**，用于说明这台机器上应优先读取的 OpenClaw 维护内容，以及 Linux 环境下应优先更新的脚本和配置。

## 机器识别

当前环境满足以下任一条件时，按 **公司（Linux）** 理解：

- 运行时主机名：`missyouangeled-VMware-Virtual-Platform`
- 系统 hostname / computer name：`missyouangeled-VMware-Virtual-Platform`
- 本地 IPv4（兜底）：`192.168.233.130`

对应默认理解：

- 设备名：`公司 Linux 机`
- 环境标签：`公司`
- 系统 / OS：`Linux`

## 默认优先读取

当 OpenClaw 运行在公司 Linux 机上，并且任务涉及系统维护、OpenClaw 保活、配置同步、脚本修复时，默认优先读取：

1. `HOST_CONTEXT.md`
2. `docs/多机器-读取与更新规则.md`
3. `docs/通用-OpenClaw-补丁注册表.md`
4. `docs/通用-OpenClaw-补丁重建清单.md`（当怀疑补丁因升级失效时）
5. 本文档 `docs/公司-Linux-OpenClaw-维护说明.md`
6. `TOOLS.md` 里与 Linux 相关的条目
7. 相关 broker / patch README（例如 `tools/openclaw-frontstage-broker/README.md`）
8. broker / watcher 的 Linux user systemd 模板与已安装单元
9. Linux 相关脚本 / 配置：
   - `scripts/openclaw-resume-watch.sh`
   - `~/.config/systemd/user/openclaw-resume-watch.service`
   - `~/.config/systemd/user/openclaw-resume-watch.timer`

## Linux 环境下默认优先更新的部分

如果任务只影响公司 Linux 环境，默认优先更新：

- 本文档 `docs/公司-Linux-OpenClaw-维护说明.md`
- Linux 专用脚本（例如 `scripts/openclaw-resume-watch.sh`）
- 所有 gateway restart 必须留证据：至少同步写入 `~/.local/state/openclaw/gateway-restart-audit.jsonl` 或 `~/.openclaw/logs/gateway-restart.log`，能够追溯触发来源、原因、是否因在线连接而跳过
- Linux systemd 用户单元说明
- `TOOLS.md` 中 Linux 相关条目

如果任务会影响所有机器，再同步更新通用规则文档。

## Linux 环境下默认不要误用的部分

在公司 Linux 环境下，以下内容默认只作参考，不应直接执行：

- `掌机（Windows）` 专用脚本
- `.ps1` / `.cmd` 脚本
- Windows Scheduled Task 相关说明
- Windows 桌面快捷入口 / `.lnk` 说明

## 同步更新工作流

当用户说“同步这台机器 / 更新这台机器 / 拉一下最新规则”时，在 **公司（Linux）** 环境下默认理解为：

1. 进入当前 workspace 仓库
2. 执行 `git pull --ff-only`
3. 如果仓库有变化，或用户要求立即生效，则执行 `openclaw gateway restart`

## 当前已知 Linux 维护点

### Control UI 当前会话模型下拉补丁（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-06-01
- 目标：聊天页模型下拉选择哪个模型，当前会话后续回复就使用哪个模型；切换后以前端显示为辅，以 `sessions.patch` 后端 resolved 结果为准。

相关文件：

- 补丁脚本：`scripts/apply-openclaw-session-model-selector-fix.py`
- 当前用户态 systemd drop-in：`~/.config/systemd/user/openclaw-gateway.service.d/model-selector.conf`
- live 前端资产：`~/.npm-global/lib/node_modules/openclaw/dist/control-ui/assets/index-*.js`
- session 工具资产：`~/.npm-global/lib/node_modules/openclaw/dist/session-utils-*.js`

当前自动触发：

- gateway 启动前通过 `ExecStartPre=-/usr/bin/python3 .../apply-openclaw-session-model-selector-fix.py` 自动重打。

当前最小验收：

```bash
python3 scripts/apply-openclaw-session-model-selector-fix.py
openclaw gateway call sessions.patch --timeout 60000 --json --params '{"key":"agent:main:main","model":"github-copilot/gpt-5.5"}'
```

通过时应返回 resolved 为 `github-copilot/gpt-5.5`。补丁脚本会给 `index.html` 主 bundle 引用追加 `?jarvisModelSelector=<mtime>`，绕开 service worker 对 hashed assets 的 cache-first；浏览器端若仍旧显示不变，再做硬刷新 / 清 service worker 缓存。


### 0. 双盘空间预检与落盘规则（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-09
- 背景：当前公司 Linux 机有两块 50G 盘：根盘 `/` 与数据盘 `/mnt/data`。以后凡是下载大文件、解压模型、同步大仓库、生成大体积中间产物，都不要上来就直接写根盘。

当前固定规则：

1. **先预估，再执行**
   - 在下载、解压、模型转换、批量生成音频/视频、缓存大模型、复制大目录前，先估算一次体积。
   - 默认按“**预计大小 × 2**”估算峰值占用，覆盖下载包 + 解压中转 + 临时缓存。

2. **根盘保底空余**
   - 执行后根盘 `/` 剩余空间不应低于 **8G**。
   - 更稳妥的目标是长期尽量保持 **10G** 以上空余。

3. **大于等于 1G 的新增占用默认优先去 `/mnt/data`**
   - 包括但不限于：模型文件、语音/视频素材、研究样本、临时导入包、批量输出目录。
   - 默认 staging 目录：`/mnt/data/openclaw/download-staging/`

4. **只有小而短命的东西才优先放根盘**
   - 例如 `<300M` 的临时脚本输出、很快会删除的小文件、明显依赖固定相对路径的轻量缓存。
   - 但如果根盘本身已紧张，即便是中等体积文件，也应转去 `/mnt/data`。

5. **能用软链接保路径，就不要硬改上层调用路径**
   - 如果某些既有工具已经写死在 `~/.openclaw/workspace/tmp/...`、`~/.cache/...` 这类路径，优先考虑把实际大目录迁到 `/mnt/data/openclaw/...`，再在原处放回 symlink。
   - 这样既能减轻根盘压力，也能尽量避免改动主链路。

已新增辅助脚本：

- `scripts/storage-preflight.sh`

用法示例：

```bash
bash scripts/storage-preflight.sh 1.5G ChatTTS-assets
bash scripts/storage-preflight.sh 800M 临时解压包
```

当前已落地的迁移策略（2026-05-09）：

- `~/.openclaw/workspace/tmp/voice-replies` → 迁到 `/mnt/data/openclaw/workspace-tmp/voice-replies` 后用 symlink 回挂
- `~/.cache/modelscope` → 迁到 `/mnt/data/openclaw/modelscope-cache` 后用 symlink 回挂

### 1. 本地健康诊断层（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-12
- 用途：在不依赖 AI 模型回复的前提下，周期检查本机 OpenClaw 的 gateway、本机外联、以及主线模型 provider 路由可达性，尽量把“为什么这次像死掉了”归类成更具体的原因。

相关文件：

- 诊断脚本：`scripts/openclaw-local-health-diagnose.py`
- README：`tools/openclaw-local-health/README.md`
- service 模板：`tools/openclaw-local-health/openclaw-local-health-watch.service`
- timer 模板：`tools/openclaw-local-health/openclaw-local-health-watch.timer`
- 当前用户态 systemd：`~/.config/systemd/user/openclaw-local-health-watch.service`
- 当前用户态 timer：`~/.config/systemd/user/openclaw-local-health-watch.timer`
- 运行期状态目录：`~/.local/state/openclaw/local-health/`

当前最小检查项：

1. `openclaw status --json` 本地探测
2. Gateway reachability / service runtime 判断
3. 通用外网探测（当前默认：GitHub API、百度首页）
4. `~/.openclaw/openclaw.json` 中主线 provider 的 `baseUrl` 路由探测

当前职责边界：

- 只负责：本地网络、Gateway、主线 provider 路由
- 不负责：页面主会话消息级超时监听
- 页面主会话“长时间没回复”的体感问题，继续交给 `main-supervisor-lite` 负责

当前产物：

- `~/.local/state/openclaw/local-health/last-report.json`
- `~/.local/state/openclaw/local-health/last-summary.txt`
- `~/.local/state/openclaw/local-health/health-diagnostic.log`
- `~/.local/state/openclaw/local-health/host-thermal-bridge.json`（宿主机温度桥接输入，若存在则优先读取）
- `tools/openclaw-local-health/host-thermal-bridge-windows.ps1`（宿主机是 Windows 时的温度采集脚本）
- `tools/openclaw-local-health/install-host-thermal-bridge-task-windows.ps1`（Windows 宿主机计划任务安装脚本）
- `~/.openclaw/canvas/documents/local-health-status/index.html`（固定健康监督页面）

当前稳定性补充：

- 页面会按 `checkedAt` 自动判断数据是否过期：超过约 12 分钟提示“可能过期”，超过约 20 分钟提示“可能已失效”
- 诊断日志会做保守留存：超过约 2MB 时自动裁到最近约 1MB
- `openclaw-local-health-watch.service` 应保留 `SuccessExitStatus=1 2`，避免 systemd 把“告警结果”误判成“脚本执行失败”
- 当前还已接入：`温度` 与 `负载 / 内存` 两条本地诊断维度；其中温度优先尝试读取宿主机桥接 JSON，读不到时再退回当前机器自身传感器
- 若当前是 VMware 客体，脚本也会自动尝试 `/mnt/hgfs/*/host-thermal-bridge.json`；推荐宿主机共享名直接使用 `OpenClawBridge`
- 2026-05-13 当前实测：客体内 `open-vm-tools` / `vmhgfs-fuse` / `vmware-hgfsclient` 已安装且 `open-vm-tools.service` 正常运行，但 `vmware-hgfsclient` 返回空，用户态测试 `vmhgfs-fuse .host:/ <mountpoint>` 返回 `Error -107 cannot open connection!`；这更像宿主机尚未启用/提供共享文件夹，而不是客体缺少 VMware 工具。

当前默认频率：

- 开机后约 2 分钟首次运行
- 之后约每 5 分钟运行一次

说明：

- 这层不是“万能保险”，但只要本机、gateway、本地脚本环境还活着，它就能尽量把故障归类成 gateway、本机外联、或 provider 路由问题。
- 当前主线 provider 会在摘要中标 `*`；非主线 provider 失败只作补充线索，不单独拉高整体告警等级。
- 当前还额外预留了一个未来本地 fallback 模型接口位：诊断输出 JSON 中会带 `fallback` 字段，后续若用户在本机部署了小模型，可再把自动接管逻辑挂到这一层后面。

### 2. 恢复后自愈 watcher

相关脚本：

- `scripts/openclaw-resume-watch.sh`

用途：

- 检测休眠恢复或长时间暂停后，自动重启 `openclaw-gateway.service`

### 3. 前台恢复观察 watcher（broker 第二阶段）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-14
- 用途：周期对比当前前台 dashboard 的 durable transcript 与 `chat.history` 投影，尽早发现“回复 live 里出现过、但最终没稳定留在前台/history”的异常，并把 anomaly / recovered 这些辅助信息统一经由 frontstage broker 回到当前 dashboard。

相关文件：

- 观察脚本：`scripts/openclaw-frontstage-recovery-watch.py`
- README：`tools/openclaw-frontstage-recovery/README.md`
- service 模板：`tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.service`
- timer 模板：`tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.timer`
- 当前用户态 systemd：`~/.config/systemd/user/openclaw-frontstage-recovery-watch.service`
- 当前用户态 timer：`~/.config/systemd/user/openclaw-frontstage-recovery-watch.timer`
- 运行期状态目录：`~/.local/state/openclaw/frontstage-recovery/`

当前产物：

- `~/.local/state/openclaw/frontstage-recovery/last-report.json`
- `~/.local/state/openclaw/frontstage-recovery/notify-state.json`
- `~/.local/state/openclaw/frontstage-recovery/frontstage-recovery-events.log`

当前最小检测项：

1. `assistant_missing_in_history`
2. `history_oversized_placeholder`
3. `assistant_text_mismatch`
4. `assistant_turn_missing_visible_text`（assistant turn 已发生，但最终稳定可见文本为空；当前已用于兜住“边回边消失”的 silent / empty final 情况）
5. `pendingProjection`（仅作缓冲判断，不当成异常；当前既覆盖“history 还在追赶 transcript”，也覆盖目标 dashboard 仍 `hasActiveRun=true` / session 仍 `running` 的进行中窗口，以及 session 刚结束不久、history 仍在最终追赶的短窗口）

当前默认频率：

- 开机后约 60 秒首次运行
- 之后约每 15 秒运行一次

当前 service 模板默认会带上：

```ini
ExecStart=/usr/bin/python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-frontstage-recovery-watch.py --notify-frontstage --print-human
```

含义是：除了持续写本地状态，它也会在 anomaly / recovered 这些变化时，经由 `scripts/openclaw-frontstage-broker.py` 把一句辅助摘要回到当前 dashboard 前台。

当前边界：

- 只做观察 + 辅助回报，不接管正常主回复
- 依赖 Gateway / transcript / `chat.history` / Python / user systemd
- 若更底层整体阻塞，这条链也可能只能留下本地证据，不能保证一定送达前台

2026-05-15 当前又补了一处与监工自动回报直接相关的前台绑定修补：

- `scripts/openclaw-supervisor-subagent.py` 现在在 `requestedSessionKey=agent:main:main` 且同一 owner 下存在 dashboard 前台时，会优先解析到最新 dashboard，而不再因为 `agent:main:main` 的时间戳较新就误回落到 owner 本身
- `scripts/openclaw-supervisor-status.py` 已兼容 broker `emit` 返回顶层 `messageId`，避免 `notify-state.json` / `supervisor-events.log` 把成功注入误记成 `messageId=null`
- 当怀疑 supervisor 仍没真正打到当前页时，优先检查：
  - `python3 scripts/openclaw-supervisor-subagent.py resolve-frontstage --session-key 'agent:main:main' --print-json`
  - `~/.local/state/openclaw/supervisor/supervisor-events.log`
  - 当前 dashboard transcript 里是否实际存在对应 `messageId`
- 2026-05-15 11:08 的真烟测已确认：`notify_sent ... target=agent:main:dashboard:0e238e2b-0e3c-4e63-9c1d-790e3f2794cf messageId=ab0baee2-9cc5-4301-9cee-bcd554d10942`，且该 id 已真实出现在当前 dashboard transcript 中

### 4. broker 周期重建（broker 数据层 1.0）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-14
- 用途：即使当前没有新的辅助消息进入 broker，也定期从 `supervisor / local-health / frontstage-recovery` 的现有状态文件重建 broker 视图，避免 sidecar 数据源长期停留在旧快照。

相关文件：

- broker 脚本：`scripts/openclaw-frontstage-broker.py`
- apply 入口：`scripts/apply-openclaw-frontstage-broker-data.py`
- service 模板：`tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service`
- timer 模板：`tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer`
- 当前用户态 systemd：`~/.config/systemd/user/openclaw-frontstage-broker-rebuild.service`
- 当前用户态 timer：`~/.config/systemd/user/openclaw-frontstage-broker-rebuild.timer`

当前默认频率：

- 开机后约 75 秒首次运行
- 之后约每 60 秒运行一次

当前最小验收：

```bash
python3 scripts/openclaw-frontstage-broker.py rebuild-views --print-json
systemctl --user start openclaw-frontstage-broker-rebuild.service
systemctl --user show openclaw-frontstage-broker-rebuild.service -p Result -p ExecMainStatus -p ActiveState -p SubState
systemctl --user show openclaw-frontstage-broker-rebuild.timer -p UnitFileState -p ActiveState -p SubState
```

### 5. infos-handle sidecar（Control UI 直连入口）

用途：

- 给 Control UI / 其他轻量 consumer 提供 infos-handle 的最小本地 HTTP / SSE 直连入口
- 当前 live branding patch 在浏览器侧默认走同源 `/v1/...` 统一入口（即经 `:18788` unified proxy 代理到 sidecar）；若这条 live 链不可用，再回退 `jarvis-frontstage-snapshot.json`

相关文件：

- sidecar 脚本：`scripts/openclaw-infos-handle-sidecar.py`
- README：`tools/openclaw-infos-handle-sidecar/README.md`
- service 模板：`tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
- 当前用户态 systemd：`~/.config/systemd/user/openclaw-infos-handle-sidecar.service`

当前监听：

- `127.0.0.1:18790`

当前最小接口：

- `GET /healthz`
- `GET /v1/query/<kind>`
- `POST /v1/handle`
- `GET /v1/events/stream`

当前最小验收：

```bash
systemctl --user show openclaw-infos-handle-sidecar.service -p ActiveState -p SubState -p UnitFileState
curl -s http://127.0.0.1:18790/healthz
curl -s 'http://127.0.0.1:18790/v1/query/snapshot.summary?format=json'
curl -s 'http://127.0.0.1:18790/v1/query/contract.catalog?format=json'
curl -N 'http://127.0.0.1:18790/v1/events/stream?kind=snapshot.summary&intervalMs=1000'
```

### 6. infos-handle 统一入口代理（Caddy）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-19
- 用途：给 Gateway 与 infos-handle sidecar 提供单端口统一入口；默认 `:18788`，其余保持 Gateway `:18789` 与 sidecar `:18790` 分离。

相关文件：

- Caddyfile：`tools/openclaw-infos-handle-gateway-proxy/Caddyfile`
- README：`tools/openclaw-infos-handle-gateway-proxy/README.md`
- apply/verify 脚本：`scripts/apply-openclaw-infos-handle-gateway-proxy.py`
- service 模板：`tools/openclaw-infos-handle-gateway-proxy/openclaw-unified-proxy.service`
- 当前用户态 systemd：`~/.config/systemd/user/openclaw-unified-proxy.service`

当前路由：

- `/v1/query/*` `/v1/handle*` `/v1/artifacts/*` `/v1/events/*` `/healthz*` → `127.0.0.1:18790`
- 其余 → `127.0.0.1:18789`

当前关键点：

- 会透传原始客户端 IP（`X-Forwarded-For` + `X-Real-IP`）
- sidecar 会据此判断远程请求，不再把经代理进入的 LAN 请求误判为 localhost 免鉴权
- 当前支持 HTTP / HTTPS（域名）两种模式；切到 HTTPS 推荐直接走 apply 脚本

推荐命令：

```bash
python3 scripts/apply-openclaw-infos-handle-gateway-proxy.py --install-user-systemd --enable --restart --verify --print-json
python3 scripts/apply-openclaw-infos-handle-gateway-proxy.py --mode https --domain your-domain.com --email you@example.com --reload --verify --print-json
```

### 7. systemd 用户单元

相关文件：

- `~/.config/systemd/user/openclaw-resume-watch.service`
- `~/.config/systemd/user/openclaw-resume-watch.timer`

用途：

- 在 Linux 用户态下调度 resume-watch 逻辑

### 8. Control UI 品牌覆盖（贾维斯）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-07
- 维护来源：用户希望把 Control UI 左上角默认的 OpenClaw / 小龙虾品牌，逐步替换成更贴近“贾维斯”的品牌呈现，并要求采用“可重复应用”的方案，避免 OpenClaw 升级后又回到默认样式。

相关文件：

- 配置：`config/control-ui-branding.json`
- 应用脚本：`scripts/apply-openclaw-control-ui-branding.py`
- systemd 自动重应用：`~/.config/systemd/user/openclaw-gateway.service.d/branding.conf`
- 当前默认品牌图：`avatars/jarvis-neon-20260507.png`

用途：

- 重复应用 Control UI 左上角品牌名与 logo 覆盖
- 同步覆盖浏览器标题、favicon / apple-touch-icon、manifest 名称与默认通知标题
- 通过页面注入脚本，把 Control UI 里可见的 `OpenClaw` 文案尽量替换成“贾维斯”（保留聊天内容 / 代码块等常见高风险区域的跳过规则）
- 在 Control UI 顶部工具栏下方稳定挂一个统一的“前台状态”固定入口；当前默认折叠成小圆角按钮，点击后向下展开详情卡片，尽量不遮挡上方按钮
- 当前这枚入口会先尝试同源 `/v1/query/snapshot.summary?format=json` / `/v1/events/stream?...` 这条 live 链；失败时再回退 broker sidecar 重建出来的统一 snapshot 公共副本：`/jarvis-frontstage-snapshot.json`，并打开 `/jarvis-frontstage-status.html`
- 本地健康自己的独立公开页仍继续保留：`/jarvis-local-health-status.json` / `/jarvis-local-health-status.html`
- 健康页与入口卡片都应携带一组无需 AI 参与的本地自救建议；例如“状态正常但页面卡住”时直接提示刷新页面 / 重开浏览器
- 当前也负责重复应用三个前台状态补丁：
  - 把聊天页“进行中”判断补成同时考虑 `loading / sending / stream / canAbort / queue.length > 0 / session.hasActiveRun / session.status=running`，避免后台仍在工作但前台既不流字、也不转圈的空窗
  - 当 assistant final 为空 / silent 时，不再立刻强制 `chat.history` reload，先压住“前台刚有阶段性内容又被立即清掉”的 ghost/disappear 体感
  - 当 `chat.history` 里出现 `sessions_yield` 的 `toolResult(status=yielded,message=...)`，但没有对应可见 assistant 回复时，前端会补投影出一条临时 assistant 文本，避免出现“三个点消失了，但一行字都没回”的空窗
- 尽量避免每次升级后再手工去改 `dist/control-ui/` 里的静态产物

当前默认配置：

- 左上角品牌名：`贾维斯`
- 小标题：`CONTROL`
- 浏览器标题：`贾维斯 Control`

应用方式：

```bash
python3 scripts/apply-openclaw-control-ui-branding.py
```

说明：

- 该脚本会把配置中的品牌图复制到本机 OpenClaw 安装目录下的 `dist/control-ui/`，并注入一个额外的 `jarvis-branding-override.js` 覆盖脚本。
- 当前 `jarvis-branding-override.js` 里的 infos-handle live Href 已改成同源 `/v1/...` 路径，不再写死 `http://127.0.0.1:18790`，以避免被页面 CSP 的 `connect-src` 拦截。
- 同一个脚本现在还会顺手给 `dist/control-ui/assets/index-*.js` 打三条最小前台状态补丁：
  - 把聊天页的“进行中”条件从只看 `sending / stream`，补成也看 `loading / canAbort / queue.length > 0`，并把 `session.hasActiveRun / session.status=running` 一并算作“前台仍活着”
  - 把 `assistant final 为空 / silent 时立刻强制 reload history` 这条路径改成更保守的收口，减少前台内容一闪而空
  - 当 reload 回来的 `chat.history` 里只有 `yielded toolResult`、却没有可见 assistant 文本时，补投影出 `yielded.message`，把“已生成但没显示出来”的那句话稳定留在前台
- 另外已在公司 Linux 机的 `openclaw-gateway.service` 上挂了一个 `ExecStartPre`：每次 gateway 启动前，都会自动先跑一遍这个品牌补丁脚本；即使以后 OpenClaw 升级覆盖了静态资源，只要重启 gateway，就会自动重新覆盖。
- 该 `ExecStartPre` 使用了前缀 `-` 忽略失败，避免品牌补丁偶发出错时直接把 gateway 启动也一并卡死。
- 如果以后用户想把左上角名称改成 `J.A.R.V.I.S.`、改别的图、或继续往电影风格靠，只需要改 `config/control-ui-branding.json` 再重跑脚本。
- 当前这个“前台状态”入口刻意做成固定悬浮入口，而不是强依赖某个侧边栏内部节点；这样对 Control UI 升级后的 DOM 变化更稳。
- 当前交互为：默认折叠成小圆角按钮；点击后展开详情卡片；点击卡片右上角 `×` 再收起回小按钮。
- 这是“可重复应用补丁”，不是官方配置项；如果以后 OpenClaw 前端结构变化很大，补丁脚本可能需要跟着调整，但总体维护点已经集中到这几个文件里，不需要再手工逐个改 dist 文件。

### 6. NVIDIA 免费语音模型桥接（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-08
- 用途：让当前这台公司 Linux 机上的 OpenClaw gateway 通过本地 bridge 使用 NVIDIA 免费语音模型（TTS / ASR），并保持主 gateway 继续稳定运行。

当前方案：

- OpenClaw gateway 继续监听：`127.0.0.1:18789`
- 本地 NVIDIA 音频 bridge 监听：`127.0.0.1:18890`
- gateway 新增代理路径：
  - `/v1/audio/speech`
  - `/v1/audio/transcriptions`
- bridge 内部通过 `nvidia-riva-client` 走 `grpc.nvcf.nvidia.com:443` + `function-id` 调用 NVIDIA 公共免费语音函数，而不是直接依赖 `integrate.api.nvidia.com/v1/audio/...`

相关文件：

- bridge 服务代码：`tools/nvidia-audio-bridge/bridge.py`
- bridge README：`tools/nvidia-audio-bridge/README.md`
- 依赖清单：`tools/nvidia-audio-bridge/requirements.txt`
- repo 内 service 模板：`tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service`
- gateway 补丁脚本：`scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
- bridge 用户态 systemd：`~/.config/systemd/user/openclaw-nvidia-audio-bridge.service`
- OpenClaw 配置：`~/.openclaw/openclaw.json`
- OpenClaw 安装产物（被补丁修改）：`~/.npm-global/lib/node_modules/openclaw/dist/server.impl-*.js`
- 新增代理模块：`~/.npm-global/lib/node_modules/openclaw/dist/openai-audio-http-nvidia-bridge.js`

当前关键配置：

- `~/.openclaw/openclaw.json` 已增加：

```json
{
  "gateway": {
    "http": {
      "endpoints": {
        "chatCompletions": {
          "enabled": true
        }
      }
    }
  }
}
```

说明：

- 这是为了让 OpenClaw 内部 `openAiCompatEnabled` 变为启用状态，从而让新增的音频 HTTP 路由真正生效。
- 这个改动仍然保持 gateway 为 `loopback` 绑定，不会把本机接口直接暴露到外网。

当前已验证结果：

- 通过 gateway 调用 TTS：`200 OK`，可返回 `audio/mpeg`
- 通过 gateway 调用 ASR：`200 OK`
- 使用 gateway 先生成 TTS，再把生成的 MP3 回送 ASR，已得到正确转写：`Hello from nvidia gateway bridge test.`

新机器最小落地步骤：

1. 先读 `tools/nvidia-audio-bridge/README.md`，确认用途、依赖和验证命令。
2. 确认 `~/.openclaw/openclaw.json` 里已有可用的 `models.providers.nvidia.apiKey`。
3. 准备 bridge 运行环境（当前公司 Linux 机使用 `~/.local/share/openclaw-nvidia-audio-bridge-venv`）。
4. 复制 repo 内模板 `tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service` 到 `~/.config/systemd/user/`，执行 `systemctl --user daemon-reload && systemctl --user enable --now openclaw-nvidia-audio-bridge.service`。
5. 执行 `python3 scripts/apply-openclaw-nvidia-audio-gateway-patch.py` 给 OpenClaw 打补丁，再重启 bridge 与 gateway。
6. 用 README 里的 `/health`、TTS、ASR 验证命令做最小回归。

systemd 维护命令：

```bash
systemctl --user status openclaw-nvidia-audio-bridge.service
systemctl --user restart openclaw-nvidia-audio-bridge.service
journalctl --user -u openclaw-nvidia-audio-bridge.service -n 100 --no-pager
```

注意：

- 该方案是本机补丁，不是 OpenClaw 官方现成配置项；未来 OpenClaw 升级后，如果 `dist/server.impl-*.js` 文件名或结构变化，需要重新执行或调整补丁脚本。
- 如果 gateway 重启后音频接口重新变成 `404` 或 `502`，优先检查两点：
  1. `openclaw-nvidia-audio-bridge.service` 是否仍在运行；
  2. OpenClaw 升级后补丁是否被覆盖。
- 不要把 NVIDIA API key 硬编码进脚本；bridge 会从 `~/.openclaw/openclaw.json` 中读取现有 `providers.nvidia.apiKey`。

## 标注规则

今后凡是会同步到 GitHub、且内容属于 **公司（Linux）** 专用的系统说明、脚本说明、修复记录，都必须在正文显式写出：

- 适用机器：`公司（Linux）`
- 系统 / OS：`Linux`
- 用途说明
