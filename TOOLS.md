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

- Startup online notice is driven by `BOOT.md` + the `boot-md` hook.
- Resume recovery watcher script: `scripts/openclaw-resume-watch.sh`
- Windows 更新脚本（掌机）：
  - `scripts/update-openclaw.ps1`
  - `scripts/update-openclaw.cmd`
  - 用途：执行 `git pull --ff-only`，若仓库有新提交则自动 `openclaw gateway restart`
  - 掌机建议直接运行：`.\scripts\update-openclaw.cmd`
- User systemd units:
  - `~/.config/systemd/user/openclaw-resume-watch.service`
  - `~/.config/systemd/user/openclaw-resume-watch.timer`

### Git / GitHub

- This machine has a GitHub-specific SSH key at `~/.ssh/id_ed25519_github_openclaw`.
- If plain `git push origin master` hits `Permission denied (publickey)`, use:
  - `GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_openclaw -o IdentitiesOnly=yes' git push origin master`
- Cause: the default SSH identity selection may miss the GitHub key unless it is specified explicitly or wired through `~/.ssh/config`.

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
  - **Current default voice-reply version**: `基础聊天女声版本`
    - definition: local `msedge-tts` using `zh-CN-XiaoxiaoNeural`, optimized by using more conversational text rather than imitation/cloning
    - user-selected reference sample: `tmp/voice-replies/basic-female-confession-chatty-20260422-165649.mp3`
    - usage rule: for future normal voice replies, default to this version first
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
