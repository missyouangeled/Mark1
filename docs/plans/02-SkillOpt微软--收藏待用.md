## SkillOpt（微软）- 收藏待用

- **日期**：2026-06-17 调研
- **状态**：`收藏` — 当前不适用，等有自动评分 benchmark 后再评估
- **标签**：`AI工具`, `skill优化`, `微软`, `开源MIT`
- **仓库**：https://github.com/microsoft/SkillOpt
- **论文**：https://arxiv.org/abs/2605.23904
- **定位**：文本空间优化器，把 SKILL.md 当可训练参数，通过 rollout→reflect→edit→gate 四步循环自动打磨 agent skill 文档
- **核心数据**：52/52 全胜，GPT-5.5 +23.5，训练成本 $1-5/任务，零部署开销
- **不适用原因**：需要可自动评分的 benchmark（train/val/test split），当前 Mark42 面向开放域系统管理+日常对话，无可量化评分闭环
- **何时重评**：Mark42 有了 armor 压缩准确率 benchmark / engine 调度成功率 benchmark 等可评分任务后
> **方案索引**:`PLANS_INDEX.md` - 历史方案过长时先看这里,按主题 / 状态 / 适用时机定位到正确方案,避免误把旧方案当当前方案。

---
