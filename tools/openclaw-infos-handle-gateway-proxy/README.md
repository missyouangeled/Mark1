# infos-handle unified proxy (Caddy)

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 用途：给 Gateway（18789）与 infos-handle sidecar（18790）提供**单端口统一入口**，当前默认监听 `:18788`。

## 当前职责

- infos-handle 路由：
  - `/v1/query/*`
  - `/v1/handle*`
  - `/v1/artifacts/*`
  - `/v1/events/*`
  - `/healthz*`
  - → 反代到 `127.0.0.1:18790`
- 其余请求 → 反代到 Gateway `127.0.0.1:18789`
- 自动注入最小 CORS 响应头
- 透传原始客户端 IP：
  - `X-Forwarded-For` 走 Caddy 默认反代行为
  - `X-Real-IP: {remote_host}` 显式补上

## 为什么显式上送原始客户端 IP

sidecar 当前的鉴权语义是：

- **localhost 直连**：免鉴权（兼容本机 Control UI / 本机脚本）
- **远程/LAN 请求**：必须带 `Authorization: Bearer <gateway-token>`

如果统一入口代理不把原始客户端 IP 透传给 sidecar，那么 sidecar 只能看到反向代理这个 loopback 对端，容易把远程请求误判成 localhost 放过。

因此当前 Caddyfile 已明确把 `X-Forwarded-For` / `X-Real-IP` 传给 sidecar；sidecar 也只信任来自 loopback 代理的这两个头。

## 安装

```bash
mkdir -p ~/.config/systemd/user
cp tools/openclaw-infos-handle-gateway-proxy/openclaw-unified-proxy.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-unified-proxy.service
```

查看状态：

```bash
systemctl --user status openclaw-unified-proxy.service
journalctl --user -u openclaw-unified-proxy.service -n 100 --no-pager
```

## 最小验证

本机 localhost：

```bash
curl -s http://127.0.0.1:18788/
curl -s http://127.0.0.1:18788/healthz
curl -s 'http://127.0.0.1:18788/v1/query/snapshot.summary?format=text'
```

LAN 访问（需 Bearer）：

```bash
curl -H 'Authorization: Bearer <gateway-token>' \
  'http://<lan-ip>:18788/v1/query/snapshot.summary?format=json'
```

## 公网/TLS

`Caddyfile` 已带一段注释掉的域名配置模板：

- 填入域名
- 取消全局 `email` 注释
- 删掉或停用当前 `http://:18788` 块
- reload Caddy

即可使用自动 Let's Encrypt TLS。

## 当前边界

- 当前主要是 **统一入口 / 统一路由**，不是新的业务层
- 当前还**不负责** rate limit / 多租户隔离
- 当前对 Gateway 的 WebSocket 主链不做额外增强，只做现有反代
