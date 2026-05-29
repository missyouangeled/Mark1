#!/bin/bash
# flush-memory-sync.sh
# 把 memory flush 事件写入的扁平路径内容合并到 daily 归档
# 每天由 lifecycle-maintainer 调用
set -euo pipefail

WORKSPACE="${WORKSPACE_DIR:-/home/missyouangeled/.openclaw/workspace}"
MEMORY_DIR="$WORKSPACE/memory"
DAILY_DIR="$MEMORY_DIR/daily"
TODAY="$(date +%Y-%m-%d)"

FLAT_PATH="$MEMORY_DIR/${TODAY}.md"
DAILY_PATH="$DAILY_DIR/${TODAY}.md"

if [ ! -f "$FLAT_PATH" ]; then
    echo "no flush memory for $TODAY"
    exit 0
fi

CONTENT_SIZE=$(stat -c%s "$FLAT_PATH" 2>/dev/null || echo 0)
if [ "$CONTENT_SIZE" -eq 0 ]; then
    echo "empty flush memory, nothing to sync"
    rm -f "$FLAT_PATH"
    exit 0
fi

mkdir -p "$DAILY_DIR"

# Append with separator
{
    echo ""
    echo "## flush-sync $(date +%H:%M)"
    cat "$FLAT_PATH"
} >> "$DAILY_PATH"

echo "synced ${CONTENT_SIZE} bytes from flush to daily archive"
rm -f "$FLAT_PATH"
