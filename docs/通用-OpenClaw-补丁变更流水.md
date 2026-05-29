# OpenClaw 补丁变更流水

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：按时间追加的修改 / 补丁 / 功能变更流水

## 用途

这份文档记录**每次实际改了什么**，重点回答：

- 这次改动发生在什么时候
- 改的是功能、补丁、修复还是维护流程
- 影响范围是什么
- 改了哪些文件
- 是否已经同步到补丁注册表 / 重建清单 / 自检清单

它和其它文档的关系：

- `docs/通用-OpenClaw-补丁注册表.md`：记录**正式补丁清单**
- `docs/通用-OpenClaw-补丁重建清单.md`：记录**升级后怎么重建**
- `docs/通用-OpenClaw-升级后自检清单.md`：记录**升级后怎么快速验**
- `docs/通用-OpenClaw-非正式修改备忘录.md`：记录**未进入正式补丁体系的临时/手工/外部修改**
- **本文件**：记录**这次具体动了什么**

## 记录规则

1. 只要发生了实际修改、修补、接链路、打补丁、改脚本、改配置、改文档，就应追加一条流水。
2. 若本次改动已经达到“正式补丁”标准，还要同步更新注册表 / 重建清单 / 必要时更新自检清单。
3. 若只是一次性排查、临时试验、未形成稳定入口，可只记流水，不强行登记为正式补丁；若它对后续排查仍重要，再补进 `docs/通用-OpenClaw-非正式修改备忘录.md`。

---

## 2026-05-20 08:18:44 CST (+08:00) — 建立补丁自动留痕模式

- 类型：process
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 新增补丁变更流水文档，用来按时间记录每次实际改了什么
- 新增 openclaw-change-log 脚本，后续修改任务可直接追加流水
- 把自动留痕规则写进 AGENTS.md / TOOLS.md / MEMORY.md，作为默认工作模式
- 验收 / 验证：
- python3 -m py_compile scripts/openclaw-change-log.py 通过
- 已创建 memory/daily/2026-05-20.md 记录本轮变更
- 相关文件：
- `AGENTS.md`
- `MEMORY.md`
- `TOOLS.md`
- `docs/通用-OpenClaw-补丁变更流水.md`
- `memory/daily/2026-05-20.md`
- `scripts/openclaw-change-log.py`

## 2026-05-20 08:19:16 CST (+08:00) — 补齐 OpenClaw 补丁台账覆盖范围

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：未更新
- 结果摘要：
- 补丁注册表新增 Linux resume-watch、supervisor 状态层、local-health 诊断层、Windows battery policy 等条目
- 补丁重建清单新增 sidecar / unified proxy / supervisor / local-health / resume-watch / Windows battery policy 的重建步骤
- 把推荐重建顺序改成先补自动重打入口，再补 broker / sidecar / proxy，再补各类 watcher/service，最后补机器专用 patch
- 验收 / 验证：
- 已读取 docs/通用-OpenClaw-补丁注册表.md，确认新增条目落盘
- 已读取 docs/通用-OpenClaw-补丁重建清单.md，确认新增步骤与顺序落盘
- 相关文件：
- `docs/通用-OpenClaw-补丁注册表.md`
- `docs/通用-OpenClaw-补丁重建清单.md`

## 2026-05-20 08:24:41 CST (+08:00) — 接入非正式修改备忘录并补入掌机历史修复

- 类型：maintenance
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 新增 docs/通用-OpenClaw-非正式修改备忘录.md，用来记录临时修复、手工补配、外部修改等未进入正式补丁体系的条目
- openclaw-change-log 脚本新增 memo 子命令，可直接追加非正式修改备忘录
- 已补入掌机微信二维码登录 Content-Length 兼容修复、微信通道手工补配回写、watchdog 保持卸载状态三条历史记录
- 验收 / 验证：
- python3 -m py_compile scripts/openclaw-change-log.py 通过
- 已读取 docs/通用-OpenClaw-非正式修改备忘录.md，确认三条条目落盘
- 相关文件：
- `AGENTS.md`
- `MEMORY.md`
- `TOOLS.md`
- `docs/通用-OpenClaw-补丁变更流水.md`
- `docs/通用-OpenClaw-非正式修改备忘录.md`
- `memory/daily/2026-05-20.md`
- `scripts/openclaw-change-log.py`

## 2026-05-21 10:12:53 CST (+08:00) — Control UI 模型选择下拉修复

- 类型：patch
- 适用范围：公司-Linux
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：不适用
- 结果摘要：
- 修复 Control UI 中模型选择下拉列表选择后不生效的问题。在 branding override 中新增 WebSocket 拦截 + capture 阶段事件监听，确保 change/input 事件能直接触发 sessions.patch。
- 验收 / 验证：
- JS 语法验证通过；branding re-apply 成功；Gateway 日志会话正常
- 相关文件：
- `scripts/apply-openclaw-control-ui-branding.py`

## 2026-05-21 13:28:35 CST (+08:00) — 修复 Control UI 模型选择器因品牌覆盖JS劫持导致不工作

- 类型：patch
- 适用范围：公司-Linux
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：不适用
- 结果摘要：
- 从 jarvis-branding-override.js 及其生成脚本 apply-openclaw-control-ui-branding.py 中移除模型选择器劫持代码（~59行），该代码在 capture 阶段重复拦截 change/input 事件，与 Control UI 自带的模型切换处理冲突导致下拉列表切换失效，严重时触发页面刷新。
- 验收 / 验证：
- agent-browser 验证：下拉列表可展开、模型可正常切换、无页面刷新。JS/Python 语法检查通过。
- 相关文件：
- `scripts/apply-openclaw-control-ui-branding.py`

## 2026-05-21 15:33:39 CST (+08:00) — Control UI favicon 替换为 J.A.R.V.I.S. 蓝色环形 logo

- 类型：patch
- 适用范围：公司-Linux
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：不适用
- 结果摘要：
- Firefox 快捷方式图标从红色龙虾换为 J.A.R.V.I.S. 蓝色同心圆: 新增 SVG favicon, 正确尺寸 PNG/ICO, 更新品牌化脚本覆盖所有 favicon 格式
- 验收 / 验证：
- favicon.svg/favicon-32.png/favicon.ico 已正确部署到 dist/control-ui/, 脚本无 SyntaxWarning, Firefox 清除缓存后应显示新图标
- 相关文件：
- `scripts/apply-openclaw-control-ui-branding.py`

## 2026-05-21 17:42:53 CST (+08:00) — SOUL.md 语言锁定规则前移加强 — 双语硬约束防止模型切换后回复英文

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 把语言强制规则从 SOUL.md 底部移至文件顶部（第一个可见段落），做成中英双语硬约束，并在底部精简为引用顶部规则。防止切换模型（DeepSeek/GLM/Kimi/NVIDIA等）后部分模型忽略底部指令而输出英文。
- 验收 / 验证：
- SOUL.md 第一段即为中英双语语言锁定规则；原底部规则已改为引用顶部
- 相关文件：
- `SOUL.md`

## 2026-05-22 08:06:48 CST (+08:00) — 新增 SKILL_CATALOG.md + 换模型强制阅读机制

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 创建 SKILL_CATALOG.md（30个Skill按7类分组），AGENTS.md 启动序列新增第7步强制阅读，HANDOFF.md 顶部新增换模型第一步索引
- 验收 / 验证：
- AGENTS.md 启动序列含第7步、HANDOFF.md 顶部含 SKILL_CATALOG.md 索引、SKILL_CATALOG.md 内容完整
- 相关文件：
- `SKILL_CATALOG.md`

## 2026-05-22 08:20:30 CST (+08:00) — 新增统一日报采集层（跨模型对话记录聚合）

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 创建 scripts/aggregate-daily-transcript.py + systemd timer（每5分钟），自动扫描所有模型的当天 session JSONL，汇集成 memory/daily/YYYY-MM-DD-transcript.md；AGENTS.md 第5步扩展为同时读取统一日报，换模型后不再丢失当天对话上下文
- 验收 / 验证：
- timer enabled+active，script 首跑成功（27条消息），transcript.md 已生成，journalctl 日志正常
- 相关文件：
- `scripts/aggregate-daily-transcript.py`

## 2026-05-22 08:39:16 CST (+08:00) — 新增补丁自动修复脚本 openclaw-patch-repair.py

- 类型：patch
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 对标 openclaw doctor --fix，14条自定义补丁一键检查+修复，支持 --check/--repair/--force/--dry-run/--target；修完自动复查
- 验收 / 验证：
- --check 模式通过：12/14 正常（2条FAIL为预存问题），修复动作注册完整
- 相关文件：
- `scripts/openclaw-patch-repair.py`

## 2026-05-22 09:18:33 CST (+08:00) — 引入 obra/superpowers 工程方法论

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 将 obra/superpowers 的 brainstorming → writing-plans → subagent-driven-dev → verification → finishing 五阶段流程适配到 OpenClaw，新增 docs/methodology/superpowers-adapted.md，AGENTS.md 修改类任务入口已接入引用
- 验收 / 验证：
- 方法论文档可读，AGENTS.md 引用可追溯，git 已推送
- 相关文件：
- `docs/methodology/superpowers-adapted.md`

## 2026-05-22 09:22:04 CST (+08:00) — 监工系统 × 方法论深度整合

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 将监工服务/监工分身与 obra/superpowers 五阶段方法论做深度配合：每阶段明确监工行为、阶段③执行期给出四种分支处理流程、附命令速查和阶段边界动作模板
- 验收 / 验证：
- 方法论文档可读，五阶段联动表完整，快速参考卡片含监工切换步骤
- 相关文件：
- `docs/methodology/superpowers-adapted.md`

## 2026-05-22 09:35:27 CST (+08:00) — 提炼上下文工程精华（context-optimization/degradation/multi-agent）

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 从 muratcankoylan/agent-skills-for-context-engineering 提炼三个核心文档：上下文优化（四层策略+结构化压缩）、上下文退化诊断（5种模式+修复）、多Agent架构（三种模式+15x成本+六种失败模式），全部适配OpenClaw现有体系
- 验收 / 验证：
- 三份文档可读，AGENTS.md引用已接入，git已推送
- 相关文件：
- `docs/methodology/context-optimization.md`

## 2026-05-22 09:42:13 CST (+08:00) — 上下文优化规则细化：加入场景判断标准

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 按用户指示：日常聊天可压缩（保留大意即可）、工作/工程/决策/修改尽量不要压缩、拆分身按现有AGENTS.md场景判定表执行。更新context-optimization.md末尾执行规则节
- 验收 / 验证：
- 文档已更新，git已推送
- 相关文件：
- `docs/methodology/context-optimization.md`

## 2026-05-22 10:14:28 CST (+08:00) — 方法论审查修复：4严重矛盾+8逻辑漏洞+术语统一

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 对S1-S4四个严重矛盾、Y1-Y8八个逻辑漏洞进行系统性修复：联动表对齐AGENTS.md（监工分身触发条件）、场景切换压缩衔接规则、阈值统一、用户中断处理、两级审查明确主会话执行、分批执行规则、poisoning截断后重跑验证、术语统一等。四份文档交叉引用已补全
- 验收 / 验证：
- git已推送，4份文档交叉一致，联动表与AGENTS.md判定表口径统一
- 相关文件：
- `docs/methodology/superpowers-adapted.md`

## 2026-05-22 10:28:39 CST (+08:00) — 方法论三审收口：措辞级修复

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 快速参考卡片补分批执行步骤；multi-agent-patterns补分批规则交叉引用。三轮审查+烟测后达到9.5+/10
- 验收 / 验证：
- 文档交叉一致，快速参考完整
- 相关文件：
- `docs/methodology/superpowers-adapted.md`

## 2026-05-22 10:51:10 CST (+08:00) — 新增主会话响应性看门狗

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：不适用
- 结果摘要：
- 独立于模型的响应性检测：每15秒检查dashboard session transcript，若用户消息超30s无回复则向主会话注入提醒，60s升级紧急提醒
- 验收 / 验证：
- systemctl --user status openclaw-responsiveness-watch.timer 确认运行；--print-human确认正常检测
- 相关文件：
- `scripts/openclaw-responsiveness-watch.py`

## 2026-05-22 11:00:17 CST (+08:00) — 响应性看门狗接入升级后自检体系

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：已更新
- 结果摘要：
- 补丁注册表+重建清单+升级后自检脚本三条均已加入 watchdog，更新后自检会自动验证 timer 是否在位
- 验收 / 验证：
- grep确认自检脚本含responsiveness-watch.timer；注册表成功push
- 相关文件：
- `scripts/openclaw-post-upgrade-self-check.py`

## 2026-05-22 11:45:55 CST (+08:00) — 修复终审9个磕碰（实际6个缺项+3个已在位）

- 类型：patch
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 退化5模式统一量化+Agent自检规则+掌机模型差异+跨机器分身协议+场景插问答题标准+TOOLS边界说明；#1阈値#2引用#5sessions.json已在位
- 验收 / 验证：
- git push 成功；5文件60行增改；无语法错误
- 相关文件：
- `docs/methodology/context-degradation.md`

## 2026-05-25 09:24:01 CST (+08:00) — ChatTTS 音色一致性：全链路固定随机种子 seed=1910

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：不适用
- 结果摘要：
- 在 chattts_stable.py、chattts_daemon.py、chattts-on-demand.sh、chattts_voice_reply.py 四层全部添加 --seed 1910 默认值，确保同一 preset=default + 同一文本 = MD5 完全一致的声音输出
- 验收 / 验证：
- 两条相同文本/same preset 的语音 MD5 完全一致
- 相关文件：
- `skills/chattts-stable/scripts/chattts_stable.py`

## 2026-05-25 14:56:32 CST (+08:00) — 开机自动体检 + 自愈（boot-health-check）

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：不适用
- 结果摘要：
- 创建 openclaw-boot-health-check 脚本 + systemd oneshot 服务，开机后自动扫描 3 个核心服务、3 个定时器、磁盘/内存/端口，缺失服务自动拉起；BOOT.md 集成并在启动消息中回报体检结果
- 验收 / 验证：
- 手动运行全绿通过 ✅，提交并推送到 GitHub
- 相关文件：
- `scripts/openclaw-boot-health-check.py`

## 2026-05-26 08:53:27 CST (+08:00) — 修复 systemd 启动顺序循环依赖

- 类型：fix
- 适用范围：公司-Linux
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 去掉 openclaw-infos-handle-sidecar.service 的 After=default.target，改为 After=network-online.target，消除与 gateway(unified-proxy 的 default.target 三方循环。sidecar 重启后正常运行，healthz 双路径验证通过。
- 验收 / 验证：
- systemctl restart sidecar 后 ActiveState=active；curl :18790/healthz 和 :18788/healthz 均返回 ok
- 相关文件：
- `tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
- `~/.config/systemd/user/openclaw-infos-handle-sidecar.service`

## 2026-05-26 08:55:33 CST (+08:00) — 新增自动化临时文件清理（语音/输出/通用tmp）

- 类型：feature
- 适用范围：公司-Linux
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 新增 openclaw-cleanup-temp.sh + systemd service/timer。每30分钟自动清理：超过4小时的语音回复 mp3/wav、超过4小时的 infos-handle outputs、超过24小时的通用 tmp 旧文件。首次运行清理了27个过期文件(34.57 MB)。
- 验收 / 验证：
- systemctl --user show openclaw-cleanup-temp.timer 状态 active/enabled；手动运行脚本正常
- 相关文件：
- `scripts/openclaw-cleanup-temp.sh`
- `tools/openclaw-cleanup/openclaw-cleanup-temp.service`
- `tools/openclaw-cleanup/openclaw-cleanup-temp.timer`

## 2026-05-26 08:58:12 CST (+08:00) — local-health-watch 新增磁盘空间监控

- 类型：feature
- 适用范围：公司-Linux
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 在 openclaw-local-health-diagnose.py 新增 collect_disk_usage()，监控 / 和 /mnt/data 两个挂载点。使用率 ≥80% warn、≥90% critical；根盘余量低于 8G 安全线时也会 warn。已接入 issue 检测、canvas HTML 卡片、self-help actions 和 broker 数据流。
- 验收 / 验证：
- 脚本编译通过；运行后 report disk.status=ok；根盘 75.8%(11.8G) 未触发告警；/mnt/data 39.1% 正常
- 相关文件：
- `scripts/openclaw-local-health-diagnose.py`

## 2026-05-26 08:59:31 CST (+08:00) — 修复 frontstage-recovery 对 NO_REPLY 的假阳性误报

- 类型：fix
- 适用范围：公司-Linux
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 在 assistant_turn_missing_visible_text 检测中增加 rawText==NO_REPLY 的判断：当 assistant turn 的 rawText 为 NO_REPLY 时，不再上报异常，因为这是预期的静默回应。同时修复了两处中文引号导致的 SyntaxError。
- 验收 / 验证：
- 脚本编译通过；运行后输出 OK - latest assistant turn 为 NO_REPLY（预期静默回应），不视为异常
- 相关文件：
- `scripts/openclaw-frontstage-recovery-watch.py`

## 2026-05-26 09:07:07 CST (+08:00) — Watcher 整合第一步：前台保护器 + 生命周期维护器

- 类型：refactor
- 适用范围：公司-Linux
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 8→4 watcher 整合第一步：新增 frontstage-guardian（合并 recovery+responsiveness，每20s）和 lifecycle-maintainer（合并 daily-transcript+cleanup，每5min，cleanup每6次触发）。禁用旧 timer：frontstage-recovery-watch、responsiveness-watch、daily-transcript-aggregator、cleanup-temp。原脚本保留未删，可随时回退。
- 验收 / 验证：
- 新 timer active/enabled；旧 timer disabled；frontstage-guardian 运行输出 OK；lifecycle-maintainer 运行输出 OK
- 相关文件：
- `scripts/openclaw-frontstage-guardian.py`
- `scripts/openclaw-lifecycle-maintainer.py`
- `tools/openclaw-watchers/openclaw-frontstage-guardian.service`
- `tools/openclaw-watchers/openclaw-frontstage-guardian.timer`
- `tools/openclaw-watchers/openclaw-lifecycle-maintainer.service`
- `tools/openclaw-watchers/openclaw-lifecycle-maintainer.timer`

## 2026-05-26 09:08:28 CST (+08:00) — Watcher 整合第二步：健康采集器（合并 supervisor + broker + local-health）

- 类型：refactor
- 适用范围：公司-Linux
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 新增 health-collector（每60s 轻量层：supervisor 刷新 + broker rebuild；每5次/5min 完整层：追加 local-health 诊断）。禁用旧 timer：supervisor-watch、frontstage-broker-rebuild、local-health-watch。原脚本保留未删。
- 验收 / 验证：
- health-collector 运行输出 OK；新 timer active/enabled；3 个旧 timer disabled
- 相关文件：
- `scripts/openclaw-health-collector.py`
- `tools/openclaw-watchers/openclaw-health-collector.service`
- `tools/openclaw-watchers/openclaw-health-collector.timer`

## 2026-05-26 09:27:21 CST (+08:00) — Watcher 整合第五步：新增任务调度器（Task Scheduler）

- 类型：feature
- 适用范围：公司-Linux
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 新增 task-scheduler（每30s 扫描 runs.sqlite，自动开关监工、检测静默/僵尸任务、回报前台）。端到端验证：手动关监工→spawn 任务→调度器自动检测 active tasks→auto-enable supervisor 成功。排除主会话持久 running 任务，避免误判。
- 验收 / 验证：
- task-scheduler timer active/enabled；端到端 auto-enable 验证通过；5 个 watcher timer 全部正常
- 相关文件：
- `scripts/openclaw-task-scheduler.py`
- `tools/openclaw-watchers/openclaw-task-scheduler.service`
- `tools/openclaw-watchers/openclaw-task-scheduler.timer`

## 2026-05-26 09:34:24 CST (+08:00) — 任务调度器阶段2+3：清理自动化 + 智能调度

- 类型：feature
- 适用范围：公司-Linux
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 阶段2：接入 openclaw tasks maintenance --apply（每 10 周期/5min 自动执行 gateway 任务维护）、tasks audit（error 级别审计+通知）、旧 subagent/dashboard 会话清理。阶段3：并发控制（超过 4 个 active 任务告警）、近期失败检测（10min 窗口）+去重通知。run count 持久化，维护按周期频率触发。
- 验收 / 验证：
- 编译通过；dry-run 验证 would-run-maintenance/would-audit-tasks/would-scan-sessions 均触发；live 验证 maintenance-applied 成功
- 相关文件：
- `scripts/openclaw-task-scheduler.py`

## 2026-05-26 10:51:23 CST (+08:00) — 系统审查后修复：watcher PATH + infos-handle healthz + yt-dlp

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：不适用
- 结果摘要：
- 修复4个watcher服务的PATH环境变量缺失、infos-handle的healthz查询支持、安装yt-dlp
- 验收 / 验证：
- 所有watcher timer active且最后一次运行SUCCESS；healthz查询经代理返回200；yt-dlp 2026.03.17可用
- 相关文件：
- `scripts/openclaw-infos-handle.py`

## 2026-05-26 10:58:05 CST (+08:00) — 新建升级记录文档：跨模型可读的升级全过程记录

- 类型：docs
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 创建 docs/通用-OpenClaw-升级记录.md，记录升级 #1 (2026.5.22) 完整经过：版本变化、4个问题根因与修复、验收、经验教训。接入自检清单和 TOOLS.md 索引。
- 验收 / 验证：
- 文档 7.4KB，结构清晰（基本信息/升级内容/问题详情/修复/验收/当前状态），已关联自检清单和 TOOLS.md
- 相关文件：
- `docs/通用-OpenClaw-升级记录.md`

## 2026-05-26 11:34:16 CST (+08:00) — 新增卡住会话检测器 (Stuck Session Detector)

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 检测网关日志中 long-running session 警告（activeWorkKind=model_call + recovery=none），通过 health-collector 每 60s 自动检测，发现主会话阻塞时通过 broker 向前台报告
- 验收 / 验证：
- 脚本可正常解析并检测到主会话卡住：blockedMain=true，集成到 health-collector 的轻量层
- 相关文件：
- `scripts/openclaw-stuck-session-detector.py`

## 2026-05-26 17:27:06 CST (+08:00) — 2026-05-26 系统优化与自动恢复（截图卡死修复+Watcher PATH修复+升级记录体系）

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：已更新
- 结果摘要：
- 修复截图发送导致主会话卡死的根因（视觉模型上下文溢出+长运行会话阻塞队列），实现卡住会话自动检测与分级恢复，修复所有 watcher systemd PATH缺失，建立升级记录文档体系
- 验收 / 验证：
- 截图发送不再卡死主会话，5个watcher全部正常触发，自动恢复已实战验证，升级记录文档已接入自检和启动流程
- 相关文件：
- `scripts/openclaw-stuck-session-detector.py`

## 2026-05-27 08:48:36 CST (+08:00) — 将 GitHub Copilot GPT-5.5 加入 OpenClaw 可用模型列表

- 类型：maintenance
- 适用范围：公司（Linux）
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 在 allowlist 模式下新增 github-copilot/gpt-5.5，保留当前默认模型不变。
- 验收 / 验证：
- openclaw config validate 通过。
- openclaw models status --json 已显示 allowed 包含 github-copilot/gpt-5.5。
- 相关文件：
- `/home/missyouangeled/.openclaw/openclaw.json`
- `/home/missyouangeled/.openclaw/workspace/docs/plans/2026-05-27-gpt55-copilot-openclaw-config.md`

## 2026-05-27 11:28:50 CST (+08:00) — 将 thinkingDefault 设为 off 防止思考链路泄露到前台

- 类型：patch
- 适用范围：公司（Linux）
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 将 agents.defaults.thinkingDefault 设定为 off，确保任何模型（包括 NVIDIA/DeepSeek/Copilot 等）不在前台输出 thinking 内部内容，杜绝中英混合泄露。Gateway 重启后生效。
- 验收 / 验证：
- openclaw config validate 通过。
- openclaw gateway 日志中已显示 config change detected: agents.defaults.thinkingDefault。
- 相关文件：
- `/home/missyouangeled/.openclaw/openclaw.json`

## 2026-05-27 16:33:39 CST (+08:00) — 关闭 DeepSeek V4 Pro 原生 reasoning 防止 thinking 泄露（第二层修复）

- 类型：patch
- 适用范围：公司（Linux）
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：已更新
- 结果摘要：
- 上次 thinkingDefault:off 只关了 OpenClaw 层面的 thinking，但 DeepSeek V4 Pro 模型的 reasoning:true 仍会在输出中生成 thinking 块。本次直接修改插件 plugin.json 将 reasoning 设为 false，并建立自动重应用脚本。配合 thinkingDefault:off 形成双层防护。
- 验收 / 验证：
- 插件文件已修改：reasoning: false。
- 补丁重应用脚本已创建：patches/auto-reapply/deepseek-v4-pro-reasoning-off.sh。
- 相关文件：
- `/home/missyouangeled/.npm-global/lib/node_modules/openclaw/dist/extensions/deepseek/openclaw.plugin.json`
- `/home/missyouangeled/.openclaw/workspace/patches/auto-reapply/deepseek-v4-pro-reasoning-off.sh`

## 2026-05-28 08:42:52 CST (+08:00) — 批量卸载：OpenCLI + Google Chrome + browser-automation + npm缓存清理；新建安装注册表

- 类型：cleanup
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 卸载 OpenCLI(26MB)、Google Chrome(423MB)、browser-automation软链接、npm缓存(527MB)，共释放约1GB根盘空间。保留 agent-browser。新建 docs/install-registry.md 作为工具/Skill安装卸载的统一注册表，并更新 AGENTS.md / MEMORY.md 引用。
- 验收 / 验证：
- 根盘从78%降至76%；所有残留已清理验证通过
- 相关文件：
- `docs/install-registry.md`

## 2026-05-28 09:00:35 CST (+08:00) — 卸载系统自带游戏：麻将/扫雷/数独 + 残留依赖

- 类型：cleanup
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 卸载 gnome-mahjongg(4.9M) + gnome-mines(1.7M) + gnome-sudoku(2.0M)，含自动清理残留库 libgnome-games-support/libqqwing，共释放约9.3MB
- 验收 / 验证：
- apt list --installed 确认三个包已不在；/usr/games 目录下对应二进制已清除
- 相关文件：
- `docs/install-registry.md`

## 2026-05-28 09:16:03 CST (+08:00) — 卸载非必要桌面应用：Onboard/Pluma/PowerStats/Printers + 残留

- 类型：cleanup
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 卸载 onboard(25M) + pluma(27M) + gnome-power-manager(0.3M) + system-config-printer(1.9M) 及 9 个残留依赖，共释放约62MB
- 验收 / 验证：
- dpkg -l 确认全部已清除
- 相关文件：
- `docs/install-registry.md`

## 2026-05-28 09:21:39 CST (+08:00) — 卸载 LibreOffice Draw/Math（连带 Impress）+ 残留

- 类型：cleanup
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 卸载 libreoffice-draw(12M) + libreoffice-math(2M) + libreoffice-impress(连带移除) 及 6 个残留依赖，共释放约31MB。保留 Writer + Calc 核心组件。
- 验收 / 验证：
- dpkg -l 确认 draw/math/impress 已清除；writer/calc 正常保留
- 相关文件：
- `docs/install-registry.md`

## 2026-05-28 15:41:12 CST (+08:00) — 系统审计修复：health-collector三态退出/QMD重建/ChatTTS资产确认

- 类型：bugfix
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 修复health-collector对supervisor exit2的误判(改为三态OK/⚠/❌)；QMD索引1300块→重建验证119文件；ChatTTS资产确认在tmp/下完整。systemd不再因降级状态误触FAILURE。
- 验收 / 验证：
- health-collector exit0 on degraded; QMD index 119/119; ChatTTS 7files 325MB
- 相关文件：
- `scripts/openclaw-health-collector.py`

## 2026-05-29 10:57:05 CST (+08:00) — QMD 语义搜索排查 → 切换到 builtin + github-copilot embeddings

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- QMD vsearch 在无 GPU 机器上因需要加载 1.2GB LLM 做查询扩展，导致 120s 超时或 OOM；切到 OpenClaw builtin 引擎 + github-copilot 云端 embedding，向量搜索 4-6s 完成，语义召回正常。
- 验收 / 验证：
- memory_search 验证：121 文件/1493 chunk，搜索耗时 4-6s，vectorScore 0.54-0.63
- 相关文件：
- `/home/missyouangeled/.openclaw/openclaw.json`
