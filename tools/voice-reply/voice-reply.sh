#!/usr/bin/env bash
# =============================================================================
# voice-reply.sh — Main-session voice reply entry point
#
# Called from the main agent when generating a voice reply for the chat.
# Architecture: agent → voice-reply.sh → chattts_voice_reply.py → chattts-on-demand.sh
#
# Usage:
#   bash tools/voice-reply/voice-reply.sh "回复文本内容"
#   bash tools/voice-reply/voice-reply.sh "文本" default
#   bash tools/voice-reply/voice-reply.sh "文本" preset-1
#
# Returns:
#   Path to generated audio file, or empty string on failure.
#   The main agent should fall back to text-only if the output is empty.
#
# Zero OpenClaw gateway impact.
# =============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$BASE_DIR/tools/voice-reply/chattts_voice_reply.py"
VENV_PYTHON="$HOME/.local/share/openclaw-voice-venv311/bin/python3"

TEXT="${1:-}"
PRESET="${2:-default}"

if [[ -z "$TEXT" ]]; then
  echo "" >&2
  exit 0
fi

# Call the Python wrapper; on failure, output nothing (empty) which signals
# the caller to fall back to text-only.
OUTPUT=$("$VENV_PYTHON" "$WRAPPER" --text "$TEXT" --preset "$PRESET" 2>/dev/null) || true

if [[ -n "$OUTPUT" && -f "$OUTPUT" ]]; then
  echo "$OUTPUT"
else
  echo ""
fi
