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

### 0. 双盘空间预检与落盘规则（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-09
- 背景：当前公司 Linux 机有两块 50G 盘：根盘 `/` 与数据盘 `/mnt/data`。以后凡是下载大文件、解压模型、同步大仓库、生成大体积中间产物，都不要上来就直接写根盘。

当前固定规则：

1. **先预估，再执行**
   - 在下载、解压、模型转换、批量生成音频/视频、缓存大模型、复制大目录前，先估算一次体积。
   - 默认按“**预计大小 × 2**”估算峰值占用，覆盖下载包 + 解压中转 + 临时缓存。

2. **根盘保底空余**
   - 执行后根盘 `/` 剩余空间不应低于 **8G**。
   - 更稳妥的目标是长期尽量保持 **10G** 以上空余。

3. **大于等于 1G 的新增占用默认优先去 `/mnt/data`**
   - 包括但不限于：模型文件、语音/视频素材、研究样本、临时导入包、批量输出目录。
   - 默认 staging 目录：`/mnt/data/openclaw/download-staging/`

4. **只有小而短命的东西才优先放根盘**
   - 例如 `<300M` 的临时脚本输出、很快会删除的小文件、明显依赖固定相对路径的轻量缓存。
   - 但如果根盘本身已紧张，即便是中等体积文件，也应转去 `/mnt/data`。

5. **能用软链接保路径，就不要硬改上层调用路径**
   - 如果某些既有工具已经写死在 `~/.openclaw/workspace/tmp/...`、`~/.cache/...` 这类路径，优先考虑把实际大目录迁到 `/mnt/data/openclaw/...`，再在原处放回 symlink。
   - 这样既能减轻根盘压力，也能尽量避免改动主链路。

已新增辅助脚本：

- `scripts/storage-preflight.sh`

用法示例：

```bash
bash scripts/storage-preflight.sh 1.5G ChatTTS-assets
bash scripts/storage-preflight.sh 800M 临时解压包
```

当前已落地的迁移策略（2026-05-09）：

- `~/.openclaw/workspace/tmp/voice-replies` → 迁到 `/mnt/data/openclaw/workspace-tmp/voice-replies` 后用 symlink 回挂
- `~/.cache/modelscope` → 迁到 `/mnt/data/openclaw/modelscope-cache` 后用 symlink 回挂

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

### 4. NVIDIA 免费语音模型桥接（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 维护时间：2026-05-08
- 用途：让当前这台公司 Linux 机上的 OpenClaw gateway 通过本地 bridge 使用 NVIDIA 免费语音模型（TTS / ASR），并保持主 gateway 继续稳定运行。

当前方案：

- OpenClaw gateway 继续监听：`127.0.0.1:18789`
- 本地 NVIDIA 音频 bridge 监听：`127.0.0.1:18890`
- gateway 新增代理路径：
  - `/v1/audio/speech`
  - `/v1/audio/transcriptions`
- bridge 内部通过 `nvidia-riva-client` 走 `grpc.nvcf.nvidia.com:443` + `function-id` 调用 NVIDIA 公共免费语音函数，而不是直接依赖 `integrate.api.nvidia.com/v1/audio/...`

相关文件：

- bridge 服务代码：`tools/nvidia-audio-bridge/bridge.py`
- bridge README：`tools/nvidia-audio-bridge/README.md`
- 依赖清单：`tools/nvidia-audio-bridge/requirements.txt`
- repo 内 service 模板：`tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service`
- gateway 补丁脚本：`scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
- bridge 用户态 systemd：`~/.config/systemd/user/openclaw-nvidia-audio-bridge.service`
- OpenClaw 配置：`~/.openclaw/openclaw.json`
- OpenClaw 安装产物（被补丁修改）：`~/.npm-global/lib/node_modules/openclaw/dist/server.impl-*.js`
- 新增代理模块：`~/.npm-global/lib/node_modules/openclaw/dist/openai-audio-http-nvidia-bridge.js`

当前关键配置：

- `~/.openclaw/openclaw.json` 已增加：

```json
{
  "gateway": {
    "http": {
      "endpoints": {
        "chatCompletions": {
          "enabled": true
        }
      }
    }
  }
}
```

说明：

- 这是为了让 OpenClaw 内部 `openAiCompatEnabled` 变为启用状态，从而让新增的音频 HTTP 路由真正生效。
- 这个改动仍然保持 gateway 为 `loopback` 绑定，不会把本机接口直接暴露到外网。

当前已验证结果：

- 通过 gateway 调用 TTS：`200 OK`，可返回 `audio/mpeg`
- 通过 gateway 调用 ASR：`200 OK`
- 使用 gateway 先生成 TTS，再把生成的 MP3 回送 ASR，已得到正确转写：`Hello from nvidia gateway bridge test.`

新机器最小落地步骤：

1. 先读 `tools/nvidia-audio-bridge/README.md`，确认用途、依赖和验证命令。
2. 确认 `~/.openclaw/openclaw.json` 里已有可用的 `models.providers.nvidia.apiKey`。
3. 准备 bridge 运行环境（当前公司 Linux 机使用 `~/.local/share/openclaw-nvidia-audio-bridge-venv`）。
4. 复制 repo 内模板 `tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service` 到 `~/.config/systemd/user/`，执行 `systemctl --user daemon-reload && systemctl --user enable --now openclaw-nvidia-audio-bridge.service`。
5. 执行 `python3 scripts/apply-openclaw-nvidia-audio-gateway-patch.py` 给 OpenClaw 打补丁，再重启 bridge 与 gateway。
6. 用 README 里的 `/health`、TTS、ASR 验证命令做最小回归。

systemd 维护命令：

```bash
systemctl --user status openclaw-nvidia-audio-bridge.service
systemctl --user restart openclaw-nvidia-audio-bridge.service
journalctl --user -u openclaw-nvidia-audio-bridge.service -n 100 --no-pager
```

注意：

- 该方案是本机补丁，不是 OpenClaw 官方现成配置项；未来 OpenClaw 升级后，如果 `dist/server.impl-*.js` 文件名或结构变化，需要重新执行或调整补丁脚本。
- 如果 gateway 重启后音频接口重新变成 `404` 或 `502`，优先检查两点：
  1. `openclaw-nvidia-audio-bridge.service` 是否仍在运行；
  2. OpenClaw 升级后补丁是否被覆盖。
- 不要把 NVIDIA API key 硬编码进脚本；bridge 会从 `~/.openclaw/openclaw.json` 中读取现有 `providers.nvidia.apiKey`。

## 标注规则

今后凡是会同步到 GitHub、且内容属于 **公司（Linux）** 专用的系统说明、脚本说明、修复记录，都必须在正文显式写出：

- 适用机器：`公司（Linux）`
- 系统 / OS：`Linux`
- 用途说明
