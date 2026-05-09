#!/usr/bin/env bash
# =============================================================================
# cleanup-old-audio.sh — prune expired ChatTTS reply audio artifacts
#
# Default policy:
#   delete generated reply audio older than 4 hours
#
# Scope (safe-by-default):
#   - tmp/voice-replies/chattts-ondemand-*
#   - tmp/voice-replies/voice-reply-*
#
# Notes:
#   - Only touches generated reply files for the on-demand / direct-reply path
#   - Does not touch other voice assets, presets, or long-term samples
# =============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RETENTION_HOURS="${OPENCLAW_VOICE_REPLY_RETENTION_HOURS:-4}"
RETENTION_MINUTES=$(( RETENTION_HOURS * 60 ))
QUIET=false
DRY_RUN=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quiet) QUIET=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --verbose) VERBOSE=true; shift ;;
    --help|-h)
      cat <<'EOF'
Usage: cleanup-old-audio.sh [--quiet] [--dry-run] [--verbose]

Deletes generated ChatTTS reply audio older than OPENCLAW_VOICE_REPLY_RETENTION_HOURS
(default: 4 hours).
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

TARGET_DIR="$BASE_DIR/tmp/voice-replies"
if [[ ! -d "$TARGET_DIR" ]]; then
  $QUIET || echo "No voice reply directory yet: $TARGET_DIR"
  exit 0
fi

mapfile -d '' FILES < <(
  find "$TARGET_DIR" -maxdepth 1 -type f \
    \( -name 'chattts-ondemand-*' -o -name 'voice-reply-*' \) \
    -mmin "+$RETENTION_MINUTES" -print0
)

COUNT=0
for file in "${FILES[@]}"; do
  [[ -n "$file" ]] || continue
  COUNT=$((COUNT + 1))
  if $DRY_RUN; then
    echo "[dry-run] $file"
    continue
  fi
  rm -f -- "$file"
  if $VERBOSE; then
    echo "Deleted: $file"
  fi
done

if ! $QUIET; then
  if $DRY_RUN; then
    echo "Would delete $COUNT expired audio file(s) older than ${RETENTION_HOURS}h."
  else
    echo "Deleted $COUNT expired audio file(s) older than ${RETENTION_HOURS}h."
  fi
fi
