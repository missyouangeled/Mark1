# 第二阶段索引细化设计（2026-06-08）

## 目标

在不破坏现有启动链路与总导航的前提下，为真正过长、最容易找不到的区域补充二级索引。

## 现状判断

- `WORKSPACE_INDEX.md`：91 行，体量合适，继续保持总地图角色
- `TOOLS.md`：646 行，脚本/服务/凭据指针容易埋深
- `PLANS.md`：3713 行，历史方案过长，且存在“旧方案被误当当前方案”的风险
- `memory/daily/`：按日期散落，适合补“主题 → 日期”锚点表
- `MEMORY.md`：152 行，仍可控，不拆正文

## 方案

新增三个二级索引：

1. `TOOLS_INDEX.md`
   - 给 `TOOLS.md` 做二级目录
   - 聚焦：自动化、监工、语音、视频下载、凭据指针

2. `PLANS_INDEX.md`
   - 给 `PLANS.md` 做高价值方案目录
   - 每条附：标题、状态、标签、何时读取
   - 只记入口，不复制方案正文

3. `memory/INDEX.md`
   - 做“主题 → 日期/文件”的记忆锚点表
   - 聚焦：Unity、QMD/memory_search、监工、语音、OpenCode Zen 备用 key

## 交叉补链

- `WORKSPACE_INDEX.md`：加入三个二级索引入口
- `TOOLS.md`：顶部快速导航加入 `TOOLS_INDEX.md`
- `PLANS.md`：顶部加入 `PLANS_INDEX.md`
- `MEMORY.md`：快速查找加入 `memory/INDEX.md` 与 `PLANS_INDEX.md`

## 验证方式

用以下 5 个问题做最小验收：

1. OpenCode Zen 备用 key 放哪？
2. Unity Wall 的 PaintWhite 问题在哪天？
3. 监工规则和相关脚本去哪找？
4. 语音默认模板 / 语音主线去哪找？
5. 以前的双机协同方案在哪？

若都能通过总导航 → 二级索引 → 原文件的链路快速定位，则第二阶段验收通过。
