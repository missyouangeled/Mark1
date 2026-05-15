# OpenClaw Frontstage Broker

- 适用机器：公司（Linux）（脚本本身也可给其他 Linux 机器复用）
- 系统 / OS：Linux
- 用途：统一接收辅助消息来源（如 `supervisor` / `local-health` / `frontstage-recovery`），完成去重、前台投递，并在当前阶段顺手把这些消息沉淀成可供后续 renderer 消费的 sidecar 数据源。

## 当前产物

- broker 脚本：`scripts/openclaw-frontstage-broker.py`
- broker 最小回归：`scripts/test-frontstage-broker.py`
- infos-handle 最小入口：`scripts/openclaw-infos-handle.py`
- infos-handle 最小回归：`scripts/test-openclaw-infos-handle.py`
- broker 数据层 apply 入口：`scripts/apply-openclaw-frontstage-broker-data.py`
- broker 周期重建 systemd 模板：`tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service` / `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer`

## 当前状态文件

### 旧状态（兼容现有链路）

- `~/.local/state/openclaw/frontstage/broker-state.json`

用途：

- 继续保存按 `source` 聚合后的最近一次已发事件
- 保持现有 dedupe / frontstage 投递链路不被打断

### 新数据源（当前阶段新增）

- `~/.local/state/openclaw/broker/events.jsonl`
- `~/.local/state/openclaw/broker/manifest.json`
- `~/.local/state/openclaw/broker/views/frontstage.json`
- `~/.local/state/openclaw/broker/views/health.json`
- `~/.local/state/openclaw/broker/views/tasks.json`
- `~/.local/state/openclaw/broker/views/recovery.json`
- `~/.local/state/openclaw/broker/views/snapshot.json`（正式顶层口径）
- `~/.local/state/openclaw/broker/views/overview.json`（兼容别名，内容与 `snapshot.json` 一致）
- `~/.openclaw/canvas/documents/frontstage-status/index.html`
- `~/.openclaw/canvas/documents/frontstage-status/status.json`（兼容别名）
- `~/.openclaw/canvas/documents/frontstage-status/snapshot.json`（正式公开快照）
- `dist/control-ui/jarvis-frontstage-status.html`
- `dist/control-ui/jarvis-frontstage-status.json`（兼容别名）
- `dist/control-ui/jarvis-frontstage-snapshot.json`（正式公开快照）

用途：

- `events.jsonl`：append-only 结构化事件流（当前阶段同时记录 broker 已收下的 source 事件，以及已完成的前台投递事件）
- `views/frontstage.json`：按 source 汇总后的统一前台快照；现在明确降级为**支撑视图**，供 `snapshot` 组装，不再当顶层主入口
- `views/health.json`：`local-health` 的最新视图；同样是支撑视图，不再当顶层主入口
- `views/tasks.json`：当前先汇总 `supervisor` / `frontstage-recovery`；同样是支撑视图，不再当顶层主入口
- `views/recovery.json`：`frontstage-recovery` 的最新视图；同样是支撑视图，不再当顶层主入口
- `views/snapshot.json`：当前统一 snapshot 顶层口径，给 renderer / 前端状态面板直接消费
- `views/overview.json`：当前保留的兼容别名，内容与 `snapshot.json` 一致；后续入口默认不应再把它当正式主口径
- `frontstage-status/index.html` + `jarvis-frontstage-status.html`：当前 broker sidecar 的前端状态页（canvas 版 + Control UI 公共静态副本）；现在会优先用 `sourceView` / `sourceEventType` 这些正式契约字段渲染“最近辅助投递”，不再只靠原始 `source` 名猜语义
- `frontstage-status/snapshot.json` + `jarvis-frontstage-snapshot.json`：给 dock / 轻量消费方优先读取的统一 snapshot 公共副本
- `frontstage-status/status.json` + `jarvis-frontstage-status.json`：当前仅保留为兼容别名，内容与对应 snapshot 文件一致

## 事件契约（当前正式口径）

本轮开始，broker sidecar 对外默认提供一套最小正式事件口径，避免 renderer / 排查脚本继续只靠 `source` 名临场猜语义。

同时，这一轮也开始把 broker 往“数据中心优先”推进：

- `ingest`：只入 broker 数据层，不直接打前台
- `emit`：兼容旧链路，仍会打前台
- `infos-handle`：作为 broker 与消费方之间的最小信息处理层，当前先支持 text/json 查询与前台通知

### 1. `events.jsonl` 的正式含义

`events.jsonl` 现在是一个**统一 broker 事件流**，当前至少包含两类记录：

#### A. `broker.source.event`

表示 broker 已经把某个来源事件收下并写入数据层，但**还没有要求它一定打到前台**。

最小字段：

- `recordType = broker.source.event`
- `source`
- `sourceEventType`
- `sourceView`
- `eventKey`
- `sessionKey`
- `message`
- `recordedAt`
- `data`（可选，给来源事件带结构化附加信息）

#### B. `frontstage.delivery.sent`

表示 broker 或 infos-handle 已经成功完成了一次前台投递。

最小字段：

- `recordType = frontstage.delivery.sent`
- `source`
- `sourceEventType`
- `sourceView`
- `eventKey`
- `sessionKey` / `targetSessionKey` / `messageId` / `message` / `sentAt` / `recordedAt`

因此当前的口径变成：

- 要看“来源事件先后发生了什么” → 读 `broker.source.event`
- 要看“哪些内容真正打到前台了” → 读 `frontstage.delivery.sent`

### 2. `views/frontstage.json` 里的两组快照

`frontstage.json` 里现在分成两组快照：

#### A. `sources.<name>`

表示：

- `recordType = frontstage.delivery.latest`
- 这是该 source **最近一次已成功投递** 的快照

#### B. `sourceStates.<name>`

表示：

- `recordType = broker.source.latest`
- 这是该 source **最近一次已被 broker ingest** 的来源事件快照
- 即使当前没有前台 renderer、没有 Control UI、或者本轮没有发生前台投递，这组快照也应能独立存在

因此当前建议读取顺序是：

- 要看 append-only 历史 → 读 `events.jsonl`
- 要看每个 source 最近一次前台已发事件 → 读 `views/frontstage.json` 的 `sources`
- 要看每个 source 最近一次被 broker 收下的来源状态 → 读 `views/frontstage.json` 的 `sourceStates`

### 3. 当前已正式收口的 source → event type 映射

- `local-health` → `local_health.status.changed` → `health`
- `supervisor` → `supervisor.status.changed` → `tasks`
- `frontstage-recovery` → `frontstage_recovery.status.changed` → `recovery`

此外，`frontstage.json` / `health.json` / `tasks.json` / `recovery.json` / `snapshot.json` / `overview.json` / `manifest.json` 现在都会带：

- `contractVersion`
- `contracts`

其中 `snapshot.json` / `overview.json` / `manifest.json` 还会额外带：

- `snapshotContract`
  - 明确声明：`snapshot` 是正式主视图
  - `overview` / `frontstage-status.json` 这类名字当前只是兼容别名
  - `viewCatalog` 会把 `snapshot` 标成 `primary`，把 `overview` 标成 `legacy_alias`，并把 `frontstage / health / tasks / recovery` 明确标成 `supporting_view`
  - `publishedJsonCatalog` 会把 `jarvis-frontstage-snapshot.json` / `snapshot.json` 标成 `primary`，把 `jarvis-frontstage-status.json` / `status.json` 标成 `legacy_alias`
- `manifest.json` 还会额外带 `artifacts`
  - 用实际路径把这些 view / published JSON 的主入口、支撑视图、兼容别名关系再落一遍，减少后续排查时继续把旧名字误当正式入口

`rebuild-views` 也会顺手把历史 `events.jsonl` 里缺失这些正式字段的旧记录补齐到当前口径；因此后续 renderer / 排查脚本应优先读这些正式字段，而不是自行猜 `source` 的语义。

当前已落地的真实消费方有两类：

1. `jarvis-frontstage-status.html` 这条状态页链路会直接读取 broker 契约字段，把 `sourceView` 作为主分组语义、把 `sourceEventType` 作为事件语义说明，再保留原始 `source` 作为排查辅助信息；与它同名的 `status.json` 当前只再作为兼容别名保留。
2. Control UI 顶部“前台状态”小入口 / dock 现在优先读取 `jarvis-frontstage-snapshot.json`，并按统一 snapshot 顶层口径取 `summary / issueOverview / selfHelpActions / panels.*`；live `jarvis-branding-override.js` 里也会显式同时保留 `snapshotJsonHref`（正式入口）与 `legacyStatusJsonHref`（兼容别名），避免旧 `statusJsonHref` 字段名继续表现得像主入口；`jarvis-frontstage-status.json` 只再作为兼容别名保留，不应继续作为新的正式入口。
3. `infos-handle` 当前已经可以把 broker 视图整理成稳定 text/json 查询；JSON 响应里带 `queryContractVersion=10` 与 `result` 字段，消费方不必直接啃整份 snapshot。
4. `infos-handle query --kind sources.latest` 现在除了保留原始 `sourceStateSnapshots / sources` keyed snapshot 外，也会额外暴露 `count / availableSources / sourceItems[]`；其中每个 `sourceItems[]` item 会与 `sources.catalog / source.inspect` 对齐，稳定带出 `latestEventSummary / latestEventItem / latestDeliveryMessage / latestSourceStateSummary` 等字段，减少消费方自己翻 raw broker event。
5. `infos-handle query --kind sources.catalog` 现在会返回 machine-readable source inventory（来源契约、是否已有 ingest 快照、是否已有 frontstage delivery），并补齐 `latestEventSummary / latestEventKey / latestDeliveryEventKey / latestDeliveryRecordType` 这类稳定顶层摘要字段；同时新增 `latestEventItem`，把最近一条来源事件压平成稳定 item shape，减少消费方自己拼 `recordType / summary / checkedAt / status` 的工作。
6. `infos-handle query --kind source.inspect` 也会稳定暴露 `recentDeliveryCount`、`latestEventItem` 与 `recentEventItems[]`；handoff / 排查脚本优先读取这些 item shape，就不必直接解析 `recentEvents[]` 或 `latestDelivery` 原始对象。
7. `infos-handle query --kind panels.catalog` 现在会返回稳定的 panel inventory（`panelName / available / summary / severity / checkedAt` 等字段），`contract.catalog` 也会同时公开每个 query kind 的参数/格式约束，方便其他机器先读契约再发请求。

## 当前阶段边界

当前 broker 升级只做到：

1. 保持现有 `emit` 行为不变
2. 在每次成功投递后，把事件写入 `events.jsonl`
3. 顺手生成可读视图文件，作为 sidecar 数据层的第一步
4. 支持 `rebuild-views`，可从现有 source 状态文件与兼容 `broker-state.json` 重建当前视图
5. 在重建视图时顺手生成统一 `snapshot.json`（并保留 `overview.json` 兼容别名）与前端状态页，作为 broker 的第一版 renderer 输入
6. 当前已补上用户态 systemd timer，可周期重建视图，降低“长时间无新辅助消息时视图逐渐变旧”的风险

当前**还没有**做：

- 独立 HTTP / SSE / WebSocket 数据接口
- 图片 / 音频这类 richer output handler
- 强制让 Control UI 改为只读 infos-handle / broker
- 把工作层完全改造成 broker 硬依赖

## 手工运行

```bash
python3 scripts/openclaw-frontstage-broker.py ingest --source local-health --event-key local-health-smoke --session-key 'agent:main:main' --message '本地健康状态已记录' --data-json '{"severity":"ok"}' --print-json
python3 scripts/openclaw-frontstage-broker.py emit --source broker-smoke --event-key broker-smoke-readme --session-key 'agent:main:main' --message '[Broker README 烟测] frontstage broker 可用。' --print-json
python3 scripts/openclaw-frontstage-broker.py rebuild-views --print-json
python3 scripts/test-frontstage-broker.py
python3 scripts/test-openclaw-infos-handle.py
python3 scripts/openclaw-infos-handle.py query --kind snapshot.summary --format text
python3 scripts/openclaw-infos-handle.py query --kind sources.latest --format text
python3 scripts/openclaw-infos-handle.py query --kind sources.catalog --format json
python3 scripts/openclaw-infos-handle.py query --kind panels.catalog --format json
python3 scripts/openclaw-infos-handle.py query --kind source.inspect --source-name local-health --format json
python3 scripts/openclaw-infos-handle.py query --kind contract.catalog --format json
python3 scripts/apply-openclaw-frontstage-broker-data.py
python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock
python3 scripts/apply-openclaw-frontstage-broker-data.py --install-user-systemd
# 若只想手工装 timer，也可：
cp tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service ~/.config/systemd/user/
cp tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-frontstage-broker-rebuild.timer
```

## 当前验证口径

- `scripts/test-frontstage-broker.py` 应返回 `ALL PASS`
- `events.jsonl` 应出现非重复事件
- `manifest.json` 应存在，并列出当前 views 与 source 文件路径
- `views/frontstage.json` 应存在
- `views/snapshot.json` 应存在
- `views/overview.json` 应继续存在（兼容别名）
- `snapshot.json` / `manifest.json` 里的 `snapshotContract.primaryView` 应为 `snapshot`
- `snapshotContract.viewCatalog.snapshot.role` 应为 `primary`，`snapshotContract.viewCatalog.overview.role` 应为 `legacy_alias`，`snapshotContract.viewCatalog.frontstage` / `health` / `tasks` / `recovery` 应为 `supporting_view`
- `snapshotContract.publishedJsonCatalog.frontstageStatusJson.role` 应为 `legacy_alias`
- `manifest.json` 里的 `artifacts` 应把 `snapshot` 标成主入口、把 `overview` / `frontstage-status.json` 标成兼容别名
- 旧 `broker-state.json` 仍应继续更新
- `rebuild-views` 应能在不新增前台消息的前提下，直接把当前 source 状态重建成视图
- `jarvis-frontstage-status.html` / `jarvis-frontstage-status.json` / `jarvis-frontstage-snapshot.json` 应能随 rebuild 同步更新
- 若跑了 `--apply-control-ui-branding --verify-control-ui-snapshot-dock`，则应额外看到：
  - live `jarvis-branding-override.js` 的 `snapshotJsonHref = /jarvis-frontstage-snapshot.json`
  - live `jarvis-branding-override.js` 的 `legacyStatusJsonHref = /jarvis-frontstage-status.json`
  - `frontstagePublication.snapshotFirstReady = true`，证明 live 公开链路里 snapshot 是首选入口、status.json 只是兼容别名
- `scripts/apply-openclaw-frontstage-broker-data.py` 应能完成 py_compile + 测试 + rebuild-views 这一整套最小重装流程
- 若使用 `--install-user-systemd`，应额外输出已安装的 user systemd service/timer 路径
- `openclaw-frontstage-broker-rebuild.timer` 应处于 `enabled + active(waiting)`
- 若 `broker-state.json` 里已有 `local-health` / `frontstage-recovery`，即使这些来源不是本轮新发事件，也应能被回填到对应视图文件

## 边界与稳定性原则

- broker 当前仍应是 **sidecar 数据层**，不是 OpenClaw 主体的硬依赖
- 没有 broker 数据目录时，现有 OpenClaw 主链不应因此报错
- 当前阶段任何 broker 升级都必须优先保持现有 frontstage 投递能力不回退
- 未来若要继续往“真正数据层”推进，应优先沿这几个产物演进，而不是直接硬拆 Gateway / Control UI 主链
