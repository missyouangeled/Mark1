#!/usr/bin/env bash
# =============================================================================
# voice-reply-chunked-deliver.sh — 分块音频 → 当前会话一次性交付
#
# 核心约定（用户 2026-05-12 明确）：
#   "主会话" ≡ "当前会话"
#   所有交付绑定当前会话，一次回复送所有音频。
#   本脚本不包含任何会话标识——agentReply 由调用者的会话自然绑定。
#   调用者不得拼入 agent:main:main 之类的标识。
#
# 做法：
#   调用现有分块语音管线，生成所有分块音频后，
#   输出包含媒体路径的 agentReply 文本。
#
# 输出（stdout JSON）：
#   ok:                  true/false
#   agentReply:          当前会话可直接返回的文本
#                        格式：头段文字
#                              [[audio_as_voice]]
#                              MEDIA:块1绝对路径
#                              MEDIA:块2绝对路径（如有）
#                              ...
#   chunkCount:          分块数
#   mediaPaths:          所有音频路径的数组（workspace 绝对路径）
#   audioAsVoice:        标记已含 [[audio_as_voice]]
#
# 用法（agent exec 调用）：
#   result=$(bash tools/voice-reply/voice-reply-chunked-deliver.sh "回复文本" [preset])
#   echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['agentReply'])"
#   # 将 agentReply 作为当前会话返回内容
#
# 架构（现有管线不动）：
#   voice-reply-chunked-deliver.sh
#     └─→ voice-reply-chunked.sh（现有，未改动）
#           └─→ chunked_voice_reply.py（现有，未改动）
#                 └─→ chattts_voice_reply.py（现有，未改动）
# =============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHUNKED_SH="$BASE_DIR/tools/voice-reply/voice-reply-chunked.sh"
CLEANUP_SH="$BASE_DIR/tools/chattts-on-demand/cleanup-old-audio.sh"

TEXT="${1:-}"
PRESET="${2:-${OPENCLAW_VOICE_REPLY_PRESET:-default}}"

if [[ -z "$TEXT" ]]; then
  echo '{"ok":false,"error":"empty text","agentReply":"","chunkCount":0,"mediaPaths":[],"audioAsVoice":false}'
  exit 1
fi

if [[ ! -f "$CHUNKED_SH" ]]; then
  TEXT_SAFE=$(echo "$TEXT" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")
  echo "{\"ok\":false,\"error\":\"chunked pipeline not found\",\"agentReply\":${TEXT_SAFE},\"chunkCount\":0,\"mediaPaths\":[],\"audioAsVoice\":false}"
  exit 0
fi

# 机会性清理
[[ -x "$CLEANUP_SH" ]] && "$CLEANUP_SH" --quiet 2>/dev/null || true

# 调用现有分块管线
RAW=$("$CHUNKED_SH" "$TEXT" "$PRESET" --message-plan 2>/dev/null) || {
  TEXT_SAFE=$(echo "$TEXT" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")
  echo "{\"ok\":false,\"error\":\"synthesis failed — fall back to text-only\",\"agentReply\":${TEXT_SAFE},\"chunkCount\":0,\"mediaPaths\":[],\"audioAsVoice\":false}"
  exit 0
}

# 验证 JSON
echo "$RAW" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null || {
  TEXT_SAFE=$(echo "$TEXT" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")
  echo "{\"ok\":false,\"error\":\"invalid JSON from chunked pipeline\",\"agentReply\":${TEXT_SAFE},\"chunkCount\":0,\"mediaPaths\":[],\"audioAsVoice\":false}"
  exit 0
}

# 组装 agentReply：分块文字 + [[audio_as_voice]] + 所有 MEDIA: 行
# 用 Python 处理 JSON 和字符串拼接
echo "$RAW" | python3 -c "
import json, sys

data = json.load(sys.stdin)
all_chunks = data.get('allChunks', [])
paths = [c.get('path', '') for c in all_chunks if c.get('path')]
texts = [c.get('text', '') for c in all_chunks]

if not paths:
    output = {
        'ok': False,
        'error': 'no audio generated',
        'agentReply': '',
        'chunkCount': 0,
        'mediaPaths': [],
        'audioAsVoice': False,
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)

# 拼成当前会话可返回的一条消息
# 头段：所有分块文字拼接（保持阅读流畅）
head_text = ' '.join(texts)
# MEDIA 行
media_lines = '\\n'.join(f'MEDIA:{p}' for p in paths)

agent_reply = f\"\"\"{head_text}

[[audio_as_voice]]
{media_lines}\"\"\"

output = {
    'ok': True,
    'agentReply': agent_reply,
    'chunkCount': len(paths),
    'mediaPaths': paths,
    'audioAsVoice': True,
}
print(json.dumps(output, ensure_ascii=False))
"
