#!/usr/bin/env bash
# Mark42 集群打包脚本
# 用途：将指定集群的配置 + 状态打包为 tar.gz，用于 R14 集群替换
#
# 用法：
#   ./cluster-pack.sh <cluster-name>          # 打包到 /tmp/
#   ./cluster-pack.sh <cluster-name> /path/   # 打包到指定目录
#
# 打包内容：
#   - config.json       集群配置
#   - status.json       当前状态
#   - restart_count     重启计数
#   - FAILURE.md        失败契约（如有）
#   - manifest.json     打包清单（打包时间、源主机、集群信息）

set -euo pipefail

CLUSTER_NAME="${1:?用法: $0 <cluster-name> [output-dir]}"
OUTPUT_DIR="${2:-/tmp}"

STATE_DIR="${HOME}/.local/state/openclaw/mark42/clusters"
CLUSTER_DIR="${STATE_DIR}/${CLUSTER_NAME}"

if [ ! -d "$CLUSTER_DIR" ]; then
    echo "❌ 集群目录不存在: $CLUSTER_DIR"
    echo "可用集群:"
    ls -1 "$STATE_DIR" 2>/dev/null || echo "  (无)"
    exit 1
fi

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
TARBALL="${OUTPUT_DIR}/${CLUSTER_NAME}-${TIMESTAMP}.tar.gz"

# 生成 manifest
MANIFEST=$(mktemp)
cat > "$MANIFEST" << EOF
{
    "cluster": "${CLUSTER_NAME}",
    "packedAt": "${TIMESTAMP}",
    "host": "$(hostname)",
    "files": []
}
EOF

# 添加文件列表到 manifest
FILES_JSON="[]"
for f in "$CLUSTER_DIR"/*; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    FILES_JSON=$(echo "$FILES_JSON" | python3 -c "import json,sys; l=json.load(sys.stdin); l.append('${fname}'); print(json.dumps(l))")
done

python3 -c "
import json
with open('$MANIFEST') as f:
    m = json.load(f)
m['files'] = $FILES_JSON
with open('$MANIFEST', 'w') as f:
    json.dump(m, f, indent=2)
"

# 打包
cd "$STATE_DIR"
tar czf "$TARBALL" \
    -C "$STATE_DIR" \
    --transform="s,^${CLUSTER_NAME}/,," \
    "$CLUSTER_NAME/config.json" \
    "$CLUSTER_NAME/status.json" \
    "$CLUSTER_NAME/restart_count" \
    2>/dev/null || true

# 尝试加入可选文件
for opt_file in "FAILURE.md"; do
    if [ -f "$CLUSTER_DIR/$opt_file" ]; then
        tar rf "$TARBALL" -C "$STATE_DIR" --transform="s,^${CLUSTER_NAME}/,," "$CLUSTER_NAME/$opt_file" 2>/dev/null || true
    fi
done

# 加入 manifest
tar rf "$TARBALL" -C "$(dirname "$MANIFEST")" "$(basename "$MANIFEST")" --transform="s,^$(basename "$MANIFEST"),manifest.json," 2>/dev/null || true

# 重新压缩（追加后需要）
if ! gzip -t "$TARBALL" 2>/dev/null; then
    # 如果 tar 追加破坏了 gzip，用 tar czf 重新打包
    tmp_dir=$(mktemp -d)
    tar xzf "$TARBALL" -C "$tmp_dir" 2>/dev/null || true
    cp "$MANIFEST" "$tmp_dir/manifest.json"
    tar czf "$TARBALL" -C "$tmp_dir" .
    rm -rf "$tmp_dir"
fi

rm -f "$MANIFEST"

echo "✅ 集群打包完成"
echo "   集群: $CLUSTER_NAME"
echo "   文件: $TARBALL"
echo "   大小: $(du -h "$TARBALL" | cut -f1)"

# 校验
echo ""
echo "📦 包内容:"
tar tzf "$TARBALL"
