# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics - the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## 快速导航

| 要找什么 | 看哪 |
|---|---|
| 工作区总导航 | `WORKSPACE_INDEX.md` |
| 工具二级索引 | `TOOLS_INDEX.md` |
| 本地凭据指针 | `Local-only credential pointers` |
| API 密钥归属清单 | `docs/贾维斯中枢-API密钥清单.md`（个人/公司/免费归属与统一换密钥指南） |
| OpenClaw 自动化 / 监工 / watcher | `OpenClaw automation` |
| 升级后自检 / 升级记录 | `OpenClaw automation` |
| 大工程 / scratch / 批量改名 | `OpenClaw automation` |
| 视频下载相关入口 | `视频平台下载默认工作流` / 相关下载脚本条目 |
| OCR 文字识别 | `scripts/jarvis-ocr.py` / `tools/jarvis-ocr.sh` / Mark2 小模型清单 |
| 本地语音 / ChatTTS / XTTS | `ChatTTS` / `Local free voice-cloning stack` |
| SSH / 远端 GPU / API key 路径 | `Local-only credential pointers` |

## 权限规则

- 适用机器:公司(Linux)
- 本机默认拥有最高权限,无需逐次确认;涉及连接到其他设备操作时,再询问权限。

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.


## 详细文档索引

> 以下是原本内联的详细运维文档，已拆分为独立文件以节省上下文。

| 主题 | 文件 |
|------|------|
| OpenClaw automation | [openclaw-automation.md](docs/tools/openclaw-automation.md) |
| Watcher 体系 | [watchers.md](docs/tools/watchers.md) |
| 监工相关 | [supervisor.md](docs/tools/supervisor.md) |
| Voice replies / TTS | [voice-tts.md](docs/tools/voice-tts.md) |
| Local-only credential pointers | [credentials.md](docs/tools/credentials.md) |
