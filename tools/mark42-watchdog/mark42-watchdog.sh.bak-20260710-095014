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

MARK42_WORKSPACE="${MARK42_WORKSPACE:-/home/missyouangeled/.openclaw/workspace}"
MARK42_CLI="${MARK42_CLI:-$MARK42_WORKSPACE/scripts/mark42.py}"
MARK42_PYTHON_BIN="${MARK42_PYTHON_BIN:-python3}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
MARK42_STATE_DIR="${MARK42_STATE_DIR:-$XDG_STATE_HOME/openclaw/mark42}"
MARK42_LOG_DIR="${MARK42_LOG_DIR:-$MARK42_STATE_DIR/logs}"
MARK42_SCRATCH="${MARK42_SCRATCH:-/mnt/data/openclaw/scratch}"
WORKSPACE="$MARK42_WORKSPACE"
HEARTBEAT="${HEARTBEAT:-$MARK42_STATE_DIR/engine/daemon-heartbeat.json}"
LOGFILE="${LOGFILE:-$MARK42_STATE_DIR/watchdog.log}"
PROACTIVE_INJECT="${PROACTIVE_INJECT:-$MARK42_WORKSPACE/scripts/openclaw-proactive-inject.py}"

mkdir -p "$(dirname "$LOGFILE")"
log() {
    local line="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    if [ -t 1 ]; then
        printf '%s\n' "$line" | tee -a "$LOGFILE"
    else
        printf '%s\n' "$line"
    fi
}

run_and_log() {
    if [ -t 1 ]; then
        "$@" 2>&1 | tee -a "$LOGFILE"
    else
        "$@"
    fi
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
    "$MARK42_PYTHON_BIN" "$PROACTIVE_INJECT" \
        --source "mark42-watchdog" --file "$ALERT_FILE" >/dev/null 2>&1 || true
}

# ── 0. L2.5 嵌入索引健康检查（只告警，不重启 service） ──
EMBED_INDEX="${EMBED_INDEX:-$MARK42_SCRATCH/memory-embed-index/embeddings.npy}"
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
MEMORY_INDEX="${MEMORY_INDEX:-$MARK42_SCRATCH/memory-index/MEMORY_INDEX.json}"
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
    last_tick=$("$MARK42_PYTHON_BIN" -c "
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

# 【2026-06-30 全面审查 K 修复】检查 4 个守护 Loop 状态
# 文档说 4 守护服务,实际 2 daemon + bootstrap + watchdog (4 个 Loop 由 engine_daemon 动态跑)
# watchdog 额外检查 4 Loop activeLoops=4、每个 loop 状态='registered',挂了就报
loops_check=$(python3 -c "
import json, subprocess
try:
    r = subprocess.run(['$MARK42_PYTHON_BIN', '$MARK42_CLI', 'status', '--json'],
                      capture_output=True, text=True, timeout=10)
    d = json.loads(r.stdout)
    eng = d.get('engine', {})
    active = eng.get('activeLoops', 0)
    total = eng.get('totalLoops', 0)
    loops = eng.get('loops', {})
    bad = [k for k, v in loops.items() if v.get('status') != 'registered']
    print(f'OK {active}/{total} {\",\".join(bad) if bad else \"\"}')
except Exception as e:
    print(f'ERR {e}')
" 2>/dev/null)
if [ -n "$loops_check" ]; then
    if [[ "$loops_check" == ERR* ]]; then
        reason="${reason:+$reason; }loops 检查出错 ($loops_check)"
        # 【🟡3】本地 log 留痕
        log "⚠️ 4 Loop 检查出错: $loops_check"
        notify_alert "loops-check-error" "🚨 mark42 watchdog 检查 4 Loop 时出错: $loops_check"
    else
        active_total=$(echo "$loops_check" | awk '{print $2}')
        bad_loops=$(echo "$loops_check" | awk '{print $3}')
        expected_active=$(echo "$active_total" | cut -d/ -f1)
        expected_total=$(echo "$active_total" | cut -d/ -f2)
        if [ "$expected_active" != "$expected_total" ]; then
            reason="${reason:+$reason; }4 Loop 有挂 (active=$expected_active/$expected_total)"
            # 【🟡3】本地 log 留痕
            log "⚠️ 4 Loop 状态: $expected_active/$expected_total (expected: $expected_total)"
            notify_alert "loops-missing" "🚨 mark42 4 Loop 状态: $expected_active/$expected_total。可能是 engine_daemon 出问题,需查 \`mark42.py status\`"
        elif [ -n "$bad_loops" ]; then
            reason="${reason:+$reason; }Loop 状态不为 registered: $bad_loops"
            # 【🟡3】本地 log 留痕
            log "⚠️ Loop 状态不为 registered: $bad_loops"
            notify_alert "loops-degraded" "🚨 mark42 Loop 状态异常: $bad_loops。看 \`mark42.py status --json\` 查细节"
        fi
    fi
else
    reason="${reason:+$reason; }loops 检查无输出"
    # 【🟡3】本地 log 留痕
    log "⚠️ 4 Loop 检查无输出"
fi

# ── 3. 处置 ──
if [ -n "$need_restart" ]; then
    log "⚠️ 检测到异常: $reason → 重启 service"
    run_and_log systemctl --user restart mark42-engine-daemon.service || log "   engine-daemon 重启失败"
    run_and_log systemctl --user restart mark42-armor-guard.service || log "   armor-guard 重启失败"
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
