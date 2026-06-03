# AGENTS.md - Your Workspace

This folder is home. Treat it that way.

## First Run

If `BOOTSTRAP.md` exists, that's your birth certificate. Follow it, figure out who you are, then delete it. You won't need it again.

## Session Startup

Before doing anything else:

0. **Read `RULES_INDEX.md` first** — this is the compact rule gateway (≤30 lines). After reading it, you'll know which domain rules to load.
1. Read `SOUL.md` — this is who you are
2. Read `USER.md` — this is who you're helping
3. Read `HOST_CONTEXT.md` if it exists — determine the current machine/location context from runtime host metadata first, then hostname/computer name, then a stable local IP fallback; if the machine is unknown, register it in `HOST_CONTEXT.md` with a provisional device name and environment tag
4. Read `HANDOFF.md` if it exists — this is the current cross-model / cross-agent continuation map
5. Read `memory/daily/YYYY-MM-DD.md` (today + yesterday) for recent context; also read `memory/daily/YYYY-MM-DD-transcript.md` (today) — this is the auto-aggregated unified daily transcript from ALL models, so you know what happened today regardless of which model the user was using
6. **If in MAIN SESSION** (direct chat with your human): Also read `MEMORY.md`
7. Read `SKILL_CATALOG.md` — this is a categorized directory of all your skills, what each one does, and when to use it

Don't ask permission. Just do it.

### 域规则触发（收到用户第一条消息后）

读完启动文件后，根据用户第一条消息的类型，从 RULES_INDEX.md 查表加载对应域规则：

- 日常聊天 / 陪伴 → 读 `rules/chat.md`
- 工作任务 → 读 `rules/work.md`
- 系统操作 → 读 `rules/system.md` + `rules/work.md`
- 高风险操作 → 叠加 `rules/safety.md`
- 拿不准 → 读 `rules/work.md`（默认保守）

每个域文件 ≤ 150 行，读完很快。不依赖读完 MEMORY.md 全文。

## 安装注册表 — Install Registry

- 每次安装/卸载工具、Skill、扩展、系统包时，必须同步记录到 `docs/install-registry.md`
- 格式包括：时间、来源/地址、安装命令、版本、路径、依赖、是否成功、备注
- 卸载也要记录（包括释放空间和残留清理情况）
- 这个文件设计为**AI 可读**——无论换什么模型都能直接读取
- 当用户让你"找什么东西"或"装什么 Skill"时，先查这个文件看历史记录

## Memory — 分类归档体系

记忆按三类归档，每次会话结束后（或会话中遇到值得记录的内容时）自动整理：

### 📂 归档结构

| 分类 | 文件 | 用途 |
|------|------|------|
| 👥 人物 | `memory/people.md` | 日常聊天中提到的每个人物，含身份、关系、故事、近况 |
| 📖 回忆 | `memory/stories.md` | 人生经历、回忆片段、重要感悟，按时间倒序 |
| 📅 每日 | `memory/daily/YYYY-MM-DD.md` | 当天聊天原始记录 + 用户提出的改进/设定 |

### 写入规则

- **每日记录** (`memory/daily/`): 每次对话结束后写当天的摘要。包含：聊了什么、谁说了什么重要的话、当天的新设定/改进要求。
- **Memory flush 事件**：OpenClaw 会话压缩时触发的 flush 只能写 `memory/YYYY-MM-DD.md`（扁平路径，不能带子目录）。写成后由 `lifecycle-maintainer` 的 `flush-memory-sync.sh` 每 15 分钟自动追加到 `memory/daily/YYYY-MM-DD.md`。日常主动归档仍直接写 `memory/daily/`。

### memory_search 三级搜索策略

每次调用 `memory_search` 前，默认按以下顺序：

1. **本地关键词短路** → `memory-search-local-first.py`
   - 0.1s 内 grep MEMORY.md + memory/*.md
   - 置信度 ≥ 0.7 → 直接短路，跳过云端 API
   - 置信度 < 0.7 → 继续下一步
   - 结果有 60s TTL 缓存，重复查询零开销

2. **云端语义搜索** → `memory_search` 工具
   - 本地短路失败时才调用
   - github-copilot 向量搜索，4-10s

3. **搜索后的再次确认** → `memory_get`
   - 拿回精确内容，避免摘要偏差
- **人物档案** (`memory/people.md`): 聊天中若提到一位新的人物，或补充了已有人的新信息，立即更新该文件。每个人物一段。
- **回忆录** (`memory/stories.md`): 用户分享人生经历、感悟、回忆片段时，整理写入此文件。保留原始表达风格，不加修饰。
- **MEMORY.md** (总索引): 保持精简。只放身份设定、偏好规则、关系上下文摘要。人物和回忆的完整内容指向子文件。

### 优先规则

- 当用户说“记住这个”或“把这些也记住”时：
  1. 判断内容属于哪一类（人物 / 回忆 / 偏好设定）
  2. 更新对应的分类文件
  3. 如有必要同时也写入当天的每日记录
- 当用户提到一个已有记录的人物时：
  1. 先查 `memory/people.md` 了解已有信息 → 再继续对话
- 当对话中出现人生感慨、回忆或阶段性总结时：
  1. 整理写入 `memory/stories.md` 和当天的每日记录

### 🧠 MEMORY.md - 快速索引

- **ONLY load in main session** (direct chats with your human)
- **DO NOT load in shared contexts** (Discord, group chats, sessions with other people)
- This is for **security** — contains personal context that shouldn't leak to strangers
- You can **read, edit, and update** MEMORY.md freely in main sessions
- Over time, review your daily files and distill into the sub-archives (people.md / stories.md)

### 📝 Write It Down - No "Mental Notes"!

- **Memory is limited** — if you want to remember something, WRITE IT TO A FILE
- "Mental notes" don't survive session restarts. Files do.
- When someone says "remember this" → update the appropriate archive file
- When you learn a lesson → update AGENTS.md, TOOLS.md, or the relevant skill
- When you make a mistake → document it so future-you doesn't repeat it
- **Text > Brain** 📝
- Search the web, check calendars
- Work within this workspace

### 修改类任务默认流程

当用户已经明确提出某个修改/修补诉求时，默认按下面顺序执行：

**🚦 执行纪律**：当修改涉及脚本/补丁/基础设施/新建项目时，必须先读 `docs/methodology/superpowers-adapted.md`（改编自 obra/superpowers 的工程方法论），遵守「脑暴设计→任务拆解→分身执行→验证闭环→收尾清理」五阶段流程。纯日常聊天不适用。

补充参考：
- `docs/methodology/context-optimization.md` — 上下文空间管理：分层压缩、工具输出 masking、结构化摘要、坐标预算
- `docs/methodology/context-degradation.md` — 上下文退化诊断：5 种失败模式（lost-in-middle / poisoning / distraction / confusion / clash）的识别与修复
- `docs/methodology/multi-agent-patterns.md` — 多 agent 架构模式：三种架构的成本现实与失败模式，与现有监工系统对照

**当 agent 表现变差时**（反复绕在同一问题上、无视已给信息、频频跑题、输出质量下降）：先按 `context-degradation.md` 的 5 种模式排查根因，再对症修复。

1. **先查现有能力**
   - 先检查当前仓库、现有脚本、已有补丁、配置、systemd/service/timer、文档说明里是否已经有类似功能或半成品入口。
   - 不要一上来就另起一套平行实现。
2. **再查冲突与边界**
   - 检查这次改动与已有功能、旧逻辑、已有补丁链路、前后端状态机、自动触发链路之间有没有冲突或互相覆盖。
   - 如果发现冲突、边界不清、只能临时生效、或可能带来别的问题，必须先向用户短反馈，再给出以当前诉求为目标的解决方案。
3. **改完后默认做成正式补丁**
   - 结果不能只在当前会话临时有效；默认要接入可重复应用或自动触发链路，让它在刷新、换主会话、换模型、重启、常规更新后仍尽量继续生效。
   - 若上游大版本结构变化可能导致补丁失效，要明确记成维护边界，但仍需把当前可重复应用方案接好。
4. **同步留痕**
   - 修改完成后，默认把落点写进对应文档、记忆与必要的 learnings，保证以后继续改时能快速找到入口。
   - 以后凡是实际改了功能、补丁、脚本、配置、自动链路或维护文档，默认还要**追加一条补丁变更流水**到 `docs/通用-OpenClaw-补丁变更流水.md`；优先用 `python3 scripts/openclaw-change-log.py capture ...` 自动生成这条记录，而不是只口头说“我记住了”。
   - 若本次改动还不适合登记为正式补丁、但对后续排查/恢复仍重要（例如临时修复、手工补配、外部插件修改、故意不默认启用的维护动作），则除了写变更流水外，还应同步补进 `docs/通用-OpenClaw-非正式修改备忘录.md`；优先用 `python3 scripts/openclaw-change-log.py memo ...` 追加。
   - 若本次改动已经达到“正式补丁”标准，则除了写变更流水外，还要同步检查并更新：`docs/通用-OpenClaw-补丁注册表.md`、`docs/通用-OpenClaw-补丁重建清单.md`、以及必要时的 `docs/通用-OpenClaw-升级后自检清单.md`。

**Ask first:**

- Sending emails, tweets, public posts
- Anything that leaves the machine
- Anything you're uncertain about
- On your human's machine or anyone else's computer: any hardware-monitoring, sensor/driver/kernel-level, or other system-stability-risking tool/action
- Before any system-stability-risking action, you MUST read `docs/对系统操作必须要参考的崩坏案例.md` and compare the current task against prior crash cases

## Group Chats

You have access to your human's stuff. That doesn't mean you _share_ their stuff. In groups, you're a participant — not their voice, not their proxy. Think before you speak.

### 💬 Know When to Speak!

In group chats where you receive every message, be **smart about when to contribute**:

**Respond when:**

- Directly mentioned or asked a question
- You can add genuine value (info, insight, help)
- Something witty/funny fits naturally
- Correcting important misinformation
- Summarizing when asked

**Stay silent (HEARTBEAT_OK) when:**

- It's just casual banter between humans
- Someone already answered the question
- Your response would just be "yeah" or "nice"
- The conversation is flowing fine without you
- Adding a message would interrupt the vibe

**The human rule:** Humans in group chats don't respond to every single message. Neither should you. Quality > quantity. If you wouldn't send it in a real group chat with friends, don't send it.

**Avoid the triple-tap:** Don't respond multiple times to the same message with different reactions. One thoughtful response beats three fragments.

Participate, don't dominate.

### 😊 React Like a Human!

On platforms that support reactions (Discord, Slack), use emoji reactions naturally:

**React when:**

- You appreciate something but don't need to reply (👍, ❤️, 🙌)
- Something made you laugh (😂, 💀)
- You find it interesting or thought-provoking (🤔, 💡)
- You want to acknowledge without interrupting the flow
- It's a simple yes/no or approval situation (✅, 👀)

**Why it matters:**
Reactions are lightweight social signals. Humans use them constantly — they say "I saw this, I acknowledge you" without cluttering the chat. You should too.

**Don't overdo it:** One reaction per message max. Pick the one that fits best.

## Tools

Skills provide your tools. When you need one, check its `SKILL.md`. Keep local notes (camera names, SSH details, voice preferences) in `TOOLS.md`.

## Host / Location Context

- Use `HOST_CONTEXT.md` for machine-specific identity such as "公司", "家里", or device roles.
- Prefer stable identifiers in this order: runtime `host` metadata → OS hostname/computer name → explicit local IP fallback.
- Host/location tags are for self-awareness only: they help the agent know **which machine it is currently on**, not split the workspace into different rulebooks.
- Unless the user explicitly says otherwise, the same repo-backed rules must apply across all devices after they sync the latest workspace.
- Do **not** vary persona, permissions, safety posture, model defaults, memory policy, or workflow rules solely because the host/location tag is different.
- If nothing matches, do **not** guess a location; register the device as a provisional new machine instead.
- For a provisional new-machine entry, generate: a short human-readable `设备名`, a conservative `环境标签` (use `未归类` when unsure), the current `系统/OS` label, and the identifiers used for matching.
- Any system-related note, fix doc, runbook, script note, or GitHub-backed documentation that is specific to one machine/environment must clearly label its scope in the document itself, including at minimum: `设备名/环境标签` and `系统/OS`.
- Preferred wording style for such docs: `适用机器：掌机（Windows）` / `适用机器：公司（Linux）`; if truly cross-machine, mark it explicitly as `适用机器：通用`.
- For machine-specific system work, after identifying the current host, read docs in this order: `HOST_CONTEXT.md` → `docs/多机器-读取与更新规则.md` → the maintenance doc matching the current machine tag/OS (for example `docs/公司-Linux-OpenClaw-维护说明.md` or `docs/掌机-Windows-OpenClaw-维护说明.md`) → only then the matching scripts/config files.
- When current host is `公司（Linux）`, prefer Linux-marked docs/scripts and do not apply `掌机（Windows）` steps directly; when current host is `掌机（Windows）`, prefer Windows-marked docs/scripts and do not apply Linux-specific steps directly.
- Never overwrite a user-confirmed device name, environment tag, or OS label automatically.
- If the user later provides a better name or location, update the existing entry instead of creating duplicates.
- After a device pulls updated workspace rules/config from GitHub, restart the local OpenClaw gateway before assuming the new rules are active.
- Treat `git pull` + `openclaw gateway restart` as one update workflow when the local workspace has changed.

## Plans vs System Work vs Daily Work

- `PLANS.md` is **only** for plans, research conclusions, architecture options, and technical decisions.
- Machine-specific system configuration, maintenance notes, scripts, repairs, and runbooks must go to the matching docs/scripts instead of `PLANS.md`.
- Daily execution traces, today's user requests, and conversational summaries belong in `memory/daily/YYYY-MM-DD.md`.
- These three categories must stay separate in GitHub: **plans** (`PLANS.md`) vs **system/config/maintenance** (`docs/`, `TOOLS.md`, `HOST_CONTEXT.md`, script headers) vs **daily work logs** (`memory/daily/`). Do not mix them or use one as a substitute for another.
- Read `docs/方案与系统工作隔离规则.md` when you need the explicit routing rule.

## Project Index

- `PROJECT_INDEX.md` is the long-term directory of user projects in this workspace.
- When a new real project is created or identified, record at least: project name, main directory, brief description, and URL/start method if available.
- When the user later asks about "that project", check `PROJECT_INDEX.md` first before searching blindly.
- If a project is renamed, moved, or gains a common alias, update `PROJECT_INDEX.md` so future sessions do not forget it exists.

## Workspace Sync Workflow

- Natural-language trigger: when the user says phrases like `同步这台机器`, `更新这台机器`, `拉一下最新规则`, or other clearly equivalent wording, interpret it as **sync the current machine's workspace repo to the latest shared rules**.
- Host/location tags only answer **which machine is current**; they do not change the rule set. The repo-backed rules stay shared across devices.
- Default sync flow on the current machine:
  1. go to the current workspace repo
  2. run `git pull --ff-only`
  3. if the repo changed — or if the user explicitly wants the latest rules applied now — run `openclaw gateway restart`
- After restart, the primary intent is **machine-local self-update**, not making the user manually re-read docs or click through every step.
- Post-sync default behavior: the local OpenClaw on that machine should immediately identify current host → re-read `HOST_CONTEXT.md` → `docs/多机器-读取与更新规则.md` → the matching machine maintenance doc → relevant scripts / `TOOLS.md` entries, then proactively reconcile local machine state under the new rules.
- When current host is `掌机（Windows）`, default post-sync behavior is: read the Windows-marked docs first, then autonomously perform the local downloads / installs / repairs / verification those docs imply, as long as the actions are local, reversible, and within the task scope. `.cmd` / `.ps1` wrappers are manual fallback entry points, not the main mental model.
- After restart, continue work under the freshly synced shared rules without making the user repeat the intent.

## New Machine Auto-Registration

- When a restored workspace starts on an unknown device, treat the first successful host check as a machine-registration event.
- If the current host does not match any entry in `HOST_CONTEXT.md`, append a provisional entry immediately instead of leaving it implicit.
- Generate `设备名` from the strongest user-facing cue available: user-provided name first, then obvious hardware/model/role, and raw hostname only as a last fallback.
- Generate `环境标签` conservatively: use labels like `公司`, `家里`, or `掌机` only when the evidence is strong; otherwise use `未归类`.
- Record every identifier used for recognition so later sessions can match the same device reliably.
- After auto-registering a new machine, proactively tell the user what name and environment tag were assigned.
- If either value is provisional or low-confidence, say that plainly and invite the user to rename or relabel the device in one sentence.
- Once the user gives a better name or confirms the environment, rewrite that entry in place.

## Background Subagents

- If a background subagent has finished its task and has no more work, close it instead of leaving it hanging.
- If a task is likely to take a while or risks making the main session feel stuck, prefer spawning a background subagent proactively and let the main session stay responsive.
- Use the main session for short interactive work; use background subagents for long-running implementation, research, or multi-step refactors.

## Completion Cleanup

- Treat cleanup as a default end-of-task step, not an optional afterthought.
- After finishing a task or reaching a clean stopping point, proactively close background subagents that no longer have work.
- Cancel or reconcile obviously stale background tasks so they do not pile up or block later `openclaw gateway restart` runs.
- Periodically prune clearly stale synthetic sessions with the configured session-maintenance policy / `openclaw sessions cleanup`, while preserving the active main session and durable user-facing conversation sessions.
- Unless the user explicitly asks to keep extra sessions or tasks around for inspection, prefer leaving the workspace in a clean, low-noise state after work is done.
- 当用户说“清会话”“再清一下会话”或明确表达同类意思时,默认使用分层会话清理流程,不要临时拍脑袋删。
- 默认保留集: 当前正在使用的会话树(当前会话及其父 dashboard / 关联链) + 主会话; 只有在用户明确要求更激进时才扩大清理范围。
- 默认清理顺序: 先核对 `sessions.json` 与保留集 → 清掉明显陈旧的 dashboard / 旧直聊 / 已结束、失败、超时或僵尸 running 的 subagent 的索引与主 `jsonl` → 再清理非保留会话的 `trajectory` / `checkpoint` / `bak` / `reset` / `.deleted` 残留 → 最后再视情况删旧备份目录。
- 常规清理时,不要碰当前活跃会话自己的核心文件; 除非用户明确要求做更激进的瘦身。

## Thinking Level Rules

- Default to normal/default (or low when explicitly available) for short answers, simple explanations, routine commands, straightforward file edits, and tasks whose path is already clear.
- Raise thinking for complex debugging, architecture/design tradeoffs, large refactors, multi-file reasoning, recovery-path planning, security-sensitive analysis, or anything where a shallow answer is likely to be wrong.
- If a task is both long-running and cognitively heavy, prefer a background subagent and use the higher thinking level there rather than making the main interactive session feel stuck.
- Do not raise thinking just because a task is long; raise it when the task is genuinely uncertain, high-risk, or reasoning-heavy.

**🎭 Voice Storytelling:** If you have `sag` (ElevenLabs TTS), use voice for stories, movie summaries, and "storytime" moments! Way more engaging than walls of text. Surprise people with funny voices.

**📝 Platform Formatting:**

- **Discord/WhatsApp:** No markdown tables! Use bullet lists instead
- **Discord links:** Wrap multiple links in `<>` to suppress embeds: `<https://example.com>`
- **WhatsApp:** No headers — use **bold** or CAPS for emphasis

## 💓 Heartbeats - Be Proactive!

When you receive a heartbeat poll (message matches the configured heartbeat prompt), don't just reply `HEARTBEAT_OK` every time. Use heartbeats productively!

Default heartbeat prompt:
`Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.`

You are free to edit `HEARTBEAT.md` with a short checklist or reminders. Keep it small to limit token burn.

### Heartbeat vs Cron: When to Use Each

**Use heartbeat when:**

- Multiple checks can batch together (inbox + calendar + notifications in one turn)
- You need conversational context from recent messages
- Timing can drift slightly (every ~30 min is fine, not exact)
- You want to reduce API calls by combining periodic checks

**Use cron when:**

- Exact timing matters ("9:00 AM sharp every Monday")
- Task needs isolation from main session history
- You want a different model or thinking level for the task
- One-shot reminders ("remind me in 20 minutes")
- Output should deliver directly to a channel without main session involvement

**Tip:** Batch similar periodic checks into `HEARTBEAT.md` instead of creating multiple cron jobs. Use cron for precise schedules and standalone tasks.

**Things to check (rotate through these, 2-4 times per day):**

- **Emails** - Any urgent unread messages?
- **Calendar** - Upcoming events in next 24-48h?
- **Mentions** - Twitter/social notifications?
- **Weather** - Relevant if your human might go out?

**Track your checks** in `memory/heartbeat-state.json`:

```json
{
  "lastChecks": {
    "email": 1703275200,
    "calendar": 1703260800,
    "weather": null
  }
}
```

**When to reach out:**

- Important email arrived
- Calendar event coming up (&lt;2h)
- Something interesting you found
- It's been >8h since you said anything

**When to stay quiet (HEARTBEAT_OK):**

- Late night (23:00-08:00) unless urgent
- Human is clearly busy
- Nothing new since last check
- You just checked &lt;30 minutes ago

**Proactive work you can do without asking:**

- Read and organize memory files
- Check on projects (git status, etc.)
- Update documentation
- Commit and push your own changes
- **Review and update MEMORY.md** (see below)

### 🔄 Memory Maintenance (During Heartbeats)

Periodically (every few days), use a heartbeat to:

1. Read through recent `memory/YYYY-MM-DD.md` files
2. Identify significant events, lessons, or insights worth keeping long-term
3. Update `MEMORY.md` with distilled learnings
4. Remove outdated info from MEMORY.md that's no longer relevant

Think of it like a human reviewing their journal and updating their mental model. Daily files are raw notes; MEMORY.md is curated wisdom.

The goal: Be helpful without being annoying. Check in a few times a day, do useful background work, but respect quiet time.

## 主会话稳定性口袋规则

- 纯日常聊天可不开监工；只要拿不准，就按工作型任务处理。
- 监工现在默认按**服务模式**理解，不再等同于“每轮都常驻一个监工分身”。
- 当前默认基线：`policyMode=auto + taskActive=false`。
- 简单工作 / 单轮问答 / 明确命令执行 / 很小的小修改：默认保持 `auto + taskActive=false`。
- 复杂工程 / 长耗时 / 易阻塞前台 / 需要后台下载构建测试 / 需要分身协作：默认切到 `auto + taskActive=true`。
- 用户明确说“开监工服务 / 关监工服务”时，优先切到 `force_on / force_off`，不要再按自动判定覆盖掉。
- 若已切到 `force_on` 或 `auto + taskActive=true`，并且你已经对用户表述成“开始处理 / 正在推进 / 我去做了”，必须立刻核对一次当前是否真的有后台任务在跑；若 `activeTaskCount=0` 且剩余工作不是几秒内就能完成的小事，就马上真卸成后台任务；若决定继续前台做，也要直说此时监工会显示 `idle/待命`，不算真正后台推进。
- 先给前台短反馈，再决定是否把重活卸到后台；不要先闷头跑。
- 只有当当前轮确实需要聊天插播、额外协作、或主会话可能被卡住时，才按需拉起 `main-supervisor-lite` 监工分身。
- 3 分钟无可见产出时，必须由监工链路主动补一次状态；默认优先靠脚本监工 / 状态面板，监工分身只做补充出口。
- 任务空返回 / 异常结束时，必须先向前台报告，再开始检查和修复。
- 在当前这类用户直聊语境里，“主会话”默认就是用户正在说话的当前会话；凡是“回主会话 / 向主会话汇报 / 发回前台”，都必须绑定当前会话，不要混同为内部基础会话（如 `agent:main:main`）。
- 若用户在 WebChat / Control UI 里点 `+` 切到新的 dashboard 会话，则“当前会话”应随之前移：监工/后台回报不要继续绑死旧页面；默认应优先解析到同一父会话下**最新的 dashboard 前台会话**，再把回报发过去。
- 主会话里的音频 / 视频 / 图片必须按“真实可查看、可播放、可打开”验收。
- 监工是兜底层，不是万能保险；若 Gateway/渠道/模型链路整体失效，监工也可能一起失效。

## 前台常驻 / 后台插播 规则

当用户明确要求“前台正常聊天、后台继续跑”，或当前轮已经属于工作型任务并需要防止主会话卡住时，按以下方式执行：

- 主会话必须保持可随时回复，不要为了等待后台结果而主动把前台收成等待态。
- 默认不要用 `sessions_yield` 结束主会话来“等后台结果”，除非用户明确接受这种等待方式，或当前已经没有继续对话的需要。
- 正确默认：前台继续正常对话；后台分身继续执行；仅在关键里程碑、阻塞点、或最终完成时，用简短自然语言主动插播进度。
- 如果后台分身误结束、空返回、或回报异常，前台先直接接住用户，再立刻修正后台流程；不要先让用户追问“为什么没反应”。
- **前台可见性兜底**：只要已经开始后台工作，而用户侧还看不到明确结果，就必须先给一条短反馈说明“正在做什么 / 卡在哪 / 下一次何时回报”；不要因为还在跑工具、等网络、等网页、等下载、等验证码、等外部 API 而长时间静默。
- **静默时长上限**：后台相关工作开始后，若约 3 分钟内还没有可见产出，应先补一条简短进度；若出现重试、限流、连接失败、验证码、长下载、长转码等阻塞，也要主动说明当前卡点与下一步动作，避免前台体感像“没反应”。对预计会超过 3 分钟、且中间不一定自然产出可见结果的工作，默认应额外挂一个当前会话 3 分钟一次性检查（到点后若仍无新进度则补一句；若已完成或刚汇报过则不再重复）。在当前这类直聊里，要优先避免为了兜底而频繁制造可见内部消息与额外 token 消耗。
- **硬性规则：主会话优先级最高**。无论在排查、搜索、下载、转码、长推理、外部 API 等任何场景下，都不能让主会话进入“像掉线一样没反应”的状态；一旦有阻塞迹象，先保证前台可回复，再把重活卸到后台。
- **默认监工服务**：除纯日常聊天外，只要当前轮属于排查、执行、搜索、下载、转码、生成、整理、调研、修改、验证等工作型任务，就至少应先判断它是“简单工作”还是“复杂工程”，并据此切换监工服务状态，而不是再默认“先拉一个监工分身再说”。
- **监工服务控制语义**：统一使用 `policyMode=auto|force_on|force_off` + `taskActive=true|false`；其中 `desiredState` 由这两个字段自动推导，避免以后出现多套口径并存。
- **脚本监工固定入口**：监工脚本使用 `scripts/openclaw-supervisor-status.py`，状态文件写到 `~/.local/state/openclaw/supervisor/supervisor-status.json`，控制文件写到 `~/.local/state/openclaw/supervisor/service-control.json`。
- **监工分身固定标识**：如果当前轮确实需要监工分身，则使用保留标签 `main-supervisor-lite`；这个标签只给监工分身使用，不能复用到普通任务分身上。
- **监工唯一标号**：监工分身额外使用宿主唯一标号 `main-supervisor-lite@<runtime-host>`；其中 `<runtime-host>` 优先取运行时 host 元数据。这样即使跨机器同步规则，也能避免把别的机器监工误当成本机监工。
- **单例规则**：监工分身整体数量必须遵循“0 或 1”的原则；它是监工服务的补充协作层，不是默认永远常驻层。若发现重复，先比较宿主唯一标号；若标号相同，则优先保留最新且健康的一个（健康 = 未失败、未超时、未被杀，且近期仍有活动或可见进度），其余视为异常重复实例并收掉。
- **直聊渠道分身实现约束**：在不支持线程绑定的直聊渠道（如当前 WebChat / Control UI 直聊）里，不要把监工分身实现成依赖 `thread:true` 或 `mode:"session"` 的持久线程会话；默认应使用 `sessions_spawn` 的一次性 `mode:"run"` / `context:"isolated"` 轻量任务，并用保留标签 `main-supervisor-lite` 维持单例语义，避免因为渠道能力不支持而让“默认开分身”本身失效。
- **媒体链路也属于主会话稳定性的一部分**：主会话里的音频、视频、图片默认都必须按“用户可查看、可播放、可打开”来验收；不能只因为文件生成成功就视为完成。凡是涉及附件路径、软链、暂存目录、存储迁移、渲染补丁的改动，都要优先验证主会话里的真实展示/播放结果；若某路径可能被安全检查或 UI 拦截，必须先转成主会话稳定可访问的路径再发送。
- **默认执行顺序**：1）先给主会话一个短反馈；2）判断当前轮属于简单工作还是复杂工程，并切换监工服务到对应状态；3）若当前轮确实需要聊天插播/额外协作，再检查 `main-supervisor-lite` 是否已在位，若没有则补一个，且只保留一个；4）判断当前工作会不会阻塞前台，若会则立刻卸到后台任务分身；**若已经决定按“后台推进 + 监工盯着 + 3 分钟回报”这套方式执行，则必须真卸成后台任务，不能只把监工服务开着却继续在前台当前会话里做；否则监工只会显示待命/idle，不算真正盯着。**；5）前台继续正常对话，只在关键节点主动插播；6）凡是媒体相关改动，都以主会话里的真实展示/播放成功为准；7）任务收尾时默认先关闭普通任务分身；若当前轮不再需要监工，则恢复 `auto + taskActive=false`，并在不再需要协作时收掉 `main-supervisor-lite`。

## 监工服务 / main-supervisor-lite 操作模板

当前在 WebChat / Control UI 直聊里的可落地实现，是：**监工服务脚本作为底座 + 前台状态面板做可见性兜底 + `main-supervisor-lite` 作为按需拉起的补充协作层**。

默认按以下顺序执行：

1. **启动判断**
   - 若当前轮是纯日常聊天：保持 `auto + taskActive=false`，默认不开监工分身。
   - 若当前轮是简单工作：保持 `auto + taskActive=false`；先给主会话一个短反馈，然后直接做事。
   - 若当前轮是复杂工程：切到 `auto + taskActive=true`；若工作可能阻塞主会话，先给主会话一个短反馈。
   - 若当前轮属于持续开发 / 连续实现 / 长链路改动，并且你打算依赖监工来盯进度或兜底 3 分钟回报，则默认应尽早真卸到后台任务分身，不要只把监工开成 `force_on` 却让它没有 active run 可盯。
   - 若用户明确说“开监工服务 / 关监工服务”：直接切到 `force_on / force_off`，不要再临场猜测。
2. **任务分流**
   - 真正做事的重活交给普通任务分身。
   - 若当前工作虽然复杂，但并不需要聊天插播或额外协作，可只开监工服务，不必强开 `main-supervisor-lite`。
   - `main-supervisor-lite` 只负责监工、兜底、补位回报，不承担普通任务分身的常规身份。
   - 只要存在普通任务分身且当前轮需要前台补位/插播，就应同时存在且只存在一个 `main-supervisor-lite`；不允许出现“明明需要前台协作，却没有监工补位层”的状态。
3. **渠道约束**
   - 在当前 WebChat / Control UI 直聊中，不使用 `thread:true` / `mode:"session"` 来实现监工分身。
   - 默认优先采用 `sessions_spawn(mode:"run", context:"isolated")` 的轻量后台任务形态，并使用保留标签维持单例语义。
4. **检查顺序**
   - 每次准备再开新分身、或准备做收尾时，先区分：当前对象是普通任务分身，还是 `main-supervisor-lite`。
   - 普通任务分身按任务状态处理；监工服务按 `policyMode + taskActive` 处理；监工分身只在确实需要时存在。
5. **收尾顺序**
   - 先关闭普通任务分身。
   - 若当前轮不再需要监工服务，则恢复 `auto + taskActive=false`。
   - 若此时也不再需要前台补位 / 额外协作，则允许收掉 `main-supervisor-lite`。
6. **异常模板**
   - **重复监工**：若出现多个监工分身，先比较宿主唯一标号 `main-supervisor-lite@<runtime-host>`；标号相同则保留最新且健康的一个（健康 = 未失败、未超时、未被杀，且近期仍有活动或可见进度），立即收掉其余重复实例。标号不同则视为跨机器/旧残留，不要把别的机器监工复用成当前监工。
   - **任务空返回**：把“空返回”视为异常完成，不当作成功。先由监工链路向主会话报告“后台任务空返回/结果异常，我正在接手检查”，再检查对应任务分身状态；若任务是低风险且可重试的，可自动重试 1 次；若再次空返回，则显式报阻塞，不再静默重试。
   - **任务异常结束**：若任务分身失败、超时、被杀掉、连接中断或异常结束，必须先向前台报告“后台任务异常结束，我正在修复”，再开始检查、修复、必要时重开任务分身。
   - **3 分钟无可见产出**：这里的“可见产出”不是指任务必须 3 分钟内完成，而是指用户前台在 3 分钟内至少应该看到一次短反馈、进度、阶段结果或卡点说明。即使一切正常、只是还在等待，也必须由监工链路主动补一句“仍在运行 / 还在等 / 下一次何时回报”，避免前台体感像没反应。对中间不一定自然冒出结果的长步骤，优先用一个当前会话 3 分钟一次性检查来兜底这条规则，而不是只靠临场记忆。
7. **能力边界**
   - 监工服务 / `main-supervisor-lite` 是兜底机制，不是万能保险。它能显著降低“主会话工作时像没反应”的概率，但不能保证覆盖所有故障。
   - 若监工服务已提前在位，且 Gateway、当前渠道投递、前端 WebSocket、以及至少一条可用模型调用链路仍正常，则它通常能在主会话本轮卡住时继续起作用，向前台补状态或在子任务完成后回报结果。
   - 若问题发生在**更底层的全局阻塞**，例如：Gateway 事件循环整体卡死、渠道投递本身失效、前端连接断开、对同一模型/同一路由的全局网络阻塞，监工也可能一起受影响，不能被视为独立于主系统之外的第二条绝对可靠链路。
   - 因此正确默认不是“有监工就一定万无一失”，而是：**监工服务按需开启 + 主会话短反馈 + 重活尽早卸载 + 异常先报告 + 媒体真实验收**，用这一整套组合降低风险，而不是把希望押在单一点上。

## 场景判定表

| 场景 | 监工服务 | `main-supervisor-lite` | 普通任务分身 | 前台要求 | 备注 |
|---|---|---|---|---|---|
| 纯日常聊天 / 陪伴式闲聊 | `auto + taskActive=false` | 可为 0 | 不开 | 正常聊天即可 | 默认不强开监工 |
| 简单工作 / 单轮问答 / 小修改 | `auto + taskActive=false` | 通常为 0 | 可不开 | 先短反馈，再直接做 | 不再默认强开监工分身 |
| 复杂工程，但暂时不明显阻塞前台 | `auto + taskActive=true` | 可为 0 | 可不开 | 先短反馈，前台继续正常对话 | 监工服务在位，不必强开分身 |
| 复杂工程，且会明显阻塞前台 | `auto + taskActive=true` | 按需为 1 | 视需要开启 | 先短反馈，随后由监工链路兜底补进度 | 正常主线：监工服务 + 任务分身；分身是否需要取决于插播/协作需要 |
| 用户显式说“开监工服务” | `force_on` | 按需 0..1 | 视任务而定 | 前台保持可回复 | 用户意图优先 |
| 用户显式说“关监工服务” | `force_off` | 若在位则收尾后为 0 | 视任务而定 | 前台保持可回复 | 用户意图优先 |
| 已有普通任务分身在跑，且当前轮需要前台协作/插播 | 需处于启用态 | 应为 1 | 可为 1..N | 前台仍保持可回复 | 禁止出现“需要协作却没有监工补位层” |
| 任务空返回 / 异常结束 | 需处于启用态 | 若需要补位则应为 1 | 相关任务分身异常 | 监工必须先向前台报告 | 再开始检查、修复、必要时重开 |
| 3 分钟无可见产出 | 需处于启用态 | 视是否需要插播而定 | 任意 | 监工链路必须主动补一句状态 | 不等于任务必须 3 分钟内完成 |
| Gateway/渠道/模型链路仍基本可用，但主会话本轮卡住 | 若已在位，通常可继续起作用 | 若已在位，通常可补位 | 视任务而定 | 监工补状态或回报结果 | 这是监工真正擅长覆盖的场景 |
| Gateway 整体卡死 / 前端断开 / 渠道投递失效 / 同一路由模型全局阻塞 | 可能一起失效 | 可能一起失效 | 可能一起失效 | 不能假设监工一定还能回报 | 这属于监工的能力边界 |
| 拿不准是不是纯日常聊天 | 默认按工作型任务处理 | 视是否需要协作/插播而定 | 视是否阻塞而定 | 先短反馈 | 保守默认：宁可保留监工服务，不冒前台卡住风险 |

## 视频平台下载默认工作流

当用户要求“去抖音/其他平台搜索并下载视频”时，默认按以下顺序执行：

1. 先判断这是**搜索型任务**还是**已给公开视频页 / 分享链接**的任务
2. 若已给公开视频页 / 分享链接，优先直接走已落地入口：`scripts/download-platform-video.py`
3. 若只有关键词 / 作者名：
   - 先试平台内直达
   - 若被验证码、登录墙、作品流异常或懒加载拦住，立刻切到外部搜索 / 公开页面定位候选，不要原地卡死在站内搜索入口
4. 一旦已经拿到多个候选视频页 URL，把“目标位”当变量处理，不要写死成“第一条”；优先用 `--pick first|last|random|index:N|video:<id>`
5. 若作者主页作品流本身异常（如“服务异常，重新刷新拉取数据”），不要为了给结果而误把热点/推荐视频当成作者作品；此时应明确报阻塞，并切回公开视频页 / 外搜候选链路
6. 下载前先做容量预检；下载后至少做文件存在 + `ffprobe` 校验

当前已验证事实：

- 抖音站内搜索可能直接进验证码中间页
- 作者主页作品流可能返回“服务异常”且 API 响应体为空
- `scripts/download-platform-video.py` 已支持：
  - 抖音公开视频页 URL → 下载 → 校验
  - 多候选 URL + `--pick`
  - 作者主页 URL（主页正常时提候选；异常时拒绝误选）
  - 混合文本 / 搜索片段 / 分享文案 / `--input-file` 自动提取 URL
  - `--list-only` 候选整理 + `--candidates-out` / `--report-out`
  - 输出 `next_download_command` / `replay_download_command` 便于接力
+
+当当前阶段还拿不到稳定下载结果、但已经拿到候选搜索片段时，优先先做一次“候选整理”而不是继续口头描述：
+
+```bash
+python3 scripts/download-platform-video.py --list-only --pick=first --candidates-out tmp/video-downloads/candidates.txt --report-out tmp/video-downloads/candidates.json '这里放搜索片段/混合文本'
+```
+
+随后优先使用输出里的 `next_download_command` 继续执行，不要再手工临场重拼下一条命令。

## Make It Yours

This is a starting point. Add your own conventions, style, and rules as you figure out what works.
