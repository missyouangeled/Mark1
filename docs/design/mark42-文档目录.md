# Mark42 文档目录

> ⚠️ 换模型/重建上下文后，先读这个文件，搞清楚每份文档是干什么的。

## 📂 路径速查（换模型时必看）

| 什么东西 | 路径 |
|:---|:---|
| **代码入口** | `scripts/mark42.py`（CLI）/ `scripts/mark42_modules/`（模块） |
| **配置文件** | `~/.local/state/openclaw/mark42/config.json` |
| **运行日志** | `/mnt/data/openclaw/mark42/logs/`（数据盘） |
| **引擎心跳** | `~/.local/state/openclaw/mark42/engine/daemon-heartbeat.json` |
| **Loop 状态** | `~/.local/state/openclaw/mark42/engine/loops.json` |
| **铠甲记忆索引** | `~/.local/state/openclaw/mark42/armor/memory-index.json` |
| **铠甲出手记录** | `~/.local/state/openclaw/mark42/armor/actions.jsonl` |
| **3天守护日志** | `docs/design/mark42-3天守护日志.md` |
| **broker 事件** | `~/.local/state/openclaw/mark42/broker/mark42-events.jsonl` |

## 文档速查

| 文档 | 用途 | 什么时候看 |
|:---|:---|:---|
| `mark42-context-loop-heavy.md` | 🏗️ 架构设计 | 理解三模块怎么拆怎么拼 |
| `mark42-商品化路线图.md` | 🗺️ 路线图 | 知道当前在哪一阶段、下一步是什么 |
| `mark42-全线审查报告-20260617.md` | 🔍 审查报告 | 了解上次审查发现了什么 |
| `mark42-更新日志.md` | 📋 变更记录 | 查某个改动是什么时候做的 |
| **`mark42-开发经验.md`** | 🧠 经验教训 | **下次写代码前先看这个** |
| `mark42-compaction-analysis-20260616.md` | 📊 压缩分析 | context compaction 的技术分析 |

## 不是 Mark42 项目文档，别混进来

| 文档 | 实际是干什么的 |
|:---|:---|
| `.learnings/LEARNINGS.md` | 全局日常开发经验（和学习系统相关，与 Mark42 无关） |
| `.learnings/ERRORS.md` | 全局错误记录 |
| `memory/` | 个人记忆/聊天记录 |
| `SOUL.md` / `MEMORY.md` / `USER.md` | 人格/偏好/用户信息 |
