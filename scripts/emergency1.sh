#!/bin/bash
# 救命 1 v4: 主会话行数 + watcher 告警转发
# 由 openclaw cron 调用（--command "bash /path/to/emergency1.sh"）
set +e

SESSIONS_JSON=/home/missyouangeled/.openclaw/agents/main/sessions/sessions.json
WORKSPACE=/home/missyouangeled/.openclaw/workspace
MAIN_SID=$(python3 -c "import json; d=json.load(open('$SESSIONS_JSON')); print(d.get('agent:main:main',{}).get('sessionId',''))")
SESS=${SESSIONS_DIR:-/home/missyouangeled/.openclaw/agents/main/sessions}/${MAIN_SID}.jsonl

if [ ! -f "$SESS" ]; then
  echo "[救命 1 错误] 主 session 文件不存在: $SESS"
  exit 1
fi

LINES=$(wc -l < "$SESS" 2>/dev/null || echo 0)
THRESHOLD=12000
ALERT_FLAG=/tmp/emergency1-alert.flag

# 1b. trajectory 大小检查（独立告警）
TRAJ=${SESS%.jsonl}.trajectory.jsonl
TRAJ_THRESHOLD_MB=5
TRAJ_ALERT_FLAG=/tmp/emergency1-trajectory-alert.flag
if [ -f "$TRAJ" ]; then
  TRAJ_MB=$(du -m "$TRAJ" 2>/dev/null | cut -f1)
  if [ "${TRAJ_MB:-0}" -gt $TRAJ_THRESHOLD_MB ]; then
    if [ ! -f "$TRAJ_ALERT_FLAG" ] || [ -n "$(find "$TRAJ_ALERT_FLAG" -mmin +60 2>/dev/null)" ]; then
      MSG="[救命 1 trajectory 告警] 当前会话 trajectory ${TRAJ_MB}MB > 阈值 ${TRAJ_THRESHOLD_MB}MB。sessionId: ${MAIN_SID}。建议运行：python3 scripts/compress-trajectory.py ${MAIN_SID} --keep 3 --execute"
      python3 "$WORKSPACE/scripts/openclaw-proactive-inject.py" --source "emergency-1-trajectory-alert" "$MSG" 2>&1
      touch "$TRAJ_ALERT_FLAG"
      echo "[救命 1 trajectory 告警已发] ${TRAJ_MB}MB > ${TRAJ_THRESHOLD_MB}MB"
    else
      echo "[救命 1 trajectory 静默（cooldown 60min）] ${TRAJ_MB}MB"
    fi
  else
    rm -f "$TRAJ_ALERT_FLAG"
    echo "[救命 1 trajectory 静默] ${TRAJ_MB}MB <= ${TRAJ_THRESHOLD_MB}MB"
  fi
else
  echo "[救命 1 trajectory 不存在] $TRAJ"
fi

# 1. session 行数检查
if [ "$LINES" -gt $THRESHOLD ]; then
  if [ ! -f "$ALERT_FLAG" ] || [ -n "$(find "$ALERT_FLAG" -mmin +30 2>/dev/null)" ]; then
    MSG="[救命 1 告警] main session 行数 ${LINES} > ${THRESHOLD}。sessionId: ${MAIN_SID}。按 CASE-20260706-005 不动 session，建议人工处理。"
    touch "$ALERT_FLAG"
    python3 "$WORKSPACE/scripts/openclaw-proactive-inject.py" --source "emergency-1-alert" "$MSG" 2>&1
    echo "[救命 1 告警已发] LINES=$LINES"
  else
    echo "[救命 1 静默（cooldown）] LINES=$LINES"
  fi
else
  rm -f "$ALERT_FLAG"
  echo "[救命 1 静默] session=${MAIN_SID} LINES=$LINES"
fi

# 2. 转发 watcher 未读 alerts
WATCHER_ALERTS=/home/missyouangeled/.local/state/openclaw/session-size-watcher/alerts.json
if [ -f "$WATCHER_ALERTS" ]; then
  ALERT_DATA=$(python3 "$WORKSPACE/scripts/emergency1-watcher-read.py" "$WATCHER_ALERTS")
  if echo "$ALERT_DATA" | grep -q "^UNREAD_SUMMARY="; then
    SUMMARY=$(echo "$ALERT_DATA" | grep "^UNREAD_SUMMARY=" | head -1 | sed "s/^UNREAD_SUMMARY=//")
    DETAILS=$(echo "$ALERT_DATA" | grep "^WARN:" | head -3)
    FORWARD_FLAG=/tmp/emergency1-watcher-alert.flag
    if [ ! -f "$FORWARD_FLAG" ] || [ -n "$(find "$FORWARD_FLAG" -mmin +30 2>/dev/null)" ]; then
      MSG="[救命 1 watcher 转发] session-size-watcher 未读告警: ${SUMMARY}
${DETAILS}
（按 docs/系统自动行为盘点.md 第 7 节 P0 修复：观察并自动转发 alerts）"
      python3 "$WORKSPACE/scripts/openclaw-proactive-inject.py" --source "emergency-1-watcher-forward" "$MSG" 2>&1
      touch "$FORWARD_FLAG"
      echo "[救命 1 watcher 告警已转] $SUMMARY"
    else
      echo "[救命 1 watcher 告警 cooldown]"
    fi
  fi
fi
