# infos-handle sidecar

- 适用机器：公司（Linux）（脚本本身也可给其他 Linux 机器复用）
- 系统 / OS：Linux
- 用途：为 `scripts/openclaw-infos-handle.py` 提供最小本地 HTTP / SSE sidecar，让 Control UI / 其他轻量 consumer 优先直连 infos-handle 正式请求层，而不是只读 broker 静态快照。

> **最新增强 (2026-05-19):**
> - 默认 image preset 已切到 `summary-card-v3`（`image.summary-card.v3`），v2 仍可通过显式 `--image-preset summary-card` / `imagePreset=summary-card` 使用
> - audio handler 升级到 `audio.local-tts.v2`：自然口语 preamble + conversational connectors 连接 segment
> - sidecar 已接入 Gateway Bearer token 鉴权：**本地直连 localhost 免鉴权；远程/LAN 访问需 `Authorization: Bearer <gateway-token>`**
> - 若经 Caddy 统一入口转发，sidecar 会按 `X-Forwarded-For` / `X-Real-IP` 识别原始客户端，不会再把远程代理请求误当 localhost 放过
> - sidecar 新增远程 rate limit：**仅限制非 localhost 客户端**，默认 `120 req / 60s`
> - 新增 artifact cleanup：`--cleanup-artifacts-older-than-hours N` 可清理过期 artifact
> - 所有测试保持绿色

## 当前入口

- sidecar 脚本：`scripts/openclaw-infos-handle-sidecar.py`
- service 模板：`tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
- 脚本默认监听：`127.0.0.1:18790`
- service 模板默认监听：`0.0.0.0:18790`
- 鉴权语义：本地直连 localhost 免鉴权；远程/LAN 请求需 Bearer token；若经统一入口代理，按原始客户端 IP 判定
- 远程限流：默认仅对非 localhost 客户端生效，`120 req / 60s`（可用环境变量覆盖）
- 当前 Control UI 品牌补丁默认读取：
  - `GET /v1/query/snapshot.summary?format=json`
  - `GET /v1/query/contract.catalog?format=json`
  - `GET /v1/events/stream?kind=snapshot.summary`

## 为什么需要这层

当前 broker / infos-handle 主线已经把正式入口收敛到：

- `handle`
- `--request-file`
- `openclaw_infos_handle_contract.py`

但 Control UI 这类轻量 consumer 如果每次都直接跑 CLI，会比较重，也不利于做前台状态小卡片的高频刷新。

因此这层 sidecar 只做一件事：

> 把 infos-handle 的正式请求层，最小地桥成 HTTP / SSE 入口（本地直连优先，也可在受控 LAN / 统一入口下复用）。

它不是新的业务主链，也不是要替代 broker；只是让前端优先直连 infos-handle 当前主入口。

## 当前已提供的接口

### 1. 健康检查

```http
GET /healthz
```

返回当前 sidecar 是否在线，以及它使用的：

- `snapshotPath`
- `eventsPath`
- `outputRoot`
- `artifactRoutePrefix`
- `remoteRateLimit`

### 2. 查询接口

```http
GET /v1/query/<kind>?format=json
GET /v1/query/<kind>?format=text
```

当前支持：

- `snapshot.summary`
- `health.summary`
- `health.detail`
- `tasks.summary`
- `recovery.summary`
- `panel.inspect`
- `panels.catalog`
- `sources.latest`
- `sources.catalog`
- `source.inspect`
- `events.recent`
- `events.timeline`
- `contract.catalog`

常用 query string：

- `format=text|json`
- `limit=<n>`
- `sourceName=<name>` / `source_name=<name>`
- `panelName=<name>` / `panel_name=<name>`

说明：

- query 现在只开放 `text/json`
- richer `image/audio` 继续走 `POST /v1/handle`

### 3. 统一 handle 入口

```http
POST /v1/handle
Content-Type: application/json
```

请求体直接复用 infos-handle 正式 request envelope，例如：

```json
{
  "requestId": "dock-smoke-1",
  "kind": "snapshot.summary",
  "format": "image",
  "deliveryMode": "none"
}
```

sidecar 会自动补：

- `snapshotPath`
- `eventsPath`
- `outputRoot`

然后复用 `invoke_handle_request()` 调用正式主入口。

当 `format=image|audio` 时，sidecar 现在还会在返回体里额外补一层可直接给网页消费的 artifact 链接：

- `response.output.artifactHref`
- `response.output.artifact.href`
- `response.delivery.artifactHref`
- 以及 `notice / artifactNotice / frontstage` 这些嵌套对象里的 `artifactHref`

这样消费方不必自己从本地路径拼 URL，只需要拿 `artifactRef` 或返回里的 `artifactHref` 即可继续取文件。

### 4. Artifact 文件读取

```http
GET /v1/artifacts/<artifactRef>
GET /v1/artifacts?ref=<artifactRef>
```

可选参数：

- `download=1` / `attachment=1`：返回 `Content-Disposition: attachment`

当前行为：

- 只允许读取当前 `outputRoot` 下的 `image/` 与 `audio/` artifact
- 会按 `artifactRef` 解析成实际文件并返回正确 `Content-Type`
- 主要给自建网页 / Control UI 扩展 consumer 直接挂 `<img>` / `<audio>` 使用

### 5. SSE 推送

```http
GET /v1/events/stream?kind=snapshot.summary
```

可选参数：

- `kind=<queryKind>`（默认：`snapshot.summary`）
- `intervalMs=<ms>`（默认：`15000`，最小会收敛到 `1000`）

当前行为：

- 以固定间隔重复查询 infos-handle
- 每轮以 `event: snapshot` + JSON `data:` 推给前端
- 当前是 **poll-to-SSE** 的最小实现，不引入新的持久状态层

## 最小启动方式

### 前台手工启动

```bash
python3 scripts/openclaw-infos-handle-sidecar.py
```

### 指定端口

```bash
python3 scripts/openclaw-infos-handle-sidecar.py --host 127.0.0.1 --port 18790
# 若要给 LAN / 其他设备直连：
python3 scripts/openclaw-infos-handle-sidecar.py --host 0.0.0.0 --port 18790
```

## user systemd 安装（公司 Linux）

```bash
mkdir -p ~/.config/systemd/user
cp tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-infos-handle-sidecar.service
```

查看状态：

```bash
systemctl --user status openclaw-infos-handle-sidecar.service
journalctl --user -u openclaw-infos-handle-sidecar.service -n 100 --no-pager
```

## 最小验证

```bash
curl -s http://127.0.0.1:18790/healthz
curl -s 'http://127.0.0.1:18790/v1/query/snapshot.summary?format=json'
curl -s 'http://127.0.0.1:18790/v1/query/contract.catalog?format=json'
curl -s -X POST 'http://127.0.0.1:18790/v1/handle' -H 'Content-Type: application/json' -d '{"kind":"snapshot.summary","format":"image"}'
curl -s 'http://127.0.0.1:18790/v1/artifacts/infos-handle%3Aimage%3Aexample-ref' || true
curl -N 'http://127.0.0.1:18790/v1/events/stream?kind=snapshot.summary'
```

更完整的回归仍看：

```bash
python3 scripts/test-openclaw-infos-handle.py
python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar
```

其中 `--verify-control-ui-infos-handle-sidecar` 当前不只检查 `healthz / summary / contract / SSE`，也会额外走一跳真实 `POST /v1/handle {"kind":"snapshot.summary","format":"image"}`，并继续验证返回的 `artifactHref` 确实可经 `/v1/artifacts/...` 取回 SVG。

若当前还要连同 live branding 注入与 snapshot-first 回退链路一起验，则用：

```bash
python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock --verify-control-ui-infos-handle-sidecar --require-control-ui-infos-handle-sidecar
```

## 与 Control UI 的关系

当前 `scripts/apply-openclaw-control-ui-branding.py` 会把下面三条 href 注入进 live `jarvis-branding-override.js`：

- `infosHandleSummaryHref`
- `infosHandleContractHref`
- `infosHandleSseHref`

当前 dock 行为是：

1. 优先请求 `infosHandleSummaryHref`
2. 若失败，再回退到 `jarvis-frontstage-snapshot.json`
3. 若浏览器支持 `EventSource`，再尝试连 `infosHandleSseHref`

而对自建网页这类 richer consumer，现在更推荐的最小接法是：

1. `GET /v1/query/...` / `POST /v1/handle` 先拿结构化结果
2. 若返回里带 `artifactHref`，直接继续请求 `GET <artifactHref>`
3. 需要轻量刷新时，再订阅 `GET /v1/events/stream`

因此 sidecar 当前的价值是：

- 让 Control UI 可以优先读 infos-handle 的**正式主入口结果**
- 保留 broker 静态快照作为低风险回退

## 当前边界

- 脚本默认仍是 loopback；若使用 service 模板或显式 `--host 0.0.0.0`，则变为 LAN 可达
- 远程/LAN 请求默认需要 Bearer token；本地 localhost 直连保留免鉴权兼容
- 只做最小 HTTP / SSE bridge，不做新的数据库/缓存层
- 不把 OpenClaw 主聊天链改成依赖 sidecar
- richer image/audio 仍以 `handle` 主请求面为核心，sidecar 只是 transport
- 当前 SSE 是定时 query 的最小实现，不是 broker 原生事件流
- artifact cleanup 可通过 infos-handle 主入口的 `--cleanup-artifacts-older-than-hours N` 手工触发，sidecar 当前不做自动清理

一句话：

> 这层 sidecar 是 infos-handle 正式主入口的轻量运输层，不是新的平行主线。
