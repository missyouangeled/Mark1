## 2026-05-19：broker / infos-handle v1 收口说明

### 定位

当前这条线的正式定位是：

- **broker** = sidecar 数据层 + compat 壳
- **infos-handle** = 正式请求 / 信息处理层
- **sidecar** = infos-handle 的轻量 HTTP / SSE 运输层
- **unified proxy** = Gateway + infos-handle 的统一入口层

它已经不再是“半成品探索”，而是一个**可用、可测、可续接、可升级后自检**的内部统一信息系统。

### v1 现在明确算完成的范围

按 2026-05-19 当前停点，下面这些已经属于 **v1 已完成范围**：

1. **broker 数据层已成型**
   - `events.jsonl`
   - `manifest.json`
   - `views/frontstage.json`
   - `views/health.json`
   - `views/tasks.json`
   - `views/recovery.json`
   - `views/snapshot.json`

2. **infos-handle 正式主入口已成型**
   - `handle --request-file` + contract helper 是唯一推荐主路径
   - query / compat / caller 都已围绕这条路径收口

3. **多种输出形态已成型**
   - `text`
   - `json`
   - `image.summary-card.v3`（默认）
   - `image.summary-card.v2`（兼容）
   - `audio.local-tts.v2`

4. **sidecar 已成型**
   - `GET /healthz`
   - `GET /v1/query/<kind>`
   - `POST /v1/handle`
   - `GET /v1/artifacts/<artifactRef>`
   - `GET /v1/events/stream`

5. **统一入口已成型**
   - `:18788` → unified proxy
   - `:18789` → Gateway
   - `:18790` → infos-handle sidecar

6. **鉴权闭环已完成**
   - localhost 直连 sidecar 可免鉴权（兼容本机 consumer）
   - 远程/LAN sidecar 访问需 Bearer token
   - 经 unified proxy 进入时也会按原始客户端 IP 判定，不再出现 localhost 绕过

7. **基础限流已完成**
   - sidecar 对非 localhost 客户端已有远程 rate limit

8. **安装/验证入口已成型**
   - `scripts/apply-openclaw-frontstage-broker-data.py`
   - `scripts/apply-openclaw-infos-handle-gateway-proxy.py`

9. **升级后自检链已成型**
   - `BOOT.md` 启动时自动触发
   - `scripts/openclaw-post-upgrade-self-check.py` 已覆盖：
     - branding
     - broker snapshot-first
     - infos-handle contract
     - infos-handle snapshot summary
     - infos-handle sources latest
     - infos-handle sidecar live
     - unified proxy verify
     - sidecar/proxy service 状态
     - broker / infos-handle / caller / recovery 回归

### v1 明确不包含的范围

下面这些**不属于 v1 已完成范围**：

1. **公网正式服务版**
   - 当前没有实际域名时，不算公网正式交付
   - 但 HTTPS/TLS 切换入口已经备好

2. **多租户 / 多用户边界**
   - 当前仍是单机 owner/operator 语义优先

3. **更强的入口层防护**
   - 目前有 sidecar 远程 rate limit
   - 但 unified proxy 自己还不是完整的公网防护层

4. **把 sidecar / infos-handle 变成 OpenClaw 主聊天链硬依赖**
   - 当前仍坚持 sidecar / broker 弱依赖路线

5. **把这条线扩成“另一个 Gateway”**
   - infos-handle 仍是窄职责信息处理层，不接管主会话状态机

### 完成度判断

如果按**本机 / LAN / 内部 consumer** 口径判断：

> **v1 已完成，可以正式收口。**

如果按**公网正式服务 / 多租户产品化** 口径判断：

> **v1 不覆盖这部分；这属于 v2+ 方向。**

### 以后默认怎么理解

后续再提到这条线时，默认按下面口径理解：

> **broker / infos-handle 当前已经是“完整的内部版统一信息系统”，而不是半成品。**
> **升级后默认会自动自检并尽量保持可用；若未来 OpenClaw 大版本改动过大，则按自检结果决定是否进入补丁修复。**

### v2 之后若要继续，优先顺序

1. 公网正式域名 / HTTPS 实装
2. unified proxy 更强的入口层限流 / 防护
3. 更明确的对外 consumer 接入文档
4. 如果真的有必要，再讨论更远的多租户 / 产品化边界

---
