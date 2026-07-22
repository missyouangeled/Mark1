#!/bin/bash
# 清理 media/tts/ 下超过 4 小时的语音文件
TTS_DIR="/home/missyouangeled/.openclaw/workspace/media/tts"
MAX_AGE_MINUTES=240  # 4 小时

if [ ! -d "$TTS_DIR" ]; then
  exit 0
fi

find "$TTS_DIR" -type f \( -name "*.wav" -o -name "*.mp3" \) -mmin +"$MAX_AGE_MINUTES" -delete

# 记录清理日志
DELETED=$(find "$TTS_DIR" -type f \( -name "*.wav" -o -name "*.mp3" \) 2>/dev/null | wc -l)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] TTS cleanup done, remaining files: $DELETED"
