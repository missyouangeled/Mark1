# 公司 Linux OpenClaw 本机配置期望

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 文档类型：本机配置期望（不包含敏感值）
- 最后更新：2026-06-01

## 用途

`~/.openclaw/openclaw.json` 不提交到 GitHub，因为它可能包含 token / provider / 本机私有配置。

这份文档只记录**非敏感的期望状态**，方便升级、迁移、排错时知道当前机器应该长什么样。

## 当前安全期望

### elevated allowlist

`tools.elevated.allowFrom.webchat` 不允许使用通配符：

```json
"*"
```

当前期望为显式 webchat 身份候选：

```json
{
  "webchat": [
    "webchat",
    "id:webchat",
    "from:webchat",
    "name:webchat"
  ]
}
```

说明：这是公司 Linux 本机个人 Control UI 使用场景下的折中收紧；它比通配符安全，但不等同于公网/多人环境的强身份模型。

### Control UI insecure auth

当前期望：

```json
{
  "gateway": {
    "controlUi": {
      "allowInsecureAuth": false
    }
  }
}
```

### trusted proxies

当前期望至少包含 loopback：

```json
{
  "gateway": {
    "trustedProxies": ["127.0.0.1", "::1"]
  }
}
```

## 验收命令

```bash
openclaw config get tools.elevated.allowFrom --json
openclaw config get gateway.controlUi.allowInsecureAuth --json
openclaw config get gateway.trustedProxies --json
openclaw security audit
```

期望：

```text
openclaw security audit
=> 0 critical · 0 warn
```

## 边界

- 这份文件不保存 token、API key、账号、provider 密钥等敏感值。
- 如果未来 Control UI 暴露到公网、多人共用、或经复杂反代开放到外部设备，需要重新做安全评估；当前配置只按个人本机使用场景验收。
