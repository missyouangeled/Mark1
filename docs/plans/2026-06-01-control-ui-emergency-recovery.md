# Control UI 黑屏应急修复器设计

- 创建时间：2026-06-01 12:40 CST
- 适用机器：通用设计；当前先在公司（Linux）落地验证
- 系统 / OS：Linux 当前验证，脚本尽量保持跨平台路径探测

## 背景

点点上午遇到过 Control UI 整页黑屏、怎么也打不开的问题。当前已有多条可能影响 Control UI 的链路：

- 浏览器缓存 / Service Worker / 扩展 / 本地存储
- Gateway 主服务 / 端口 / WebSocket 探针
- Control UI 静态 HTML / hashed JS / CSS / manifest / favicon
- 自定义注入 `jarvis-branding-override.js`
- 模型选择器补丁对 hashed bundle 的修改
- frontstage broker 静态 JSON / sidecar / unified proxy
- systemd user services / timers

需要一个低侵入应急入口，从“浏览器视角”开始逐层诊断，并能执行安全修复。

## 成功标准

1. `check` 模式只诊断不修改。
2. `repair` 模式只做低风险修复：重建 broker 视图、重打 Control UI 补丁、重启必要服务、验证页面静态资源。
3. `safe-mode` 模式用于黑屏时兜底：临时禁用自定义 branding 注入，保留原始 Control UI 主 bundle，优先让页面能打开。
4. 不安装浏览器插件，不清用户浏览器数据，不碰系统底层驱动/硬件监控，不新增 timer。
5. 输出给用户可执行的浏览器侧应急步骤：无痕窗口、禁扩展、清站点数据、强刷、检查控制台。

## 分层流程

### L0 浏览器侧建议（不自动改）

- 输出当前 Control UI 地址。
- 建议按顺序尝试：强刷、无痕窗口、禁用扩展、清理 `127.0.0.1:18789` 站点数据。
- 如果页面仍黑：让脚本继续看服务器侧。

### L1 Gateway / 服务层

- `openclaw gateway status`
- `openclaw status` 或轻量 HTTP 探测
- `GET /` 是否返回 HTML

修复动作：

- `openclaw gateway restart`（仅在 repair 模式且 Gateway 不可达/探针失败时）

### L2 Control UI 静态资源层

- 解析 `index.html` 的 `script src` / `link href`
- 检查主 JS / CSS / branding override / manifest / icon 是否 HTTP 200 且非空
- 检查 `<openclaw-app>` mount 点存在
- 检查 mount fallback 存在

修复动作：

- 重跑 `apply-openclaw-control-ui-branding.py`
- 重跑 `apply-openclaw-session-model-selector-fix.py`

### L3 自定义注入层

- 检查 `jarvis-branding-override.js` 是否存在、大小、关键函数、是否明显异常
- 检查 `index.html` 的 `jarvis-branding` 注入块是否存在

修复动作：

- `repair`：重打 branding
- `safe-mode`：备份 `index.html`，移除 branding 注入块，把 `jarvis-branding-override.js` 旁路改名为 `.disabled-时间戳`；不删除文件

### L4 前台辅助数据层

- 检查 broker views 是否存在
- 检查 `jarvis-frontstage-snapshot.json`
- 检查 sidecar `http://127.0.0.1:18790/healthz`
- 检查 unified proxy `http://127.0.0.1:18788/healthz`

修复动作：

- `openclaw-frontstage-broker.py rebuild-views`
- `apply-openclaw-frontstage-broker-data.py` 验证/重建
- `apply-openclaw-infos-handle-gateway-proxy.py --install-user-systemd --enable --restart --verify`

### L5 收尾验证

- 重新 GET `/`
- 重新 GET 所有静态资源
- `openclaw-patch-repair.py --check`
- `openclaw-system-summary.py --print-human`

## 涉及文件

- 新增：`scripts/openclaw-control-ui-emergency.py`
- 新增：`docs/通用-OpenClaw-ControlUI黑屏应急修复.md`
- 更新：`TOOLS.md`
- 更新：`docs/通用-OpenClaw-当前正式架构状态.md`
- 更新：`docs/通用-OpenClaw-总控面板.md`
- 变更流水：`docs/通用-OpenClaw-补丁变更流水.md`

## 验证命令

```bash
python3 scripts/openclaw-control-ui-emergency.py --check --print-json
python3 scripts/openclaw-control-ui-emergency.py --repair --dry-run --print-human
python3 scripts/openclaw-control-ui-emergency.py --safe-mode --dry-run --print-human
python3 scripts/openclaw-control-ui-emergency.py --check --print-human
python3 scripts/openclaw-system-summary.py --print-human
```
