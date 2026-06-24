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

# ── 告警通知函数（去重 + 推送到当前 dashboard） ──
NOTIFY_COOLDOWN_DIR="/tmp/mark42-watchdog-notify"
ALERT_FILE="/tmp/mark42-watchdog-alert.txt"
mkdir -p "$NOTIFY_COOLDOWN_DIR" 2>/dev/null || true

notify_alert() {
    local key="$1"
    local msg="$2"
    local cooldown_file="$NOTIFY_COOLDOWN_DIR/$key"
    local now_epoch=$(date +%s)
    # 1 小时去重
    if [ -f "$cooldown_file" ]; then
        local last=$(cat "$cooldown_file" 2>/dev/null || echo 0)
        if [ $((now_epoch - last)) -lt 3600 ]; then
            return 0  # 静默
        fi
    fi
    echo "$now_epoch" > "$cooldown_file" 2>/dev/null || true
    # 推送到 dashboard (失败不影响主流程)
    echo -n "$msg" > "$ALERT_FILE" 2>/dev/null || true
    python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-proactive-inject.py \
        --source "mark42-watchdog" --file "$ALERT_FILE" >/dev/null 2>&1 || true
}

# ── 0. L2.5 嵌入索引健康检查（只告警，不重启 service） ──
EMBED_INDEX="/mnt/data/openclaw/scratch/memory-embed-index/embeddings.npy"
EMBED_MIN_BYTES=100000  # 100 KB 以下视为异常（正常 ~10 MB）
if [ ! -f "$EMBED_INDEX" ]; then
    log "🚨 L2.5 嵌入索引缺失: $EMBED_INDEX 不存在"
    notify_alert "embed-missing" "🚨 记忆系统 L2.5 嵌入索引丢失了。点点的语义搜索会变哑，关键词搜索 (L1) 还能用。需要跑：memory-embed-index.py --force 重建"
elif [ ! -s "$EMBED_INDEX" ]; then
    log "🚨 L2.5 嵌入索引为空: $EMBED_INDEX 是 0 字节文件"
    notify_alert "embed-empty" "🚨 记忆系统 L2.5 嵌入索引变成了 0 字节空文件。需要跑：memory-embed-index.py --force 重建"
else
    size=$(stat -c%s "$EMBED_INDEX" 2>/dev/null || echo 0)
    if [ "$size" -lt "$EMBED_MIN_BYTES" ]; then
        log "🚨 L2.5 嵌入索引过小: $EMBED_INDEX 只有 ${size} 字节 (阈值 ${EMBED_MIN_BYTES})"
        notify_alert "embed-tiny" "🚨 记忆系统 L2.5 嵌入索引只有 ${size} 字节 (正常 ~10MB)。可能重建失败中断了，需要跑：memory-embed-index.py --force 重建"
    fi
fi

# ── 0b. L1 MEMORY_INDEX 健康检查（只告警，不重启 service） ──
MEMORY_INDEX="/mnt/data/openclaw/scratch/memory-index/MEMORY_INDEX.json"
MEMORY_INDEX_MIN_BYTES=10000  # 10 KB 以下视为异常（正常 ~260 KB）
if [ ! -f "$MEMORY_INDEX" ]; then
    log "🚨 L1 关键词索引缺失: $MEMORY_INDEX 不存在"
    notify_alert "l1-missing" "🚨 记忆系统 L1 关键词索引丢失了。点点的记忆快搜会完全失灵。需要跑：memory-index-builder.py 重建"
elif [ ! -s "$MEMORY_INDEX" ]; then
    log "🚨 L1 关键词索引为空: $MEMORY_INDEX 是 0 字节文件"
    notify_alert "l1-empty" "🚨 记忆系统 L1 关键词索引变成了 0 字节空文件。需要跑：memory-index-builder.py 重建"
else
    size=$(stat -c%s "$MEMORY_INDEX" 2>/dev/null || echo 0)
    if [ "$size" -lt "$MEMORY_INDEX_MIN_BYTES" ]; then
        log "🚨 L1 关键词索引过小: $MEMORY_INDEX 只有 ${size} 字节 (阈值 ${MEMORY_INDEX_MIN_BYTES})"
        notify_alert "l1-tiny" "🚨 记忆系统 L1 关键词索引只有 ${size} 字节 (正常 ~2.2MB)。需要跑：memory-index-builder.py 重建"
    fi
fi

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