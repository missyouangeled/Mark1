# 2026-06-01 OpenClaw 架构优化待办

- 创建时间：2026-05-29 16:25 CST
- 来源：周五架构巡检后，点点说“先保存，周一来做”
- 目标：不继续盲目加功能，优先把整套补丁/验证/文档/Skill 管理体系收紧成可长期维护的总控系统。

## 周一优先级

### P0-1：全局健康验收脚本

把当前 `scripts/verify-today-patches.py` 正式升级/迁移为：

```text
scripts/openclaw-verify-system.py
```

目标：从“今天补丁验证”升级为“整套 OpenClaw 系统健康验收”。

建议分组：

- `[core]` gateway / model / memory
- `[patches]` branding / broker / sidecar / proxy
- `[watchers]` 5 timers + timer service 最近一次 Result/ExecMainStatus
- `[performance]` search shortcut / ttl cache / latency baseline
- `[docs]` 总控面板 / 注册表 / 重建清单一致性
- `[skills]` 自定义 skill 存在性与关键入口

当前已完成基础：

- `verify-today-patches.py` 已补第 12 项 `timer-service-last-result`
- 当前验证：12/12 passed

### P0-2：补丁文档一致性审计脚本

新增：

```text
scripts/openclaw-patch-doc-audit.py
```

检查项：

- 总控面板里的 Pxx 是否都能在注册表找到
- 注册表里的 `PATCH-*` 是否都出现在总控面板
- “待处理”里不能出现已经正式注册的补丁
- 如果脚本仍被其他脚本引用，不能标记为“可归档”
- 重建清单里不能还要求启用已经废弃的旧 timer

周五已发现的真实漂移：

- `boot-health-check` 已晋升正式补丁，但总控面板一度还放在 C03 待处理
- `openclaw-stuck-session-detector.py` 仍被 `health-collector` 调用，不能归档
- `openclaw-responsiveness-watch.py` / `openclaw-frontstage-recovery-watch.py` 仍被 `frontstage-guardian` 调用，不能归档脚本本体，只能归档旧独立 timer/unit

### P1-1：修正旧 watcher 注册表/重建清单状态

当前事实：

- `frontstage-guardian.py` 调用：
  - `openclaw-frontstage-recovery-watch.py`
  - `openclaw-responsiveness-watch.py`
- `health-collector.py` 调用：
  - `openclaw-stuck-session-detector.py`

需要把文档状态统一成三类：

| 状态 | 含义 |
|------|------|
| `active-service` | 独立 systemd service/timer 仍在运行 |
| `active-module` | 不独立运行，但被 watcher 调用 |
| `retired` | 真正可归档/删除 |

重点修：

- `PATCH-FRONTSTAGE-RECOVERY-WATCH`：从独立 timer 改成 `active-module via frontstage-guardian`
- `PATCH-RESPONSIVENESS-WATCHDOG`：从独立 timer 改成 `active-module via frontstage-guardian`
- 重建清单里旧 `openclaw-frontstage-recovery-watch.timer` 不应再要求恢复

### P1-2：Skill 总控清单

新增：

```text
docs/通用-OpenClaw-Skill总控清单.md
```

覆盖 8 个自定义 Skill：

- `chattts-stable`
- `noizai-tts`
- `warm-companion-zh`
- `ex-qianqian`
- `humanizer-zh`
- `characteristic-voice`
- `douyin`
- `multi-search-engine`

每个 Skill 记录：

- 路径
- 用途
- 外部依赖/API key
- 是否 Git 管理
- 最小验收方式
- 升级/迁移风险

### P2：归档实验脚本

目标：清理 `scripts/` 目录，但不删除排查价值。

候选：

- `chattts_seeta_smoke*.py`
- `chattts_debug*.py`
- `chattts_verify*.py`

建议移动到：

```text
archive/experiments/chattts-seeta/
```

或：

```text
tools/chattts-stable/experiments/
```

先查引用，再移动，移动后跑最小验证。

## 周一开始前先跑

```bash
cd /home/missyouangeled/.openclaw/workspace
python3 scripts/verify-today-patches.py --print
systemctl --user list-timers 'openclaw-*' --no-pager
systemctl --user show openclaw-lifecycle-maintainer.service -p Result -p ExecMainStatus -p ActiveState -p SubState
```

## 周五已完成的修复

- 修复 `openclaw-lifecycle-maintainer.py`：`run_sub_check()` 支持 `timeout` 参数
- `verify-today-patches.py` 增加 `timer-service-last-result`
- 总控面板纠偏：旧 watcher 脚本仍是 active dependency，不能归档脚本本体
- 验证：12/12 passed
- 已推送 commit：
  - `f7b105d`：修复 lifecycle-maintainer 失败并补 timer 服务结果验证
  - `dae2d5e`：旧 watcher 脚本为 guardian 依赖不可归档
