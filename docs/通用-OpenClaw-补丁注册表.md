# OpenClaw 补丁注册表

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：跨机器共享的补丁索引 / 迁移注册表

## 用途

这份注册表不是简单记录“改过哪些文件”，而是记录：

- 每个正式补丁想保证的**结果**
- 当前通过什么**实现链路**达成
- 它依赖哪些**自动触发**或重打入口
- 升级后如何判断它是否仍然生效
- 如果上游大版本变化导致失效，后续该去哪里续接

一句话目标：

> 即使 OpenClaw 大版本改动了，也能按这份表逐项恢复“结果不变”的补丁能力，而不是重新靠记忆猜我们以前做过什么。

---

## 字段说明

| 字段 | 含义 |
|---|---|
| Patch ID | 稳定标识，便于跨文档引用 |
| 结果目标 | 用户真正想要的效果 |
| 当前实现 | 现在用什么脚本 / 配置 / service 达成 |
| 自动触发 | 是否在 gateway 启动前或 systemd timer 中自动生效 |
| 适用范围 | 通用 / 公司（Linux）/ 掌机（Windows）等 |
| 升级风险点 | 大版本最可能破坏哪一层 |
| 失效判断 | 怎么快速判断这条补丁是不是掉了 |
| 最小验收 | 如何做一轮最小回归 |
| 维护落点 | 需要优先查看/续改的文件 |

---

## 注册表

### PATCH-POST-UPGRADE-SELF-CHECK

- **结果目标**：当 OpenClaw 版本变化并重新打开后，主动按统一自检清单核对关键补丁 / broker / recovery watcher 是否仍正常；版本未变时不重复刷屏。
- **当前实现**：`scripts/openclaw-post-upgrade-self-check.py` + `BOOT.md`
- **自动触发**：`BOOT.md` + `boot-md` hook（启动时先跑脚本，再按输出消息上线）
- **适用范围**：通用
- **升级风险点**：boot hook 行为变化；package 版本检测入口变化；systemd / dist 路径变化
- **失效判断**：OpenClaw 更新后再次打开，没有主动给出升级后自检结果；或脚本无法识别版本变化；或明明版本变化却没有触发自检
- **最小验收**：运行 `python3 scripts/openclaw-post-upgrade-self-check.py --force --print-human`，应能完成清单核对并输出通过/失败摘要；运行 `python3 scripts/openclaw-post-upgrade-self-check.py --print-boot-json`，应返回包含 `bootMessage` 的 JSON
- **维护落点**：
  - `docs/通用-OpenClaw-升级后自检清单.md`
  - `scripts/openclaw-post-upgrade-self-check.py`
  - `BOOT.md`
  - `TOOLS.md`

### PATCH-CTRLUI-BRANDING

- **结果目标**：Control UI 左上角品牌、浏览器标题、图标、页面内可见 OpenClaw 品牌尽量统一替换为“贾维斯”风格。
- **当前实现**：`scripts/apply-openclaw-control-ui-branding.py`
- **自动触发**：`~/.config/systemd/user/openclaw-gateway.service.d/branding.conf` 的 `ExecStartPre`
- **适用范围**：当前主落地为 公司（Linux）
- **升级风险点**：`dist/control-ui/` 前端结构 / `index.html` 注入点变化
- **失效判断**：Control UI 刷新后重新出现大量默认 `OpenClaw` 品牌文案
- **最小验收**：运行 `python3 scripts/apply-openclaw-control-ui-branding.py` 后，确认输出成功；刷新页面后品牌名/标题仍为“贾维斯”
- **维护落点**：
  - `scripts/apply-openclaw-control-ui-branding.py`
  - `config/control-ui-branding.json`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-CTRLUI-RUNNING-SIGNAL

- **结果目标**：只要聊天页后台 run 还没真结束，前台尽量持续显示“进行中/活着信号”，并减少 assistant silent/empty final 时“前台刚有阶段性内容又被立即清掉”的 ghost/disappear 体感；若 `sessions_yield` 已经产出 `message`，也尽量把它稳定留成前台可见文本，而不是让“三个点消失了但没回字”。
- **当前实现**：并入 `scripts/apply-openclaw-control-ui-branding.py`，重打 `dist/control-ui/assets/index-*.js`
- **自动触发**：同 `PATCH-CTRLUI-BRANDING`，随 gateway 启动前自动重打
- **适用范围**：当前主落地为 公司（Linux）
- **升级风险点**：聊天页前端状态机构造变化，`sI(...)` 或等价逻辑重构
- **失效判断**：tool 阶段 / history reload / active run 明显仍在进行时，前台不流字也不转圈；或 `sessions_yield` 明明已经给了 `message`，前台却出现“三个点消失但没回字”
- **最小验收**：确认补丁后的条件仍覆盖 `loading / sending / stream / canAbort / queue.length > 0 / session.hasActiveRun / session.status=running`，并确认 `u&&!o&&!a){Gl(e);return}` 这条“silent final 立刻 reload”旧分支已不再存在；再确认前端资产里已带 `JarvisProjectYieldedHistoryReply`，并能把 `yielded toolResult` 里的 `message` 补投影成 assistant 可见文本
- **维护落点**：
  - `scripts/apply-openclaw-control-ui-branding.py`
  - `docs/公司-Linux-OpenClaw-维护说明.md`
  - `TOOLS.md`

### PATCH-FRONTSTAGE-BROKER

- **结果目标**：把监工、本地健康、前台恢复观察等辅助消息统一收口后，再稳定投递到“当前前台 dashboard”，并沉淀成统一 snapshot 口径的 sidecar 数据源，供 renderer / dock 等消费方直接复用；`overview` / `frontstage-status.json` 等旧名字只保留为兼容层。
- **当前实现**：`scripts/openclaw-frontstage-broker.py` + `scripts/openclaw-infos-handle.py` + `scripts/apply-openclaw-frontstage-broker-data.py`
- **自动触发**：由 `supervisor` / `local-health` / `frontstage-recovery` 等调用方间接触发；当前另外有 `openclaw-frontstage-broker-rebuild.service` + `openclaw-frontstage-broker-rebuild.timer` 周期刷新视图
- **适用范围**：当前主落地为 公司（Linux）
- **升级风险点**：`openclaw-supervisor-subagent.py send-frontstage` 调用约定变化；`chat.inject` 路由变化；broker 视图模型与事件契约从“纯 delivery”演进为“source + delivery 双记录”后的兼容性；`infos-handle` 与 broker CLI 参数约定变化
- **失效判断**：辅助消息仍回到旧 dashboard，或 `broker-state.json` / `events.jsonl` / `views/*.json` 不再更新；或 `events.jsonl` 里不再出现 `broker.source.event`；或 `openclaw-infos-handle.py query` 不能正常返回 text/json
- **最小验收**：执行 `python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock` 应成功；执行一次 `ingest` 烟测后，确认 `~/.local/state/openclaw/broker/events.jsonl` 出现 `broker.source.event`；执行 `python3 scripts/openclaw-infos-handle.py query --kind snapshot.summary --format text` 应能正常返回；`views/snapshot.json` 与 `jarvis-frontstage-snapshot.json` 已刷新，`manifest.json` / `snapshot.json` 都声明 `snapshotContract.primaryView = snapshot`，并把 `overview` / `frontstage-status.json` 标成 `legacy_alias`、把 `frontstage / health / tasks / recovery` 标成 `supporting_view`；apply 输出里的 `controlUiSnapshotDock.snapshotJsonHref` 应指向 `/jarvis-frontstage-snapshot.json`，`frontstagePublication.snapshotFirstReady` 应为 `true`；`openclaw-frontstage-broker-rebuild.timer` 处于 `enabled + active(waiting)`
- **维护落点**：
  - `scripts/openclaw-frontstage-broker.py`
  - `scripts/test-frontstage-broker.py`
  - `scripts/openclaw-infos-handle.py`
  - `scripts/test-openclaw-infos-handle.py`
  - `scripts/apply-openclaw-frontstage-broker-data.py`
  - `scripts/openclaw-supervisor-subagent.py`
  - `tools/openclaw-frontstage-broker/README.md`
  - `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service`
  - `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer`
  - `~/.config/systemd/user/openclaw-frontstage-broker-rebuild.service`
  - `~/.config/systemd/user/openclaw-frontstage-broker-rebuild.timer`
  - `~/.local/state/openclaw/frontstage/broker-state.json`
  - `~/.local/state/openclaw/broker/`

### PATCH-SUPERVISOR-AUTO-NOTIFY

- **结果目标**：监工状态在 `stalled / failed / done` 变化时，自动经由 broker 回前台，并能跟随当前 dashboard 页面。
- **当前实现**：`scripts/openclaw-supervisor-status.py --notify-transitions`
- **自动触发**：`openclaw-supervisor-watch.service` + `openclaw-supervisor-watch.timer`
- **适用范围**：当前主落地为 公司（Linux）
- **升级风险点**：task 状态模型变化；frontstage 解析规则变化；broker `emit` 返回结构（尤其 `messageId` 字段位置）变化
- **失效判断**：`notify-state.json` 不更新、事件日志无 `notify_sent`、前台无监工摘要；或摘要误落回 `agent:main:main` 而不是当前 dashboard；或日志里的 `messageId` 异常为 `null`
- **最小验收**：人工烟测一次 `done / failed / stalled` 任务，并确认前台收到对应摘要；`notify_sent` 日志里的 `target=` 应指向当前 dashboard，且 `messageId` 为真实注入消息 id
- **维护落点**：
  - `scripts/openclaw-supervisor-status.py`
  - `tools/openclaw-supervisor/README.md`
  - `~/.local/state/openclaw/supervisor/notify-state.json`

### PATCH-LOCAL-HEALTH-FRONTSTAGE

- **结果目标**：本地健康在 `warn / critical / recovered` 变化时，经由 broker 回前台一条简明辅助摘要，但不周期性“报平安”。
- **当前实现**：`scripts/openclaw-local-health-diagnose.py --notify-frontstage`
- **自动触发**：`openclaw-local-health-watch.service` + `openclaw-local-health-watch.timer`
- **适用范围**：当前主落地为 公司（Linux）
- **升级风险点**：local-health 状态摘要结构变化；broker 接口变化
- **失效判断**：健康状态变化时 `transition-state.json` 更新，但前台和 broker state 没有对应消息
- **最小验收**：人为造一次 `warn -> ok` 恢复烟测，确认 broker state 出现 `local-health` 的 recovered 记录
- **维护落点**：
  - `scripts/openclaw-local-health-diagnose.py`
  - `tools/openclaw-local-health/README.md`
  - `~/.local/state/openclaw/local-health/transition-state.json`

### PATCH-FRONTSTAGE-RECOVERY-WATCH

- **结果目标**：周期对比 durable transcript 与 `chat.history` 投影，尽早发现“主回复前台没稳定留下 / 投影异常”的情况，并在 anomaly / recovered 变化时经由 broker 回前台。
- **当前实现**：`scripts/openclaw-frontstage-recovery-watch.py`
- **自动触发**：`openclaw-frontstage-recovery-watch.service` + `openclaw-frontstage-recovery-watch.timer`
- **适用范围**：当前主落地为 公司（Linux）
- **升级风险点**：`chat.history` 投影规则变化；`sessions.list` 状态字段变化；前端 optimistic-tail 行为变化
- **失效判断**：`last-report.json` 停更；明明出现 anomaly/recovered，`notify-state.json` 和事件日志不变；或频繁误报
- **最小验收**：运行 `python3 scripts/test-frontstage-recovery-watch.py` 应全部通过；service/timer 应正常运行
- **维护落点**：
  - `scripts/openclaw-frontstage-recovery-watch.py`
  - `scripts/test-frontstage-recovery-watch.py`
  - `tools/openclaw-frontstage-recovery/README.md`
  - `~/.local/state/openclaw/frontstage-recovery/`

### PATCH-NVIDIA-AUDIO-GATEWAY-BRIDGE

- **结果目标**：让当前机器的 OpenClaw gateway 暴露 NVIDIA 音频代理接口（TTS / ASR），并保持主 gateway 继续稳定运行。
- **当前实现**：`scripts/apply-openclaw-nvidia-audio-gateway-patch.py` + `tools/nvidia-audio-bridge/bridge.py`
- **自动触发**：当前依赖手工补丁重打；bridge 本身由用户态 systemd 运行
- **适用范围**：当前主落地为 公司（Linux）
- **升级风险点**：`dist/server.impl-*.js` 结构变化；新增代理模块注入位变化
- **失效判断**：TTS/ASR 路由变回 404/502，或 gateway 升级后补丁丢失
- **最小验收**：按 README 做 `/health`、TTS、ASR 三步验证
- **维护落点**：
  - `scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
  - `tools/nvidia-audio-bridge/README.md`
  - `docs/公司-Linux-OpenClaw-维护说明.md`

---

## 当前使用规则

- 新补丁只有满足下面三条，才算进入注册表：
  1. 有明确的**结果目标**
  2. 有稳定的**实现入口**
  3. 有可复跑的**最小验收**
- 如果只是临时手工改一次当前文件、还没有自动触发或正式补丁入口，不应直接算正式注册补丁。
- 大版本升级后，先按本表逐项检查“结果是否还在”，不要只看文件是否改过。
