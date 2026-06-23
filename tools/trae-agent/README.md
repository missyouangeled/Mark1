# trae-agent 集成配置层（Mark1 仓库用）

> 这是 trae-agent 的"贾维斯配置层"——在 Mark1 workspace 仓库里给 trae-agent 用的胶水代码。
> trae-agent 主仓库（https://github.com/bytedance/trae-agent）不在这里。

## 文件清单

- `jarvis-trae.sh` —— 启动脚本
- `trae_config.yaml` —— trae-agent 配置（**不含 key**，key 走环境变量）
- `.env.example` —— 环境变量模板（不含真 key）
- `README.md` —— 本文件

## 在新机器上 4.5 步接通 trae-agent

```bash
# 1. 拉 trae-agent 主仓库
cd ~
git clone https://github.com/bytedance/trae-agent.git
cd trae-agent

# 2. 装依赖（用阿里源）
uv venv
source .venv/bin/activate
uv pip install --index-url https://mirrors.aliyun.com/pypi/simple/ -e ".[test]"

# 3. 覆盖 trae_config.yaml + jarvis-trae.sh（从 Mark1 拉来）
cp /path/to/Mark1/tools/trae-agent/trae_config.yaml .
cp /path/to/Mark1/tools/trae-agent/jarvis-trae.sh .

# 4. 注入 API key（走环境变量，避免 key 进 git）
cp /path/to/Mark1/tools/trae-agent/.env.example .env
chmod 600 .env
# 编辑 .env 把 *** 占位符换成 OpenRouter 控制台的真 key

# 4.5. 跑
./jarvis-trae.sh "在当前目录写一个 hello.py"
```

## 安全设计

- `trae_config.yaml` 里 `api_key: ""` —— **不含 key**
- key 走 `OPENROUTER_API_KEY` 环境变量，从 `~/trae-agent/.env` 读
- `.env` 在 trae-agent 主仓库的 `.gitignore` 里（**已确认**），不会进 git
- Mark1 仓库里只有 `.env.example`（模板），**不含真 key**
- 即使 Mark1 仓库公开，**任何人在你电脑上跑 `./jarvis-trae.sh` 都通不过**——必须自己拿真 key

## 备选免费模型（OpenRouter 全 0$/M）

- `openai/gpt-oss-120b:free` ← 当前用的，OpenAI 开源 120B，1M context
- `nvidia/nemotron-3-super-120b-a12b:free`（快但中文啰嗦）
- 限流避开：`qwen/qwen3-coder:free`（Venice 端点常 429）、`meta-llama/llama-3.3-70b-instruct:free`（也 429）

## 烟测结果（2026-06-23）

| 任务 | 步骤 | tokens | 费用 | 结果 |
|---|---|---|---|---|
| `trae-cli run "写 hello.py"` | 5 | 13474 | $0 | ✅ |
| `trae-cli run "写 index.html"` | 8 | 26663 | $0 | ✅ |
| `trae-cli show-config` | — | — | — | ✅ mask 正确 |

## 已知问题

- `pyinstaller` + `google-genai` 装包时容易断流（60MB+），GLM-5.1 根本用不到，不必硬装
- trae-cli 默认 rich panel，timeout 90s 稳
- snap 版 Firefox 看不到 /tmp，必须用 `file:///home/.../*.html` 打开

## 关联文档

- `~/.openclaw/workspace/docs/install-registry.md` 2026-06-23 条目
- trae-agent 主仓库 README：https://github.com/bytedance/trae-agent
