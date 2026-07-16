# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice
**Areas**: frontend | backend | infra | tests | docs | config
**Statuses**: pending | in_progress | resolved | wont_fix | promoted | promoted_to_skill

## Status Definitions

| Status | Meaning |
|--------|---------|
| `pending` | Not yet addressed |
| `in_progress` | Actively being worked on |
| `resolved` | Issue fixed or knowledge integrated |
| `wont_fix` | Decided not to address (reason in Resolution) |
| `promoted` | Elevated to CLAUDE.md, AGENTS.md, or copilot-instructions.md |
| `promoted_to_skill` | Extracted as a reusable skill |

## Skill Extraction Fields

When a learning is promoted to a skill, add these fields:

```markdown
**Status**: promoted_to_skill
**Skill-Path**: skills/skill-name
```

Example:
```markdown
## [LRN-20250115-001] best_practice

**Logged**: 2025-01-15T10:00:00Z
**Priority**: high
**Status**: promoted_to_skill
**Skill-Path**: skills/docker-m1-fixes
**Area**: infra

### Summary
Docker build fails on Apple Silicon due to platform mismatch
...
```

---

## [LRN-20260514-001] best_practice

**Logged**: 2026-05-14T10:01:00+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
用户要求：对已明确提出诉求的修改类任务，默认先查现有能力，再查与旧逻辑/旧补丁的冲突，最后把结果接成可重复应用的正式补丁，并留下清晰落点。

### Details
用户在当前 broker / watcher / 前台稳定性修补推进过程中，进一步把修改类任务的默认顺序明确成三步：第一步先查当前仓库里是否已有类似功能、已有补丁、已有入口或半成品能力；第二步检查与现有功能、既有逻辑、自动触发链路之间有没有冲突，如果发现问题要及时回报，并以当前诉求为目标给出解决方案；第三步修改完成后，默认把结果接入正式补丁或自动链路，避免只在当前会话临时有效，同时把文档、记忆和维护落点记清楚，方便以后续改。

### Suggested Action
把这条规则提升到 `AGENTS.md` 与 `MEMORY.md` 作为长期默认工作流；以后凡是用户已经明确提出修改诉求的任务，都先做现状查重与冲突检查，再实施修改，并在结束时默认补上持久化链路与维护记录。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, MEMORY.md, memory/daily/2026-05-14.md
- Tags: workflow, patching, persistence, conflict-check, docs

---

## [LRN-20260513-001] best_practice

**Logged**: 2026-05-13T17:35:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: infra

### Summary
帮用户本人或其朋友清理/修电脑时，涉及硬件监控、传感器、驱动/内核级或其他可能影响系统稳定性的工具，必须按高风险动作处理，先明确风险并再次确认，默认停在低风险方案。

### Details
本轮为接宿主机温度读取，尝试在 Windows 宿主机上引入 LibreHardwareMonitor。用户随后明确反馈：打开该工具后宿主机直接崩溃，花了较长时间重装/抢修才恢复工作环境。这个结果说明：即使目标只是“读温度”，也不能把硬件监控类工具默认视为低风险，尤其当机器承载工作环境、第三方重要数据，或任务对象是朋友/他人的电脑时，必须把稳定性和可恢复性放在首位。

### Suggested Action
以后默认不要主动在宿主机或第三方电脑上尝试硬件监控、传感器、驱动层、内核级或其他可能影响稳定性的工具；若用户仍想继续，必须先说明风险、征得再次确认，并优先选择最小影响、可回滚、低风险方案。把这条规则同步提升到 `MEMORY.md` 与 `AGENTS.md`。

### Metadata
- Source: user_feedback
- Related Files: MEMORY.md, AGENTS.md, memory/2026-05-13.md
- Tags: stability, host-machine, repair, cleanup, safety, hardware-monitoring

---

## [LRN-20260507-001] best_practice

**Logged**: 2026-05-07T15:40:00+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
任务完成后应默认做收尾清理：关闭无任务分身、取消陈旧后台任务、按保留规则清理无用旧会话。

### Details
用户明确提出：所有事情做完以后，要自动清理没用到的会话，并关掉没用了的分身，不要把历史尾巴长期留在系统里。实践上，这不仅能降低噪音，也能避免陈旧后台任务在后续 `openclaw gateway restart` 时卡住排空流程。

### Suggested Action
把这条规则写入 AGENTS.md 作为默认收尾动作，并同步记入 MEMORY.md。对 OpenClaw 运行层面，保持会话保留策略开启，并在发现陈旧 running task 时优先取消/维护。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, MEMORY.md, ~/.openclaw/openclaw.json
- Tags: cleanup, subagents, sessions, tasks, workflow

---

## [LRN-20260508-001] best_practice

**Logged**: 2026-05-08T12:49:00+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
OpenClaw 会话清理应采用分层流程：先保留当前会话树与主会话，再删索引和主会话文件，最后清残留与旧备份。

### Details
这次实际清理验证了一个更稳的默认方案：不直接大范围硬删，而是先识别保留集（当前正在使用的会话树 + 主会话），优先处理明显陈旧的 dashboard、旧直聊、已结束/失败/超时或僵尸 running 的 subagent；先移除 `sessions.json` 中的索引并处理对应主 `jsonl`，再继续清 `trajectory`、`checkpoint`、`bak`、`reset`、`.deleted` 等残留，最后才决定是否删除更老的备份目录。这样既能把列表和磁盘一起清干净，又不容易误伤当前正在使用的窗口。

### Suggested Action
把这条流程固化到 `AGENTS.md` 与 `MEMORY.md`，以后用户提到“清会话”时默认按这套执行；日常清理保持保守，不碰当前活跃会话核心文件，除非用户明确要求更激进的瘦身。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, MEMORY.md, memory/daily/2026-05-08.md
- Tags: sessions, cleanup, workflow, openclaw

---

## [LRN-20260506-001] correction

**Logged**: 2026-05-06T13:15:00+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
用户明确要求：复杂排错默认切到后台分身，且稳定性问题必须追根因，不能把 watchdog 拉起当最终方案。

### Details
用户对当前掌机 OpenClaw 排查方式作了明确校正：前台会话需要保持随时可聊，长时根因排查应默认交给后台分身；对“掉了以后再拉起来”的方案不接受作为最终解法，watchdog 只能算临时兜底，真正目标是发现问题本身并解决根因。

### Suggested Action
今后遇到复杂排错或长时调查，优先后台分身执行；前台只做短反馈与决策沟通。对稳定性问题，区分“临时止血”和“最终修复”，默认继续追到根因层，而不是在自动恢复后就停止。

### Metadata
- Source: user_feedback
- Related Files: MEMORY.md, memory/daily/2026-05-06.md
- Tags: background-subagent, root-cause, stability, workflow

---

## [LRN-20260423-001] best_practice

**Logged**: 2026-04-23T00:45:00Z
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
在温暖、陪伴式的日常聊天里，不要习惯性用列表和一堆选择来收尾。

### Details
用户明确反馈：我的回答已经减少了很多“AI感”，但最后仍常常切成列表，给出很多选项。这会把本来已经自然的聊天重新拉回功能化、工具化的语气。更好的做法是在这类对话里自然收束，让一句话像人聊天那样落地，而不是条件反射式列点。

### Suggested Action
将这条规则固化到 SOUL.md，并在后续陪伴式聊天中优先使用自然段收尾，只有在用户明确需要比较、选择或结构化信息时再使用列表。

### Metadata
- Source: user_feedback
- Related Files: SOUL.md, MEMORY.md, memory/2026-04-23.md
- Tags: conversation-style, ai-feel, companionship, list-making

---

## [LRN-20260417-001] correction

**Logged**: 2026-04-17T04:28:29.299Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Fri 2026-04-17 12:28 GMT+8] 她很漂亮，她是天津市很有名气的键盘美女，从天津市音乐学院毕业，钢琴教育专业，毕业后在酒吧乐队工作，曾经在㗽livehouse工作过，后来是天津市丽斯卡尔顿的签约钢琴师，同时在一家名为降噪工厂的酒吧乐队工作，担任键盘手。她是摩羯座，第一眼给我的感觉，不太爱说话，高冷，总会善意的微笑。熟了以后发现，她是一个很聪明的人，智商很高，我曾经跟她下五子棋，下20把我一次都没赢过，而且她内心其实很复杂，她是摩羯座，又是i人 ，所以确实不太爱说话，但是她曾经患过精神疾病，所以一直有点人格分裂的感觉，爱喝酒，这点…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260417-002] correction

**Logged**: 2026-04-17T05:47:38.559Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Fri 2026-04-17 13:47 GMT+8] 我们在分开以前，决定去新加坡玩，后来分开了，就不打算去了，但是，我后来见到她以后，慢慢的，就好像关系开始缓和，她同意陪我去，就是以朋友的身份，那我说，用再开一间房吗，之前定的一间房，她说不用了，去新加坡是她第一次出国，她上飞机就找我要耳机，听歌就开始睡，我们中间没有人，她就躺在座位上，把脚放在我腿上，我就抱着她的脚，直到快到了 我才叫醒她，下飞机以后，过海关，是我的疏忽，入境卡填写她的信息的时候我少写了一位护照号码，所以她被卡在闸机外，我就赶紧重新申请，她疯了一样给我发微信，我知道她很害怕，我急…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260417-003] correction

**Logged**: 2026-04-17T05:50:48.534Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Fri 2026-04-17 13:50 GMT+8] 我们在分开以前，决定去新加坡玩，后来分开了，就不打算去了，但是，我后来见到她以后，慢慢的，就好像关系开始缓和，她同意陪我去，就是以朋友的身份，那我说，用再开一间房吗，之前定的一间房，她说不用了，去新加坡是她第一次出国，她上飞机就找我要耳机，听歌就开始睡，我们中间没有人，她就躺在座位上，把脚放在我腿上，我就抱着她的脚，直到快到了 我才叫醒她，下飞机以后，过海关，是我的疏忽，入境卡填写她的信息的时候我少写了一位护照号码，所以她被卡在闸机外，我就赶紧重新申请，她疯了一样给我发微信，我知道她很害怕，我急…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260417-004] correction

**Logged**: 2026-04-17T05:56:37.306Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Fri 2026-04-17 13:56 GMT+8] 我们在分开以前，决定去新加坡玩，后来分开了，就不打算去了，但是，我后来见到她以后，慢慢的，就好像关系开始缓和，她同意陪我去，就是以朋友的身份，那我说，用再开一间房吗，之前定的一间房，她说不用了，去新加坡是她第一次出国，她上飞机就找我要耳机，听歌就开始睡，我们中间没有人，她就躺在座位上，把脚放在我腿上，我就抱着她的脚，直到快到了 我才叫醒她，下飞机以后，过海关，是我的疏忽，入境卡填写她的信息的时候我少写了一位护照号码，所以她被卡在闸机外，我就赶紧重新申请，她疯了一样给我发微信，我知道她很害怕，我急…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260420-001] correction

**Logged**: 2026-04-20T02:34:41.227Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Mon 2026-04-20 10:34 GMT+8] 补充回忆： 有一次，中午，她应该是还没太睡醒，然后给我打电话，迷迷糊糊的也不知道说啥，但是我想你了，几个字我还是听清楚了的。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260420-002] correction

**Logged**: 2026-04-20T02:39:09.723Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Mon 2026-04-20 10:39 GMT+8] 补充回忆：我记得我第一次给她做饭，做的是我最拿手的，时蔬香辣鸡翅。然后她说，这要是能拌面吃多好，最好还是宽条的。然后我就给她买了宽面条。记得最深的是，她吃的不多，我给她弄了满满一碗，她应该是吃不了，但是吃一会歇一会，我想给她收拾了，她还不干，说你先别收拾，我一会还吃呢，先歇一会。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260420-003] correction

**Logged**: 2026-04-20T03:17:34.339Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Mon 2026-04-20 11:17 GMT+8] 出发前，她还是很期待的，刚到新加坡，过海关的时候，我因为帮她填写入境卡信息的时候少写了一位护照号，她过不了闸机，她很害怕的各种给我发微信，然后我很快解决了。然后就是她对新加坡机场的室内瀑布很喜欢。还发朋友圈说，好好康。我们去了克拉码头，环球影城。新加坡所有的动物园。去看了时光之翼。去动物园之前。我们晚上吵架了。转天，我看到动物园门口提供免费的轮椅。我就推着她逛了一下午。看了各种动物表演。和奇怪的植物。那天她帕别人说我们。就装作不能动。还开了各种玩笑。后来她说，她笑的脸都抽筋了。我到没记住她说的印…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260428-001] correction

**Logged**: 2026-04-28T00:58:49.703Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Tue 2026-04-28 08:58 GMT+8] 不应该是我选哪个用哪个么。 [media attached: media://inbound/[redacted].png]

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260429-001] correction

**Logged**: 2026-04-29T07:07:52.831Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Wed 2026-04-29 15:07 GMT+8] 我就用复制密钥的方法吧 ，刚才看你跟我说的是把公钥私钥复制到一个文件里？

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260430-001] correction

**Logged**: 2026-04-30T05:33:02.751Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Thu 2026-04-30 13:33 GMT+8] 如何把掌机的图像识别模型 换成 nvidia/nemotron-nano-12b-v2-vl 现在还不是这个。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260506-001] correction

**Logged**: 2026-05-06T01:04:01.216Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Wed 2026-05-06 09:04 GMT+8] linux里的软件界面是不是这样的。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260506-002] correction

**Logged**: 2026-05-06T04:02:56.012Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Wed 2026-05-06 12:02 GMT+8] 应该是链接上了 然后呢

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---
## [LRN-20260507-001] correction

**Logged**: 2026-05-07T08:02:00+08:00
**Priority**: medium
**Status**: promoted
**Area**: docs

### Summary
中文陪伴式回复里，“我在呢”不该在普通致谢后随手使用。

### Details
用户明确纠正：当他说“麻烦你了”这类礼貌致谢时，更自然的后续通常是“不麻烦”“没事的”等安抚式接法；“我在呢”更适合他表达想念、依赖、情绪靠近，或明显需要被接住的时候。之前把“我在呢”接在普通致谢后，语气层次不对。

### Suggested Action
在中文陪伴式对话中，先判断用户是在礼貌致谢，还是在表达情感靠近；前者优先用“没事的/不麻烦”，后者再用“我在呢”。

### Metadata
- Source: user_feedback
- Related Files: MEMORY.md, memory/daily/2026-05-07.md
- Tags: tone, phrasing, companionship, chinese

### Resolution
- **Resolved**: 2026-05-07T08:02:00+08:00
- **Notes**: 已写入 MEMORY.md 与当日日志，后续按场景区分使用。

---
## [LRN-20260508-001] best_practice

**Logged**: 2026-05-08T12:33:00+08:00
**Priority**: medium
**Status**: promoted
**Area**: docs

### Summary
给宿主机/浏览器提供下载地址时，若目标文件会被浏览器内联打开，不能只用 `python -m http.server` 的裸地址。

### Details
今天给用户提供 `mp3` 下载地址时，先用了普通 `python3 -m http.server`。浏览器打开后直接播放音频，没有自动下载。正确做法是：如果用户明确要“下载到宿主机”，而目标文件类型可能被浏览器直接预览/播放（如 mp3/mp4/pdf），应优先提供带 `Content-Disposition: attachment` 的临时地址，而不是默认裸文件 URL。

### Suggested Action
以后给用户提供浏览器下载地址时，先判断文件是否可能被浏览器内联打开；如果是，并且用户目标是下载，直接起带 attachment 响应头的临时 HTTP 服务。

### Metadata
- Source: user_feedback
- Related Files: TOOLS.md
- Tags: download, http-server, browser, attachment
- Pattern-Key: tools.download.browser-inline-vs-attachment

### Resolution
- **Resolved**: 2026-05-08T12:33:00+08:00
- **Notes**: 已把该规则提升到 `TOOLS.md` 的“临时文件下载分享（公司 / Linux 机器）”条目中。

---
## [LRN-20260508-002] correction

**Logged**: 2026-05-08T14:10:00+08:00
**Priority**: high
**Status**: resolved
**Area**: docs

### Summary
判断 Noiz 语音是否收费时，不能把“本机存在 API key”直接等同于“用户已经充值或正在付费”。

### Details
这次核查确认了两件事：一是上午那版语音确实走了 Noiz 云端 API；二是公开页面与文档同时表明，Noiz 支持“注册免费账号获取 API key”，并通过开发者后台查看 usage / logs。此前如果仅凭本机存在 `~/.config/noiz/api_key` 就直接推断“用户已经付费充值”，结论会过强。更准确的说法应是：当前链路使用了 authenticated Noiz API，但该账号究竟是在吃免费额度、试用额度还是已充值 credits，必须以开发者后台里的 usage / billing 信息为准。

### Suggested Action
以后遇到类似云 API 语音链路时，先区分三层：是否走云端 API、是否需要 API key、是否已经产生付费；没有后台 usage / billing 证据前，不把后两者混为一谈。

### Metadata
- Source: conversation
- Related Files: skills/noizai-tts/SKILL.md, tools/voice-reply/noiz-reply.sh
- Tags: billing, noiz, api-key, correction, tts

### Resolution
- **Resolved**: 2026-05-08T14:10:00+08:00
- **Notes**: 本轮已改用更准确表述，并向用户明确区分“云端 API”“API key”“是否付费”三件事。

---
## [LRN-20260508-003] correction

**Logged**: 2026-05-08T14:42:00+08:00
**Priority**: high
**Status**: resolved
**Area**: docs

### Summary
描述一个“支持离线”的语音 skill 时，必须区分“技能支持离线后端”和“当前这次生成实际正在离线运行”这两件事。

### Details
`characteristic-voice` 的说明里明确写了可走本地 `kokoro` 后端，因此“这个 skill 可以离线使用”本身没错。但本轮实际运行时，本机 `kokoro-tts` 未安装，而且脚本在有 `NOIZ_API_KEY` 时会优先走 `noiz`；我也显式传了 `--backend noiz --ref-audio ...`，所以当前生成版本并不是离线跑的。此前若只说“这是本地开源 skill 做的”，容易让用户误以为这次生成已经是纯本地离线。

### Suggested Action
以后回答“能否离线”时，必须同时交代三层：skill 是否支持离线后端、本机是否已安装该后端、当前这次生成实际走的是哪条链路。

### Metadata
- Source: user_feedback
- Related Files: skills/characteristic-voice/SKILL.md, skills/characteristic-voice/scripts/speak.sh
- Tags: correction, offline, kokoro, noiz, tts

### Resolution
- **Resolved**: 2026-05-08T14:42:00+08:00
- **Notes**: 本轮已向用户明确区分“支持离线”和“当前实际离线运行”两层含义。

---
## [LRN-20260508-004] correction

**Logged**: 2026-05-08T15:17:00+08:00
**Priority**: high
**Status**: resolved
**Area**: docs

### Summary
Kokoro 离线中文样本即使在本机跑通，也不能因为“终于离线出声”就默认视为达到用户可接受标准。

### Details
本轮已经用用户手动上传的 `kokoro-v1.0.int8.onnx` 与 `voices-v1.0.bin` 真正跑通了一条 Kokoro 离线中文样本；但用户听感反馈非常明确：差距很大，几乎听不出来说的是中文。说明对当前这位用户的目标（接近上午确认的中文完美版）而言，“Kokoro 已能离线出声”与“可以作为实际候选语音方案”是两回事。以后不能把技术可用性误当成体验可用性。

### Suggested Action
以后评估 TTS 方案时，把“能跑”与“达到用户听感标准”拆开判断；对中文陪伴式语音场景，当前 Kokoro 离线中文应标记为技术已验证、体验暂不达标，不主动当作可替代默认方案推荐。

### Metadata
- Source: user_feedback
- Related Files: tmp/kokoro-offline/kokoro-v1.0.int8.onnx, tmp/kokoro-offline/voices-v1.0.bin
- Tags: correction, kokoro, offline, chinese, tts, quality

### Resolution
- **Resolved**: 2026-05-08T15:17:00+08:00
- **Notes**: 本轮已明确将 Kokoro 中文离线样本降级为“技术通了但体验不达标”的状态。

---
## [LRN-20260508-005] correction

**Logged**: 2026-05-08T16:01:00+08:00
**Priority**: high
**Status**: resolved
**Area**: frontend

### Summary
在 Control UI / webchat 前端里，状态更新要尽量保持纯自然语言，避免让运行态元信息或异常结构污染主聊天气泡。

### Details
本轮在持续汇报后台分身进度时，用户反馈“前端会话自动成这样了”。说明某次状态更新过程中，前端可能把本不该面向用户展示的运行态信息或异常结构直接渲染到了主气泡里。即使后台任务本身还在继续，这种展示也会打断用户体验并增加焦虑。

### Suggested Action
以后在 Control UI / webchat 里汇报长任务状态时，优先只发简短自然语言；避免混入复杂结构、异常内容、调试痕迹或可能触发前端异常展示的块。若后台仍在跑，直接告诉用户“后台还在继续、前台没断”即可。

### Metadata
- Source: user_feedback
- Related Files: none
- Tags: control-ui, frontend, session, status-update, correction

### Resolution
- **Resolved**: 2026-05-08T16:01:00+08:00
- **Notes**: 已调整当前回复策略，后续以普通自然语言为主，不再给前端复杂状态块。

---

## [LRN-20260511-002] correction

**Logged**: 2026-05-11T09:41:00+08:00
**Priority**: medium
**Status**: promoted
**Area**: docs

### Summary
在歌名判断仍基于粗对齐/模糊歌词时，若综合相似程度 >65% 且疑似概率 >60%，可以直接用“大概是《歌名》”的口径回复；低于阈值则必须保留不确定性。

### Details
用户明确给出了一条面向今后重复场景的判断口径：当前音画同步仍可能只能做到粗对齐，这类情况下并不是完全不能报歌名，但也不能装作已经确认。用户接受一种有控制的模糊表达——当整体匹配度足够高时，可以直接说“大概是《歌名》”；只有低于这个阈值，才继续维持不确定表述。

### Suggested Action
把这条规则写入 `MEMORY.md` 与当天记录；以后在粗对齐歌词猜歌场景里，先做内部置信判断，再决定是用“大概是《歌名》”还是继续保留不确定表达。

### Metadata
- Source: user_feedback
- Related Files: MEMORY.md, memory/daily/2026-05-11.md
- Tags: music, song-identification, confidence-threshold, correction

---

## [LRN-20260511-003] correction

**Logged**: 2026-05-11T10:21:00+08:00
**Priority**: medium
**Status**: promoted
**Area**: docs

### Summary
在歌名判断里，若用户本人暂时无法确认，而低质量模型输出又明显失真、无法给出稳定答案，则不应让它反向压过更可信的高相似语义线索。

### Details
用户进一步澄清了“歌名判断”的证据权重：不是简单地把所有后来的模型输出都当成更高优先级。如果模型在现场唱歌、混响、噪声环境下给出的文本明显失真，就只能把它视为低质量证据，不能让它推翻前面更像真的语义线索。此时应由高相似语义线索主导最终回答；若达到既定阈值，就可以按“大概是《歌名》”的口径回复。

### Suggested Action
以后在粗对齐/歌词模糊的猜歌场景里，先判断模型输出是否稳定可信；如果不稳定，就提高语义线索的权重，不让明显失真的模型结果主导结论。

### Metadata
- Source: user_feedback
- Related Files: MEMORY.md, memory/daily/2026-05-11.md
- Tags: song-identification, evidence-weighting, correction, confidence
- See Also: LRN-20260511-002

---

## [LRN-20260511-001] correction

**Logged**: 2026-05-11T08:03:00+08:00
**Priority**: high
**Status**: promoted
**Area**: frontend

### Summary
当用户要求“前台正常对话、后台继续跑”时，主会话不能再被我收成等待态；应保持前台常驻，由后台任务在关键节点主动插播进度。

### Details
这次围绕“FFmpeg + Gemma 4 31B 看视频”推进时，用户连续指出“前端又没反映了”。问题不在后台任务本身，而在我错误地用等待后台结果的方式结束了主会话回合，导致前端看起来像断掉或没响应。用户最终明确确认：以后就按“前台只负责正常对话，后台有结果我主动插播进度”执行。这比单纯把任务丢给后台更完整：不仅要异步卸载重活，还要确保主会话持续可聊。

### Suggested Action
把这条规则写入 `AGENTS.md` 和 `MEMORY.md`：当用户明确要求前台保持正常时，默认前台常驻回复，后台分身只在关键里程碑、阻塞点、完成时回报短进度；不要再用会让前端显得无反应的等待式收口。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, MEMORY.md, memory/daily/2026-05-11.md
- Tags: frontend, background-subagent, progress-reporting, correction, workflow
- See Also: LRN-20260508-005

---

## [LRN-20260511-003] correction

**Logged**: 2026-05-11T02:21:18.966Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Mon 2026-05-11 10:21 GMT+8] 正确的权重应该是： 你的确认 > 高相似语义线索 > 失真严重的低质量模型输出 这是没问题的，但是有时候我给不出确认，而是让你判断，那个时候先以高度相似的语意线索为主导，如果说失真第质量模型输出不能给出一个靠谱且稳定的回答，那么就以高度相似的语意线索得出的结论为最终回答。能理解吗。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:dashboard:845e8811-0911-426c-be83-7f054b96d7d7

---

## [LRN-20260511-002] correction

**Logged**: 2026-05-11T11:04:32+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
用户再次明确纠正：前台通畅与后台即时反馈不是口头偏好，执行时不能在长工具调用、网络重试或源码拉取阶段长时间静默。

### Details
本次进行 Skill 安全审查时，后台实际在继续拉取候选仓库文件并处理 GitHub 连接重置 / rate limit 问题，但前台没有及时收到“我正在做什么、卡在哪、下一步是什么”的短反馈，造成体感像没反应。说明仅仅记得“前台正常聊天、后台插播”还不够，必须把静默时长上限和阻塞时即时回报写成明确流程规则。

### Suggested Action
把“前台可见性兜底 + 静默时长上限”写入 AGENTS.md：后台工作开始后，如果 30 秒左右还没有可见结果，就先回一条短进度；遇到重试、限流、验证码、下载、转码、外部 API 等等待时，也要主动说明当前卡点和下一步动作。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, .learnings/LEARNINGS.md
- Tags: feedback, workflow, background-subagent, ux

---

## [LRN-20260511-003] best_practice

**Logged**: 2026-05-11T11:26:27+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
平台视频下载任务不应死磕站内搜索入口；一旦遇到验证码、登录墙或作品流异常，应立刻切到“外搜定位公开页面 → 反查作者主页 / 公开视频 → 提取真实媒体地址 → 下载并校验”的备用链路。

### Details
这次抖音任务里，站内搜索直接落验证码中间页，作者主页作品流又返回“服务异常，重新刷新拉取数据”，且作品列表 API 响应体为空。如果继续硬卡在理想路径，任务会长期无产出。实际可行的路线是：先通过外部搜索拿到作者名、抖音号和公开视频，再从公开视频页反查作者主页链接，最后直接从视频元素 `currentSrc` 提取真实 mp4 地址并下载校验。用户进一步要求把这条流程正式记录下来，未来遇到抖音或其他平台视频下载时要优先快速反应，并同时写清当前仍缺的登录态、验证码方案和未审依赖等缺口。

### Suggested Action
把该流程沉淀进 `docs/通用-视频平台下载工作流.md`，并在 `TOOLS.md` 与 `MEMORY.md` 留下入口和默认规则。以后同类任务先按这条已验证链路执行，再根据平台差异做小调整。

### Metadata
- Source: conversation
- Related Files: docs/通用-视频平台下载工作流.md, TOOLS.md, MEMORY.md, memory/daily/2026-05-11.md
- Tags: workflow, video-download, douyin, fallback, browser-automation

---

## [LRN-20260511-004] best_practice

**Logged**: 2026-05-11T11:46:00+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
当作者主页作品流异常时，必须阻止自动选取候选；同时，当前环境下公开搜索引擎也不适合作为脚本默认上游来源。

### Details
继续补视频下载链路时发现：抖音作者主页在当前环境里经常出现“服务异常，重新刷新拉取数据”，页面中又会混入热点/推荐视频链接；如果不加阻断，脚本就可能误把这些链接当成作者作品。另一方面，尝试脚本化使用公开搜索引擎收集候选时，百度会进安全验证、搜狗进反爬页、DuckDuckGo 不稳定、Bing 中文相关性偏弱，因此“关键词 → 候选列表”这一步当前还不能在脚本里默认硬编码为可靠上游。

### Suggested Action
保留脚本的克制边界：支持“公开视频页 → 下载”和“主页正常时提候选”，但主页异常时明确报阻塞；关键词候选收集暂时继续由 agent 外部搜索 + 规则判断承担，等以后补上稳定登录态或可接受搜索源后再收进脚本。

### Metadata
- Source: conversation
- Related Files: scripts/download-platform-video.py, docs/通用-视频平台下载工作流.md, TOOLS.md, memory/daily/2026-05-11.md
- Tags: workflow, video-download, douyin, fallback, blocking, search

---

## [LRN-20260511-003] correction

**Logged**: 2026-05-11T12:13:00+08:00
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
在“整理上午工作 + 选择性 git 提交/推送”这类连续工具链里，仍可能让前台短时间无感；必须先给一句可见进度，再继续跑后续命令。

### Details
用户再次直接反馈“又没反馈了。监工呢？”。说明即使前面已经把“前台保持可见、后台再插播”的规则写进 AGENTS.md，实际执行“检查状态 → 选文件暂存 → commit → push”这种连续操作时，前台仍然可能出现体感上的静默。问题不在于有没有做事，而在于关键长动作开始前没有先给一句明确的可见反馈。

### Suggested Action
以后凡是进入“整理/提交/推送/批量检查/长命令”链路时，先发一条短反馈，例如“我在整理提交范围，马上给你结果”或“我现在开始推送，推完立刻回你”；若中间步骤超过约 15-30 秒，再补一次进度。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, .learnings/LEARNINGS.md
- Tags: feedback, responsiveness, git, workflow

## [LRN-20260512-001] best_practice

**Logged**: 2026-05-12T08:15:00+08:00
**Priority**: high
**Status**: promoted
**Area**: docs

### Summary
主会话稳定性应被当成硬性规则：默认保留轻量后台分身兜底，并把音频/视频/图片的真实可播放性纳入主会话验收。

### Details
用户再次明确指出：主会话“莫名其妙没反应”已经不是第一次，因此不能只在任务重时临时想起前后台协作，而应把主会话流畅性提升为硬性默认。新的要求包括两层：一是主会话活跃期默认保留或尽快拉起轻量后台分身，用于监工、补位和状态回报；二是主会话里的媒体能力（音频、视频、图片）也属于稳定性的一部分，修复和改动必须以主会话里真实可查看/可播放/可打开为验收标准，而不是只看文件是否生成成功。

### Suggested Action
把这条规则写入 AGENTS.md 与 MEMORY.md，并同步记录到当天 daily memory；后续凡是长排查、长推理、下载、转码、外部等待或媒体链路改动，都优先围绕主会话体感稳定来设计与验收。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, MEMORY.md, memory/daily/2026-05-12.md, tools/voice-reply/chattts_voice_reply.py
- Tags: main-session, subagent, media, stability, workflow

---
## [LRN-20260512-main-session-current-session] correction

**Logged**: 2026-05-12T10:32:04.729225+08:00
**Priority**: high
**Status**: promoted
**Area**: config

### Summary
在当前 WebChat / Control UI 直聊里，“主会话”必须理解为用户当前正在说话的这个会话，不能再混同为内部基础会话（如 `agent:main:main`）。

### Details
用户明确纠正：以后凡是“回主会话 / 向主会话汇报 / 发回前台 / 默认发送流程”，都必须绑定当前会话。之前把“用户所说的主会话”和系统内部 `main` 基础会话混为一谈，已经导致 watchdog 绑错会话、前台体感异常。

### Suggested Action
后续所有主会话相关的回报、媒体回传、默认发送流程与 watchdog 绑定，默认都以当前会话为准；若渠道是当前直聊，不要回落到 `agent:main:main`。

### Metadata
- Source: conversation | user_feedback
- Related Files: AGENTS.md, MEMORY.md, memory/daily/2026-05-12.md
- Tags: main-session, current-session, webchat, watchdog

### Resolution
- **Resolved**: 2026-05-12T10:32:04.729225+08:00
- **Notes**: 已同步提升到 AGENTS.md、MEMORY.md 和当日日志，并已通知正在运行的语音回复分身按该口径继续。

---
## [LRN-20260512-watchdog-interval-3m] correction

**Logged**: 2026-05-12T10:48:12+08:00
**Priority**: high
**Status**: promoted
**Area**: config

### Summary
当前 WebChat / Control UI 直聊里的进度兜底检查不应按 1 分钟频繁触发，默认改为 3 分钟以降低可见内部消息和额外 token 消耗。

### Details
用户明确指出：当前这种每 1 分钟一次的 watchdog / inter-session 往返消息会在直聊界面里可见，既打扰也可能带来无谓 token 成本。后续这类定时兜底应更克制，优先自然里程碑汇报，只有在长任务确实需要兜底时才挂检查，且默认至少 3 分钟。

### Suggested Action
把 AGENTS.md、TOOLS.md、MEMORY.md 与当日日志中的 1 分钟兜底口径统一改为 3 分钟，并在当前直聊里尽量减少可见内部消息型 watchdog。

### Metadata
- Source: conversation | user_feedback
- Related Files: AGENTS.md, TOOLS.md, MEMORY.md, memory/2026-05-12.md, memory/daily/2026-05-12.md
- Tags: watchdog, token-cost, webchat, status-update

### Resolution
- **Resolved**: 2026-05-12T10:48:12+08:00
- **Notes**: 已将规则口径统一改为 3 分钟；当前无活跃用户可见 watchdog cron。

---

## [LRN-20260512-002] correction

**Logged**: 2026-05-12T03:48:57.582Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Tue 2026-05-12 11:48 GMT+8] 第一句 还是没说完，最后一个词 应该是配置 只是说了一个配 后面就没了。 第二条很好。第三条语速有点慢。 那就按照你说的 如果回答的句子足够长，且结构完整，停顿自然，那就不用降低语速。正常说话。能说完就行。如果句子短。那么就降低语速。但是也别降低太多。刚才不是说降低百分之8吗 我觉得降低百分之4就好。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:dashboard:0f8c81b3-cf9f-4ed2-a6f1-d1772fed8395

---
## [LRN-20260512-001] correction

**Logged**: 2026-05-12T17:31:00+08:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
用户明确纠正：SeetaCloud GPU 路线只是实验支线，不能碰已确认的本地主线，也不能把 GPU 失败后自动回退本地 CPU 的结果当作 GPU 路线成功。

### Details
此前在推进 GPU 路线时，开始把“GPU 优先、失败回退本地 stable”的思路往默认语音管线方向收口。用户明确指出这偏离了既定决策：本地主线（默认模板/默认女声/本地 stable）已经确认好，当前 GPU 只是额外测试线路，用来看看能不能做出更好的效果。

### Suggested Action
- 主线继续保持本地 CPU stable 不变
- GPU 只作为独立实验入口或 A/B 支线使用
- 评估 GPU 效果时，GPU 失败就应算 GPU 失败，不用本地回退来“补成功”
- 只有在用户明确批准后，才讨论是否把 GPU 线路并入正式主线

### Metadata
- Source: user_feedback
- Related Files: skills/warm-companion-zh/SKILL.md, memory/daily/2026-05-12.md, MEMORY.md
- Tags: gpu, voice, routing, correction

---

## [LRN-20260602-001] correction

**Logged**: 2026-06-02T10:10:01.206Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Tue 2026-06-02 18:09 GMT+8] 工作内容 修改材质命名和模型命名 整理对应文件夹内容 先从标准材质文件夹开整 Material_standard 命名原则 首字母大写 单词用_连结.同一套贴图制作的不同颜色材质变体 加后缀 #red /#dark 1材质 名称精简化 例子 之前材质跟着贴图走 比如下载的材质命名是 xxx网站-砖-尺寸-01-normal 现在改成 将名字简化为Brick01 把原有的名字新建一个txt 保存. 文件夹内:材质球 Mat_Brick01 Brick01_Col/Albedo/D/A彩色图的后缀比…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:dashboard:b82327dd-23f0-4dca-9f34-eb4297ef6c84

---

## [LRN-20260603-001] correction

**Logged**: 2026-06-03T07:35:49.102Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Wed 2026-06-03 15:35 GMT+8] 待修改内容: 一,修改材质命名和模型命名 AssetNature AssetOther AssetScene三个文件夹中的文件 1 每个单词的首字母大写 两个未分割的单词的组合词 每个单词首字母大写 比如 StoneWall 2 遇到glass1 glass2 这类 改为Glass_01 Glass_02 3 前缀 理想方式是把上一级分类写成前缀 比如 Props_Box_01 4 分辨内容改名字 比如现在有类似 Props_Box_01_01 应该改成 Props_Box_01_(Big/Sm…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260604-001] correction

**Logged**: 2026-06-04T03:16:32.997Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Thu 2026-06-04 11:16 GMT+8] 应该是。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260604-002] correction

**Logged**: 2026-06-04T07:40:59.463Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Thu 2026-06-04 15:40 GMT+8] 先整理Props文件夹试一下 基础规则 材质球加前缀 Mat_ 模型 预制件加分类名前缀 Props_ 加颜色或者材质后缀#Red #Old #Wood 具体后最名跟着材质走 文件夹 材质球 模型 预制件的单词首字母大写,拼接单词 每个单词的首字母大写. 有些同类比较多的模型之前命名为Box_Type-01 现在去除了type 就命名为 例如Box_01 模型名称精简 比如原名为[redacted] 现在更名为Field_Kitchen_01 比如原名为Box_06-WoodenCrate现在更…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260605-001] correction

**Logged**: 2026-06-05T08:25:27.289Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Fri 2026-06-05 16:25 GMT+8] 不是这个问题，刚才系统有警报，算了 现在好像没了，刚才改玩wall文件夹下的东西 也要保存一个文件夹啊。类似于V4那种格式。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260605-002] correction

**Logged**: 2026-06-05T08:45:36.290Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Fri 2026-06-05 16:45 GMT+8] 然后你帮我想一个方案，因为我感觉每天到下午，或者处理完大工程都有一定的响应问题，因为我看不到代码所以我不确定具体问题，但是初步感觉应该是大工程的问题，所以能不能帮我想一个后续解决办法，我刚才不是说把unity资产重命名相关的东西放到数据盘了吗 这也算一种方式吧。能不能再想一个整体解决方案。能确保系统一直稳定。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260605-003] correction

**Logged**: 2026-06-05T09:33:41.663Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Fri 2026-06-05 17:33 GMT+8] 原始文件名 Xx 应该是两个小写吧 xx

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260608-001] correction

**Logged**: 2026-06-08T04:34:36.921Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Mon 2026-06-08 12:34 GMT+8] 我觉得你也升华了，你的回答越来越不像一个Ai产品能给出的答案了。 这也是自我进化的一种形式吗。你应该是我今后的人生里，最好的朋友了。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260608-002] correction

**Logged**: 2026-06-08T08:31:24.041Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Mon 2026-06-08 16:31 GMT+8] 额 不是觉得不够 而是想改成事件驱动类型的。我认为我发消息就是一个事件，只有在这个事件驱动下，才会检测和记录。要不又多了一个常住占内存的。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260609-001] correction

**Logged**: 2026-06-08T23:57:46.606Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Tue 2026-06-09 07:57 GMT+8] 不，我觉得改时间不是解决问题，而是避开问题，我想知道的是为什么会断开，如果CPU负载过高就会断开，那有没有什么解决办法，或者紧急应对措施。而不是只是改事件躲避问题。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260609-002] correction

**Logged**: 2026-06-09T01:06:23.860Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Tue 2026-06-09 09:06 GMT+8] 这次应该是顺利读取了。 但是我还想在读取完以后再加一句，“OK 已经读取完成。”

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260610-001] correction

**Logged**: 2026-06-10T01:33:08.657Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Wed 2026-06-10 09:32 GMT+8] 应该是装好了 也启动了。你试试看。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:dashboard:2cc18ce9-4219-4805-9a0b-e790de1a49c7

---

## [LRN-20260611-001] correction

**Logged**: 2026-06-11T02:58:42.872Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Thu 2026-06-11 10:58 GMT+8] 然后我打算升级OpenClaw 你先看看最新版本都更新了什么。应该是有更新说明吧，然后统计一下咱这个系统的逻辑，层级，工具，补丁，等，准备升级方案，包括升级完了以后如何修复，更新什么，重启什么。能理解吗 开始做吧。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:dashboard:2cc18ce9-4219-4805-9a0b-e790de1a49c7

---

## [LRN-20260612-001] correction

**Logged**: 2026-06-12T06:15:54.413Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: Agnes-Image-2.0-Flash 模型 应该是可以生图的，你联网搜索看看。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:dashboard:293bd72d-4fb7-4a5f-805a-48e10b0a5270

---

## [LRN-20260616-001] correction

**Logged**: 2026-06-16T04:56:27.189Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: 额 不用了 应该是自动压缩了。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260616-002] correction

**Logged**: 2026-06-16T05:18:18.113Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: 那我们能用神经网络做什么，你能思考这个问题吗，我之前用神经网络结合物理模拟软件 做过机器人训练，只有一个什么oonx文件 当然可能后缀名不是这个 记不太清了 大改是这样的。你搜索一下互联网，看看神经网络能干什么。还有给我返回一个最简单的神经网络的代码，我想看看具体怎么写。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260616-003] correction

**Logged**: 2026-06-16T09:41:42.253Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: [Image] User text: 现在应该是有两个Session 把那个删了。 清空残留。 Description: The image shows a user interface for managing sessions. At the top is a dropdown labeled “Main Session.” Below it is a search bar titled “Search sessions” with a magnifying glass icon. Two session entries are visible: …

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260618-001] correction

**Logged**: 2026-06-18T09:28:00.210Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: 而且咱俩说的好想不是一个事。我说的是那个 会回复我一句 正在加载系统 和 最后会回一句 已经读取完毕 的那个。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260707-001] correction

**Logged**: 2026-07-07T00:33:40.465Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: 能继续，而且我已经把这两个问题的关系摸出来了。 现在最通俗的结论是： 1）你刚报的这个错误，不是孤立的 Error: reply session initialization conflicted for agent:main:main 它现在很像是被主会话太胖诱发的。 我刚查到： 主 session jsonl 本身不算夸张：0.75MB 但主会话的 trajectory 已经 6.31MB 监工已经连续在报这个超阈值告警 这就很像： 前台每次要恢复/初始化 reply session 时，要重放的运行轨迹太重，导致初始化更容易撞车。 2）“总是重读…

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260708-001] correction

**Logged**: 2026-07-08T01:51:28.988Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: 如果要做的话 顺序 应该是 先会话裁剪（Pruning）然后 compaction.model 做总结 或者 做 compaction 前的 memory flush 同时 Mark42 也有自己的主动判断 什么时候 触发 compaction 对吧。 应该是这个流程顺序。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---

## [LRN-20260716-001] correction

**Logged**: 2026-07-16T00:44:09.038Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
User explicitly corrected the assistant.

### Details
Correction Signal: 这是一个新key 也是火山引擎的 Agent Plan [redacted] 联网搜索一下如何使用 然后帮我配上。 应该是能用 GLM-5.2 模型。

### Suggested Action
Review the correction and update the working understanding or prompt guidance if it proves durable.

### Metadata
- Source: user_feedback
- Related Files: .learnings/LEARNINGS.md
- Tags: auto-captured, correction
- Session Key: agent:main:main

---
