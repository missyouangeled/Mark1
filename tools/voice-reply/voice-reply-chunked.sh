#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$BASE_DIR/tools/voice-reply/chunked_voice_reply.py"
VENV_PYTHON="$HOME/.local/share/openclaw-voice-venv311/bin/python3"

TEXT="${1:-}"
PRESET="${2:-${OPENCLAW_VOICE_REPLY_PRESET:-default}}"
shift_count=0
[[ $# -ge 1 ]] && shift_count=$((shift_count + 1))
[[ $# -ge 2 ]] && shift_count=$((shift_count + 1))
if (( shift_count > 0 )); then
  shift "$shift_count"
fi

if [[ -z "$TEXT" ]]; then
  echo "" >&2
  exit 1
fi

exec "$VENV_PYTHON" "$SCRIPT" --text "$TEXT" --preset "$PRESET" "$@"
