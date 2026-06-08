# 记忆与工具索引层设计（2026-06-08）

## 目标

解决“换模型后读不全、找不到、入口散落”的问题，给工作区补一层 **极小、稳定、可跳转** 的索引入口。

## 现状

当前已经有几层入口，但还不够收口：

- `RULES_INDEX.md`：负责按对话类型路由规则，做得对，但只覆盖规则层
- `SKILL_CATALOG.md`：负责技能目录，做得对，但不覆盖本地脚本/凭据/记忆档案
- `PROJECT_INDEX.md`：负责项目入口，做得对，但不覆盖系统维护/个人记忆/工具落点
- `MEMORY.md`：长期偏好很多，但偏向内容摘要，不是“去哪找什么”的导航页
- `TOOLS.md`：本地脚本/服务/凭据很多，但内容越来越长，缺少“先看哪块”的总导航

用户当前核心痛点：
1. 换模型后，不知道该读哪几个文件
2. 记录散落在多份文件里，要靠搜索和运气拼出来
3. 有些关键落点（如凭据指针、维护脚本、人物档案）没有单独的索引入口

## 方案候选

### 方案 A：继续扩写 `RULES_INDEX.md`

**做法**：把记忆/工具/项目/凭据入口都塞进 `RULES_INDEX.md`

**优点**：
- 入口最集中
- 启动时一定会读到

**缺点**：
- `RULES_INDEX.md` 会失去“极小路由器”特性
- 规则层和资源层混在一起，后续越长越乱

**结论**：不推荐。

---

### 方案 B：新建统一导航页 `WORKSPACE_INDEX.md`（推荐）

**做法**：新增一个真正的“工作区总导航”，只做索引，不承载长规则。

内容分 6 块：
1. 启动必读（RULES / SOUL / USER / MEMORY / SKILL）
2. 规则入口（chat/work/system/safety）
3. 记忆入口（MEMORY / people / stories / daily）
4. 工具与环境入口（TOOLS / docs / scripts / credentials 指针）
5. 项目入口（PROJECT_INDEX / 主要项目）
6. 常见任务 → 应先看哪些文件（如“工作任务”“系统修复”“日常聊天”“找凭据”）

**优点**：
- 不破坏现有结构
- 换模型时只要读 1 页，就知道去哪里找
- 便于持续扩展，不污染规则入口
- 也能作为 AGENTS.md / 启动流程的二级跳转页

**缺点**：
- 多了一个文件，需要把它接入启动链路

**结论**：推荐。

---

### 方案 C：做多个小索引（memory index / tools index / docs index）

**做法**：分别新增 `memory/INDEX.md`、`docs/INDEX.md`、`tools/INDEX.md`

**优点**：
- 各目录都自洽
- 适合后期继续细分

**缺点**：
- 现在就这么做会一下增加太多入口
- 还得再有一个总索引把它们串起来

**结论**：可作为第二阶段，不适合现在先上。

## 推荐实施

先做 **方案 B**，控制在最小变更：

### 新增
- `WORKSPACE_INDEX.md`

### 更新
- `AGENTS.md`：在启动顺序或相关说明里补一句“读完基础文件后，如需快速导航，读 `WORKSPACE_INDEX.md`”
- `RULES_INDEX.md`：底部追加一句“规则之外的记忆/工具/项目导航见 `WORKSPACE_INDEX.md`”
- `MEMORY.md`：在顶部索引区补一条“工作区总导航见 `WORKSPACE_INDEX.md`”
- `TOOLS.md`：顶部或合适位置补一句“快速导航见 `WORKSPACE_INDEX.md`”

## `WORKSPACE_INDEX.md` 结构草案

```md
# WORKSPACE_INDEX.md — 工作区总导航

## 1. 启动必读
- RULES_INDEX.md
- SOUL.md
- USER.md
- MEMORY.md（仅主会话）
- SKILL_CATALOG.md

## 2. 规则入口
- rules/chat.md
- rules/work.md
- rules/system.md
- rules/safety.md

## 3. 记忆入口
- MEMORY.md
- memory/people.md
- memory/stories.md
- memory/daily/YYYY-MM-DD.md

## 4. 工具与环境入口
- TOOLS.md
- docs/install-registry.md
- docs/通用-OpenClaw-当前正式架构状态.md
- credentials/（只记指针，不记明文）

## 5. 项目入口
- PROJECT_INDEX.md
- Unity 模型整理
- 纳达尔星项目

## 6. 常见任务 → 去哪找
- 工作任务
- 系统修复
- 日常聊天
- 找 API key / SSH / 本地路径
- 找方案 / 历史决策
```

## 验证方式

1. 读 `WORKSPACE_INDEX.md`，确认一页内能回答：
   - “找工作规则看哪”
   - “找长期记忆看哪”
   - “找本地凭据指针看哪”
   - “找项目入口看哪”
2. 再从 `AGENTS.md` / `RULES_INDEX.md` / `MEMORY.md` / `TOOLS.md` 任一入口出发，确认都能跳到 `WORKSPACE_INDEX.md`
3. 文件总量控制：新增 1 个索引文件 + 小范围补链，不新造复杂体系

## 推荐结论

**先落地 `WORKSPACE_INDEX.md`，做“总导航 + 少量反向链接”**。

这是最小改动、收益最大的做法。
