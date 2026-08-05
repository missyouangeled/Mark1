# Mark42 工程管理方案

> 版本：v1.0（2026-06-17）
> 定位：不影响日常开发的轻量管理规则。不是为了流程而流程，是为了工程大了不乱。

---

## 一、版本号规范（Semantic Versioning）

```
v<主版本>.<次版本>.<修订号>
  MAJOR . MINOR . PATCH

MAJOR = 架构级改动、模块重写、不向后兼容
MINOR = 新功能、新模块、显著改进
PATCH = bug 修复、健壮性改进、文档更新
```

示例：

| 改动 | 版本变更 |
|:---|:---|
| 修复 task-watch 变量未初始化 | v2.3.0 → v2.3.1 |
| 新增 Heavy CLI 命令行入口 | v2.3.0 → v2.4.0 |
| 三模块拆分成独立包 | v2.x.x → v3.0.0 |

**版本号写在哪里**：
1. `config.py` 的 `mark42_init()` 函数（`"version": "2.3.0"`）
2. `config.json` 状态文件（运行时写入，--init 时更新）

---

## 二、文档体系

> 以 [mark42-文档目录.md](./mark42-文档目录.md) 为准。本节仅列出工程管理层必读。

```
docs/design/
├── mark42-文档目录.md         ← 📂 入口索引（必看）
├── mark42-工程管理方案.md      ← 📐 本文件（必看）
├── mark42-架构设计.md         ← 🏗 三模块设计（参照看）
├── mark42-商品化路线图.md      ← 🗺️ 阶段 + 缺口（路线判断）
├── mark42-更新日志.md         ← 📋 每个版本改了什么（追溯）
├── mark42-文档审计报告-20260629.md  ← 🔍 文档质量审计（2026-06-29）
├── mark42-开发经验.md         ← 🧠 踩过的坑 + 自检清单（下一次写代码前必看）
├── mark42-运维日志.md         ← 📊 守护运行记录（看运行状态）
├── mark42-测试手册.md         ← 🧪 写测试前必看（8 陷阱 + helper）
├── mark42-测试体系*.md        ← 🧪 测试体系设计与状态（其中 Phase1 收官已归档）
├── mark42-Phase2*.md          ← 🧪 Phase 2 路线与执行（2 个文件，历史阶段）
├── mark42-压缩方案借鉴Headroom-20260624.md  ← 🧩 设计灵感来源（已落地标注）
├── mark42-压缩方案-性能基准-20260626.md   ← 📊 历史性能快照
├── mark42-开发手册-压缩子系统.md  ← 📖 压缩子系统实战手册
├── mark42-compaction-analysis-20260616.md
├── _archive/                  ← 已归档文档（仅追溯用, 不引用）
│   ├── mark42-Phase2路线-20260625.md
│   ├── mark42-阶段1收官README-20260625.md
│   ├── mark42-压缩方案-阶段1实施计划-20260624.md
│   └── mark42-测试体系-Phase1收官-20260629.md
└── 审查报告/                  ← 每次全线审查存档
```

> **方针**：文档以代码为准。代码变了，文档要跟上。

---

## 三、开发流程（四步）

```
🎯 计划  →  🔧 开发  →  🧪 验证  →  📋 收尾
```

### 3.1 计划（5-10 分钟）
- 明确要改什么、为什么改
- 读 `mark42-开发经验.md` 自检清单
- 评估影响范围（改哪个模块、会碰到谁）
- 如果是大改动，在 docs/design 里新建简要说明文档

### 3.2 开发
- **修改前先 grep 全量搜索**（自检清单第 3 条）
- 每个模块改完即时跑语法检查：`python3 -m compileall scripts/mark42_modules/`
- 不要攒一堆改动再一次验证——改一个模块测一个

### 3.3 验证
- 跑完整烟测：`python3 scripts/mark42-tests.py`
- 确认 assemble 启动 → 守护运行 → 优雅关闭
- 确认 stderr 无新增错误

### 3.4 收尾（必做）
1. 更新 `mark42-更新日志.md`（版本号 + 改动清单 + 验证结果）
2. 涉及文档变更 → 同步更新 `mark42-文档目录.md`
3. 踩到新坑 → 追加 `mark42-开发经验.md`
4. git commit（Conventional Commits 格式）
5. git push

---

## 四、Git Commit 规范（Conventional Commits）

```
<type>: <简短描述>

类型：
feat     = 新功能
fix      = bug 修复
docs     = 文档
refactor = 重构（不改功能）
perf     = 性能优化
test     = 测试相关
chore    = 杂务（日志、路径、配置管理）

示例：
feat: armor-guard 新增上下文 70% 预警自动通知前台
fix: task-watch 在无活跃任务时 UnboundLocalError
docs: 文档目录新增路径速查表
chore: 日志迁移到数据盘 + 自动截尾
```

---

## 五、分支策略

```
master  ─── 永远可部署、永远干净

日常开发直接在 master（单分支，不用 PR）。
重大高风险改动 → 临时分支 → 验证完合并回 master 删分支。
临时分支命名：<type>/<简短描述>，如 fix/session-read-nesting
```

---

## 六、质量门禁（每次收尾前过一遍）

| # | 检查项 |
|:---:|------|
| 1 | `python3 -m compileall scripts/mark42_modules/` 零报错 |
| 2 | `python3 scripts/mark42-tests.py` 全通过 |
| 3 | `mark42.py status --json` 正常输出 |
| 4 | stderr 无新增错误 |
| 5 | `mark42-更新日志.md` 已追加当前版本条目 |
| 6 | commit message 符合 Conventional Commits |
| 7 | 涉及路径/常量变更 → `mark42-文档目录.md` 已同步 |
| 8 | 守护重启后 1 分钟心跳正常 |

---

## 七、每周例行检查

- 运维日志是否正常更新（心跳文件）
- 日志大小是否在阈值内
- 是否有新的审查报告需要归档到 `审查报告/`
- `mark42-开发经验.md` 是否有新的教训

---

## 八、自动行为守则（2026-06-30 补充，点点提出）

> **点点原话**：“怕有什么意外或者自动压缩 你又不记得了”
> **原则**：“写下来 > 记着”，“自动 ＝ 默认不跳”。

### 8.1 默认 dry-run 是硬护栏

- 任何"自动执行"函数（脚本执行 / 进程控制 / 清理 / 重启）**默认不跳** + 需 `execute_now` flag
- `heavy_execute` 修了同款问题（ERR-20260630-006）后，后续所有同类函数都这么写
- 增量检查项（追加到上表六、）：
  9. “自动执行”函数默认 dry-run（调用者未传 `execute_now` 不会启动任何子进程）
  10. 启动后状态有 PID / logPath 记入 status.json
  11. broker 事件区分 queued vs started（供其他模块决策）

### 8.2 自动行为每次必留痕

| 触发 | 留痕位置 | 谁看 |
|---|---|---|
| `armor.compress` | `armor/actions.jsonl` + `armor/memory-index.json` | 人 / 审查 |
| `heavy.batch.started` | broker `mark42-events.jsonl` | 人 / engine daemon |
| `log_rotate` | `mark42/log-rotation.json` | 人 / watchdog |
| 任何 daemon 启停 | journalctl + bootstrap.log | 人 / watchdog |
| 修改 systemd service | commit message + bootstrap.log | 人 |

### 8.3 动作 / 副作用必告知

- 自动做事之前：打印 ⚠️ 告知下一步
- 做完：打印 + 写 broker event + 写 status.json（三重留痕）
- 跨日 / 重启后：读 log-rotation.json / bootstrap.log 了解上次动作

### 8.4 审查周期

- 每 1-2 周：文档 vs 代码 vs 真生产 三方对照审查
- 审查报告档： `docs/design/mark42-全面审查-YYYYMMDD.md`
- 审查后：商品化路线图更新 H/I/J 等诊断项，标记 ✅ / ⏳ 状态

---

*此文件随工程管理流程迭代同步更新。*
