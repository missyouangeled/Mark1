---
name: chattts-stable
description: Use when generating Chinese voice replies with the verified local ChatTTS hybrid stable path, especially when the task needs the 2026-05-09 accepted baseline voice, preset voice switching, or local/offline-ish ChatTTS output without routing through Noiz. Triggers include requests to render ChatTTS stable samples, switch among approved preset voices, list or test preset voices, or produce new audio with this exact hybrid asset chain.
---

# chattts-stable

Use the formal ChatTTS stable entry instead of ad-hoc prototype scripts whenever the request is specifically about this proven hybrid path.

## Quick start

List presets:

```bash
python3 skills/chattts-stable/scripts/chattts_stable.py --list-presets
```

Render with the accepted default voice:

```bash
python3 skills/chattts-stable/scripts/chattts_stable.py \
  --preset default \
  --text '嗯，我在。' \
  --out tmp/voice-replies/chattts-stable-default.mp3
```

Render with another preset:

```bash
python3 skills/chattts-stable/scripts/chattts_stable.py \
  --preset preset-2 \
  --text '我给你换一条音色。' \
  --out tmp/voice-replies/chattts-stable-preset2.mp3
```

Local wrapper:

```bash
tools/voice-reply/chattts-stable.sh --preset preset-1 --text '测试一下' --out tmp/voice-replies/test.mp3
```

## Rules

- Prefer this skill when the user explicitly wants **ChatTTS stable** rather than Noiz / Kokoro / other TTS paths.
- Treat `default` as the current mainline voice. It is the fixed `seed_1910` speaker embedding confirmed on 2026-05-09 and stored under `assets/presets/default-main-20260509.spk.txt`.
- Treat `model-default` as the old drifting baseline kept only for manual comparison/debugging, not as the normal main-session voice.
- Treat `preset-1` / `preset-2` / `preset-3` as saved `spk_emb` presets stored under `assets/presets/`.
- Default tempo is now set to `1.10`, because the 2026-05-12 A/B test showed this gives the best overall feel on the accepted default voice. Override with `--tempo` only when the user asks.
- Keep the asset chain fixed unless the task is explicitly about rebuilding ChatTTS assets.
- If the user asks for more voices later, add new preset files plus `assets/presets.json`; do not replace the current approved presets casually.

## On-demand daemon (alternative startup)

An on-demand daemon is available at `tools/chattts-on-demand/` that keeps the model warm between calls and auto-exits after 5 minutes of idle. Use for multiple sequential TTS requests without the ~12s cold-start overhead each time.

```bash
# First call (cold start, ~12s)
bash tools/chattts-on-demand/chattts-on-demand.sh --text '你好' --out /tmp/out.wav

# Subsequent calls (hot, ~4-10s depending on text length)
bash tools/chattts-on-demand/chattts-on-demand.sh --text '第二次' --out /tmp/out2.wav
```

### Features (verified stable 2026-05-09)

| Feature | Status |
|---------|--------|
| Idle auto-exit after 300s | ✅ Verfied — clean exit, no zombie processes |
| Cold restart after idle exit | ✅ Verified — auto-starts on next request |
| Stale socket recovery | ✅ Verified — detects dead daemon, cleans artifacts, restarts |
| Multiple cold/hot cycles | ✅ Verified — no zombie accumulation |
| Preset switching while hot | ✅ Verified — 4 presets tested, spk_emb switching works |
| Crash recovery (`--cold` fallback) | ✅ Verified — works independently of daemon state |
| Concurrent request queuing | ✅ Verified — serial processing, 3 rapid requests queued |

### Improved stale-socket handling (2026-05-09)

The `chattts-daemon.sh request` handler now includes a stale socket detection step:
before connecting to the daemon socket, it performs a quick TCP-style probe
(connect with 5s timeout). If the socket is stale (e.g., daemon crashed and
left the socket file behind), it:
1. Removes the stale socket + lock files
2. Calls `$0 start` to spawn a fresh daemon
3. Retries the request

This eliminates the edge case where a `kill -9` on the daemon left the socket
file intact but the process dead, causing subsequent requests to silently fail.

See `tools/chattts-on-demand/README.md` for details, architecture, and risks. The daemon is separate from OpenClaw and does not affect gateway stability.

## Important files

- Main entry: `skills/chattts-stable/scripts/chattts_stable.py`
- Preset config: `skills/chattts-stable/assets/presets.json`
- Preset embeddings: `skills/chattts-stable/assets/presets/*.spk.txt`
- Convenience wrapper: `tools/voice-reply/chattts-stable.sh`
- Underlying hybrid assets: `tmp/voice-replies/chattts-hybrid/`

## Validation

Before claiming success, run at least:

1. `--list-presets`
2. one short render with `default`
3. one short render with a non-default preset

Current accepted main-session quality direction (2026-05-12):
- keep the accepted `default` voice
- prefer `tempo 1.10` for overall feel
- when clarity matters, prefer `wav` (or the least-lossy export path available) over mp3

Keep validation lightweight because CPU inference is slow on this machine.
