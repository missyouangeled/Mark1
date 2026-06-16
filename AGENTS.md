# AGENTS.md — 工作区总控（精简入口）

> ⚠️ 本文件是精简代理入口（≤80行）。
> 核心行为协议在 `rules/agents-core.md`（始终加载，≤120行）。
> 域规则在 `rules/chat.md` / `rules/work.md` / `rules/system.md` / `rules/safety.md`（按需触发）。
> 详细操作模板在 `rules/operations/`（按需读取）。

## 启动流程

0. 读 `ACTIVE_RULES.md`
0.1 读 `BOOT_INDEX.md`（分层加载入口）
0.2 读 `RULES_INDEX.md`（域规则网关）
1. 读 `SOUL.md`
2. 读 `USER.md`
3. 读 `HOST_CONTEXT.md`（如存在）
4. 读 `HANDOFF.md`（如存在）
5. 读今日+昨日 `memory/daily/` + session-backup 快照
6. 主会话另读 `MEMORY.md`
7. 读 `SKILL_CATALOG.md`
8. 读 `WORKSPACE_INDEX.md`

> 若 BOOT_INDEX.md 不可读：按步骤 1-8 直接逐条读。

## 分层加载体系

```
BOOT_INDEX.md  ─── 启动入口，指向下面各层
    │
    ├─ rules/agents-core.md  ─── ✅ 始终加载（核心行为协议）
    │
    ├─ 域规则（按第一条消息触发）：
    │     rules/chat.md      ─── 日常聊天
    │     rules/work.md      ─── 工作任务
    │     rules/system.md    ─── 系统操作
    │     rules/safety.md    ─── 高风险操作
    │
    └─ 操作模板（按需读取）：
          rules/operations/supervisor.md          ─── 监工/后台插播
          rules/operations/heartbeat.md           ─── 心跳/定时检查
          rules/operations/video-download.md      ─── 视频下载
          rules/operations/multi-machine.md       ─── 多机器同步
          rules/operations/session-cleanup.md     ─── 会话清理
          rules/operations/foreground-background.md ─── 前台/后台
```

## 关键文件速查

| 需求 | 文件 |
|---|---|
| 人格 | `SOUL.md` |
| 用户 | `USER.md` |
| 长期记忆 | `MEMORY.md` |
| 工具/环境 | `TOOLS.md` |
| 技能目录 | `SKILL_CATALOG.md` |
| 工作区导航 | `WORKSPACE_INDEX.md` |
| 项目索引 | `PROJECT_INDEX.md` |
| 方案存档 | `PLANS.md` |
| 安装记录 | `docs/install-registry.md` |
| 崩坏案例 | `docs/对系统操作必须要参考的崩坏案例.md` |

## 基本规则（摘要）

- 只用中文。交付前自检。
- 修改任务：先查现有能力 → 再查冲突 → 做成补丁 → 留痕
- 记忆：人物→people.md / 回忆→stories.md / 每日→daily/
- 方案/系统/每日三者不混
- 发送邮件/推文/公开内容前先问
- 高风险系统操作前读崩坏案例
- 群聊：质量>数量，用 emoji 反应

---

*本文件由 Mark42 v2.2 铠甲分层加载体系维护。详细规则见 `rules/agents-core.md`。*
