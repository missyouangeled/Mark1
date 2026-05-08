# 掌机（Windows）OpenClaw 维护说明

- 适用机器：掌机（Windows）
- 系统 / OS：Windows
- 文档类型：本机专用说明
- 当前维护对象：ROG 掌机 / `TABLET-EH5U3C01`（系统里也可能显示为 `TABLET-EH5U3CO1`）
- 最近维护日期：2026-05-07
- 最近维护时间：2026-05-07 14:23 CST (+0800)
- 最近维护来源：公司（Linux）机器通过 SSH 远程维护掌机（Windows）

## 用途

这份说明只面向 **ROG 掌机 / 掌机（Windows）** 这台机器。

目的：让任何设备上的 OpenClaw 只要读到这份文档，就能快速明白这台掌机当前的 OpenClaw 状态、2026-05-07 做过哪些关键修复、哪些问题已经解决、哪些问题只是暂时缓解，以及后续应该怎么继续维护。

---

## 最短理解版（主流程）

如果你只想知道这台 **掌机（Windows）** 在拉完 GitHub 更新后默认应该怎么继续，先记这 5 步：

1. 掌机上的 OpenClaw 在本机完成 `git pull --ff-only` 并重启 gateway
2. 重启后，它先识别自己是 **掌机（Windows）**
3. 然后按顺序读取：
   - `HOST_CONTEXT.md`
   - `docs/多机器-读取与更新规则.md`
   - `docs/掌机-Windows-OpenClaw-维护说明.md`
   - `TOOLS.md` 里标注为 `掌机（Windows）` 的条目
   - 相关 `.ps1` / `.cmd` 脚本说明
4. 接着它应根据这些说明，**自主完成当前机器需要的下载 / 安装 / 修复 / 验证**
5. 完成后再检查：
   - `openclaw gateway status`
   - 本地 Control UI：`http://127.0.0.1:18789/`
   - 若涉及微信，再继续看本文后面的“优先判断顺序”与“关键修复记录”

一句话记忆：

> 这台掌机是 **Windows**；主流程是“拉更新 / 重启后由本机 OpenClaw 自己读文档并继续自更新”，`.cmd / .ps1` 只是手动兜底入口，不是主路线。

### 手动兜底入口（只有在需要人工强制触发时才用）

如果确实需要人在掌机上手动触发一次同步，可以再用：

- `scripts/update-openclaw.cmd`
- `powershell -ExecutionPolicy Bypass -File .\scripts\update-openclaw.ps1`

---

## 2026-05-07 当前结论（先看这里）

截至 **2026-05-07 14:23 CST (+0800)**，这台掌机上的 OpenClaw 结论如下：

1. **OpenClaw gateway 当前可用**
   - 本地 dashboard：`http://127.0.0.1:18789/`
   - gateway 处于运行状态

2. **微信链路当前已恢复到可正常使用状态**
   - `openclaw-weixin` 当前状态：`ON / OK / configured`
   - 已完成重新扫码登录
   - 微信消息已验证：能收、能回

3. **默认模型当前仍为 DeepSeek**
   - 当前默认主模型：`deepseek/deepseek-chat`
   - 这是为了优先保证掌机上的启动稳定性与微信链路稳定性

4. **GitHub Copilot 当前已启用、已加载，但不是默认模型**
   - `github-copilot` provider 当前状态：`enabled + loaded`
   - 说明：不是“不能用 Copilot”，而是“当前默认不走 Copilot”

5. **电池供电策略已经修正**
   - `OpenClaw Gateway` 计划任务当前已修到：
     - `DisallowStartIfOnBatteries = False`
     - `StopIfGoingOnBatteries = False`
   - 这意味着：**拔掉电源后，不应再因为计划任务设置而直接把 OpenClaw 停掉**

6. **Watchdog 当前仍保持卸载状态**
   - 这是用户明确要求，用来避免 watchdog 持续自动重启掩盖真正根因
   - 当前不依赖 watchdog 兜底保活

7. **当前剩余问题已经从“不能用”收敛为“小尾巴”**
   - 首几条回复偶尔偏慢
   - `sendTyping` 偶发超时
   - `getUpdates` 偶发 `AbortError` / 网络抖动，但能自行续上
   - 这些更像性能/稳定性优化项，不是主链路故障

---

## 2026-05-07 关键修复记录

### 1. 微信插件彻底删干净重装

本次按“彻底删干净重装”执行，而不是保守修复。

已清理内容：

- 卸载 `openclaw-weixin`
- 删除 `C:\Users\GOG\.openclaw\openclaw-weixin`
- 删除 `C:\Users\GOG\.openclaw\credentials\openclaw-weixin-pairing.json`
- 清理 `C:\Users\GOG\.openclaw\openclaw.json` 中与 `openclaw-weixin` 直接相关的配置项

重装结果：

- 当前实际恢复使用的插件版本：`openclaw-weixin 2.4.1`
- 微信新账号已重新落盘：
  - `C:\Users\GOG\.openclaw\openclaw-weixin\accounts.json`
  - `C:\Users\GOG\.openclaw\openclaw-weixin\accounts\0340e6583b0a-im-bot.json`

### 2. 修复二维码登录阶段的 `fetch failed`

本次把微信登录阶段的模糊错误：

- `TypeError: fetch failed`

进一步收敛为更具体的兼容性问题：

- `UND_ERR_INVALID_ARG`
- `invalid content-length header`

根因结论：

- `openclaw-weixin` 在 OpenClaw 运行环境里，向微信接口请求二维码时，手工设置的 `Content-Length` 头与当前 `undici` 行为存在兼容问题
- 同机用 Node 直接发等价请求可以成功，说明不是单纯网络不通

本次采取的修复：

- 移除插件里手工设置的 `Content-Length`
- 让底层自动计算请求体长度

结果：

- 二维码拉取恢复正常
- 用户已重新扫码并确认连接

### 3. 修复“扫码成功但微信通道没真正拉起”

本次还遇到一个容易误判的问题：

- 用户扫码确认成功后，登录态其实已经保存
- 但 OpenClaw 自动写回 `openclaw.json` 时被 size-drop 保护拦住
- 导致微信通道没有被自动重新拉起

本次处理方式：

- 手工补齐 `channels.openclaw-weixin` 配置
- 手工补齐账号启用项
- 重启 gateway

结果：

- `openclaw-weixin` 成功进入 `ON / OK / configured`
- 日志已看到：
  - `starting weixin provider`
  - `weixin monitor started`
  - `getUpdates` 正常轮询
  - 微信消息已实测“能收、能回”

### 4. 模型链路状态调整

#### 当前默认模型

- `agents.defaults.model.primary = deepseek/deepseek-chat`

#### 当前 GitHub Copilot 状态

- `github-copilot` provider 已启用、已加载
- 当前不是默认模型

这样做的原因：

- 保留 Copilot 能力可用
- 但继续让掌机的默认链路优先走 DeepSeek，避免刚恢复的微信链路又被默认模型切换引入新变量

结论：

- **现在不是“只能用 DeepSeek”**
- 而是：**默认走 DeepSeek，Copilot 也已经能用，但默认不切过去**

### 5. 电池供电策略修复

本次再次确认并执行：

- `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1`

修复后的计划任务状态：

- `DisallowStartIfOnBatteries = False`
- `StopIfGoingOnBatteries = False`

当前结论：

- **拔掉电源后，不应再因为计划任务的电池限制而停掉 OpenClaw**

---

## 当前已部署内容

### 1. Gateway 计划任务

相关计划任务：

- `OpenClaw Gateway`

当前状态：

- 已安装
- 已注册
- 当前运行中
- 电池供电限制已修正为安全状态（False / False）

### 2. Watchdog

相关脚本：

- `scripts/openclaw-gateway-watchdog.ps1`
- `scripts/install-openclaw-gateway-watchdog.ps1`
- `scripts/uninstall-openclaw-gateway-watchdog.ps1`

当前状态：

- **`OpenClaw Gateway Watchdog` 当前已卸载**

原因：

- 用户明确要求：先移除 watchdog，避免“掉了以后再自动拉起来”掩盖根因

说明：

- 若未来确实需要恢复兜底保活，可重新执行：
  - `scripts/install-openclaw-gateway-watchdog.ps1`

### 3. 一键关闭 / 恢复入口

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

1. 禁用 `OpenClaw Gateway Watchdog`（若存在）
2. 禁用 `OpenClaw Gateway`
3. 停止当前 gateway 实例

恢复逻辑：

1. 启用 `OpenClaw Gateway`
2. 启用 `OpenClaw Gateway Watchdog`（若用户决定恢复）
3. 启动 gateway

---

## 2026-05-07 系统清理记录

本次已做一轮保守清理，只删除明确的临时文件 / 缓存 / 日志 / 没用的安装包。

### 已清理内容

- OpenClaw 旧的 `*.clobbered.*` / `*.rejected.*` / `*.tmp` / 部分旧备份残留
- `sessions/*.bak-*` 残留
- `devices/*.tmp` 残留
- `%TEMP%` 下的 OpenClaw 诊断临时目录
- `%TEMP%` 下的 `weixin-manual-install` 残留
- `%TEMP%` 下的 `node-compile-cache`
- `%TEMP%` 下的 `jiti` 缓存
- `%TEMP%` 下部分日志与 `*.tmp` 文件
- Downloads 中明确没用的安装包/安装器：
  - `WeChatWin_4.1.8.exe`
  - `node-v22.22.2-x64.msi`
  - `tailscale-setup-1.96.3.exe`
  - `EAappInstaller.exe`
  - `FLiNGTrainer_setup.exe`

### 近似释放空间

- 约 **310 MB**

### 明确保留的文件

- `rustdesk-1.4.6-x86_64.exe`
- 视频文件
- OpenClaw 关键配置备份
- 微信账号状态文件
- 任何用途不明确、可能仍有用的压缩包 / 文档 / 项目文件

---

## 当前维护建议

### 1. 日常使用建议

当前建议：

- 继续正常使用掌机上的 OpenClaw 与微信链路
- 不要重复扫码
- 默认保持 DeepSeek 当主模型
- Copilot 保持启用但暂不切默认

### 2. 掌机（Windows）下载更新后的默认处理方式

当这台掌机从 GitHub 拉到最新 workspace，或用户明确说：

- `同步这台机器`
- `更新这台机器`
- `拉一下最新规则`

在 **掌机（Windows）** 上，默认应按 Windows 方式理解，而不是照 Linux 的命令路径生搬硬套。

#### 推荐更新入口

优先直接运行：

- `scripts/update-openclaw.cmd`

或在 PowerShell 中运行：

- `powershell -ExecutionPolicy Bypass -File .\scripts\update-openclaw.ps1`

#### 这两个脚本的默认行为

1. 进入当前 workspace 仓库
2. 执行 `git pull --ff-only`
3. 若检测到新提交，则自动执行 `openclaw gateway restart`
4. 若用户明确要求“即使没更新也立刻应用一次”，则可用 PowerShell 版本加 `-AlwaysRestart`

#### 掌机上更新后的默认阅读顺序

如果这台掌机刚拉完更新，OpenClaw 应优先按这个顺序理解规则：

1. `HOST_CONTEXT.md`
2. `docs/多机器-读取与更新规则.md`
3. 本文档 `docs/掌机-Windows-OpenClaw-维护说明.md`
4. `TOOLS.md` 里所有标注为 `掌机（Windows）` 的条目
5. 再看对应的 `.ps1` / `.cmd` 脚本

#### 掌机上默认不要误用的更新方式

- 不要把公司（Linux）的 `systemd` / shell 更新方式直接搬到掌机执行
- 不要优先按 Linux 路径去找 `~/.config/systemd/user/*`
- 不要把“gateway 重启”理解成 Linux service 操作；在掌机上应按 Windows 下的 `openclaw gateway restart` 或既有 `.cmd/.ps1` 包装器处理

### 3. 如果后续再出问题，优先判断顺序

优先按这个顺序判断：

1. `openclaw status --deep`
2. 看微信通道是否仍是 `ON / OK / configured`
3. 看 `OpenClaw Gateway` 是否仍在运行
4. 看电池策略是否仍是 False / False
5. 再看 `%LOCALAPPDATA%\OpenClaw\` 和 `%TEMP%\openclaw\openclaw-YYYY-MM-DD.log`

### 3. 对当前小尾巴的理解

这些现象目前视为“已知但可接受”：

- 首几条回复偶尔偏慢
- `sendTyping` 偶发超时
- `getUpdates` 偶发 `AbortError` / 网络抖动后自行续上

当前不建议为了追求“更丝滑”而贸然大改参数，因为主链路已经恢复。

---

## SSD 优化

相关脚本：

- `scripts/optimize-ssd-trim-zhangji-windows.ps1`
- `scripts/optimize-ssd-trim-zhangji-windows.cmd`

用途：

- 对掌机这台 Windows 机器的 SSD 卷执行 `Analyze + ReTrim`

注意：

- 需要“以管理员身份运行”

---

## 退出机制约定

对于 **掌机（Windows）**：

当用户明确说“关闭 OpenClaw / 先停掉 / 关这个”时，默认按“关闭 OpenClaw 网关链路”理解，而不是关闭整个 Windows 系统。

---

## 标注规则

今后凡是会同步到 GitHub、且内容属于某台机器或某类环境专用的系统说明、修复记录、脚本说明，都必须在正文显式写出：

- 适用机器 / 环境标签
- 系统 / OS
- 日期
- 时间
- 当前结论 / 影响范围

这份文档当前就是 **掌机（Windows）** 的专用维护文档，不适用于公司（Linux）机器直接照抄执行。
