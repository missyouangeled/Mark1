# TOOLS_INDEX.md — 工具与本机环境索引

> 这是 `TOOLS.md` 的二级索引。只放入口、用途和关键词，不放凭据明文。

## 使用原则

- 详细内容仍在 `TOOLS.md`
- 本文件只负责帮你快速定位章节
- 敏感信息只记录路径与边界，不记录明文

## 1. OpenClaw 自动化 / 系统总览

| 主题 | 去哪找 | 用途 / 关键词 |
|---|---|---|
| OpenClaw automation | `TOOLS.md` → `OpenClaw automation` | 启动、升级、自检、统一维护入口 |
| 系统一眼总览 | `TOOLS.md` → `OpenClaw automation` | `openclaw-system-summary.py` |
| 当前正式架构状态 | `TOOLS.md` → `OpenClaw automation` | 正式运行组件/历史回退/可选组件 |
| Git 工作区污染规则 | `TOOLS.md` → `OpenClaw automation` | 提交前边界、哪些能进 Git |

## 2. 大工程 / Unity / scratch / 批量改名

| 主题 | 去哪找 | 用途 / 关键词 |
|---|---|---|
| 大工程稳定运行方案 | `TOOLS.md` → `OpenClaw automation` | 前台轻量化、后台分身、scratch |
| 大工程开工入口 | `TOOLS.md` → `OpenClaw automation` | `openclaw-heavy-task-start.py` |
| 大工程预检 | `TOOLS.md` → `OpenClaw automation` | `openclaw-heavy-task-preflight.py` |
| scratch 过期清理 | `TOOLS.md` → `OpenClaw automation` | `/mnt/data/openclaw/scratch/` |
| 批量改名前冲突预扫 | `TOOLS.md` → `OpenClaw automation` | `openclaw-rename-conflict-check.py` |
| Unity / Wall / Props 相关查找 | `WORKSPACE_INDEX.md` + `memory/INDEX.md` | 项目与日期锚点 |

## 3. 监工 / Watcher / 前台恢复

| 主题 | 去哪找 | 用途 / 关键词 |
|---|---|---|
| Watcher 体系 | `TOOLS.md` → `Watcher 体系（2026-05-26 整合后：8→5）` | frontstage / scheduler / health / lifecycle |
| 监工相关 | `TOOLS.md` → `监工相关` | `main-supervisor-lite`、监工脚本、前台绑定 |
| 本地健康诊断 | `TOOLS.md` → `OpenClaw automation` / `本地健康诊断层` | `openclaw-local-health-diagnose.py` |
| 前台 broker / infos-handle | `TOOLS.md` → `OpenClaw automation` | broker、sidecar、unified proxy |

## 4. 语音 / TTS / ChatTTS / XTTS

| 主题 | 去哪找 | 用途 / 关键词 |
|---|---|---|
| Voice replies / TTS | `TOOLS.md` → `Voice replies / TTS` | 主会话语音回复主线 |
| ChatTTS hybrid 中文语音 | `TOOLS.md` → `ChatTTS hybrid 中文语音(2026-05-09 起已有正式 stable 入口)` | 当前 stable 入口 |
| Kokoro TTS | `TOOLS.md` → `Kokoro TTS 离线中文语音(2026-05-08 已验证通过)` | 离线路线 |
| 本地 voice cloning | `TOOLS.md` → `Local free voice-cloning stack` | XTTS / uv / cache 路径 |
| 音频裁剪 / 参考音频准备 | `TOOLS.md` → `Local audio trimming / reference-voice prep` | 本地前处理 |

## 5. 视频下载 / 浏览器 / CLI 入口

| 主题 | 去哪找 | 用途 / 关键词 |
|---|---|---|
| 视频平台下载工作流 | `TOOLS.md` + `docs/通用-视频平台下载工作流.md` | 抖音/公开页下载 |
| CLI-Anything | `TOOLS.md` → `CLI-Anything` | GUI harness |
| Git / GitHub | `TOOLS.md` → `Git / GitHub` | pull / push / 同步 |

## 6. 本地凭据指针（无明文）

| 名称 | 去哪找 | 用途 | 边界 |
|---|---|---|---|
| OpenCode Zen 备用 API key | `TOOLS.md` → `Local-only credential pointers` | 紧急备用模型网关 | 不默认接入，不用于长期主会话 |
| SeetaCloud ChatTTS GPU | `TOOLS.md` → `Local-only credential pointers` | 远端 GPU 实验线路 | 凭据只保存在 `credentials/` |

## 7. 常见问题怎么找

- “OpenCode 备用 key 放哪了” → 本文件第 6 节 → `TOOLS.md` → `Local-only credential pointers`
- “监工脚本叫什么” → 本文件第 3 节 → `TOOLS.md` → `监工相关`
- “Unity 大工程 scratch 在哪” → 本文件第 2 节 → `TOOLS.md` → `OpenClaw automation`
- “语音默认主线在哪” → 本文件第 4 节 → `TOOLS.md` → `Voice replies / TTS`
