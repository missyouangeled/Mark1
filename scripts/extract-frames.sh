#!/usr/bin/env bash
# ============================================================================
# extract-frames.sh — 从视频按时间间隔抽帧
#
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 用途：从视频中提取关键帧，供 Gemma 4 31B 等视觉模型做画面理解。
#       完全不碰 OpenClaw 主链路，可独立运行验证。
#
# 用法：
#   bash scripts/extract-frames.sh <视频路径> [间隔秒数] [输出目录]
#
# 默认值：
#   - 间隔：5 秒（每 5 秒抽一帧）
#   - 输出目录：/mnt/data/openclaw/frame-extract-jobs/<视频名>_<时间戳>/
#
# 输出：
#   - 每帧文件：frame_0001.jpg, frame_0002.jpg, ...
#   - 帧列表文件：frame-list.txt（每行：时间戳 帧路径）
#   - 总帧数打印
# ============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "用法: $0 <视频路径> [间隔秒数] [输出目录]"
  echo ""
  echo "示例:"
  echo "  bash scripts/extract-frames.sh test.mp4"
  echo "  bash scripts/extract-frames.sh test.mp4 2"
  echo "  bash scripts/extract-frames.sh test.mp4 5 /tmp/frames/"
  exit 1
fi

VIDEO="$1"
INTERVAL="${2:-5}"
OUTDIR="${3:-}"

# 验证视频存在
if [ ! -f "$VIDEO" ]; then
  echo "❌ 文件不存在: $VIDEO"
  exit 1
fi

# 如果没有指定输出目录，自动生成
if [ -z "$OUTDIR" ]; then
  BASENAME=$(basename "$VIDEO")
  BASENAME="${BASENAME%.*}"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  OUTDIR="/mnt/data/openclaw/frame-extract-jobs/${BASENAME}_${TIMESTAMP}"
fi

mkdir -p "$OUTDIR"

echo "📼 视频:     $VIDEO"
echo "⏱️  间隔:    每 ${INTERVAL} 秒"
echo "📁 输出:     $OUTDIR"
echo ""

# 用 ffmpeg 抽帧（顺序编号，不依赖 PTS）
# 先获取视频时长
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO" 2>/dev/null || echo 0)
DURATION_INT=${DURATION%.*}

ffmpeg -i "$VIDEO" \
  -vf "fps=1/${INTERVAL},setpts=N/1/TB" \
  -q:v 3 \
  -start_number 1 \
  "${OUTDIR}/frame_%04d.jpg" \
  -y 2>&1 | grep -v "^\s*$" || true

# 生成帧列表
FRAME_LIST="${OUTDIR}/frame-list.txt"
: > "$FRAME_LIST"

FRAME_FILES=()
while IFS= read -r -d '' f; do
  FRAME_FILES+=("$f")
done < <(find "$OUTDIR" -maxdepth 1 -name 'frame_*.jpg' -print0 | sort -z -V)

for f in "${FRAME_FILES[@]}"; do
  # 从文件名提取帧序号
  FNAME=$(basename "$f" .jpg)
  FRAME_NUM="${FNAME##*_}"
  FRAME_NUM=$((10#$FRAME_NUM))
  # 计算时间戳 = (帧序号 - 1) * 间隔
  TIMESTAMP_SEC=$(( (FRAME_NUM - 1) * INTERVAL ))
  # 如果超过视频时长则跳过
  if [ "$TIMESTAMP_SEC" -gt "$DURATION_INT" ] 2>/dev/null; then
    continue
  fi
  # 格式化为 HH:MM:SS
  H=$(( TIMESTAMP_SEC / 3600 ))
  M=$(( (TIMESTAMP_SEC % 3600) / 60 ))
  S=$(( TIMESTAMP_SEC % 60 ))
  TIMESTAMP_FMT=$(printf "%02d:%02d:%02d" "$H" "$M" "$S")
  echo "$TIMESTAMP_FMT  $f" >> "$FRAME_LIST"
done

TOTAL="${#FRAME_FILES[@]}"
echo ""
echo "✅ 抽帧完成！共 ${TOTAL} 帧"
echo "   帧列表: ${FRAME_LIST}"
echo ""

# 显示前几帧预览
if [ "$TOTAL" -gt 0 ]; then
  echo "📋 前 5 帧："
  head -5 "$FRAME_LIST"
  if [ "$TOTAL" -gt 5 ]; then
    echo "   ... 共 ${TOTAL} 帧"
  fi
fi
