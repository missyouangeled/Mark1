# OpenClaw 非正式修改备忘录

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：未进入正式补丁体系的临时修复 / 手工改动 / 外部修改备忘录

## 用途

这份备忘录记录那些**对后续排查很重要，但暂时还不适合直接登记为正式补丁**的内容，例如：

- 一次性手工修复
- 只在外部插件 / 外部环境里发生过的修改
- 当前故意不做成默认自动触发的维护动作
- 尚未收敛成稳定实现入口的实验性改动

它和正式补丁体系的区别：

- 正式补丁 → 进 `补丁注册表 / 重建清单 / 必要时的自检清单`
- 非正式修改 → 先进这份备忘录，后续若收敛成熟，再升级为正式补丁

## 记录规则

1. 只有当一条修改对后续排查/恢复仍有价值，但又还不适合登记为正式补丁时，才写这里。
2. 写入时要明确：当前状态、为何未纳入正式补丁、以及后续若再出问题应先看哪里。
3. 若后来它已经具备稳定入口、最小验收、可重复恢复方案，应把它升级进正式补丁体系。

---

## 2026-05-20 08:23:45 CST (+08:00) — 掌机微信二维码登录阶段 Content-Length 兼容修复

- 类型：external-change
- 适用范围：掌机（Windows）
- 当前状态：已在用
- 未纳入正式补丁原因：
- 修复发生在 openclaw-weixin 插件侧与运行环境兼容层，不是当前 workspace 内已收敛好的正式补丁入口
- 当前更像历史兼容修复记录，尚未沉淀成通用可重放的正式补丁链路
- 后续排查 / 恢复提示：
- 若掌机再次出现二维码登录阶段 fetch failed / UND_ERR_INVALID_ARG / invalid content-length header，先看 docs/掌机-Windows-OpenClaw-维护说明.md 对应章节
- 确认当前 openclaw-weixin 插件版本与二维码请求逻辑是否又重新带回手工 Content-Length 头
- 备注：
- 这条修复曾把模糊的 fetch failed 收敛成更明确的 invalid content-length header 兼容问题
- 相关文件：
- `docs/掌机-Windows-OpenClaw-维护说明.md`

## 2026-05-20 08:23:45 CST (+08:00) — 掌机微信通道手工补配回写

- 类型：manual-fix
- 适用范围：掌机（Windows）
- 当前状态：已在用
- 未纳入正式补丁原因：
- 这是当时为绕过 size-drop 保护导致的自动写回失败而做的手工配置补齐，不是正式自动修复入口
- 后续若要升级为正式补丁，需要先把 openclaw.json 回写失败的根因收敛成稳定方案
- 后续排查 / 恢复提示：
- 若扫码成功后微信仍未真正进入 ON / OK / configured，先检查 docs/掌机-Windows-OpenClaw-维护说明.md 里的手工补配章节
- 优先核对 channels.openclaw-weixin、账号启用项以及 gateway 重启后的 provider 启动日志
- 备注：
- 这条记录对应的是“扫码成功但通道没真正拉起”的那次修复
- 相关文件：
- `docs/掌机-Windows-OpenClaw-维护说明.md`

## 2026-05-20 08:23:45 CST (+08:00) — 掌机 watchdog 当前保持卸载状态

- 类型：maintenance-note
- 适用范围：掌机（Windows）
- 当前状态：已停用
- 未纳入正式补丁原因：
- watchdog 当前被明确视为临时兜底，不应默认作为正式稳定性方案写进补丁注册表
- 用户已经明确要求优先追根因，而不是靠自动拉起掩盖问题
- 后续排查 / 恢复提示：
- 若掌机后续再次掉线，先按 docs/掌机-Windows-OpenClaw-维护说明.md 做状态诊断，不要先默认重装 watchdog
- 只有用户明确要求恢复兜底保活时，再使用 install-openclaw-gateway-watchdog 脚本
- 相关文件：
- `docs/掌机-Windows-OpenClaw-维护说明.md`
- `scripts/install-openclaw-gateway-watchdog.ps1`
- `scripts/uninstall-openclaw-gateway-watchdog.ps1`

## 2026-05-25 16:34:28 CST (+08:00) — 新增：硬件审查前置规则 — 问"能不能用"自动审查

- 类型：manual-fix
- 适用范围：通用
- 当前状态：已记录
- 未纳入正式补丁原因：
- 用户要求以后每次问某个工具/方案能不能用，默认先做硬件审查（CPU/GPU/RAM/磁盘/网络/API/依赖）+ 查已有规定，再给结论，避免再出现没查就断言"无头"的情况
- 后续排查 / 恢复提示：
- MEMORY.md / AGENTS.md 中新增规则，今后自动触发
- 相关文件：
- `MEMORY.md`

## 2026-05-26 10:51:29 CST (+08:00) — watcher systemd 服务 PATH 环境变量修复

- 类型：config-fix
- 适用范围：通用
- 当前状态：已修复
- 未纳入正式补丁原因：
- systemd 环境缺少 ~/.npm-global/bin，导致 openclaw CLI 不可用；已更新 frontstage-guardian/health-collector/task-scheduler/lifecycle-maintainer 四个 service 文件
- 后续排查 / 恢复提示：
- 若 OpenClaw 升级后 PATH 变化，检查 ~/.config/systemd/user/*.service 的 Environment=PATH 行
- 相关文件：
- `~/.config/systemd/user/openclaw-*.service`

## 2026-05-26 11:34:22 CST (+08:00) — health-collector 集成 stuck-session-detect 检测项

- 类型：manual-fix
- 适用范围：通用
- 当前状态：已生效
- 未纳入正式补丁原因：
- health-collector 轻量层新增第 3 个检测项，每 60s 自动检测卡住会话
- 后续排查 / 恢复提示：
- 检测到 stuck-session 时查看状态文件 ~/.local/state/openclaw/stuck-session-detector/status.json
- 相关文件：
- `scripts/openclaw-health-collector.py`

## 2026-05-27 08:48:36 CST (+08:00) — GPT-5.5 已加入可用模型列表但尚未切为默认模型

- 类型：maintenance-note
- 适用范围：公司（Linux）
- 当前状态：已在用
- 未纳入正式补丁原因：
- 本次目标是让 GPT-5.5 随时可切换使用，不主动改变当前默认模型与现有工作流。
- 后续排查 / 恢复提示：
- 若后续希望全局默认改为 GPT-5.5，可再执行 openclaw models set github-copilot/gpt-5.5 并做真实回包验收。
- 相关文件：
- `/home/missyouangeled/.openclaw/openclaw.json`

## 2026-05-27 11:28:58 CST (+08:00) — thinkingDefault off 基于用户反馈临时紧急修复

- 类型：manual-fix
- 适用范围：公司（Linux）
- 当前状态：已应用
- 未纳入正式补丁原因：
- 用户反馈在 NVIDIA nemotron 模型下中英混合的 thinking 内容泄露到前台，影响正常对话体验。此为紧急修复，不是上游架构问题，后续 OpenClaw 升级后需确认未被覆盖。
- 后续排查 / 恢复提示：
- 若升级后 thinking 再次泄露，可重新执行：openclaw config set agents.defaults.thinkingDefault off && openclaw gateway restart
- 相关文件：
- `/home/missyouangeled/.openclaw/openclaw.json`
