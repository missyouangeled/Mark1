#!/usr/bin/env bash
# 适用机器：公司（Linux）（脚本本身也可用于其他 Linux，但当前规则按公司 Linux 机的双盘布局写）
# 系统 / OS：Linux
# 用途：在下载大文件、解压模型、拉仓库、生成大体积中间产物前，先估算空间并给出建议落盘位置。
set -euo pipefail

if [[ $# -lt 1 ]]; then
  cat <<'EOF'
用法：
  bash scripts/storage-preflight.sh <预计大小> [用途说明]

例子：
  bash scripts/storage-preflight.sh 1.5G ChatTTS-assets
  bash scripts/storage-preflight.sh 800M 临时解压包

规则（默认）：
  - 峰值占用按“预计大小 x 2”估算（下载 + 解压/中转/缓存）
  - 若预计大小 >= 1G，默认建议放到 /mnt/data
  - 若执行后根盘 / 剩余空间会低于 8G，也默认建议放到 /mnt/data
EOF
  exit 1
fi

ESTIMATE_RAW="$1"
PURPOSE="${2:-未命名任务}"
ROOT_PATH="/"
DATA_PATH="/mnt/data"
STAGING_PATH="/mnt/data/openclaw/download-staging"
WORKSPACE_TMP_PATH="$HOME/.openclaw/workspace/tmp"
ROOT_MIN_FREE_BYTES=$((8 * 1024 * 1024 * 1024))
ROOT_PREFERRED_FREE_BYTES=$((10 * 1024 * 1024 * 1024))
LARGE_BYTES=$((1024 * 1024 * 1024))
PEAK_FACTOR=2

if ! command -v numfmt >/dev/null 2>&1; then
  echo "缺少 numfmt，无法解析大小参数。" >&2
  exit 2
fi

estimate_bytes=$(numfmt --from=iec "$ESTIMATE_RAW" 2>/dev/null || true)
if [[ -z "$estimate_bytes" ]]; then
  estimate_bytes=$(numfmt --from=si "$ESTIMATE_RAW" 2>/dev/null || true)
fi
if [[ -z "$estimate_bytes" ]]; then
  echo "无法解析大小：$ESTIMATE_RAW" >&2
  exit 2
fi

peak_bytes=$((estimate_bytes * PEAK_FACTOR))
root_free=$(df --output=avail -B1 "$ROOT_PATH" | tail -1 | tr -d ' ')
data_free=$(df --output=avail -B1 "$DATA_PATH" | tail -1 | tr -d ' ')
root_after=$((root_free - peak_bytes))
data_after=$((data_free - peak_bytes))

human() {
  numfmt --to=iec --suffix=B "$1"
}

recommendation="根盘可接受"
suggested_path="$WORKSPACE_TMP_PATH"
reason="预计体积较小，且根盘剩余空间仍足够。"

if (( estimate_bytes >= LARGE_BYTES )); then
  recommendation="优先放到数据盘"
  suggested_path="$STAGING_PATH"
  reason="预计单次体积 >= 1G，按规则默认优先放到 /mnt/data。"
elif (( root_after < ROOT_MIN_FREE_BYTES )); then
  recommendation="必须放到数据盘"
  suggested_path="$STAGING_PATH"
  reason="若放根盘，执行后 / 剩余空间会低于 8G 安全线。"
elif (( root_free < ROOT_PREFERRED_FREE_BYTES )); then
  recommendation="倾向放到数据盘"
  suggested_path="$STAGING_PATH"
  reason="当前根盘空余本来就偏紧，建议把新增占用放到 /mnt/data。"
fi

cat <<EOF
[storage-preflight]
用途：$PURPOSE
预计大小：$(human "$estimate_bytes")
按 2x 峰值预估：$(human "$peak_bytes")

当前剩余：
- 根盘 /：$(human "$root_free")
- 数据盘 /mnt/data：$(human "$data_free")

若写入根盘后预计剩余：$(human "$root_after")
若写入数据盘后预计剩余：$(human "$data_after")

结论：$recommendation
建议路径：$suggested_path
原因：$reason
EOF
