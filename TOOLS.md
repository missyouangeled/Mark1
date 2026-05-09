# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Local Setup Notes

### OpenClaw automation

- 适用机器：通用（其中带“掌机”字样的条目仅适用于掌机（Windows））
- 系统 / OS：通用 / Windows / Linux（按各条目说明执行）

- Startup online notice is driven by `BOOT.md` + the `boot-md` hook.
- Resume recovery watcher script: `scripts/openclaw-resume-watch.sh`
- Windows 更新脚本（掌机）：
  - 适用机器：掌机（Windows）
  - 系统 / OS：Windows
  - `scripts/update-openclaw.ps1`
  - `scripts/update-openclaw.cmd`
  - 用途：执行 `git pull --ff-only`，若仓库有新提交则自动 `openclaw gateway restart`
  - 掌机建议直接运行：`.\scripts\update-openclaw.cmd`
- Windows gateway 保活（掌机）：
  - 适用机器：掌机（Windows）
  - 系统 / OS：Windows
  - watchdog 脚本：`scripts/openclaw-gateway-watchdog.ps1`
  - 安装脚本：`scripts/install-openclaw-gateway-watchdog.ps1`
  - 卸载脚本：`scripts/uninstall-openclaw-gateway-watchdog.ps1`
  - 停机脚本：`scripts/stop-openclaw-gateway-zhangji-windows.ps1`
  - 恢复脚本：`scripts/start-openclaw-gateway-zhangji-windows.ps1`
  - cmd 包装器：`scripts/install-openclaw-gateway-watchdog.cmd` / `scripts/uninstall-openclaw-gateway-watchdog.cmd` / `scripts/stop-openclaw-gateway-zhangji-windows.cmd` / `scripts/start-openclaw-gateway-zhangji-windows.cmd`
  - 桌面快捷入口：`关闭 OpenClaw（掌机）.cmd` / `启动 OpenClaw（掌机）.cmd`
  - 桌面快捷方式：`关闭 OpenClaw（掌机）.lnk` / `启动 OpenClaw（掌机）.lnk`
  - 电池策略修复脚本：`scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1`
  - cmd 包装器：`scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.cmd`
  - 计划任务名：`OpenClaw Gateway Watchdog` / `OpenClaw Gateway`
  - 作用：登录时检查一次，并且每 3 分钟巡检一次；若本地 `http://127.0.0.1:18789/` 不通，则先尝试 `openclaw gateway restart`，若检测到原生 `OpenClaw Gateway` 任务被设成“仅交流电供电时启动 / 切到电池就停止”，则继续直接调用 `C:\Users\GOG\.openclaw\gateway.cmd` 兜底拉起
  - 停机规则：当需要手动关闭掌机上的 OpenClaw 时，先禁用 `OpenClaw Gateway Watchdog` 与 `OpenClaw Gateway`，再停止当前 gateway 实例，避免稍后又被自动拉起
  - 日志位置：`%LOCALAPPDATA%\OpenClaw\watchdog\gateway-watchdog.log`
- Windows SSD 优化（掌机）：
  - 适用机器：掌机（Windows）
  - 系统 / OS：Windows
  - 脚本：`scripts/optimize-ssd-trim-zhangji-windows.ps1`
  - cmd 包装器：`scripts/optimize-ssd-trim-zhangji-windows.cmd`
  - 作用：对掌机这台 Windows 机器的 SSD 卷执行 `Analyze + ReTrim`
  - 注意：需要“以管理员身份运行”
- User systemd units:
  - 适用机器：公司（Linux）/ 其他 Linux 机器
  - 系统 / OS：Linux
  - `~/.config/systemd/user/openclaw-resume-watch.service`
  - `~/.config/systemd/user/openclaw-resume-watch.timer`

- 读取 / 更新总规则：`docs/多机器-读取与更新规则.md`
- 详细维护说明：`docs/掌机-Windows-OpenClaw-维护说明.md`
- 详细维护说明：`docs/公司-Linux-OpenClaw-维护说明.md`
- Control UI 品牌补丁（当前已用于把左上角 OpenClaw 品牌改成贾维斯风格）：
  - 适用机器：公司（Linux）（脚本本身可复用，但当前部署记录在公司 Linux 机）
  - 系统 / OS：Linux
  - 配置文件：`config/control-ui-branding.json`
  - 应用脚本：`scripts/apply-openclaw-control-ui-branding.py`
  - systemd 自动重应用：`~/.config/systemd/user/openclaw-gateway.service.d/branding.conf`
  - 作用：重复应用 Control UI 左上角品牌名、Logo、浏览器标题、favicon / apple-touch-icon / manifest 名称覆盖，并额外把页面里可见的 `OpenClaw` 文案尽量替换成“贾维斯”，避免 OpenClaw 升级后手工逐个改静态文件
  - 默认品牌图来源：`avatars/jarvis-neon-20260507.png`
  - 自动生效规则：公司 Linux 机上每次 `openclaw-gateway.service` 启动前，都会先自动执行一次品牌补丁脚本；因此以后只要 OpenClaw 升级后重启 gateway，就会自动重新覆盖
  - 手工用法：`python3 scripts/apply-openclaw-control-ui-branding.py`
- NVIDIA 语音桥（公司 / Linux 机器）：
  - 适用机器：公司（Linux）
  - 系统 / OS：Linux
  - bridge 服务代码：`tools/nvidia-audio-bridge/bridge.py`
  - bridge README：`tools/nvidia-audio-bridge/README.md`
  - 依赖清单：`tools/nvidia-audio-bridge/requirements.txt`
  - systemd 模板：`tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service`
  - gateway 补丁脚本：`scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
  - 当前 bridge venv：`~/.local/share/openclaw-nvidia-audio-bridge-venv`
  - 当前用户态 service：`~/.config/systemd/user/openclaw-nvidia-audio-bridge.service`
  - 用途：让本机 OpenClaw gateway 通过本地 bridge 暴露 NVIDIA 免费 TTS / ASR 路径
  - 快速定位规则：新机器若要复用这一套，先看 README，再按公司 Linux 维护说明执行
- 临时文件下载分享（公司 / Linux 机器）：
  - 适用机器：公司（Linux）
  - 系统 / OS：Linux
  - 用途：当需要把当前机器上的文件交给宿主机浏览器或其他同网段设备下载时，优先在目标文件所在目录起临时 HTTP 服务，然后直接把完整 URL 发给用户
  - 默认推荐命令：`python3 -m http.server 8765 --bind 0.0.0.0`
  - 推荐做法：在包含目标文件的目录执行；随后把 `http://当前机器IP:8765/文件名` 发给用户
  - 当前公司 Linux 机器兜底 IP：`192.168.233.130`
  - 例如：`http://192.168.233.130:8765/rustdesk-1.4.6-x86_64.exe`
  - 使用场景：用户说“给我一个地址，我去宿主机浏览器里下”或明确表示附件 / 本地路径不好用时
  - **注意**：对 `mp3` / `mp4` / `pdf` 等浏览器可能直接内联打开的文件，如果用户明确想要“直接下载”而不是在线播放/预览，**不要只给 `python -m http.server` 的裸地址**；应优先提供带 `Content-Disposition: attachment` 的临时下载服务地址
  - 这次已验证的坑：浏览器访问普通 `http.server` 的 `mp3` 链接时，可能直接播放而不自动下载
  - 处理方式：为目标文件单独起一个带 `attachment` 响应头的临时 HTTP 服务，再把那个地址发给用户
  - 收尾：文件下载完成后，可结束对应的临时 HTTP 服务进程，避免长期暴露目录
- 浏览器上传到当前机器（公司 / Linux 机器）：
  - 适用机器：公司（Linux）（脚本本身可复用）
  - 系统 / OS：Linux
  - 用途：当用户需要把宿主机浏览器里的本地文件直接拷到当前机器时，优先起一个一次性临时上传页，让用户在浏览器里直接选文件上传
  - 固定脚本：`scripts/openclaw-upload-drop-server.py`
  - 推荐起法：`python3 scripts/openclaw-upload-drop-server.py tmp/upload-drop/inbox <token> 8771`
  - 推荐地址格式：`http://当前机器IP:8771/<token>`
  - 适用场景：用户说“我把文件拷给你”“我从宿主机传给你”“浏览器给你上传文件”这类需求
  - 当前验证通过的典型文件：`voices-v1.0.bin`、`kokoro-v1.0.int8.onnx`
  - 默认规则：以后当用户需要把文件从宿主机/浏览器拷到这台机器时，优先直接用这种临时上传页，而不是先折腾聊天附件、下载地址反向中转或别的更绕的方法
  - 安全做法：使用随机 token 路径、单独 inbox 目录；文件收完后及时关闭上传服务，避免长期暴露

### Git / GitHub

- 适用机器：通用（其中带“掌机”字样的条目仅适用于掌机（Windows））
- 系统 / OS：通用 / Windows（按各条目说明执行）

- 公司 / Linux 机器：
  - This machine has a GitHub-specific SSH key at `~/.ssh/id_ed25519_github_openclaw`.
  - If plain `git push origin master` hits `Permission denied (publickey)`, use:
    - `GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_openclaw -o IdentitiesOnly=yes' git push origin master`
  - Cause: the default SSH identity selection may miss the GitHub key unless it is specified explicitly or wired through `~/.ssh/config`.

- 掌机（Windows）：
  - Current SSH key path: `~/.ssh/id_ed25519_rog_ally`
  - `~/.ssh/config` now routes `github.com` through `ssh.github.com:443`
  - Reason: this machine can authenticate to GitHub over SSH, but direct port 22 to `github.com` may abort; port 443 to `ssh.github.com` works reliably here
  - Expected result after this change: plain `git push origin master` should work without extra per-command overrides

### CLI-Anything

- Local repository path: `/home/missyouangeled/Desktop/CLI-Anything`
- OpenClaw skill installed at: `~/.openclaw/skills/cli-anything/SKILL.md`
- Local helper command installed at: `~/.local/bin/cli-anything`
  - `cli-anything repo` → print repo path
  - `cli-anything skill` → print installed OpenClaw skill path
  - `cli-anything openclaw` → print suggested OpenClaw usage
- Important: CLI-Anything itself is not a single preinstalled global official executable on this machine. It is mainly a repo containing an OpenClaw skill, Claude Code plugin, OpenCode commands, and generated per-software harnesses.
- Minimal local verification succeeded with the built-in GIMP harness via:
  - `PYTHONPATH=/home/missyouangeled/Desktop/CLI-Anything/gimp/agent-harness python3 -m cli_anything.gimp.gimp_cli --help`
  - `PYTHONPATH=/home/missyouangeled/Desktop/CLI-Anything/gimp/agent-harness python3 -m cli_anything.gimp.gimp_cli project profiles`
- Note: the sample GIMP harness README still references an older module path (`python3 -m cli.gimp_cli`), but the runnable module on this machine is `python3 -m cli_anything.gimp.gimp_cli`.

### Voice replies / TTS

- Local voice-reply helpers live in: `tools/voice-reply/`
- **Simple local fallback** uses `msedge-tts` in user space (no root required)
  - Script: `tools/voice-reply/tts.mjs`
  - Default Chinese voice: `zh-CN-XiaoxiaoNeural`
  - **Current default voice-reply version**: `中文混合模板版本`
    - definition: 以更自然的中文音色为底，再吸收用户最终确认的更真实语气与语速；当前采用的成品模板为“第一条合体版提速 20%”
    - user-selected reference sample: `tmp/voice-replies/zh-hybrid-default-template.mp3`
    - usage rule: for future Chinese voice replies, use this as the default template across voice-reply surfaces unless the user explicitly asks for another voice/template
    - target feel: “第一条的声音 + 第二条的语气和语速”，最终确认版为 `zh-hybrid-noiz-natural-plus20-20260508-1225.mp3`
  - Named fallback preset: **基础女声版本**
    - definition: local `msedge-tts` baseline using `zh-CN-XiaoxiaoNeural`
    - purpose: safety fallback when later experiments sound worse, stiffer, or less natural
    - restore rule: if the user says “恢复到基础女声版本”, revert to this preset directly
    - reference sample chosen by user: `tmp/voice-replies/natural-baseline-xiaoxiao-20260422-164306.mp3`
  - Prefer mp3 for current OpenClaw / Control UI usage
  - Example:
    - `node tools/voice-reply/tts.mjs --text '你好，我是贾维斯。' --out /tmp/jarvis-voice.mp3`
- **Noiz-based helper** for stronger timbre continuity:
  - Script: `tools/voice-reply/noiz-reply.sh`
  - Private default reference clip path: `~/.local/share/openclaw-voice-reply/default-ref.mp3`
  - Presets: `natural`, `gentle`, `bright`, `late-night`
  - Current preferred Chinese template chain:
    - timbre-direction sample: `tmp/voice-replies/zh-msedge-closer-to-nvidia-20260508-1222.mp3`
    - user-final chosen template result: `tmp/voice-replies/zh-hybrid-noiz-natural-plus20-20260508-1225.mp3`
    - stable alias for future reuse: `tmp/voice-replies/zh-hybrid-default-template.mp3`
  - Supports pitch correction after synthesis with formant preservation:
    - `--pitch-semitones -1.5` → lower register slightly while keeping the speaking feel mostly intact
    - implemented with ffmpeg `rubberband` filter and `formant=preserved`
  - Example:
    - `bash tools/voice-reply/noiz-reply.sh --style natural --pitch-semitones -1.5 --text '你好，我在。' --out /tmp/noiz-reply.mp3`
- **Local free XTTS helper** for on-device voice cloning:
  - Script: `tools/voice-reply/local-xtts-reply.sh`
  - Uses local env: `~/.local/share/openclaw-voice-venv311`
  - Default private reference clip path: `~/.local/share/openclaw-voice-reply/default-ref.mp3`
  - Default output path: `tmp/voice-replies/local-xtts-YYYYmmdd-HHMMSS.mp3`
  - Example:
    - `bash tools/voice-reply/local-xtts-reply.sh --text '你好，我在。' --out /tmp/local-xtts.mp3`
- If a helper is used manually, send with:
  - `[[audio_as_voice]]`
  - `MEDIA:/path/to/file.mp3`

### Local audio trimming / reference-voice prep

- User-space ffmpeg helper installed at:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg`
- Reason: this machine has no system `ffmpeg` / `ffprobe`, but Noiz voice cloning rejects reference audio longer than 30s, so local trimming may be needed before upload.
- Example trim command:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg -y -ss 40 -t 10 -i '/path/input.mp3' -vn -acodec libmp3lame -b:a 96k '/path/output.mp3'`

### Kokoro TTS 离线中文语音（2026-05-08 已验证通过）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 模型文件位置：`tmp/kokoro-offline/`
  - `kokoro-v1.0.int8.onnx`（92MB，官方 int8 量化）
  - `voices-v1.0.bin`（28MB，54 个声音全部含中文）
- Python 运行环境：`/tmp/kokoro-test-venv`（Python 3.11，已安装 `kokoro-onnx`, `misaki`, `scipy`, `soundfile`）
- **完全离线**，无网络依赖、无播放设备依赖（纯推理→wav）
- 可用中文声音：`zf_xiaobei` `zf_xiaoni` `zf_xiaoxiao` `zf_xiaoyi`（女声）、`zm_yunjian` `zm_yunxi` `zm_yunxia` `zm_yunyang`（男声）
- 用法（直接 Python）：
  ```python
  from kokoro_onnx import Kokoro
  kokoro = Kokoro(
      model_path='tmp/kokoro-offline/kokoro-v1.0.int8.onnx',
      voices_path='tmp/kokoro-offline/voices-v1.0.bin'
  )
  audio, sr = kokoro.create('你好', voice='zf_xiaoxiao', speed=1.0, lang='cmn')
  ```
- 包装脚本：`tools/kokoro-tts/kokoro-tts.sh`
  - `bash tools/kokoro-tts/kokoro-tts.sh --text '你好' --voice zf_xiaoxiao --out /tmp/out.mp3`
- 试听样本：`tmp/voice-replies/kokoro-zh-official-int8-demo.mp3`
- **默认使用路由**：由主会话决定是否替换当前 Noiz/Edge TTS 管线

### ChatTTS hybrid 中文语音（2026-05-09 起已有正式 stable 入口）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 当前定位：**用户已明确认可这条 ChatTTS hybrid stable 主线，可作为正式的 ChatTTS 本地入口使用；`Noiz` 继续保留为保底版本。**
- 运行环境：`~/.local/share/openclaw-voice-venv311/bin/python3`
- 正式入口（Skill 脚本）：`skills/chattts-stable/scripts/chattts_stable.py`
- 本地便捷包装器：`tools/voice-reply/chattts-stable.sh`
- preset 配置：`skills/chattts-stable/assets/presets.json`
- preset embedding 文件：`skills/chattts-stable/assets/presets/*.spk.txt`
- 当前默认规则：
  - `default` = 当前主线默认音色（model-default）
  - `preset-1` / `preset-2` / `preset-3` = 已保存的可切换候选音色
  - **默认语速 / 节奏**：`tempo=1.15`（因为这版是用户确认通过的基线）
- 推荐运行方式：
  - `python3 skills/chattts-stable/scripts/chattts_stable.py --list-presets`
  - `python3 skills/chattts-stable/scripts/chattts_stable.py --preset default --text '你好，我在。' --out tmp/voice-replies/chattts-stable-default.mp3`
  - `bash tools/voice-reply/chattts-stable.sh --preset preset-2 --text '我给你换一条音色。' --out tmp/voice-replies/chattts-stable-preset2.mp3`
- 历史原型脚本（保留作研发记录，不再作为正式入口）：
  - `tmp/voice-replies/chattts-run-hybrid.py`
  - `tmp/voice-replies/chattts-run-hybrid-stable.py`
  - `tmp/voice-replies/chattts-hybrid-sample-speakers.py`
- hybrid 资产目录：`tmp/voice-replies/chattts-hybrid/asset/`
  - `DVAE_full.pt` / `Vocos.pt` / `Decoder.pt`：来自 `chattts-v011/`
  - `Embed.safetensors` + tokenizer：来自 v3 资产
  - GPT：由 v011 `GPT.pt` 转成 HuggingFace `config.json + model.safetensors`
- 当前关键补丁点（已内置在正式入口里）：
  - 绕过官方 sha256 校验（自组装资产不会匹配原始哈希）
  - `DVAE/DVAEDecoder load_state_dict(..., strict=False)`，容忍缺失 encoder 键
  - tokenizer 从已失效的 `encode_plus()` 改走 `__call__()`，兼容当前 transformers
- 已知限制：
  - **无 encoder**：只能稳定走 decoder 推理路径，不适合参考音频克隆
  - **纯 CPU**：短句可用，但不适合追求实时流式
  - **版本脆弱**：对依赖版本和素材结构敏感，后续升级时要防回归
- 判断规则：
  - 若用户明确要走 `ChatTTS stable` / 本地 ChatTTS / preset 音色切换，优先使用这条正式入口
  - 若要“任意参考音频克隆”或更强 timbre continuity，仍优先评估 `Noiz` / 其他方案，不要误把当前 stable 路线当成通用克隆器

### Local free voice-cloning stack

- `uv` installed in user space at:
  - `~/.local/bin/uv`
- Reason: system Python lacks `pip` / `ensurepip`, so normal `venv` bootstrap is broken on this machine.
- Working local Coqui/XTTS environment path:
  - `~/.local/share/openclaw-voice-venv311`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/openclaw-voice-venv311`
- XTTS model cache path:
  - `~/.local/share/tts`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/tts`
- uv cache path:
  - `~/.cache/uv`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/uv-cache`
- Important compatibility notes:
  - Coqui TTS `0.22.0` does **not** support Python 3.12 on this machine; use Python 3.11 via `uv`.
  - XTTS with current PyTorch/TTS stack needed local compatibility fixes on this machine:
    - pin `transformers==4.41.2` (newer 5.x / late 4.x removed `BeamSearchScorer` expected by XTTS)
    - patch `TTS/utils/io.py` to default `torch.load(..., weights_only=False)` for trusted XTTS checkpoints under PyTorch >=2.6
    - patch `TTS/tts/models/xtts.py` `load_audio()` to use `librosa.load()` instead of `torchaudio.load()` to avoid missing system FFmpeg shared-library issues
- First XTTS model download requires explicit Coqui CPML confirmation:
  - tool recognizes `COQUI_TOS_AGREED=1`
  - do **not** set it unless the user has explicitly agreed to the non-commercial CPML / relevant license terms.
- Current local XTTS smoke test output path:
  - `/home/missyouangeled/.openclaw/workspace/tmp/voice-replies/local-xtts-test.mp3`

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
