# infos-handle sidecar

- 适用机器：公司（Linux）（脚本本身也可给其他 Linux 机器复用）
- 系统 / OS：Linux
- 用途：为 `scripts/openclaw-infos-handle.py` 提供最小本地 HTTP / SSE sidecar，让 Control UI / 其他轻量 consumer 优先直连 infos-handle 正式请求层，而不是只读 broker 静态快照。

## 当前入口

- sidecar 脚本：`scripts/openclaw-infos-handle-sidecar.py`
- service 模板：`tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
- 默认监听：`127.0.0.1:18790`
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

> 把 infos-handle 的正式请求层，最小地桥成 loopback HTTP / SSE 入口。

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

### 2. 查询接口

```http
GET /v1/query/<kind>?format=json
GET /v1/query/<kind>?format=text
```

当前支持：

- `snapshot.summary`
- `health.summary`
- `tasks.summary`
- `recovery.summary`
- `panel.inspect`
- `panels.catalog`
- `sources.latest`
- `sources.catalog`
- `source.inspect`
- `events.recent`
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

### 4. SSE 推送

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
curl -N 'http://127.0.0.1:18790/v1/events/stream?kind=snapshot.summary'
```

更完整的回归仍看：

```bash
python3 scripts/test-openclaw-infos-handle.py
python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar
```

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

因此 sidecar 当前的价值是：

- 让 Control UI 可以优先读 infos-handle 的**正式主入口结果**
- 保留 broker 静态快照作为低风险回退

## 当前边界

- 只监听 `127.0.0.1`
- 只做最小 HTTP / SSE bridge，不做新的数据库/缓存层
- 不把 OpenClaw 主聊天链改成依赖 sidecar
- richer image/audio 仍以 `handle` 主请求面为核心，sidecar 只是 transport
- 当前 SSE 是定时 query 的最小实现，不是 broker 原生事件流

一句话：

> 这层 sidecar 是 infos-handle 正式主入口的 loopback 运输层，不是新的平行主线。
