# 公司（Linux）OpenClaw 维护说明

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 文档类型：本机专用说明

## 用途

这份说明只面向 **公司 Linux 机**，用于说明这台机器上应优先读取的 OpenClaw 维护内容，以及 Linux 环境下应优先更新的脚本和配置。

## 机器识别

当前环境满足以下任一条件时，按 **公司（Linux）** 理解：

- 运行时主机名：`missyouangeled-VMware-Virtual-Platform`
- 系统 hostname / computer name：`missyouangeled-VMware-Virtual-Platform`
- 本地 IPv4（兜底）：`192.168.233.130`

对应默认理解：

- 设备名：`公司 Linux 机`
- 环境标签：`公司`
- 系统 / OS：`Linux`

## 默认优先读取

当 OpenClaw 运行在公司 Linux 机上，并且任务涉及系统维护、OpenClaw 保活、配置同步、脚本修复时，默认优先读取：

1. `HOST_CONTEXT.md`
2. `docs/多机器-读取与更新规则.md`
3. 本文档 `docs/公司-Linux-OpenClaw-维护说明.md`
4. `TOOLS.md` 里与 Linux 相关的条目
5. Linux 相关脚本 / 配置：
   - `scripts/openclaw-resume-watch.sh`
   - `~/.config/systemd/user/openclaw-resume-watch.service`
   - `~/.config/systemd/user/openclaw-resume-watch.timer`

## Linux 环境下默认优先更新的部分

如果任务只影响公司 Linux 环境，默认优先更新：

- 本文档 `docs/公司-Linux-OpenClaw-维护说明.md`
- Linux 专用脚本（例如 `scripts/openclaw-resume-watch.sh`）
- Linux systemd 用户单元说明
- `TOOLS.md` 中 Linux 相关条目

如果任务会影响所有机器，再同步更新通用规则文档。

## Linux 环境下默认不要误用的部分

在公司 Linux 环境下，以下内容默认只作参考，不应直接执行：

- `掌机（Windows）` 专用脚本
- `.ps1` / `.cmd` 脚本
- Windows Scheduled Task 相关说明
- Windows 桌面快捷入口 / `.lnk` 说明

## 同步更新工作流

当用户说“同步这台机器 / 更新这台机器 / 拉一下最新规则”时，在 **公司（Linux）** 环境下默认理解为：

1. 进入当前 workspace 仓库
2. 执行 `git pull --ff-only`
3. 如果仓库有变化，或用户要求立即生效，则执行 `openclaw gateway restart`

## 当前已知 Linux 维护点

### 1. 恢复后自愈 watcher

相关脚本：

- `scripts/openclaw-resume-watch.sh`

用途：

- 检测休眠恢复或长时间暂停后，自动重启 `openclaw-gateway.service`

### 2. systemd 用户单元

相关文件：

- `~/.config/systemd/user/openclaw-resume-watch.service`
- `~/.config/systemd/user/openclaw-resume-watch.timer`

用途：

- 在 Linux 用户态下调度 resume-watch 逻辑

### 3. Control UI 品牌覆盖（贾维斯）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-07
- 维护来源：用户希望把 Control UI 左上角默认的 OpenClaw / 小龙虾品牌，逐步替换成更贴近“贾维斯”的品牌呈现，并要求采用“可重复应用”的方案，避免 OpenClaw 升级后又回到默认样式。

相关文件：

- 配置：`config/control-ui-branding.json`
- 应用脚本：`scripts/apply-openclaw-control-ui-branding.py`
- systemd 自动重应用：`~/.config/systemd/user/openclaw-gateway.service.d/branding.conf`
- 当前默认品牌图：`avatars/jarvis-neon-20260507.png`

用途：

- 重复应用 Control UI 左上角品牌名与 logo 覆盖
- 同步覆盖浏览器标题、favicon / apple-touch-icon、manifest 名称与默认通知标题
- 通过页面注入脚本，把 Control UI 里可见的 `OpenClaw` 文案尽量替换成“贾维斯”（保留聊天内容 / 代码块等常见高风险区域的跳过规则）
- 尽量避免每次升级后再手工去改 `dist/control-ui/` 里的静态产物

当前默认配置：

- 左上角品牌名：`贾维斯`
- 小标题：`CONTROL`
- 浏览器标题：`贾维斯 Control`

应用方式：

```bash
python3 scripts/apply-openclaw-control-ui-branding.py
```

说明：

- 该脚本会把配置中的品牌图复制到本机 OpenClaw 安装目录下的 `dist/control-ui/`，并注入一个额外的 `jarvis-branding-override.js` 覆盖脚本。
- 另外已在公司 Linux 机的 `openclaw-gateway.service` 上挂了一个 `ExecStartPre`：每次 gateway 启动前，都会自动先跑一遍这个品牌补丁脚本；即使以后 OpenClaw 升级覆盖了静态资源，只要重启 gateway，就会自动重新覆盖。
- 该 `ExecStartPre` 使用了前缀 `-` 忽略失败，避免品牌补丁偶发出错时直接把 gateway 启动也一并卡死。
- 如果以后用户想把左上角名称改成 `J.A.R.V.I.S.`、改别的图、或继续往电影风格靠，只需要改 `config/control-ui-branding.json` 再重跑脚本。
- 这是“可重复应用补丁”，不是官方配置项；如果以后 OpenClaw 前端结构变化很大，补丁脚本可能需要跟着调整，但总体维护点已经集中到这几个文件里，不需要再手工逐个改 dist 文件。

## 标注规则

今后凡是会同步到 GitHub、且内容属于 **公司（Linux）** 专用的系统说明、脚本说明、修复记录，都必须在正文显式写出：

- 适用机器：`公司（Linux）`
- 系统 / OS：`Linux`
- 用途说明
