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

相关计划任务：

- `OpenClaw Gateway Watchdog`
- `OpenClaw Gateway`

默认行为：

- 登录时自动检查 gateway
- 每 3 分钟巡检一次
- 如果本地 `http://127.0.0.1:18789/` 不通，则自动执行 `openclaw gateway restart`

日志位置：

- `%LOCALAPPDATA%\OpenClaw\watchdog\gateway-watchdog.log`

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
