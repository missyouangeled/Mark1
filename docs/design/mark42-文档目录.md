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
| **运维日志** | `docs/design/mark42-运维日志.md` |
| **工程管理方案** | `docs/design/mark42-工程管理方案.md` |
| **broker 事件** | `~/.local/state/openclaw/broker/mark42-events.jsonl` |

## 文档速查

| 文档 | 用途 | 什么时候看 |
|:---|:---|:---|
| `mark42-架构设计.md` | 🏗️ 架构设计 | 理解三模块怎么拆怎么拼 |
| `mark42-工程管理方案.md` | 📐 工程规范 | 版本号/分支/Git/质量门禁 |
| `mark42-商品化路线图.md` | 🗺️ 路线图 | 知道当前在哪一阶段、下一步是什么 |
| `mark42-更新日志.md` | 📋 变更记录 | 查某个改动是什么时候做的 |
| **`mark42-开发经验.md`** | 🧠 经验教训 | **下次写代码前先看这个** |
| `mark42-运维日志.md` | 📊 运行记录 | 守护跑了多久、有没有异常 |
| `mark42-compaction-analysis-20260616.md` | 📊 压缩分析 | context compaction 的技术分析 |
| `mark42-压缩方案借鉴Headroom-20260624.md` | 🧩 压缩方案 | 借鉴 Headroom 6 大算法到 Mark42 铠甲的 3 阶段路线 |
| `mark42-压缩方案-阶段1实施计划-20260624.md` | 📋 实施计划 | 4 个方向的具体修改方案 (代码+集成+配置+验证+回滚) |
| **`mark42-测试体系设计方案-20260629.md`** | 🧪 测试设计 | 完整设计方案 (conftest + 3 层目录 + 8 fixture + 4 周路线) |
| **`mark42-测试手册.md`** | 🧪 实战手册 | **写测试先看这个**（8 个常见陷阱 + helper 样板） |
| **`mark42-测试体系-Phase1收官-20260629.md`** | 🧪 阶段收官 | Phase 1 完成快照（111 测试 / 37.8% 覆盖 / 1 bug 修复） |
| **`mark42-Phase2路线-20260629.md`** | 🧪 Phase 2 路线 | 10 个模块 / 76 个新测试 / 37.8%→50%+ 覆盖目标 |
| **`mark42-Phase2执行手册-20260629.md`** | 🧪 Phase 2 战术 | **复制粘贴可干**（10 步 / 完整测试代码 / 故障排查） |
| `审查报告/` | 🔍 审查存档 | 历史审查报告 |

## 不是 Mark42 项目文档，别混进来

| 文档 | 实际是干什么的 |
|:---|:---|
| `.learnings/LEARNINGS.md` | 全局日常开发经验（和学习系统相关，与 Mark42 无关） |
| `.learnings/ERRORS.md` | 全局错误记录 |
| `memory/` | 会话记忆系统 |
| `SOUL.md` / `MEMORY.md` / `USER.md` | OpenClaw 人格/偏好/用户配置 |

---

*本文件在新增/删除/改名 Mark42 文档时需同步更新。*
