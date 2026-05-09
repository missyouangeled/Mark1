#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$HOME/.local/share/openclaw-voice-venv311/bin/python3"
SCRIPT="$BASE_DIR/skills/chattts-stable/scripts/chattts_stable.py"

exec "$PY" "$SCRIPT" "$@"
