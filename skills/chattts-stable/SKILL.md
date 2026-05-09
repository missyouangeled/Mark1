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
- Treat `default` as the current mainline voice. It uses the model-default speaker on top of the fixed hybrid asset chain.
- Treat `preset-1` / `preset-2` / `preset-3` as saved `spk_emb` presets stored under `assets/presets/`.
- Default tempo is already set to `1.15`, because that is the currently accepted baseline. Override with `--tempo` only when the user asks.
- Keep the asset chain fixed unless the task is explicitly about rebuilding ChatTTS assets.
- If the user asks for more voices later, add new preset files plus `assets/presets.json`; do not replace the current approved presets casually.

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

Keep validation lightweight because CPU inference is slow on this machine.
