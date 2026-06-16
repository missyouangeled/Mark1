#!/bin/bash
# Mark42 Bootstrap — 公司机器开机自动挂载四个守护 Loop
# 
# 原则：不修改 Mark42 代码，纯通过现有 CLI 接口调用。
# 这样 Mark42 项目保持通用，公司定制独立在本文件里。
#
# 安装：
#   systemctl --user enable --now mark42-bootstrap.service
# 或手动：
#   bash tools/mark42-bootstrap/mark42-bootstrap.sh

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

# 逐个注册 Loop（幂等——重复注册同名 Loop 会失败但不影响运行）
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

log "✅ Bootstrap 完成（4 个 Loop 已就绪）"
log ""
