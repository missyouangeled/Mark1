#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/openclaw"
STATE_FILE="$STATE_DIR/resume-watch.env"
LOG_FILE="$STATE_DIR/resume-watch.log"
AUDIT_LOG="$STATE_DIR/gateway-restart-audit.jsonl"
RESTART_LOG="$HOME/.openclaw/logs/gateway-restart.log"
THRESHOLD_SECONDS=600
GATEWAY_PORT=18789

# 检查 Gateway 是否有活跃连接（WebSocket/HTTP）
# 有则说明用户在线，不应重启
has_active_connections() {
  ss -tnp 2>/dev/null | grep -q ":${GATEWAY_PORT} .*ESTAB"
}

write_restart_audit() {
  local reason="$1"
  local detail="$2"
  local active="$3"
  python3 - <<'PY' "$AUDIT_LOG" "$reason" "$detail" "$active" "$boot_id" "$now" "$gap"
import json, sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "recordedAt": datetime.now(timezone.utc).isoformat(),
    "source": "openclaw-resume-watch.sh",
    "reason": sys.argv[2],
    "detail": sys.argv[3],
    "hasActiveConnections": sys.argv[4] == "1",
    "bootId": sys.argv[5],
    "nowEpoch": int(sys.argv[6]),
    "gapSeconds": int(sys.argv[7]),
}
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
PY
  mkdir -p "$(dirname "$RESTART_LOG")"
  printf '[%s] source=resume-watch reason=%s active=%s gap=%ss detail=%s\n' \
    "$(date --iso-8601=seconds)" "$reason" "$active" "$gap" "$detail" >> "$RESTART_LOG" 2>/dev/null || true
}

mkdir -p "$STATE_DIR"

now="$(date +%s)"
boot_id="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown)"
last_ts=""
last_boot=""

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

# 始终更新时间戳（相当于「用户活跃就复位开关」）
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

# gap > 阈值，但先检查用户是否在线
if has_active_connections; then
  write_restart_audit "skip-active-connections" "gap threshold exceeded but gateway still has active connections" "1"
  {
    echo "[$(date --iso-8601=seconds)] Gap=${gap}s > threshold but gateway has active connections; skipping restart (user online)"
  } >> "$LOG_FILE" 2>&1 || true
  exit 0
fi

write_restart_audit "restart-gap-threshold" "detected sleep/resume or long pause; restarting gateway" "0"
{
  echo "[$(date --iso-8601=seconds)] Detected sleep/resume or long pause (gap=${gap}s, no active connections); restarting openclaw-gateway.service"
  systemctl --user restart openclaw-gateway.service
  if systemctl --user --quiet is-active openclaw-gateway.service; then
    echo "[$(date --iso-8601=seconds)] openclaw-gateway.service is active after restart"
  else
    echo "[$(date --iso-8601=seconds)] openclaw-gateway.service restart requested, but service is not active yet"
  fi
} >> "$LOG_FILE" 2>&1 || true
