---
name: emergency-repair-pack
description: 保命修复插件包：只包含白名单、可回滚、不触碰主会话内容的自动修复动作。
disable-model-invocation: true
---

# Emergency Repair Pack

这是保命体系的第二层：可插拔修复包。

原则：

- 不能替代核心保命层。
- 删除本 skill 后，核心巡检、告警、留痕仍必须可正常工作。
- 这里只允许非常窄的白名单修复动作：
  - 幂等
  - 可回滚
  - 不修改当前主会话内容
  - 不修改 cron / systemd / gateway 配置
  - 失败后最多退回告警，不能扩大故障

当前包含的修复器：

- `scripts/repair_stale_watcher_alerts.py`
  - 仅处理 watcher 的历史未清告警归档
  - 不触碰活跃 trajectory 告警
  - 不修改主 session

- `scripts/repair_archive_resolved_watcher_alerts.py`
  - 仅归档聚合器已经判定为 `resolvedItems` 的 watcher 历史告警
  - 只清理 `alerts.json` 中已被当前状态证伪的旧提醒
  - 会把原始告警追加写入 `emergency-aggregator/watcher-resolved-archive.jsonl`
  - 不触碰活跃 trajectory 告警
  - 不修改主 session

- `scripts/repair_backup_kick_once.py`
  - 仅在 backup 超时、且 frontstage/health/cron 全部正常时补跑一次快照备份
  - 调用现有 `scripts/openclaw-session-backup.py --quiet`
  - 不修改 systemd 配置，不重启服务
  - 失败后退回告警，不扩大故障

- `scripts/repair_health_collect_once.py`
  - 仅在 health 状态过旧、且 cron/frontstage 正常时补跑一次健康采集
  - 调用现有 `scripts/openclaw-health-collector.py --print-human`
  - 不修改 systemd 配置，不重启服务
  - 失败后退回告警，不扩大故障

- `scripts/repair_frontstage_guardian_collect_once.py`
  - 仅在 frontstage 状态过旧、且 cron/health 正常时补跑一次前台保护检查
  - 调用现有 `scripts/openclaw-frontstage-guardian.py --print-human --no-notify`
  - 不修改 systemd 配置，不重启服务
  - 使用 `--no-notify`，避免修复动作本身产生额外前台打扰

- `scripts/repair_audit_snapshot.py`
  - 只读地把当前保命聚合快照追加写入 `repair-audit.jsonl`
  - 不执行修复、不触碰系统状态
  - 作用是为后续回放、复盘、阈值调参留一条轻量审计轨迹

本 skill 当前不要求模型直接调用；由核心保命层的 repair runner 以脚本白名单方式调度。
