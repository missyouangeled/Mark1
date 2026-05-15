#!/usr/bin/env bash
# =============================================================================
# voice-reply-gpu-first.sh — GPU-first voice reply entry point
#
# Same interface as voice-reply.sh, but tries remote GPU (SeetaCloud) first,
# and falls back to local CPU stable if GPU fails.
#
# Usage:
#   bash tools/voice-reply/voice-reply-gpu-first.sh "回复文本内容"
#   bash tools/voice-reply/voice-reply-gpu-first.sh "文本" preset-1
#
# Architecture:
#   This wrapper → voice-reply.sh → chattts_voice_reply.py (unchanged)
#   But with OPENCLAW_VOICE_REPLY_BACKEND=gpu-first, which makes
#   chunked_voice_reply.py import synthesize from chattts_gpu_first_wrapper.py
#   instead of chattts_voice_reply.py.
#
# Returns:
#   Path to generated audio file, or empty string on failure.
#   The main agent should fall back to text-only if the output is empty.
#
# Zero OpenClaw gateway impact.
# =============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

TEXT="${1:-}"
PRESET="${2:-${OPENCLAW_VOICE_REPLY_PRESET:-default}}"

if [[ -z "$TEXT" ]]; then
  echo "" >&2
  exit 0
fi

# GPU-first backend selection
export OPENCLAW_VOICE_REPLY_BACKEND=gpu-first

# Delegate to the existing voice-reply.sh which already handles everything
exec bash "$BASE_DIR/tools/voice-reply/voice-reply.sh" "$TEXT" "$PRESET"
