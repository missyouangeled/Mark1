## 2026-05-26：任务调度器（Task Scheduler）详细设计

### 目标

消除当前后台任务管理中的 4 个手动决策点，把监工开关、任务跟踪、异常回报、清理回收全部自动化：

```
改造前（手动）：
  你发任务 → 我判断"要不要开监工" → 手动切 force_on
  → 手动 spawn 后台 → 等结果
  → 监工 3min 回报 → 任务完成 → 我手动关监工 + 清理分身

改造后（自动）：
  你发任务 → 我 spawn 后台 → 调度器自动接管
  → 自动开启监工 → 自动跟踪进度 → 自动 3min 回报
  → 任务完成 → 自动关监工 + 自动清理
```

### 架构定位

调度器是 watcher 体系的第 5 个成员，补充现有 4 个 watcher 的能力盲区：

| Watcher | 职责 | 调度器补充什么 |
|---------|------|---------------|
| 🛡️ 前台保护器 | 检测前台回复是否正常显示 | 不重叠，独立运行 |
| 🏥 健康采集器 | supervisor 刷新 + broker 重建 + 健康诊断 | 调度器接管"任务完成后自动关监工" |
| 🔄 resume 恢复 | 休眠恢复检测 | 不重叠 |
| 🧹 生命周期维护器 | 转录聚合 + 临时文件清理 | 调度器接管"旧会话/僵尸任务清理" |
| ⚙️ **调度器（新增）** | **任务生命周期自动化** | — |

### 数据流

```
runs.sqlite ──→ 调度器 ──→ supervisor-status.py --set-policy-mode（开关监工）
                 │
                 ├──→ broker emit（前台回报）
                 │
                 ├──→ supervisor-subagent.py kill（清理僵尸分身）
                 │
                 └──→ 自身状态文件（供 health-collector 读入 broker 视图）
```

### 任务模型

调度器从 `runs.sqlite` 的 `task_runs` 表读取，关注以下字段：

| 字段 | 用途 |
|------|------|
| task_id | 唯一标识 |
| label | 任务标签（用于区分"需要监工的"vs"系统 cron"） |
| status | running / succeeded / failed / cancelled / timed_out / lost |
| owner_key | 归属会话（过滤非当前用户的任务） |
| child_session_key | 后台分身 session key |
| created_at / started_at | 时间线 |
| last_event_at | 最后活动时间（静默检测） |
| error / terminal_summary | 失败原因 |

**任务过滤规则**：
- 只管理 `owner_key` 属于当前用户（`agent:main:*`）的任务
- 排除系统 cron（通过 label 前缀过滤，如 `system:cron:*`）
- 排除已有 label 标记为"不需要调度的"任务

### 调度器核心逻辑

```python
每 30s 运行一次：

1. 扫描 runs.sqlite → 找出所有 active 任务
   - active = status IN ('running') AND owner_key LIKE 'agent:main:%'
   - 排除 label 前缀为 'system:cron:' 的系统定时任务
   - 排除 label 包含 '[noschedule]' 标记的任务

2. 状态判定：
   ┌─ 有 active 任务 + 监工未开启 → 自动开启监工 (auto + taskActive=true)
   ├─ 有 active 任务 + 监工已开启 → 检查是否需要前台回报（3min 无产出）
   ├─ 无 active 任务 + 监工开启 + 超过冷却窗口(10min) → 自动关闭监工
   └─ 无 active 任务 + 监工关闭 → 空闲，检查是否需要清理

3. 清理判定：
   ├─ terminal 任务（succeeded/failed/cancelled）超过清理阈值 → 标记可清理
   ├─ 僵尸 running 任务（无 activity > 超时阈值）→ 自动 kill
   └─ 陈旧 subagent session → 通过 sessions_list 查询并清理

4. 写状态文件 → 供 health-collector 读取并汇入 broker 视图
5. 如有状态变化 → 通过 broker emit 回报前台
```

### 关键配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 调度频率 | 30s | systemd timer OnUnitActiveSec |
| 静默阈值 | 180s (3min) | 超此时间无产出 → 触发前台回报 |
| 监工关闭冷却 | 600s (10min) | 最后任务完成后等待这么长再关监工 |
| 僵尸任务超时 | 1800s (30min) | 无 activity 超过此时间 → 自动 kill |
| 终端任务保留 | 3600s (1h) | succeeded/failed 任务保留多久后才清理 |

### 与现有系统的关系

**不改动的**：
- `openclaw-supervisor-status.py`：继续做状态快照，调度器通过它管理监工开关
- `openclaw-supervisor-subagent.py`：调度器调用它做 kill 操作
- `openclaw-frontstage-broker.py`：调度器通过它 emit 事件
- 前台保护器、resume 恢复、生命周期维护器：完全不受影响

**调度器可能逐步接管生命周期维护器的部分职责**：
- 旧会话清理（当前手动做）→ 调度器自动化
- 僵尸 subagent 清理（当前手动做）→ 调度器自动化

**但短期不改**：
- 临时文件清理 → 仍由 lifecycle-maintainer 负责
- 转录聚合 → 仍由 lifecycle-maintainer 负责

### 实施步骤

#### 阶段 1：最小可行调度器（本次实施）
- [x] 创建 `scripts/openclaw-task-scheduler.py`
- [x] 创建 systemd service + timer（每 30s）
- [x] 实现核心逻辑：
  - 扫描 active 任务 → 自动开/关监工
  - 3min 静默检测 → broker 回报前台
  - 僵尸任务检测 → 自动 kill
- [x] 验证：手动 spawn 一个后台任务 → 调度器自动开启监工 → 任务完成 → 冷却后自动关闭

#### 阶段 2：清理自动化
- [x] 终端任务超时自动清理 — 每 10 周期（5min）调用 `openclaw tasks maintenance --apply`
- [x] 任务审计 — 每 10 周期调用 `openclaw tasks audit --severity error`，严重问题回报前台
- [x] 旧 subagent session 自动清理 — 每 10 周期扫描 done/failed/killed 会话并清理
- [x] 与 lifecycle-maintainer 协调职责边界 — scheduler 负责 OpenClaw 级任务/会话清理，lifecycle-maintainer 负责文件级清理

#### 阶段 3：智能调度
- [x] 任务并发控制 — 超过 4 个 active 任务告警记录
- [x] 近期失败任务检测 — 10min 窗口扫描 failed 任务，去重通知前台
- [x] 失败自动重试预备 — 扫描失败任务含原始 task 文本，为未来重试做准备

### 状态
🟢 全部三个阶段已完成（2026-05-26）。

**阶段 1 已完成交付物：**
- `scripts/openclaw-task-scheduler.py`
- `tools/openclaw-watchers/openclaw-task-scheduler.service`
- `tools/openclaw-watchers/openclaw-task-scheduler.timer`
- 已安装 systemd timer，每 30s 运行
- 验证通过：端到端 auto-enable supervisor 成功

**阶段 2+3 新增能力：**
- `openclaw tasks maintenance --apply`：每 5min 自动 gateway 维护
- `openclaw tasks audit --severity error`：每 5min 审计，发现问题通知前台
- 旧 subagent/dashboard 会话自动清理
- 并发控制（>4 active 告警）+ 失败检测（10min 窗口去重通知）

---
