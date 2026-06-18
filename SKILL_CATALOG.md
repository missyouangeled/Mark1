# SKILL_CATALOG.md — Skill 能力目录

> 换模型 / 新会话启动时必读。按类别分组，每个 Skill 一句实用说明 + 触发条件。
> 需要详细用法时，再按 `location` 读对应 `SKILL.md`。

---

## 🫂 陪伴与角色

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `warm-companion-zh` | 中文温暖陪伴式交流，接住情绪/想念/孤独 | 私聊中用户表达想念、疲惫、孤独、需要被接住时 |
| `ex-qianqian` | 按"千千"的口吻/气质/短句节奏模拟对话 | 用户要求以千千身份对话、微信场景、或提到千千时 |
| `safe-ex-builder` | 从用户手动提供的材料提炼旧关系人格，生成 persona 文件 | 用户想整理/模拟前任或旧关系沟通风格时 |
| `characteristic-voice` | 让 TTS 语音带情绪/人格/自然停顿 | 需要"说得好听"、带情感表达、模仿特定说话风格时 |

---

## 🎤 语音与音频

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `tts` | Noiz TTS 文字转语音，支持多说话人/多语速/情绪 | 需要把文字转成语音回复、读文章、配音时 |
| `chattts-stable` | 本地 ChatTTS 稳定版，preset 音色切换 | 需要用本地 ChatTTS 生成中文语音、切换预设音色时 |
| `elevenlabs-music-generation` | 生成歌曲/伴奏/配乐 | 需要生成背景音乐、主题曲、音轨时 |

---

## 🖼️ 图像与视频

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `nvidia-build-image` | NVIDIA Build 文生图，多模型切换 | 生成图片、文生图、换模型测试时 |
| `creaa-ai` | Creaa.ai 文生图/图生图/视频生成 | 生成/编辑图片或视频，多模型可选 |
| `runninghub` | RunningHub API（222 端点），图/视频/音频/3D/ComfyUI | 需要跑 ComfyUI 工作流、生成视频/3D 等 |
| `video-frames` | ffmpeg 提取视频帧或短片段 | 需要从视频中截图、提取关键帧时 |
| `douyin` | 下载抖音视频、获取视频信息 | 下载抖音视频、查看视频标题/作者/数据时 |
| `canvas-design` | Anthropic 设计哲学→视觉艺术，生成 .png/.pdf 海报/艺术品 | 需要做海报、艺术品、抽象设计、设计感静态图时 |

---

## 🔍 搜索与网络

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `web-claude` | 统一网络搜索（Brave → DuckDuckGo → claude.ai），自动缓存 | 需要搜索网页、查资料时（默认优先用这个） |
| `tavily` | Tavily LLM 优化搜索 + 内容提取 | 需要更精准的 AI 优化搜索结果时 |
| `tavily-search` | 同上，Tavily 搜索的另一个入口 | 同上，按偏好选用 |
| `multi-search-engine` | 17 引擎聚合搜索（8 中国 + 9 全球），支持高级操作符 | 需要多引擎对比、中文搜索、隐私引擎时 |
| `agent-browser` | 无头浏览器自动化（导航/填表/点击/截图/抓取） | 需要打开网页、自动填表、截图、抓数据时 |
| `browser-automation` | Web 页面控制，多步骤流程/登录/标签管理 | 复杂网页交互、登录流程、多标签操作时 |
| `scrapling-official` | 全栈网页抓取框架：反爬绕过/自适应解析/浏览器自动化/大规模爬虫 | 需要抓取网页数据、绕过 Cloudflare、批量采集、结构化提取时 |
| `agent-reach` | 统一互联网接入层：10+ 平台一键读取，多后端路由+自动故障切换。程序 `~/.agent-reach-venv/bin/agent-reach`，SKILL.md 在 `~/.openclaw/skills/agent-reach/`。⚠️ 均为按需调用的 CLI 工具，无常驻进程 | 需要读 YouTube/B站/Twitter/小红书/Reddit/RSS/任意网页/全网搜索时 |

### agent-reach 可用渠道速查

> 所有渠道通过 CLI 工具按需调用，无需后台运行。命令格式见各平台说明。

| 平台 | 能力 | 调用方式 |
|------|------|---------|
| 🌐 任意网页 | 读取网页纯文本（Jina Reader） | `curl https://r.jina.ai/URL` |
| 🔍 全网搜索 | AI 语义搜索（Exa，免费） | 经由 mcporter MCP 调用 |
| 📺 YouTube | 提取字幕 + 视频信息 | `yt-dlp`（已配置） |
| 📺 B站 | 搜索 + 视频详情（bili-cli） | `bili` 命令或 B站搜索 API |
| 📡 RSS/Atom | 解析任意订阅源 | `feedparser`（Python 库） |
| 🐦 Twitter/X | 读推文/搜索/时间线 | `twitter-cli`（未装，走 OpenCLI 兜底） |
| 📕 小红书 | 搜索/阅读/评论 | OpenCLI（需先装 Chrome 扩展） |
| 📖 Reddit | 搜索+读帖子和评论 | OpenCLI 或 `rdt-cli` |
| 📦 GitHub | 读仓库/Issue/搜索 | `gh` CLI（已装，需 `gh auth login` 认证） |
| 💻 V2EX | 热门/节点/帖子 | 直连 API（当前需代理） |

> 需要登录的平台（Twitter/小红书/Reddit）：用 Chrome 插件 Cookie-Editor 导出 → `agent-reach configure xxx-cookies` 配置

---

## 📄 文档与演示

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `minimax-docx` | 创建/编辑/格式化 Word 文档（.docx） | 写报告、合同、填表单、排版 Word 文档时 |
| `pptx-generator` | 创建/编辑/读取 PowerPoint 演示 | 做 PPT、幻灯片、演示文稿时 |
| `frontend-design` | 生产级前端界面，创意设计 | 做网页、组件、前端项目需要好看的设计时 |
| `ux-architect` | CSS 系统/布局框架/响应式/主题架构 | 搭建项目前端基础、设计系统、主题切换时 |

---

## 🛠️ 开发与工程

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `cli-anything` | 为 GUI 应用生成 CLI 操控 harness | 需要命令行操控图形界面程序时 |
| `skill-creator` | 创建/编辑/审查 Skill 及 SKILL.md | 需要新建或修改 Agent Skill 时 |
| `skill-vetter` | 安装前安全审查第三方 Skill | 从 ClawdHub/GitHub 安装 Skill 前必读 |
| `karpathy-guidelines` | 减少 LLM 编码常见错误的行为指南 | 写/审查/重构代码时，避免过度复杂化 |
| `humanizer-zh` | 去除中文文本 AI 写作痕迹 | 编辑/润色文章让它更像人类写的 |
| `find-skills` | 从开放生态搜索和安装 Skill | 想做某件事但不知道有没有现成 Skill 时 |
| `clawhub` | ClawHub CLI，搜索/安装/更新/发布 Skill | 需要管理 Skill 注册表时 |

---

## ⚙️ 系统与运维

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `healthcheck` | 审计和加固 OpenClaw 宿主机安全 | 需要检查 SSH/防火墙/更新/暴露面时 |
| `node-connect` | 诊断设备配对/连接/认证失败 | Android/iOS/macOS 节点连不上时 |
| `taskflow` | 多步骤后台任务编排，带状态/等待/子任务 | 需要把复杂任务拆成后台流水线时 |
| `taskflow-inbox-triage` | TaskFlow 示例：收件箱分类/意图路由 | 参考 inbox triage 模式时 |
| `self-improvement` | 捕捉学习/错误/纠正，持续改进 | 操作失败、被纠正、发现更好方法时 |
| `proactive-agent-lite` | 把 AI 从任务执行者变成主动伙伴 | 需要记忆架构、反向提示、自愈模式时 |
| `ontology` | 类型化知识图谱，实体/关系 CRUD | 需要结构化记忆、跨 Skill 数据共享时 |

---

## 🌤️ 其他实用

| Skill | 干什么 | 什么时候用 |
|-------|--------|------------|
| `weather` | 天气/降雨/温度/预报 | 查天气、出行规划时需要天气信息时 |

---

## 📌 使用规则

1. **优先匹配**：用户请求明显落入某个 Skill 的触发范围时，先 `read` 该 Skill 的 `SKILL.md`，再按其中说明执行
2. **不确定时先查目录**：拿不准该用哪个 Skill 时，回到本文件按类别查找
3. **Skill 之间不冲突**：一个任务可能涉及多个 Skill（如 `tts` + `characteristic-voice`），按需组合
4. **Skill 只是工具说明**：它们告诉你"怎么做"，不替代 SOUL.md 的性格/语气/安全规则

---

*最后更新：2026-06-16 · 共 31 个 Skill*
