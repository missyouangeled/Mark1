# Watcher 体系

> 8→5 Watcher 体系


- 🛡️ **前台保护器**：`scripts/openclaw-frontstage-guardian.py`
  - 合并了 frontstage-recovery-watch + responsiveness-watch
  - 每 20s：检测 transcript/history 投影异常 + 主会话响应性
  - 状态目录：`~/.local/state/openclaw/frontstage-guardian/`
  - service/timer 模板：`tools/openclaw-watchers/openclaw-frontstage-guardian.*`
  - 已安装：`~/.config/systemd/user/openclaw-frontstage-guardian.*`
- ⚙️ **任务调度器**：`scripts/openclaw-task-scheduler.py`
  - 每 30s：扫描 runs.sqlite → 自动开关监工、检测静默/僵尸任务、回报前台
  - 状态目录：`~/.local/state/openclaw/task-scheduler/`
  - service/timer 模板：`tools/openclaw-watchers/openclaw-task-scheduler.*`
  - 已安装：`~/.config/systemd/user/openclaw-task-scheduler.*`
- 🏥 **健康采集器**：`scripts/openclaw-health-collector.py`
  - 合并了 supervisor-watch + broker-rebuild + local-health-watch
  - 每 60s 轻量层（supervisor 刷新 + broker 重建）；每 5 次/5min 完整层（追加 local-health 诊断）
  - 状态目录：`~/.local/state/openclaw/health-collector/`
  - service/timer 模板：`tools/openclaw-watchers/openclaw-health-collector.*`
  - 已安装：`~/.config/systemd/user/openclaw-health-collector.*`
- 🧹 **生命周期维护器**：`scripts/openclaw-lifecycle-maintainer.py`
  - 合并了 daily-transcript-aggregator + cleanup-temp
  - 每 5min：每次都聚合转录，每 6 次/30min 做一次文件清理
  - 状态目录：`~/.local/state/openclaw/lifecycle-maintainer/`
  - service/timer 模板：`tools/openclaw-watchers/openclaw-lifecycle-maintainer.*`
  - 已安装：`~/.config/systemd/user/openclaw-lifecycle-maintainer.*`
- 🔄 **Resume 恢复**：`scripts/openclaw-resume-watch.sh`（保持独立）
  - 每 60s：检测休眠恢复 / boot_id 跳变 → 自动重启 Gateway
  - 已安装：`~/.config/systemd/user/openclaw-resume-watch.*`

> 保留脚本（原入口未删，可回退）：`openclaw-frontstage-recovery-watch.py` / `openclaw-responsiveness-watch.py` / `openclaw-supervisor-status.py` / `openclaw-frontstage-broker.py` / `openclaw-local-health-diagnose.py` / `aggregate-daily-transcript.py` / `openclaw-cleanup-temp.sh`

### 监工相关