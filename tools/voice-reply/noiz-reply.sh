#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/missyouangeled/.openclaw/workspace"
REF_AUDIO_DEFAULT="$HOME/.local/share/openclaw-voice-reply/default-ref.mp3"
FFMPEG_BIN="$HOME/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg"
STYLE="${VOICE_STYLE:-natural}"
PITCH_SEMITONES="${VOICE_PITCH_SEMITONES:-0}"
OUT=""
TEXT=""
REF_AUDIO="$REF_AUDIO_DEFAULT"
LANG="zh"

usage() {
  cat <<'EOF'
Usage:
  bash tools/voice-reply/noiz-reply.sh --text "你好" [--style natural|gentle|bright|late-night] [--pitch-semitones -1.5] [--out /path/out.mp3] [--ref-audio /path/ref.mp3]

Notes:
  - Uses Noiz with a fixed short reference clip to keep the timbre close to the chosen sample.
  - Prosody is shaped mainly by style preset + punctuation in the input text.
  - Pitch is adjusted post-synthesis with ffmpeg rubberband using formant preservation.
  - Current default ref audio path: ~/.local/share/openclaw-voice-reply/default-ref.mp3
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --text|-t)
      TEXT="$2"
      shift 2
      ;;
    --style)
      STYLE="$2"
      shift 2
      ;;
    --out|-o)
      OUT="$2"
      shift 2
      ;;
    --pitch-semitones)
      PITCH_SEMITONES="$2"
      shift 2
      ;;
    --ref-audio)
      REF_AUDIO="$2"
      shift 2
      ;;
    --lang)
      LANG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$TEXT" ]]; then
  echo "Error: --text is required" >&2
  exit 1
fi

if [[ ! -f "$REF_AUDIO" ]]; then
  echo "Error: reference audio not found: $REF_AUDIO" >&2
  exit 1
fi

case "$STYLE" in
  natural)
    SPEED="0.97"
    EMO='{"Tenderness":0.14,"Joy":0.04}'
    ;;
  gentle)
    SPEED="0.93"
    EMO='{"Tenderness":0.32,"Joy":0.08}'
    ;;
  bright)
    SPEED="1.02"
    EMO='{"Joy":0.22,"Tenderness":0.05}'
    ;;
  late-night)
    SPEED="0.90"
    EMO='{"Tenderness":0.42,"Sadness":0.04}'
    ;;
  *)
    echo "Error: unknown style '$STYLE'" >&2
    exit 1
    ;;
esac

if [[ -z "$OUT" ]]; then
  mkdir -p "$BASE_DIR/tmp/voice-replies"
  OUT="$BASE_DIR/tmp/voice-replies/noiz-${STYLE}-$(date +%Y%m%d-%H%M%S).mp3"
fi

python3 "$BASE_DIR/skills/noizai-tts/scripts/tts.py" \
  --text "$TEXT" \
  --ref-audio "$REF_AUDIO" \
  --backend noiz \
  --format mp3 \
  --lang "$LANG" \
  --speed "$SPEED" \
  --emo "$EMO" \
  --output "$OUT"

if [[ "$PITCH_SEMITONES" != "0" && "$PITCH_SEMITONES" != "0.0" ]]; then
  if [[ ! -x "$FFMPEG_BIN" ]]; then
    echo "Error: ffmpeg helper not found: $FFMPEG_BIN" >&2
    exit 1
  fi
  PITCH_FACTOR="$(python3 - "$PITCH_SEMITONES" <<'PY'
import math, sys
semi=float(sys.argv[1])
print(f"{2 ** (semi / 12.0):.6f}")
PY
)"
  TMP_OUT="${OUT%.mp3}.pitchtmp.mp3"
  "$FFMPEG_BIN" -y -i "$OUT" -af "rubberband=pitch=${PITCH_FACTOR}:formant=preserved:pitchq=quality:transients=smooth" "$TMP_OUT" >/dev/null 2>&1
  mv -f "$TMP_OUT" "$OUT"
fi

printf '%s\n' "$OUT"
