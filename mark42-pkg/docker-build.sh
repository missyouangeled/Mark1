#!/usr/bin/env bash
# Mark42 Docker 构建脚本
# 用法: bash docker-build.sh [tag]
set -euo pipefail

TAG="${1:-latest}"
IMAGE="mark42"

echo "🔨 构建 ${IMAGE}:${TAG}..."
docker build -t "${IMAGE}:${TAG}" -f Dockerfile .. || {
    echo "❌ 构建失败"
    exit 1
}

echo "✅ 构建完成: ${IMAGE}:${TAG}"
echo ""
echo "运行示例:"
echo "  docker run --rm ${IMAGE}:${TAG} status"
echo "  docker run --rm ${IMAGE}:${TAG} armor --check"
echo "  docker run --rm -v ~/.openclaw:/home/mark42/.openclaw ${IMAGE}:${TAG} status"
