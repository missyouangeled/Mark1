# OpenClaw Supervisor

- 适用机器：公司（Linux）（脚本本身也可给其他 Linux 机器复用）
- 系统 / OS：Linux
- 用途：把 `scripts/openclaw-supervisor-status.py` 以用户态 systemd service/timer 的方式周期运行，持续刷新监工状态文件，供本地健康页与后续监工逻辑读取。

## 当前产物

- 监工脚本：`scripts/openclaw-supervisor-status.py`
- systemd service 模板：`tools/openclaw-supervisor/openclaw-supervisor-watch.service`
- systemd timer 模板：`tools/openclaw-supervisor/openclaw-supervisor-watch.timer`

## 状态输出

默认会写到：

- `~/.local/state/openclaw/supervisor/supervisor-status.json`
- `~/.local/state/openclaw/supervisor/service-control.json`
- `~/.local/state/openclaw/supervisor/supervisor-events.log`

其中：

- `service-control.json` 负责表达当前监工服务控制语义：
  - `policyMode = auto | force_on | force_off`
  - `taskActive = true | false`
- `supervisor-status.json` 负责表达当前推导后的监工状态：
  - `service.state = disabled | armed | active | stopping`
  - `status = idle | waiting | running | stalled | done | failed`
- `notify-state.json` 记录最近一次已投递的监工事件，用来给 timer 轮询去重，避免重复刷屏

## 当前默认语义

- 默认基线：`auto + taskActive=false`
- 简单工作：保持 `auto + taskActive=false`
- 复杂工程：切到 `auto + taskActive=true`
- 用户显式说“开监工服务”：切到 `force_on`
- 用户显式说“关监工服务”：切到 `force_off`
- 当上一轮后台任务完成后，若当前仍处于工作型监工语义（`force_on` 或 `taskActive=true`），监工会进入一个默认约 10 分钟的“等待接续任务”窗口：
  - 会先向前台发一句“已完成，等待下一轮后台任务”的提示
  - 若窗口内出现新的 active run，则继续盯下一轮
  - 若窗口超时仍没有新的后台任务或继续信号，则自动退回 `auto + taskActive=false`

## 手工运行

```bash
python3 scripts/openclaw-supervisor-status.py --print-human
python3 scripts/openclaw-supervisor-status.py --print-json
```

常用控制：

```bash
# 强制开监工服务
python3 scripts/openclaw-supervisor-status.py --set-policy-mode force_on --reason 'user-request' --print-human

# 强制关监工服务
python3 scripts/openclaw-supervisor-status.py --set-policy-mode force_off --reason 'user-request' --print-human

# 恢复自动 + 当前不激活
python3 scripts/openclaw-supervisor-status.py --set-policy-mode auto --deactivate-task --reason 'back-to-auto' --print-human

# 标记当前轮为复杂工程
python3 scripts/openclaw-supervisor-status.py --set-policy-mode auto --activate-task --reason 'complex-work' --print-human
```

退出码：

- `0` = 正常（`idle / running / done`）
- `1` = `stalled`
- `2` = `failed`

建议在 systemd service 里保留：

```ini
SuccessExitStatus=1 2
```

这样 systemd 会把“监工发现 stalled/failed”视为一次**成功完成的状态刷新**，而不是把 service 本身误标成执行失败。

## systemd 接入（公司 Linux）

把模板复制到用户态 systemd 目录后启用：

```bash
mkdir -p ~/.config/systemd/user
cp tools/openclaw-supervisor/openclaw-supervisor-watch.service ~/.config/systemd/user/
cp tools/openclaw-supervisor/openclaw-supervisor-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-supervisor-watch.timer
```

当前默认频率：

- 开机后约 1 分钟首次运行
- 之后约每 30 秒运行一次

这样可以较平滑地覆盖 3 分钟静默阈值，而不需要高频常驻轮询。

当前 service 模板默认会带上：

```ini
ExecStart=/usr/bin/python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-supervisor-status.py --notify-transitions --print-human
```

含义是：除了刷新状态文件，它也会在 `stalled / failed / done` 这些状态变化时，自动做一次前台回报判定。

## 前台会话绑定（WebChat / Control UI）

在当前这类直聊里，用户点 `+` 新开页面后，会得到新的 dashboard `sessionKey`。因此监工/后台回报不能继续绑死在启动时那个旧 dashboard 会话。

当前已落地的最小规则：

- 监工分身 owner 默认先收敛到共享父会话（通常是 `agent:main:main`）
- 真正要“发回前台”时，再优先解析到同一父会话下**最新的 dashboard 会话**
- 调试可用：

```bash
python3 scripts/openclaw-supervisor-subagent.py resolve-frontstage --session-key '<当前或旧的 dashboard key>' --print-json
```

- 实际前台投递可用：

```bash
python3 scripts/openclaw-supervisor-subagent.py send-frontstage --session-key '<当前或旧的 dashboard key>' --message '简短汇报' --print-json
```

这两条命令会输出：

- `resolvedOwnerSessionKey`：共享 owner 会话
- `targetSessionKey`：当前应视为前台的 dashboard 会话

其中 `send-frontstage` 当前走的是 `chat.inject`，会直接把 assistant note 落到解析出的前台会话，不额外触发一轮模型。

当前绑定选择还补了一条更保守的判定：

- 如果传入的是 `agent:main:main` 这类根直聊，会优先比较“请求会话本身”与“同一父会话下最新 dashboard”的 `updatedAt`
- 只有当 dashboard 明显更新得更新时，才继续投给 dashboard；否则优先回到当前这条根直聊
- 这样可以避免“旧 dashboard 还留在 store 里，但当前真正活着的是主直聊”时，辅助消息继续误投到昨天那页旧前台

当前已验证闭环：

- `supervisor-auto-notify-smoke` 任务完成后，状态脚本可识别 `done`
- `supervisor-auto-failed-smoke` 任务超时后，状态脚本可识别 `failed`
- `supervisor-auto-stalled-smoke` 在降低静默阈值的烟测下，状态脚本可识别 `stalled`
- 同一条 `supervisor-auto-stalled-smoke` 后续恢复完成后，状态脚本还能继续识别 `done`
- `--notify-transitions` 会生成 `notify-state.json`
- 事件日志会写入 `notify_sent ... messageId=...`
- 实际 assistant note 会被 inject 到当前 dashboard 前台

## 边界

- 该层只负责**独立观察 + 状态落盘**，不是聊天消息投递器。
- 它能稳定刷新监工状态，但不保证一定把结果直接发进当前聊天框。
- `main-supervisor-lite` 仍然只是按需拉起的补充协作层，不应重新退回“默认永远常驻分身”的旧模型。
- 若 Gateway、前端连接、渠道投递、或模型链路发生更底层整体阻塞，本层也可能只能留下本地状态证据，而不能独立完成对外回报。
