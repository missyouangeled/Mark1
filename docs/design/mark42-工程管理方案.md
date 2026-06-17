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

```
docs/design/
├── mark42-文档目录.md         ← 📂 入口索引
├── mark42-工程管理方案.md      ← 📐 本文件
├── mark42-架构设计.md         ← 三模块设计
├── mark42-商品化路线图.md      ← 四阶段 + 缺口
├── mark42-更新日志.md         ← 每个版本改了什么
├── mark42-开发经验.md         ← 踩过的坑 + 自检清单
├── mark42-运维日志.md         ← 守护运行记录
├── mark42-compaction-analysis-20260616.md
└── 审查报告/                  ← 每次全线审查存档
    └── mark42-全线审查报告-20260617.md
```

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

*此文件随工程管理流程迭代同步更新。*
