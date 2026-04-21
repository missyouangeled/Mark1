#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/missyouangeled/.openclaw/workspace"
VENV_DIR="$HOME/.local/share/openclaw-voice-venv311"
PYTHON_BIN="$VENV_DIR/bin/python"
REF_AUDIO_DEFAULT="$HOME/.local/share/openclaw-voice-reply/default-ref.mp3"
FFMPEG_BIN="$HOME/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg"
MODEL_NAME="tts_models/multilingual/multi-dataset/xtts_v2"
OUT=""
TEXT=""
REF_AUDIO="$REF_AUDIO_DEFAULT"
LANG="zh-cn"
PITCH_SEMITONES="0"
KEEP_WAV="0"

usage() {
  cat <<'EOF'
Usage:
  bash tools/voice-reply/local-xtts-reply.sh --text "你好" [--out /path/out.mp3] [--ref-audio /path/ref.mp3] [--lang zh-cn] [--pitch-semitones -1.0] [--keep-wav]

Notes:
  - Uses the local Coqui XTTS environment already prepared on this machine.
  - Default reference audio: ~/.local/share/openclaw-voice-reply/default-ref.mp3
  - Default output path: workspace tmp/voice-replies/local-xtts-YYYYmmdd-HHMMSS.mp3
  - If the output suffix is .wav, the raw XTTS wav is kept directly.
  - Optional pitch adjustment is done after synthesis with ffmpeg rubberband.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --text|-t)
      TEXT="$2"
      shift 2
      ;;
    --out|-o)
      OUT="$2"
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
    --pitch-semitones)
      PITCH_SEMITONES="$2"
      shift 2
      ;;
    --keep-wav)
      KEEP_WAV="1"
      shift
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

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: local XTTS python not found: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$REF_AUDIO" ]]; then
  echo "Error: reference audio not found: $REF_AUDIO" >&2
  exit 1
fi

if [[ -z "$OUT" ]]; then
  mkdir -p "$BASE_DIR/tmp/voice-replies"
  OUT="$BASE_DIR/tmp/voice-replies/local-xtts-$(date +%Y%m%d-%H%M%S).mp3"
fi

mkdir -p "$(dirname "$OUT")"
OUT_EXT="${OUT##*.}"
OUT_EXT_LOWER="$(printf '%s' "$OUT_EXT" | tr '[:upper:]' '[:lower:]')"
RAW_WAV="${OUT%.*}.raw.wav"
if [[ "$OUT" == "$RAW_WAV" ]]; then
  RAW_WAV="${OUT}.raw.wav"
fi

TEXT="$TEXT" REF_AUDIO="$REF_AUDIO" LANG="$LANG" RAW_WAV="$RAW_WAV" MODEL_NAME="$MODEL_NAME" \
  "$PYTHON_BIN" - <<'PY'
import os
from TTS.api import TTS

text = os.environ["TEXT"]
ref_audio = os.environ["REF_AUDIO"]
language = os.environ.get("LANG", "zh-cn")
out_wav = os.environ["RAW_WAV"]
model_name = os.environ.get("MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")

tts = TTS(model_name)
tts.tts_to_file(text=text, speaker_wav=ref_audio, language=language, file_path=out_wav)
print(out_wav)
PY

if [[ "$OUT_EXT_LOWER" == "wav" ]]; then
  mv -f "$RAW_WAV" "$OUT"
else
  if [[ ! -x "$FFMPEG_BIN" ]]; then
    echo "Error: ffmpeg helper not found: $FFMPEG_BIN" >&2
    exit 1
  fi
  "$FFMPEG_BIN" -y -i "$RAW_WAV" -codec:a libmp3lame -b:a 96k "$OUT" >/dev/null 2>&1
  if [[ "$KEEP_WAV" != "1" ]]; then
    rm -f "$RAW_WAV"
  fi
fi

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
  TMP_OUT="${OUT%.*}.pitchtmp.${OUT##*.}"
  "$FFMPEG_BIN" -y -i "$OUT" -af "rubberband=pitch=${PITCH_FACTOR}:formant=preserved:pitchq=quality:transients=smooth" "$TMP_OUT" >/dev/null 2>&1
  mv -f "$TMP_OUT" "$OUT"
fi

printf '%s\n' "$OUT"
