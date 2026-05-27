#!/bin/bash
# 补丁：关闭 DeepSeek V4 Pro 的 native reasoning，防止 thinking 内容泄露到前台
# 适用机器：公司（Linux）
# 依赖：sed
# 触发：OpenClaw 升级后自动执行（由 post-upgrade hook 调用）
# 维护边界：上游 deepseek 扩展结构变化时可能失效

PLUGIN_JSON="$HOME/.npm-global/lib/node_modules/openclaw/dist/extensions/deepseek/openclaw.plugin.json"

if [ ! -f "$PLUGIN_JSON" ]; then
    echo "[deepseek-v4-pro-reasoning-off] 插件文件不存在: $PLUGIN_JSON"
    exit 1
fi

if grep -q '"id": "deepseek-v4-pro"' "$PLUGIN_JSON"; then
    if grep -A2 '"id": "deepseek-v4-pro"' "$PLUGIN_JSON" | grep -q '"reasoning": true'; then
        sed -i 's/\("id": "deepseek-v4-pro",\n            "name": "DeepSeek V4 Pro",\n            "reasoning":\) true/\1 false/' "$PLUGIN_JSON"
        # 兜底：用单行 sed
        sed -i '/"id": "deepseek-v4-pro"/,/reasoning/{s/"reasoning": true/"reasoning": false/}' "$PLUGIN_JSON"
        echo "[deepseek-v4-pro-reasoning-off] 已关闭 DeepSeek V4 Pro reasoning"
    else
        echo "[deepseek-v4-pro-reasoning-off] reasoning 已经是 false，跳过"
    fi
else
    echo "[deepseek-v4-pro-reasoning-off] 未找到 deepseek-v4-pro 模型定义，可能上游结构已变化"
    exit 1
fi
