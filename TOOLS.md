# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## 有用参考 / 书签

- **免费 API 目录**: https://github.com/public-apis/public-apis — 社区维护的公开 API 清单，含天气/金融/地理/动物等数百个免费 API，按分类排列，标注是否需要 key、是否支持 HTTPS/CORS。43 万 star，MIT 协议，安全可靠。

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## 权限规则

- 适用机器：公司（Linux）
- 本机默认拥有最高权限，无需逐次确认；涉及连接到其他设备操作时，再询问权限。

## Local Setup Notes

### OpenClaw automation

- 适用机器：通用（其中带“掌机”字样的条目仅适用于掌机（Windows））
- 系统 / OS：通用 / Windows / Linux（按各条目说明执行）

- 口袋速记：纯日常聊天 / 简单工作 = 监工服务默认 `auto + taskInactive`；复杂工程 / 长耗时 / 易阻塞前台 = 默认切到 `auto + taskActive`；用户可随时显式切成 `force_on` / `force_off`；媒体仍必须按主会话真实可用验收。
- 补充硬规则：如果已经切到 `force_on` 或 `auto + taskActive=true`，并且已经对用户说“开始处理/继续推进”，就要立刻核对是否真的出现 `activeTaskCount>0`；若没有，就不要假装监工已经在盯，要么马上真卸后台任务，要么明确说明这轮仍在前台做，所以监工会先显示 `idle/待命`。
- 新增行为（2026-05-18）：当上一轮后台任务完成后，监工会进入约 10 分钟的“等待接续任务”窗口，并向前台发一句简短提示；若这段时间内出现新的 active run，就继续盯下一轮；若 10 分钟内没有新的后台任务或继续信号，则自动退回 `auto + taskActive=false`，不再无限期空挂在 `force_on/armed`。
- Startup online notice is driven by `BOOT.md` + the `boot-md` hook.
- 升级后自检入口：`docs/通用-OpenClaw-升级后自检清单.md`
- 升级后自检脚本：`scripts/openclaw-post-upgrade-self-check.py`
  - 用途：检测 OpenClaw 版本是否变化；若已升级，则按自检清单主动核对关键补丁 / broker / infos-handle / sidecar / unified proxy / recovery watcher
  - 常用命令：`python3 scripts/openclaw-post-upgrade-self-check.py --print-human`
  - 启动行为：当前 `BOOT.md` 已改成启动时先跑这支脚本；若版本未变，只发普通上线消息；若版本变化，则先做升级后自检，再带结果上线
  - 状态目录：`~/.local/state/openclaw/post-upgrade-self-check/`
- 变更流水文档：`docs/通用-OpenClaw-补丁变更流水.md`
- 非正式修改备忘录：`docs/通用-OpenClaw-非正式修改备忘录.md`
- 变更流水脚本：`scripts/openclaw-change-log.py`
  - 用途：每次做完修改/修补后，把“这次实际改了什么”按时间追加到变更流水里；若是未进入正式补丁体系的临时/手工/外部修改，也可直接追加到非正式修改备忘录
  - 推荐命令（变更流水）：`python3 scripts/openclaw-change-log.py capture --title '本次改动标题' --kind patch --scope 通用 --summary '一句结果摘要' --verify '最小验收结果' --registry-status 已更新 --rebuild-status 已更新 --selfcheck-status 不适用 --file path/to/file`
  - 推荐命令（非正式修改备忘录）：`python3 scripts/openclaw-change-log.py memo --title '本次备忘录标题' --kind manual-fix --scope 通用 --current-status 备查 --reason '为何未纳入正式补丁' --recovery '后续排查提示' --file path/to/file`
  - 说明：正式补丁除了写流水，还要同步更新补丁注册表 / 重建清单 / 必要时更新升级后自检清单；非正式但重要的修改还应补进非正式修改备忘录
- Resume recovery watcher script: `scripts/openclaw-resume-watch.sh`
- WebChat / Control UI 直聊里的轻量后台分身，不要依赖 `thread:true` / `mode:"session"` 的线程绑定会话；默认优先使用一次性 `sessions_spawn(mode:"run", context:"isolated")`。
- 本地健康诊断层（公司 / Linux 机器）：
  - 适用机器：公司（Linux）
  - 系统 / OS：Linux
  - 诊断脚本：`scripts/openclaw-local-health-diagnose.py`
  - README：`tools/openclaw-local-health/README.md`
  - systemd 模板：`tools/openclaw-local-health/openclaw-local-health-watch.service` / `tools/openclaw-local-health/openclaw-local-health-watch.timer`
  - 当前状态目录：`~/.local/state/openclaw/local-health/`
  - 用途：在不依赖 AI 回复的前提下，对 gateway、本机外联、主线 provider 路由做周期探测，并把结果写入本地状态文件
  - 默认频率：开机后约 2 分钟首次运行，之后约每 5 分钟一次
  - 当前也会读取监工状态文件，并在页面里显示“监工”卡片与明细
  - 当前也可在 `warn / critical / recovered` 这些健康状态变化时，经由 frontstage broker 把一句摘要回到当前 dashboard 前台
  - 边界：不负责页面主会话消息超时监听；那部分继续由监工服务 / 监工分身兜底
- 监工状态脚本：`scripts/openclaw-supervisor-status.py`
  - 状态文件：`~/.local/state/openclaw/supervisor/supervisor-status.json`
  - 控制文件：`~/.local/state/openclaw/supervisor/service-control.json`
  - 通知状态文件：`~/.local/state/openclaw/supervisor/notify-state.json`
  - 策略模式：`auto` / `force_on` / `force_off`
  - 当前默认基线：`auto + taskActive=false`
  - 自动回报：可在 `stalled / failed / done` 这些状态变化时，通过 `send-frontstage + chat.inject` 把一句监工消息直接回到当前前台 dashboard，并做事件去重，避免 timer 每 30 秒重复刷屏
  - 常用命令：
    - 查看：`python3 scripts/openclaw-supervisor-status.py --print-human`
    - 开监工服务：`python3 scripts/openclaw-supervisor-status.py --set-policy-mode force_on --reason 'user-request' --print-human`
    - 关监工服务：`python3 scripts/openclaw-supervisor-status.py --set-policy-mode force_off --reason 'user-request' --print-human`
    - 恢复自动：`python3 scripts/openclaw-supervisor-status.py --set-policy-mode auto --deactivate-task --reason 'back-to-auto' --print-human`
    - 标记当前轮为复杂任务：`python3 scripts/openclaw-supervisor-status.py --set-policy-mode auto --activate-task --reason 'complex-work' --print-human`
    - 手工触发一次自动回报判定：`python3 scripts/openclaw-supervisor-status.py --notify-transitions --print-json`
- 前台辅助消息 broker：`scripts/openclaw-frontstage-broker.py`
  - README：`tools/openclaw-frontstage-broker/README.md`
  - 兼容状态文件：`~/.local/state/openclaw/frontstage/broker-state.json`
  - 当前数据源目录：`~/.local/state/openclaw/broker/`
  - 当前关键产物：`events.jsonl` / `manifest.json` / `views/frontstage.json` / `views/health.json` / `views/tasks.json` / `views/recovery.json`
  - 最小回归：`scripts/test-frontstage-broker.py`
  - 重建入口：`scripts/apply-openclaw-frontstage-broker-data.py` / `scripts/openclaw-frontstage-broker.py rebuild-views`
  - systemd 模板：`tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service` / `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer`
  - 当前用户态 systemd：`~/.config/systemd/user/openclaw-frontstage-broker-rebuild.service` / `~/.config/systemd/user/openclaw-frontstage-broker-rebuild.timer`
  - 默认频率：开机约 75 秒后首次运行，之后约每 60 秒重建一次 broker 视图
  - 用途：把监工、本地健康、前台恢复观察这类辅助消息统一收口后再发回当前前台 dashboard，并在当前阶段开始沉淀成 sidecar 数据源
  - 当前来源：`supervisor` / `local-health` / `frontstage-recovery`
  - 当前动作：`emit` / `rebuild-views`
  - 路线：broker -> `openclaw-supervisor-subagent.py send-frontstage` -> `chat.inject`
  - 规则：按 `source + eventKey` 去重；默认不接管正常主回复，只处理辅助消息；升级后可先跑 apply/rebuild 入口恢复视图；当前再由 rebuild timer 周期刷新视图，降低“长时间无新辅助消息时视图变旧”的风险
- infos-handle sidecar：`scripts/openclaw-infos-handle-sidecar.py`
  - README：`tools/openclaw-infos-handle-sidecar/README.md`
  - service 模板：`tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
  - 当前用户态 systemd：`~/.config/systemd/user/openclaw-infos-handle-sidecar.service`
  - 脚本默认监听：`127.0.0.1:18790`
  - 当前 service 实际监听：`0.0.0.0:18790`
  - 鉴权：本地 localhost 直连免鉴权；远程/LAN 访问需 `Authorization: Bearer <gateway-token>`；经统一入口代理时按 `X-Forwarded-For` / `X-Real-IP` 识别原始客户端
  - 远程限流：默认只对非 localhost 客户端生效，`120 req / 60s`（环境变量：`INFOS_HANDLE_SIDECAR_REMOTE_RATE_MAX` / `INFOS_HANDLE_SIDECAR_REMOTE_RATE_WINDOW_S`）
  - 用途：给 Control UI / 其他轻量 consumer 提供 infos-handle 的最小 HTTP / SSE 直连入口
  - 当前最小接口：`GET /healthz` / `GET /v1/query/<kind>` / `POST /v1/handle` / `GET /v1/events/stream`
  - 当前状态：已在公司（Linux）机安装并启用；Control UI branding 补丁默认会优先读这条 sidecar，失败时再回退 broker snapshot 静态文件
- infos-handle 统一入口代理：`tools/openclaw-infos-handle-gateway-proxy/`
  - Caddyfile：`tools/openclaw-infos-handle-gateway-proxy/Caddyfile`
  - README：`tools/openclaw-infos-handle-gateway-proxy/README.md`
  - apply/verify：`scripts/apply-openclaw-infos-handle-gateway-proxy.py`
  - service 模板：`tools/openclaw-infos-handle-gateway-proxy/openclaw-unified-proxy.service`
  - 当前用户态 systemd：`~/.config/systemd/user/openclaw-unified-proxy.service`
  - 当前监听：`0.0.0.0:18788`
  - 路由：infos-handle API → `127.0.0.1:18790`；其余 → Gateway `127.0.0.1:18789`
  - 当前会透传原始客户端 IP（`X-Forwarded-For` 走 Caddy 默认反代行为，`X-Real-IP` 显式补上），避免 sidecar 把远程代理请求误判为 localhost 免鉴权
- 前台恢复观察 watcher：`scripts/openclaw-frontstage-recovery-watch.py`
  - 状态目录：`~/.local/state/openclaw/frontstage-recovery/`
  - 关键文件：`last-report.json` / `notify-state.json` / `frontstage-recovery-events.log`
  - 用途：对比 durable transcript 与 `chat.history` 投影，观察“主回复在前台没稳定留下 / 前台投影异常”的情况，并在 anomaly / recovered 这些变化时经由 broker 回前台
  - 当前检测：`assistant_missing_in_history` / `history_oversized_placeholder` / `assistant_text_mismatch` / `assistant_turn_missing_visible_text`
  - 当前也会识别 `pendingProjection`，把“history 还在追赶最新 transcript”的短窗口排除在异常之外
  - 当前还会读取目标 dashboard 的 session 活跃态；若 `hasActiveRun=true` 或 session 仍是 `running`，则优先判成“仍在进行中”的 pending，而不是急着报 anomaly
  - 当前还会把“session 刚结束不久，但 history 还在做最终追赶”的短窗口判成 `pendingProjection(session-recently-ended)`，避免 tool-final / history reload 之后立刻误报
  - systemd 模板：`tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.service` / `tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.timer`
  - 当前用户态 systemd：`~/.config/systemd/user/openclaw-frontstage-recovery-watch.service` / `~/.config/systemd/user/openclaw-frontstage-recovery-watch.timer`
  - 当前默认频率：开机约 60 秒后首次运行，之后约每 15 秒运行一次
  - 当前已接入 broker 第二阶段：anomaly / recovered 都会按稳定 `eventKey` 去重后再回前台，不会每轮重复刷同一条
- 主会话响应性看门狗：`scripts/openclaw-responsiveness-watch.py`
  - README：`tools/openclaw-responsiveness-watch/README.md`
  - service 模板：`tools/openclaw-responsiveness-watch/openclaw-responsiveness-watch.service`
  - timer 模板：`tools/openclaw-responsiveness-watch/openclaw-responsiveness-watch.timer`
  - 当前用户态 systemd：`~/.config/systemd/user/openclaw-responsiveness-watch.service` / `~/.config/systemd/user/openclaw-responsiveness-watch.timer`
  - 状态目录：`~/.local/state/openclaw/responsiveness-watch/`
  - 默认频率：开机约 90 秒后首次运行，之后约每 15 秒运行一次
  - 用途：在主会话中检测模型层无响应——当用户发消息后超过 30 秒模型仍未回复时，通过 infos-handle 向主会话注入提醒（60 秒后升级为紧急提醒）；独立于模型运行，不依赖模型自身响应能力
  - 边界：只检测"用户消息 → 模型回复"超时，不覆盖其他类型的异常；依赖 session transcript 文件可读。**与本地健康诊断的边界**：健康诊断检测 Gateway 进程/端口/provider 可达性（基础设施层），看门狗检测模型层实际响应行为（应用层）——二者互补但不重叠，看门狗不重复健康诊断的功能。
- 监工分身管理脚本：`scripts/openclaw-supervisor-subagent.py`
  - 用途：通过 gateway RPC 间接调用 `/subagents`，做 `list / spawn / kill / resolve-frontstage / send-frontstage`
  - 说明：`tools.invoke` 直调 `sessions_spawn` 会被 gateway 拒绝为 `Tool not available: sessions_spawn`；当前可用路线是：
    - `tools.invoke -> subagents`：做 `list / kill`
    - `chat.send -> /subagents spawn ...`：做 `spawn`
    - `chat.inject`：做前台状态回报（不额外跑一轮模型）
  - 当前前台绑定语义（WebChat / Control UI 直聊）：
    - dashboard 会话只当“当前前台页”看，不再把它当长期 owner
    - 脚本会先把 owner 收敛到共享父会话（通常是 `agent:main:main`）
    - 真正要回报给用户时，再优先解析到同一父会话下**最新的 dashboard 会话**
    - 调试命令：`python3 scripts/openclaw-supervisor-subagent.py resolve-frontstage --session-key <当前或旧的 dashboard key> --print-json`
    - 实际投递：`python3 scripts/openclaw-supervisor-subagent.py send-frontstage --session-key <当前或旧的 dashboard key> --message '简短汇报' --print-json`
  - 当前已验证：即使传入旧 dashboard key，也能解析到较新的 dashboard 前台；`send-frontstage` 会把消息 inject 到那个较新的 dashboard，而不是旧页
- 监工 systemd 模板（公司 / Linux 机器）：
  - 适用机器：公司（Linux）
  - 系统 / OS：Linux
  - README：`tools/openclaw-supervisor/README.md`
  - service：`tools/openclaw-supervisor/openclaw-supervisor-watch.service`
  - timer：`tools/openclaw-supervisor/openclaw-supervisor-watch.timer`
  - 当前已安装到：`~/.config/systemd/user/openclaw-supervisor-watch.service` / `~/.config/systemd/user/openclaw-supervisor-watch.timer`
  - 当前状态：timer 已启用并开始周期刷新
  - 默认频率：开机约 1 分钟后首次运行，之后约每 30 秒刷新一次监工状态
- 监工分身保留标签：`main-supervisor-lite`
- 监工唯一标号格式：`main-supervisor-lite@<runtime-host>`（`<runtime-host>` 优先取运行时 host 元数据）
- 规则：这个标签只给主会话监工分身使用；普通任务分身不要复用。只有当当前轮确实需要聊天插播 / 额外协作时，才按需拉起监工分身；整体数量应为 `0 或 1`。若未来出现监工重复，先比较唯一标号；标号相同则保留最新且健康的一个（健康 = 未失败、未超时、未被杀，且近期仍有活动或可见进度）。
- 场景速记：简单工作 = 自动模式下默认不激活监工；复杂工程但不一定阻塞 = 自动模式 + `taskActive=true`，可不强开监工分身；复杂工程且需要前台插播/额外协作 = 自动模式 + `taskActive=true` + 按需监工分身；用户显式开/关 = 优先服从 `force_on` / `force_off`。
- 新增收紧规则（2026-05-15）：如果一段持续开发活决定按“后台推进 + 监工盯着 + 3 分钟回报”这套方式执行，就必须**真卸成后台任务**给监工盯；不能只把监工服务开成 `force_on` 却还在前台当前会话里继续做。否则监工只会显示 `idle/待命`，既不算真正盯着，也很难自然满足 3 分钟一次回报。
- 自动判定口径：单轮问答、明确命令执行、很小的单文件修改、短解释 = 可视为简单工作；长耗时排错、跨文件改动、需要后台下载/构建/测试、需要分身协作、用户已强调“工程复杂” = 视为复杂工程，默认激活监工。
- 异常处置速记：任务空返回 = 先由监工报告，再检查；任务异常结束 = 先由监工报告，再修复；3 分钟无可见产出 = 监工必须补一句短进度，不等于任务必须 3 分钟内完成；当前直聊里要优先避免为了兜底而频繁制造可见内部消息与额外 token 消耗。
- 能力边界速记：监工是兜底层，不是独立于 Gateway/渠道/模型链路之外的万能保险；若 Gateway 整体卡死、前端连接断开、渠道投递失效或同一路由模型调用全局阻塞，监工也可能一起失效。
- 主会话本地媒体附件（音频 / 视频 / 图片）会按 realpath 做允许路径校验；如果工作区内路径实际是软链并跳到 workspace 外（例如 `/mnt/data/...`），Control UI 可能把它拦成 `path-not-allowed`。这类文件发回主会话前，应先 stage/copy 回 workspace 内真实目录。
- Windows 更新脚本（掌机）：
  - 适用机器：掌机（Windows）
  - 系统 / OS：Windows
  - `scripts/update-openclaw.ps1`
  - `scripts/update-openclaw.cmd`
  - 用途：执行 `git pull --ff-only`，若仓库有新提交则自动 `openclaw gateway restart`
  - 掌机建议直接运行：`.\scripts\update-openclaw.cmd`
- Windows gateway 保活（掌机）：
  - 适用机器：掌机（Windows）
  - 系统 / OS：Windows
  - watchdog 脚本：`scripts/openclaw-gateway-watchdog.ps1`
  - 安装脚本：`scripts/install-openclaw-gateway-watchdog.ps1`
  - 卸载脚本：`scripts/uninstall-openclaw-gateway-watchdog.ps1`
  - 停机脚本：`scripts/stop-openclaw-gateway-zhangji-windows.ps1`
  - 恢复脚本：`scripts/start-openclaw-gateway-zhangji-windows.ps1`
  - cmd 包装器：`scripts/install-openclaw-gateway-watchdog.cmd` / `scripts/uninstall-openclaw-gateway-watchdog.cmd` / `scripts/stop-openclaw-gateway-zhangji-windows.cmd` / `scripts/start-openclaw-gateway-zhangji-windows.cmd`
  - 桌面快捷入口：`关闭 OpenClaw（掌机）.cmd` / `启动 OpenClaw（掌机）.cmd`
  - 桌面快捷方式：`关闭 OpenClaw（掌机）.lnk` / `启动 OpenClaw（掌机）.lnk`
  - 电池策略修复脚本：`scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1`
  - cmd 包装器：`scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.cmd`
  - 计划任务名：`OpenClaw Gateway Watchdog` / `OpenClaw Gateway`
  - 作用：登录时检查一次，并且每 3 分钟巡检一次；若本地 `http://127.0.0.1:18789/` 不通，则先尝试 `openclaw gateway restart`，若检测到原生 `OpenClaw Gateway` 任务被设成“仅交流电供电时启动 / 切到电池就停止”，则继续直接调用 `C:\Users\GOG\.openclaw\gateway.cmd` 兜底拉起
  - 停机规则：当需要手动关闭掌机上的 OpenClaw 时，先禁用 `OpenClaw Gateway Watchdog` 与 `OpenClaw Gateway`，再停止当前 gateway 实例，避免稍后又被自动拉起
  - 日志位置：`%LOCALAPPDATA%\OpenClaw\watchdog\gateway-watchdog.log`
- Windows SSD 优化（掌机）：
  - 适用机器：掌机（Windows）
  - 系统 / OS：Windows
  - 脚本：`scripts/optimize-ssd-trim-zhangji-windows.ps1`
  - cmd 包装器：`scripts/optimize-ssd-trim-zhangji-windows.cmd`
  - 作用：对掌机这台 Windows 机器的 SSD 卷执行 `Analyze + ReTrim`
  - 注意：需要“以管理员身份运行”
- User systemd units:
  - 适用机器：公司（Linux）/ 其他 Linux 机器
  - 系统 / OS：Linux
  - `~/.config/systemd/user/openclaw-resume-watch.service`
  - `~/.config/systemd/user/openclaw-resume-watch.timer`

- 读取 / 更新总规则：`docs/多机器-读取与更新规则.md`
- 补丁索引：`docs/通用-OpenClaw-补丁注册表.md`
- 升级后重建清单：`docs/通用-OpenClaw-补丁重建清单.md`
- 详细维护说明：`docs/掌机-Windows-OpenClaw-维护说明.md`
- 详细维护说明：`docs/公司-Linux-OpenClaw-维护说明.md`
- Control UI 品牌补丁（当前已用于把左上角 OpenClaw 品牌改成贾维斯风格）：
  - 适用机器：公司（Linux）（脚本本身可复用，但当前部署记录在公司 Linux 机）
  - 系统 / OS：Linux
  - 配置文件：`config/control-ui-branding.json`
  - 应用脚本：`scripts/apply-openclaw-control-ui-branding.py`
  - systemd 自动重应用：`~/.config/systemd/user/openclaw-gateway.service.d/branding.conf`
  - 作用：重复应用 Control UI 左上角品牌名、Logo、浏览器标题、favicon / apple-touch-icon / manifest 名称覆盖，并额外把页面里可见的 `OpenClaw` 文案尽量替换成“贾维斯”，避免 OpenClaw 升级后手工逐个改静态文件
  - 当前也顺手负责两个前台稳定性补丁：
    - 把聊天页“进行中”判断补成同时考虑 `loading / sending / stream / canAbort / queue.length > 0 / session.hasActiveRun / session.status=running`，减少“后台仍在跑，但前台没有任何转圈/进行中信号”的空窗
    - 当 assistant final 为空 / silent 时，不再立刻强制 `chat.history` reload，先压住“前台刚有阶段性内容又被立即清掉”的 ghost/disappear 体感
  - 默认品牌图来源：`avatars/jarvis-neon-20260507.png`
  - 自动生效规则：公司 Linux 机上每次 `openclaw-gateway.service` 启动前，都会先自动执行一次品牌补丁脚本；因此以后只要 OpenClaw 升级后重启 gateway，就会自动重新覆盖
  - 手工用法：`python3 scripts/apply-openclaw-control-ui-branding.py`
- NVIDIA 语音桥（公司 / Linux 机器）：
  - 适用机器：公司（Linux）
  - 系统 / OS：Linux
  - bridge 服务代码：`tools/nvidia-audio-bridge/bridge.py`
  - bridge README：`tools/nvidia-audio-bridge/README.md`
  - 依赖清单：`tools/nvidia-audio-bridge/requirements.txt`
  - systemd 模板：`tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service`
  - gateway 补丁脚本：`scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
  - 当前 bridge venv：`~/.local/share/openclaw-nvidia-audio-bridge-venv`
  - 当前用户态 service：`~/.config/systemd/user/openclaw-nvidia-audio-bridge.service`
  - 用途：让本机 OpenClaw gateway 通过本地 bridge 暴露 NVIDIA 免费 TTS / ASR 路径
  - 快速定位规则：新机器若要复用这一套，先看 README，再按公司 Linux 维护说明执行
- NVIDIA Build 文生图（当前已在公司 / Linux 机器验证打通）：
  - 适用机器：公司（Linux）（其他机器若已配置 `nvidia:default` 也可复用）
  - 系统 / OS：Linux
  - 当前已验证认证来源：`~/.openclaw/agents/main/agent/auth-profiles.json` 里的 `nvidia:default`
  - 关键结论：OpenClaw 的 `nvidia:default` 不只是给文本模型用，也能直接复用到 `https://ai.api.nvidia.com/v1/genai/...` 的 NVIDIA Build 官方文生图接口
  - 当前已打通的官方模型：
    - `black-forest-labs/flux.1-schnell`：适合快速 smoke test / 首次通路验证
    - `black-forest-labs/flux.1-dev`：更适合人物图、真实感、人像比例稳定性
  - 当前已在 NVIDIA Build 页面看到相关条目、但本轮未找到可直接复用的 hosted 公开路由或未打通的模型：
    - `qwen/qwen-image`
    - `qwen/qwen-image-edit`
    - `nvidia/consistory`
  - 当前未查到可直接用的 NVIDIA Build **Gemini 文生图**模型；`build.nvidia.com/google` 这边目前看到的是 `Gemma` / `PaliGemma` / 图像理解类，不是 Gemini image generation
  - 当前已验证的接口坑：
    - `flux.1-dev` 不接受我临时猜加的 `guidance_scale` / `aspect_ratio`，会返回 422
    - `seed` 必须 `< 4294967296`，超出会返回 422
    - 当前这台机器走的 NVIDIA Build **hosted** 路线，对本地图片直传图生图会报 `Expected: example_id, got: base64`；这点不只出现在 `flux.1-dev canny/depth`，连 `flux.1-kontext-dev` 也同样卡住
    - NVIDIA Visual GenAI NIM 文档里虽有 `/v1/images/edits` 与 OpenAI-compatible image generation/editing 说明，但当前 `ai.api.nvidia.com` / `integrate.api.nvidia.com` 上未发现可直接调用的对应 hosted 根路由；至少在本轮认证与路径下，`/v1/images/generations`、`/v1/images/edits` 都返回 404
  - 当前用户偏好（很重要）：在同模型同 seed 的对比里，用户明确更喜欢 **自然直说式 prompt**，不喜欢过于模板化、结构化、像表单一样的 prompt；以后做“真实、好看”的女性人像，优先沿 `FLUX.1-dev + 自然语言描述 + 少模板感` 这条线继续微调
  - 本轮公平测试结论（同一模型 `FLUX.1-dev`、同一 seed、同一主题）：
    - `01-raw`（自然 prompt）= 用户最喜欢
    - `02-claude-office-style` / `03-supercent-style` = 可借结构，但不应替代自然 prompt 主线
  - 本轮找到的外部 skill 候选及适配判断：
    - `claude-office-skills/skills@image-generation`：更适合作为 prompt 工程参考，可与 NVIDIA Build 结合
    - `secondsky/claude-skills@nano-banana-prompts`：对“更像真人摄影的人像 prompt”很有参考价值
    - `eachlabs/skills@portrait-enhancement`：适合借鉴“自然人像更耐看”的修饰方向
    - `supercent-io/skills-template@image-generation`：更偏 Gemini / MCP 思路，不适合直接拿来接 NVIDIA Build
    - `inference-sh*/...@ai-image-generation` / `@flux-image`：后端是 inference.sh，不适合和 NVIDIA Build 做同一条链路混用
  - 当前测试输出目录：`tmp/nvidia-image-test/`
  - 当前三张公平对比图目录：`tmp/nvidia-image-test/comparison-20260511-143556/`
  - 本地 skill 原型：`skills/nvidia-build-image/`
    - 用途：把 NVIDIA Build 的文生图 / 模型切换收成固定入口，并提前预留 self-hosted NIM 的第二后端接口，后续不必每次手写脚本
    - 主脚本：`skills/nvidia-build-image/scripts/nvidia_build_image.py`
    - 当前正式可用主线：`--backend build-hosted`
      - `flux-dev`：主线质量文生图
      - `flux-schnell`：快速 smoke test
      - `flux-klein`：快速切另一条官方文生图模型比较
    - 当前已预留但未在本机实测跑通的第二后端：`--backend nim-http`
      - `flux-dev`：按 Visual GenAI NIM 文档预留 `base/canny/depth`
      - `flux-schnell`：预留基础文生图
      - `flux-kontext`：预留本地图编辑入口
    - 当前明确未打通：Build hosted 路线下的“任意本地图片直传图生图”
    - 当前机器现实边界：本轮检查里 `nvidia-smi` 不可用，因此不能把“这台机器已具备 self-hosted NIM 条件”当成事实
    - 已验证：脚本可直接复用 OpenClaw 的 `nvidia:default`，并已完成 `flux-schnell` 与 `flux-klein` 的最小成功探活；skill 已通过打包校验
    - 打包校验产物：`tmp/skill-dist/nvidia-build-image.skill`
- 临时文件下载分享（公司 / Linux 机器）：
  - 适用机器：公司（Linux）
  - 系统 / OS：Linux
  - 用途：当需要把当前机器上的文件交给宿主机浏览器或其他同网段设备下载时，优先在目标文件所在目录起临时 HTTP 服务，然后直接把完整 URL 发给用户
  - 默认推荐命令：`python3 -m http.server 8765 --bind 0.0.0.0`
  - 推荐做法：在包含目标文件的目录执行；随后把 `http://当前机器IP:8765/文件名` 发给用户
  - 当前公司 Linux 机器兜底 IP：`192.168.233.130`
  - 例如：`http://192.168.233.130:8765/rustdesk-1.4.6-x86_64.exe`
  - 使用场景：用户说“给我一个地址，我去宿主机浏览器里下”或明确表示附件 / 本地路径不好用时
  - **注意**：对 `mp3` / `mp4` / `pdf` 等浏览器可能直接内联打开的文件，如果用户明确想要“直接下载”而不是在线播放/预览，**不要只给 `python -m http.server` 的裸地址**；应优先提供带 `Content-Disposition: attachment` 的临时下载服务地址
  - 这次已验证的坑：浏览器访问普通 `http.server` 的 `mp3` 链接时，可能直接播放而不自动下载
  - 处理方式：为目标文件单独起一个带 `attachment` 响应头的临时 HTTP 服务，再把那个地址发给用户
  - 收尾：文件下载完成后，可结束对应的临时 HTTP 服务进程，避免长期暴露目录
- 浏览器上传到当前机器（公司 / Linux 机器）：
  - 适用机器：公司（Linux）（脚本本身可复用）
  - 系统 / OS：Linux
  - 用途：当用户需要把宿主机浏览器里的本地文件直接拷到当前机器时，优先起一个一次性临时上传页，让用户在浏览器里直接选文件上传
  - 固定脚本：`scripts/openclaw-upload-drop-server.py`
  - 推荐起法：`python3 scripts/openclaw-upload-drop-server.py tmp/upload-drop/inbox <token> 8771`
  - 推荐地址格式：`http://当前机器IP:8771/<token>`
  - 适用场景：用户说“我把文件拷给你”“我从宿主机传给你”“浏览器给你上传文件”这类需求
  - 当前验证通过的典型文件：`voices-v1.0.bin`、`kokoro-v1.0.int8.onnx`
  - 默认规则：以后当用户需要把文件从宿主机/浏览器拷到这台机器时，优先直接用这种临时上传页，而不是先折腾聊天附件、下载地址反向中转或别的更绕的方法
  - 安全做法：使用随机 token 路径、单独 inbox 目录；文件收完后及时关闭上传服务，避免长期暴露
- 视频平台下载工作流（通用）：
  - 适用机器：通用（浏览器参数按当前机器环境调整）
  - 系统 / OS：通用
  - 详细文档：`docs/通用-视频平台下载工作流.md`
  - 最小脚本入口：`scripts/download-platform-video.py`
  - 当前脚本能力：已支持“抖音公开视频页 URL → 提取真实 mp4 → 下载 → ffprobe 校验”；当已拿到多个候选视频页 URL 时，也支持把目标位作为变量选择；当输入作者主页 URL 时，会尝试提取候选列表，但若检测到主页作品流“服务异常”，会主动停止自动选取，避免误把热点/推荐视频当成作者作品；当输入是一段混合文本 / 搜索片段 / 分享文案时，也可自动提取其中的受支持 URL；`--list-only` 结果里会直接给出下一步下载命令，下载结果里也会附带可回放命令
  - 目标位变量：`--pick first|last|random|index:N|video:<id>`
  - 示例：`python3 scripts/download-platform-video.py 'https://www.douyin.com/video/7589959897509317938?source=Googlebot' --browser-args=--no-sandbox`
  - 示例：`python3 scripts/download-platform-video.py --pick=index:2 'https://www.douyin.com/video/第1条?source=Googlebot' 'https://www.douyin.com/video/第2条?source=Googlebot' --browser-args=--no-sandbox`
  - 示例：`python3 scripts/download-platform-video.py --pick=last '这里有两个候选 https://www.douyin.com/video/第1条?source=Googlebot 和 https://www.douyin.com/video/第2条?source=Googlebot' --browser-args=--no-sandbox`
  - 示例：`python3 scripts/download-platform-video.py dummy --input-file ./candidates.txt --pick=index:1 --browser-args=--no-sandbox`
  - 示例：`python3 scripts/download-platform-video.py --list-only --pick=last '这里有两个候选 https://www.douyin.com/video/第1条?source=Googlebot 和 https://www.douyin.com/video/第2条?source=Googlebot'`
  - 示例：`python3 scripts/download-platform-video.py --list-only --pick=last --candidates-out tmp/video-downloads/candidates.txt '这里有两个候选 https://www.douyin.com/video/第1条?source=Googlebot 和 https://www.douyin.com/video/第2条?source=Googlebot'`
  - 示例：`python3 scripts/download-platform-video.py --list-only --pick=last --candidates-out tmp/video-downloads/candidates.txt --report-out tmp/video-downloads/candidates.json '这里有两个候选 https://www.douyin.com/video/第1条?source=Googlebot 和 https://www.douyin.com/video/第2条?source=Googlebot'`
  - 默认规则：以后当用户要求“去抖音/其他平台搜索并下载视频”时，优先先试站内直接路径；若被验证码、登录墙、作品流异常或前端懒加载拦住，立刻切到“外搜定位公开页面 → 拿作者主页 / 公开视频 → 提取真实媒体地址 → 下载并校验”的通用流程，不要原地卡死在站内搜索入口
  - 抖音当前已验证可跑的关键点：
    - 站内搜索可能直接落到验证码中间页
    - 作者主页可打开，但作品流可能返回“服务异常，重新刷新拉取数据”且作品列表 API 响应体为空
    - 可先从公开视频页反查作者主页，再从 `<video>.currentSrc` 直接拿到真实 mp4 地址
    - 最小脚本已能直接处理公开视频页 URL，适合作为“最后一跳下载器”
  - 当前公司 Linux 机 / VM 的浏览器注意事项：若 `agent-browser` 报 `No usable sandbox!`，需先 `agent-browser close --all`，再改用 `agent-browser --args "--no-sandbox" ...`
  - 当前未补齐的缺口：
    - 还没有稳定可复用的抖音登录态 / 账号态浏览器路径
    - 还没有通过安全审查的通用验证码自动化方案
    - `nodriver-kit` 公开来源与安装路径尚未确认，不要在来源不清时盲装
    - 公开搜索引擎在当前链路里也不稳定：百度会进安全验证、搜狗会进反爬页、DuckDuckGo 不稳定、Bing 中文相关性偏弱，暂时不适合直接写死成脚本默认上游
    - 当前脚本还不能直接完成“作者主页 / 关键词搜索 → 自动判断候选列表”整条链路，后续可继续补强
- 双盘空间预检（公司 / Linux 机器）：
  - 适用机器：公司（Linux）
  - 系统 / OS：Linux
  - 背景：当前公司 Linux 机是“根盘 `/` + 数据盘 `/mnt/data`”双盘结构；以后遇到下载大文件、解压模型、批量生成素材、拉大仓库、落大缓存时，不要直接默认写根盘
  - 固定规则：
    - 先预估大小，再执行；默认按 **预计大小 × 2** 估算峰值占用
    - 执行后根盘 `/` 剩余空间不要低于 **8G**，更稳妥是长期留 **10G+**
    - 预计新增占用 **>= 1G** 时，默认优先写到 `/mnt/data/openclaw/download-staging/` 或其他 `/mnt/data/openclaw/...` 目录
    - 只有小而短命的输出，才优先留在根盘/工作区
    - 如果上层路径已被现有工具写死，优先采用“迁到 `/mnt/data` + 原路径放 symlink 回挂”方式，尽量不改主链路调用习惯
  - 预检脚本：`scripts/storage-preflight.sh`
    - 用法：`bash scripts/storage-preflight.sh 1.5G ChatTTS-assets`
    - 用法：`bash scripts/storage-preflight.sh 800M 临时解压包`
  - 当前已落地迁移：
    - `~/.openclaw/workspace/tmp/voice-replies` → `/mnt/data/openclaw/workspace-tmp/voice-replies`
    - `~/.cache/modelscope` → `/mnt/data/openclaw/modelscope-cache`

### Git / GitHub

- 适用机器：通用（其中带“掌机”字样的条目仅适用于掌机（Windows））
- 系统 / OS：通用 / Windows（按各条目说明执行）

- 公司 / Linux 机器：
  - This machine has a GitHub-specific SSH key at `~/.ssh/id_ed25519_github_openclaw`.
  - If plain `git push origin master` hits `Permission denied (publickey)`, use:
    - `GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_openclaw -o IdentitiesOnly=yes' git push origin master`
  - Cause: the default SSH identity selection may miss the GitHub key unless it is specified explicitly or wired through `~/.ssh/config`.

- 掌机（Windows）：
  - Current SSH key path: `~/.ssh/id_ed25519_rog_ally`
  - `~/.ssh/config` now routes `github.com` through `ssh.github.com:443`
  - Reason: this machine can authenticate to GitHub over SSH, but direct port 22 to `github.com` may abort; port 443 to `ssh.github.com` works reliably here
  - Expected result after this change: plain `git push origin master` should work without extra per-command overrides

### CLI-Anything

- Local repository path: `/home/missyouangeled/Desktop/CLI-Anything`
- OpenClaw skill installed at: `~/.openclaw/skills/cli-anything/SKILL.md`
- Local helper command installed at: `~/.local/bin/cli-anything`
  - `cli-anything repo` → print repo path
  - `cli-anything skill` → print installed OpenClaw skill path
  - `cli-anything openclaw` → print suggested OpenClaw usage
- Important: CLI-Anything itself is not a single preinstalled global official executable on this machine. It is mainly a repo containing an OpenClaw skill, Claude Code plugin, OpenCode commands, and generated per-software harnesses.
- Minimal local verification succeeded with the built-in GIMP harness via:
  - `PYTHONPATH=/home/missyouangeled/Desktop/CLI-Anything/gimp/agent-harness python3 -m cli_anything.gimp.gimp_cli --help`
  - `PYTHONPATH=/home/missyouangeled/Desktop/CLI-Anything/gimp/agent-harness python3 -m cli_anything.gimp.gimp_cli project profiles`
- Note: the sample GIMP harness README still references an older module path (`python3 -m cli.gimp_cli`), but the runnable module on this machine is `python3 -m cli_anything.gimp.gimp_cli`.

### Voice replies / TTS

- Local voice-reply helpers live in: `tools/voice-reply/`
- **Simple local fallback** uses `msedge-tts` in user space (no root required)
  - Script: `tools/voice-reply/tts.mjs`
  - Default Chinese voice: `zh-CN-XiaoxiaoNeural`
  - **Current default voice-reply version**: `中文混合模板版本`
    - definition: 以更自然的中文音色为底，再吸收用户最终确认的更真实语气与语速；当前采用的成品模板为“第一条合体版提速 20%”
    - user-selected reference sample: `tmp/voice-replies/zh-hybrid-default-template.mp3`
    - usage rule: for future Chinese voice replies, use this as the default template across voice-reply surfaces unless the user explicitly asks for another voice/template
    - target feel: “第一条的声音 + 第二条的语气和语速”，最终确认版为 `zh-hybrid-noiz-natural-plus20-20260508-1225.mp3`
  - Named fallback preset: **基础女声版本**
    - definition: local `msedge-tts` baseline using `zh-CN-XiaoxiaoNeural`
    - purpose: safety fallback when later experiments sound worse, stiffer, or less natural
    - restore rule: if the user says “恢复到基础女声版本”, revert to this preset directly
    - reference sample chosen by user: `tmp/voice-replies/natural-baseline-xiaoxiao-20260422-164306.mp3`
  - 当前正式默认：`voice-reply-hard-default` 已挂进运行配置，并在当前公司 Linux 机的 gateway 中启用
  - 当前 OpenClaw / Control UI 主线默认：优先 `wav` / 尽量少损，不再把 `mp3` 当主默认
  - Example:
    - `node tools/voice-reply/tts.mjs --text '你好，我是贾维斯。' --out /tmp/jarvis-voice.mp3`
- **Noiz-based helper** for stronger timbre continuity:
  - Script: `tools/voice-reply/noiz-reply.sh`
  - Private default reference clip path: `~/.local/share/openclaw-voice-reply/default-ref.mp3`
  - Presets: `natural`, `gentle`, `bright`, `late-night`
  - Current preferred Chinese template chain:
    - timbre-direction sample: `tmp/voice-replies/zh-msedge-closer-to-nvidia-20260508-1222.mp3`
    - user-final chosen template result: `tmp/voice-replies/zh-hybrid-noiz-natural-plus20-20260508-1225.mp3`
    - stable alias for future reuse: `tmp/voice-replies/zh-hybrid-default-template.mp3`
  - Supports pitch correction after synthesis with formant preservation:
    - `--pitch-semitones -1.5` → lower register slightly while keeping the speaking feel mostly intact
    - implemented with ffmpeg `rubberband` filter and `formant=preserved`
  - Example:
    - `bash tools/voice-reply/noiz-reply.sh --style natural --pitch-semitones -1.5 --text '你好，我在。' --out /tmp/noiz-reply.mp3`
- **Local free XTTS helper** for on-device voice cloning:
  - Script: `tools/voice-reply/local-xtts-reply.sh`
  - Uses local env: `~/.local/share/openclaw-voice-venv311`
  - Default private reference clip path: `~/.local/share/openclaw-voice-reply/default-ref.mp3`
  - Default output path: `tmp/voice-replies/local-xtts-YYYYmmdd-HHMMSS.mp3`
  - Example:
    - `bash tools/voice-reply/local-xtts-reply.sh --text '你好，我在。' --out /tmp/local-xtts.mp3`
- **Chunked voice reply delivery (首句先出，当前会话一次性交付)**:
  - 核心约定：**主会话 ≡ 当前会话**，一次回复送所有分块音频到当前会话
  - Script: `tools/voice-reply/voice-reply-chunked-deliver.sh`
  - 调用现有分块管线，自动把所有分块音频放到一条消息中返回
  - 输出 JSON 的 `agentReply` 字段包含可直接返回当前会话的文本，格式为：
    - `分块文字拼接` + `\n\n[[audio_as_voice]]\nMEDIA:块1\nMEDIA:块2（如有）\n...`
  - Example（agent exec 调用）:
    - `result=$(bash tools/voice-reply/voice-reply-chunked-deliver.sh "回复文本内容")`
    - `agentReply=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['agentReply'])")`
    - 然后将 `$agentReply` 作为当前会话返回内容
  - Output fields:
    - `ok`: true/false
    - `agentReply`: 当前会话可直接返回的文本（含 `[[audio_as_voice]]` + 所有 `MEDIA:`）
    - `chunkCount`: 分块数
    - `mediaPaths[]`: 所有音频路径
    - `audioAsVoice`: 始终为 true（有音频时）
  - 失败时自动回退纯文本（`ok: false`，`agentReply` 为原始文本）
  - 向后兼容：`voice-reply.sh` 仍然是稳定的单块默认入口
- If a helper is used manually, send with:
  - `[[audio_as_voice]]`
  - `MEDIA:/path/to/file.mp3`
- If a helper is used manually, send with:
  - `[[audio_as_voice]]`
  - `MEDIA:/path/to/file.mp3`

### Local audio trimming / reference-voice prep

- User-space ffmpeg helper installed at:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg`
- Reason: this machine has no system `ffmpeg` / `ffprobe`, but Noiz voice cloning rejects reference audio longer than 30s, so local trimming may be needed before upload.
- Example trim command:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg -y -ss 40 -t 10 -i '/path/input.mp3' -vn -acodec libmp3lame -b:a 96k '/path/output.mp3'`

### Kokoro TTS 离线中文语音（2026-05-08 已验证通过）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 模型文件位置：`tmp/kokoro-offline/`
  - `kokoro-v1.0.int8.onnx`（92MB，官方 int8 量化）
  - `voices-v1.0.bin`（28MB，54 个声音全部含中文）
- Python 运行环境：`/tmp/kokoro-test-venv`（Python 3.11，已安装 `kokoro-onnx`, `misaki`, `scipy`, `soundfile`）
- **完全离线**，无网络依赖、无播放设备依赖（纯推理→wav）
- 可用中文声音：`zf_xiaobei` `zf_xiaoni` `zf_xiaoxiao` `zf_xiaoyi`（女声）、`zm_yunjian` `zm_yunxi` `zm_yunxia` `zm_yunyang`（男声）
- 用法（直接 Python）：
  ```python
  from kokoro_onnx import Kokoro
  kokoro = Kokoro(
      model_path='tmp/kokoro-offline/kokoro-v1.0.int8.onnx',
      voices_path='tmp/kokoro-offline/voices-v1.0.bin'
  )
  audio, sr = kokoro.create('你好', voice='zf_xiaoxiao', speed=1.0, lang='cmn')
  ```
- 包装脚本：`tools/kokoro-tts/kokoro-tts.sh`
  - `bash tools/kokoro-tts/kokoro-tts.sh --text '你好' --voice zf_xiaoxiao --out /tmp/out.mp3`
- 试听样本：`tmp/voice-replies/kokoro-zh-official-int8-demo.mp3`
- **默认使用路由**：由主会话决定是否替换当前 Noiz/Edge TTS 管线

### ChatTTS hybrid 中文语音（2026-05-09 起已有正式 stable 入口）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 当前定位：**用户已明确认可这条 ChatTTS hybrid stable 主线，可作为正式的 ChatTTS 本地入口使用；`Noiz` 继续保留为保底版本。**
- 运行环境：`~/.local/share/openclaw-voice-venv311/bin/python3`
- 正式入口（Skill 脚本）：`skills/chattts-stable/scripts/chattts_stable.py`
- 本地便捷包装器：`tools/voice-reply/chattts-stable.sh`
- preset 配置：`skills/chattts-stable/assets/presets.json`
- preset embedding 文件：`skills/chattts-stable/assets/presets/*.spk.txt`
- 当前默认规则：
  - `default` = 当前主线默认音色（model-default）
  - `preset-1` / `preset-2` / `preset-3` = 已保存的可切换候选音色
  - **默认语速 / 节奏**：`tempo=1.10`（2026-05-12 的 A/B 后，用户确认这档整体感觉最好）
  - **当前清晰度优先导出方向**：优先 `wav` / 尽量少损的导出；同一文本下，用户明确觉得无损版清晰度最好
- 推荐运行方式：
  - `python3 skills/chattts-stable/scripts/chattts_stable.py --list-presets`
  - `python3 skills/chattts-stable/scripts/chattts_stable.py --preset default --text '你好，我在。' --out tmp/voice-replies/chattts-stable-default.mp3`
  - `bash tools/voice-reply/chattts-stable.sh --preset preset-2 --text '我给你换一条音色。' --out tmp/voice-replies/chattts-stable-preset2.mp3`
- 历史原型脚本（保留作研发记录，不再作为正式入口）：
  - `tmp/voice-replies/chattts-run-hybrid.py`
  - `tmp/voice-replies/chattts-run-hybrid-stable.py`
  - `tmp/voice-replies/chattts-hybrid-sample-speakers.py`
- hybrid 资产目录：`tmp/voice-replies/chattts-hybrid/asset/`
  - `DVAE_full.pt` / `Vocos.pt` / `Decoder.pt`：来自 `chattts-v011/`
  - `Embed.safetensors` + tokenizer：来自 v3 资产
  - GPT：由 v011 `GPT.pt` 转成 HuggingFace `config.json + model.safetensors`
- 当前关键补丁点（已内置在正式入口里）：
  - 绕过官方 sha256 校验（自组装资产不会匹配原始哈希）
  - `DVAE/DVAEDecoder load_state_dict(..., strict=False)`，容忍缺失 encoder 键
  - tokenizer 从已失效的 `encode_plus()` 改走 `__call__()`，兼容当前 transformers
- 已知限制：
  - **无 encoder**：只能稳定走 decoder 推理路径，不适合参考音频克隆
  - **纯 CPU**：短句可用，但不适合追求实时流式
  - **版本脆弱**：对依赖版本和素材结构敏感，后续升级时要防回归
- 判断规则：
  - 若用户明确要走 `ChatTTS stable` / 本地 ChatTTS / preset 音色切换，优先使用这条正式入口
  - 若要“任意参考音频克隆”或更强 timbre continuity，仍优先评估 `Noiz` / 其他方案，不要误把当前 stable 路线当成通用克隆器

### Local free voice-cloning stack

- `uv` installed in user space at:
  - `~/.local/bin/uv`
- Reason: system Python lacks `pip` / `ensurepip`, so normal `venv` bootstrap is broken on this machine.
- Working local Coqui/XTTS environment path:
  - `~/.local/share/openclaw-voice-venv311`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/openclaw-voice-venv311`
- XTTS model cache path:
  - `~/.local/share/tts`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/tts`
- uv cache path:
  - `~/.cache/uv`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/uv-cache`
- Important compatibility notes:
  - Coqui TTS `0.22.0` does **not** support Python 3.12 on this machine; use Python 3.11 via `uv`.
  - XTTS with current PyTorch/TTS stack needed local compatibility fixes on this machine:
    - pin `transformers==4.41.2` (newer 5.x / late 4.x removed `BeamSearchScorer` expected by XTTS)
    - patch `TTS/utils/io.py` to default `torch.load(..., weights_only=False)` for trusted XTTS checkpoints under PyTorch >=2.6
    - patch `TTS/tts/models/xtts.py` `load_audio()` to use `librosa.load()` instead of `torchaudio.load()` to avoid missing system FFmpeg shared-library issues
- First XTTS model download requires explicit Coqui CPML confirmation:
  - tool recognizes `COQUI_TOS_AGREED=1`
  - do **not** set it unless the user has explicitly agreed to the non-commercial CPML / relevant license terms.
- Current local XTTS smoke test output path:
  - `/home/missyouangeled/.openclaw/workspace/tmp/voice-replies/local-xtts-test.mp3`

### Local-only credential pointers

- SeetaCloud 租用 ChatTTS GPU（westd）：
  - 用途：远端 GPU 环境，准备给 ChatTTS / 更逼真的主会话语音回复使用
  - 非敏感连接标识：`root@connect.westd.seetacloud.com:18786`
  - 敏感凭据本地保存：`credentials/ssh/seetacloud-chattts-westd.md`
  - 安全规则：该文件位于 `credentials/`（gitignored），只在本机保存，不写进 Git 历史
  - 若后续再次卡住需要重连，先从这里定位到本地凭据文件，再 SSH 上去看 `/root/autodl-tmp/voice-lab/install_chattts_gpu.log`

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
