#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/openclaw"
STATE_FILE="$STATE_DIR/resume-watch.env"
LOG_FILE="$STATE_DIR/resume-watch.log"
THRESHOLD_SECONDS=180

mkdir -p "$STATE_DIR"

now="$(date +%s)"
boot_id="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown)"
last_ts=""
last_boot=""

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

printf 'last_ts=%s\nlast_boot=%q\n' "$now" "$boot_id" > "$STATE_FILE.tmp"
mv "$STATE_FILE.tmp" "$STATE_FILE"

if [[ -z "${last_ts:-}" ]]; then
  exit 0
fi

if [[ "${last_boot:-}" != "$boot_id" ]]; then
  exit 0
fi

gap=$(( now - last_ts ))
if (( gap < THRESHOLD_SECONDS )); then
  exit 0
fi

{
  echo "[$(date --iso-8601=seconds)] Detected sleep/resume or long pause (gap=${gap}s); restarting openclaw-gateway.service"
  systemctl --user restart openclaw-gateway.service
  if systemctl --user --quiet is-active openclaw-gateway.service; then
    echo "[$(date --iso-8601=seconds)] openclaw-gateway.service is active after restart"
  else
    echo "[$(date --iso-8601=seconds)] openclaw-gateway.service restart requested, but service is not active yet"
  fi
} >> "$LOG_FILE" 2>&1 || true
