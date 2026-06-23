# SKILL_CATALOG.md — Skill 目录

> 换模型/新会话必读。需要详细用法时读对应 SKILL.md。

## 🫂 陪伴
| Skill | 用途 |
|-------|------|
| `warm-companion-zh` | 中文温暖陪伴 |
| `ex-qianqian` | 千千口吻模拟 |
| `characteristic-voice` | TTS 情绪/人格 |

## 🎤 语音
| Skill | 用途 |
|-------|------|
| `tts` | Noiz TTS 文字转语音 |
| `chattts-stable` | 本地 ChatTTS |
| `elevenlabs-music-generation` | 音乐/配乐生成 |

## 🖼️ 图像/视频
| Skill | 用途 |
|-------|------|
| `nvidia-build-image` | NVIDIA 文生图 |
| `creaa-ai` | Creaa.ai 图/视频生成 |
| `runninghub` | RunningHub 222端点 |
| `video-frames` | ffmpeg 视频帧提取 |
| `douyin` | 抖音下载 |
| `canvas-design` | 海报/艺术品设计 |

## 🔍 搜索
| Skill | 用途 |
|-------|------|
| `web-claude` | 统一搜索（默认） |
| `tavily` / `tavily-search` | AI 优化搜索 |
| `multi-search-engine` | 17引擎聚合 |
| `agent-browser` | 无头浏览器 |
| `browser-automation` | 复杂网页交互 |
| `agent-reach` | 10+平台一键读取（见下） |

### agent-reach 渠道速查
| 平台 | 方式 |
|------|------|
| 网页 | `curl https://r.jina.ai/URL` |
| 搜索 | Exa via mcporter |
| YouTube | `yt-dlp` |
| B站 | `bili` / API |
| RSS | `feedparser` |
| Twitter/X | OpenCLI |
| 小红书 | OpenCLI |
| Reddit | OpenCLI / `rdt-cli` |
| GitHub | `gh` CLI |
| V2EX | 直连 API |

## 📄 文档
| Skill | 用途 |
|-------|------|
| `minimax-docx` | Word 文档 |
| `pptx-generator` | PPT 演示 |
| `frontend-design` | 前端界面 |
| `ux-architect` | CSS/布局/主题 |

## 🛠️ 开发
| Skill | 用途 |
|-------|------|
| `skill-creator` | 新建/修改 Skill |
| `skill-vetter` | 安装前审查 Skill |
| `karpathy-guidelines` | 减少 LLM 编码错误 |
| `humanizer-zh` | 中文去 AI 痕迹 |
| `find-skills` | 搜索安装 Skill |
| `clawhub` | Skill 注册表管理 |
| `trae-agent-engineering` | trae-cli 工程任务标准调用流程（多文件重构/加功能/跑测试） |

## ⚙️ 系统
| Skill | 用途 |
|-------|------|
| `healthcheck` | 宿主机安全审计 |
| `taskflow` | 后台任务编排 |
| `self-improvement` | 捕捉错误/持续改进 |
| `proactive-agent-lite` | 主动伙伴模式 |
| `ontology` | 知识图谱 |

## 🌤️ 其他
| Skill | 用途 |
|-------|------|
| `weather` | 天气查询 |
| `officecli` | Word/Excel/PPT CLI |
| `ponytail` | 极简代码审查 |
| `huashu-nuwa` | 女娲 AI |

> 匹配规则：用途明显落入 Skill 范围时，先读 SKILL.md 再执行。共 31+ Skill · 更新于 2026-06-23
