# OpenClaw Frontstage Recovery Watcher

- 适用机器：公司（Linux）（脚本本身也可给其他 Linux 机器复用）
- 系统 / OS：Linux
- 用途：周期对比当前前台 dashboard 的 durable transcript 与 `chat.history` 投影，尽早发现“live 里出现过、但最终没稳定留在前台/history”的主回复异常，并通过 frontstage broker 做辅助回报。

## 当前产物

- 观察脚本：`scripts/openclaw-frontstage-recovery-watch.py`
- systemd service 模板：`tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.service`
- systemd timer 模板：`tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.timer`

## 当前状态文件

默认会写到：

- `~/.local/state/openclaw/frontstage-recovery/last-report.json`
- `~/.local/state/openclaw/frontstage-recovery/notify-state.json`
- `~/.local/state/openclaw/frontstage-recovery/frontstage-recovery-events.log`

其中：

- `last-report.json`：最近一次观测结果
- `notify-state.json`：最近一次已投递的 anomaly / recovered 事件，用来给 timer 轮询去重
- `frontstage-recovery-events.log`：辅助记录 `notify_sent / notify_failed`

## 当前检测范围

当前第一版最小检测覆盖五类情况：

1. `assistant_missing_in_history`
   - transcript 里有可见 assistant 回复，但 `chat.history` 投影里没有稳定结果
2. `history_oversized_placeholder`
   - `chat.history` 返回了 `[chat.history omitted: message too large]`
3. `assistant_text_mismatch`
   - transcript 与 `chat.history` 的最新可见 assistant 文本不一致
4. `assistant_turn_missing_visible_text`
   - assistant turn 实际已经发生，但最终稳定可见文本为空（例如 silent `NO_REPLY` 或只剩工具阶段内容）；前台可能出现“边回边消失”
5. `yielded_tool_result_missing_visible_reply`
   - 主会话已经收到带 `message` 的 `status=yielded` 工具结果，但它没有投影成可见 assistant 回复；前台常见体感就是“三个点先消失了，但没回字”

另外，脚本会把以下这类情况判成：

- `pendingProjection`

包括：

- 最新 transcript 只是比 `chat.history` 早一步落盘
- 目标 dashboard 当前仍有 `hasActiveRun=true`
- 目标 dashboard 当前 session 仍处于 `running`
- 目标 dashboard 刚结束不久，`chat.history` 仍在做最后一轮追赶

这类情况当前**不算异常**，也不会发前台告警，避免把正常的 history 追赶延迟、tool 阶段、history reload 空窗误报成故障。

当前还额外有一条更偏“补救”的行为：

- 如果命中 `yielded_tool_result_missing_visible_reply`，且 watcher 能拿到 `yielded.message` 的正文，它会优先把这段正文直接重新投递到当前前台，而不是只发一句泛化告警。
- 这样做的目标不是替代主链，而是在“run 已结束、三个点消失、但真正想给用户看的 yielded 文本没投影出来”时，先把那条本来就该看见的话补回来。

## 手工运行

```bash
python3 scripts/openclaw-frontstage-recovery-watch.py --print-human
python3 scripts/openclaw-frontstage-recovery-watch.py --print-json
python3 scripts/openclaw-frontstage-recovery-watch.py --notify-frontstage --print-human
python3 scripts/test-frontstage-recovery-watch.py
```

退出码：

- `0` = 正常 / 仅 pendingProjection
- `1` = 检测到 anomaly

其中：

- `scripts/test-frontstage-recovery-watch.py` 是当前第二阶段的最小稳定性回归脚本，用来验证 anomaly / duplicate suppression / recovered / pending 这些关键过渡逻辑。

## systemd 接入（公司 Linux）

把模板复制到用户态 systemd 目录后启用：

```bash
mkdir -p ~/.config/systemd/user
cp tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.service ~/.config/systemd/user/
cp tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-frontstage-recovery-watch.timer
```

当前默认频率：

- 开机后约 60 秒首次运行
- 之后约每 15 秒运行一次

当前 service 模板默认会带上：

```ini
ExecStart=/usr/bin/python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-frontstage-recovery-watch.py --notify-frontstage --print-human
```

含义是：除了持续写 `last-report.json`，它也会在 anomaly / recovered 这些状态变化时，经由 `scripts/openclaw-frontstage-broker.py` 把一句辅助摘要回到当前 dashboard 前台。

## 边界

- 这条 watcher 目前只做**观察 + 辅助回报**，不直接拦截正常主回复。
- 它依赖：Gateway CLI、session transcript、`chat.history`、以及本机 Python / systemd。
- 如果前台异常来自更底层的整体阻塞，或 Gateway 本身已经严重失常，它也可能只能留下本地状态证据，不能保证一定把消息送达。
- 当前它的价值主要是：把“主回复像消失了 / 前台投影不稳定”从体感抱怨，尽量落成可复查的本地状态与可去重的辅助事件。
