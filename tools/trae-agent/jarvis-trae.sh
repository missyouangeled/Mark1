#!/bin/bash
# trae-cli wrapper for 贾维斯（OpenClaw）
# 用法：
#   ./jarvis-trae.sh "在当前目录写一个 hello.py"
#   ./jarvis-trae.sh "fix bug in scripts/mark42_modules/armor.py"
#
# 配置：
#   trae_config.yaml 里有真 key（明码），也会读 .env 里的 OPENROUTER_API_KEY
#   默认走 trae_config.yaml（OpenRouter + openai/gpt-oss-120b:free）
#   想换模型就改 trae_config.yaml
#
# 路径策略：
#   如果 TRAE_AGENT_HOME 环境变量存在 → 切换到那里（独立 trae-agent 仓库用法）
#   否则 → 假设 trae-agent 跟 jarvis-trae.sh 同目录（直接 clone bytedance/trae-agent）
#   Mark1 仓库里这个脚本默认是"配置层"用法，TRAE_AGENT_HOME 指向 ~/trae-agent

set -e

# 决定工作目录
if [ -n "$TRAE_AGENT_HOME" ] && [ -d "$TRAE_AGENT_HOME" ]; then
    cd "$TRAE_AGENT_HOME"
elif [ -f .venv/bin/activate ] && [ -f trae_config.yaml ]; then
    # 当前目录就是 trae-agent 仓库根
    :
else
    # 默认假设用户把 trae-agent clone 在 ~/trae-agent
    if [ -d "$HOME/trae-agent" ]; then
        cd "$HOME/trae-agent"
    else
        echo "❌ 找不到 trae-agent 仓库。请设置 TRAE_AGENT_HOME 或 clone https://github.com/bytedance/trae-agent 到 ~/trae-agent"
        exit 1
    fi
fi

# 加载 .env（如果有）
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

source .venv/bin/activate
exec trae-cli run "$@"
