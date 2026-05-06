# 掌机（Windows）OpenClaw 维护说明

- 适用机器：掌机（Windows）
- 系统 / OS：Windows
- 文档类型：本机专用说明

## 用途

这份说明只面向 **ROG 掌机 / 掌机（Windows）** 这台机器，用于说明当前已经部署的 OpenClaw 本地维护机制、停机方式、恢复方式与 SSD 优化脚本。

## 当前已部署内容

### 1. Gateway 保活

相关脚本：

- `scripts/openclaw-gateway-watchdog.ps1`
- `scripts/install-openclaw-gateway-watchdog.ps1`
- `scripts/uninstall-openclaw-gateway-watchdog.ps1`
- `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1`
- `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.cmd`

相关计划任务：

- `OpenClaw Gateway Watchdog`
- `OpenClaw Gateway`

默认行为：

- 登录时自动检查 gateway
- 每 3 分钟巡检一次
- 如果本地 `http://127.0.0.1:18789/` 不通，则优先执行 `openclaw gateway restart`
- 如果发现原生 `OpenClaw Gateway` 计划任务带有“仅交流电供电时启动 / 切到电池就停止”的限制，watchdog 会继续直接调用 `C:\Users\GOG\.openclaw\gateway.cmd` 兜底拉起网关，避免掌机在电池模式下失联

当前已确认现象：

- 这台掌机上的原生 `OpenClaw Gateway` 计划任务 XML 当前带有：
  - `<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>`
  - `<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>`
- 这会导致“只在接通电源时自动启动 / 保持运行”的错误行为
- 由于当前会话没有可用提权能力，暂未直接改写该原生任务；已通过 watchdog 与手动启动脚本加入 direct-wrapper fallback 规避此问题
- 如需把底层原生任务也修正为电池安全，可执行：
  - `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1`
  - 或 `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.cmd`
  - 某些系统环境下需要“以管理员身份运行”

日志位置：

- `%LOCALAPPDATA%\OpenClaw\watchdog\gateway-watchdog.log`

当前调试状态（2026-05-06）：

- 用户已明确要求：为避免 watchdog 持续自动重启掩盖根因，先把 `OpenClaw Gateway Watchdog` 从掌机上彻底移除
- 当前已执行：`scripts/uninstall-openclaw-gateway-watchdog.ps1`
- 当前结果：计划任务 `OpenClaw Gateway Watchdog` 已卸载，不再继续对 gateway 做自动健康检查与自动重启
- 这意味着后续需要人工观察并手动拉起 gateway，但也能更干净地暴露“微信消息进入后回复链路把 gateway 拖挂”的根本问题
- 若后续确有需要恢复兜底保活，可重新执行：`scripts/install-openclaw-gateway-watchdog.ps1`

### 1.5 启动稳定性（GitHub Copilot / 默认模型链路）

已确认掌机上存在一类会让 gateway“能启动但不稳定”、并进一步把微信插件也拖着一起掉线的启动问题。

典型现象：

- `openclaw gateway restart` 可能长时间卡住，最后报 health check / probe timeout
- watchdog 分钟巡检会误判 gateway 不健康，然后反复自动重启
- Control UI 会出现 websocket 握手超时或反复重连
- 日志里可见：
  - `startup model warmup timed out after 5000ms`
  - `models.list` 偶发耗时非常长（现场见过约 68s / 74s）
  - `liveness warning` 中出现很高的 event loop delay / utilization

根因收敛：

- 仅关闭 `github-copilot` 的启动期 discovery 还不够
- 当默认模型仍指向 `github-copilot/gpt-5.4`，且该模型仍保留在 `agents.defaults.models` 里时，启动 warmup / 模型列表链路仍可能把 event loop 卡住
- 一旦卡到 watchdog 的分钟健康检查窗口，watchdog 就会把 gateway 当成“坏了”，于是继续自动重启；微信插件本身虽然能起来，但会被这些重启一起打断

本机当前采用的稳定化设置：

- 配置文件：`C:\Users\GOG\.openclaw\openclaw.json`
- 已设置：
  - `plugins.entries.github-copilot.config.discovery.enabled = false`
  - `plugins.entries.github-copilot.enabled = false`
  - `agents.defaults.model.primary = deepseek/deepseek-chat`
  - 从 `agents.defaults.models` 中移除 `github-copilot/gpt-5.4`

作用：

- 禁用 **GitHub Copilot 启动期 discovery**
- 同时把默认运行链路从 Copilot 切回 DeepSeek，避免启动 warmup / models.list 再次走到 Copilot 那条慢路径
- 保留 `openclaw-weixin` 正常启用，优先保证掌机上的 OpenClaw 与微信插件稳定在线

补充说明：

- 首次缓解前备份：`C:\Users\GOG\.openclaw\openclaw.json.bak-20260506-1505`
- 稳定化调整前备份：`C:\Users\GOG\.openclaw\openclaw.json.bak-20260506-1526-stability`
- 当前验证结果：
  - `openclaw gateway restart` 可完成
  - 本地 HTTP 探测返回 `200`
  - watchdog 在后续分钟巡检中恢复为 `Gateway healthy: HTTP probe ok`
  - 微信插件日志可见 `weixin monitor started`
- 若未来需要重新启用 GitHub Copilot，建议逐项回退并重新观察 watchdog / models.list / warmup，而不要一次性全部恢复

### 2. 一键关闭 / 恢复入口

相关脚本：

- `scripts/stop-openclaw-gateway-zhangji-windows.ps1`
- `scripts/stop-openclaw-gateway-zhangji-windows.cmd`
- `scripts/start-openclaw-gateway-zhangji-windows.ps1`
- `scripts/start-openclaw-gateway-zhangji-windows.cmd`

桌面入口：

- `关闭 OpenClaw（掌机）.cmd`
- `启动 OpenClaw（掌机）.cmd`
- `关闭 OpenClaw（掌机）.lnk`
- `启动 OpenClaw（掌机）.lnk`

关闭逻辑：

1. 禁用 `OpenClaw Gateway Watchdog`
2. 禁用 `OpenClaw Gateway`
3. 停止当前 gateway 实例

恢复逻辑：

1. 启用 `OpenClaw Gateway`
2. 启用 `OpenClaw Gateway Watchdog`
3. 启动 gateway

## 退出机制约定

对于 **掌机（Windows）**：

当用户明确说“关闭 OpenClaw / 先停掉 / 关这个”时，默认按“关闭 OpenClaw 网关链路”理解，而不是关闭整个 Windows 系统。

## SSD 优化

相关脚本：

- `scripts/optimize-ssd-trim-zhangji-windows.ps1`
- `scripts/optimize-ssd-trim-zhangji-windows.cmd`

用途：

- 对掌机这台 Windows 机器的 SSD 卷执行 `Analyze + ReTrim`

注意：

- 需要“以管理员身份运行”

## 标注规则

今后凡是会同步到 GitHub、且内容属于某台机器或某类环境专用的系统说明、修复记录、脚本说明，都必须在正文显式写出：

- 适用机器 / 环境标签
- 系统 / OS

例如：

- `公司（Linux）`
- `掌机（Windows）`
- 若为跨机器通用内容，则明确写 `通用`
