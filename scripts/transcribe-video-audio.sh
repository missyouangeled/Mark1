#!/usr/bin/env bash
# ============================================================================
# transcribe-video-audio.sh — 从视频提取音频 + 调用 NVIDIA ASR bridge 转写
#
# 用途：从视频（或视频片段）提取音频，通过本地 NVIDIA Audio Bridge
#       ASR 端点做语音转写，输出转写文本。
#
# 依赖：
#   - ffmpeg（系统安装或 FALLBACK 路径）
#   - NVIDIA Audio Bridge 服务运行在 http://127.0.0.1:18890
#
# 用法：
#   bash scripts/transcribe-video-audio.sh <视频路径> [选项]
#
# 选项：
#   --start TIME          片段起始位置（HH:MM:SS 或秒数），默认 00:00:00
#   --duration SEC         片段时长（秒），与 --end 二选一
#   --end TIME             片段结束位置（HH:MM:SS 或秒数），与 --duration 二选一
#   --model MODEL          ASR 模型。默认自动选择：
#                             中文 → nvidia/whisper-large-v3
#                             (bridge 中有中文自动 fallback)
#   --language LANG       语言代码（zh-CN / en-US 等）。默认自动检测
#   -o, --outdir DIR       输出目录，默认自动生成
#   -f, --force            覆盖已有输出目录
#   --bridge-url URL       bridge 地址，默认 http://127.0.0.1:18890
#   --bridge-port PORT     bridge 端口（替代完整 URL）
#   -h, --help             显示帮助
#
# 输出目录结构：
#   <outdir>/
#     audio/                ← 提取的音频文件
#       original.wav         ← WAV 格式音频
#       original.mp3         ← MP3 格式音频（可听）
#     transcript.txt         ← 转写纯文本
#     transcript.json        ← 转写完整 JSON（含模型信息）
#     manifest.json          ← 作业元数据
#
# 示例：
#   bash scripts/transcribe-video-audio.sh test.mp4
#   bash scripts/transcribe-video-audio.sh test.mp4 --language zh-CN
#   bash scripts/transcribe-video-audio.sh test.mp4 --start 5 --duration 10
# ============================================================================

set -euo pipefail

# ---------- 颜色 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ️${NC} $*"; }
ok()    { echo -e "${GREEN}✅${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠️${NC} $*"; }
err()   { echo -e "${RED}❌${NC} $*" >&2; }

# ---------- 默认值 ----------
ASR_MODEL=""               # 空 = 让 bridge 自动选择
ASR_LANGUAGE="zh-CN"       # 默认中文
OUTDIR=""
FORCE=false

SEGMENT_START=""
SEGMENT_DURATION=""
SEGMENT_END=""

BRIDGE_URL="http://127.0.0.1:18890"
BRIDGE_PORT=""

# ---------- 路径 ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="${HOME}/.openclaw/workspace"

# ---------- 辅助函数 ----------
to_seconds() {
  local val="$1"
  if [[ "$val" =~ ^[0-9]+$ ]]; then
    echo "$val"
  elif [[ "$val" =~ ^([0-9]+):([0-9]{2}):([0-9]{2})$ ]]; then
    local h=${BASH_REMATCH[1]}
    local m=${BASH_REMATCH[2]}
    local s=${BASH_REMATCH[3]}
    echo "$((10#$h * 3600 + 10#$m * 60 + 10#$s))"
  else
    echo ""
  fi
}

fmt_time() {
  local secs="$1"
  local h=$(( secs / 3600 ))
  local m=$(( (secs % 3600) / 60 ))
  local s=$(( secs % 60 ))
  printf "%02d:%02d:%02d" "$h" "$m" "$s"
}

# ---------- 解析参数 ----------
usage() {
  cat <<'HELP'
transcribe-video-audio.sh — 从视频提取音频 + 调用 NVIDIA ASR bridge 转写

用法:
  bash scripts/transcribe-video-audio.sh <视频路径> [选项]

选项:
  --start TIME      片段起始位置（HH:MM:SS 或秒数），默认 00:00:00
  --duration SEC    片段时长（秒），与 --end 二选一
  --end TIME        片段结束位置（HH:MM:SS 或秒数），与 --duration 二选一
  --model MODEL     ASR 模型。示例：nvidia/whisper-large-v3
  --language LANG   语言代码，默认 zh-CN
  -o, --outdir DIR  输出目录，默认自动生成
  -f, --force       覆盖已有输出目录
  --bridge-url URL  bridge 地址，默认 http://127.0.0.1:18890
  --bridge-port PORT bridge 端口（替代完整 URL）
  -h, --help        显示帮助
HELP
  exit 0
}

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage;;
    --start) SEGMENT_START="$2"; shift 2;;
    --duration) SEGMENT_DURATION="$2"; shift 2;;
    --end) SEGMENT_END="$2"; shift 2;;
    --model) ASR_MODEL="$2"; shift 2;;
    --language) ASR_LANGUAGE="$2"; shift 2;;
    -o|--outdir) OUTDIR="$2"; shift 2;;
    -f|--force) FORCE=true; shift;;
    --bridge-url) BRIDGE_URL="$2"; shift 2;;
    --bridge-port) BRIDGE_PORT="$2"; shift 2;;
    --) shift; POSITIONAL+=("$@"); break;;
    -*) err "未知选项: $1"; usage;;
    *) POSITIONAL+=("$1"); shift;;
  esac
done
set -- "${POSITIONAL[@]}"

VIDEO="${1:-}"

if [ -z "$VIDEO" ]; then
  err "请指定视频路径"
  usage
fi

if [ ! -f "$VIDEO" ]; then
  err "文件不存在: $VIDEO"
  exit 1
fi

# 处理 bridge 端口
if [ -n "$BRIDGE_PORT" ]; then
  BRIDGE_URL="http://127.0.0.1:${BRIDGE_PORT}"
fi
ASR_URL="${BRIDGE_URL}/v1/audio/transcriptions"

# 参数互斥检查
if [ -n "$SEGMENT_DURATION" ] && [ -n "$SEGMENT_END" ]; then
  err "--duration 和 --end 不能同时使用，请二选一"
  exit 1
fi

# ---------- 获取视频信息 ----------
FULL_VIDEO_PATH=$(realpath "$VIDEO")
TOTAL_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FULL_VIDEO_PATH" 2>/dev/null || echo 0)
TOTAL_DURATION_INT=${TOTAL_DURATION%.*}

# 检查是否有音频轨
HAS_AUDIO=$(ffprobe -v error -select_streams a:0 -show_entries stream=index -of default=noprint_wrappers=1:nokey=1 "$FULL_VIDEO_PATH" 2>/dev/null || echo "")
if [ -z "$HAS_AUDIO" ]; then
  err "该视频没有音频轨，无法转写: $FULL_VIDEO_PATH"
  exit 1
fi

info "视频: $FULL_VIDEO_PATH"
info "总时长: ${TOTAL_DURATION_INT}s"

# ---------- 解析片段 ----------
SEGMENT_START_SEC=0
if [ -n "$SEGMENT_START" ]; then
  SEGMENT_START_SEC=$(to_seconds "$SEGMENT_START")
  if [ -z "$SEGMENT_START_SEC" ]; then
    err "无法解析 --start 值: $SEGMENT_START"
    exit 1
  fi
fi

if [ -n "$SEGMENT_END" ]; then
  _end_sec=$(to_seconds "$SEGMENT_END")
  [ -z "$_end_sec" ] && { err "无法解析 --end 值: $SEGMENT_END"; exit 1; }
  SEGMENT_DURATION_SEC=$(( _end_sec - SEGMENT_START_SEC ))
  [ "$SEGMENT_DURATION_SEC" -le 0 ] && { err "结束位置须在起始之后"; exit 1; }
elif [ -n "$SEGMENT_DURATION" ]; then
  SEGMENT_DURATION_SEC=$(to_seconds "$SEGMENT_DURATION")
  [ -z "$SEGMENT_DURATION_SEC" ] && { err "无法解析 --duration 值: $SEGMENT_DURATION"; exit 1; }
else
  SEGMENT_DURATION_SEC=$(( TOTAL_DURATION_INT - SEGMENT_START_SEC ))
fi

MAX_END=$(( SEGMENT_START_SEC + SEGMENT_DURATION_SEC ))
if [ "$MAX_END" -gt "$TOTAL_DURATION_INT" ] 2>/dev/null; then
  SEGMENT_DURATION_SEC=$(( TOTAL_DURATION_INT - SEGMENT_START_SEC ))
  warn "片段截断到视频末尾"
fi

SEGMENT_START_FMT=$(fmt_time $SEGMENT_START_SEC)
SEGMENT_END_FMT=$(fmt_time $((SEGMENT_START_SEC + SEGMENT_DURATION_SEC)))

info "片段: ${SEGMENT_START_FMT} → ${SEGMENT_END_FMT}（${SEGMENT_DURATION_SEC}s）"

# ---------- 输出目录 ----------
if [ -z "$OUTDIR" ]; then
  BASENAME=$(basename "$VIDEO")
  BASENAME="${BASENAME%.*}"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  OUTDIR="/mnt/data/openclaw/transcribe-jobs/${BASENAME}_${TIMESTAMP}"
fi

if [ -d "$OUTDIR" ]; then
  if [ "$FORCE" = true ]; then
    rm -rf "$OUTDIR"
    info "覆盖已有目录: $OUTDIR"
  else
    # 目录已存在但不强制覆盖：分析是否可复用（检查 audio 子目录）
    if [ -f "${OUTDIR}/audio/original.wav" ] || [ -f "${OUTDIR}/transcript.txt" ]; then
      info "目录已存在，复用已有输出: $OUTDIR"
      # 只创建缺失的子目录
      mkdir -p "${OUTDIR}/audio"
    else
      info "目录已存在，其中不含音频转写产物，将继续写入: $OUTDIR"
      mkdir -p "${OUTDIR}/audio"
    fi
  fi
fi

mkdir -p "$OUTDIR/audio"

# ---------- 1. 提取音频 ----------
AUDIO_WAV="${OUTDIR}/audio/original.wav"
AUDIO_MP3="${OUTDIR}/audio/original.mp3"

info "提取音频..."

if [ "$SEGMENT_START_SEC" -gt 0 ] || [ "$SEGMENT_DURATION_SEC" -lt "$TOTAL_DURATION_INT" ]; then
  ffmpeg -ss "$SEGMENT_START_FMT" -i "$FULL_VIDEO_PATH" \
    -t "$SEGMENT_DURATION_SEC" \
    -vn -acodec pcm_s16le -ar 16000 -ac 1 \
    -y "$AUDIO_WAV" 2>/dev/null
else
  ffmpeg -i "$FULL_VIDEO_PATH" \
    -vn -acodec pcm_s16le -ar 16000 -ac 1 \
    -y "$AUDIO_WAV" 2>/dev/null
fi

WAV_SIZE=$(stat -c%s "$AUDIO_WAV" 2>/dev/null || echo 0)
ok "音频提取完成: ${AUDIO_WAV} ($(( WAV_SIZE / 1024 )) KB)"

# 也生成一份 MP3（可听版本）
ffmpeg -y -i "$AUDIO_WAV" -acodec libmp3lame -b:a 64k "$AUDIO_MP3" 2>/dev/null
MP3_SIZE=$(stat -c%s "$AUDIO_MP3" 2>/dev/null || echo 0)
ok "MP3 版本: ${AUDIO_MP3} ($(( MP3_SIZE / 1024 )) KB)"

# ---------- 2. 检查 bridge ----------
info "检查 NVIDIA Audio Bridge..."
BRIDGE_HEALTH=$(curl -s --max-time 5 "${BRIDGE_URL}/health" 2>/dev/null || echo "UNREACHABLE")
if echo "$BRIDGE_HEALTH" | grep -q '"ok": true'; then
  ok "Bridge 运行正常: ${BRIDGE_URL}"
else
  warn "Bridge 似乎不可达 (${BRIDGE_URL})，尝试调用 ASR 端点..."
  # 不直接退出，尝试调 ASR 时会明确报错
fi

# ---------- 3. 调用 ASR ----------
info "调用 ASR (${ASR_URL})..."
if [ -n "$ASR_MODEL" ]; then
  info "指定模型: $ASR_MODEL"
  CURL_EXTRA="-F model=${ASR_MODEL}"
else
  CURL_EXTRA=""
fi

ASR_RESULT_FILE="${OUTDIR}/transcript.json"

if ! curl -s --max-time 300 -X POST "${ASR_URL}" \
  -F "file=@${AUDIO_WAV}" \
  ${CURL_EXTRA} \
  -F "language=${ASR_LANGUAGE}" \
  -F "response_format=verbose_json" \
  > "$ASR_RESULT_FILE" 2>/dev/null; then
  err "ASR 调用失败（curl 错误）"
  rm -f "$ASR_RESULT_FILE"
  exit 1
fi

# 检查结果是否包含错误
if grep -q '"detail"' "$ASR_RESULT_FILE" 2>/dev/null; then
  DETAIL=$(grep -oP '"detail":\s*"[^"]*"' "$ASR_RESULT_FILE" | head -1)
  err "ASR 返回错误: $DETAIL"
  exit 1
fi

# 提取文本（用 python3 安全解析 JSON，避免 grep 误匹配 segments 内的 text 字段）
TRANSCRIPT_TEXT=$(python3 -c "
import json, sys
try:
    with open('$ASR_RESULT_FILE') as f:
        d = json.load(f)
    print(d.get('text', '') or '')
except Exception as e:
    print('', end='')
" 2>/dev/null || echo "")
MODEL_USED=$(python3 -c "
import json, sys
try:
    with open('$ASR_RESULT_FILE') as f:
        d = json.load(f)
    print(d.get('model_used', d.get('model', 'unknown')) or 'unknown')
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")

if [ -z "$TRANSCRIPT_TEXT" ]; then
  warn "转写结果为空（可能音频无人声）"
else
  ok "转写完成，模型: $MODEL_USED"
fi

# ---------- 4. 生成 transcript.txt ----------
echo "$TRANSCRIPT_TEXT" > "${OUTDIR}/transcript.txt"
ok "文本保存: ${OUTDIR}/transcript.txt"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  转写结果"
echo "═══════════════════════════════════════════════════════"
echo ""
if [ -n "$TRANSCRIPT_TEXT" ]; then
  echo "  「${TRANSCRIPT_TEXT}」"
else
  echo "  （无识别结果）"
fi
echo ""

# ---------- 5. 生成 manifest.json ----------
cat > "${OUTDIR}/gen-manifest.py" << 'PYEOF'
import json, os
OUTDIR = os.environ.get('GEN_OUTDIR', '')
manifest = {
    'job': {
        'type': 'audio-transcription',
        'video': os.environ.get('GEN_VIDEO', ''),
        'totalDurationSec': int(os.environ.get('GEN_TOTAL_DURATION', '0')),
        'segment': {
            'startSec': int(os.environ.get('GEN_SEG_START', '0')),
            'startTime': os.environ.get('GEN_SEG_START_FMT', ''),
            'endSec': int(os.environ.get('GEN_SEG_END', '0')),
            'endTime': os.environ.get('GEN_SEG_END_FMT', ''),
            'durationSec': int(os.environ.get('GEN_DURATION', '0')),
        },
        'params': {
            'language': os.environ.get('GEN_LANG', ''),
            'model': os.environ.get('GEN_MODEL', 'auto'),
            'bridge': os.environ.get('GEN_BRIDGE', ''),
        },
    },
    'transcription': {
        'text': os.environ.get('GEN_TEXT', ''),
        'modelUsed': os.environ.get('GEN_MODEL_USED', 'unknown'),
        'language': os.environ.get('GEN_LANG', ''),
    },
    'files': {
        'wav': os.environ.get('GEN_WAV', ''),
        'mp3': os.environ.get('GEN_MP3', ''),
        'transcriptText': os.environ.get('GEN_TXT', ''),
        'transcriptJson': os.environ.get('GEN_JSON', ''),
    },
    'outputDir': OUTDIR,
    'generatedAt': os.environ.get('GEN_TIME', ''),
}
with open(os.path.join(OUTDIR, 'manifest.json'), 'w') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
PYEOF

GEN_OUTDIR="${OUTDIR}" \
GEN_VIDEO="${FULL_VIDEO_PATH}" \
GEN_TOTAL_DURATION="${TOTAL_DURATION_INT}" \
GEN_SEG_START="${SEGMENT_START_SEC}" \
GEN_SEG_START_FMT="${SEGMENT_START_FMT}" \
GEN_SEG_END="$((SEGMENT_START_SEC + SEGMENT_DURATION_SEC))" \
GEN_SEG_END_FMT="${SEGMENT_END_FMT}" \
GEN_DURATION="${SEGMENT_DURATION_SEC}" \
GEN_LANG="${ASR_LANGUAGE}" \
GEN_MODEL="${ASR_MODEL:-auto}" \
GEN_BRIDGE="${BRIDGE_URL}" \
GEN_TEXT="${TRANSCRIPT_TEXT}" \
GEN_MODEL_USED="${MODEL_USED}" \
GEN_WAV="${AUDIO_WAV}" \
GEN_MP3="${AUDIO_MP3}" \
GEN_TXT="${OUTDIR}/transcript.txt" \
GEN_JSON="${ASR_RESULT_FILE}" \
GEN_TIME="$(date -u +%Y%m%dT%H%M%SZ)" \
python3 "${OUTDIR}/gen-manifest.py" 2>/dev/null

rm -f "${OUTDIR}/gen-manifest.py"

ok "manifest 已生成: ${OUTDIR}/manifest.json"

# ---------- 6. 最终输出 ----------
echo ""
echo "═══════════════════════════════════════════════"
echo -e "  ${GREEN}转写完成!${NC}"
echo "═══════════════════════════════════════════════"
echo ""
echo "  输出目录:    $OUTDIR"
echo "    ├── audio/original.wav        (原始音频 16kHz 16bit mono)"
echo "    ├── audio/original.mp3        (可听版本)"
echo "    ├── transcript.txt            (转写纯文本)"
echo "    ├── transcript.json           (转写完整 JSON)"
echo "    └── manifest.json"
echo ""
echo "  转写文本:"
echo "    ${TRANSCRIPT_TEXT:-（无识别结果）}"
echo ""

# 建议
if [ -z "$TRANSCRIPT_TEXT" ]; then
  echo "💡 提示：如果音频中人声微弱（背景音乐干扰），可尝试："
  echo "   1. 用音频软件放大音量后重新提交"
  echo "   2. 指定更精确的片段范围（--start / --duration）"
  echo ""
fi
