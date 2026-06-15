#!/usr/bin/env bash
# 贾维斯 OCR 便捷入口 — bash 包装器
# 适用机器：通用（当前 Mark1 / 公司 Linux 已验证）
# 系统 / OS：Linux
# 用途：确保始终使用 PaddleOCR venv 的 Python 执行 OCR
#
# 用法：
#   bash tools/jarvis-ocr.sh --input image.png
#   bash tools/jarvis-ocr.sh --input image.png --json
#   bash tools/jarvis-ocr.sh --list-models

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="/mnt/data/openclaw/paddleocr-venv/bin/python3"
OCR_SCRIPT="$SCRIPT_DIR/../scripts/jarvis-ocr.py"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ PaddleOCR venv 未找到: $VENV_PYTHON" >&2
    echo "   请先按 docs/贾维斯中枢-Mark2-小模型清单.md 安装" >&2
    exit 1
fi

exec "$VENV_PYTHON" "$OCR_SCRIPT" "$@"
