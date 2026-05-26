#!/usr/bin/env bash
# =============================================================================
# chattts-on-demand.sh — ChatTTS on-demand TTS CLI
#
# User-facing interface for the ChatTTS on-demand daemon.
# Starts the daemon on first use, reuses it for subsequent calls,
# and auto-exits after 5 minutes of idle.
#
# Usage:
#   ./chattts-on-demand.sh --text "你好，你在吗？"
#   ./chattts-on-demand.sh --text "你好" --out /tmp/output.mp3 --preset preset-1
#   ./chattts-on-demand.sh --text "测试" --format wav
#   ./chattts-on-demand.sh --list-presets          # Show available voices
#   ./chattts-on-demand.sh --stop                  # Stop daemon
#   ./chattts-on-demand.sh --status                # Check daemon status
#   ./chattts-on-demand.sh --cold                  # Force cold start (no daemon)
#
# For quick inline use when daemon not running:
#   Text output → speech, background async.
# =============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$BASE_DIR/skills/chattts-stable/scripts/chattts_stable.py"
VENV_PYTHON="$HOME/.local/share/openclaw-voice-venv311/bin/python3"
DAEMON_SH="$BASE_DIR/tools/chattts-on-demand/chattts-daemon.sh"
CLEANUP_SH="$BASE_DIR/tools/chattts-on-demand/cleanup-old-audio.sh"
PRESETS_FILE="$BASE_DIR/skills/chattts-stable/assets/presets.json"

# Parse args
TEXT=""
OUT=""
PRESET=""
FORMAT="auto"
TEMPO=""
MAX_NEW_TOKEN=""
COLD_MODE=false
LIST_PRESETS=false
STOP_DAEMON=false
STATUS_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --text) TEXT="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --preset|--voice) PRESET="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    --tempo) TEMPO="$2"; shift 2 ;;
    --max-new-token) MAX_NEW_TOKEN="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --cold) COLD_MODE=true; shift ;;
    --list-presets) LIST_PRESETS=true; shift ;;
    --stop) STOP_DAEMON=true; shift ;;
    --status) STATUS_ONLY=true; shift ;;
    --help|-h)
      echo "Usage: $0 [--text TEXT] [--out PATH] [--preset NAME] [--format wav|mp3]"
      echo "       $0 [--tempo N] [--max-new-token N] [--cold|--list-presets|--stop|--status]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Try --help"
      exit 1
      ;;
  esac
done

# Handle special modes
if $LIST_PRESETS; then
  cat "$PRESETS_FILE" | python3 -c "
import json, sys
config = json.load(sys.stdin)
print('Available presets:')
for name, p in config.get('presets', {}).items():
    label = p.get('label', '')
    aliases = ', '.join(p.get('aliases', []))
    alias_info = f' [aliases: {aliases}]' if aliases else ''
    print(f'  - {name}: {label}{alias_info}')
print(f'Default tempo: {config.get(\"defaultTempo\", 1.0)}')
"
  exit 0
fi

if $STOP_DAEMON; then
  exec "$DAEMON_SH" stop
fi

if $STATUS_ONLY; then
  exec "$DAEMON_SH" status
fi

if [[ -z "$TEXT" ]]; then
  echo "Error: --text is required"
  echo "Try --help"
  exit 1
fi

# Best-effort pruning of expired generated reply audio.
# The stricter guarantee is handled by the recurring cleanup cron job.
if [[ -x "$CLEANUP_SH" ]]; then
  "$CLEANUP_SH" --quiet >/dev/null 2>&1 || true
fi

# ── Cold mode: direct stable script (bypass daemon) ──────────────────
if $COLD_MODE; then
  args=("--text" "$TEXT")
  [[ -n "$OUT" ]] && args+=("--out" "$OUT")
  [[ -n "$PRESET" ]] && args+=("--preset" "$PRESET")
  args+=("--format" "$FORMAT")
  [[ -n "$TEMPO" ]] && args+=("--tempo" "$TEMPO")
  [[ -n "$MAX_NEW_TOKEN" ]] && args+=("--max-new-token" "$MAX_NEW_TOKEN")
  exec "$VENV_PYTHON" "$SCRIPT" "${args[@]}"
fi

# ── Normal mode: use daemon ─────────────────────────────────────────
# Generate output path if not specified
if [[ -z "$OUT" ]]; then
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  OUT="$BASE_DIR/tmp/voice-replies/chattts-ondemand-$TIMESTAMP.mp3"
  mkdir -p "$(dirname "$OUT")"
fi

# Determine format
if [[ "$FORMAT" == "auto" ]]; then
  case "$OUT" in
    *.wav) FORMAT="wav" ;;
    *) FORMAT="mp3" ;;
  esac
fi

# Build JSON payload via Python tempfile (no shell escaping issues)
PAYLOAD_FILE=$(mktemp /tmp/chattts-payload-json.XXXXXX)
CHATTTS_TEXT="$TEXT" CHATTTS_OUT="$OUT" CHATTTS_FORMAT="$FORMAT" \
  CHATTTS_PRESET="${PRESET:-}" CHATTTS_TEMPO="${TEMPO:-}" CHATTTS_MAX_NEW_TOKEN="${MAX_NEW_TOKEN:-}" CHATTTS_SEED="${SEED:-}" CHATTTS_PAYLOAD_FILE="$PAYLOAD_FILE" \
  "$VENV_PYTHON" -c "
import json, os
payload = {
    'text': os.environ['CHATTTS_TEXT'],
    'out': os.environ['CHATTTS_OUT'],
    'format': os.environ['CHATTTS_FORMAT'],
}
p = os.environ.get('CHATTTS_PRESET', '')
t = os.environ.get('CHATTTS_TEMPO', '')
s = os.environ.get('CHATTTS_SEED', '')
if p:
    payload['preset'] = p
if t:
    payload['tempo'] = float(t)
if s:
    payload['seed'] = int(s)
m = os.environ.get('CHATTTS_MAX_NEW_TOKEN', '')
if m:
    payload['max_new_token'] = int(m)
with open(os.environ['CHATTTS_PAYLOAD_FILE'], 'w') as f:
    f.write(json.dumps(payload, ensure_ascii=False))
"

# Send request via daemon (auto-starts if not running)
# Pipe payload from file to daemon's stdin
RESPONSE=$("$DAEMON_SH" request < "$PAYLOAD_FILE" 2>/dev/null || echo '{"ok":false,"error":"daemon request failed"}')
rm -f "$PAYLOAD_FILE"

# Parse response
OK=$(echo "$RESPONSE" | "$VENV_PYTHON" -c "import json,sys; print(json.loads(sys.stdin.read()).get('ok', False))" 2>/dev/null)
ERR=$(echo "$RESPONSE" | "$VENV_PYTHON" -c "import json,sys; print(json.loads(sys.stdin.read()).get('error', 'unknown'))" 2>/dev/null || true)
PATH_FIELD=$(echo "$RESPONSE" | "$VENV_PYTHON" -c "import json,sys; print(json.loads(sys.stdin.read()).get('path', ''))" 2>/dev/null || true)

if [[ "$OK" == "True" ]]; then
  echo "DONE: $PATH_FIELD"
  exit 0
else
  echo "Error: $ERR" >&2
  exit 1
fi
