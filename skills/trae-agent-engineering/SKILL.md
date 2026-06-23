---
name: "trae-agent-engineering"
description: "封装 trae-cli 调用流程：检查配置、用 wrapper 调、验证轨迹与改动。贾维斯工程任务默认走这条。"
---

# trae-agent-engineering Skill — 贾维斯调 trae-agent 的标准流程

## 0. 这是什么

封装 trae-cli（bytedance 开源）的标准调用流程，让贾维斯在"工程任务"（改代码、加功能、跑测试、修 bug、重构）里：

1. **能自动走**：不需要每次重新讲怎么调 trae
2. **能少出错**：把今天踩过的 3 个坑（401、404、必填字段）固化进 skill
3. **能审计**：每次调用都看轨迹文件、改动文件、diff

**触发条件**（任一即可）：

- 用户说"让 trae 改"、"调 trae"、"用 trae 重构"、"修这个 bug"、"加这个功能"、"跑测试"
- 任务涉及"工程目录里的多文件改动"
- 用户说"这个是大型项目，启用 trae"

**不触发**：

- 单文件改一句话 → 直接 edit
- 跑命令查状态 → 直接 exec
- 写文案/聊天 → 不走 trae

## 1. 调 trae-agent 的标准流程（已固化）

### 步骤 1：确认 trae 已就位

```bash
test -d ~/trae-agent || { echo "trae-agent 未装，参考 PLANS #34 装"; return 1; }
test -x ~/trae-agent/.venv/bin/trae-cli || { echo "trae-cli 不在 venv"; return 1; }
test -f ~/trae-agent/trae_config.yaml || { echo "trae_config.yaml 缺失"; return 1; }
```

### 步骤 2：验证配置合法

```bash
cd ~/trae-agent && source .venv/bin/activate
trae-cli show-config | head -20
# 期望看到：trae_agent_model / deepseek-v4-flash / provider: openrouter
```

### 步骤 3：用 wrapper 调 trae

**永远用 wrapper**，不要直接调 trae-cli：

```bash
~/trae-agent/jarvis-trae.sh "<自然语言任务>"
```

wrapper 内容：

```bash
#!/bin/bash
set -e
cd ~/trae-agent
source .venv/bin/activate
exec trae-cli run "$@"
```

### 步骤 4：验证

```bash
ls -lat ~/trae-agent/trajectories/*.json | head -3
cat /path/to/modified/file | head -30
```

### 步骤 5：报告

- token 成本（从轨迹读 usage，按 V4 Flash 价估算）
- 修改了哪些文件（git diff --stat）
- 是否需要 commit（告诉用户，等用户决定）

## 2. 今天踩过的 3 个坑

| 坑 | 症状 | 修法 |
|---|---|---|
| **401** | `Error code: 401` / `Your api key: ****HERE is invalid` | 真 key，从 `~/.openclaw/openclaw.json` 第 561~564 行填 |
| **404 / model not found** | `provider: openai` 走 `responses.create()`（OpenAI 5.x 专有端点） | 改 `provider: openrouter`（走 `chat.completions`） |
| **缺字段** | `ModelConfig.__init__() missing 2 required positional arguments: 'top_k' and 'parallel_tool_calls'` | models 块加 `top_k: 0` + `parallel_tool_calls: true` |
| **Lakeview** | `Lakeview is enabled but no lakeview config provided` | agents 块加 `enable_lakeview: false` |

## 3. trae_config.yaml 标准模板

```yaml
agents:
  trae_agent:
    enable_lakeview: false
    model: trae_agent_model
    max_steps: 30
    tools:
      - bash
      - str_replace_based_edit_tool
      - sequentialthinking
      - task_done

model_providers:
  deepseek:
    api_key: "***"
    provider: openrouter
    base_url: "https://api.deepseek.com/v1"

models:
  trae_agent_model:
    model_provider: deepseek
    model: deepseek-v4-flash
    max_tokens: 4096
    temperature: 0.3
    top_p: 1
    top_k: 0
    max_retries: 5
    parallel_tool_calls: true
```

## 4. 走 trae 还是不走 trae

```
任务来 → 是工程任务吗？
  ├─ 不是（聊天/查东西/单文件一句话） → 直接 exec/edit
  └─ 是 → 是大型项目吗？
        ├─ 不是（单文件 bug fix） → 直接 edit
        └─ 是（多文件/跨目录/重构） → 走 trae
```

## 5. 资源

- 仓库：`bytedance/trae-agent`（⭐ 11.7k，2026-06-22 验证）
- 安装方案：`docs/plans/34-2026-06-23Trae-Linux-国内版--trae-agent-CLI-待装方案.md`
- 烟测报告：`docs/plans/34-trae-agent-烟测报告-2026-06-23.md`

## 6. 已知限制

- HTTP server 模式不可用（`server/Readme.md` 明说 under construction）
- v0.1.0 还在早期
- 轨迹文件只在本地
- trae_config.yaml 里的真 key 还没移到环境变量（P0 待办）
