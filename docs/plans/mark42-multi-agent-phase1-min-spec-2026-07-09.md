# Mark42 多 Agent 支持最小设计（Phase 1）

日期：2026-07-09
状态：待实现
目标版本：Mark42 Phase 1

## 1. 目标

把 Mark42 从“默认只服务 main 主会话”的实现，升级成“可以面向多个 OpenClaw agent / session 工作”的最小可用版本。

本阶段只解决三个问题：

1. 消除代码里对 `agent:main:main` 和 `~/.openclaw/agents/main/...` 的硬编码依赖
2. 让 `context-safety` / `armor` 能显式指定目标 agent 或 session
3. 为后续角色分工（main / researcher / coder）预留配置入口

## 2. 本阶段不做什么

以下内容明确不在 Phase 1：

- 不做全自动多 Agent 编排
- 不让 agent 之间自动长链互聊
- 不做复杂任务自动拆分给 researcher/coder 再自动汇总
- 不改 Mark42 的 broker 事件总线语义
- 不强行改变当前默认工作方式（默认仍可继续服务 main）

## 3. 现状问题

当前工作区内已有多 agent 定义：

- `main`
- `researcher`
- `coder`

但 Mark42 仍存在单 Agent 假设：

- `scripts/mark42_modules/armor.py`
  - compact 时写死 `agent:main:main`
- `scripts/mark42_modules/context_safety.py`
  - 会话存储路径写死 `~/.openclaw/agents/main/sessions/sessions.json`
  - 当前 session override 读取写死 `data["agent:main:main"]`
- `scripts/mark42_modules/utils.py`
  - `_find_active_session()` 只扫描 `~/.openclaw/agents/main/sessions`

此外，OpenClaw 配置虽然定义了 `researcher` / `coder`，但当前权限仍偏单 Agent：

- `agents.defaults.subagents.allowAgents = ["main"]`
- `tools.agentToAgent.allow = ["main"]`

这意味着多 Agent 运行底子已有，但还没完全放通，也还没被 Mark42 正式消费。

## 4. 设计原则

### 4.1 默认行为保持不变

如果用户不传任何 agent / session 参数：

- Mark42 继续默认服务 `main`
- 当前已有命令不应因多 Agent 改造而失效

### 4.2 配置优先于硬编码

所有 session / agent 解析都应该通过统一函数完成，而不是散落在各模块里拼路径、写字符串。

### 4.3 agent 与 session 分层

需要区分两个概念：

- `agent_id`：如 `main` / `researcher` / `coder`
- `session_key`：如 `agent:main:main`

Phase 1 优先支持：

- 按 `agent_id` 指定
- 内部解析到该 agent 的默认主 session key

必要时允许显式传 `session_key`，但不是第一优先接口。

## 5. 最小配置模型

建议在 Mark42 内引入以下最小配置：

```json
{
  "multiAgent": {
    "enabled": true,
    "defaultAgent": "main",
    "managedAgents": ["main", "researcher", "coder"]
  }
}
```

说明：

- `enabled`
  - 只是 Mark42 自己的多 Agent 开关
  - 不替代 OpenClaw 的 `agentToAgent` 或 `subagents` 权限
- `defaultAgent`
  - 所有未指定 agent 的命令默认落到这个 agent
- `managedAgents`
  - 允许 Mark42 操作的 agent 白名单
  - 后续可作为 CLI 校验依据

## 6. 统一解析接口

建议新增一组统一函数，放到 `utils.py` 或专门的新模块中：

- `resolve_mark42_agent(agent: str | None) -> str`
  - 返回最终 agent id
- `resolve_agent_session_key(agent: str | None) -> str`
  - 例如 `main -> agent:main:main`
- `get_agent_sessions_dir(agent: str | None) -> Path`
  - 例如 `~/.openclaw/agents/<agent>/sessions`
- `find_active_session(agent: str | None) -> Path | None`
  - 在指定 agent 的 sessions 目录内找活跃 session

现有 `_find_active_session()` 应改为支持 agent 参数，而不是永远扫描 main。

## 7. CLI 变更范围（Phase 1）

### 7.1 context-safety

新增：

- `context-safety status --agent <id>`
- `context-safety verify --agent <id>`

行为：

- 默认：`--agent main`
- info 项中的 `currentSession.modelOverride` 改为读取对应 agent 的 sessions store

注意：

- `apply` 主要改的是全局 `openclaw.json` 基线，不是 per-agent 配置
- 所以 `apply --agent ...` 在 Phase 1 可以不做，或者接受参数但仅用于展示上下文

### 7.2 armor

新增：

- `armor --check --agent <id>`
- `armor --compress --agent <id>`
- `armor --dry-run --agent <id>`

行为：

- `_find_active_session(agent)` 在对应 agent 下找活跃 session
- `openclaw sessions compact` 的目标 session key 改为解析后的 `agent:<id>:main`

### 7.3 status

Phase 1 可以先不做多 agent 聚合大盘。

先保持：

- 默认仍展示当前默认 agent 的状态
- 如要扩展，最多增加 `status --agent <id>`

不在本阶段做：

- 一个面板里同时展示所有 agent 的并行状态

## 8. OpenClaw 配置联动

Mark42 Phase 1 要能工作，至少还需要 OpenClaw 侧具备：

- `subagents.allowAgents` 包含 `main/researcher/coder`
- `agentToAgent.allow` 包含 `main/researcher/coder`

这部分属于运行时依赖，不一定要在第一刀代码里自动改，但至少要：

- 在 `context-safety verify` 或新检查项里提示
- 或作为文档前置条件明确写出

## 9. 风险点

### 9.1 “agent” 和 “session” 混淆

如果只传 agent，但该 agent 下存在多个活跃 session，Phase 1 的行为必须简单清楚：

- 默认只认该 agent 的主 session 目录中的“最近活跃 session”
- 不试图解决多 session 编排问题

### 9.2 全局配置与 per-agent 配置混用

`context-safety apply` 改的是全局配置基线，不是某个 agent 私有配置。
因此不能让用户误以为 `--agent researcher` 会写 researcher 专属的 pruning 设置。

### 9.3 verify 语义扩张过快

Phase 1 的 `verify --agent` 只负责验证：

- 该 agent 的 session store 是否可读
- 对应 override 是否可读
- 对应 compact 路径是否能工作

不在本阶段验证复杂 A2A 行为。

## 10. 最小验收

### 10.1 静态验收

- `py_compile` 通过
- 默认命令行为不回归

### 10.2 CLI 验收

至少验证：

```bash
python3 scripts/mark42.py context-safety status
python3 scripts/mark42.py context-safety status --agent main
python3 scripts/mark42.py context-safety status --agent researcher
python3 scripts/mark42.py armor --check --agent main
python3 scripts/mark42.py armor --dry-run --agent main
```

如果 researcher 会话存在，再补：

```bash
python3 scripts/mark42.py armor --check --agent researcher
```

### 10.3 回归验收

- `bash tools/mark42-systemd/verify.sh` 继续通过

## 11. 推荐实施顺序

1. 先加统一 agent/session 解析函数
2. 改 `context_safety.py`
3. 改 `armor.py`
4. 改 CLI 参数接线
5. 最后再考虑把 verify 扩成多 agent 检查

## 12. Phase 2 展望

Phase 2 才考虑：

- agent 角色路由建议（researcher / coder）
- heavy 任务指定 agent 执行
- engine loop 与 agent 角色绑定
- 多 agent 聚合状态看板
