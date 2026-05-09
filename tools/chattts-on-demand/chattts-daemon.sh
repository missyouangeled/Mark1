#!/usr/bin/env bash
# =============================================================================
# chattts-daemon.sh — ChatTTS on-demand daemon lifecycle manager
#
# Starts the daemon if not running, sends a TTS request via Unix socket,
# and waits for the response. The daemon auto-exits after idle timeout.
#
# Usage:
#   ./chattts-daemon.sh start                 # Start daemon in background
#   ./chattts-daemon.sh stop                  # Stop daemon gracefully
#   ./chattts-daemon.sh status                # Check if daemon is running
#   echo '{"text":"hello"}' | ./chattts-daemon.sh request  # Send request
#
# For most users, use chattts-on-demand.sh instead (simpler CLI).
# =============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DAEMON_PY="$BASE_DIR/tools/chattts-on-demand/chattts_daemon.py"
SOCKET="$BASE_DIR/tmp/.chattts-daemon.sock"
LOCK="$BASE_DIR/tmp/.chattts-daemon.lock"
PID_FILE="$BASE_DIR/tmp/.chattts-daemon.pid"
VENV_PYTHON="$HOME/.local/share/openclaw-voice-venv311/bin/python3"
LOG_FILE="$BASE_DIR/tmp/.chattts-daemon.log"

action="${1:-}"
shift 2>/dev/null || true

case "$action" in
  start)
    if [ -f "$PID_FILE" ]; then
      pid=$(cat "$PID_FILE")
      if kill -0 "$pid" 2>/dev/null; then
        echo "Daemon already running (PID $pid)"
        exit 0
      fi
      echo "Stale PID file. Removing."
      rm -f "$PID_FILE"
    fi
    rm -f "$SOCKET" "$LOCK"
    # Rotate log: keep last 2 logs, truncate current
    if [ -f "$LOG_FILE" ]; then
      cp "$LOG_FILE" "$LOG_FILE.old" 2>/dev/null || true
    fi
    : > "$LOG_FILE"
    echo "Starting ChatTTS daemon..."
    nohup "$VENV_PYTHON" "$DAEMON_PY" --idle-timeout 300 > "$LOG_FILE" 2>&1 &
    daemon_pid=$!
    echo $daemon_pid > "$PID_FILE"
    disown
    echo -n "Waiting for daemon to start"
    for i in $(seq 1 60); do
      if [ -S "$SOCKET" ]; then
        echo " OK (PID $daemon_pid)"
        exit 0
      fi
      if ! kill -0 "$daemon_pid" 2>/dev/null; then
        echo " FAILED"
        cat "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
      fi
      echo -n "."
      sleep 1
    done
    echo " TIMEOUT (60s)"
    cat "$LOG_FILE"
    exit 1
    ;;

  stop)
    if [ ! -f "$PID_FILE" ]; then
      echo "Daemon not running (no PID file)"
      rm -f "$SOCKET" "$LOCK"
      exit 0
    fi
    pid=$(cat "$PID_FILE")
    echo "Stopping daemon (PID $pid)..."
    kill "$pid" 2>/dev/null || true
    for i in $(seq 1 10); do
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "Stopped"
        rm -f "$PID_FILE" "$SOCKET" "$LOCK"
        exit 0
      fi
      sleep 1
    done
    echo "Force killing..."
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE" "$SOCKET" "$LOCK"
    echo "Force stopped"
    ;;

  status)
    if [ -f "$PID_FILE" ]; then
      pid=$(cat "$PID_FILE")
      if kill -0 "$pid" 2>/dev/null; then
        echo "Daemon running: PID $pid"
        if [ -S "$SOCKET" ]; then
          echo "Socket: $SOCKET (connected)"
        else
          echo "Socket: missing (stale?)"
        fi
        exit 0
      fi
      echo "PID file exists but process is dead (stale PID $pid)"
      rm -f "$PID_FILE" "$SOCKET" "$LOCK"
    else
      if [ -S "$SOCKET" ]; then
        echo "Stale socket found (no PID file). Cleaning up."
        rm -f "$SOCKET" "$LOCK"
      fi
      echo "Daemon not running"
    fi
    ;;

  request)
    # Read JSON payload from arguments or stdin (stdin is safer for complex payloads)
    # Before anything: cleanup any stale PID file from a previous daemon that idle-exited
    if [ -f "$PID_FILE" ]; then
      pid=$(cat "$PID_FILE")
      if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE" "$SOCKET" "$LOCK"
      fi
    fi
    if [ ! -S "$SOCKET" ]; then
      echo "Daemon not running. Auto-starting..." >&2
      $0 start >&2
    fi

    # Read payload: first arg, or stdin
    payload=""
    if [ $# -ge 1 ]; then
      payload="$1"
    else
      payload=$(cat)
    fi

    if [ -z "$payload" ]; then
      echo '{"ok":false,"error":"Empty payload"}'
      exit 1
    fi

    # Write payload to temp file, then use python to send via Unix socket
    # (This avoids all shell escaping issues with JSON)
    tmpfile=$(mktemp /tmp/chattts-payload.XXXXXX)
    printf '%s\n' "$payload" > "$tmpfile"
    # Retry loop: daemon might still be starting up
    for attempt in $(seq 1 30); do
      if [ -S "$SOCKET" ]; then
        break
      fi
      sleep 1
    done
    # Try to connect. If socket is stale (daemon crashed), auto-restart.
    CONNECT_RESULT=$("$VENV_PYTHON" -c "
import json, socket, sys
payload = open('$tmpfile', 'r').read().strip()
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(5.0)
try:
    s.connect('$SOCKET')
    s.close()
    print('ok')
except Exception as e:
    print('stale: ' + str(e))
    sys.exit(1)
" 2>/dev/null || echo 'failed')

    if [ "$CONNECT_RESULT" != "ok" ]; then
      echo "Stale socket detected, restarting daemon..." >&2
      rm -f "$SOCKET" "$LOCK" "$PID_FILE"
      $0 start >&2
      # Give daemon a moment to start listening
      sleep 2
    fi

    "$VENV_PYTHON" -c "
import json, socket, sys
payload = open('$tmpfile', 'r').read().strip()
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(180.0)
try:
    s.connect('$SOCKET')
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False))
    sys.exit(1)
s.sendall((payload + chr(10)).encode('utf-8'))
buf = b''
while True:
    try:
        ch = s.recv(4096)
        if not ch:
            break
        buf += ch
        if b'\n' in buf:
            break
    except socket.timeout:
        break
s.close()
try:
    resp = json.loads(buf.decode('utf-8').strip())
    print(json.dumps(resp, ensure_ascii=False))
except:
    print(buf.decode('utf-8').strip())
" 2>/dev/null || echo '{"ok":false,"error":"Connection failed"}'
    rm -f "$tmpfile"
    ;;

  *)
    echo "Usage: $0 {start|stop|status|request [payload]}"
    exit 1
    ;;
esac
