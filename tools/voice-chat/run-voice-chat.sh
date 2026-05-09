#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$HOME/.local/share/openclaw-nvidia-audio-bridge-venv/bin/python"
APP="$BASE_DIR/voice_chat_app.py"

if [[ ! -x "$PY" ]]; then
  echo "缺少 Python 解释器：$PY" >&2
  echo "请先确认 NVIDIA audio bridge 的 venv 已按 tools/nvidia-audio-bridge/README.md 建好。" >&2
  exit 1
fi

exec "$PY" "$APP"
