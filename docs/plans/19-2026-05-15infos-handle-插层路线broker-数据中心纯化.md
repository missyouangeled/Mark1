## 2026-05-15:infos-handle 插层路线(broker 数据中心纯化)

### 背景

用户在 2026-05-15 11:40(Asia/Shanghai)进一步把长期方向说得更具体:

- broker 应真正退到"数据中心 / 数据层"角色
- 在 broker 与具体消费方之间,再加一层暂名 `infos-handle`
- 以后无论是 Control UI、别的平台、CLI、本地脚本,还是文字 / 图片 / 音频返回,都尽量通过 `infos-handle` 取数与处理,而不是直接啃 broker 原始状态和当前前台主会话细节
- Control UI 只是一个 renderer / consumer,不应继续表现成默认唯一承载层
- 即使将来把 Control UI 整个删掉,broker 也不应因为缺少 UI 而报错;最多只是"没人消费,所以没有可见反馈"

这条要求与 2026-05-14 已确认的"工作层 / 数据层 / 渲染层"路线一致,但比昨天更进一步:

> 不只是让 broker 先成为 sidecar 数据源,而是明确补出一个"信息处理 / 分发层"。

### 当前代码与结构的真实耦合点(2026-05-15 实地核对)

#### 1. broker 当前仍同时承担"数据"和"前台投递"

`scripts/openclaw-frontstage-broker.py` 现在的关键现实是:

- `emit_frontstage()` 内部直接调用 `openclaw-supervisor-subagent.py send-frontstage`
- `emit_event(...)` 会在 `emit_frontstage()` 成功后,才把结果记成 broker record,并顺手 rebuild views

也就是说,当前 broker 还不是纯数据中心,而是:

- 接事件
- 去重
- 发前台
- 写已发记录
- 重建视图

这对当前"辅助消息能打回 dashboard"很实用,但职责还不够纯。

#### 2. 当前事件日志主要记录的是"已成功投递",不是"原始 source 事件"

当前 README 已明确:

- `events.jsonl` 记录的是 `frontstage.delivery.sent`
- 它描述的是 broker 已经成功完成的一次前台投递
- 而不是 source watcher 的原始状态变化镜像

因此当前 broker 数据层仍偏"delivery-first",还没完全到"source-of-truth first"。

#### 3. Control UI 当前已开始读 broker snapshot,但仍不是纯 renderer

`scripts/apply-openclaw-control-ui-branding.py` 当前已经把顶部"前台状态"小入口接成:

- 优先读取 `/jarvis-frontstage-snapshot.json`
- `jarvis-frontstage-status.json` 只保留兼容别名

说明:

- Control UI 已经开始消费 broker snapshot
- 但它仍深度依赖 Gateway / `chat.history` / live chat 主链
- 因此当前只能说"辅助状态区逐步在 renderer 化",还不能说"Control UI 已彻底变成 broker consumer"

#### 4. watcher/source 现在默认仍把 broker 当"前台统一投递入口"

例如:

- `scripts/openclaw-frontstage-recovery-watch.py` 在 anomaly / recovered 时,直接调用 `openclaw-frontstage-broker.py emit`
- `scripts/openclaw-supervisor-status.py` 也是通过 broker 发前台

所以当前 broker 对 source 来说,不只是数据层,还是"带前台投递副作用的入口"。

### 我们现在认定的四层结构

基于当前目标,后续统一按这四层理解,而不是继续把 Control UI 和 broker 混成两层:

1. **工作层 / runtime layer**
   - Gateway / agent runtime / sessions / transcript / watcher / cron / subagents
   - 负责真正产生状态、事件、任务、会话
2. **数据层 / broker layer**
   - 负责统一事件、统一快照、统一查询源
   - 不因为缺少 renderer 或缺少 infos-handle 而报错
3. **信息处理层 / infos-handle layer**
   - 负责接请求、取数据、组结果、选输出形式、决定发给谁
   - 这是本轮新增补出来的中间层
4. **渲染 / 消费层 / renderer-consumer layer**
   - Control UI / WebChat / CLI / 本地脚本 / 图片卡片 / 音频返回 / 其他平台

一句话职责定义:

- **broker 负责"存事实"**
- **infos-handle 负责"把事实变成结果"**
- **Control UI 负责"显示结果"**

### infos-handle 的职责边界

`infos-handle` 当前建议先定义成一个**窄职责版本**,不要一上来就变成"另一个 Gateway"或"另一个主对话状态机"。

#### 它应该做的

1. 接收请求
   - chat 请求
   - CLI 请求
   - 本地 HTTP/API 请求(后续)
   - 其他平台消费请求(后续)
2. 读取数据
   - 优先从 broker snapshot / broker events 读取
   - 必要时补读少量 runtime 状态(例如 session 活跃态)
3. 组织结果
   - 过滤
   - 聚合
   - 摘要
   - 对话式解释
   - 结构化 JSON 输出
4. 选择输出形式
   - `text`
   - `json`
   - 后续再补 `image` / `audio`
5. 选择投递方式
   - stdout / 文件
   - frontstage / chat session
   - 其他消费方(后续)

#### 它当前不该做的

- 不接管 OpenClaw 主会话状态机
- 不替代 Gateway transcript 主链
- 不一上来承诺完整跨平台对话一致性
- 不要求 Control UI 先整体重写后才能存在

### 目标状态(分层后的理想数据流)

```text
[工作层 / runtime]
  supervisor / local-health / recovery / transcript / sessions / tasks
            ↓
[broker / 数据层]
  原始事件、规范化事件、快照、查询源
            ↓
[infos-handle / 信息处理层]
  取数、解释、聚合、选格式、选投递方式
            ↓
[renderers / consumers]
  Control UI / WebChat / CLI / 本地脚本 / 图片 / 音频 / 其他平台
```

### 稳定性红线(这条路线必须遵守)

1. **OpenClaw 主体稳定性优先**
2. **broker 当前仍必须保持 sidecar / 弱依赖形态**
3. **没有 Control UI 时,broker 仍应可运行**
4. **没有 infos-handle 时,broker 也应可单独留下事件与快照**
5. **当前阶段不重写主聊天链**
6. **先做 text/json,再做 image/audio;不要一口气上多模态**

### 当前推荐实施顺序

#### Phase 0:先冻结契约和边界(本阶段立即做)

目标:先把名字、职责、边界定清楚,避免一边写代码一边改口径。

本阶段产出:

- 这份方案(当前章节)
- `infos-handle` 的最小职责说明
- broker / infos-handle / renderer 的边界与非目标

#### Phase 1:先把 broker 纯化成"数据中心优先"

目标:让 broker 先更像数据中心,而不是"默认会直接发前台的投递器"。

建议最小改动:

1. broker 内部把两类事件显式区分:
   - `source event`:原始或规范化来源事件
   - `delivery event`:实际投递结果
2. 新增或明确一条**不带前台副作用**的 ingest 路径
   - 例如 `ingest` / `append-source-event` 之类动作
   - 只负责写事件、更新快照、重建视图
3. 现有 `emit` 保留兼容
   - 继续给旧 watcher 用
   - 但语义上标成兼容层,而不是未来正式主入口
4. `publish_frontstage_status(...)` 这类 Control UI 公共副本发布应保持**best-effort**
   - 有 Control UI dist 就发布
   - 没有就跳过,不把 broker 判失败

本阶段验收:

- 删除或暂时拿走 Control UI dist 后,broker 的 ingest / rebuild 仍可通过
- broker 仍能输出 `events.jsonl` / `snapshot.json` / `manifest.json`
- 没有 renderer 时,broker 不因"无人消费"报错

#### Phase 2:做一个最小 infos-handle(只做 text/json)

目标:先让 infos-handle 成为"能收请求、能取数、能回 text/json"的信息处理层。

建议最小文件:

- `scripts/openclaw-infos-handle.py`

建议最小 action:

1. `query`
   - 读取 broker snapshot / events
   - 输出 `json` 或 `text`
2. `notify-frontstage`
   - 仍可调用现有 frontstage 投递适配器
   - 但这是 infos-handle 的职责,不再属于 broker 核心职责
3. (后续再补)`render-image` / `render-audio`

建议最小 request kind:

- `snapshot.summary`
- `health.summary`
- `tasks.summary`
- `recovery.summary`
- `events.recent`

建议最小输出格式:

- `--format json`
- `--format text`

本阶段验收:

- `python3 scripts/openclaw-infos-handle.py query --kind snapshot.summary --format json`
- `python3 scripts/openclaw-infos-handle.py query --kind tasks.summary --format text`
- 在没有 Control UI 的情况下,这些请求仍能正常返回

#### Phase 3:把"前台投递"从 broker 迁到 infos-handle

目标:让 broker 更纯,让 infos-handle 开始承担"如何把结果送出去"的职责。

建议顺序:

1. 新 watcher / 新入口优先调用 infos-handle
2. infos-handle 内部:
   - 先调 broker ingest / query
   - 再决定是否 `notify-frontstage`
3. 旧 watcher 继续允许调用 broker `emit`
   - 直到迁完再收兼容层

本阶段验收:

- `frontstage-recovery` 或 `supervisor` 其中一条链先切到 infos-handle 路由
- 当前 dashboard 仍能收到消息
- broker 仍能留下数据,即使前台投递失败

#### Phase 4:Control UI 逐步改成 infos-handle / broker 的 consumer

目标:让 Control UI 在辅助状态层面变成真正的 consumer,而不是继续承载太多中间逻辑。

当前只做:

- 辅助状态区 / 状态 dock 继续优先读取 broker snapshot
- 若后续需要请求式摘要,可让 dock 调 infos-handle 的 text/json 接口

当前不做:

- 不重写聊天主链
- 不试图让 Control UI 立刻脱离 Gateway live chat 机制

#### Phase 5:再补 image / audio / 本地解析

目标:等 infos-handle 的 text/json 稳定后,再补多模态。

可后续支持:

- `--format image`
- `--format audio`
- `--format file`
- 本地 parser / 本地 renderer 输入

这一步必须后置,避免现在就把复杂度拉高。

### 第一批建议立刻实现的东西(安全顺序)

1. broker 增加**纯 ingest 路径**,不带前台投递副作用
2. broker 把 `source event` 与 `delivery event` 分离
3. 新建 `scripts/openclaw-infos-handle.py`,先只支持:
   - `query snapshot.summary`
   - `query health.summary`
   - `query tasks.summary`
   - `query recovery.summary`
   - `notify-frontstage`(复用现有 frontstage 解析与 inject 适配器)
4. 给 infos-handle 加最小测试 / smoke
5. 保持现有 Control UI dock 不变,先不碰聊天主链

### 当前一句话结论

> 这条路线是可行的,而且是比"继续堆 Control UI 补丁"更接近长期正确结构的路线;但正确起手式不是立刻重写 UI,而是先把 broker 纯化,再补一个最小 infos-handle,把"取数据 / 解释请求 / 选输出 / 选投递"从 broker 和 Control UI 之间剥出来。

### 当前实现进度(截至 2026-05-15 17:50)

当前已经完成:

1. **Phase 1 的主体已站稳**
   - `scripts/openclaw-frontstage-broker.py` 已有:
     - `ingest`
     - `record-delivery`
   - 当前 broker 事件流已明确区分:
     - `broker.source.event`
     - `frontstage.delivery.sent`
   - `views/frontstage.json` / `snapshot.json` 已有 `sourceStates` / `sourceStateSnapshots` 这类"最近已 ingest 来源状态"字段
   - broker 契约当前已能从 `contract.catalog` 直接读到;当前 `brokerContractVersion=2`

2. **Phase 2 的最小 infos-handle 已从 contract-first 查询层继续推进到"统一信息处理层最小版"**
   - 已新增:`scripts/openclaw-infos-handle.py`
   - 当前已支持:
     - `query --kind snapshot.summary|health.summary|tasks.summary|recovery.summary|panel.inspect|panels.catalog|sources.latest|sources.catalog|source.inspect|events.recent|contract.catalog`
     - `notify-frontstage`
     - `handle`(统一正式请求入口)
   - 其中:
     - `query` 仍是低风险兼容入口,只支持 `--format text|json`
     - `handle` 现在统一支持 `--format text|json|image|audio`
   - `contract.catalog` 当前会公开:
     - `queryCatalog`(各 query kind 的格式/必填参数/默认 limit)
     - `queryCatalog.outputFormatCatalog`(当前 `text/json=ready`、`image/audio=preview`)
     - `requestCatalog`(统一 `handle` 入口、request/response shape、delivery matrix、`request_json / request_file` 输入模式,以及 `response_file` 单次响应输出模式;当前还额外公开 `preferredRequestInputMode=request_file`、`preferredRequestFileValue=-`、`preferredResponseOutputMode=stdout` 与 `clientHelperModule=openclaw_infos_handle_contract.py`)
     - `handlerCatalog`(当前 stdout / image summary-card / audio local-tts handler)
     - broker 的 `contracts.recordTypes / contracts.eventFieldCatalog`
     - `queryContractVersion=17`
     - `requestContractVersion=6`
   - source 相关 query 的推荐读取顺序现已明确:先读 `sources.latest` 做轻量 inventory / handoff,再在需要 raw latest snapshots / contract 时读 `sources.catalog`,最后只在深挖单个 source 时读 `source.inspect`
   - `sources.latest` 现在除了保留原始 `sourceStateSnapshots / sources` keyed snapshot 外,也会额外暴露 `count / availableSources / sourceItems[]`,把每个 source 的最近摘要收成与 `sources.catalog / source.inspect` 更一致的稳定 item shape;其中已包含 `latestEventItem / latestDeliveryItem`
   - `sources.catalog` / `source.inspect` 当前已补齐稳定顶层字段(如 `latestEventAt`、`latestRecordType`、`latestEventSummary`、`latestEventKey`、`latestSourceStateSummary`、`latestDeliveryMessage`、`latestDeliveryEventKey`、`latestDeliveryRecordType`),减少消费方解析嵌套对象的成本
   - `sources.catalog` 现在会同时补 `latestEventItem / latestDeliveryItem`,把最近一条 source 相关事件和最近一条 delivery 都压平成稳定 item shape(`recordType / summary / checkedAt / reportStatus / deliveryStatus` 等),方便 handoff / 排查脚本直接消费
   - `source.inspect` 还会稳定暴露 `recentDeliveryCount`、`latestEventItem`、`latestDeliveryItem`、`recentEventItems[]` 与 `recentDeliveryItems[]`;消费方优先读这些 item shape,就不必直接解析 `recentEvents[]` 或 `latestDelivery` 原始对象
   - `events.recent` 现在也会稳定暴露 `count / latestEventAt / availableSources / sourceEventCount / deliveryCount / recordTypeCounts / eventItems[] / latestBySource / latestBySourceItems[]`;其中 `latestBySource` 保留 keyed object 便于按 source 直取,`latestBySourceItems[]` 则提供按 `latestEventAt desc` 排好的稳定摘要顺序,handoff / 排查脚本优先读这些稳定字段,不必再直接翻原始 `events[]`
   - `panel.inspect` / `panels.catalog` 也已纳入同一份 `queryCatalog`
   - `handle --format image` 现在会生成低风险 `summary-card SVG` artifact
   - `handle --format audio` 现在会走现有本地 `tools/voice-reply/voice-reply.sh` / ChatTTS 链路;测试里可通过 stub renderer 验证返回契约
   - `handle --delivery-mode frontstage` 现在也能覆盖 `image/audio`:先产出 artifact,再发一条 text artifact notice 到前台,并同时返回稳定 artifact 元数据
   - `image/audio` 的 frontstage artifact-notice 合同已进一步收口:消费方优先读取 `response.delivery.notice / response.delivery.frontstage`;旧 `artifactNotice / metadata` 仅保兼容别名
   - `handle` 现已允许可选 `brokerStateDir / brokerDataDir` 覆盖,便于把 artifact-notice 元数据一并走 broker ingest / delivery 回归,而不污染默认本地状态目录
   - `handle` 现也支持 `--request-file <path|->`,作为低风险文件 / stdin 单次请求入口;同时补了 `--request-id` / `--response-file <path>`,让单次 CLI 调用也能走更正式的 request/response envelope,而不引入常驻服务
   - 为避免每个 caller 手搓命令 / 解析返回,已补一个很薄的 `scripts/openclaw_infos_handle_contract.py` request client helper;broker compat emit、supervisor、frontstage-recovery、local-health 这几条真实 caller 开始共用它,统一走 `handle --request-file -`;本轮又把它补成同时支持 `request_file + response_file` 这一跳最小正式入口;后续又继续补了 `invoke_handle_query()` 与 `extract_handle_response_snapshot()`,把 query consumer 也拉到同一条正式 request/response envelope 上;这次再继续收口后,`extract_frontstage_notify_payload()` 与 `build_compat_delivery_bundle()` 也一并纳入正式 helper 公开面,watcher notify adapter 与 broker compat emit 直接复用同一份 contract helper,不再各自留一套返回解析
   - 已新增最小回归:`scripts/test-openclaw-infos-handle.py`(已覆盖 `handle --format json/image/audio` smoke、image/audio frontstage artifact-notice smoke、`--request-file` 入口、以及 `--response-file` 响应出口)

3. **Phase 3 已开始,且已有真实迁移点**
   - broker 当前对 canvas / Control UI 公开副本发布也已进一步收成 `best_effort`;即使这些前端副本发布失败,也不应阻塞 `views/*.json` 与 `manifest.json` 继续重建
   - broker `emit` 当前也已进一步压成更明显的 legacy compatibility wrapper:前台发送优先经 `infos-handle handle`,broker 自己只保 delivery 兼容记录;新能力优先落到 infos-handle;本轮又继续收口为直接走 request envelope(`--request-file -`),且已开始复用统一 request helper;同时 `frontstageSource / frontstageEventKey / brokerStateDir / brokerDataDir` 也透传进 `handle` 主请求面,优先复用 infos-handle 内部 broker ingest / delivery 记录
   - `scripts/openclaw-supervisor-status.py`
   - `scripts/openclaw-frontstage-recovery-watch.py`
   - `scripts/openclaw-local-health-diagnose.py`
   - 上面三条链之前已从"直接调 broker emit"改成先走 `infos-handle notify-frontstage`
   - 旧 `notify-frontstage` compat 入口本轮也已继续弱化:内部改成走 `handle` 主请求面,再回吐兼容 payload,避免再长平行逻辑
   - 当前又继续往前推了一小步:这三条 caller 已迁到 `infos-handle handle --delivery-mode frontstage --format text`,并在本轮继续统一收口为直接发送 stdin request envelope(`--request-file -`);同时它们与 broker compat emit 现在都会稳定带上 `requestId`
   - 为了保兼容,caller / broker compat consumer 侧额外补了一层很薄的返回适配:优先吃 `handle.response.delivery.notice / frontstage / artifactRef`,旧 `notify-frontstage` payload 与 `delivery.notify` 只保回退;本轮又把 adapter 的归一结果补成 `deliveryNotice / frontstageDelivery` 稳定 alias
   - 其中 `supervisor / frontstage-recovery / local-health` 这三条当前也会把结构化 `data-json` 一并 ingest 进 broker
   - 这意味着:前台投递的直接调用点已进一步从旧 notify convenience route 往统一 `handle` route 收拢;同时 `scripts/openclaw-post-upgrade-self-check.py` 也开始经 helper 走 `handle --request-file -` 查询 `contract.catalog`,成为一个真实 non-delivery consumer
   - 下一步更自然的迁移点是:继续找剩余 caller / consumer,或者给 `handle` 补更正式的 artifact / richer delivery,而不是再扩旧 `notify-frontstage`

4. **当前停点与验证**
   - 当前代码停点提交见 `git log --oneline -1`
   - 这一串关键提交已继续推进到当前这版最终收口停点;更早的主线提交依次是:`2f57998` → `a862517` → `45258f1` → `e7095d8` → `4de50fb` → `2575456` → `ff07c2f` → `7fe7efd` → `3aa091e` → `eb8aa4f` → `7396ede`
   - 当前最小核验保持全绿:
     - `python3 -m py_compile scripts/openclaw-infos-handle.py scripts/test-openclaw-infos-handle.py scripts/openclaw-frontstage-broker.py scripts/test-frontstage-broker.py`
     - `python3 -m py_compile scripts/openclaw-supervisor-status.py scripts/openclaw-frontstage-recovery-watch.py scripts/openclaw-local-health-diagnose.py scripts/test-frontstage-recovery-watch.py scripts/test-infos-handle-frontstage-callers.py`
     - `python3 scripts/test-frontstage-broker.py`
     - `python3 scripts/test-openclaw-infos-handle.py`
     - `python3 scripts/test-frontstage-recovery-watch.py`
     - `python3 scripts/test-infos-handle-frontstage-callers.py`
     - `python3 scripts/openclaw-infos-handle.py query --kind contract.catalog --format json`
     - `python3 scripts/apply-openclaw-frontstage-broker-data.py`
   - `apply-openclaw-frontstage-broker-data.py` 现在也会顺手走一遍 `handle --request-file ... --response-file ...` 的正式入口 smoke,且已迁到直接复用 `openclaw_infos_handle_contract.py` helper,作为新的真实 consumer / 验证入口

当前继续不做、但已不阻塞本轮收口:

- `image/audio` 虽已有 preview handler 与更稳定的 frontstage artifact-notice 合同,但还没有 richer renderer / real artifact transport(例如多模板图片卡片、音频直接投递队列、失败回退策略)
- Control UI 对 infos-handle 的直接消费尚未开始
- broker 仍保留 `emit` 兼容入口
- infos-handle 还没有独立 HTTP / SSE / WebSocket 请求入口

因此当前判断应是:

- **Phase 1:已基本落地,且 renderer 发布已进一步 best_effort 化**
- **Phase 2:已从"纯查询契约层"推进到"统一 request + preview handler + 最小 artifact-notice delivery"这一步,并已正式稳定**
- **Phase 3:本轮收口已达到可称"最终版"的状态**:`handle --request-file` + `openclaw_infos_handle_contract.py` helper 已成为正式主入口;新增 caller / consumer 已统一优先走这条主路径;broker 只保 sidecar 数据层 + compat 壳;剩余项属于下一阶段增强,不再阻塞本轮结束
