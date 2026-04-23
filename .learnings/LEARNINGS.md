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
