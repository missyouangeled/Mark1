#!/bin/bash
# Mark42 Bootstrap — 公司机器开机自动挂载守护 Loop + 启动守护进程
# 
# 原则：不修改 Mark42 代码，纯通过现有 CLI 接口调用。
# 这样 Mark42 项目保持通用，公司定制独立在本文件里。
#
# 安装：（由 mark42-bootstrap.service 自动调用，无需手动执行）

set -e

MARK42="/home/missyouangeled/.openclaw/workspace/scripts/mark42.py"
LOGFILE="/home/missyouangeled/.local/state/openclaw/mark42/bootstrap.log"

mkdir -p "$(dirname "$LOGFILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

log "=== Mark42 Bootstrap 启动 ==="

# 等待 Mark42 初始化完成（首次可能需要 --init）
if [ ! -f /home/missyouangeled/.local/state/openclaw/mark42/config.json ]; then
    log "Mark42 未初始化，执行 --init"
    python3 "$MARK42" --init >> "$LOGFILE" 2>&1
fi

# 等待 Gateway 就绪（最多等 30 秒）
log "等待 Gateway 就绪..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:18789/healthz > /dev/null 2>&1; then
        log "✅ Gateway 就绪 (${i}s)"
        break
    fi
    if [ $i -eq 30 ]; then
        log "⚠️ Gateway 30s 内未就绪，继续注册 Loop（可能失败）"
    fi
    sleep 1
done

# ── Phase 1: 注册 Loop（纯注册，不执行） ──
register_loop() {
    local template="$1"
    local task="$2"
    local period="$3"
    log "注册 Loop: $template → $task ($period s)"
    python3 "$MARK42" engine --start --task "$task" --template "$template" --interval "$period" >> "$LOGFILE" 2>&1 || {
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
