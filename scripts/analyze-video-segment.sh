#!/usr/bin/env bash
# ============================================================================
# analyze-video-segment.sh — 视频片段抽帧 + 代表帧选取 + workspace staging
#
# 用途：从视频（或视频片段）抽帧，挑选代表帧供视觉模型做画面理解。
#       支持精确指定起止片段，自动做 workspace staging 让 image 工具可直接读取。
#
# 依赖：
#   - ffmpeg / ffprobe（系统安装）
#   - scripts/extract-frames.sh（同目录下的抽帧脚本）
#
# 用法：
#   bash scripts/analyze-video-segment.sh <视频路径> [选项]
#
# 选项：
#   -i, --interval SEC      抽帧间隔（秒），默认 5
#   -m, --max-frames N      最大代表帧数量，默认 3（image 工具更稳定）
#   -o, --outdir DIR        结果输出目录，默认自动生成
#   -f, --force             覆盖已有输出目录
#   --start TIME             片段起始位置。格式：HH:MM:SS 或秒数。默认 00:00:00
#   --duration SEC           片段时长（秒）。与 --end 二选一
#   --end TIME               片段结束位置。格式：HH:MM:SS 或秒数。与 --duration 二选一
#   --no-staging             不做 workspace staging（只保留主输出目录）
#   --no-framelist           不生成帧清单帧摘要（仅做抽帧）
#   --with-audio             同时提取音频 + ASR 转写（需 NVIDIA Audio Bridge 运行）
#   --asr-language LANG      ASR 语言，默认 zh-CN
#   -h, --help               显示帮助
#
# 输出目录结构（主输出，/mnt/data/ 下）：
#   <outdir>/
#     frames/                 ← 抽帧图片
#     representative/         ← 选取的代表帧
#     audio/                  ← 提取的音频（仅 --with-audio）
#     transcript.txt          ← ASR 转写文本（仅 --with-audio）
#     transcript.json         ← ASR 转写 JSON（仅 --with-audio）
#     frame-list.txt          ← 完整帧清单
#     summary.md              ← 视频分析摘要（含画面 + 音频信息）
#     manifest.json           ← 元数据 + workspace staging 路径
#
# workspace staging（~/.openclaw/workspace/tmp/video-analysis/<job>/）：
#     representative/         ← 缩放后的代表帧（image 工具可直接读取）
#     manifest.json / analysis-input.md
#
# 示例：
#   bash scripts/analyze-video-segment.sh test.mp4
#   bash scripts/analyze-video-segment.sh test.mp4 --interval 3 --max-frames 5
#   bash scripts/analyze-video-segment.sh test.mp4 --start 5 --duration 10
#   bash scripts/analyze-video-segment.sh test.mp4 --start 00:01:30 --end 00:02:00
#   bash scripts/analyze-video-segment.sh test.mp4 --start 10 --duration 8 --max-frames 4
#   bash scripts/analyze-video-segment.sh test.mp4 --with-audio --asr-language zh-CN
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
INTERVAL=5
MAX_FRAMES=3        # 默认 3（更稳定，对 image 友好）
OUTDIR=""
FORCE=false
GEN_FRAMELIST=true
DO_STAGING=true
DO_AUDIO=false
DO_TIMELINE=false
ASR_LANGUAGE="zh-CN"
TRANSCRIBE_MODEL=""
TRANSCRIBE_ENGINE="bridge"   # bridge|local
SEGMENT_START=""
SEGMENT_DURATION=""
SEGMENT_END=""

# ---------- 路径 ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACT_SCRIPT="${SCRIPT_DIR}/extract-frames.sh"
WORKSPACE_DIR="${HOME}/.openclaw/workspace"

# ---------- 辅助函数 ----------
# 将 HH:MM:SS 或纯秒数统一转为秒数
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

# 将秒格式化为 HH:MM:SS
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
analyze-video-segment.sh — 视频片段抽帧 + 代表帧选取 + workspace staging

用法:
  bash scripts/analyze-video-segment.sh <视频路径> [选项]

选项:
  -i, --interval SEC      抽帧间隔（秒），默认 5
  -m, --max-frames N      最大代表帧数量，默认 3
  -o, --outdir DIR        结果输出目录，默认自动生成
  -f, --force             覆盖已有输出目录
  --start TIME             片段起始位置（HH:MM:SS 或秒数），默认 00:00:00
  --duration SEC           片段时长（秒），与 --end 二选一
  --end TIME               片段结束位置（HH:MM:SS 或秒数），与 --duration 二选一
  --no-staging             不做 workspace staging
  --no-framelist           不生成帧清单
  --timeline               生成时间轴切片音画同步分析（timeline.md + timeline.json）
  --transcribe-model MODEL 本地引擎模型（tiny|base|small|medium），默认 base
  -h, --help               显示帮助

示例:
  bash scripts/analyze-video-segment.sh test.mp4
  bash scripts/analyze-video-segment.sh test.mp4 -i 3 -m 5
  bash scripts/analyze-video-segment.sh test.mp4 --start 5 --duration 10
  bash scripts/analyze-video-segment.sh test.mp4 --start 00:01:30 --end 00:02:00
HELP
  exit 0
}

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage;;
    -i|--interval) INTERVAL="$2"; shift 2;;
    -m|--max-frames) MAX_FRAMES="$2"; shift 2;;
    -o|--outdir) OUTDIR="$2"; shift 2;;
    -f|--force) FORCE=true; shift;;
    --start) SEGMENT_START="$2"; shift 2;;
    --duration) SEGMENT_DURATION="$2"; shift 2;;
    --end) SEGMENT_END="$2"; shift 2;;
    --no-staging) DO_STAGING=false; shift;;
    --no-framelist) GEN_FRAMELIST=false; shift;;
    --timeline) DO_TIMELINE=true; shift;;
    --with-audio) DO_AUDIO=true; shift;;
    --transcribe-engine) TRANSCRIBE_ENGINE="$2"; shift 2;;
    --transcribe-model) TRANSCRIBE_MODEL="$2"; shift 2;;
    --asr-language) ASR_LANGUAGE="$2"; shift 2;;
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

if [ ! -f "$EXTRACT_SCRIPT" ]; then
  err "找不到抽帧脚本: $EXTRACT_SCRIPT"
  exit 1
fi

# 参数互斥检查
if [ -n "$SEGMENT_DURATION" ] && [ -n "$SEGMENT_END" ]; then
  err "--duration 和 --end 不能同时使用，请二选一"
  exit 1
fi

# ---------- 解析片段参数 ----------
FULL_VIDEO_PATH=$(realpath "$VIDEO")
# 总时长（用于验证片段范围）
TOTAL_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FULL_VIDEO_PATH" 2>/dev/null || echo 0)
TOTAL_DURATION_INT=${TOTAL_DURATION%.*}

SEGMENT_START_SEC=0
if [ -n "$SEGMENT_START" ]; then
  SEGMENT_START_SEC=$(to_seconds "$SEGMENT_START")
  if [ -z "$SEGMENT_START_SEC" ]; then
    err "无法解析 --start 值: $SEGMENT_START（支持 HH:MM:SS 或秒数）"
    exit 1
  fi
  if [ "$SEGMENT_START_SEC" -ge "$TOTAL_DURATION_INT" ] 2>/dev/null; then
    err "--start 超出视频时长（${TOTAL_DURATION_INT}s）: ${SEGMENT_START_SEC}s"
    exit 1
  fi
fi

SEGMENT_DURATION_SEC=""
if [ -n "$SEGMENT_DURATION" ]; then
  SEGMENT_DURATION_SEC=$(to_seconds "$SEGMENT_DURATION")
  if [ -z "$SEGMENT_DURATION_SEC" ]; then
    err "无法解析 --duration 值: $SEGMENT_DURATION"
    exit 1
  fi
fi

if [ -n "$SEGMENT_END" ]; then
  _end_sec=$(to_seconds "$SEGMENT_END")
  if [ -z "$_end_sec" ]; then
    err "无法解析 --end 值: $SEGMENT_END"
    exit 1
  fi
  SEGMENT_DURATION_SEC=$(( _end_sec - SEGMENT_START_SEC ))
  if [ "$SEGMENT_DURATION_SEC" -le 0 ]; then
    err "片段结束位置必须在起始位置之后"
    exit 1
  fi
  unset _end_sec
fi

# 如果没指定片段，默认整段
if [ -z "$SEGMENT_DURATION_SEC" ]; then
  SEGMENT_DURATION_SEC=$(( TOTAL_DURATION_INT - SEGMENT_START_SEC ))
fi

# 确保不超出视频范围
MAX_END=$(( SEGMENT_START_SEC + SEGMENT_DURATION_SEC ))
if [ "$MAX_END" -gt "$TOTAL_DURATION_INT" ] 2>/dev/null; then
  SEGMENT_DURATION_SEC=$(( TOTAL_DURATION_INT - SEGMENT_START_SEC ))
  warn "片段超出视频范围，截断到视频末尾（${SEGMENT_DURATION_SEC}s）"
fi

# ---------- 输出目录 ----------
if [ -z "$OUTDIR" ]; then
  BASENAME=$(basename "$VIDEO")
  BASENAME="${BASENAME%.*}"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  OUTDIR="/mnt/data/openclaw/frame-extract-jobs/${BASENAME}_${TIMESTAMP}"
fi

if [ -d "$OUTDIR" ]; then
  if [ "$FORCE" = true ]; then
    rm -rf "$OUTDIR"
    info "清空已有目录: $OUTDIR"
  else
    err "输出目录已存在: $OUTDIR（使用 -f 覆盖）"
    exit 1
  fi
fi

mkdir -p "$OUTDIR/frames" "$OUTDIR/representative"

# ---------- 1. 获取视频信息 ----------
info "获取视频信息..."
DURATION=$TOTAL_DURATION
WIDTH=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=noprint_wrappers=1:nokey=1 "$FULL_VIDEO_PATH" 2>/dev/null || echo "?")
HEIGHT=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "$FULL_VIDEO_PATH" 2>/dev/null || echo "?")
CODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$FULL_VIDEO_PATH" 2>/dev/null || echo "?")
FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$FULL_VIDEO_PATH" 2>/dev/null || echo "?")

echo "   视频:    $FULL_VIDEO_PATH"
echo "   总时长:  ${TOTAL_DURATION_INT}s"
echo "   片段:    $(fmt_time $SEGMENT_START_SEC) ~ $(fmt_time $((SEGMENT_START_SEC + SEGMENT_DURATION_SEC)))（${SEGMENT_DURATION_SEC}s）"
echo "   分辨率:  ${WIDTH}x${HEIGHT}"
echo "   编码:    $CODEC"
echo "   FPS:     $FPS"
echo "   代表帧上限: ${MAX_FRAMES}"
echo ""

ok "视频信息获取完成"

# ---------- 2. 抽帧（如果指定了片段，用 ffmpeg seek） ----------
info "调用 extract-frames.sh 抽帧（间隔 ${INTERVAL}s）..."

# 策略：如果指定了片段，使用临时裁剪视频
# 这样 extract-frames.sh 不需要改，且片段逻辑集中在这一层
if [ "$SEGMENT_START_SEC" -gt 0 ] || [ "$SEGMENT_DURATION_SEC" -lt "$TOTAL_DURATION_INT" ]; then
  info "使用片段模式：start=$(fmt_time $SEGMENT_START_SEC) duration=${SEGMENT_DURATION_SEC}s"
  # 生成一个临时裁剪视频来实现精确 seek
  TEMP_SEGMENT=$(mktemp /tmp/video-segment-XXXXXX.mp4)
  # 使用 ffmpeg seek + 精确裁剪（关键帧对齐做加速，但这里为精准用 non-seekable）
  ffmpeg -ss "$(fmt_time $SEGMENT_START_SEC)" -i "$FULL_VIDEO_PATH" \
    -t "$SEGMENT_DURATION_SEC" \
    -c:v libx264 -crf 23 -preset fast \
    -an \
    -y "$TEMP_SEGMENT" 2>/dev/null

  # 用裁剪后的视频抽帧
  bash "$EXTRACT_SCRIPT" "$TEMP_SEGMENT" "$INTERVAL" "$OUTDIR/frames"

  # 清理临时视频
  rm -f "$TEMP_SEGMENT"

  # 调整帧列表中的时间戳，使其对应原视频时间
  # extract-frames.sh 生成的时间戳是从 0 开始的（相对于裁剪段）
  # 需要加上 SEGMENT_START_SEC
  if [ -f "$OUTDIR/frames/frame-list.txt" ]; then
    _TMP_LIST=$(mktemp)
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      old_ts=$(echo "$line" | awk '{print $1}')
      fp=$(echo "$line" | awk '{print $2}')
      old_sec=$(to_seconds "$old_ts")
      new_sec=$(( old_sec + SEGMENT_START_SEC ))
      new_ts=$(fmt_time $new_sec)
      echo "$new_ts  $fp" >> "$_TMP_LIST"
    done < "$OUTDIR/frames/frame-list.txt"
    mv "$_TMP_LIST" "$OUTDIR/frames/frame-list.txt"
    ok "帧时间戳已调整（+${SEGMENT_START_SEC}s）"
  fi
else
  info "使用整段模式..."
  bash "$EXTRACT_SCRIPT" "$FULL_VIDEO_PATH" "$INTERVAL" "$OUTDIR/frames"
fi

# 获取实际帧数
FRAME_COUNT=$(find "$OUTDIR/frames" -maxdepth 1 -name 'frame_*.jpg' | wc -l)
ok "抽帧完成，共 ${FRAME_COUNT} 帧"

# ---------- 3. 选择代表帧 ----------
info "选择最多 ${MAX_FRAMES} 帧代表帧..."

# 读帧列表
FRAME_LIST_FILE="$OUTDIR/frames/frame-list.txt"
REAL_FRAMES=()
REAL_TIMESTAMPS=()
if [ -f "$FRAME_LIST_FILE" ]; then
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    TS=$(echo "$line" | awk '{print $1}')
    FP=$(echo "$line" | awk '{print $2}')
    REAL_FRAMES+=("$FP")
    REAL_TIMESTAMPS+=("$TS")
  done < "$FRAME_LIST_FILE"
else
  # fallback: 直接找文件
  while IFS= read -r -d '' f; do
    REAL_FRAMES+=("$f")
  done < <(find "$OUTDIR/frames" -maxdepth 1 -name 'frame_*.jpg' -print0 | sort -z -V)
  for f in "${REAL_FRAMES[@]}"; do
    REAL_TIMESTAMPS+=("?")
  done
fi

ACTUAL_COUNT="${#REAL_FRAMES[@]}"
if [ "$ACTUAL_COUNT" -eq 0 ]; then
  warn "没有帧被抽出，跳过代表帧选择"
else
  SELECTED_COUNT=$(( MAX_FRAMES < ACTUAL_COUNT ? MAX_FRAMES : ACTUAL_COUNT ))
  SELECTED_INDICES=""

  if [ "$ACTUAL_COUNT" -le "$MAX_FRAMES" ]; then
    SELECTED_INDICES=$(seq 0 $((ACTUAL_COUNT - 1)))
  else
    # 均匀选取（保证首尾都在内）
    STEP=$(python3 -c "import math; print(int(($ACTUAL_COUNT - 1) / ($MAX_FRAMES - 1)))" 2>/dev/null || echo 1)
    [ "$STEP" -lt 1 ] && STEP=1
    for i in $(seq 0 "$STEP" $((ACTUAL_COUNT - 1))); do
      SELECTED_INDICES="$SELECTED_INDICES $i"
      if [ "$(echo "$SELECTED_INDICES" | wc -w)" -ge "$MAX_FRAMES" ]; then
        break
      fi
    done
    # 确保末尾帧包含
    LAST_IDX=$((ACTUAL_COUNT - 1))
    if ! echo "$SELECTED_INDICES" | grep -qw "$LAST_IDX"; then
      SELECTED_INDICES="$SELECTED_INDICES $LAST_IDX"
    fi
    # 去重排序
    SELECTED_INDICES=$(echo "$SELECTED_INDICES" | tr ' ' '\n' | sort -un | tr '\n' ' ')
  fi

  # 复制到 representative 目录
  REP_LIST_FILE="$OUTDIR/representative/representative-list.txt"
  : > "$REP_LIST_FILE"

  for idx in $SELECTED_INDICES; do
    SRC="${REAL_FRAMES[$idx]}"
    TS="${REAL_TIMESTAMPS[$idx]}"
    FNAME=$(basename "$SRC")
    DST="$OUTDIR/representative/$FNAME"

    if [ -f "$SRC" ]; then
      cp "$SRC" "$DST"
      echo "$TS  $DST" >> "$REP_LIST_FILE"
    fi
  done

  REP_COUNT=$(wc -l < "$REP_LIST_FILE")
  ok "代表帧选取完成：$REP_COUNT 帧"
fi

# ---------- 4. 生成 manifest.json ----------
SEGMENT_START_FMT=$(fmt_time $SEGMENT_START_SEC)
SEGMENT_END_FMT=$(fmt_time $((SEGMENT_START_SEC + SEGMENT_DURATION_SEC)))
MANIFEST_FILE="$OUTDIR/manifest.json"

{
  echo "{"
  echo "  \"job\": {"
  echo "    \"video\": \"$FULL_VIDEO_PATH\","
  echo "    \"totalDurationSec\": $TOTAL_DURATION_INT,"
  echo "    \"segment\": {"
  echo "      \"startSec\": $SEGMENT_START_SEC,"
  echo "      \"startTime\": \"$SEGMENT_START_FMT\","
  echo "      \"endSec\": $((SEGMENT_START_SEC + SEGMENT_DURATION_SEC)),"
  echo "      \"endTime\": \"$SEGMENT_END_FMT\","
  echo "      \"durationSec\": $SEGMENT_DURATION_SEC"
  echo "    },"
  echo "    \"params\": {"
  echo "      \"interval\": $INTERVAL,"
  echo "      \"maxFrames\": $MAX_FRAMES"
  echo "    }"
  echo "  },"
  echo "  \"frames\": {"
  echo "    \"total\": $FRAME_COUNT,"
  echo "    \"representative\": $REP_COUNT"
  echo "  },"
  echo "  \"representativeFrames\": ["
  if [ "$REP_COUNT" -gt 0 ]; then
    _I=0
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      TS=$(echo "$line" | awk '{print $1}')
      FP=$(echo "$line" | awk '{print $2}')
      TS_SEC=$(( 10#${TS:0:2} * 3600 + 10#${TS:3:2} * 60 + 10#${TS:6:2} ))
      FNAME=$(basename "$FP")
      [ "$_I" -gt 0 ] && echo ","
      echo -n "    { \"index\": $_I, \"timestamp\": \"$TS\", \"timestampSec\": $TS_SEC, \"file\": \"$FNAME\", \"path\": \"$FP\" }"
      _I=$((_I + 1))
    done < "$REP_LIST_FILE"
    echo ""
  fi
  echo "  ],"
if [ -n "${TRANSCRIPT_TEXT:-}" ]; then
  echo "  \"audio\": {"
  echo "    \"transcriptText\": \"$(echo "$TRANSCRIPT_TEXT" | sed 's/"/\\"/g')\","
  echo "    \"modelUsed\": \"${MODEL_USED:-unknown}\","
  echo "    \"language\": \"${ASR_LANGUAGE}\""
  echo "  },"
fi
echo "  \"outputDir\": \"$OUTDIR\","
echo "  \"generatedAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
echo "}"
} > "$MANIFEST_FILE"

ok "manifest 已生成: $MANIFEST_FILE"

# ---------- 5. Workspace Staging ----------
STAGING_DIR=""
STAGING_REP_DIR=""
STAGING_MANIFEST=""
if [ "$DO_STAGING" = true ] && [ "$REP_COUNT" -gt 0 ]; then
  BASENAME=$(basename "$VIDEO")
  BASENAME="${BASENAME%.*}"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  STAGING_DIR="${WORKSPACE_DIR}/tmp/video-analysis/${BASENAME}_${TIMESTAMP}"
  STAGING_REP_DIR="${STAGING_DIR}/representative"
  STAGING_MANIFEST="${STAGING_DIR}/analysis-input.md"
  mkdir -p "$STAGING_REP_DIR"

  info "创建 workspace staging（image 工具友好版）：$STAGING_DIR"
  echo "   路径: ${STAGING_DIR}"
  echo ""

  # 复制带缩放的 staging 副本
  # 最大宽 800px，平衡读取速度和画质
  I=0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    TS=$(echo "$line" | awk '{print $1}')
    SRC_PATH=$(echo "$line" | awk '{print $2}')
    FNAME=$(basename "$SRC_PATH")
    # 带缩放的 staging 副本
    STAGED="${STAGING_REP_DIR}/${FNAME}"
    ffmpeg -y -i "$SRC_PATH" -vf "scale='min(800,iw)':'min(800,ih)':force_original_aspect_ratio=decrease" -q:v 3 "$STAGED" 2>/dev/null
    I=$((I + 1))
  done < "$REP_LIST_FILE"

  # 复制原始代表帧也在 staging 里（给手动需要的场景）
  mkdir -p "${STAGING_DIR}/original"
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    SRC_PATH=$(echo "$line" | awk '{print $3}')
    [ -z "$SRC_PATH" ] && SRC_PATH=$(echo "$line" | awk '{print $2}')
    FNAME=$(basename "$SRC_PATH")
    cp "$SRC_PATH" "${STAGING_DIR}/original/$FNAME"
  done < "$REP_LIST_FILE"

  ok "staging 副本就绪：${I} 帧（缩放至 800px 宽边）"

  # 生成 staging 的 analysis-input.md（给 image 工具使用）
  {
    echo "# Analysis Input — Video Segment"
    echo ""
    echo "## Segment Info"
    echo ""
    echo "| Field | Value |"
    echo "|-------|-------|"
    echo "| Video | \`$FULL_VIDEO_PATH\` |"
    echo "| Segment | ${SEGMENT_START_FMT} → ${SEGMENT_END_FMT} (${SEGMENT_DURATION_SEC}s) |"
    echo "| Total Duration | ${TOTAL_DURATION_INT}s |"
    echo "| Resolution | ${WIDTH}x${HEIGHT} |"
    echo ""
    echo "## Representative Frames (staged in workspace)"
    echo ""
    I=0
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      TS=$(echo "$line" | awk '{print $1}')
      FP=$(echo "$line" | awk '{print $2}')
      FNAME=$(basename "$FP")
      STAGED_PATH="${STAGING_REP_DIR}/${FNAME}"
      echo "| $I | $TS | \`${FNAME}\` | \`${STAGED_PATH}\` |"
      I=$((I + 1))
    done < "$REP_LIST_FILE"

    echo ""
    echo "## Suggested Analysis Order"
    echo ""
    echo "1. Read this file to understand the segment context."
    echo "2. Use \`image\` tool to analyze each representative frame in time order."
    echo "3. Write frame-by-frame Chinese descriptions + overall analysis into \`summary.md\`."
    echo ""
    echo "Images are in: \`${STAGING_REP_DIR}/\`"
    echo ""
    echo "---"
    echo "_Generated by analyze-video-segment.sh on $(date '+%Y-%m-%d %H:%M:%S')_"
  } > "$STAGING_MANIFEST"

  # 也在 staging 目录放一个 manifest.json
  cp "$MANIFEST_FILE" "${STAGING_DIR}/manifest.json"

  ok "analysis-input.md 已生成: $STAGING_MANIFEST"
fi

# ---------- 6. 生成 summary.md ----------
SUMMARY_FILE="$OUTDIR/summary.md"
{
  echo "# 视频段分析报告"
  echo ""
  echo "## 视频信息"
  echo ""
  echo "| 属性 | 值 |"
  echo "|------|-----|"
  echo "| 路径 | \`$FULL_VIDEO_PATH\` |"
  echo "| 总时长 | ${TOTAL_DURATION_INT} 秒 |"
  echo "| 分辨率 | ${WIDTH}x${HEIGHT} |"
  echo "| 编码 | $CODEC |"
  echo "| FPS | $FPS |"
  echo ""
  echo "## 分析片段"
  echo ""
  echo "| 属性 | 值 |"
  echo "|------|-----|"
  echo "| 起始 | ${SEGMENT_START_FMT} (${SEGMENT_START_SEC}s) |"
  echo "| 结束 | ${SEGMENT_END_FMT} ($((SEGMENT_START_SEC + SEGMENT_DURATION_SEC))s) |"
  echo "| 时长 | ${SEGMENT_DURATION_SEC} 秒 |"
  echo ""
  echo "## 分析参数"
  echo ""
  echo "| 参数 | 值 |"
  echo "|------|-----|"
  echo "| 抽帧间隔 | ${INTERVAL} 秒 |"
  echo "| 抽帧总数 | ${FRAME_COUNT} |"
  echo "| 代表帧数量 | ${REP_COUNT:-0} |"
  echo ""
  echo "## 代表帧清单"
  echo ""
  echo "| # | 时间戳 | 文件 |"
  echo "|---|--------|------|"
  I=1
  if [ -f "$REP_LIST_FILE" ]; then
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      TS=$(echo "$line" | awk '{print $1}')
      FP=$(echo "$line" | awk '{print $2}')
      FNAME=$(basename "$FP")
      echo "| $I | $TS | \`$FNAME\` |"
          done < "$REP_LIST_FILE"
  fi
  if [ -n "${TRANSCRIPT_TEXT:-}" ]; then
  echo ""
  echo "## 音频转写结果"
  echo ""
  echo "| 属性 | 值 |"
  echo "|------|-----|"
  echo "| ASR 模型 | ${MODEL_USED:-N/A} |"
  echo "| 语言 | ${ASR_LANGUAGE} |"
  echo "| 转写文本 | ${TRANSCRIPT_TEXT:-} |"
  echo ""
  echo "> 转写原文：${TRANSCRIPT_TEXT}"
  echo ""
fi
echo ""
echo "## 画面分析（待视觉模型补充）"
echo ""
echo "_此部分将由视觉模型（如 Gemma 4 31B）分析代表帧后填充。_"
echo ""
echo "---"
echo "_由 analyze-video-segment.sh 于 $(date '+%Y-%m-%d %H:%M:%S') 生成_"
} > "$SUMMARY_FILE"

ok "summary 文件已生成: $SUMMARY_FILE"

# ---------- 7. 音频转写（如果带 --with-audio）----------
TRANSCRIPT_TEXT=""
MODEL_USED=""
if [ "$DO_AUDIO" = true ]; then
  if [ "$TRANSCRIBE_ENGINE" = "local" ]; then
    TRANS_SCRIPT="${SCRIPT_DIR}/transcribe-video-audio-local.sh"
  else
    TRANS_SCRIPT="${SCRIPT_DIR}/transcribe-video-audio.sh"
  fi
  if [ ! -f "$TRANS_SCRIPT" ]; then
    warn "找不到转写脚本: $TRANS_SCRIPT，跳过音频"
  else
    info "检测到音频轨，启动 ASR 转写（引擎: ${TRANSCRIBE_ENGINE}）..."
    AUDIO_OUTDIR="${OUTDIR}/audio"
    mkdir -p "$AUDIO_OUTDIR"
    
    # 调用转写脚本，用同样的片段参数
    TRANS_OUTDIR="${OUTDIR}"
    
    if [ "$TRANSCRIBE_ENGINE" = "local" ]; then
      # 本地 faster-whisper 引擎
      LOCAL_MODEL_ARGS=""
      [ -n "$TRANSCRIBE_MODEL" ] && LOCAL_MODEL_ARGS="--model ${TRANSCRIBE_MODEL}"
      TRANS_ARGS="--language ${ASR_LANGUAGE} --start ${SEGMENT_START_SEC} --duration ${SEGMENT_DURATION_SEC} -o ${TRANS_OUTDIR} ${LOCAL_MODEL_ARGS}"
    else
      # bridge 引擎（默认）
      TRANS_ARGS="--language ${ASR_LANGUAGE} --start ${SEGMENT_START_SEC} --duration ${SEGMENT_DURATION_SEC} -o ${TRANS_OUTDIR}"
    fi
    
    if bash "$TRANS_SCRIPT" "$FULL_VIDEO_PATH" ${TRANS_ARGS} 2>&1; then
      # 读取转写结果
      if [ -f "${OUTDIR}/transcript.txt" ]; then
        TRANSCRIPT_TEXT=$(cat "${OUTDIR}/transcript.txt")
      fi
      if [ -f "${OUTDIR}/transcript.json" ]; then
        MODEL_USED=$(python3 -c "
import json
try:
    with open('${OUTDIR}/transcript.json') as f:
        d = json.load(f)
    print(d.get('model_used', d.get('model', 'unknown')) or 'unknown')
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")
      fi
      
      if [ -n "${TRANSCRIPT_TEXT:-}" ]; then
        ok "音频转写完成（模型: ${MODEL_USED}）"
      else
        warn "音频转写结果为空"
      fi
    else
      warn "音频转写出错（引擎: ${TRANSCRIBE_ENGINE}）"
    fi
  fi
fi

# 如果音频转写拿到了结果，重新生成 summary.md 包含音频信息
if [ -n "${TRANSCRIPT_TEXT:-}" ]; then
  # 重新生成 summary.md（追加音频转写信息）
  _TMP_SUMMARY=$(mktemp /tmp/summary-regen-XXXXXX.md)
  
  # 先复制原有的 summary 内容（画面分析部分）
  cp "$SUMMARY_FILE" "$_TMP_SUMMARY"
  
  # 在 "画面分析" 之前插入音频转写信息
  python3 -c "
import sys
with open(sys.argv[1]) as f:
    content = f.read()
insert = '''

## 音频转写结果

| 属性 | 值 |
|------|-----|
| ASR 模型 | ${MODEL_USED:-N/A} |
| 语言 | ${ASR_LANGUAGE} |
| 转写文本 | ${TRANSCRIPT_TEXT} |

> 转写原文：${TRANSCRIPT_TEXT}

'''
# Insert before '## 画面分析'
if '## 画面分析' in content:
    content = content.replace('## 画面分析', insert + '## 画面分析', 1)
with open(sys.argv[1], 'w') as f:
    f.write(content)
" "$_TMP_SUMMARY"
  mv "$_TMP_SUMMARY" "$SUMMARY_FILE"
  ok "summary 已更新（含音频转写信息）"
fi

# ---------- 8. 生成时间轴切片音画同步（--timeline）----------
build_timeline() {
  local outdir="$1"
  local interval="$2"
  local start_sec="$3"
  local duration_sec="$4"
  local transcript_text="$5"

  info "生成时间轴切片（--timeline）..."

  local slice_width=$interval
  [ "$slice_width" -lt 1 ] && slice_width=1

  python3 - "$outdir" "$slice_width" "$start_sec" "$duration_sec" "$FULL_VIDEO_PATH" "${MODEL_USED:-N/A}" <<'PYEOF'
import json, math, os, sys
from datetime import datetime, timezone
from pathlib import Path

outdir = Path(sys.argv[1])
slice_width = max(1, int(sys.argv[2]))
start_sec = int(sys.argv[3])
duration_sec = int(sys.argv[4])
video_path = sys.argv[5]
model_used = sys.argv[6]

transcript_path = outdir / 'transcript.json'
frame_list_path = outdir / 'frames' / 'frame-list.txt'

def fmt_time(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def parse_frame_list(path: Path):
    frames = []
    if not path.exists():
        return frames
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        ts_str, fp = parts
        hh, mm, ss = ts_str.split(':')
        frames.append({
            'sec': int(hh) * 3600 + int(mm) * 60 + int(ss),
            'timestamp': ts_str,
            'path': fp,
            'name': os.path.basename(fp),
        })
    return frames

def overlap(a_start, a_end, b_start, b_end):
    return max(a_start, b_start) < min(a_end, b_end)

def coarse_segments(text: str, num_slices: int):
    if not text:
        return ['[无音频转写]'] * num_slices
    compact = text.strip()
    if not compact:
        return ['[无音频转写]'] * num_slices
    total = len(compact)
    result = []
    for i in range(num_slices):
        c0 = total * i // num_slices
        c1 = total * (i + 1) // num_slices
        seg = compact[c0:c1].strip()
        result.append(seg or '[无对应文本]')
    return result

transcript = {}
if transcript_path.exists():
    try:
        transcript = json.loads(transcript_path.read_text())
    except Exception:
        transcript = {}

full_text = transcript.get('text', '') or ''
words = transcript.get('words') or []
segments = transcript.get('segments') or []
frames = parse_frame_list(frame_list_path)

num_slices = max(1, math.ceil(duration_sec / slice_width))

alignment_precision = 'coarse'
alignment_note = '未拿到时间戳，按文本位置做粗对齐'
if any((w.get('start') is not None and w.get('end') is not None) for w in words):
    alignment_precision = 'word_timestamps'
    alignment_note = 'ASR 返回了词级时间戳，按词级时间对齐'
elif any((s.get('start') is not None and s.get('end') is not None) for s in segments):
    alignment_precision = 'segment_timestamps'
    alignment_note = 'ASR 返回了段级时间戳，按段级时间对齐'

coarse_texts = coarse_segments(full_text, num_slices)

slice_items = []
for idx in range(num_slices):
    sl_start = start_sec + idx * slice_width
    sl_end = min(start_sec + duration_sec, sl_start + slice_width)
    mid = (sl_start + sl_end) / 2.0

    closest = None
    if frames:
        closest = min(frames, key=lambda f: abs(f['sec'] - mid))

    audio_text = '[无对应文本]'
    if alignment_precision == 'word_timestamps':
        matched = [w.get('word', '').strip() for w in words if w.get('word') and overlap(float(w.get('start', 0)), float(w.get('end', 0)), sl_start, sl_end)]
        if matched:
            audio_text = ' '.join(matched).strip()
    elif alignment_precision == 'segment_timestamps':
        matched = [s.get('text', '').strip() for s in segments if s.get('text') and overlap(float(s.get('start', 0) or 0), float(s.get('end', 0) or 0), sl_start, sl_end)]
        if matched:
            audio_text = ' / '.join(matched).strip()
    else:
        audio_text = coarse_texts[idx]

    slice_items.append({
        'slice': idx,
        'startSec': sl_start,
        'startTime': fmt_time(sl_start),
        'endSec': sl_end,
        'endTime': fmt_time(sl_end),
        'closestFrame': closest['name'] if closest else '',
        'closestFrameTimestamp': closest['timestamp'] if closest else '',
        'audioText': audio_text or '[无对应文本]',
        'alignmentPrecision': alignment_precision,
    })

payload = {
    'job': {
        'video': video_path,
        'segmentDurationSec': duration_sec,
        'sliceWidthSec': slice_width,
        'numSlices': num_slices,
        'fullTranscript': full_text,
        'transcriptModel': model_used,
        'alignmentPrecision': alignment_precision,
        'alignmentNote': alignment_note,
    },
    'slices': slice_items,
}
(outdir / 'timeline.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))

lines = [
    '# 时间轴切片音画同步分析',
    '',
    '## 作业信息',
    '',
    '| 属性 | 值 |',
    '|------|-----|',
    f'| 视频 | `{video_path}` |',
    f'| 片段时长 | {duration_sec} 秒 |',
    f'| 切片宽度 | {slice_width} 秒 |',
    f'| 切片数量 | {num_slices} |',
    f'| ASR 模型 | {model_used} |',
    f'| 对齐精度 | **{alignment_precision}** |',
    '',
    f'> {alignment_note}',
    '',
    '## 音频转写全文',
    '',
    '```',
    full_text or '[无音频转写]',
    '```',
    '',
    '## 时间轴切片',
    '',
    '| # | 时间区间 | 最近帧 | 帧时间 | 该段对应音频 |',
    '|---|--------|--------|--------|----------------|',
]
for s in slice_items:
    lines.append(f"| {s['slice'] + 1} | {s['startTime']} → {s['endTime']} | {s['closestFrame'] or '-'} | {s['closestFrameTimestamp'] or '-'} | {s['audioText']} |")
lines += [
    '',
    '---',
    f"_由 analyze-video-segment.sh (--timeline) 于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} 生成_",
]
(outdir / 'timeline.md').write_text("\n".join(lines) + "\n")
PYEOF

  local gen_result=$?
  if [ $gen_result -eq 0 ]; then
    ok "时间轴 JSON 已生成: ${outdir}/timeline.json"
    ok "时间轴 Markdown 已生成: ${outdir}/timeline.md"
  else
    warn "时间轴生成失败"
  fi
}

# 调用时间轴生成
if [ "$DO_TIMELINE" = true ]; then
  if [ -n "${TRANSCRIPT_TEXT:-}" ]; then
    build_timeline "$OUTDIR" "$INTERVAL" "$SEGMENT_START_SEC" "$SEGMENT_DURATION_SEC" "$TRANSCRIPT_TEXT"
  else
    build_timeline "$OUTDIR" "$INTERVAL" "$SEGMENT_START_SEC" "$SEGMENT_DURATION_SEC" ""
  fi
fi

# ---------- 9. 最终输出 ----------
echo ""
echo "═══════════════════════════════════════════════"
echo -e "  ${GREEN}分析完成!${NC}"
echo "═══════════════════════════════════════════════"
echo ""
echo "  输出目录:    $OUTDIR"
echo "    ├── frames/              (${FRAME_COUNT} 帧)"
echo "    ├── representative/      (${REP_COUNT:-0} 代表帧)"
echo "    ├── frame-list.txt"
echo "    ├── summary.md"
echo "    ├── manifest.json"
if [ "$DO_TIMELINE" = true ]; then
  echo "    ├── timeline.md"
  echo "    └── timeline.json"
fi

if [ -n "${TRANSCRIPT_TEXT:-}" ] && [ -n "${MODEL_USED:-}" ]; then
  echo "  音频转写 (${MODEL_USED}):"
  echo "    → ${TRANSCRIPT_TEXT}"
  echo ""
fi

if [ -n "$STAGING_DIR" ]; then
  echo "  workspace staging:"
  echo "    ├── ${STAGING_DIR}/"
  echo "    ├── representative/    (缩放版本，供 image 直接读取)"
  echo "    ├── manifest.json"
  echo "    └── analysis-input.md  (分析提示)"
  echo ""
  echo "  image 分析命令参考:"
  echo "    image（OpenClaw 内）："
  echo "      参数:"
  echo "        - prompt: 请用中文分析这些代表帧画面，描述画面内容、关键元素、构图、颜色。"
  echo "        - images: 以下文件依次"
  I=0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    FP=$(echo "$line" | awk '{print $2}')
    FNAME=$(basename "$FP")
    echo "          ${STAGING_REP_DIR}/${FNAME}"
    I=$((I + 1))
  done < "$REP_LIST_FILE"
  echo "        - model: nvidia/google/gemma-4-31b-it"
  echo ""
fi

echo "  代表帧路径:  $REP_LIST_FILE"
echo "  manifest:    $MANIFEST_FILE"

# 如果带音频转写，追加展示
if [ -n "$TRANSCRIPT_TEXT" ] && [ -n "$MODEL_USED" ]; then
  echo ""
  echo "  音频转写 (${MODEL_USED}):"
  echo "    → ${TRANSCRIPT_TEXT}"
  echo ""
fi

# ---------- 9. 建议下一步 ----------
if [ "${REP_COUNT:-0}" -gt 0 ]; then
  echo "💡 下一步建议："
  echo "    使用 image 工具调视觉模型分析代表帧，然后更新 summary.md"
  echo ""
  echo "   示例（OpenClaw 内）："
  echo "     image 工具 - 读取 staging representative 目录下的多张代表帧"
  echo "     用 nvidia/google/gemma-4-31b-it 做中文描述分析"
  echo ""
fi
