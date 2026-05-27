# GPT-5.5（Copilot）接入 OpenClaw 设计与实施计划

- 日期：2026-05-27
- 适用范围：公司（Linux）/ 当前这台 OpenClaw 实例
- 目标：把 `github-copilot/gpt-5.5` 加入 OpenClaw 允许模型列表，让主会话和后续会话都可以随时切换使用；默认模型先保持不变。

## 现状

- 当前默认模型：`deepseek/deepseek-v4-pro`
- 当前已存在 Copilot 授权：`github-copilot:github`
- 当前 `agents.defaults.models` 已启用 allowlist，因此新模型若不加入 allowlist，会出现“Model is not allowed”。

## 方案选择

### 方案 A（采用）：只加入 `github-copilot/gpt-5.5` 到 allowlist
- 优点：最小改动、风险低、不影响当前默认模型和既有工作流
- 缺点：如果未来还想自动看到更多 Copilot 新模型，还要继续单独加入

### 方案 B：加入 `github-copilot/*` provider wildcard
- 优点：后续 Copilot 新模型会自动出现在模型选择中
- 缺点：放开范围更大，模型列表会变动，不够克制

### 方案 C：直接把默认模型改成 `github-copilot/gpt-5.5`
- 优点：立刻全局默认走 GPT-5.5
- 缺点：会改变当前默认工作流和成本/响应特征，本次先不默认这样做

## 本次实施

1. 用 `openclaw config set ... --merge --dry-run` 先验证配置写法
2. 将 `github-copilot/gpt-5.5` 加入 `agents.defaults.models`
3. 运行 `openclaw config validate`
4. 运行 `openclaw models status --json`，确认 allowlist 已出现该模型
5. 补写变更流水和非正式修改备忘录

## 验证标准

- `openclaw config validate` 成功
- `openclaw models status --json` 的 `allowed` 数组中包含 `github-copilot/gpt-5.5`
- 默认模型仍为 `deepseek/deepseek-v4-pro`
