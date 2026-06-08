# PLANS_INDEX.md — 历史方案索引

> 这是 `PLANS.md` 的二级索引。只记录方案标题、状态、标签和何时读取，不复制正文。

## 方案状态说明

| 状态 | 含义 |
|---|---|
| `active` | 当前仍可继续推进或仍推荐参考 |
| `reference` | 历史参考，不代表当前默认落地 |
| `done` | 已完成收口，可作为结果参考 |
| `paused` | 暂停，等待用户继续 |
|

## 高价值方案目录

| 日期 | 主题 | 状态 | 标签 | 什么时候读 |
|---|---|---|---|---|
| 2026-05-19 | broker / infos-handle v1 收口说明 | `done` | OpenClaw, broker, infos-handle | 查当前正式内部信息系统口径时 |
| 2026-05-19 | infos-handle 增强轮 4 方向收口 | `done` | OpenClaw, infos-handle | 查增强轮收口范围时 |
| 2026-05-18 | infos-handle phase2 最小增强落点 | `reference` | OpenClaw, infos-handle | 查 phase2 设计来源时 |
| 2026-05-13 | 前台独立监工方案（脚本监工 + 前台状态面板） | `reference` | 监工, 前台, 状态面板 | 查监工体系设计来源时 |
| 2026-04-29 | 云服务器部署方案 | `reference` | 部署, 云服务器 | 查云部署路线时 |
| 2026-04-29 | ROG 掌机（Windows）部署方案 | `reference` | 掌机, Windows, 部署 | 查掌机单机方案时 |
| 2026-04-30 | 双机协同推荐方案（公司机主脑 + 掌机远程入口） | `reference` | 多设备, 双机协同 | 查公司机/掌机协同时 |
| 2026-04-30 | 三设备协同方案（微信总控 + 掌机对话 + 多设备执行） | `reference` | 多设备, 微信 | 查更复杂多端协同时 |
| 2026-05-08 | ChatTTS encoder 补全与 zero-shot 恢复方案 | `reference` | 语音, ChatTTS | 查 ChatTTS 深层恢复路线时 |
| 2026-05-09 | 主会话语音回复升级为“流式直聊”的方案 | `reference` | 语音, 主会话 | 查语音主线演进时 |
| 2026-05-11 | 当前设备语音提速的最小实施方案 | `reference` | 语音, 提速 | 查低风险提速时 |
| 2026-05-12 | 主会话语音模板不动前提下的“更像人 / 更有情感 / 更细腻”研究结论 | `reference` | 语音, 听感 | 查语音风格调优时 |
| 2026-05-09 | FFmpeg + Gemma 4 31B 视觉陪看片方案 | `paused` | 视觉, FFmpeg, Gemma | 继续视觉陪看片时 |
| 2026-05-15 | infos-handle 插层路线（broker 数据中心纯化） | `reference` | OpenClaw, broker | 查分层收敛路线时 |
| 2026-05-14 | 工作层 / 数据层 / 渲染层分层路线（当前先升级 broker 为数据源） | `reference` | 架构, 分层 | 查整体分层方向时 |
| 2026-05-22 | 贾维斯视觉识别能力调研 | `reference` | 视觉, 能力调研 | 查视觉能力方向时 |
| 2026-05-22 | 贾维斯语音架构重构 | `reference` | 语音, 架构 | 查语音大方向时 |
| 2026-05-22 | 贾维斯自进化方案（self-improvement + capability-evolver 融合） | `reference` | 自进化, 学习 | 查自进化方向时 |
| 2026-05-25 | Agent-S GUI Agent — 待装机方案 | `paused` | Agent, GUI | 准备装 Agent-S 时 |
| 2026-05-25 | tavily-key-generator — API Key 自动注册器 | `paused` | API, 自动注册 | 继续这条工具线时 |
| 2026-05-25 | AI Agent 接单赚钱 — 待启动方案 | `paused` | 商业化 | 讨论副业/变现时 |
| 2026-05-25 | 分布式 Agent 算力网络设计 | `reference` | Agent, 分布式 | 查算力网络思路时 |
| 2026-05-25 | 贾维斯语音随身助手 — 蓝牙耳机实时对话方案 | `paused` | 语音, 随身助手 | 讨论耳机实时对话时 |
| 2026-05-26 | 统一工作调度层方案 | `reference` | 调度, 架构 | 查任务调度层设计时 |
| 2026-05-26 | 任务调度器（Task Scheduler）详细设计 | `reference` | 调度器, watcher | 查调度器细节时 |
| 2026-05-29 | QMD 语义搜索排查结论 | `done` | memory_search, QMD | 查 memory_search / QMD 路线时 |

## 使用提醒

- 先看这里决定要读哪条方案，再去 `PLANS.md` 读正文
- 若某条方案已经被当前正式架构替代，不要默认拿旧方案当现行方案
- 新方案写进 `PLANS.md` 后，记得同步补一条到这里
