# WORKSPACE_INDEX.md — 工作区查找导航

> 这是工作区的**总导航页**。只负责告诉你“某类信息应该去哪找”，不存放长规则、长记忆、凭据明文。
> 任何模型换上来后，如果已经读完启动必读文件、但还需要快速定位资料，请读这页。

## 使用原则

- **本页只做索引，不重复存事实**：详细内容留在原文件
- **敏感信息只记路径，不记明文**
- **规则 / 记忆 / 工具 / 项目 / 方案分层存放，不混写**

## 1. 当前任务先读什么

| 当前任务 | 优先读取 |
|---|---|
| 日常聊天 / 陪伴 / 情绪承接 | `RULES_INDEX.md` → `rules/chat.md` → `MEMORY.md` |
| 工作任务 / 修改脚本 / 项目推进 | `RULES_INDEX.md` → `rules/work.md` → `PROJECT_INDEX.md` |
| 系统修复 / 配置 / 服务 / 补丁 | `RULES_INDEX.md` → `rules/system.md` + `rules/work.md` → `TOOLS.md` |
| 高风险动作 / 权限 / 外部操作 / 稳定性风险 | `rules/safety.md` → `docs/对系统操作必须要参考的崩坏案例.md` |
| CPU 过载 / 系统卡顿 / 临时处理 | `docs/通用-CPU负载过高临时处理方案.md` → `scripts/openclaw-cpu-emergency.py --diagnose` |
| Unity 路径过长 / rename 风险 | `docs/通用-Unity资产路径过长风险分析与应对方案.md` |
| 找历史方案 / 技术决策 | `PLANS.md` |
| 找项目入口 / 项目目录 | `PROJECT_INDEX.md` |
| 找本地脚本 / 服务 / 维护入口 | `TOOLS.md` / `TOOLS_INDEX.md` |
| 找 API key / SSH / 本地凭据路径 | `TOOLS_INDEX.md` → `Local-only credential pointers` |
| 找长期偏好 / 用户设定 | `MEMORY.md` / `memory/INDEX.md` |
| 找人物关系 / 某个人是谁 | `memory/people.md` |
| 找人生回忆 / 千千相关故事 | `memory/stories.md` |
| 找今天或最近发生了什么 | `memory/daily/YYYY-MM-DD.md` + `memory/daily/YYYY-MM-DD-transcript.md` |
| 找技能与适用场景 | `SKILL_CATALOG.md` |

## 2. 关键文件职责

| 文件 | 职责 |
|---|---|
| `AGENTS.md` | 启动顺序、整体工作纪律、长期工程方法 |
| `RULES_INDEX.md` | 规则路由器：按任务类型决定该读哪些规则 |
| `rules/chat.md` | 日常聊天、陪伴、语音、千千 persona 等 |
| `rules/work.md` | 工作任务、补丁流程、批量操作、项目执行规则 |
| `rules/system.md` | 系统操作、监工、设备识别、维护规则 |
| `rules/safety.md` | 高风险动作、凭据隐私、系统稳定性边界 |
| `MEMORY.md` | 主会话长期偏好与关系上下文的快速索引 |
| `TOOLS.md` | 本机脚本、服务、路径、维护入口、凭据指针 |
| `TOOLS_INDEX.md` | `TOOLS.md` 的二级索引：工具、服务、凭据指针快速定位 |
| `PROJECT_INDEX.md` | 项目名称、目录、别名、常用入口 |
| `PLANS.md` | 历史方案、调研结论、技术决策 |
| `PLANS_INDEX.md` | `PLANS.md` 的二级索引：方案标题、状态、何时读取 |
| `SKILL_CATALOG.md` | Skill 能力目录与触发条件 |
| `memory/INDEX.md` | 记忆主题锚点索引：某件事发生在哪天 |

## 3. 常见查找路线

### 找 CPU 过载怎么处理
- 一键诊断：`python3 scripts/openclaw-cpu-emergency.py --diagnose`
- 全自动修复：`python3 scripts/openclaw-cpu-emergency.py --repair`
- 详细方案：`docs/通用-CPU负载过高临时处理方案.md`

### 找 Unity 那些整理/重命名的事
- 项目入口：`PROJECT_INDEX.md` → `Unity 模型整理`
- 最近执行记录：`memory/daily/2026-06-05.md`
- 若找脚本/大工程规则：`TOOLS.md`（搜索 `Unity` / `大工程` / `rename`）

### 找 OpenCode / 备用模型 / API key 指针
- 先看 `TOOLS_INDEX.md` → `Local-only credential pointers`
- 再跳到 `TOOLS.md` 看路径和用途边界
- 这里只记路径和用途边界，不在索引页写密钥明文

### 找系统修复入口
- 先看 `rules/system.md` / `rules/safety.md`
- 再看 `TOOLS.md` 中对应脚本与文档入口
- 任何高风险系统动作前，都要先看：`docs/对系统操作必须要参考的崩坏案例.md`

### 找视频下载相关入口
- 工作规则：`rules/work.md`
- 实际工具与脚本入口：`TOOLS.md`
- 详细流程：`docs/通用-视频平台下载工作流.md`

### 找语音 / TTS / ChatTTS / XTTS
- 偏好与长期规则：`MEMORY.md` / `memory/INDEX.md`
- 本机部署与路径：`TOOLS_INDEX.md` → `TOOLS.md`
- 相关方案：`PLANS_INDEX.md`
- 相关 Skill：`SKILL_CATALOG.md`

## 4. 新内容应该记到哪里

| 新内容类型 | 应写入 |
|---|---|
| 新用户偏好 / 长期规则 | `MEMORY.md`（必要时同步 `rules/`） |
| 新人物 | `memory/people.md` |
| 新回忆 / 人生感慨 | `memory/stories.md` |
| 今日事项 / 今天聊了什么 | `memory/daily/YYYY-MM-DD.md` |
| 新项目 | `PROJECT_INDEX.md` |
| 新脚本 / 服务 / 本地路径 / 凭据指针 | `TOOLS.md` |
| 新凭据明文 | `credentials/`（只本地保存，不进 Git） |
| 新技术方案 / 调研结论 | `PLANS.md` |
| 新补丁 / 维护变更 | `docs/通用-OpenClaw-补丁变更流水.md` |
| 当前接力 / 继续做什么 | `HANDOFF.md` |

## 5. 边界提醒

- 不要把 `WORKSPACE_INDEX.md` 变成第二个 `AGENTS.md` 或第二个 `MEMORY.md`
- 不要在索引页复制大量正文；只写“去哪找”
- 目录和文件职责一旦改变，要同步更新这里
