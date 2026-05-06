# HANDOFF.md - Model / Agent Handoff

如果以后更换 AI 大模型、代理、运行时，先读这个文件，再继续工作。

## 当前默认接手方式

## 当前临时高优先级接手任务（掌机 OpenClaw / 微信回复链路）

- 任务目标：让 `掌机（Windows）` 上的 OpenClaw 达到“稳定可用 + 微信插件能稳定回复”，而不只是“能启动”。
- 当前机器：`TABLET-EH5U3CO1` / `掌机（Windows）`
- 远程接管方式：公司 Linux 机通过 SSH 连接 `GOG@100.122.111.6`（密钥：`~/.ssh/id_ed25519_openclaw_handheld`）

### 截至 2026-05-06 晚上的当前结论

1. **启动主故障已部分收敛**
   - 原先最明显的启动卡死与 `github-copilot` 默认模型链路有关。
   - 已在掌机配置 `C:\Users\GOG\.openclaw\openclaw.json` 中改为：
     - `agents.defaults.model.primary = deepseek/deepseek-chat`
     - 移除默认模型里的 `github-copilot/gpt-5.4`
     - `plugins.entries.github-copilot.enabled = false`
     - `plugins.entries.github-copilot.config.discovery.enabled = false`
   - 对应备份：
     - `C:\Users\GOG\.openclaw\openclaw.json.bak-20260506-1505`
     - `C:\Users\GOG\.openclaw\openclaw.json.bak-20260506-1526-stability`

2. **微信插件“收消息”是通的，但“回复执行”会把 gateway 拖挂**
   - 日志已确认微信消息能进入 gateway：有 `inbound message` / `bodyLen=2 hasMedia=false`
   - 紧接着出现 `acpx staging bundled runtime deps`
   - 随后出现 `eventLoopUtilization=1`、`active=1 queued=1`
   - 然后 gateway 卡死，之前会被 watchdog 误判重启
   - 结论：当前主问题不是微信收不到，而是**收到微信后，agent / ACPX / 回复执行链路会把 gateway 卡住**

3. **watchdog 已按用户要求彻底移除**
   - 用户明确要求：先删掉 watchdog，避免它继续掩盖根因
   - 已执行：`scripts/uninstall-openclaw-gateway-watchdog.ps1`
   - 当前 `OpenClaw Gateway Watchdog` 计划任务已不存在
   - 相关记录已写入 `docs/掌机-Windows-OpenClaw-维护说明.md`

4. **当前现场状态并不稳定，且到傍晚又回到了启动失败态**
   - 17:05 之后的日志可见：
     - `loading configuration…`
     - `resolving authentication…`
     - `starting...`
   - 17:24 曾出现：`Gateway restart timed out after 180s waiting for health checks.`
   - 截至本次收口前，`openclaw gateway status --deep` 仍可能返回：
     - `Connectivity probe: failed`
     - `connect ECONNREFUSED 127.0.0.1:18789`
   - 这说明：**去掉 watchdog 后，gateway 本体仍存在独立的启动/运行异常，不是只有微信回复这一层**

### 下一步最该做的事

按优先级继续：

1. **先把“当前为什么连 gateway 都起不来”重新钉死**
   - 重点看 17:05 之后这一段日志到底停在什么阶段
   - 不要再让旧结论（下午一度能起来）覆盖晚上的新现场

2. **把“收到微信后触发 ACPX / 回复链路卡死”的问题继续往下切**
   - 重点看：session 元数据已写入，但真正 session 文件/agent run 是否在落盘前就阻塞
   - 重点源码：`selection-ABXC-aG3.js`、ACPX runtime 相关 dist 文件、bundled runtime staging 相关文件

3. **优先尝试低风险修法**
   - 配置级绕过 > 小补丁 > 大改
   - 优先考虑：把 ACPX/runtime 的初始化从“首条微信消息触发”改成“启动前预热/预展开”，避免把回复主链路卡死

### 相关文档 / 提交

- 维护说明：`docs/掌机-Windows-OpenClaw-维护说明.md`
- 相关提交：
  - `979a206` `docs: 记录掌机 GitHub Copilot discovery 启动修复`
  - `9342661` `docs: 更新掌机稳定配置与微信链路说明`
  - `2c020b2` `docs: 记录掌机 watchdog 卸载状态`

当用户说：
- 继续做
- 继续开发
- 接着上次
- 继续纳达尔星项目
- 恢复星云初始03

默认按下面顺序恢复上下文：

1. 读 `PROJECT_VERSIONS.md`
2. 读 `PROJECT_INDEX.md`
3. 读 `memory/YYYY-MM-DD.md`（今天 + 昨天）
4. 如果在主会话里，再读 `MEMORY.md`
5. 查看当前 Git 分支与最近提交
6. 再开始动代码

## 当前主项目

- 项目名：**纳达尔星项目**
- 当前主锚点版本：**星云初始03**
- 当前主要代码目录：`pulsenest-php/`
- 说明：用户已在 2026-04-03 明确要求“用目前这个版本替换星云初始03”，所以从现在开始，星云初始03 默认指向当前这版更成熟、统一、接近成品验收的结果。

## 跨机器恢复口令

以后如果用户在另一台新装好的 OpenClaw 机器上说：

- **恢复 星云初始03全量工作备份**

默认按下面语义执行：

1. 先把当前工作区 Git 仓库同步到 GitHub 最新 `master`
2. 以当前 `星云初始03` 锚点为准恢复纳达尔星项目
3. 一并恢复已进仓的工作日志与工作记忆，包括：
   - `memory/*.md`
   - `.learnings/*.md`
   - `PROJECT_VERSIONS.md`
   - `HANDOFF.md`
   - 项目代码目录 `pulsenest-php/`
4. 先应用 `openclaw-env/restore-skills.sh`，按清单恢复 Skills 本体并自动套用本仓 overlay
5. 再应用 `openclaw-env/restore-openclaw-env.sh`，安装 hooks / systemd 模板并补齐 `.learnings/`

### 这个“全量工作备份”当前不包含什么

下面这些不应默认宣称“自动同步完成”，因为它们目前没有一起进 GitHub 或依赖本机环境：

- SSH key / GitHub key / agent 状态
- `~/.openclaw/hooks/` 的启用状态本身
- `~/.openclaw/openclaw.json` 等机器本地配置
- systemd 服务、运行中的进程、端口监听状态
- 本机安装的软件包 / Node 依赖的运行态缓存

如果用户要“连机器设置都一起恢复”，那属于下一层任务：需要单独做一套**环境引导 / bootstrap 恢复包**。

## 当前已确认的版本语义

### 星云初始03

这是当前默认继续开发、验收、回退的主锚点。

并且它已经被用户在 2026-04-03 用“当前这个更成熟的版本”正式替换过一次，所以不要再把它理解成更早的星云初始03阶段状态。

如果用户说：
- 恢复星云初始03
- 回到星云初始03
- 继续星云初始03

默认以：
- `PROJECT_VERSIONS.md` 中更新后的「星云初始03」描述为准
- Git 最新已确认提交为准

## 当前系统状态（简版）

当前这套 `pulsenest-php/` 已经不只是论坛原型，而是在往可实际上线运营的论坛系统推进，且到 2026-04-03 晚些时候，已经推进到**接近终检状态**，当前继续做的主要是人工验收级微调与“认真运营中的社区产品”细节补层，已包含：

- 用户系统、登录注册、个人中心、公开用户主页
- 发帖 / 评论 / 回复 / 点赞 / 浏览量
- 帖子状态流：published / pending / hidden / draft
- 后台帖子审核队列与批量审核
- 举报系统：帖子 / 评论举报、后台举报队列、筛选、分页、批量处理、联动处置
- 通知闭环：审核结果、举报处理结果、内容状态变化
- 站点设置中心：登录 / 注册 / 举报 / 只读 / 审核 / 内容阈值
- 内容分发：最新 / 综合热度 / 最多回复 / 最多浏览 / 时间窗口热榜
- 首页运营模块：推荐作者、最高浏览、活跃版块、社区即时快照
- 创作者数据：累计获赞 / 浏览 / 回复 / 最近发帖
- 运营后台看板：新增量 / 积压量 / 活跃版块 / 活跃作者 / 举报分布 / 趋势
- 用户治理系统：治理记录、封禁联动停用、状态流转、高风险用户榜单
- staff 单用户治理档案页：`/user-governance.php?id=...`

## 当前预览方式

当前预览地址：

- 局域网访问：`http://192.168.233.130:8093/`
- 后台：`http://192.168.233.130:8093/admin.php`

当前预览服务已做成常驻：

- systemd 用户服务：`pulsenest-preview.service`
- 启动脚本：`scripts/pulsenest-preview.sh`

常用命令：

```bash
systemctl --user status pulsenest-preview.service
systemctl --user restart pulsenest-preview.service
systemctl --user stop pulsenest-preview.service
```

## 当前用户偏好（重要）

用户明确希望：

- **系统性修改后，要及时提交并推送到 GitHub 备份**

所以当一次改动已经达到“系统性修改”的程度时：

1. 先整理版本锚点 / 说明
2. 再 `git commit`
3. 再推送 GitHub

## 当前 Git 参考

后续继续前，建议先看：

```bash
git log --oneline -5
git status --short
```

## 接手时建议对用户说的话（简版）

你可以直接这么理解任务：

- 继续纳达尔星项目
- 以 `星云初始03` 为当前主锚点
- 在当前工作区和 Git 最新状态上继续开发
- 优先沿着“可实际上线运营的论坛系统”方向推进

## 最近 3 个最自然开发方向

如果用户没有指定下一步，就优先从下面 3 个方向里选一个继续：

1. **终检级真机复看与单点修正**
   - 继续按真实数据量检查首页、提醒中心、帖子详情、作者页、会员中心
   - 只修那些“已经很好但还差一点”的边角
   - 避免再做系统性结构改动

2. **认真运营中的社区产品细节补层**
   - 继续补用户成长感、创作者状态、互动承接、低打扰运营提示
   - 保持轻玻璃 / 假玻璃 / 轻阴影路线
   - 不做重功能，只做产品成熟度补层

3. **上线经营前的稳态准备**
   - 检查图片旧资产、极端数据状态、后台个别旧措辞
   - 补恢复包 / 备份清单 / 环境说明
   - 让这套东西更适合长期维护和跨机器恢复

默认优先级判断：
- 用户如果正在盯页面效果 → 优先做终检级真机复看与单点修正
- 用户如果正在盯‘社区像不像在认真运营’ → 优先做社区产品细节补层
- 用户如果在问备份、恢复、长期维护 → 优先做上线经营前的稳态准备

## 注意

- 除非用户明确要求，不要擅自覆盖 `PROJECT_VERSIONS.md` 里旧版本的历史含义
- 如果用户说“用当前版本替换星云初始03”，才更新对应锚点定义
- 做大改前，优先保留可回退路径
