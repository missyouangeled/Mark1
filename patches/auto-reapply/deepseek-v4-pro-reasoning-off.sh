#!/bin/bash
# 补丁：关闭 DeepSeek V4 Pro / V4 Flash 的 native reasoning，防止 thinking 内容泄露到前台
# 适用机器：公司（Linux）
# 依赖：sed
# 触发：OpenClaw 升级后自动执行（由 post-upgrade hook 调用）
# 维护边界：上游 deepseek 扩展结构变化时可能失效
# 注意：DeepSeek Reasoner 的 reasoning 保持 true（那是推理模型的本职）

PLUGIN_JSON="$HOME/.npm-global/lib/node_modules/openclaw/dist/extensions/deepseek/openclaw.plugin.json"

if [ ! -f "$PLUGIN_JSON" ]; then
    echo "[deepseek-reasoning-off] 插件文件不存在: $PLUGIN_JSON"
    exit 1
fi

for MODEL_ID in deepseek-v4-pro deepseek-v4-flash; do
    if grep -q "\"id\": \"$MODEL_ID\"" "$PLUGIN_JSON"; then
        if sed -n "/\"id\": \"$MODEL_ID\"/,/reasoning/p" "$PLUGIN_JSON" | grep -q '"reasoning": true'; then
            sed -i "/\"id\": \"$MODEL_ID\"/,/reasoning/{s/\"reasoning\": true/\"reasoning\": false/}" "$PLUGIN_JSON"
            echo "[deepseek-reasoning-off] 已关闭 $MODEL_ID reasoning"
        else
            echo "[deepseek-reasoning-off] $MODEL_ID reasoning 已经是 false，跳过"
        fi
    else
        echo "[deepseek-reasoning-off] 未找到 $MODEL_ID 模型定义，可能上游结构已变化"
    fi
done
