#!/usr/bin/env bash
# ============================================================================
# transcribe-video-audio-local.sh — 本地 faster-whisper 转写（带真实时间戳）
#
# 用途：从视频提取音频，通过本地 faster-whisper 模型做语音转写。
#       输出带真实 segments / words 时间戳的 JSON，不依赖 NVIDIA ASR bridge。
#
# 依赖：
#   - ffmpeg（系统安装）
#   - faster-whisper venv 在 /mnt/data/openclaw/faster-whisper-venv/
#   - 模型文件在 /mnt/data/openclaw/whisper-models/faster-whisper-{tiny,small,medium}/
#
# 用法：
#   bash scripts/transcribe-video-audio-local.sh <视频路径> [选项]
#
# 选项：
#   --start TIME          片段起始位置（HH:MM:SS 或秒数），默认 00:00:00
#   --duration SEC         片段时长（秒），与 --end 二选一
#   --end TIME             片段结束位置（HH:MM:SS 或秒数），与 --duration 二选一
#   --model MODEL          本地模型：tiny|base|small|medium|large-v3，默认 small
#   --language LANG        语言代码（zh / en 等）。默认自动检测
#   -o, --outdir DIR       输出目录，默认自动生成
#   -f, --force            覆盖已有输出目录
#   -h, --help             显示帮助
#
# 输出目录结构：
#   <outdir>/
#     audio/                ← 提取的音频文件
#       original.wav         ← WAV 格式音频
#       original.mp3         ← MP3 格式音频（可听）
#     transcript.txt         ← 转写纯文本
#     transcript.json        ← 转写完整 JSON（含 segments / words 时间戳）
#     manifest.json          ← 作业元数据
#
# 示例：
#   bash scripts/transcribe-video-audio-local.sh test.mp4
#   bash scripts/transcribe-video-audio-local.sh test.mp4 --model tiny --language zh
#   bash scripts/transcribe-video-audio-local.sh test.mp4 --start 5 --duration 10
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
LOCAL_MODEL="base"
LOCAL_LANGUAGE=""   # 空 = 自动检测
OUTDIR=""
FORCE=false

SEGMENT_START=""
SEGMENT_DURATION=""
SEGMENT_END=""

# ---------- 路径 ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="${HOME}/.openclaw/workspace"
VENV_DIR="/mnt/data/openclaw/faster-whisper-venv"
MODELS_DIR="/mnt/data/openclaw/whisper-models"
HF_CACHE_DIR="/mnt/data/openclaw/hf-cache"

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
transcribe-video-audio-local.sh — 本地 faster-whisper 转写（带真实时间戳）

用法:
  bash scripts/transcribe-video-audio-local.sh <视频路径> [选项]

选项:
  --start TIME      片段起始位置（HH:MM:SS 或秒数），默认 00:00:00
  --duration SEC    片段时长（秒），与 --end 二选一
  --end TIME        片段结束位置（HH:MM:SS 或秒数），与 --duration 二选一
  --model MODEL     本地模型：tiny|base|small|medium|large-v3，默认 small
  --language LANG   语言代码（zh / en 等）。默认自动检测
  -o, --outdir DIR  输出目录，默认自动生成
  -f, --force       覆盖已有输出目录
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
    --model) LOCAL_MODEL="$2"; shift 2;;
    --language) LOCAL_LANGUAGE="$2"; shift 2;;
    -o|--outdir) OUTDIR="$2"; shift 2;;
    -f|--force) FORCE=true; shift;;
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

# ---------- 语言代码规范化 ----------
# faster-whisper 不识别 zh-CN / zh-TW 等带区域码的格式，需要截断到标准 BCP-47
normalize_language() {
  local lang="$1"
  [[ "$lang" =~ ^([a-z]{2,3}) ]] && echo "${BASH_REMATCH[1]}" || echo "$lang"
}

if [ -n "$LOCAL_LANGUAGE" ]; then
  # 备份原始值供日志用
  LOCAL_LANGUAGE_RAW="$LOCAL_LANGUAGE"
  LOCAL_LANGUAGE="$(normalize_language "$LOCAL_LANGUAGE")"
  if [ "$LOCAL_LANGUAGE_RAW" != "$LOCAL_LANGUAGE" ]; then
    info "语言代码规范化: ${LOCAL_LANGUAGE_RAW} → ${LOCAL_LANGUAGE}"
  fi
fi

# ---------- 模型可用性检查 ----------
MODEL_DIR_NAME="faster-whisper-${LOCAL_MODEL}"
MODEL_PATH="${MODELS_DIR}/${MODEL_DIR_NAME}"

if [ ! -f "${MODEL_PATH}/model.bin" ]; then
  err "本地模型未找到: ${MODEL_PATH}/model.bin"
  err "请先下载模型。可用命令："
  err "  source ${VENV_DIR}/bin/activate"
  err "  python3 -c \"from faster_whisper import WhisperModel; WhisperModel('${LOCAL_MODEL}', device='cpu', download_root='${MODELS_DIR}')\""
  err ""
  err "或手动下载到: ${MODEL_PATH}/"
  err "  https://hf-mirror.com/Systran/${MODEL_DIR_NAME}/resolve/main/model.bin"
  exit 1
fi

# ---------- venv 检查 ----------
if [ ! -d "$VENV_DIR" ]; then
  err "faster-whisper venv 未找到: $VENV_DIR"
  err "请先运行: uv venv '${VENV_DIR}' && source '${VENV_DIR}/bin/activate' && uv pip install faster-whisper"
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
info "本地模型: ${LOCAL_MODEL}（模型路径: ${MODEL_PATH}）"

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
  OUTDIR="/mnt/data/openclaw/transcribe-local-jobs/${BASENAME}_${TIMESTAMP}"
fi

if [ -d "$OUTDIR" ]; then
  if [ "$FORCE" = true ]; then
    rm -rf "$OUTDIR"
    info "覆盖已有目录: $OUTDIR"
  else
    if [ -f "${OUTDIR}/audio/original.wav" ] || [ -f "${OUTDIR}/transcript.txt" ]; then
      info "目录已存在，复用已有输出: $OUTDIR"
      mkdir -p "${OUTDIR}/audio"
    else
      info "目录已存在，将继续写入: $OUTDIR"
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

# 也生成一份 MP3
ffmpeg -y -i "$AUDIO_WAV" -acodec libmp3lame -b:a 64k "$AUDIO_MP3" 2>/dev/null
MP3_SIZE=$(stat -c%s "$AUDIO_MP3" 2>/dev/null || echo 0)
ok "MP3 版本: ${AUDIO_MP3} ($(( MP3_SIZE / 1024 )) KB)"

# ---------- 2. 调用 faster-whisper ----------
info "调用 faster-whisper 本地模型 ${LOCAL_MODEL}..."

# 组装语言参数
LANG_ARG=""
if [ -n "$LOCAL_LANGUAGE" ]; then
  LANG_ARG="--language ${LOCAL_LANGUAGE}"
fi

ASR_RESULT_FILE="${OUTDIR}/transcript.json"

# 用 venv 内的 python3 跑
source "${VENV_DIR}/bin/activate"

# 设置 HF 缓存路径
export HF_HOME="${HF_CACHE_DIR}"

python3 - "$AUDIO_WAV" "$OUTDIR" "$LOCAL_MODEL" "$MODELS_DIR" "$LOCAL_LANGUAGE" "$SEGMENT_START_SEC" <<'PYEOF'
import json, os, sys
from pathlib import Path

segment_start_offset = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
from datetime import datetime, timezone

audio_path = sys.argv[1]
outdir = Path(sys.argv[2])
model_name = sys.argv[3]
models_dir = sys.argv[4]
language = sys.argv[5] or None

# 获取模型路径
model_path = os.path.join(models_dir, f"faster-whisper-{model_name}")

from faster_whisper import WhisperModel

# 加载模型
# 对于 tiny/base: compute_type='int8' 在 CPU 上稳定
# 对于 small+ : 用 'int8_float32' 在 CPU 上运行
compute_type = 'int8'
if model_name in ('small', 'medium', 'large-v3'):
    compute_type = 'int8_float32'

model = WhisperModel(
    model_path,
    device='cpu',
    compute_type=compute_type,
    download_root=models_dir,
)

# 转写
# word_timestamps=True 是拿到词级时间戳的关键
segments, info = model.transcribe(
    audio_path,
    beam_size=5,
    word_timestamps=True,
    language=language,
    vad_filter=False,
)

# 收集结果
detected_language = info.language
detected_prob = info.language_probability
transcription_text = ""
all_segments = []
all_words = []

for seg in segments:
    seg_text = seg.text.strip()
    transcription_text += seg_text + " "

    seg_data = {
        "start": round(seg.start + segment_start_offset, 3),
        "end": round(seg.end + segment_start_offset, 3),
        "text": seg_text,
        "id": seg.id,
    }

    # 词级时间戳
    seg_words = []
    if seg.words:
        for w in seg.words:
            word_data = {
                "word": w.word.strip(),
                "start": round(w.start + segment_start_offset, 3),
                "end": round(w.end + segment_start_offset, 3),
                "probability": round(w.probability, 3),
            }
            seg_words.append(word_data)
            all_words.append(word_data)

    seg_data["words"] = seg_words
    all_segments.append(seg_data)

transcription_text = transcription_text.strip()

result = {
    "text": transcription_text,
    "language": detected_language,
    "language_probability": round(detected_prob, 3),
    "model_used": f"faster-whisper/{model_name}",
    "segments": all_segments,
    "words": all_words,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

with open(str(outdir / "transcript.json"), "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# 也写文本
with open(str(outdir / "transcript.txt"), "w") as f:
    f.write(transcription_text)
    f.write("\n")

print(f"DETECTED_LANG={detected_language}")
print(f"DETECTED_PROB={detected_prob}")
print(f"SEGMENTS={len(all_segments)}")
print(f"WORDS={len(all_words)}")

# 打印前 3 个 segment 时间戳做验证
print("---TIMESTAMP_CHECK---")
for i, seg in enumerate(all_segments[:3]):
    print(f"  seg[{i}]: {seg['start']:.3f}s -> {seg['end']:.3f}s | {seg['text'][:40]}")
if all_words:
    print(f"  words: first={all_words[0]}, last={all_words[-1]}")
print("---TIMESTAMP_CHECK_END---")
PYEOF

PYEXIT=$?
deactivate 2>/dev/null || true

if [ "$PYEXIT" -ne 0 ]; then
  err "faster-whisper 转写失败（退出码: $PYEXIT）"
  exit 1
fi

# ---------- 3. 验证和展示结果 ----------
# 从 JSON 提取关键信息
HAS_TIMESTAMPS=$(python3 -c "
import json
with open('$ASR_RESULT_FILE') as f:
    d = json.load(f)
segments = d.get('segments', [])
words = d.get('words', [])
has_seg = bool(segments) and segments[0].get('start') is not None
has_word = bool(words) and words[0].get('start') is not None
if has_word:
    print('word_timestamps')
elif has_seg:
    print('segment_timestamps')
else:
    print('coarse')
" 2>/dev/null || echo "unknown")

TRANSCRIPT_TEXT=$(python3 -c "
import json
try:
    with open('$ASR_RESULT_FILE') as f:
        d = json.load(f)
    print(d.get('text', '') or '')
except Exception:
    print('')
" 2>/dev/null || echo "")

TIMESTAMP_INFO=""
if [ "$HAS_TIMESTAMPS" = "word_timestamps" ]; then
  TIMESTAMP_INFO="${GREEN}词级时间戳${NC}"
elif [ "$HAS_TIMESTAMPS" = "segment_timestamps" ]; then
  TIMESTAMP_INFO="${YELLOW}段级时间戳${NC}"
else
  TIMESTAMP_INFO="${RED}无时间戳（粗对齐）${NC}"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  本地转写完成"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  模型:          faster-whisper/${LOCAL_MODEL}"
echo "  时间戳精度:    ${TIMESTAMP_INFO}"
echo ""
if [ -n "$TRANSCRIPT_TEXT" ]; then
  echo "  转写文本:"
  echo "    「${TRANSCRIPT_TEXT}」"
fi
echo ""

# ---------- 4. 验证时间戳 ----------
python3 -c "
import json

with open('$ASR_RESULT_FILE') as f:
    d = json.load(f)

segments = d.get('segments', [])
words = d.get('words', [])

print('═══════════════════════════════════════════════════════')
print('  timestamp 实际值验证')
print('═══════════════════════════════════════════════════════')
print()
print(f'  总 segments: {len(segments)}')
print(f'  总 words: {len(words)}')
print()

if segments:
    print('  前 5 个 segments:')
    for seg in segments[:5]:
        s = seg.get('start', '?')
        e = seg.get('end', '?')
        t = seg.get('text', '')[:50]
        print(f'    {s:>8.3f}s -> {e:>8.3f}s  {t}')
    print()
    if len(segments) > 5:
        print(f'  ... 还有 {len(segments) - 5} 个 segments')
    print()

if words:
    print('  前 10 个 words:')
    for w in words[:10]:
        s = w.get('start', '?')
        e = w.get('end', '?')
        word = w.get('word', '')
        prob = w.get('probability', '')
        print(f'    {s:>8.3f}s -> {e:>8.3f}s  [{prob:.3f}]  {word}')
    print()
    if len(words) > 10:
        print(f'  ... 还有 {len(words) - 10} 个 words')
    print()

# 验证：每个 word 的 start/end 是否在对应 segment 范围内
if segments and words:
    mismatches = 0
    for i, w in enumerate(words):
        ws = w.get('start', 0)
        we = w.get('end', 0)
        # 找到包含这个 word 的 segment
        in_seg = any(
            s.get('start', 0) <= ws and s.get('end', 0) >= we
            for s in segments if s.get('words')
        )
        if not in_seg:
            mismatches += 1
    if mismatches:
        print(f'  ⚠️  {mismatches}/{len(words)} words 不在任何 segment 范围内')
    else:
        print(f'  ✅ 所有 words 的时间戳在对应 segments 范围内')
    print()

print(f'  整体音频时长: {sum(s.get(\"end\", 0) - s.get(\"start\", 0) for s in segments):.1f}s')
print()
" 2>/dev/null

# ---------- 5. 生成 manifest.json ----------
cat > "${OUTDIR}/gen-manifest.py" << 'PYEOF'
import json, os
OUTDIR = os.environ.get('GEN_OUTDIR', '')
with open(os.path.join(OUTDIR, 'transcript.json')) as f:
    d = json.load(f)
segments = d.get('segments', [])
words = d.get('words', [])
manifest = {
    'job': {
        'type': 'audio-transcription',
        'engine': 'faster-whisper',
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
            'language': os.environ.get('GEN_LANG', 'auto'),
            'model': os.environ.get('GEN_MODEL', ''),
        },
    },
    'transcription': {
        'text': d.get('text', ''),
        'modelUsed': d.get('model_used', 'faster-whisper'),
        'language': d.get('language', ''),
        'languageProbability': d.get('language_probability', 0),
        'numSegments': len(segments),
        'numWords': len(words),
        'timestampPrecision': 'word_timestamps' if words and words[0].get('start') is not None else ('segment_timestamps' if segments and segments[0].get('start') is not None else 'coarse'),
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
GEN_LANG="${LOCAL_LANGUAGE:-auto}" \
GEN_MODEL="faster-whisper/${LOCAL_MODEL}" \
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
echo -e "  ${GREEN}本地转写完成!${NC}"
echo "═══════════════════════════════════════════════"
echo ""
echo "  输出目录:    $OUTDIR"
echo "    ├── audio/original.wav        (原始音频 16kHz 16bit mono)"
echo "    ├── audio/original.mp3        (可听版本)"
echo "    ├── transcript.txt            (转写纯文本)"
echo "    ├── transcript.json           (转写完整 JSON，含 segments + words 时间戳)"
echo "    └── manifest.json"
echo ""
echo "  转写文本:"
echo "    ${TRANSCRIPT_TEXT:-（无识别结果）}"
echo ""
