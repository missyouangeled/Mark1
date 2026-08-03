#!/usr/bin/env bash
# ============================================================
# generate-sbom.sh - Mark42 SBOM（软件物料清单）生成脚本
#
# 功能：使用 cyclonedx-py 从当前 Python 环境生成 CycloneDX JSON 格式 SBOM
# 输出：dist/sbom/mark42-sbom.json
#
# 用法：
#   ./scripts/generate-sbom.sh          # 生成 SBOM
#   ./scripts/generate-sbom.sh --help   # 查看帮助
#
# 依赖：cyclonedx-bom (pip install cyclonedx-bom)
# ============================================================

set -euo pipefail

# ---------- 帮助信息 ----------
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Mark42 SBOM 生成脚本

功能：
  扫描当前 Python 环境，生成 CycloneDX JSON 格式的软件物料清单 (SBOM)。
  SBOM 记录了项目中所有第三方依赖的名称、版本、许可证等信息，
  用于安全审计、合规检查和供应链透明度。

用法：
  ./scripts/generate-sbom.sh          # 生成 SBOM 到 dist/sbom/
  ./scripts/generate-sbom.sh --help   # 显示本帮助

输出：
  dist/sbom/mark42-sbom.json          # CycloneDX 1.6 JSON 格式

依赖：
  cyclonedx-bom (pip install cyclonedx-bom)
  版本要求：>= 7.0

环境变量：
  无特殊要求。脚本会自动查找 python3 和 cyclonedx-py。
EOF
  exit 0
fi

# ---------- 变量定义 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/dist/sbom"
OUTPUT_FILE="$OUTPUT_DIR/mark42-sbom.json"
PYPROJECT="$PROJECT_DIR/pyproject.toml"

# ---------- 前置检查 ----------
# 检查 python3
if ! command -v python3 &>/dev/null; then
  echo "❌ 错误：未找到 python3，请先安装 Python 3。" >&2
  exit 1
fi

# 检查 cyclonedx-py
# 优先用 PATH 中的，其次尝试用户安装路径 ~/.local/bin
CYCLONEDX_PY=""
if command -v cyclonedx-py &>/dev/null; then
  CYCLONEDX_PY="cyclonedx-py"
elif [[ -x "$HOME/.local/bin/cyclonedx-py" ]]; then
  CYCLONEDX_PY="$HOME/.local/bin/cyclonedx-py"
else
  echo "❌ 错误：未找到 cyclonedx-py。" >&2
  echo "   请先安装：pip install cyclonedx-bom" >&2
  exit 1
fi

# 检查 pyproject.toml
if [[ ! -f "$PYPROJECT" ]]; then
  echo "❌ 错误：未找到 pyproject.toml ($PYPROJECT)" >&2
  echo "   SBOM 生成需要 pyproject.toml 来识别主组件信息。" >&2
  exit 1
fi

# ---------- 生成 SBOM ----------
echo "📦 正在生成 SBOM..."
echo "   项目目录：$PROJECT_DIR"
echo "   Python：$(python3 --version 2>&1)"
echo "   cyclonedx-py：$($CYCLONEDX_PY --version 2>&1)"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 生成 SBOM
# 使用 environment 子命令扫描当前 Python 环境
# --pyproject 关联主组件信息（名称、版本等）
# --of JSON 指定输出格式为 JSON
if ! $CYCLONEDX_PY environment \
  --pyproject "$PYPROJECT" \
  --of JSON \
  -o "$OUTPUT_FILE" 2>&1; then
  echo "❌ 错误：SBOM 生成失败。" >&2
  exit 1
fi

# ---------- 结果报告 ----------
COMPONENT_COUNT=$(python3 -c "
import json, sys
with open('$OUTPUT_FILE') as f:
    bom = json.load(f)
print(len(bom.get('components', [])))
" 2>/dev/null || echo "未知")

echo ""
echo "✅ SBOM 生成成功！"
echo "   输出文件：$OUTPUT_FILE"
echo "   文件大小：$(du -h "$OUTPUT_FILE" | cut -f1)"
echo "   组件数量：$COMPONENT_COUNT"
echo "   格式：CycloneDX 1.6 JSON"
