# OpenClaw Frontstage Broker

- 适用机器：公司（Linux）（脚本本身也可给其他 Linux 机器复用）
- 系统 / OS：Linux
- 用途：统一接收辅助消息来源（如 `supervisor` / `local-health` / `frontstage-recovery`），完成去重、前台投递，并在当前阶段顺手把这些消息沉淀成可供后续 renderer 消费的 sidecar 数据源。
- 当前阶段收口判断：按本轮目标已到可称“最终版”的状态——`infos-handle handle` + `--request-file` + `openclaw_infos_handle_contract.py` helper 是正式主入口；`query` / `notify-frontstage` / broker `emit` 只保 compat 壳。

## 当前产物

- broker 脚本：`scripts/openclaw-frontstage-broker.py`
- broker 最小回归：`scripts/test-frontstage-broker.py`
- infos-handle 最小入口：`scripts/openclaw-infos-handle.py`
- infos-handle 最小回归：`scripts/test-openclaw-infos-handle.py`
- broker 数据层 apply 入口：`scripts/apply-openclaw-frontstage-broker-data.py`
- broker 周期重建 systemd 模板：`tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service` / `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer`
- infos-handle sidecar 说明与 service 模板：`tools/openclaw-infos-handle-sidecar/README.md` / `tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`

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
- `emit`：兼容旧链路，仍会打前台；当前实现上也已更明确地退成 compatibility wrapper（前台发送优先经 `infos-handle handle`，broker 自己只保 delivery 兼容记录，不建议继续给它加新能力）
- `infos-handle`：作为 broker 与消费方之间的最小信息处理层；当前除了 text/json 查询与前台通知外，也新增了统一 `handle` 请求入口，可正式处理 `text/json/image/audio` 四类输出（其中 `image/audio` 目前是 preview 级最小 handler）

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
  - 其中 `contracts.recordTypes` 会正式列出当前四类 broker 记录（`broker.source.event` / `frontstage.delivery.sent` / `frontstage.delivery.latest` / `broker.source.latest`）的 `description / requiredFields / optionalFields`
  - `contracts.eventFieldCatalog` 会收口 `sourceEventType / sourceView / eventKey / recordedAt / sentAt` 这些字段的正式语义，减少消费方继续靠 README 文本猜字段

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
2. Control UI 顶部“前台状态”小入口 / dock 现在会先尝试直连本地 infos-handle sidecar（默认 `http://127.0.0.1:18790/v1/query/snapshot.summary?format=json`，并可选订阅 `/v1/events/stream?kind=snapshot.summary` SSE），失败时再回退到 `jarvis-frontstage-snapshot.json`；live `jarvis-branding-override.js` 里会同时保留 `infosHandleSummaryHref / infosHandleContractHref / infosHandleSseHref`、`snapshotJsonHref`（正式静态回退）与 `legacyStatusJsonHref`（兼容别名），避免旧 `statusJsonHref` 字段名继续表现得像主入口；`jarvis-frontstage-status.json` 只再作为兼容别名保留，不应继续作为新的正式入口。
3. `infos-handle` 当前已经可以把 broker 视图整理成稳定 text/json 查询；JSON 响应里带 `queryContractVersion=17`、`format` 与 `result` 字段，消费方不必直接啃整份 snapshot。
4. source 相关 query 的推荐读取顺序现在明确为：先读 `sources.latest` 做轻量 inventory / handoff，再在需要原始快照或契约时读 `sources.catalog`，最后只对单个 source 深挖时再读 `source.inspect`。
5. `infos-handle query --kind sources.latest` 现在除了保留原始 `sourceStateSnapshots / sources` keyed snapshot 外，也会额外暴露 `count / availableSources / sourceItems[]`；其中每个 `sourceItems[]` item 会与 `sources.catalog / source.inspect` 对齐，稳定带出 `latestEventSummary / latestEventItem / latestDeliveryItem / latestDeliveryMessage / latestSourceStateSummary` 等字段，减少消费方自己翻 raw broker event。
6. `infos-handle query --kind sources.catalog` 现在会返回 machine-readable source inventory（来源契约、是否已有 ingest 快照、是否已有 frontstage delivery），并补齐 `latestEventSummary / latestEventKey / latestDeliveryEventKey / latestDeliveryRecordType` 这类稳定顶层摘要字段；同时新增 `latestEventItem / latestDeliveryItem`，把最近一条来源事件与最近一条投递都压平成稳定 item shape，减少消费方自己拼 `recordType / summary / checkedAt / status` 的工作。
7. `infos-handle query --kind source.inspect` 也会稳定暴露 `recentDeliveryCount`、`latestEventItem`、`latestDeliveryItem`、`recentEventItems[]` 与 `recentDeliveryItems[]`；handoff / 排查脚本优先读取这些 item shape，就不必直接解析 `recentEvents[]` 或 `latestDelivery` 原始对象。
8. `infos-handle query --kind panels.catalog` 现在会返回稳定的 panel inventory（`panelName / available / summary / severity / checkedAt` 等字段），`contract.catalog` 也会同时公开每个 query kind 的参数/格式约束，以及 `outputFormatCatalog`（当前 `text/json=ready`、`image/audio=preview`），方便其他机器先读契约再发请求。
9. `infos-handle query --kind contract.catalog` 现在除了 query catalog 之外，也会把 broker 自己的 `contracts.recordTypes / contracts.eventFieldCatalog` 原样带出；同时当前公开 `requestContractVersion=6`、`requestCatalog` 与 `handlerCatalog`，把统一 `handle` 入口、`request_json / request_file` 输入模式、`response_file` 单次响应出口、输出 handler、delivery matrix，以及新增的 `artifactShape / outputShape / delivery.frontstage` 正式 shape 一并公开；其中 `requestCatalog.actions.handle` 还会直接声明 `preferredRequestInputMode=request_file`、`preferredRequestFileValue=-`、`preferredResponseOutputMode=stdout`、`clientHelperModule=openclaw_infos_handle_contract.py`，以及 helper 侧的 `clientHelperFunctions / clientHelperResponseShape`；当前 helper 公开面已覆盖 request builder / request invoke / query invoke / snapshot adapter / notify adapter / compat delivery bundle，消费方若只想确认 infos-handle 正式入口与 helper 归一结果，可直接从这里读，不必再去翻 README 或手抠 `manifest.json`。
10. `infos-handle query --kind events.recent` 现在也会稳定暴露 `count / latestEventAt / availableSources / sourceEventCount / deliveryCount / recordTypeCounts / eventItems[] / latestBySource / latestBySourceItems[]`；其中 `latestBySource` 保留 keyed object 便于按 source 直取，`latestBySourceItems[]` 则提供按 `latestEventAt desc` 排好的稳定顺序摘要（如 `latestEventSummary / latestEventKey / sourceEventType / sourceView / isDelivery`），handoff / 排查脚本优先读这些稳定字段，不必再直接解析原始 `events[]`。
11. `infos-handle handle` 现在是 CLI 之上的统一正式请求入口：既可以按同一套 query 契约取数，也可以直接处理一条 `--message` 文本，再根据 `--format` 走对应 handler；`--format image` 目前已从单条 summary-card 提升到低风险 richer multi-panel SVG（会稳定回传 `layout / panels / badge / footerLines` 这组结果元数据），`--format audio` 会先把 query 结果整形成稳定 spoken-text plan（`textPlanVersion / strategy / segmentCount / segments / estimatedDurationSeconds`）再走现有 `tools/voice-reply/voice-reply.sh` / ChatTTS 本地链路，并把结果收成稳定 artifact 描述；当前 preview 输出在 `response.output.artifact` 与 `response.delivery.artifact` 两侧都复用同一套 artifact shape，后续 caller/renderer 可以直接沿这条正式面接入，而不是继续自己拼命令。
12. `handle --delivery-mode frontstage` 现在不只支持 `text/json`；对 `image/audio` 也会先生成 artifact，再发一条低风险 text artifact notice 到前台，并把 `artifact.ref`、`artifactNotice.{displayText|fallbackText|delivery}` 与 `artifact.{format|handler|mediaType|path|fileName|sizeBytes|preset}` 一并带进返回与可选 broker ingest data，作为现阶段更稳定的最小多模态 delivery 契约。
13. 当前 `response.delivery` 已继续收口成可直接给 consumer 用的稳定形状：优先读 `delivery.notice`（统一 `message / artifact_notice` 两类）、`delivery.frontstage`（统一前台投递元数据，当前也会稳定带 `noticeKind / artifactRef / displayText`）、以及 `delivery.artifactRef / delivery.artifact`；旧的 `delivery.artifactNotice / delivery.metadata` 仍保留作兼容别名；preview 输出被 broker ingest 时也会把 `deliveryNotice / frontstageDelivery` 一并带入 `data`，减少消费方再自己拼字段。当前 broker compat emit、`supervisor`、`frontstage-recovery` 这些真实 consumer 也都已改成优先经同一层 delivery adapter 读取 `notice/frontstage/artifactRef`，只把旧 `notify` 结果当回退；本轮又把 adapter 的归一结果补成 `deliveryNotice / frontstageDelivery / artifactNotice` 稳定 alias，而 `extract_handle_response_snapshot()` 也同步公开 `notice / frontstage / artifactNotice / notify / targetSessionKey / messageId` 顶层快照字段；这次再继续收口后，`extract_frontstage_notify_payload()` 与 `build_compat_delivery_bundle()` 也成为同一 helper 的正式公开面，broker compat emit 与 watcher notify adapter 直接复用它们，不再各自再写一套前台返回解析。继续往前收后，`notify-frontstage` compat payload 与 broker `emit` compat 壳也开始把 `notice / deliveryNotice / frontstage / frontstageDelivery / artifact / artifactNotice / notify` 这些字段显式 null-normalize，legacy edge shape 不再混用缺省空对象。
14. `handle` 现在还支持 `--request-file <path>`（`-` 表示 stdin）这条最小正式请求入口；同时新增了可选 `--request-id` 与 `--response-file <path>`，让一次性 CLI 请求也能带稳定关联 id，并把完整响应写到文件里。当前 `supervisor / frontstage-recovery / local-health` 三条 caller 都已进一步迁到 `--request-file -` 这条正式面，broker `emit` compat wrapper 也同步改成走 stdin request envelope；`apply-openclaw-frontstage-broker-data.py` 则新增为 `--request-file + --response-file` 的真实 smoke consumer。本轮又补了一个很薄的 `openclaw_infos_handle_contract.py` request client helper，broker compat emit / watcher caller 现在开始共用它；现在它也能直接驱动 `request_file + response_file` 这一跳，`apply-openclaw-frontstage-broker-data.py` 已迁到复用它。后续又继续补了 `invoke_handle_query()`，让 query consumer 也能经同一主请求面取 `contract.catalog` 这类结果；`openclaw-post-upgrade-self-check.py` 之后，这一轮又继续把它往前推了一步：升级后自检除了 `contract.catalog / snapshot.summary`，现在也会再跑一跳真实 `sources.catalog` consumer，`apply-openclaw-frontstage-broker-data.py` 则同步把 helper response shape 的 `notify` alias 一并纳入验证；这一轮又再补上一跳真实 `events.recent` consumer，用 live `limit` 参数验证 query caller 也已经沿同一 `handle --request-file -` 主路径收口。再往前一步，旧 `query` compat 入口现在也改成内部先走 `handle` 主请求面、再回吐原有 query payload；`notify-frontstage` compat 入口则继续只保留兼容壳与 legacy 返回整形。这样 watcher / compat caller / query consumer / apply 验证脚本侧现在统一都在往同一套 request envelope 收，而不是继续混用 `--request-json` 与旧 notify convenience route。

## 当前阶段边界

当前 broker 升级只做到：

1. 保留现有 `emit` 兼容行为，但实现已收口为“先走 infos-handle handle 发前台，再回 broker 记 delivery”；当前 compat wrapper 也改成经 `--request-file -` 把 request envelope 送进 infos-handle，并优先消费 `delivery.notice / delivery.frontstage / delivery.artifactRef` 这条正式返回；同时会把 `frontstageSource / frontstageEventKey / brokerStateDir / brokerDataDir` 透传给 `handle` 主请求面，优先复用 infos-handle 内部 broker ingest / record-delivery。
2. 在每次成功投递后，把事件写入 `events.jsonl`
3. 顺手生成可读视图文件，作为 sidecar 数据层的第一步
4. 支持 `rebuild-views`，可从现有 source 状态文件与兼容 `broker-state.json` 重建当前视图
5. 在重建视图时顺手生成统一 `snapshot.json`（并保留 `overview.json` 兼容别名）与前端状态页，作为 broker 的第一版 renderer 输入；这些前端公开副本现在按 **best-effort** 发布，不应反向阻塞 broker 核心视图重建
6. 当前已补上用户态 systemd timer，可周期重建视图，降低“长时间无新辅助消息时视图逐渐变旧”的风险

当前**还没有**做：

- 网关主链级别的 HTTP / SSE / WebSocket 数据接口（当前只有独立本地 sidecar：`scripts/openclaw-infos-handle-sidecar.py`，默认暴露 `/v1/query/*`、`/v1/handle` 与最小只读 `/v1/events/stream`）
- 比当前 preview 更丰富的 image / audio renderer（例如真正多模板图片卡片、音频直投递/队列；当前仍是 low-risk richer preview）
- 强制让 Control UI 改为只读 infos-handle / broker（当前是 infos-handle sidecar 优先、snapshot 静态文件回退）
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
python3 scripts/openclaw-infos-handle.py handle --kind snapshot.summary --format json
python3 scripts/openclaw-infos-handle.py handle --kind snapshot.summary --format image
python3 scripts/openclaw-infos-handle.py handle --kind snapshot.summary --format image --delivery-mode frontstage
python3 scripts/openclaw-infos-handle.py handle --kind snapshot.summary --format audio
python3 scripts/openclaw-infos-handle.py handle --kind snapshot.summary --format audio --delivery-mode frontstage
printf '%s\n' '{"message":"文件入口 smoke","format":"text","deliveryMode":"frontstage","sessionKey":"agent:main:main"}' > /tmp/infos-request.json
python3 scripts/openclaw-infos-handle.py handle --request-file /tmp/infos-request.json
python3 scripts/openclaw-infos-handle.py handle --request-id smoke-1 --request-file /tmp/infos-request.json --response-file /tmp/infos-response.json
python3 scripts/openclaw-infos-handle-sidecar.py --host 127.0.0.1 --port 18790
python3 scripts/apply-openclaw-frontstage-broker-data.py
python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock --verify-control-ui-infos-handle-sidecar --require-control-ui-infos-handle-sidecar
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
- `manifest.json` 里的 `publicationMode` 应为 `best_effort`；正常情况下 `publicationWarnings` 应为空数组
- 旧 `broker-state.json` 仍应继续更新
- `rebuild-views` 应能在不新增前台消息的前提下，直接把当前 source 状态重建成视图
- `jarvis-frontstage-status.html` / `jarvis-frontstage-status.json` / `jarvis-frontstage-snapshot.json` 应能随 rebuild 同步更新；即使这些公开副本发布失败，broker 也仍应保住 `views/*.json` 与 `manifest.json`
- 若跑了 `--apply-control-ui-branding --verify-control-ui-snapshot-dock`，则应额外看到：
  - live `jarvis-branding-override.js` 的 `snapshotJsonHref = /jarvis-frontstage-snapshot.json`
  - live `jarvis-branding-override.js` 的 `legacyStatusJsonHref = /jarvis-frontstage-status.json`
  - `frontstagePublication.snapshotFirstReady = true`，证明 live 公开链路里 snapshot 是首选入口、status.json 只是兼容别名
- 若再跑了 `--verify-control-ui-infos-handle-sidecar`，则应额外看到：
  - `controlUiInfosHandleSidecar.ok = true`
  - `healthzHref / summaryHref / contractHref` 都指向当前 branding 注入的 live sidecar URL
  - `summaryKind = snapshot.summary`
  - `requestContractVersion = 6`
  - 若当前 dock 已启用 SSE，`sseReady = true`
- `scripts/apply-openclaw-frontstage-broker-data.py` 应能完成 py_compile + 测试 + rebuild-views 这一整套最小重装流程
- 若使用 `--install-user-systemd`，应额外输出已安装的 user systemd service/timer 路径
- `openclaw-frontstage-broker-rebuild.timer` 应处于 `enabled + active(waiting)`
- 若 `broker-state.json` 里已有 `local-health` / `frontstage-recovery`，即使这些来源不是本轮新发事件，也应能被回填到对应视图文件

## 边界与稳定性原则

- broker 当前仍应是 **sidecar 数据层**，不是 OpenClaw 主体的硬依赖
- 没有 broker 数据目录时，现有 OpenClaw 主链不应因此报错
- 当前阶段任何 broker 升级都必须优先保持现有 frontstage 投递能力不回退
- 未来若要继续往“真正数据层”推进，应优先沿这几个产物演进，而不是直接硬拆 Gateway / Control UI 主链
