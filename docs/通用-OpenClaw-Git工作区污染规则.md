# OpenClaw Git 工作区污染规则

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：Git 提交与自动生成文件分类规则
- 最后更新：2026-06-01

## 用途

避免系统修改提交时混入无关运行态文件、临时文件、自动转录或学习记录。

以后做系统类提交前，先按本规则判断 `git status --short` 里的文件归属。

## 三类文件

### A. 应随系统修改提交

这些文件改变了系统行为、恢复能力或维护说明，应该随对应任务提交：

- `scripts/*.py` / `scripts/*.sh`
- `tools/**` 下的 systemd 模板、README、正式脚本
- `docs/通用-OpenClaw-*`
- `docs/公司-Linux-*` / `docs/掌机-Windows-*`
- `TOOLS.md` / `AGENTS.md` / `HOST_CONTEXT.md` / `SKILL_CATALOG.md`
- 正式补丁注册表、重建清单、升级后自检清单、变更流水

### B. 可提交，但应低频整理

这些文件是记忆/学习内容，不能混在系统补丁提交里；应在单独的记忆整理提交中处理：

- `memory/daily/YYYY-MM-DD.md`
- `memory/people.md`
- `memory/stories.md`
- `.learnings/ERRORS.md`
- `.learnings/LEARNINGS.md`
- `.learnings/FEATURE_REQUESTS.md`
- `.learnings/INBOX.md`

### C. 默认不提交

这些是自动运行态、中间产物或临时兜底文件，默认不进 Git：

- `memory/.YYYY-MM-DD-*.fallback.tmp`
- `tmp/**`
- `.openclaw/**`
- `*.log`
- `__pycache__/**`
- 大模型、压缩包、缓存、临时下载产物

### D. transcript 文件

`memory/daily/*-transcript.md` 是自动聚合转录，体积和变化频率都较高。

当前策略：

- 已经在 Git 中跟踪的历史 transcript，不在系统补丁提交里顺手改。
- 新生成的 transcript，默认不混入系统修改提交。
- 如果用户明确要求备份某天完整 transcript，再单独提交。

## 提交前推荐流程

```bash
git status --short
# 只 add 本次系统任务明确涉及的文件
git add <明确文件1> <明确文件2>
git diff --cached --stat
git commit -m '<本次系统修改标题>'
git push origin master
```

不要使用：

```bash
git add .
```

除非已经确认工作区只有本次相关文件。

## 当前建议的 .gitignore 方向

保留 Git 对正式 daily 摘要的跟踪能力，但忽略临时 fallback：

```gitignore
memory/.????-??-??-*.fallback.tmp
memory/daily/*-transcript.md
```

注意：如果某些 transcript 已经被 Git 跟踪，`.gitignore` 不会自动停止跟踪；后续如要完全调整 transcript 策略，应单独做一次清理任务，不混进普通补丁提交。
