# 方案 44：火山方舟 Agent Plan 接入 GLM-5.2

> **日期**：2026-07-16
> **状态**：已完成
> **关联**：MEMORY.md API 路由规则 / Mark42 v3-4 advisor

## 背景

点点买了火山方舟 Agent Plan 套餐。需要接入 OpenClaw 作为 fallback 模型 + Mark42 advisor。

## 关键发现

1. Coding Plan 和 Agent Plan 用不同 endpoint：`coding/v3` vs `plan/v3`
2. Coding Plan 不允许通用 API 调用（违规封号），Agent Plan 允许 OpenClaw 接入
3. GLM-5.2 真实版本号 `glm-5-2-260617`，1M 上下文，支持 thinking
4. GLM-5.2 返回可能包 markdown ```json 包裹（需剥离）

## 接入配置

- OpenClaw: volcengine-agent provider, fallback #4/#5
- Mark42: model.yaml advisor.enabled=true, model=glm-5.2
- key 备份: ~/.openclaw/credentials/.volcengine-agent.key

## 验证

- curl 烟测 ✅ (HTTP 200, content="您好，今天是星期日。")
- OpenClaw models list ✅ (volcengine-agent/glm-5.2 configured)
- advisor ping ✅ (approve/1.0/8s)
- 429 限流降级 ✅ (fallback to ask_user)
