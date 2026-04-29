#!/bin/bash
set -e

# =============================================
# OpenClaw 配置迁移导出脚本
# 用法：bash scripts/export-setup.sh
# 输出：openclaw-setup-export-<日期>.tar.gz
# =============================================

WORKSPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
EXPORT_DIR="/tmp/openclaw-export-$$"
OUTPUT_FILE="$WORKSPACE_DIR/openclaw-setup-export-$(date +%Y%m%d).tar.gz"

echo "📦 开始导出 OpenClaw 配置..."

mkdir -p "$EXPORT_DIR/config"
mkdir -p "$EXPORT_DIR/credentials"

# 1. 导出 openclaw.json（脱敏处理）
echo "   → 导出配置文件（脱敏）..."
python3 -c "
import json, sys

with open('$OPENCLAW_DIR/openclaw.json') as f:
    cfg = json.load(f)

def mask_sensitive(obj):
    if isinstance(obj, dict):
        for k,v in obj.items():
            if any(s in k.lower() for s in ['token', 'secret', 'password', 'apikey', 'api_key']):
                if isinstance(v, str) and len(v) > 8:
                    obj[k] = v[:6] + '***' + v[-4:]
            else:
                mask_sensitive(v)
    elif isinstance(obj, list):
        for item in obj:
            mask_sensitive(item)

mask_sensitive(cfg)

# 保留结构供新机参考
with open('$EXPORT_DIR/config/openclaw.json', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>&1 || echo "⚠️  config 脱敏导出失败"

# 2. 导出 credentials 目录（含所有认证信息）
if [ -d "$OPENCLAW_DIR/credentials" ] && [ "$(ls -A $OPENCLAW_DIR/credentials 2>/dev/null)" ]; then
    echo "   → 导出认证凭据..."
    cp -r "$OPENCLAW_DIR/credentials"/* "$EXPORT_DIR/credentials/" 2>/dev/null || true
else
    echo "   ⚠️  credentials 目录为空或不存在"
fi

# 3. 附带还原说明
cat > "$EXPORT_DIR/RESTORE.md" << 'EOF'
# 🚀 新机还原步骤

## 前置条件
1. 新机器已安装 Node.js (>=18)
2. 配置好 GitHub SSH 密钥

## 步骤

### 1. 安装 OpenClaw
```bash
npm install -g openclaw
```

### 2. 还原配置文件
```bash
# 将本压缩包传到新机后解压
tar xzf openclaw-setup-export-*.tar.gz

# 复制配置
cp config/openclaw.json ~/.openclaw/openclaw.json

# 复制凭据
cp -r credentials/* ~/.openclaw/credentials/
```

### 3. 克隆 workspace
```bash
git clone git@github.com:missyouangeled/test-git.git ~/.openclaw/workspace
```

### 4. 启动验证
```bash
openclaw gateway status
# 或直接启动
openclaw gateway start
```

---

⚠️ 注意：`openclaw.json` 中的敏感字段已脱敏。真正的敏感凭据存储在 `credentials/` 目录中，请确保安全传输。
EOF

# 4. 打包
cd "$EXPORT_DIR/.."
BASENAME=$(basename "$EXPORT_DIR")
tar czf "$OUTPUT_FILE" "$BASENAME/config" "$BASENAME/credentials" "$BASENAME/RESTORE.md" 2>/dev/null

# 清理
rm -rf "$EXPORT_DIR"

echo "✅ 导出完成：$OUTPUT_FILE"
echo "   (大小: $(du -h "$OUTPUT_FILE" | cut -f1))"
echo ""
echo "将此文件传到新机器，然后按照 RESTORE.md 中的步骤操作即可。"
