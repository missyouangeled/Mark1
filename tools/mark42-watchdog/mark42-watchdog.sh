#!/bin/bash
# Mark42 Watchdog — 定期检查 daemon 存活 + 自动重启
# 
# 触发：mark42-watchdog.timer (5 分钟一次)
# 行为：
#   1. 检查 daemon-heartbeat.json 的 lastTick 是否超过 5 分钟
#   2. 检查 mark42-engine-daemon / mark42-armor-guard 进程是否存在
#   3. 如果心跳超时或进程死了 → restart service
#   4. 都正常 → 静默退出

set -e

WORKSPACE="/home/missyouangeled/.openclaw/workspace"
HEARTBEAT="$HOME/.local/state/openclaw/mark42/engine/daemon-heartbeat.json"
LOGFILE="/home/missyouangeled/.local/state/openclaw/mark42/watchdog.log"

mkdir -p "$(dirname "$LOGFILE")"
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

WARN_THRESHOLD=300  # 5 分钟心跳超时视为异常

need_restart=""
reason=""

# ── 1. 心跳超时检查 ──
if [ -f "$HEARTBEAT" ]; then
    last_tick=$(python3 -c "
import json
from datetime import datetime, timezone
try:
    d = json.loads(open('$HEARTBEAT').read())
    last = datetime.fromisoformat(d.get('lastTick', '').replace('Z', '+00:00'))
    age = (datetime.now(timezone.utc) - last).total_seconds()
    print(int(age))
except Exception:
    print(-1)
" 2>/dev/null)
    if [ "$last_tick" = "-1" ]; then
        reason="心跳文件不可解析"
        need_restart=1
    elif [ "$last_tick" -gt "$WARN_THRESHOLD" ]; then
        reason="心跳超时 ${last_tick}s (>${WARN_THRESHOLD}s)"
        need_restart=1
    fi
else
    reason="心跳文件不存在"
    need_restart=1
fi

# ── 2. 进程检查 ──
engine_pid=$(pgrep -f "mark42.py engine --daemon" | head -1 || echo "")
armor_pid=$(pgrep -f "mark42.py armor --guard" | head -1 || echo "")

if [ -z "$engine_pid" ]; then
    reason="${reason:+$reason; }engine-daemon 进程不在"
    need_restart=1
fi
if [ -z "$armor_pid" ]; then
    reason="${reason:+$reason; }armor-guard 进程不在"
    need_restart=1
fi

# ── 3. 处置 ──
if [ -n "$need_restart" ]; then
    log "⚠️ 检测到异常: $reason → 重启 service"
    systemctl --user restart mark42-engine-daemon.service 2>&1 | tee -a "$LOGFILE" || log "   engine-daemon 重启失败"
    systemctl --user restart mark42-armor-guard.service 2>&1 | tee -a "$LOGFILE" || log "   armor-guard 重启失败"
    sleep 5
    new_engine=$(pgrep -f "mark42.py engine --daemon" | head -1 || echo "")
    new_armor=$(pgrep -f "mark42.py armor --guard" | head -1 || echo "")
    if [ -n "$new_engine" ] && [ -n "$new_armor" ]; then
        log "✅ 重启成功: engine=$new_engine, armor=$new_armor"
    else
        log "❌ 重启后仍有进程缺失: engine=$new_engine, armor=$new_armor"
    fi
else
    # 正常情况不输出（避免日志爆量）
    :
fi