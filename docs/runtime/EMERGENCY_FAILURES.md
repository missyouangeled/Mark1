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

