# TOOLS_INDEX.md — 工具详细索引

> ⚠️ **每次启动必须读取本文件**（BOOT_INDEX.md 第 4 步按需加载）
> 作用：主导航表之外的"详细文档"二级索引。TOOLS.md 只放主导航，详细内容来这里找。
> 索引规则：先看 TOOLS.md 的主导航 → 找到分类 → 跳到本文件查具体文档 → 再按需 read 文件

---

## 0. 启动自检清单（任何模型上来先确认）

- [ ] 我是谁？→ SOUL.md
- [ ] 主人在帮谁？→ USER.md
- [ ] 我会哪些工具（核心）？→ read / write / edit / exec / process / web_search / web_fetch / image / image_generate / cron / sessions_*
- [ ] 我在帮主人找什么？→ 读当前用户消息 + 调 memory_search 拿历史上下文
- [ ] 我有"主人"的长期记忆吗？→ MEMORY.md

---

## 1. 凭据 / API 密钥 / SSH

| 需求 | 路径 | 备注 |
|---|---|---|
| 找 OpenClaw 所有凭据指针 | [docs/tools/credentials.md](docs/tools/credentials.md) | API 密钥、SSH host、token |
| 个人 / 公司 / 免费 API 归属清单 | [docs/贾维斯中枢-API密钥清单.md](docs/贾维斯中枢-API密钥清单.md) | 改密钥前必看 |
| SSH 远端 GPU 节点 | docs/tools/credentials.md#ssh | 公司 GPU 节点列表 |

## 2. OpenClaw 自动化 / 监工 / watcher

| 需求 | 路径 |
|---|---|
| OpenClaw 自动化总览 | [docs/tools/openclaw-automation.md](docs/tools/openclaw-automation.md) |
| Watcher 体系（目录/文件监听） | [docs/tools/watchers.md](docs/tools/watchers.md) |
| 监工 / 后台插播服务 | [docs/tools/supervisor.md](docs/tools/supervisor.md) |
| 升级后自检 / 升级记录 | [docs/tools/openclaw-automation.md#upgrade](docs/tools/openclaw-automation.md) |
| 大工程 / scratch / 批量改名 | [docs/tools/openclaw-automation.md#batch](docs/tools/openclaw-automation.md) |

## 3. 视频平台下载

| 需求 | 路径 | 备注 |
|---|---|---|
| 视频下载默认工作流 | [docs/tools/openclaw-automation.md#video](docs/tools/openclaw-automation.md) | |
| 抖音 / B站 / YouTube 下载脚本 | `scripts/jarvis-dl-*.sh` | 见 tools 目录 |

## 4. OCR 文字识别

| 需求 | 路径 |
|---|---|
| OCR 脚本 | `scripts/jarvis-ocr.py` / `tools/jarvis-ocr.sh` |
| Mark2 小模型清单 | [docs/tools/openclaw-automation.md#mark2](docs/tools/openclaw-automation.md) |

## 5. 语音 / TTS

| 需求 | 路径 | 备注 |
|---|---|---|
| 语音回复总览 | [docs/tools/voice-tts.md](docs/tools/voice-tts.md) | |
| 本地 ChatTTS | `skills/chattts-stable/SKILL.md` | 稳定中文 TTS |
| Noizai TTS | `skills/noizai-tts/SKILL.md` | 备用 |
| XTTS 声音克隆 | [docs/tools/voice-tts.md#xtts](docs/tools/voice-tts.md) | 需 GPU |
| ChatTTS 配置 | `local_free_voice_cloning_stack` 见 voice-tts.md | |

## 6. 资源/常驻服务

| 资源 | 路径 |
|---|---|
| 本地 ChatTTS | [docs/tools/voice-tts.md](docs/tools/voice-tts.md) |
| 本地声音克隆栈 | [docs/tools/voice-tts.md#xtts](docs/tools/voice-tts.md) |
| 远端 GPU 节点 | docs/tools/credentials.md#ssh |

## 7. 模型路由

| 需求 | 路径 |
|---|---|
| 路由问题排查手册 | [docs/通用-AI模型路由问题排查与修复手册.md](docs/通用-AI模型路由问题排查与修复手册.md) |
| 非主模型使用手册 | [docs/非主模型使用手册.md](docs/非主模型使用手册.md) |

## 8. Skills 目录入口

- 完整目录：`SKILL_CATALOG.md`（启动链第 4 步必读）
- 单个 skill：`skills/<name>/SKILL.md`

---

## 9. 关键文件速查（10 秒内定位）

| 找什么 | 看哪 |
|---|---|
| 我是谁 | SOUL.md |
| 主人在帮谁 | USER.md |
| 我的长期记忆 | MEMORY.md |
| 启动入口 | BOOT_INDEX.md |
| 工具主导航 | TOOLS.md |
| 工具详细（=本文件） | TOOLS_INDEX.md |
| 行为协议 | rules/agents-core.md |
| 域规则 | RULES_INDEX.md |
| 凭据 | docs/tools/credentials.md |
| API 密钥归属 | docs/贾维斯中枢-API密钥清单.md |
| 模型路由 | docs/通用-AI模型路由问题排查与修复手册.md |
| 崩坏案例 | docs/对系统操作必须要参考的崩坏案例.md |
| 安装记录 | docs/install-registry.md |
| 项目入口 | PROJECT_INDEX.md |
| 方案存档 | PLANS.md |

---

## 10. 维护说明

- 本文件由贾维斯维护（Mark42 v2.2 分层加载体系）
- 每次新增"详细工具文档"时，只改本文件；TOOLS.md 不动
- TOOLS.md 的"详细文档索引"表是**镜像引用本文件**，不要双写
- 文件行数硬上限 120 行
