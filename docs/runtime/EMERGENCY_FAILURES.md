# EMERGENCY_FAILURES

> 仅记录 `CRITICAL` / `DEADMAN` 级别保命失败。
> 由 `scripts/emergency0-aggregator.py` 自动追加；正常情况下允许文件不存在。

## 处理原则

- 先看最新一条记录，再对照 `docs/runtime/保命状态快照.md`。
- 先确认是不是外部状态恢复后留下的历史条目，再决定是否人工介入。
- 不要直接改主 session 文件；当前保命体系默认只读报警。

## 常见 code 含义

- `BACKUP_STALE`：session-backup 最近快照超过 25 分钟未更新，或无法读取。
- `CRON_UNREADABLE` / `CRON_STALE` / `CRON_NOT_OK`：救命 1 cron 读取失败、过久未跑、或最近运行异常。
- `TRAJECTORY_TOO_LARGE`：当前主 trajectory 已明显高于安全阈值。
- `SESSION_LINES_HIGH`：主 session 行数逼近或超过保命上限。
- `SYSTEMD_INACTIVE`：关键 openclaw / mark42 单元出现真正 `failed`。
- `HEALTH_*`：health collector 子检查发现结构化异常；若带 `blockedMain`，优先按主会话阻塞看待。

## 排查顺序

1. 读 `docs/runtime/保命状态快照.md`
2. 查 `~/.local/state/openclaw/emergency-aggregator/status.json`
3. 查 `~/.local/state/openclaw/emergency-aggregator/events.jsonl`
4. 再看具体 watcher / health / frontstage / backup 状态目录

## 2026-07-06T14:58:27.601178+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-06T14:58:29.597391+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-06T15:00:00.077085+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-06T15:27:24.408002+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=None）

## 2026-07-07T07:06:29.766479+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=811.49592465）

## 2026-07-07T08:15:00.103215+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T09:05:49.466624+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T09:15:00.129940+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T09:30:00.309292+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T09:40:00.165332+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T10:30:00.114249+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-07T10:45:00.148979+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T11:00:00.101390+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T11:15:00.115241+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T11:25:00.101051+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T11:45:00.119554+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-07T11:50:00.097388+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-07T11:55:00.081442+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-07T12:35:00.107887+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-07T12:48:26.063202+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-07T12:55:00.126380+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-07T13:00:00.091323+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-07T13:15:00.090579+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.06MB，已明显超过 5.0MB watcher 阈值

## 2026-07-07T13:20:00.087067+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.33MB，已明显超过 5.0MB watcher 阈值

## 2026-07-07T13:25:00.116929+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.87MB，已明显超过 5.0MB watcher 阈值

## 2026-07-07T13:30:00.090613+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.69MB，已明显超过 5.0MB watcher 阈值

## 2026-07-07T13:35:00.099167+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.51MB，已明显超过 5.0MB watcher 阈值

## 2026-07-07T15:54:14.402985+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.51MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=136.85671641666667）
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=139.23984975）

## 2026-07-07T15:55:00.081466+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=137.61802443333332）

## 2026-07-07T16:00:00.080098+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=142.61800163333334）

## 2026-07-07T16:10:00.095698+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T16:25:00.102727+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T16:35:00.088802+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T16:55:00.098233+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-07T17:00:00.079503+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-08T08:26:22.448069+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=916.37395115）

## 2026-07-08T09:05:00.095948+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-08T09:45:00.084644+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-08T10:15:00.113290+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.10MB，已明显超过 5.0MB watcher 阈值

## 2026-07-08T10:20:00.080280+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.96MB，已明显超过 5.0MB watcher 阈值

## 2026-07-08T10:25:00.084020+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.96MB，已明显超过 5.0MB watcher 阈值

## 2026-07-08T10:30:00.087663+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.95MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T07:55:22.500732+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.95MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=1285.3749122000002）

## 2026-07-09T08:30:00.084631+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-09T08:35:00.087329+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-09T08:40:00.098865+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-09T08:45:01.574920+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-09T09:00:02.944015+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=15.024083583333333）

## 2026-07-09T10:00:04.497464+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.93MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.0270744）

