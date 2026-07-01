#!/bin/bash
# Mark42 Bootstrap — 公司机器开机自动挂载守护 Loop + 启动守护进程
# 
# 原则：不修改 Mark42 代码，纯通过现有 CLI 接口调用。
# 这样 Mark42 项目保持通用，公司定制独立在本文件里。
#
# 安装：（由 mark42-bootstrap.service 自动调用，无需手动执行）

set -e

MARK42_WORKSPACE="${MARK42_WORKSPACE:-/home/missyouangeled/.openclaw/workspace}"
MARK42_CLI="${MARK42_CLI:-$MARK42_WORKSPACE/scripts/mark42.py}"
MARK42_PYTHON_BIN="${MARK42_PYTHON_BIN:-python3}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
MARK42_STATE_DIR="${MARK42_STATE_DIR:-$XDG_STATE_HOME/openclaw/mark42}"
MARK42_LOG_DIR="${MARK42_LOG_DIR:-$MARK42_STATE_DIR/logs}"
MARK42_SCRATCH="${MARK42_SCRATCH:-/mnt/data/openclaw/scratch}"
LOGFILE="${LOGFILE:-$MARK42_STATE_DIR/bootstrap.log}"
CONFIG_FILE="${CONFIG_FILE:-$MARK42_STATE_DIR/config.json}"
LOOPS_FILE="${LOOPS_FILE:-$MARK42_STATE_DIR/engine/loops.json}"
GATEWAY_HEALTH_URL="${GATEWAY_HEALTH_URL:-http://127.0.0.1:18789/healthz}"

mkdir -p "$(dirname "$LOGFILE")" "$MARK42_STATE_DIR" "$MARK42_LOG_DIR" "$MARK42_SCRATCH" "$MARK42_STATE_DIR/engine"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

log "=== Mark42 Bootstrap 启动 ==="

# 等待 Mark42 初始化完成（首次可能需要 --init）
if [ ! -f "$CONFIG_FILE" ]; then
    log "Mark42 未初始化，执行 --init"
    "$MARK42_PYTHON_BIN" "$MARK42_CLI" --init >> "$LOGFILE" 2>&1
fi

# 等待 Gateway 就绪（最多等 30 秒）
log "等待 Gateway 就绪..."
for i in $(seq 1 30); do
    if curl -s "$GATEWAY_HEALTH_URL" > /dev/null 2>&1; then
        log "✅ Gateway 就绪 (${i}s)"
        break
    fi
    if [ $i -eq 30 ]; then
        log "⚠️ Gateway 30s 内未就绪，继续注册 Loop（可能失败）"
    fi
    sleep 1
done

# ── Phase 1: 注册 Loop（纯注册，不执行） ──
# 先清理上轮遗留的 registered/running 状态的 Loop（防止连续开机多次重复注册）
# 保留 status=killed/completed 的（历史记录）
log "清理上轮残留 Loop (status=registered/running 且未在心跳周期内)..."
export LOOPS_FILE
"$MARK42_PYTHON_BIN" << 'PYEOF' >> "$LOGFILE" 2>&1 || true
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone, timedelta

loops_file = Path(os.environ["LOOPS_FILE"])
if loops_file.exists():
    try:
        loops = json.loads(loops_file.read_text())
        cleaned = []
        kept = []
        now = datetime.now(timezone.utc)
        for name, lp in loops.items():
            status = lp.get("status", "")
            interval = lp.get("interval", 300)
            last_run_str = lp.get("lastRun")
            if status in ("registered", "running") and last_run_str:
                # 如果 lastRun 距今超过 3 倍 interval，说明这个 Loop 已经死了
                try:
                    last_run = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
                    age = (now - last_run).total_seconds()
                    if age > 3 * interval:
                        cleaned.append(f"{name} (dead {age:.0f}s)")
                        continue
                except Exception:
                    pass
            kept.append(name)
        # 重新构造：只留 kept
        new_loops = {k: v for k, v in loops.items() if k in kept}
        loops_file.write_text(json.dumps(new_loops, indent=2, ensure_ascii=False))
        print(f"清理了 {len(cleaned)} 个死 Loop: {cleaned}")
        print(f"保留 {len(kept)} 个 Loop: {kept}")
    except Exception as e:
        print(f"清理失败（忽略）: {e}")
PYEOF
register_loop() {
    local template="$1"
    local task="$2"
    local period="$3"
    log "注册 Loop: $template → $task ($period s)"
    "$MARK42_PYTHON_BIN" "$MARK42_CLI" engine --start --task "$task" --template "$template" --interval "$period" >> "$LOGFILE" 2>&1 || {
        log "   ⚠️ 注册失败（可能已存在，忽略）"
    }
}

register_loop "context-guard"  "守护上下文"     300
register_loop "health-watch"   "健康监控"       600
register_loop "model-fallback" "模型可用性监测"  60
register_loop "memory-index"   "记忆自动归类"   21600
# task-watch 通过 engine daemon 事件检测自动创建，无需手动注册
# （Engine daemon 检测到 heavy.task.started broker 事件后自动创建）

# ── Phase 2: 启动守护进程 ──
log "🛡️ 启动守护进程..."

# 先确保旧的 assemble 子进程已清理（如果存在）
pkill -f "mark42.py armor --guard" 2>/dev/null || true
pkill -f "mark42.py engine --daemon" 2>/dev/null || true
sleep 1

# 重新启动
systemctl --user restart mark42-armor-guard.service 2>/dev/null || log "   ⚠️ armor-guard service 不存在（跳过）"
systemctl --user restart mark42-engine-daemon.service 2>/dev/null || log "   ⚠️ engine-daemon service 不存在（跳过）"

log "✅ Bootstrap 完成（Loop 已注册 + 守护进程已启动）"
log ""
