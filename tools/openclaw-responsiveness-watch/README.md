# OpenClaw 主会话响应性看门狗 (Responsiveness Watchdog)

## 用途

独立探测模型层无响应：当用户在主会话发送消息后，模型超过阈值时间仍未回复时，自动向主会话注入提醒。

**背景问题**：AGENTS.md 里的"30秒/60秒超时规则"是行为指引——但如果模型本身卡住了（限流、网络阻塞、provider 故障），这条规则执行不了。需要一条**完全独立于模型的消息链路**来感知这种情况。

## 与现有三条线的区别

| 机制 | 能探测 | 不能探测 |
|------|--------|---------|
| 监工服务 | 分身子任务卡住/异常 | 模型层无响应（监工自己也是模型调用） |
| 本地健康诊断 | Gateway 进程、端口、provider 可达性 | 主会话实际有没有收到模型回复 |
| 前台恢复观察 | 回复写入 transcript 但没投影到 history | transcript 里压根没有新回复 |
| **响应性看门狗** | **用户发消息后模型超时不回** | 主会话消息超时之外的问题 |

## 工作原理

1. systemd timer 每 15 秒触发一次
2. 脚本找当前最活跃的 dashboard 会话
3. 读其 transcript 最后一条消息
4. 若为 `user` 角色且距今 > 30 秒 → 注入提醒
5. 若距今 > 60 秒 → 注入更紧急的提醒
6. 去重：同一条用户消息不重复提醒同一级别

## 部署

### 安装

```bash
cp tools/openclaw-responsiveness-watch/openclaw-responsiveness-watch.service ~/.config/systemd/user/
cp tools/openclaw-responsiveness-watch/openclaw-responsiveness-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-responsiveness-watch.timer
```

### 验证

```bash
systemctl --user status openclaw-responsiveness-watch.timer
systemctl --user list-timers openclaw-responsiveness-watch.timer
```

### 手动运行

```bash
python3 scripts/openclaw-responsiveness-watch.py --print-human
python3 scripts/openclaw-responsiveness-watch.py --print-json
```

## 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `WARN_THRESHOLD_S` | 30 | 第一次提醒阈值（秒） |
| `CRIT_THRESHOLD_S` | 60 | 第二次提醒阈值（秒） |
| `MAX_BACKOFF_S` | 300 | 同一条消息最多提醒间隔（秒） |

## 状态文件

- `~/.local/state/openclaw/responsiveness-watch/notify-state.json` — 去重状态
- `~/.local/state/openclaw/responsiveness-watch/responsiveness-watch-events.log` — 事件日志

## 注入链路

`responsiveness-watch.py → infos-handle contract → infos-handle sidecar → chat.inject → 主会话`

与 `frontstage-recovery-watch` 使用相同的注入路径（`delivery_mode="frontstage"`），由 infos-handle 统一收口投递。

## 适用机器

- 通用（公司 Linux、掌机 Windows）

## 实现日期

2026-05-22
