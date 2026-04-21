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

- Local voice-reply helper lives in: `tools/voice-reply/`
- Current implementation uses `msedge-tts` in user space (no root required)
- Default Chinese voice in helper: `zh-CN-XiaoxiaoNeural`
- Test command:
  - `node tools/voice-reply/tts.mjs --text '你好，我是贾维斯。' --out /tmp/jarvis-voice.webm`
- Output format is `webm/opus`, suitable for OpenClaw audio attachment replies
- If the helper is used manually, send with:
  - `[[audio_as_voice]]`
  - `MEDIA:/path/to/file.webm`
- Added Noiz-based reply helper for better timbre continuity:
  - Script: `tools/voice-reply/noiz-reply.sh`
  - Private default reference clip path: `~/.local/share/openclaw-voice-reply/default-ref.mp3`
  - Presets: `natural`, `gentle`, `bright`, `late-night`
  - Example:
    - `bash tools/voice-reply/noiz-reply.sh --style natural --text '你好，我在。' --out /tmp/noiz-reply.mp3`

### Local audio trimming / reference-voice prep

- User-space ffmpeg helper installed at:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg`
- Reason: this machine has no system `ffmpeg` / `ffprobe`, but Noiz voice cloning rejects reference audio longer than 30s, so local trimming may be needed before upload.
- Example trim command:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg -y -ss 40 -t 10 -i '/path/input.mp3' -vn -acodec libmp3lame -b:a 96k '/path/output.mp3'`

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
