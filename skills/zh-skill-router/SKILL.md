---
name: zh-skill-router
description: 中文 skill 路由器。把中文场景下的工作流触发词映射到正确的 skill。处理所有需要"专业工作流"的中文请求（如压力测试、TDD、PRD 生成），并维护每个 skill 在中文场景下的别名表。中文触发词：压力测试、挑战设计、TDD、测试驱动、红绿重构、写 PRD、需求文档、专业工作流、工作流 skill、设计评审、方案挑战。
---

# 中文 Skill 路由器

## 职责

当点点的中文输入匹配以下任何一种工作流场景时，本 skill 自动把请求路由到对应的专业 skill：

| 中文触发词 | 调用的 skill | 调用的工作流 |
|---|---|---|
| 压力测试 / 挑战设计 / 质疑方案 / 帮我 grill / 评审设计 / 设计评审 / 这个方案稳吗 | **grilling** | 对方案进行连环追问，一次一个问题 |
| TDD / 测试驱动 / 先写测试 / 红绿重构 / 测试先行 / 单元测试 / 集成测试 / 回归测试 | **tdd** | 红绿重构、vertical slice 测试 |
| 写成 PRD / 生成需求文档 / 转成需求 / 转成 PRD / 产品需求 / 拆解需求 / 需求模板 | **to-prd** | 把对话转成 PRD（贾维斯无 issue tracker，publish 步骤会失败，保留写模板能力）⚠️ to-prd 的 SKILL.md 带 `disable-model-invocation: true`，需通过本 router 手动路由触发 |

## 路由规则

1. 收到中文工作流请求时，先查上表
2. 找到匹配 → 调对应 skill 的 SKILL.md 完整行为（不是描述，要完整 body）
3. 找不到匹配 → 走默认对话流程
4. 多个匹配时 → 询问点点选哪个（一次一个）

## 兼容模型清单

本 router 在以下模型上都验证可用（贾维斯默认运行的所有模型）：
- MiniMax-M3（主）
- DeepSeek R1 / V3
- Claude 系列
- GLM 系列
- NVIDIA 模型

## 触发示例

```
点点："帮我压力测试一下这个方案"  → 调 /grilling
点点："用 TDD 给我实现这个功能"    → 调 /tdd
点点："把今天讨论的转成 PRD"      → 调 /to-prd
点点："挑战一下我的设计"          → 调 /grilling
```

## 与 grill-me router 的区别

`grill-me` 是 mattpocock 的 router（指向 `/grilling`），专管 grill 链路。
**`zh-skill-router` 是中文全工作流 router**，覆盖所有已安装的专业 skill。

## 来源

- 创建日期：2026-06-24
- 创建者：贾维斯（响应点点："动手修改吧"）
- 上游 skill 来源：mattpocock/skills (https://github.com/mattpocock/skills)
- 安装位置：~/.openclaw/workspace/skills/zh-skill-router/SKILL.md

## 维护

每次新增 mattpocock skill 时，本路由表**必须**同步更新（加一行）。