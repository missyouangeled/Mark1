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

## 2026-07-09T11:00:06.414644+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.035277400000005）

## 2026-07-09T12:03:08.033232+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=63.0283872）

## 2026-07-09T13:03:10.422147+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.04206911666667）

## 2026-07-09T14:03:12.438134+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.03505223333333）
- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-09T15:03:14.736366+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.039972766666665）

## 2026-07-09T16:03:16.072696+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.02447826666666）

## 2026-07-09T17:03:18.458872+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.041314533333335）

## 2026-07-09T17:05:00.082296+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:10:00.096584+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:15:00.104072+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:20:00.095320+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:25:00.086059+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:30:00.211910+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:35:00.079439+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:40:00.087866+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:45:00.091369+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-09T17:50:00.091816+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-10T09:24:00.066379+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=934.0009563166666）

## 2026-07-10T09:25:00.075579+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-10T09:30:00.085972+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.02MB，已明显超过 5.0MB watcher 阈值

## 2026-07-10T09:35:00.147059+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-10T09:40:00.102507+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-10T09:45:00.100284+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-10T09:50:04.593847+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-10T10:05:06.232425+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=15.02887375）

## 2026-07-10T11:05:12.548629+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.107060483333335）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service, openclaw-health-collector.service

## 2026-07-10T12:05:23.480075+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.18531791666667）

## 2026-07-10T13:05:28.924889+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.09501481666667）

## 2026-07-10T14:05:36.296163+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.124519383333336）

## 2026-07-10T15:05:41.229769+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.08346281666666）

## 2026-07-10T16:05:47.328305+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.10290508333333）

## 2026-07-10T17:05:52.309550+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.08437583333333）

## 2026-07-10T17:49:22.936706+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=43.511945100000005）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-10T17:50:24.790624+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=44.542843733333335）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-10T17:55:00.102067+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-10T18:00:00.133496+08:00

- [DEADMAN] CRON_UNREADABLE: 无法读取救命 1 cron 状态
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-10T18:05:00.142677+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-13T07:44:07.491106+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=3699.1247184333333）

## 2026-07-13T07:50:00.098854+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-13T08:10:00.087469+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-13T08:15:00.113471+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-13T08:30:00.078803+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-13T08:35:00.085609+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-13T08:40:00.090248+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-13T11:45:00.094997+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-13T13:20:00.090457+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-13T13:25:00.092727+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.70MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T13:30:00.310979+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.70MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T13:35:00.100722+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.70MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T13:40:00.090029+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.70MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T13:45:00.083251+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T13:50:00.096132+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T13:55:00.086593+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:00:00.092916+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:05:00.088032+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:10:00.087381+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:15:00.094123+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:20:00.085113+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:25:00.116648+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:30:00.114794+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:35:00.096431+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:40:00.091338+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:45:00.083188+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:50:00.089830+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T14:55:00.083502+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:00:00.105530+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:05:00.088974+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:10:00.085998+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:15:00.085127+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:20:00.086509+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:25:00.091205+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:30:00.108477+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:35:00.085787+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:40:00.088305+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:45:00.079899+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:50:00.093737+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T15:55:00.100268+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:00:00.108620+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:05:00.087371+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:10:00.092430+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:15:00.119829+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:20:00.093110+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:25:00.092609+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:30:00.098237+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:35:00.083228+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:40:00.101150+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:45:00.102419+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:50:00.115221+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T16:55:00.099803+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:00:00.107041+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:05:00.119949+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:10:00.089159+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:15:00.097232+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:20:00.091618+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:25:00.093411+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:30:00.114944+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-13T17:35:00.093796+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.59MB，已明显超过 5.0MB watcher 阈值

## 2026-07-14T07:22:25.569878+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.89MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=827.4259813000001）

## 2026-07-14T07:25:00.074375+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.89MB，已明显超过 5.0MB watcher 阈值

## 2026-07-14T08:20:00.078136+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-14T08:25:00.095980+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-14T08:35:00.085438+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-14T08:40:00.083318+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-14T09:10:00.085619+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-14T09:15:00.081756+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-14T13:50:00.081095+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-14T13:55:00.079296+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-14T14:00:00.086726+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-14T14:05:01.355304+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-14T14:20:02.742704+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=15.024495066666667）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-14T15:20:08.341002+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.095133366666666）

## 2026-07-14T16:20:14.813417+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.11092361666667）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-14T17:30:14.480546+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=69.9985591）

## 2026-07-15T08:31:53.069772+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=901.6453961999999）

## 2026-07-15T08:50:00.104088+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T08:55:00.101944+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T10:20:00.101865+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T10:25:00.101095+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T14:15:00.111273+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T14:20:00.095841+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T14:30:00.109977+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T14:35:00.099243+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.07MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T14:40:00.096807+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.07MB，已明显超过 5.0MB watcher 阈值

## 2026-07-15T14:45:00.111785+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.07MB，已明显超过 5.0MB watcher 阈值

## 2026-07-15T14:50:00.086844+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.15MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T14:55:00.118606+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.68MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-15T15:00:00.098930+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.68MB，已明显超过 5.0MB watcher 阈值

## 2026-07-15T15:05:00.097750+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.68MB，已明显超过 5.0MB watcher 阈值

## 2026-07-15T15:10:00.106057+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.21MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T08:29:47.049871+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.21MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=1039.2008311833333）
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=1039.78389785）

## 2026-07-16T08:33:53.033925+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=1043.3005654166668）

## 2026-07-16T08:35:00.092618+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=1044.4182103）

## 2026-07-16T08:55:00.096960+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T09:00:00.087129+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T09:05:00.118055+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-16T09:15:00.101776+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 8.29MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T09:20:00.113050+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.42MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T09:25:00.115067+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T09:30:00.088927+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.96MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T09:35:00.087298+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T09:40:00.115016+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T09:45:00.122086+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T09:50:00.086263+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T09:55:00.136755+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.93MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:00:00.107496+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T10:05:00.096678+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T10:10:02.089325+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-16T10:15:00.139920+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:20:00.103366+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:25:00.095134+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:30:00.119906+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:35:00.096599+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:40:00.106969+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.91MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:45:00.107527+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.91MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:50:00.088657+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T10:55:00.106442+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:00:00.115614+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-16T11:05:00.082301+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:10:00.090784+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:15:00.081971+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:20:00.103467+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:25:00.090981+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:30:00.110110+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:35:00.095872+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:40:00.125938+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:45:00.096092+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:50:00.093748+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T11:55:00.094684+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:00:00.119809+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:05:00.091786+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:10:00.091518+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:15:00.137930+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:20:00.116538+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:25:00.094835+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:30:00.112143+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:35:00.099683+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:40:00.093029+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:45:00.097560+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:50:00.090797+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T12:55:00.100233+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:00:00.108957+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:05:00.111371+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:10:00.099586+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:15:00.093507+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:20:00.129041+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:25:00.095998+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:30:00.111721+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:35:00.090921+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:40:00.103734+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:45:00.093065+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:50:00.094007+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T13:55:00.096608+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:00:00.103207+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:05:00.101617+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:10:28.410427+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:15:00.087475+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:20:00.092067+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:25:00.116278+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:30:00.110792+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:35:00.095114+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:40:00.086374+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:45:00.109894+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:50:00.122563+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T14:55:00.085075+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:00:00.107608+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:05:00.092313+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:10:00.121213+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-16T15:15:00.110709+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 10.00MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-16T15:20:00.105507+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 10.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:25:00.093677+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 10.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:30:00.090936+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 10.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:35:00.091772+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 10.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:40:00.087919+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.84MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-16T15:45:00.082430+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 10.00MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:50:00.080753+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T15:55:00.082012+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.97MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:00:00.108683+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:05:00.126774+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:10:00.127835+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:15:00.108409+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T16:20:00.334335+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T16:25:00.425854+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T16:30:00.082910+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-16T16:35:00.163786+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:40:00.097909+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:45:00.087371+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:50:00.383970+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T16:55:00.088556+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T17:00:00.090791+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-16T17:05:00.125089+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T09:18:22.716765+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=973.3785294166667）

## 2026-07-17T09:20:00.086545+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T09:25:00.092450+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T09:30:00.127831+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T09:55:00.104105+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T10:05:00.116308+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T10:10:00.083065+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T10:25:01.265267+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T10:30:00.134263+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T11:28:06.878705+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=53.11441175）

## 2026-07-17T12:00:00.108276+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.67MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:05:00.080383+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 7.67MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:10:00.083932+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:15:00.086846+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:20:00.083244+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:25:00.088254+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:30:00.087272+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:35:00.114030+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:40:00.086902+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:45:00.087884+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:50:00.151351+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T12:55:00.127224+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:00:00.227771+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.89MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:05:00.089399+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.89MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:10:00.135894+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.89MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:15:00.118709+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.89MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:20:00.091960+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.89MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:25:00.091671+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.89MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:30:00.109358+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.88MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:35:00.090368+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:40:00.090626+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.99MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:45:00.084900+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:50:00.108185+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T13:55:00.090742+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:00:00.113621+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:05:00.105539+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:10:00.092752+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:15:00.125577+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:20:00.088221+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:25:00.100944+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:30:00.126906+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:35:00.094763+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:40:00.085961+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:45:00.138611+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:50:00.095418+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T14:55:00.107812+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:00:00.108252+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:05:00.121849+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:10:00.115037+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:15:00.089814+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:20:00.090904+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:25:00.096509+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:30:00.202316+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:35:00.097114+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.81MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:40:00.102373+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.81MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T15:45:00.120467+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.89MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T15:50:00.099549+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.92MB，已明显超过 5.0MB watcher 阈值
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T15:55:00.091033+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.95MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T16:00:00.094759+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.95MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T16:05:00.076308+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.98MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T16:10:00.094785+08:00

- [CRITICAL] TRAJECTORY_TOO_LARGE: 当前主 trajectory 9.94MB，已明显超过 5.0MB watcher 阈值

## 2026-07-17T16:50:00.096588+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-17T16:55:00.099232+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T17:00:00.117676+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-17T17:05:00.101164+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-17T17:10:00.096734+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-17T17:15:00.097266+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-17T17:20:00.132762+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-17T17:25:00.094570+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-17T17:30:00.111954+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-17T17:35:00.088635+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-17T17:40:00.247415+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-17T17:45:00.087688+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-17T17:50:00.109914+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-17T17:55:00.103385+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T08:17:41.145906+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=3742.6856484333334）

## 2026-07-20T08:21:21.774756+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T08:25:00.115404+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T08:30:00.110029+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error
- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T08:35:00.104097+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T08:45:00.098386+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T08:50:00.104452+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T08:55:00.151691+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T09:00:00.138574+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T09:05:00.094386+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T09:10:00.096551+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T09:15:01.795439+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T09:20:00.101249+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T09:25:00.147312+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T09:57:52.878282+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=32.8811547）

## 2026-07-20T10:00:00.115609+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:05:00.081721+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:10:00.089042+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:15:00.096347+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:20:00.092681+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:25:00.098734+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:30:00.091108+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:40:00.497391+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service, openclaw-health-collector.service

## 2026-07-20T10:45:00.332990+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service, openclaw-health-collector.service

## 2026-07-20T10:50:00.231126+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T10:55:00.314762+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:00:00.385877+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:05:00.639379+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service

## 2026-07-20T11:10:00.268480+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:15:00.241431+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:20:00.244677+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:25:00.234409+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:30:00.383253+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:35:00.208517+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:40:00.331809+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:45:00.290815+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:50:00.276296+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T11:55:00.359331+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:00:00.387329+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T12:05:00.244332+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T12:10:00.114398+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:15:00.114434+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:20:00.121442+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:25:00.119423+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:30:00.113109+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:35:00.128438+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:40:06.037073+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:45:00.150413+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service

## 2026-07-20T12:50:00.208245+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T12:55:00.979964+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service

## 2026-07-20T13:00:00.538723+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service

## 2026-07-20T13:05:00.400080+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:10:00.099861+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:15:00.100222+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:20:00.131364+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:25:00.083950+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:30:00.089015+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:35:00.107304+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:40:00.102016+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service

## 2026-07-20T13:45:00.349338+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service

## 2026-07-20T13:50:00.109105+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T13:55:00.153701+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T14:00:00.110373+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T14:05:00.088658+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T14:10:00.116265+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T14:15:00.108546+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T14:20:00.115805+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T14:25:00.110263+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T14:35:00.118304+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T14:40:00.104627+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T14:45:00.102795+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-health-collector.service

## 2026-07-20T14:50:00.110678+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T14:55:00.095075+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T15:00:00.104382+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T15:05:00.098616+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T15:10:00.089861+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-frontstage-guardian.service

## 2026-07-20T15:15:00.133994+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service

## 2026-07-20T15:20:00.138365+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-20T15:25:00.101147+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-20T15:30:00.096156+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-frontstage-guardian.service

## 2026-07-20T15:45:00.114295+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-20T15:50:00.137216+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-20T15:55:00.146822+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-20T16:05:00.082503+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-20T16:10:00.099429+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-20T16:30:03.455530+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-20T16:55:00.085778+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-20T17:00:00.101515+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-task-scheduler.service

## 2026-07-20T17:15:00.269469+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T07:37:30.955823+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=856.5825970499999）
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=852.5157970500001）

## 2026-07-21T07:50:00.084052+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T08:20:00.108448+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T08:30:00.146294+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T08:35:00.093470+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error
- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T08:50:00.101092+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-21T08:55:00.086274+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T09:15:00.134072+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T09:20:00.098483+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-21T09:35:00.091275+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T10:05:00.103966+08:00

- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T10:50:00.084981+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-21T11:25:14.985533+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-health-collector.service

## 2026-07-21T12:43:45.970088+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=60.21616813333333）
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=58.76611813333333）

## 2026-07-21T14:45:00.087401+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error
- [CRITICAL] HEALTH_STUCK_SESSION_DETECT: health-collector 子检查异常：stuck-session-detect / 发现 1 个卡住会话，⚠ 主会话被阻塞！

## 2026-07-21T14:50:00.089526+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-21T14:55:01.610898+08:00

- [CRITICAL] CRON_NOT_OK: 救命 1 最近状态不是 ok：error

## 2026-07-21T15:10:03.705100+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=15.036485）

## 2026-07-21T16:10:05.243502+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.02695836666667）

## 2026-07-21T17:10:06.783227+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.02698711666667）

## 2026-07-22T07:41:07.118249+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=860.7186374833333）
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=871.0069208166666）

## 2026-07-22T08:41:12.011836+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.0853806）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-22T09:41:13.765576+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.03064293333333）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-22T10:41:15.986149+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.04196915）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-lifecycle-maintainer.service

## 2026-07-22T11:41:17.375353+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.024472550000006）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-lifecycle-maintainer.service

## 2026-07-22T12:41:18.970548+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.0279758）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-lifecycle-maintainer.service

## 2026-07-22T13:41:20.442828+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.02588046666666）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：mark42-watchdog.service, openclaw-lifecycle-maintainer.service

## 2026-07-22T14:41:22.477317+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.03595528333334）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-22T15:41:24.125353+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.02902255）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-22T16:41:25.691002+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.0274167）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-22T17:41:27.529955+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.03204925）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T07:15:43.554976+08:00

- [DEADMAN] BACKUP_STALE: backup 最近快照超过 25 分钟或无法读取（age=799.5092496）
- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=814.2713996）

## 2026-07-23T08:15:48.353983+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.08373305）

## 2026-07-23T08:56:05.481609+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=40.28694348333333）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T08:56:17.110697+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=40.48076161666667）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T08:56:26.625215+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=40.63933691666667）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T08:57:42.217740+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=41.89921233333334）
- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T09:05:46.775746+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=49.9751791）

## 2026-07-23T09:15:50.532038+08:00

- [DEADMAN] CRON_STALE: 救命 1 最近成功运行距离现在超过 15 分钟（age=60.037783966666666）

## 2026-07-23T09:20:00.107196+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T09:25:00.113549+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T09:30:00.079868+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T09:50:00.086754+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T09:55:00.093021+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

## 2026-07-23T10:00:00.113521+08:00

- [CRITICAL] SYSTEMD_INACTIVE: 存在 inactive/failed 的 openclaw/mark42 单元：openclaw-lifecycle-maintainer.service

