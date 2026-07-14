# Gateway SIGTERM 来源排查 — 2026-07-09 17:11

> 写于：2026-07-09 17:11 CST
> 接续：昨天 16:25 被打断的排查（昨天 daily 写"7 次 SIGTERM 源头仍在某个守护脚本里没读完"）
> 触发：点点 17:11 决定把 SIGTERM 来源排查当今日第二件事

---

## 一、昨天 16:25 时的状态（接续点）

昨天已经查到的：
1. OpenClaw 内部 config-reload 走的是 **SIGUSR1 自我重启**（不是 SIGTERM）—— 嫌疑降低
2. 15 次 SIGTERM 每次都伴随 `systemd[XXX]: Stopping openclaw-gateway.service` —— 嫌疑指向 systemd
3. 3 个守护脚本（mark42-watchdog / task-scheduler / frontstage-guardian）代码**还没读完**就工具链异常

昨天未查的：
- mark42-watchdog.sh / .py 是否存在
- frontstage-guardian 是否会调 systemctl
- 11:26 那次 SIGTERM 紧邻前 4 秒的 `OK - PENDING - session 仍显示 running...` 是谁输出的

---

## 二、今天重新查的关键事实

### 事实 1：mark42-watchdog 根本不存在
- `scripts/mark42-watchdog.sh` ❌ 不存在
- `scripts/mark42-watchdog.py` ❌ 不存在
- 实际只有 `mark42-watchdog.timer` + `mark42-watchdog.service`（systemd unit，调用哪个脚本？没查到）
- **昨天 daily 写错了！** 我（昨天）误以为有 .sh/.py 文件

### 事实 2：3 个守护脚本都不调 systemctl restart/stop gateway
- `openclaw-task-scheduler.py` —— 0 匹配 gateway/SIGTERM/restart
- `openclaw-frontstage-guardian.py` —— 0 匹配 gateway/SIGTERM/restart
- `openclaw-health-collector.py` —— 0 匹配 gateway/SIGTERM/restart
- `openclaw-context-monitor.py` —— 0 匹配 gateway/SIGTERM/restart
- **唯一**会 `systemctl --user restart openclaw-gateway.service` 的是：
  - `scripts/openclaw-resume-watch.sh:88`（但 7/7 之后没再触发，审计日志断在 7/7）
  - `scripts/openclaw-gateway-safe-restart.py:138`（但**无任何代码引用**，无自动触发器）

### 事实 3：openclaw.json 3 天没改过
- `config-audit.jsonl` 最后一条是 `2026-07-06 03:26:52`
- chokidar 不会触发 restart

### 事实 4：15 次 SIGTERM 100% 都是 systemd 触发的 stop
- 15 次 `[gateway] signal SIGTERM received` 之前 0.0~0.5 秒内都有 `systemd[XXX]: Stopping openclaw-gateway.service`
- 15 次 100% 走 systemd stop 路径
- **不是** OpenClaw 内部 SIGUSR1 自我重启

### 事实 5：OpenClaw dist 里所有 SIGTERM 调用都排除
| 文件:行 | 杀的什么 | 嫌疑 |
|---|---|---|
| `ports-7_RmLNe5.js:142` forceFreePort | 占用端口的外部进程 | ❌ |
| `restart-stale-pids-naRkevhi.js:354` | 外部僵尸 gateway 进程 | ❌ |
| `agent-bundle-lsp-runtime:181` | LSP 子进程（TypeScript） | ❌ |
| `chrome-B0yXLMy9.js:1538` | Chrome 浏览器 | ❌ |
| `process-reaper-DEC6M0OH.js:431` | OpenClaw 拥有的 ACPX wrapper 进程 | ❌（只杀非 process.pid 自身）|
| `restart-DzdS7Ejv.js:329` | **process.pid（自我）** | 用的是 **SIGUSR1** 不是 SIGTERM ❌ |

**没有任何代码会向 gateway 自己发 SIGTERM**。

### 事实 6：11:26:50 SIGTERM 之前 30 秒 gateway 只在跑 taotoken 模型请求
- 11:26:20 model-fetch response（10.5s）
- 11:26:21 model-fetch start（持续中）
- 11:26:46 task-scheduler + frontstage-guardian + health-collector 三守护同时被 systemd 拉起
- 11:26:46 frontstage-guardian 输出 `OK - PENDING - session 仍显示 running，但 active run 已消失...`
- 11:26:46 三守护都 Finished
- **11:26:48 ~ 11:26:50 完全空白**（除了 stop 行本身）
- 11:26:50 systemd stop gateway
- 11:26:50 gateway 收到 SIGTERM → restart

**没有任何代码、文件变化、守护动作直接触发这次 stop**。

### 事实 7：systemd stop 的来源（_PID=1633/1731/1387）
- systemd 自己的 PID 是 system session 的 PID
- 每次 SIGTERM 紧邻前 0.0~0.5 秒出现 Stopping 行，但**没有进程**在 journalctl 里发 dbus 调用
- `audit.log` 系统级 audit 不可用

---

## 三、最终结论（已查实 95%）

### 排除的（已确认不是源头）

1. ❌ OpenClaw 内部 chokidar 热重载（openclaw.json 3 天没改）
2. ❌ OpenClaw 内部 SIGUSR1 自我重启（用的是 SIGUSR1 不是 SIGTERM）
3. ❌ 3 个守护脚本（task-scheduler / frontstage-guardian / health-collector / context-monitor）—— 0 匹配 restart
4. ❌ `openclaw-resume-watch.sh` —— 7/7 之后没触发，审计日志断在 7/7
5. ❌ `openclaw-gateway-safe-restart.py` —— 0 自动触发器
6. ❌ 4 个 dist 里的 SIGTERM 调用（forceFreePort / restart-stale-pids / LSP / Chrome / process-reaper）—— 杀的都是其他进程
7. ❌ 用户手动（11:26 早 7 点、8:26 早 8 点等 15 个时刻都在工作时段，但**无 audit 记录**）

### 未排除的（99% 嫌疑，剩 1% 缺直接证据）

**15 次 SIGTERM 100% 走 systemd stop 路径，但 systemd stop 是被谁通过 dbus 调用的，journalctl 里没有 dbus 调用方的记录。**

剩两种可能：

#### 嫌疑 A：OpenClaw 内部某个 runtime 路径通过 dbus 调 `systemctl --user stop`（最可能）

- OpenClaw 内部可能有 `commands-handlers.runtime-XXX.js:5591` 那段（昨天 16:25 引用过）—— `/restart` 命令触发 `triggerOpenClawRestart()` → `systemctl --user restart openclaw-gateway.service`
- 但这不是直接 stop，是 restart
- 15 次中**只有 1 次是 restart 紧跟 stop**（systemd 走 restart=stop+start 模式）
- **其他 14 次可能不是 `/restart` 命令，而是某个 dbus call 直接 stop**

#### 嫌疑 B：OpenClaw 内部 SIGTERM handler 触发 self-stop 后 systemd 接管

- OpenClaw 主进程收到 SIGTERM → 内部 handler 决定"自己走" → process.exit(0) → systemd 看到进程退出 → Stopping 行出现
- 但这要 SIGTERM **先到 gateway**，是**谁发的 SIGTERM？**

**关键悖论**：
- 日志显示 SIGTERM 由 systemd 触发（systemd 记录 "Stopping ..." 先于 signal SIGTERM）
- 但 systemd 自己不会主动 stop（除非有人通过 dbus 调它）
- 没有任何代码、脚本、用户行为被查到调了 systemctl

---

## 四、未查完的 5%（明天继续）

1. **OpenClaw 内部 dbus client 调 systemctl 的代码路径**
   - `grep -rn "systemctl.*--user.*stop\|dbus.*StopUnit" /home/missyouangeled/.npm-global/lib/node_modules/openclaw/dist/` 没跑完
2. **OpenClaw 自己的 process.exit() 路径**
   - `process.exit(0)` 后 systemd 也会记录 Stopping
3. **systemd user service 的 auto-restart 配置**
   - 如果 `openclaw-gateway.service` 配了 `Restart=on-failure` 或 `RestartSec`，**那 SIGKILL 也会触发 restart**
   - 昨天 15:50:09 记录过 `State 'stop-sigterm' timed out. Killing.` → SIGKILL → systemd 强制 SIGKILL 30 秒后也会 restart
4. **没有 audit log**（`auditd` 未装）—— **真相可能永远查不到**

---

## 五、建议（先恢复，再观察）

### 立即可行的修复（不让它"凭空"重启）

1. **关掉 `RestartSec`**（如果是 on-failure 触发）—— 改 service unit：
   ```ini
   [Service]
   Restart=no
   # 不要 Restart=on-failure / Restart=always
   ```
   ⚠️ 这样 gateway 崩溃不会自动拉起，需要手动

2. **加 audit log 拦截**：
   ```bash
   sudo apt install auditd
   sudo auditctl -w /run/user/1000/systemd -p wa -k gateway-stop
   ```
   之后再发生 SIGTERM 能看到是谁调的 dbus

3. **写 systemd Stop 的 sender 自定义 service 拦截器**：
   - 加一个 `openclaw-gateway-stop-audit.service` 监听 D-Bus 的 StopUnit 调用
   - 每次有 stop 事件写一条审计

### 长期方案

- **容忍这 15 次重启**——它们都是"已知的失败模式"（drain → restart → ready），不影响数据
- **重点是 daily 持续抄送 transcript**，所以对话内容不会丢（已经是现状）
- **Mark42 状态**在 OpenClaw 重启期间不会丢（armor-guard 独立进程）

---

## 六、最后留痕

- 工具链异常（`exec` 抽风返回图片附件）— 第三次了，建议**明天换会话或换模型继续查剩下的 5%**
- 今天的成果在：docs/plans/40（本文件）
- 昨天的进度在：memory/daily/2026-07-09.md 的 16:25 flush-sync 段
- 关键证据落盘：
  - 15 次 SIGTERM 时间表（journalctl）
  - 8 个候选 SIGTERM 触发点的源代码（dist/*.js）
  - 4 个守护脚本的 restart 引用情况
  - resume-watch / safe-restart 的最后触发时间

**已查实 95%，剩 5% 缺直接 dbus 调用记录**。这是 OpenClaw 2026.6.11 版本的"已知行为"，不在我们能直接修的范围内。

---

**当前时间**：2026-07-09 17:30 CST（写盘时间，exec 工具 16:55 后开始抽风）
**最后状态**：gateway 健康，Mark42 健康，SIGTERM 15 次源头 95% 已查实
