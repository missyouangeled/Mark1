# OpenClaw 补丁注册表

- 适用机器:通用
- 系统 / OS:通用
- 文档类型:跨机器共享的补丁索引 / 迁移注册表

## 用途

这份注册表不是简单记录"改过哪些文件",而是记录:

- 每个正式补丁想保证的**结果**
- 当前通过什么**实现链路**达成
- 它依赖哪些**自动触发**或重打入口
- 升级后如何判断它是否仍然生效
- 如果上游大版本变化导致失效,后续该去哪里续接

一句话目标:

> 即使 OpenClaw 大版本改动了,也能按这份表逐项恢复"结果不变"的补丁能力,而不是重新靠记忆猜我们以前做过什么。

---

## 字段说明

| 字段 | 含义 |
|---|---|
| Patch ID | 稳定标识,便于跨文档引用 |
| 结果目标 | 用户真正想要的效果 |
| 当前实现 | 现在用什么脚本 / 配置 / service 达成 |
| 自动触发 | 是否在 gateway 启动前或 systemd timer 中自动生效 |
| 适用范围 | 通用 / 公司(Linux)/ 掌机(Windows)等 |
| 升级风险点 | 大版本最可能破坏哪一层 |
| 失效判断 | 怎么快速判断这条补丁是不是掉了 |
| 最小验收 | 如何做一轮最小回归 |
| 维护落点 | 需要优先查看/续改的文件 |

---

## 注册表

### PATCH-POST-UPGRADE-SELF-CHECK

- **结果目标**:当 OpenClaw 版本变化并重新打开后,主动按统一自检清单核对关键补丁 / broker / recovery watcher 是否仍正常;版本未变时不重复刷屏。
- **当前实现**:`scripts/openclaw-post-upgrade-self-check.py` + `BOOT.md`
- **自动触发**:`BOOT.md` + `boot-md` hook(启动时先跑脚本,再按输出消息上线)
- **适用范围**:通用
- **升级风险点**:boot hook 行为变化;package 版本检测入口变化;systemd / dist 路径变化
- **失效判断**:OpenClaw 更新后再次打开,没有主动给出升级后自检结果;或脚本无法识别版本变化;或明明版本变化却没有触发自检
- **最小验收**:运行 `python3 scripts/openclaw-post-upgrade-self-check.py --force --print-human`,应能完成清单核对并输出通过/失败摘要;运行 `python3 scripts/openclaw-post-upgrade-self-check.py --print-boot-json`,应返回包含 `bootMessage` 的 JSON
- **维护落点**:
  - `docs/通用-OpenClaw-升级后自检清单.md`
  - `scripts/openclaw-post-upgrade-self-check.py`
  - `BOOT.md`
  - `TOOLS.md`

### PATCH-LINUX-RESUME-RECOVERY

- **结果目标**:当公司(Linux)机器从休眠恢复、宿主机长时间暂停、或发生明显时间跳变后,自动重启 `openclaw-gateway.service`,尽量把"恢复后前台像没活过来"的情况收敛成可自愈的一次 gateway 恢复。
- **当前实现**:`scripts/openclaw-resume-watch.sh` + `~/.config/systemd/user/openclaw-resume-watch.service` + `~/.config/systemd/user/openclaw-resume-watch.timer`
- **自动触发**:user systemd timer;当前默认 `OnBootSec=2min`、`OnUnitActiveSec=1min`
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:`openclaw-gateway.service` 单元名变化;user systemd 行为变化;`/proc/sys/kernel/random/boot_id` 或时间跳变判定逻辑变化
- **失效判断**:休眠/恢复后 gateway 没被自动拉起;`resume-watch.log` 长期无新记录;或 timer / service 不再处于正常启用状态
- **最小验收**:执行 `systemctl --user show openclaw-resume-watch.service -p ActiveState -p SubState -p Result`、`systemctl --user show openclaw-resume-watch.timer -p UnitFileState -p ActiveState -p SubState` 应正常;必要时手工执行 `bash scripts/openclaw-resume-watch.sh` 确认脚本可运行并会写状态文件/日志
- **维护落点**:
  - `scripts/openclaw-resume-watch.sh`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`
  - `~/.config/systemd/user/openclaw-resume-watch.service`
  - `~/.config/systemd/user/openclaw-resume-watch.timer`
  - `~/.local/state/openclaw/resume-watch.env`
  - `~/.local/state/openclaw/resume-watch.log`

### PATCH-CTRLUI-BRANDING

- **结果目标**:Control UI 左上角品牌、浏览器标题、图标、页面内可见 OpenClaw 品牌尽量统一替换为"贾维斯"风格；同时确保 branding override 注入的前台 live 入口默认走同源 `/v1/...` 统一入口,避免浏览器因 `connect-src` 拦截 `127.0.0.1:18790` 而黑屏。
- **当前实现**:`scripts/apply-openclaw-control-ui-branding.py`
- **自动触发**:`~/.config/systemd/user/openclaw-gateway.service.d/branding.conf` 的 `ExecStartPre`
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:`dist/control-ui/` 前端结构 / `index.html` 注入点变化; `jarvis-branding-override.js` 的 `infosHandle*Href` 契约或 CSP 行为变化
- **失效判断**:Control UI 刷新后重新出现大量默认 `OpenClaw` 品牌文案; 或浏览器控制台重新出现 `connect-src` 拦截 `http://127.0.0.1:18790` 导致 live dock 失效 / 黑屏
- **最小验收**:运行 `python3 scripts/apply-openclaw-control-ui-branding.py` 后,确认输出成功; live `jarvis-branding-override.js` 不再包含 `http://127.0.0.1:18790`,并包含 `/v1/query/snapshot.summary?format=json`、`/v1/query/contract.catalog?format=json`、`/v1/events/stream?kind=snapshot.summary`; 刷新页面后品牌名/标题仍为"贾维斯"
- **维护落点**:
  - `scripts/apply-openclaw-control-ui-branding.py`
  - `config/control-ui-branding.json`
  - `docs/通用-OpenClaw-补丁重建清单.md`
  - `docs/通用-OpenClaw-升级后自检清单.md`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-CTRLUI-RUNNING-SIGNAL

- **结果目标**:只要聊天页后台 run 还没真结束,前台尽量持续显示"进行中/活着信号",并减少 assistant silent/empty final 时"前台刚有阶段性内容又被立即清掉"的 ghost/disappear 体感;若 `sessions_yield` 已经产出 `message`,也尽量把它稳定留成前台可见文本,而不是让"三个点消失了但没回字"。同时要求 reading-indicator 补丁保持 JS 语法安全,不能因 minify 变量重名把主 bundle 打坏造成 Control UI 黑屏。
- **当前实现**:并入 `scripts/apply-openclaw-control-ui-branding.py`,重打 `dist/control-ui/assets/index-*.js`
- **自动触发**:同 `PATCH-CTRLUI-BRANDING`,随 gateway 启动前自动重打
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:聊天页前端状态机构造变化,`sI(...)` 或等价逻辑重构; minified bundle 局部变量名变化,导致 reading-indicator 补丁出现重复声明
- **失效判断**:tool 阶段 / history reload / active run 明显仍在进行时,前台不流字也不转圈;或 `sessions_yield` 明明已经给了 `message`,前台却出现"三个点消失但没回字";或浏览器控制台出现 `SyntaxError: Identifier 'c' has already been declared` / 页面直接黑屏
- **最小验收**:确认补丁后的条件仍覆盖 `loading / sending / stream / canAbort / queue.length > 0 / session.hasActiveRun / session.status=running`,并确认 `u&&!o&&!a){Gl(e);return}` 这条"silent final 立刻 reload"旧分支已不再存在;再确认前端资产里已带 `JarvisProjectYieldedHistoryReply`,并能把 `yielded toolResult` 里的 `message` 补投影成 assistant 可见文本; live bundle 中坏片段 `let c=JarvisShouldShowPendingReadingIndicator(e)` 不存在、已改为 `let pendingIndicator=JarvisShouldShowPendingReadingIndicator(e)`;并执行 `node --check` 验证当前 `dist/control-ui/assets/index-*.js` 无语法错误
- **维护落点**:
  - `scripts/apply-openclaw-control-ui-branding.py`
  - `docs/通用-OpenClaw-补丁重建清单.md`
  - `docs/通用-OpenClaw-升级后自检清单.md`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-CTRLUI-SESSION-MODEL-SELECTOR

- **结果目标**:Control UI 聊天页模型下拉必须以“当前会话”为作用域；用户选择哪个模型，当前会话后续回复就使用哪个模型。切换后 UI 必须回填后端 `sessions.patch` 的 canonical `resolved.modelProvider/model`，并刷新 tools-effective；active run 期间也允许提交 live model switch，而不是只改前端显示。
- **当前实现**:`scripts/apply-openclaw-session-model-selector-fix.py`，重打 `dist/control-ui/assets/index-*.js`、`dist/session-utils-*.js`，并给 `dist/control-ui/index.html` 的主 bundle 引用追加 `jarvisModelSelector=<mtime>` 缓存破坏参数
- **自动触发**:公司(Linux) 已接入 `~/.config/systemd/user/openclaw-gateway.service.d/model-selector.conf` 的 `ExecStartPre`；升级或重启 gateway 前自动重打。
- **适用范围**:通用补丁脚本；当前主落地为 公司(Linux)
- **升级风险点**:Control UI bundle 中模型下拉函数 `hW/CW/bU/_U` 重构；`sessions.patch` 返回结构或 `resolved.modelProvider/model` 字段变化；`session-utils-*.js` 文件名/hash 或 `resolveSessionModelRef` 逻辑变化。
- **失效判断**:下拉显示已变化但 `session_status` / 实际下一轮回复仍使用旧模型；下拉选择后没有调用 `sessions.patch`; 切换后 UI 又被旧 `sessionsResult.sessions[].model` 覆盖；active run 时完全无法提交模型切换。
- **最小验收**:运行 `python3 scripts/apply-openclaw-session-model-selector-fix.py` 应输出 `patched-or-current`; live asset 里应同时存在 `s?.resolved?.modelProvider`、`refresh-tools-effective`、`data-chat-model-select="true"`，且旧的 `_U(e)===t` 早退分支不再存在；RPC 烟测 `openclaw gateway call sessions.patch --timeout 60000 --json --params '{"key":"agent:main:main","model":"github-copilot/gpt-5.5"}'` 应返回 `resolved=github-copilot/gpt-5.5`；`index.html` 主 bundle 引用应带 `?jarvisModelSelector=`。
- **维护落点**:
  - `scripts/apply-openclaw-session-model-selector-fix.py`
  - `~/.config/systemd/user/openclaw-gateway.service.d/model-selector.conf`
  - `docs/通用-OpenClaw-补丁重建清单.md`
  - `docs/通用-OpenClaw-升级后自检清单.md`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-SUPERVISOR-SERVICE-STATE

- **结果目标**:持续产出一份稳定可读的监工状态层,让主会话的 `policyMode/taskActive/desiredState`、活跃任务聚焦、`stalled/failed/done/waiting` 状态,以及"完成后约 10 分钟等待接续任务窗口"都有可复读、可恢复的统一状态来源。
- **当前实现**:`scripts/openclaw-supervisor-status.py` + Watcher v2 的 `scripts/openclaw-health-collector.py` 子检查;旧 `tools/openclaw-supervisor/openclaw-supervisor-watch.*` 仅保留作历史回退参考
- **自动触发**:`openclaw-health-collector.timer` 周期刷新;当前不再启用旧 `openclaw-supervisor-watch.timer`
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:任务库结构变化;session / transcript 尾部解析规则变化;控制语义(`auto|force_on|force_off`、followup window)变化
- **失效判断**:`supervisor-status.json` / `service-control.json` / `supervisor-events.log` 不再更新;或复杂任务已开启监工语义但状态长期停留错误;或 10 分钟接续窗口语义失效
- **最小验收**:运行 `python3 scripts/openclaw-supervisor-status.py --print-json` 应返回完整状态;`openclaw-health-collector.timer` 应处于 `enabled + active(waiting)`;`python3 scripts/openclaw-health-collector.py --print-human` 应能刷新监工/健康汇总
- **维护落点**:
  - `scripts/openclaw-supervisor-status.py`
  - `scripts/test-openclaw-supervisor-status.py`
  - `tools/openclaw-supervisor/README.md`
  - `tools/openclaw-supervisor/openclaw-supervisor-watch.service`（历史回退模板）
  - `tools/openclaw-supervisor/openclaw-supervisor-watch.timer`（历史回退模板）
  - `scripts/openclaw-health-collector.py`
  - `~/.config/systemd/user/openclaw-health-collector.service`
  - `~/.config/systemd/user/openclaw-health-collector.timer`
  - `~/.local/state/openclaw/supervisor/`
  - `TOOLS.md`

### PATCH-FRONTSTAGE-BROKER

- **结果目标**:把监工、本地健康、前台恢复观察等辅助消息统一收口后,再稳定投递到"当前前台 dashboard",并沉淀成统一 snapshot 口径的 sidecar 数据源,供 renderer / dock 等消费方直接复用;`overview` / `frontstage-status.json` 等旧名字只保留为兼容层。
- **当前实现**:`scripts/openclaw-frontstage-broker.py` + `scripts/openclaw-infos-handle.py` + `scripts/apply-openclaw-frontstage-broker-data.py`
- **自动触发**:由 `supervisor` / `local-health` / `frontstage-recovery` 等调用方间接触发;Watcher v2 后默认通过 `openclaw-health-collector` / `openclaw-frontstage-guardian` 的 dirty flag 事件驱动重建视图,旧 `openclaw-frontstage-broker-rebuild.*` 仅保留作手工兜底模板
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:`openclaw-supervisor-subagent.py send-frontstage` 调用约定变化;`chat.inject` 路由变化;broker 视图模型与事件契约从"纯 delivery"演进为"source + delivery 双记录"后的兼容性;`infos-handle` 与 broker CLI 参数约定变化
- **失效判断**:辅助消息仍回到旧 dashboard,或 `broker-state.json` / `events.jsonl` / `views/*.json` 不再更新;或 `events.jsonl` 里不再出现 `broker.source.event`;或 `openclaw-infos-handle.py query` 不能正常返回 text/json
- **最小验收**:执行 `python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock` 应成功;执行一次 `ingest` 烟测后,确认 `~/.local/state/openclaw/broker/events.jsonl` 出现 `broker.source.event`;执行 `python3 scripts/openclaw-infos-handle.py query --kind snapshot.summary --format text` 应能正常返回;`views/snapshot.json` 与 `jarvis-frontstage-snapshot.json` 已刷新,`manifest.json` / `snapshot.json` 都声明 `snapshotContract.primaryView = snapshot`,并把 `overview` / `frontstage-status.json` 标成 `legacy_alias`、把 `frontstage / health / tasks / recovery` 标成 `supporting_view`;apply 输出里的 `controlUiSnapshotDock.snapshotJsonHref` 应指向 `/jarvis-frontstage-snapshot.json`,`frontstagePublication.snapshotFirstReady` 应为 `true`;`python3 scripts/openclaw-frontstage-broker.py rebuild-views --print-json` 可手工重建成功,且 Watcher v2 的 dirty flag 链路可触发刷新
- **维护落点**:
  - `scripts/openclaw-frontstage-broker.py`
  - `scripts/test-frontstage-broker.py`
  - `scripts/openclaw-infos-handle.py`
  - `scripts/test-openclaw-infos-handle.py`
  - `scripts/apply-openclaw-frontstage-broker-data.py`
  - `scripts/openclaw-supervisor-subagent.py`
  - `tools/openclaw-frontstage-broker/README.md`
  - `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service`（手工兜底模板,默认不启用）
  - `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer`（手工兜底模板,默认不启用）
  - `scripts/openclaw-health-collector.py`
  - `scripts/openclaw-frontstage-guardian.py`
  - `~/.local/state/openclaw/frontstage/broker-state.json`
  - `~/.local/state/openclaw/broker/`

### PATCH-LOCAL-HEALTH-DIAGNOSTIC-LAYER

- **结果目标**:在不依赖 AI 回复的前提下,持续产出本机 OpenClaw 的本地健康诊断结果,把故障尽量分类到 gateway、本机外联、主线 provider 路由、温度、负载/内存,并同步生成本地健康页面与公共静态副本。
- **当前实现**:`scripts/openclaw-local-health-diagnose.py` + Watcher v2 的 `scripts/openclaw-health-collector.py` 子检查;旧 `tools/openclaw-local-health/openclaw-local-health-watch.*` 仅保留作历史回退参考
- **自动触发**:`openclaw-health-collector.timer`;轻量检查每轮运行,完整 local-health 诊断约每 5 轮/5 分钟运行一次;当前不再启用旧 `openclaw-local-health-watch.timer`
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:`openclaw status --json` 输出变化;provider 配置结构变化;公共静态副本路径变化;宿主机温度桥接路径与格式变化
- **失效判断**:`last-report.json` / `last-summary.txt` / `health-diagnostic.log` 长期不更新;`jarvis-local-health-status.html/.json` 不再刷新;或页面不再能给出 gateway/网络/provider 的明确分类
- **最小验收**:运行 `python3 scripts/openclaw-local-health-diagnose.py --print-json` 应成功并生成状态文件;`openclaw-health-collector.timer` 应处于 `enabled + active(waiting)`;`~/.openclaw/canvas/documents/local-health-status/index.html` 与 `jarvis-local-health-status.json` 应存在
- **维护落点**:
  - `scripts/openclaw-local-health-diagnose.py`
  - `tools/openclaw-local-health/README.md`
  - `tools/openclaw-local-health/openclaw-local-health-watch.service`（历史回退模板）
  - `tools/openclaw-local-health/openclaw-local-health-watch.timer`（历史回退模板）
  - `scripts/openclaw-health-collector.py`
  - `~/.config/systemd/user/openclaw-health-collector.service`
  - `~/.config/systemd/user/openclaw-health-collector.timer`
  - `~/.local/state/openclaw/local-health/`
  - `~/.openclaw/canvas/documents/local-health-status/`
  - `TOOLS.md`

### PATCH-INFOS-HANDLE-SIDECAR

- **结果目标**:为 Control UI / 其他轻量 consumer 提供 infos-handle 的最小 HTTP / SSE live 入口,优先读取正式请求层结果,而不是只依赖 broker 静态快照;同时保持"localhost 免鉴权、远程/LAN 需 Bearer token"的受控访问语义。当前浏览器侧 Control UI 默认应通过同源 `/v1/...`（经 `:18788` unified proxy）访问这条 live 链,而不是直接请求 `127.0.0.1:18790`。
- **当前实现**:`scripts/openclaw-infos-handle-sidecar.py` + `tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
- **自动触发**:当前主落地依赖 user systemd:`openclaw-infos-handle-sidecar.service`
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:sidecar 路由 / 返回结构变化;artifact href 语义变化;Control UI 注入的 `infosHandle*Href` 契约变化; unified proxy / same-origin 路由变化; remote auth / rate-limit 语义变化
- **失效判断**:`/healthz`、`/v1/query/*`、`/v1/events/stream` 无法正常访问;或 Control UI 不再能通过 sidecar 读取 summary / contract;或浏览器重新出现 `connect-src` 拦截 `127.0.0.1:18790`;或 image/audio artifactHref 无法继续取回文件
- **最小验收**:运行 `python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar --require-control-ui-infos-handle-sidecar` 应通过;必要时补跑 `python3 scripts/test-openclaw-infos-handle.py`;并确认 `curl -s http://127.0.0.1:18788/v1/query/snapshot.summary?format=json`、`curl -s 'http://127.0.0.1:18788/v1/query/contract.catalog?format=json'`、`curl -s http://127.0.0.1:18790/healthz` 可用; apply 输出里的 `summaryHref / contractHref / sseHref` 应为同源 `/v1/...` 相对路径
- **维护落点**:
  - `scripts/openclaw-infos-handle-sidecar.py`
  - `scripts/test-openclaw-infos-handle.py`
  - `scripts/apply-openclaw-frontstage-broker-data.py`
  - `tools/openclaw-infos-handle-sidecar/README.md`
  - `tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
  - `docs/通用-OpenClaw-补丁重建清单.md`
  - `docs/通用-OpenClaw-升级后自检清单.md`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-INFOS-HANDLE-UNIFIED-PROXY

- **结果目标**:给 Gateway 与 infos-handle sidecar 提供单端口统一入口,并把原始客户端 IP 正确透传给 sidecar,避免远程请求被误判成 localhost 免鉴权。
- **当前实现**:`tools/openclaw-infos-handle-gateway-proxy/Caddyfile` + `scripts/apply-openclaw-infos-handle-gateway-proxy.py` + `tools/openclaw-infos-handle-gateway-proxy/openclaw-unified-proxy.service`
- **自动触发**:当前主落地依赖 user systemd:`openclaw-unified-proxy.service`
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:Gateway / sidecar 端口变化;Caddy 路由规则变化;原始客户端 IP 透传头语义变化;verify 逻辑与 token 校验预期变化
- **失效判断**:`18788` 统一入口无法同时代理 Gateway 与 sidecar;`/healthz`、`/v1/query/*` 返回异常;或远程无 token 时没有得到 `401`、带 token 时也不能正常 `200`
- **最小验收**:运行 `python3 scripts/apply-openclaw-infos-handle-gateway-proxy.py --verify --print-json`,至少确认 `localHealthzOk=true`、`localSummaryCode=200`;若当前机器可从 LAN 访问,再确认 `remoteNoAuthCode=401`、`remoteWithAuthCode=200`
- **维护落点**:
  - `scripts/apply-openclaw-infos-handle-gateway-proxy.py`
  - `tools/openclaw-infos-handle-gateway-proxy/README.md`
  - `tools/openclaw-infos-handle-gateway-proxy/Caddyfile`
  - `tools/openclaw-infos-handle-gateway-proxy/openclaw-unified-proxy.service`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-SUPERVISOR-AUTO-NOTIFY

- **结果目标**:监工状态在 `stalled / failed / done` 变化时,自动经由 broker 回前台,并能跟随当前 dashboard 页面。
- **当前实现**:`scripts/openclaw-supervisor-status.py --notify-transitions`
- **自动触发**:`openclaw-health-collector.timer` 调用 `scripts/openclaw-supervisor-status.py --notify-transitions`
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:task 状态模型变化;frontstage 解析规则变化;broker `emit` 返回结构(尤其 `messageId` 字段位置)变化
- **失效判断**:`notify-state.json` 不更新、事件日志无 `notify_sent`、前台无监工摘要;或摘要误落回 `agent:main:main` 而不是当前 dashboard;或日志里的 `messageId` 异常为 `null`
- **最小验收**:人工烟测一次 `done / failed / stalled` 任务,并确认前台收到对应摘要;`notify_sent` 日志里的 `target=` 应指向当前 dashboard,且 `messageId` 为真实注入消息 id
- **维护落点**:
  - `scripts/openclaw-supervisor-status.py`
  - `tools/openclaw-supervisor/README.md`
  - `~/.local/state/openclaw/supervisor/notify-state.json`

### PATCH-LOCAL-HEALTH-FRONTSTAGE

- **结果目标**:本地健康在 `warn / critical / recovered` 变化时,经由 broker 回前台一条简明辅助摘要,但不周期性"报平安"。
- **当前实现**:`scripts/openclaw-local-health-diagnose.py --notify-frontstage`
- **自动触发**:`openclaw-health-collector.timer` 周期调用 local-health 子检查
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:local-health 状态摘要结构变化;broker 接口变化
- **失效判断**:健康状态变化时 `transition-state.json` 更新,但前台和 broker state 没有对应消息
- **最小验收**:人为造一次 `warn -> ok` 恢复烟测,确认 broker state 出现 `local-health` 的 recovered 记录
- **维护落点**:
  - `scripts/openclaw-local-health-diagnose.py`
  - `tools/openclaw-local-health/README.md`
  - `~/.local/state/openclaw/local-health/transition-state.json`

### PATCH-FRONTSTAGE-RECOVERY-WATCH

- **结果目标**:周期对比 durable transcript 与 `chat.history` 投影,尽早发现"主回复前台没稳定留下 / 投影异常"的情况,并在 anomaly / recovered 变化时经由 broker 回前台。
- **当前实现**:`scripts/openclaw-frontstage-recovery-watch.py`
- **自动触发**:`openclaw-frontstage-guardian.timer` 子检查调用;旧独立 `openclaw-frontstage-recovery-watch.*` 不再启用
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:`chat.history` 投影规则变化;`sessions.list` 状态字段变化;前端 optimistic-tail 行为变化
- **失效判断**:`last-report.json` 停更;明明出现 anomaly/recovered,`notify-state.json` 和事件日志不变;或频繁误报
- **最小验收**:运行 `python3 scripts/test-frontstage-recovery-watch.py` 应全部通过;service/timer 应正常运行
- **维护落点**:
  - `scripts/openclaw-frontstage-recovery-watch.py`
  - `scripts/test-frontstage-recovery-watch.py`
  - `tools/openclaw-frontstage-recovery/README.md`
  - `~/.local/state/openclaw/frontstage-recovery/`

### PATCH-WINDOWS-GATEWAY-BATTERY-POLICY

- **结果目标**:修复掌机(Windows)上原生 `OpenClaw Gateway` 计划任务在电池模式下"禁止启动 / 切到电池自动停止"的设置,避免拔电后因为任务计划策略把 OpenClaw 直接停掉。
- **当前实现**:`scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1` + `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.cmd`
- **自动触发**:当前依赖手工修复入口,不默认自动重打
- **适用范围**:掌机(Windows)
- **升级风险点**:Windows 计划任务 XML 结构变化;任务名 `OpenClaw Gateway` 变化;系统权限或 `schtasks` 行为变化
- **失效判断**:计划任务重新出现 `DisallowStartIfOnBatteries=True` 或 `StopIfGoingOnBatteries=True`;拔电后 OpenClaw 因任务计划限制被停掉
- **最小验收**:运行 `powershell -ExecutionPolicy Bypass -File .\scripts\repair-openclaw-gateway-battery-policy-zhangji-windows.ps1` 后,应能看到 `DisallowStartIfOnBatteries = false`、`StopIfGoingOnBatteries = false`
- **维护落点**:
  - `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1`
  - `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.cmd`
  - `docs/掌机-Windows-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-NVIDIA-AUDIO-GATEWAY-BRIDGE

- **结果目标**:让当前机器的 OpenClaw gateway 暴露 NVIDIA 音频代理接口(TTS / ASR),并保持主 gateway 继续稳定运行。
- **当前实现**:`scripts/apply-openclaw-nvidia-audio-gateway-patch.py` + `tools/nvidia-audio-bridge/bridge.py`
- **自动触发**:当前依赖手工补丁重打;bridge 本身由用户态 systemd 运行,但这是辅助语音支路,默认允许保持 `disabled + inactive`,不应为了常规自检强行启动
- **适用范围**:当前主落地为 公司(Linux)
- **升级风险点**:`dist/server.impl-*.js` 结构变化;新增代理模块注入位变化
- **失效判断**:在用户明确启用 NVIDIA 音频桥后,TTS/ASR 路由变回 404/502,或 gateway 升级后补丁丢失;若 service 处于 `disabled + inactive`,视为可选支路待命而不是系统错误
- **最小验收**:仅在需要启用时按 README 做 `/health`、TTS、ASR 三步验证;常规系统自检只确认脚本/README/service 模板存在且不会影响主 gateway
- **维护落点**:
  - `scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
  - `tools/nvidia-audio-bridge/README.md`
  - `docs/公司-Linux-OpenClaw-维护说明.md`

### PATCH-BOOT-HEALTH-CHECK

- **结果目标**：Gateway 启动后自动扫描核心服务/定时器/磁盘/内存/端口，缺失服务自动拉起，问题回报前台
- **当前实现**：`scripts/openclaw-boot-health-check.py` + systemd oneshot 服务 `openclaw-boot-health-check.service`
- **自动触发**：`BOOT.md` 启动流程 — 先跑 post-upgrade self-check → 再跑 boot-health-check → 带结果上线
- **适用范围**：通用（当前主落地为 公司（Linux））
- **升级风险点**：systemd unit 文件被移除；`BOOT.md` 启动流程被覆盖
- **失效判断**：`systemctl --user show openclaw-boot-health-check.service` 无输出或状态异常；启动消息中无体检摘要
- **最小验收**：
  - `systemctl --user start openclaw-boot-health-check.service` 正常返回
  - `python3 scripts/openclaw-boot-health-check.py --print-human` 无报错，列出服务/定时器/磁盘/内存/端口状态
- **维护落点**：
  - `scripts/openclaw-boot-health-check.py`
  - `tools/openclaw-boot-health-check/`
  - `~/.config/systemd/user/openclaw-boot-health-check.service`
  - `BOOT.md`
  - `TOOLS.md`

### PATCH-LANGUAGE-LOCK

- **结果目标**:无论主会话切换什么模型(DeepSeek / GLM / Kimi / NVIDIA 等),所有回复必须锁定为中文,不出现英文回复。
- **当前实现**:`SOUL.md` 顶部双语硬约束段落 + 底部精简引用
- **自动触发**:每次会话启动时 SOUL.md 作为 system prompt 注入,无需额外触发
- **适用范围**:通用
- **升级风险点**:如果 OpenClaw 更改 system prompt 组装方式或 contextInjection 行为,顶部规则仍会随 SOUL.md 注入
- **失效判断**:切换模型后出现英文回复即视为失效;检查 SOUL.md 第一段是否仍为双语语言锁定规则
- **最小验收**:用至少两种不同模型各发一条中文问题,验证回复均为中文
- **维护落点**:
  - `SOUL.md`(顶部段落 + 底部引用)
  - 若 OpenClaw 后续提供 `systemPromptOverride` 或预处理 hook,可进一步加固

---

## 当前使用规则

- 新补丁只有满足下面三条,才算进入注册表:
  1. 有明确的**结果目标**
  2. 有稳定的**实现入口**
  3. 有可复跑的**最小验收**
- 如果只是临时手工改一次当前文件、还没有自动触发或正式补丁入口，不应直接算正式注册补丁。
- 大版本升级后，先按本表逐项检查"结果是否还在"，不要只看文件是否改过。

### PATCH-DAILY-TRANSCRIPT-AGGREGATOR

- **结果目标**：无论用户切换哪个模型，当天所有模型的对话记录都会自动汇集到 `memory/daily/YYYY-MM-DD-transcript.md`；新模型启动时必读此文件，不再出现"换模型后发现昨天对话不见了"的情况。
- **当前实现**：`scripts/aggregate-daily-transcript.py` + `scripts/openclaw-lifecycle-maintainer.py` 子检查
- **自动触发**：`openclaw-lifecycle-maintainer.timer`;旧 `daily-transcript-aggregator.timer` 已被 Watcher v2 合并,默认不再启用
- **适用范围**：通用（当前主落地为 公司（Linux））
- **升级风险点**：OpenClaw session JSONL 格式变化；sessions.json 结构变化；路径变化
- **失效判断**：`memory/daily/YYYY-MM-DD-transcript.md` 超过 20 分钟不更新；`openclaw-lifecycle-maintainer.timer` 未启用或未运行
- **最小验收**：运行 `python3 scripts/aggregate-daily-transcript.py --print | head -20` 应有输出；`systemctl --user show openclaw-lifecycle-maintainer.timer -p UnitFileState -p ActiveState -p SubState` 应返回 `enabled` + `active` + `waiting`；检查 `memory/daily/$(date +%Y-%m-%d)-transcript.md` 存在且内容不空
- **维护落点**：
  - `scripts/aggregate-daily-transcript.py`
  - `tools/daily-transcript-aggregator/README.md`（历史说明,当前由 lifecycle-maintainer 承载）
  - `scripts/openclaw-lifecycle-maintainer.py`
  - `tools/openclaw-watchers/openclaw-lifecycle-maintainer.service`
  - `tools/openclaw-watchers/openclaw-lifecycle-maintainer.timer`
  - `~/.config/systemd/user/openclaw-lifecycle-maintainer.service`
  - `~/.config/systemd/user/openclaw-lifecycle-maintainer.timer`
  - `AGENTS.md`（第 5 步）
  - `scripts/openclaw-post-upgrade-self-check.py`（`check_daily_transcript_aggregator()`）
  - `TOOLS.md`

### PATCH-RESPONSIVENESS-WATCHDOG

- **结果目标**：当用户在主会话发消息后，模型超过阈值时间仍未回复时，自动向主会话注入提醒（30s 提醒 / 60s 紧急），不依赖模型自身响应能力。
- **当前实现**：`scripts/openclaw-responsiveness-watch.py` 作为 `scripts/openclaw-frontstage-guardian.py` 子检查承载;旧独立 systemd timer 已被 Watcher v2 合并
- **自动触发**：`openclaw-frontstage-guardian.timer`（内部调用 responsiveness 子检查）;当前不再启用旧 `openclaw-responsiveness-watch.timer`
- **适用范围**：通用（当前主落地为 公司（Linux））
- **升级风险点**：
  - dashboard session transcript 嵌套格式变化（`{"type":"message","message":"..."}` 结构）
  - infos-handle contract 的 `build_handle_request_payload` / `invoke_handle_request` API 变化
  - `sessions.json` 结构与 session key 命名规则变化
  - infos-handle 脚本路径或引入方式变化
- **失效判断**：`openclaw-frontstage-guardian.timer` 未启用或未运行；guardian 输出中 responsiveness 子检查报错或长期不更新
- **最小验收**：
  - `systemctl --user show openclaw-frontstage-guardian.timer -p UnitFileState -p ActiveState -p SubState` 返回 `enabled` + `active` + `waiting`
  - `python3 scripts/openclaw-frontstage-guardian.py --print-human` 输出 `OK` 或明确检测结果（不报错）
- **维护落点**：
  - `scripts/openclaw-responsiveness-watch.py`
  - `tools/openclaw-responsiveness-watch/README.md`（历史说明/子模块参考）
  - `scripts/openclaw-frontstage-guardian.py`
  - `tools/openclaw-watchers/openclaw-frontstage-guardian.service`
  - `tools/openclaw-watchers/openclaw-frontstage-guardian.timer`
  - `~/.config/systemd/user/openclaw-frontstage-guardian.service`
  - `~/.config/systemd/user/openclaw-frontstage-guardian.timer`
  - `scripts/openclaw-post-upgrade-self-check.py`
  - `TOOLS.md`

### PATCH-WATCHER-V2

- **结果目标**：watcher 体系从 7 timer 精简为 5，broker 从盲重建改为事件驱动（dirty flag），监工管理统一到 health-collector，guardian 异常时紧急触发 broker 刷新，ChatTTS 清理并入 lifecycle-maintainer，flush memory 自动同步到 daily 归档。
- **当前实现**：
  - `scripts/openclaw-health-collector.py`（含 _auto_manage_supervisor + dirty flag 检查 + 耗时基线）
  - `scripts/openclaw-task-scheduler.py`（已移除监工管理代码）
  - `scripts/openclaw-frontstage-guardian.py`（紧急通道 _mark_broker_dirty）
  - `scripts/openclaw-lifecycle-maintainer.py`（含 ChatTTS 清理 + flush 同步）
  - `scripts/flush-memory-sync.sh`
- **自动触发**：systemd timer（health-collector 60s, task-scheduler 60s, guardian 20s, lifecycle-maintainer 15min, resume-watch）
- **适用范围**：通用（当前主落地为 公司（Linux））
- **升级风险点**：watcher 脚本被覆盖（workspace 中，不受 OpenClaw 升级影响）；systemd timer 被禁用；broker dirty flag 路径变化
- **失效判断**：timer 数量回到 7；broker 每次周期都重建（dirty flag 失效）；监工管理出现双入口（task-scheduler 又出现 supervisor 管理日志）
- **最小验收**：`systemctl --user list-timers 'openclaw-*' --no-pager | grep -c "openclaw"` 应为 5；`python3 scripts/openclaw-health-collector.py --print-human` 正常输出；查看 `health-collector` 日志中应出现 "broker rebuild skipped" 或 "broker rebuild triggered by dirty flag"，而非每次都重建
- **维护落点**：
  - `scripts/openclaw-health-collector.py`
  - `scripts/openclaw-task-scheduler.py`
  - `scripts/openclaw-frontstage-guardian.py`
  - `scripts/openclaw-lifecycle-maintainer.py`
  - `scripts/flush-memory-sync.sh`
  - `~/.config/systemd/user/openclaw-health-collector.*`
  - `~/.config/systemd/user/openclaw-task-scheduler.*`
  - `~/.config/systemd/user/openclaw-frontstage-guardian.*`
  - `~/.config/systemd/user/openclaw-lifecycle-maintainer.*`
  - `TOOLS.md`

### PATCH-SEARCH-SHORTCIRCUIT

- **结果目标**：memory_search 不再每次走云端 github-copilot（4-10s），先经本地关键词预搜（0.1s），置信度 ≥ 0.7 直接返回；重复查询走 60s TTL 缓存零开销。
- **当前实现**：`scripts/memory-search-local-first.py` + `scripts/query-cache.py` + AGENTS.md 三级搜索规则
- **自动触发**：AGENTS.md 规则引导 agent 行为；本地脚本无需 systemd
- **适用范围**：通用
- **升级风险点**：AGENTS.md 规则被覆盖；记忆文件结构变化导致分词策略失效；缓存文件路径变化
- **失效判断**：`python3 scripts/memory-search-local-first.py "贾维斯"` 返回 `shortCircuited: false`（正常应 true）；缓存文件无新条目
- **最小验收**：`python3 scripts/memory-search-local-first.py "贾维斯"` → `shortCircuited: true, confidence >= 0.7`；`python3 scripts/memory-search-local-first.py "xyz不存在的词"` → `shortCircuited: false`；`python3 scripts/query-cache.py stats` → 正常返回 JSON
- **维护落点**：
  - `scripts/memory-search-local-first.py`
  - `scripts/query-cache.py`
  - `AGENTS.md`（memory_search 三级搜索策略段）
  - `~/.local/state/openclaw/cache/query-cache.json`
  - `TOOLS.md`

### PATCH-TASK-SCHEDULER-IDLE

- **结果目标**：task-scheduler 在无活跃任务时跳过全量扫描，仅做 0.1s SQLite 快速预检；有任务时才全量扫描。消除 95%+ 的无效周期开销。
- **当前实现**：`scripts/openclaw-task-scheduler.py`（新增 _quick_count_tasks + 快速预检跳过逻辑）
- **自动触发**：systemd timer（`openclaw-task-scheduler.timer`，60s）
- **适用范围**：通用（当前主落地为 公司（Linux））
- **升级风险点**：runs.sqlite 表结构变化导致 COUNT 查询失败；脚本被覆盖（workspace 中）
- **失效判断**：即便无活跃任务，日志仍显示每次全量扫描（而非 "idle, skipping full scan"）；dry-run 不输出 "idle - fast skip"
- **最小验收**：`python3 scripts/openclaw-task-scheduler.py --dry-run --print-human` → 输出 "idle - fast skip"（当前无活跃任务）
- **维护落点**：
  - `scripts/openclaw-task-scheduler.py`
  - `~/.config/systemd/user/openclaw-task-scheduler.*`
  - `TOOLS.md`

### PATCH-LATENCY-BASELINE

- **结果目标**：health-collector 每次子检查记录耗时，超过基线自动标 ⚠DEGRADED 并附带原因。在 guardian 发现异常前提前预警。
- **当前实现**：`scripts/openclaw-health-collector.py`（DURATION_BASELINE_MS + 汇总前基线检查逻辑）
- **自动触发**：health-collector timer（60s）
- **适用范围**：通用（当前主落地为 公司（Linux））
- **升级风险点**：脚本被覆盖导致基线表丢失
- **失效判断**：报告 checks 中无 `elapsedMs` 字段；超基线项未被标 degraded
- **最小验收**：`python3 scripts/openclaw-health-collector.py --print-json | python3 -c "import json,sys; r=json.load(sys.stdin); assert all('elapsedMs' in c for c in r['checks'])"` 应通过且无误
- **维护落点**：
  - `scripts/openclaw-health-collector.py`
  - `TOOLS.md`
