# 统一日报采集器 (Daily Transcript Aggregator)

## 用途

每 5 分钟自动扫描所有模型的当天会话记录，汇集成一份统一日报（`memory/daily/YYYY-MM-DD-transcript.md`）。

**核心价值**：换模型后，新模型能直接读取今天所有对话（跨模型），不会出现"昨天的对话去哪了"的情况。

## 文件

| 文件 | 说明 |
|------|------|
| `scripts/aggregate-daily-transcript.py` | 采集脚本 |
| `daily-transcript-aggregator.service` | systemd oneshot 服务 |
| `daily-transcript-aggregator.timer` | systemd timer（每 5 分钟） |

## 安装

```bash
cp tools/daily-transcript-aggregator/daily-transcript-aggregator.service ~/.config/systemd/user/
cp tools/daily-transcript-aggregator/daily-transcript-aggregator.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now daily-transcript-aggregator.timer
```

## 验证

```bash
# 检查 timer 状态
systemctl --user show daily-transcript-aggregator.timer -p UnitFileState -p ActiveState -p SubState

# 检查上一次运行结果
systemctl --user show daily-transcript-aggregator.service -p Result -p ExecMainStatus

# 手动跑一次
python3 scripts/aggregate-daily-transcript.py --print | head -50

# 查看今天的输出
cat memory/daily/$(date +%Y-%m-%d)-transcript.md
```

## 升级后恢复

如果 OpenClaw 升级导致 timer 丢失，重新执行安装步骤即可。输出文件在 workspace 内，不受升级影响。
