# PLANS.md — 方案存档

各类方案、调研结论、技术决策的归档。每次有新方案，先写到这里，再在 MEMORY.md 挂索引。

> 边界规则：本文件只存放"方案 / 决策 / 调研结论"，不承担系统配置说明、维护步骤、脚本运行说明、日常执行记录的归档职责。这些内容必须分别写入对应的 `docs/` / `TOOLS.md` / 脚本头部 / `memory/daily/`，避免与方案存档互相干涉。

---

## 2026-05-19：broker / infos-handle v1 收口说明

### 定位

当前这条线的正式定位是：

- **broker** = sidecar 数据层 + compat 壳
- **infos-handle** = 正式请求 / 信息处理层
- **sidecar** = infos-handle 的轻量 HTTP / SSE 运输层
- **unified proxy** = Gateway + infos-handle 的统一入口层

它已经不再是“半成品探索”，而是一个**可用、可测、可续接、可升级后自检**的内部统一信息系统。

### v1 现在明确算完成的范围

按 2026-05-19 当前停点，下面这些已经属于 **v1 已完成范围**：

1. **broker 数据层已成型**
   - `events.jsonl`
   - `manifest.json`
   - `views/frontstage.json`
   - `views/health.json`
   - `views/tasks.json`
   - `views/recovery.json`
   - `views/snapshot.json`

2. **infos-handle 正式主入口已成型**
   - `handle --request-file` + contract helper 是唯一推荐主路径
   - query / compat / caller 都已围绕这条路径收口

3. **多种输出形态已成型**
   - `text`
   - `json`
   - `image.summary-card.v3`（默认）
   - `image.summary-card.v2`（兼容）
   - `audio.local-tts.v2`

4. **sidecar 已成型**
   - `GET /healthz`
   - `GET /v1/query/<kind>`
   - `POST /v1/handle`
   - `GET /v1/artifacts/<artifactRef>`
   - `GET /v1/events/stream`

5. **统一入口已成型**
   - `:18788` → unified proxy
   - `:18789` → Gateway
   - `:18790` → infos-handle sidecar

6. **鉴权闭环已完成**
   - localhost 直连 sidecar 可免鉴权（兼容本机 consumer）
   - 远程/LAN sidecar 访问需 Bearer token
   - 经 unified proxy 进入时也会按原始客户端 IP 判定，不再出现 localhost 绕过

7. **基础限流已完成**
   - sidecar 对非 localhost 客户端已有远程 rate limit

8. **安装/验证入口已成型**
   - `scripts/apply-openclaw-frontstage-broker-data.py`
   - `scripts/apply-openclaw-infos-handle-gateway-proxy.py`

9. **升级后自检链已成型**
   - `BOOT.md` 启动时自动触发
   - `scripts/openclaw-post-upgrade-self-check.py` 已覆盖：
     - branding
     - broker snapshot-first
     - infos-handle contract
     - infos-handle snapshot summary
     - infos-handle sources latest
     - infos-handle sidecar live
     - unified proxy verify
     - sidecar/proxy service 状态
     - broker / infos-handle / caller / recovery 回归

### v1 明确不包含的范围

下面这些**不属于 v1 已完成范围**：

1. **公网正式服务版**
   - 当前没有实际域名时，不算公网正式交付
   - 但 HTTPS/TLS 切换入口已经备好

2. **多租户 / 多用户边界**
   - 当前仍是单机 owner/operator 语义优先

3. **更强的入口层防护**
   - 目前有 sidecar 远程 rate limit
   - 但 unified proxy 自己还不是完整的公网防护层

4. **把 sidecar / infos-handle 变成 OpenClaw 主聊天链硬依赖**
   - 当前仍坚持 sidecar / broker 弱依赖路线

5. **把这条线扩成“另一个 Gateway”**
   - infos-handle 仍是窄职责信息处理层，不接管主会话状态机

### 完成度判断

如果按**本机 / LAN / 内部 consumer** 口径判断：

> **v1 已完成，可以正式收口。**

如果按**公网正式服务 / 多租户产品化** 口径判断：

> **v1 不覆盖这部分；这属于 v2+ 方向。**

### 以后默认怎么理解

后续再提到这条线时，默认按下面口径理解：

> **broker / infos-handle 当前已经是“完整的内部版统一信息系统”，而不是半成品。**
> **升级后默认会自动自检并尽量保持可用；若未来 OpenClaw 大版本改动过大，则按自检结果决定是否进入补丁修复。**

### v2 之后若要继续，优先顺序

1. 公网正式域名 / HTTPS 实装
2. unified proxy 更强的入口层限流 / 防护
3. 更明确的对外 consumer 接入文档
4. 如果真的有必要，再讨论更远的多租户 / 产品化边界

---

## 2026-05-19：infos-handle 增强轮 4 方向收口

### 结论

四个方向全部完成，全量测试通过：

1. **image/audio v2 handler**：
   - image: `image.summary-card.v2` (cardVersion=3)、per-panel severity、tone accent bars、status badges、dashboard 布局（真实 broker panel key: frontstage/health/supervisor/recovery）
   - audio: `audio.local-tts.v2` (textPlanVersion=3)、自然口语 preamble + conversational connectors
   - 新增 `--cleanup-artifacts-older-than-hours N` 过期 artifact 清理

2. **consumer 收口**：所有数据 producer 已迁到 contract helper；`supervisor-subagent` send-frontstage 走 chat.inject 直投，属管理层 CLI，无需迁移

3. **Control UI consumer 推**：sidecar-first + snapshot-fallback 链路完整；apply/verify 全链通过（含 image artifact transport）

4. **sidecar 加固**：MAX_BODY_BYTES=256KB (413)、SSE 连接计数 (healthz sseConnections)、thread-safe counter

### 边界

- 不改主入口、不拆聊天主链、不改 gateway 主链接口
- 小步 contract-first 路线持续

---

## 2026-05-18:infos-handle phase2 最小增强落点

### 结论

这一轮继续沿 `broker sidecar 数据层 + infos-handle 正式请求层` 主线小步推进,当前最小可交付落点定为:

1. **richer image/audio 仍留在 `scripts/openclaw-infos-handle.py` 现有 preview handler 内**
   - `image` 不新开入口,只把单条 summary-card 提升成 richer multi-panel SVG preview,并稳定回传 `layout / panels / badge / footerLines`
   - `audio` 不碰主聊天链,只补稳定 spoken-text plan(`textPlanVersion / strategy / segmentCount / segments / estimatedDurationSeconds`)后再走现有 local TTS
   - `handle --request-file` 继续是唯一推荐主路径

2. **Control UI 直连 infos-handle 采用"sidecar 优先 + snapshot 静态回退"**
   - 不硬拆现有 broker snapshot 入口
   - live branding override 只补最小直连字段:`infosHandleSummaryHref / infosHandleContractHref / infosHandleSseHref`
   - health dock 优先读本地 infos-handle sidecar,失败再回退 `jarvis-frontstage-snapshot.json`

3. **HTTP/SSE 先做独立最小 sidecar,不改 gateway 主链**
   - 独立脚本:`scripts/openclaw-infos-handle-sidecar.py`
   - 最小 HTTP:`GET /v1/query/<kind>`、`POST /v1/handle`
   - 最小 SSE:`GET /v1/events/stream`,先提供只读状态流,足够给 Control UI 做轻量刷新
   - 仓库内同步补正式落点:`tools/openclaw-infos-handle-sidecar/README.md`、`tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`

### 边界

- 这不是 broker compat 壳的新主逻辑
- 这也不是 gateway 主链接口定稿
- 后续若继续扩,优先补 richer renderer / consumer,而不是回退正式入口

## 2026-05-13:前台独立监工方案(脚本监工 + 前台状态面板)

### 背景

当前"监工分身"规则的目标是:

- 主会话保持正常聊天
- 后台任务继续执行
- 用户前台在 3 分钟内至少能看到一次状态

但这几天的实际体验证明:**只靠 AI 分身监工并不够硬**。一旦共享链路卡住,前台仍会出现"半天没反应"的体感。用户进一步明确提出一个更合理的方向:

> 把监工做成预先写好的独立脚本,只负责盯后台任务并定时返回状态,而不是继续依赖 AI 分身临场记得去补报。

### 核心结论

这个方向是对的,而且比当前"规则 + 分身兜底"更可靠。

但 2026-05-14 用户又把使用方式进一步收敛成一个更清晰的模型:

> 监工要做成一种**可开关的服务能力**。简单工作时可以不开;复杂工程任务默认开启;用户也可以随时明确要求我开启或关闭。

因此现在的结论变成:

- **监工服务** 是用户可控制的工作模式,不再等同于"每次工作都隐式常开"
- **脚本监工** 负责独立观察和状态判断
- **监工分身** 只在服务开启、且任务确实需要时才作为补充出口/协作层出现
- 它们共同组成"监工服务",但**不等于一上来就做成 OS 级常驻守护进程**
- 它仍然**不能绝对保证**在任何故障下都把聊天消息发进当前对话框
- 因此最佳落地仍然是三层组合:
  - **脚本监工**(独立观察与判断)
  - **前台状态面板**(独立展示链路)
  - **聊天消息插播 / 监工分身**(补充出口,不再是唯一状态出口)

### 监工服务语义(2026-05-14 更新)

#### 用户视角

- **监工服务关闭**:
  - 简单工作默认不启用监工脚本、不拉起监工分身
  - 我正常直接处理任务
- **监工服务开启**:
  - 遇到复杂工程、长耗时排错、多步骤修改、可能阻塞前台的任务时,默认启用监工链路
  - 监工链路至少包括脚本状态输出;是否再拉起监工分身取决于当时任务是否需要聊天插播/额外协作
- **显式覆盖**:
  - 用户说"开监工服务"→ 本轮或后续工作按开启处理
  - 用户说"关监工服务"→ 停止自动启用,必要时也收掉已在位的监工链路

#### 系统视角

监工服务至少需要区分这几类状态:

- `disabled`:服务关闭,不自动监工
- `armed`:服务已开启,但当前无复杂后台任务,仅保留可随时接管的能力定义
- `active`:服务已开启,且已有监工对象,脚本正在产出状态
- `stopping`:收到关闭指令,正在收尾并退出监工链路

### 方案目标

#### 目标

1. 主会话前台不再长期静默得像掉线
2. 后台任务即使卡住,也能被非 AI 逻辑识别出来
3. 用户无需等待聊天消息,也能在前台看到系统是否还活着
4. 监工规则从"靠模型记得补报"升级成"程序化检查 + 固定状态输出"
5. 简单工作默认不增加额外监工开销,复杂工程默认可自动进入监工模式
6. 用户可以明确开/关监工服务,而不是只能靠我临场猜测

#### 非目标

1. 不追求"无论任何故障都一定能发聊天消息"
2. 第一版不急着做成高风险、系统级、永远常驻的守护服务
3. 不引入会明显增加 token 消耗的频繁消息轰炸

### 为什么它会比现状更好

当前后台任务分身的"独立性"主要体现在**执行独立**,即:

- 后台可以跑
- 前台不一定被直接占住

但当前监工失败的关键在于:

- 定时补状态仍有一部分依赖 AI 临场执行
- 没有真正独立的状态源
- 前台过度依赖"聊天消息成功送达"这一个出口

脚本监工能补上前两点:

- 不靠记忆
- 不靠模型回合
- 定时判断更稳定
- 更适合盯"任务是否活着 / 是否有新进展 / 是否超时"

### 推荐架构

#### 第 1 层:脚本监工(独立观察层)

单独常驻或定时运行的本地脚本,职责仅包括:

- 扫描当前是否存在后台任务 / 监工对象
- 读取任务进度来源
- 判断是否超时、卡住、异常结束、完成
- 把结果写成结构化状态文件

推荐状态文件路径:

- `~/.local/state/openclaw/supervisor-status.json`

可选附加日志:

- `~/.local/state/openclaw/supervisor-events.log`

#### 第 2 层:前台状态面板(独立展示层)

Control UI / 本地健康入口不只显示 Gateway/网络/模型,也读取监工状态文件,展示:

- 当前是否有后台任务
- 最近一次进度时间
- 当前状态:运行中 / 可能卡住 / 异常 / 已完成
- 若卡住,卡在多久、任务标签是什么

建议展示形态:

- 顶部工具栏附近的小状态点 / 小卡片
- 或并入现有"本地健康"入口卡片

#### 第 3 层:聊天消息插播(补充出口)

保留聊天插播,但只在这些时机发:

- 任务开始
- 首次超过静默阈值(例如 3 分钟)
- 明确异常结束
- 最终完成

不再把"聊天消息一定发得出来"当作唯一兜底机制。

### 监工脚本最小职责

#### 输入

脚本至少要观察这些来源中的一部分:

1. `sessions.json` / 当前运行态索引
2. 后台任务 session 的 `jsonl` / `trajectory`
3. 任务标签(label)与 session id
4. 最近更新时间 / 最近新增消息时间
5. 必要时的 gateway 本地可达性

#### 判断规则

最小规则建议:

- **idle**:无后台任务
- **running**:后台任务存在,且最近 N 秒内有新进展
- **stalled**:后台任务仍存在,但超过阈值没有新进展
- **failed**:任务异常结束 / 空返回 / 明显错误
- **done**:任务已正常完成,等待短暂展示后收口

默认阈值建议:

- 30 秒:脚本检查周期
- 3 分钟:首次"无可见产出"阈值
- 10 分钟:强提醒阈值(更明显标黄/标红)

### 状态文件建议格式

```json
{
  "checkedAt": "2026-05-13T18:10:00+08:00",
  "hasActiveTask": true,
  "status": "stalled",
  "taskLabel": "download-platform-video",
  "taskSessionId": "xxxx",
  "lastProgressAt": "2026-05-13T18:06:20+08:00",
  "silentSeconds": 220,
  "detail": "后台任务 3 分钟 40 秒无新进展",
  "recommendation": "继续等待 / 人工介入 / 检查网关 / 检查任务日志"
}
```

### 前台展示建议

前台不需要展示很多细节,重点是让用户一眼知道"系统还活着没"。

建议文案:

- `无后台任务`
- `后台运行中`
- `后台 3 分钟无新进展`
- `后台任务异常结束`
- `后台任务已完成`

颜色建议:

- 绿:running / done
- 黄:stalled
- 红:failed
- 灰:idle

### 为什么不能只靠聊天消息

因为聊天消息出口仍依赖共享链路:

- Gateway
- 当前渠道投递
- 前端 WebSocket
- 当前会话事件分发

这些链路如果整体卡住,脚本即使知道状态,也不一定能把消息推进聊天框。

所以真正能改善"像掉线"的核心是:

> **让前台页面能独立读到状态,而不是只等一条聊天消息。**

### 实施阶段建议

#### Phase 0:先定义"监工服务"的开关语义

目标:先把"什么时候开、什么时候不开、用户如何显式控制"做成明确规则。

产物:

- 监工服务状态定义:`disabled / armed / active / stopping`
- 简单工作 vs 复杂工程的默认判定口径
- 显式开关指令的优先级规则

验收:

- 用户能一句话开启或关闭监工服务
- 简单工作默认不自动启用
- 复杂工程默认自动进入监工模式

#### Phase 1:先做脚本状态文件

目标:把"独立观察 + 独立判断"做出来,作为监工服务的硬状态底座。

产物:

- `scripts/openclaw-supervisor-status.py`
- `~/.local/state/openclaw/supervisor-status.json`

验收:

- 服务开启且有后台任务时能写出 running/stalled/done/failed
- 无后台任务时能稳定回 idle
- 服务关闭时不误报 active
- 不依赖模型即可工作

#### Phase 2:前台显示接入

目标:Control UI 可见性独立兜底。

产物:

- 在现有本地健康卡片里增加"后台任务状态 / 监工服务状态"
- 或新增一个很轻的小角标/小卡片

验收:

- 不发聊天消息,用户也能看到后台是否卡住
- 3 分钟无新进展时前台明显可见
- 能区分"服务已关闭"和"服务开启但当前无任务"

#### Phase 3:监工分身 / 聊天插播收敛

目标:把 AI 分身降到补充层,只在服务开启且确有需要时参与。

产物:

- 开始 / 首次超时 / 异常 / 完成 时插播
- 仅在复杂任务或需要额外协作时拉起监工分身
- 去掉高频重复提醒

验收:

- 前台状态面板稳定
- 聊天消息显著减少但仍保留关键通知
- 关闭监工服务后,不再自动拉起监工分身

### 风险与边界

#### 能解决的

- 监工不再依赖 AI"记得补一句"
- 3 分钟无产出规则可以真正程序化
- 前台不再完全依赖聊天消息知道系统状态

#### 不能绝对解决的

- Gateway 整体卡死
- Control UI 自身前端彻底挂掉
- 页面完全断开到连状态 JSON 都读不到
- 宿主机 / 本机操作系统层面故障

所以它不是"绝对万能监工",而是把现有兜底从**软规则**升级成**硬状态链路**。

### 当前默认开工顺序(2026-05-14 更新)

现在继续这条时,默认按下面顺序开工:

1. 先补齐"监工服务"的开关语义与默认判定
2. 实现 `scripts/openclaw-supervisor-status.py`
3. 先只输出 JSON,不先碰聊天插播
4. 用已有后台任务或模拟任务验证 `idle / running / stalled / failed / done`
5. 再把它接进 Control UI 现有"本地健康"入口
6. 最后再决定聊天消息插播 / 监工分身保留到什么程度

### 当前决策

- 这条方案已确认继续推进
- 方案已从"默认常驻式监工思路"更新为"可开关的监工服务"
- 简单工作默认可不开监工服务
- 复杂工程默认开启监工服务
- 用户可以显式要求开启或关闭监工服务
- 当前优先按 **Phase 0 → Phase 1 → Phase 2** 开始做
- 温度链路暂不继续,避免干扰主稳定性问题

---

## 2026-04-29:云服务器部署方案

### 用途
让 OpenClaw(贾维斯)24小时在线,随时可访问。

### 推荐服务商对比

| 服务商 | 推荐配置 | 新用户最低价 | 续费参考价 | 特点 |
|--------|---------|------------|-----------|------|
| **腾讯云** | 轻量 2核2G 3M/40G | **68元/年**(1.4折) | ≈99元/年 | 微信登录方便,活动多 |
| **腾讯云** | 轻量 2核2G 4M/50G | **99元/年**(续费同价) | 99元/年 | **推荐:新老用户同价,续费不涨价** |
| **阿里云** | ECS 2核2G 3M/40G | **99元/年** | 99元/年 | 新老用户都能买,续费不涨价 |
| **阿里云** | 轻量 2核2G 3M/50G | **61元/年** | ≈99元/年 | 新用户轻量版 |
| **腾讯云** | 秒杀 4核4G 3M/40G | **38元/年**(0.5折) | 约99-188元/年 | 新用户限一台,配置翻倍 |

> ⚠️ 以上价格来自2026年4月腾讯云、阿里云官方活动页面。实际价格以购买时为准。

### 推荐方案(按情况)

**如果你是腾讯云新用户:**
→ 先抢 4核4G 38元/年 秒杀(0.5折),配置翻倍,一年才38块。
→ 或者直接选 2核2G 68元/年,如果觉得4核用不上。

**如果你不是新用户(阿里云/腾讯云都行):**
→ 选 **99元/年 续费同价** 的套餐,两家的差别不大。
→ 阿里云:ECS 2核2G 3M/40G,99元/年,续费不涨。
→ 腾讯云:轻量 2核2G 4M/50G,99元/年,续费同价。

### 配置建议
- **CPU**:2核足够(OpenClaw不重,模型调远程API)
- **内存**:2GB(已够用,4核4G的秒杀套餐更富余)
- **系统盘**:40-60GB SSD
- **带宽**:3-4Mbps(够用了)
- **流量**:300-500G/月(日常聊天用不完)
- **系统**:Ubuntu 22.04 / 24.04
- **不需要 GPU**:所有模型调远程 API,不需要显卡

### 部署步骤
```bash
# 1. 服务器上装 Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs

# 2. 安装 OpenClaw
npm install -g openclaw

# 3. 创建配置目录
mkdir -p ~/.openclaw

# 4. 从旧机器传导出包过来(scp / U盘 / 任何安全方式)
scp openclaw-setup-export-20260429.tar.gz 服务器IP:~/

# 5. 解压还原
tar xzf openclaw-setup-export-*.tar.gz -C ~/
cp config/openclaw.json ~/.openclaw/
cp -r credentials/* ~/.openclaw/credentials/

# 6. 克隆 workspace
git clone git@github.com:missyouangeled/test-git.git ~/.openclaw/workspace

# 7. 启动并设置开机自启
openclaw gateway start
openclaw gateway enable  # 开机自启
```

### 访问方式
- **WebChat**:浏览器打开 `http://服务器IP:18789`
- **微信通道**:配置好微信后,手机微信直接聊
- **手机浏览器**:和电脑一样

### 每月成本
- 新用户第一年:**最低38元(腾讯云秒杀)或61-68元**
- 平均年成本:**99元/年 ≈ 8元/月**
- 日常耗电:**0元(云服务器电费包含在套餐内)**

### 迁移保障
换机器后 workspace 从 GitHub 同步,我用 AGENTS.md → MEMORY.md → PLANS.md 的链路找回所有方案和记忆。

---

## 2026-04-29:ROG 掌机(Windows)部署方案

### 用途
在 ROG 掌机的 Windows 系统上运行 OpenClaw,通过手机热点联网,实现随身携带、随时在线。

### 方案选择

| 方案 | 说明 | 推荐度 |
|------|------|:----:|
| **方案A:原生 Windows+PowerShell** | 直接 Windows 上装,简单轻量 | ⭐ 推荐 |
| **方案B:WSL2 子系统** | 开 Linux 虚拟机跑,更稳定但耗电 | 可选 |

> 对于 ROG 掌机,建议走方案A(原生),不需要额外开虚拟机拖累续航。

### 方案A:原生 Windows 部署步骤

#### 第一步:安装 Node.js
1. 打开浏览器,访问 https://nodejs.org
2. 下载 **Node.js 22.x LTS**(Windows .msi 安装包)
3. 双击安装,一路下一步(全部默认勾选即可)
4. 安装完成后,打开 **PowerShell**(右键开始菜单 → Windows PowerShell)
5. 验证安装:
```powershell
node --version   # 应该显示 v22.x.x
npm --version    # 应该显示 10.x.x
```

#### 第二步:安装 OpenClaw
```powershell
npm install -g openclaw@latest
```

#### 第三步:同步 workspace 和配置
先配好 GitHub SSH 密钥:
```powershell
# 1. 检查是否有 SSH 密钥
ls ~\.ssh\id_ed25519*

# 2. 如果没有,生成一个
ssh-keygen -t ed25519 -C "你的GitHub邮箱"

# 3. 查看公钥,添加到 GitHub
cat ~\.ssh\id_ed25519.pub
# → 复制输出,去 GitHub → Settings → SSH and GPG keys → New SSH key
```

然后克隆 workspace:
```powershell
# 克隆记忆库
git clone git@github.com:missyouangeled/test-git.git %USERPROFILE%\.openclaw\workspace
```

#### 第四步:恢复配置
从旧机器通过 `scripts/export-setup.sh` 导出 tar.gz,传到 ROG 掌机解压:
```powershell
# 将 openclaw-setup-export-20260429.tar.gz 放到 C:\ 下
# 在 PowerShell 中:
cd $env:USERPROFILE\.openclaw
# 解压(Windows 可以用 7-Zip 或 tar 命令)
tar -xzf C:\openclaw-setup-export-20260429.tar.gz
# 然后复制配置和凭据
Copy-Item config\openclaw.json .\
Copy-Item credentials\* .\credentials\ -Recurse
```

#### 第五步:启动
```powershell
openclaw gateway start
```

#### 第六步:设置开机自启
1. 创建一个 `.bat` 或 `.ps1` 脚本,内容:
```powershell
start /B openclaw gateway start
```
2. 按 `Win + R`,输入 `shell:startup`
3. 把脚本放进启动文件夹

### 手机热点联网方案

**问题**:手机热点的 IP 是动态的,且 ROG 掌机在手机内网下。

**方案一(推荐):Tailscale(免费)**
1. 在 ROG 掌机装 Tailscale:https://tailscale.com/download
2. 在手机也装 Tailscale
3. 两台设备登录同一个账号 → 组成虚拟局域网
4. ROG 掌机的 Tailscale IP 固定,手机通过那个 IP:18789 访问

**方案二(简单):局域网直连**
- 手机开热点,ROG 掌机连上
- 在 ROG 掌机上运行 `ipconfig` 查看 IP
- 其他设备(或你自己)通过 `http://ROG-IP:18789` 访问
- 但手机热点断开后 IP 会变

**方案三(稍复杂):内网穿透(frp/ngrok)**
- 适合需要在外网长期稳定访问的场景
- 需要一个有公网IP的服务器做跳板

### 续航建议
- ROG 掌机插电时跑 OpenClaw 最合适
- 电池模式下 OpenClaw 本身负载低,几乎不影响续航
- 需要长时间外出时,可以用手机远程连接

### 和云服务器方案的对比
| | ROG 掌机方案 | 云服务器方案 |
|------|------------|------------|
| 成本 | 0元(已有硬件) | 约99元/年 |
| 续航 | 需插电或省电模式 | 24小时在线 |
| 便携 | 随身带 | 固定节点 |
| 网络 | 依赖手机热点 | 固定公网IP |
| 部署门槛 | 需 Windows 操作 | 需 Linux 基础 |

---

## 2026-04-30:双机协同推荐方案(公司机主脑 + 掌机远程入口)

### 用途
解决这样一个长期使用场景:
- 公司 Linux 机器和平时随身带的 ROG 掌机可能同时开机
- 用户希望在掌机上也能"叫到公司那台贾维斯"替自己做事
- 同时避免出现两个长期并行、彼此记忆分叉的独立实例

### 核心结论
**最推荐的架构不是"双主脑互相喊话",而是:**

- **公司机**:唯一主 Gateway / 主脑
- **掌机**:远程控制入口(移动驾驶舱)
- **掌机本地 OpenClaw**:保留,但默认只作备用 / 救援 / 实验实例,不作为日常主脑

一句话概括:
> 不是"让掌机上的我去转述给公司上的我",而是"让掌机直接连上公司上的同一个我"。

### 为什么推荐这套
OpenClaw 的会话、状态、长期上下文、任务与路由,本质上都归 **Gateway** 持有。
因此若公司机和掌机各自长期跑一个独立主实例,后续极易出现:

- 会话分叉
- 记忆理解不同步
- 后台任务不在同一边
- 文件修改和命令执行位置混乱
- 用户自己也逐渐分不清"刚才是哪边的我答应过这件事"

所以从长期维护成本、使用一致性、记忆连续性来说,**单主脑优于双主脑**。

### 推荐架构

#### 第一层:公司机主脑(必须)
公司机作为唯一主 Gateway,负责:
- 主会话
- 长期记忆与 workspace 规则加载
- 后台任务、cron、分身、状态
- 公司本地项目、脚本、日志、文件访问
- 你日常真正使用的"贾维斯"身份连续性

可理解为:**真正住着贾维斯的大脑**。

#### 第二层:掌机远程入口(强烈推荐)
掌机主要承担:
- 远程打开 Control UI / WebChat
- 在外面继续同一条主会话
- 给公司机上的贾维斯下命令、追结果、继续追问

可理解为:**随身携带的控制台 / 驾驶舱**。

#### 第三层:掌机本地备用实例(可选)
掌机本地仍可保留一个 OpenClaw,但默认定位应是:
- 公司机掉线时的临时替补
- 外出完全连不到公司机时的离线兜底
- 测试新规则、新配置、新 profile 的实验实例

可理解为:**救援副机**,而不是第二个长期主脑。

### 日常使用体验(目标状态)

#### 场景A:人在公司
直接在公司机上与贾维斯对话,正常本地使用。

#### 场景B:人不在公司,只带掌机
在掌机上打开远程界面,此时看到的并不是"掌机版另一个贾维斯",而是**公司机上持续运行的同一个贾维斯**。

这时你在掌机上说:
- 去某个公司项目目录看一下
- 帮我跑一下构建
- 查一下日志
- 改某个文件
- 继续一个后台任务

这些动作的真实执行位置都是**公司机**。

### 网络与连接方式建议

#### 首选:Tailscale / 私有远程访问
推荐原因:
- 公司机位置固定,掌机会在公司 / 家里 / 手机热点之间切换
- 需要一条稳定、低折腾、适合移动场景的私有连通方式
- 比直接暴露公网端口更稳、更安全

#### Gateway 暴露原则
推荐尽量保守:
- 优先使用安全内连思路(如 loopback + 安全转发 / 私有网络)
- 让掌机安全访问公司机 Gateway
- 不建议把公司机 Gateway 粗暴裸露到公网

### 掌机本地 OpenClaw 的定位建议
掌机已经装好的 OpenClaw 不算白装,但后续定位建议明确化:

#### 推荐定位
- 默认不用它承担日常主脑职责
- 保留为备用 / 救援 / 实验用途

#### 不推荐定位
- 不建议让它和公司机长期并行,形成两个平级主脑
- 不建议以后主要靠"掌机上的我去跨 Gateway 转述给公司上的我"作为常态工作流

### 为什么不推荐"双主脑互相喊话"
这条路理论上可以绕,但不是最自然的主路径,长期会带来:
- 双边上下文分裂
- 文件和执行位置容易误判
- 任务、提醒、后台状态分散
- 调试和维护成本明显上升

**与其让两个独立实例互相转述,不如让掌机直接接入公司主脑。**

### 未来可扩展方向
在"公司机唯一主脑"稳定后,可以再考虑第二阶段增强:
- 掌机不仅是远程入口,也把部分本地能力作为外围能力挂给主脑
- 后续再评估是否需要 node / 外围执行端能力
- 如需保留掌机本地实例,建议使用独立 profile / 独立端口 / 独立状态目录,明确其为备用而非主脑

### 最终推荐版(当前拍板)

#### 主架构
- **公司机:唯一主 Gateway**
- **掌机:远程访问公司机上的同一个贾维斯**
- **网络:优先 Tailscale / 私有远程方案**
- **掌机本地 OpenClaw:保留,但只作备用 / 救援 / 实验用途**

#### 排名结论
1. **最推荐**:公司机主脑 + 掌机远程入口
2. **增强版**:公司机主脑 + 掌机远程入口 + 掌机救援实例
3. **次选**:掌机主脑 + 公司机执行端
4. **不推荐**:公司机与掌机双主脑长期并行并互相喊话

### 决策摘要
对当前用户场景,最稳、最像"真正只有一个持续存在的贾维斯"的做法是:

> **让公司机上的贾维斯成为唯一主脑,掌机随时远程连进去直接使唤它。**

---

## 2026-04-30:三设备协同方案(微信总控 + 掌机对话 + 多设备执行)

### 用途
解决这样一个进一步扩展的场景:
- 用户不只拥有"公司机 + 掌机"两台设备,而是可能有第三台、第四台设备
- 用户希望用**微信**作为总控入口,随时下发任务
- 同时希望在**掌机**上继续和贾维斯实时聊天
- 还希望把不同任务定向交给不同设备执行,例如:
  - "三号设备给我找几部电影"
  - "公司设备继续工作"
  - 而掌机上的对话仍继续进行,不被后台调度打断

### 核心结论
**可以实现,但前提不是"多个独立贾维斯互相协作",而是:**

- **一个主脑**:负责统一理解、拆任务、调度设备、回收结果
- **多个入口**:微信、掌机、将来可能还有网页或别的入口
- **多个执行端**:公司机、三号设备、将来更多设备

一句话概括:
> **微信负责发号施令,掌机负责实时对话,多个设备负责干活,但背后仍然是同一个贾维斯在统筹。**

### 最推荐的总体架构

#### 1. 唯一主脑
仍建议放在**公司机**(或未来一台长期稳定在线的固定主机)上。

主脑负责:
- 统一会话与长期记忆
- 解析来自不同入口的命令
- 判断任务该交给哪台设备
- 创建后台任务 / 分身 / 定向执行
- 回收执行结果并按规则回传到微信、掌机或当前对话

#### 2. 微信:总控入口
微信最适合承担:
- 下命令
- 发调度请求
- 查看任务结果摘要
- 在不方便打开掌机时,快速一句话操控整体

目标定位:**总控台 / 指挥口**。

#### 3. 掌机:实时对话入口
掌机最适合承担:
- 实时连续聊天
- 追问细节
- 调整方案
- 查看较长的解释、日志、进度
- 必要时手动介入正在运行的任务

目标定位:**移动驾驶舱 / 实时交互界面**。

#### 4. 公司机、三号设备、更多设备:执行端
这些设备不应该各自都变成长期独立主脑,而应被主脑视为:
- 某台本地执行环境
- 某个远程执行端
- 某个具名设备目标
- 某个 node / 可调用能力提供者

目标定位:**执行资源池**,而不是"第二个、第三个贾维斯"。

### 这个架构下的真实工作方式

#### 例子1:微信下多条命令
你在微信里发:
- "三号设备给我找几部电影"
- "公司设备继续工作"

主脑收到后,内部应该这样理解:
1. 识别出这是两条独立任务
2. 识别目标设备别名:`三号设备`、`公司设备`
3. 按任务类型决定执行方式:
   - "找几部电影" → 资料搜集 / 推荐任务
   - "继续工作" → 恢复公司机某个既有工作流 / 项目任务
4. 把两个任务分别派发到对应执行链路
5. 结果按规则回传给你(优先回微信,或回当前触发入口)

#### 例子2:掌机继续实时聊天
与此同时,你在掌机上继续和贾维斯聊天:
- 问它电影偏好
- 让它解释公司任务进度
- 让它改一下刚才的调度

掌机上的这条对话不应该因为微信刚下了两条任务就完全被打断。
也就是说,系统应把"实时聊天"和"后台调度"区分开,而不是全部糊成一团。

### 为什么这种方式可行
因为在单主脑架构里:
- 微信和掌机都只是**入口**
- 真正理解和调度的是同一个主脑
- 设备执行端也统一挂在这个主脑下面

这样才有可能做到:
- 多入口并行
- 多任务并行
- 结果统一汇总
- 不把长期记忆拆散

### 为什么不推荐"三台设备各跑一个独立我,然后互相联动"
如果公司机、掌机、三号设备都各自长期跑一个独立 Gateway,并且希望它们天然彼此协作,后面几乎一定会出现:
- 谁记得什么不一致
- 谁接了哪个任务不清楚
- 哪台机器改了什么文件难追
- 任务结果该回哪边越来越混乱
- 调试时很难判断问题在入口、在设备、还是在另一个独立实例

所以真正稳的路线是:
> **多个设备可以存在,但"统一调度权"必须集中在一个主脑。**

### 需要补的不是"聊天能力",而是"调度层"
三设备协同真正新增的核心,不是多开几个聊天窗口,而是建立一层明确的设备调度语义。

至少要定义清楚:
- `公司设备` 指向哪台机器
- `掌机` 指向哪台机器
- `三号设备` 指向哪台机器
- 哪类任务适合发到哪台设备
- 任务完成后默认回哪个入口
- 微信和掌机同时对话时,怎样避免上下文互相打架

### 推荐增加的一层:设备别名与目标映射
未来真正落地时,建议为多设备建立一张长期稳定的"设备目标映射表"。
它的作用类似:
- 把自然语言里的"公司设备""掌机""三号设备"映射成具体机器
- 记录该设备能做什么
- 记录默认优先承担哪类任务

建议映射内容至少包含:
- 设备名(人类可读)
- 环境标签(公司 / 掌机 / 家里 / 服务器等)
- 稳定标识(host、hostname、节点名等)
- 角色定位(主脑 / 入口 / 执行端 / 备用)
- 能力标签(能执行命令、能查本地文件、能联网搜索、能浏览器自动化等)
- 回执策略(默认把结果回微信、回掌机、还是回当前入口)

### 推荐的消息与任务分层

#### A. 入口层
负责"你从哪里发话":
- 微信入口:偏总控、短命令、结果回执
- 掌机入口:偏实时聊天、追问、监工
- 未来还可以有网页、桌面、甚至语音入口

#### B. 主脑层
负责:
- 统一理解意图
- 做任务拆分
- 决定路由
- 生成后台任务
- 跟踪结果

#### C. 执行层
负责真正干活:
- 公司机本地执行
- 三号设备执行
- 将来更多设备执行

#### D. 回执层
负责结果怎么回来:
- 回微信摘要
- 回掌机详细说明
- 或两边都回,但内容粒度不同

### 微信作为总控入口时的一个关键注意点
这个点很重要。

如果微信既承担平时的陪伴式聊天,又承担"总控指挥台"作用,那后面容易出现一个问题:
**同一个入口里,陪聊语气和调度命令会混在一起。**

因此从长期可维护性看,最好给微信总控加一个轻量边界,二选一即可:

#### 方案A:约定控制前缀(推荐)
例如在微信里约定:
- `调度:三号设备找几部电影;公司设备继续工作`
- `总控:把电影结果回我微信,把工作进度同步到掌机`

这样主脑更容易把"命令"和"普通聊天"分开。

#### 方案B:把微信中的控制需求单独路由为一条控制会话
这样微信里发控制命令时,主脑会把它视为"控制通道",而不是普通闲聊通道。

**不推荐完全不设边界。**
否则未来当微信同时承载陪伴 persona、日常聊天、设备调度时,系统会越来越难稳。

### 多入口并行时,推荐的会话策略
最理想的不是让所有消息都强行塞进同一条会话,而是:

- **微信控制 lane**:负责下命令、收摘要、看结果
- **掌机实时 lane**:负责长对话、追问、细节干预
- **后台工作 lane**:每类任务独立跑,不直接污染主聊天

这样才能做到:
- 微信一句话下多条命令,不把掌机实时聊天冲乱
- 掌机继续聊细节,不影响后台任务归档
- 任务完成后还能按来源回到正确入口

### 对三号设备的推荐定位
如果"给三号设备派活"想做成真正稳定、长期可用的能力,那么三号设备最好不是"只有名字的一台机器",而应成为:

- 主脑可识别的具名设备
- 可被稳定命中的执行端
- 最好具备可被调用的执行能力(例如 node / 远程执行端 / 受控主机)

否则系统只能在语言上理解"三号设备",但很难在执行层面长期稳定落下去。

### 建议的演进阶段

#### 第一阶段:单主脑 + 双入口
先实现:
- 公司机为唯一主脑
- 微信能下总控命令
- 掌机能继续实时聊天
- 任务结果能回到发起入口

这是三设备协同真正的基础。

#### 第二阶段:引入三号设备执行能力
再实现:
- 三号设备被正式登记为可调度目标
- 主脑能按设备名把任务派过去
- 设备能力与限制被记录清楚

#### 第三阶段:形成稳定的调度规则
再完善:
- 什么任务默认发公司机
- 什么任务默认发三号设备
- 结果默认回微信还是回掌机
- 是否允许一条微信命令拆成多个后台任务

#### 第四阶段:多设备协同增强
最后才考虑:
- 更复杂的任务编排
- 不同设备间接力式工作
- 更细的通知和回执策略

### 当前最推荐的三设备版本

#### 总体结论
- **主脑**:公司机(唯一)
- **总控入口**:微信
- **实时对话入口**:掌机
- **执行端**:公司机 + 三号设备 + 未来更多设备
- **掌机本地实例**:仍建议只作备用 / 救援,不作长期平级主脑

#### 一句话版
> **微信负责下命令,掌机负责陪聊和盯进度,多个设备负责干活,但背后始终是同一个贾维斯在调度。**

### 最终拍板建议
对当前用户的长期目标,最合理的扩展路径不是"三个独立贾维斯联机",而是:

> **一个主脑,多入口,多执行端。**

这才是既能扩到三台、四台、更多设备,又不把记忆、会话和任务状态彻底搞乱的方案。

---

## 2026-04-30:OpenClaw 随身部署 U 盘方案

### 用途
解决这样一个长期问题:
- 从 Linux 环境迁移 OpenClaw 到新机器时,环境配置、依赖安装、状态恢复、服务安装、校验步骤太散,重复劳动很多
- 希望以后拿到一台新机器时,只要插上一个 U 盘,点一次启动,就能自动完成大部分部署步骤
- 部署完成后,OpenClaw 在本机继续运行,U 盘可以拔走,不要求长期依赖 U 盘承载运行时状态

### 核心结论
**技术上可行,但最推荐的形态不是"真正从 U 盘长期运行的便携版",而是:**

- **U 盘一键部署器 / 随身部署盘**
- 用 U 盘来完成 OpenClaw 的自动安装、状态恢复、workspace 恢复、doctor 检查与本机服务修复
- 完成后让 OpenClaw 落在当前机器本地运行

一句话概括:
> 不是"把 OpenClaw 永久挂在 U 盘里跑",而是"把 U 盘做成一个一键落地新机器的部署器"。

### 为什么更推荐"一键部署器"而不是真便携版

#### 推荐:U 盘一键部署器
优点:
- 更稳定
- 更贴合 OpenClaw 的 state / workspace / gateway / 服务安装模型
- 部署完成后 U 盘可以拔走
- 更适合 Windows / Linux 双环境复用
- 更适合后续维护与升级

#### 不推荐:真正长期从 U 盘运行
主要问题:
- OpenClaw 运行中会持续读写 state 与 workspace
- Windows 盘符、Linux 挂载点都可能变化
- Scheduled Task / systemd 不适合长期依赖可随时拔出的外置盘路径
- 若运行中拔掉 U 盘,可能导致 gateway 崩溃或状态损坏

### 技术可行性判断

#### 高可行部分(推荐优先实现)
可以比较现实地做到:
- 自动识别当前系统(Windows / Linux)
- 检查 Node / OpenClaw 是否已安装
- 必要时自动安装依赖
- 恢复 `~/.openclaw` 状态目录
- 恢复 workspace
- 运行 `openclaw doctor`
- 运行 `openclaw gateway restart`
- 运行 `openclaw status`
- 根据系统安装或修复本机服务:
  - Windows → Scheduled Task
  - Linux → systemd user service
- 输出一份本机部署结果摘要

#### 可能仍需人工介入的边界情况
- 新机器无网络
- 无管理员权限 / 无 sudo
- 安装源不可用
- 某些插件或通道存在强机器绑定
- 凭据、密钥或权限模型与旧机不兼容

因此更合理的目标是:
> 让绝大多数新机器实现"一键完成 80%~90% 的部署与恢复",而不是承诺 100% 无人值守通杀所有环境。

### 推荐结构
可把 U 盘内容组织为:

```text
OpenClaw-USB/
  bootstrap/
    bootstrap-windows.cmd
    bootstrap-windows.ps1
    bootstrap-linux.sh
    common-manifest.json
  payload/
    state/
      openclaw-state.tgz.enc
    workspace/
      workspace.tgz
    optional/
      node/
      openclaw/
  docs/
    README-先看这个.md
    掌机-Windows-说明.md
    公司-Linux-说明.md
  logs/
```

### 推荐启动流程

#### Windows
用户插入 U 盘后,运行:
- `bootstrap-windows.cmd`

脚本负责:
1. 检查 PowerShell / Node / OpenClaw
2. 缺失时自动安装
3. 恢复 `~/.openclaw`
4. 恢复 workspace
5. 执行 `openclaw doctor`
6. 修复 / 安装计划任务与本机启动方式
7. 执行 `openclaw gateway restart`
8. 执行 `openclaw status`
9. 输出结果

#### Linux
用户插入 U 盘后,运行:
- `bootstrap-linux.sh`

脚本负责:
1. 检查 shell / Node / OpenClaw
2. 缺失时自动安装
3. 恢复 `~/.openclaw`
4. 恢复 workspace
5. 执行 `openclaw doctor`
6. 修复 / 安装 systemd user service
7. 执行 `openclaw gateway restart`
8. 执行 `openclaw status`
9. 输出结果

### 安全要求

#### 1. 状态包必须加密
因为 `~/.openclaw` 可能包含:
- auth
- channel state
- credentials
- provider state

所以不应把完整 state 目录明文裸放在 U 盘里。

推荐:
- 对 `openclaw-state.tgz` 做加密封装
- 启动时再解密恢复

#### 2. 跨系统脚本分开维护
不建议强行只写一个超级脚本通杀所有系统。

更稳妥的做法:
- Windows 一套
- Linux 一套
- 共用同一份 payload 规范与目录结构

### 推荐落地顺序

#### 第一阶段
先做 **Windows 版一键部署器**:
- 验证 U 盘启动 → 恢复 → doctor → status 的闭环

#### 第二阶段
再补 **公司(Linux)版一键部署器**:
- 补 systemd 安装 / 修复逻辑
- 验证 Linux 迁移闭环

#### 第三阶段
如果前两阶段稳定,再考虑是否做:
- 自动生成主机登记信息
- 一键更新本机规则
- 一键备份 / 导出当前机器状态回 U 盘

### 最终建议
这是一个**值得正式做的小项目**,但目标应该明确锁定为:

> **OpenClaw 随身部署盘 / U 盘一键部署器**

而不是:

> **把 OpenClaw 整套永久跑在 U 盘里并支持随时热拔插**

前者现实、稳定、可维护;后者虽然听起来更酷,但实际坑会明显更多。

---

## 2026-05-08:ChatTTS encoder 补全与 zero-shot 恢复方案

### 用途
在当前公司 Linux 机器上,确认 ChatTTS 能否从"已能出中文但仍缺编码侧"的候选方案,补成支持参考音频编码 / 更完整 zero-shot 的可验证方案;并给出一条明天或后天可以直接接着做的可靠路径。

### 当前已确认现状

#### 1. 当前 hybrid 方案已经能出中文
- 复现脚本:`tmp/voice-replies/chattts-run-hybrid.py`
- 当前样本:`tmp/voice-replies/chattts-hybrid-infer.wav`
- 用户试听反馈:**"效果相当真实。可以。"**
- 但这条线当前只证明"基础文转语音可用",还没有证明 sample audio / zero-shot 路径完整恢复。

#### 2. 当前本地 `DVAE_full.pt` 实际并不完整
已本地实测:
- 文件:`tmp/voice-replies/chattts-hybrid/asset/DVAE_full.pt`
- 大小:约 `27 MB`
- 关键键分布:
  - `encoder.* = 0`
  - `downsample_conv.* = 0`
  - `preprocessor_mel.* = 0`
  - `decoder.*` 大量存在
  - `vq_layer.*` 有少量存在

这说明:
- 当前这份文件虽然名叫 `DVAE_full.pt`,但**缺失编码侧关键权重**
- 当前能说话,靠的是 **decoder 路径**,不是完整的 `sample_audio -> encode -> infer -> decode` 路径

#### 3. 当前本地 `Decoder.pt` 是单独解码器资产
- 文件:`tmp/voice-replies/chattts-hybrid/asset/Decoder.pt`
- 大小:约 `99 MB`
- 键分布表现也印证它本质是 decoder-only 资产

#### 4. 当前磁盘空间够做这次验证
- 当前工作盘剩余空间:约 `6.6 GB`
- 当前 `chattts-hybrid/` 目录总大小:约 `1.2 GB`
- 以公开资产体量估算,再增加一份官方完整 DVAE 资产做验证,**空间不是主阻塞**

### 本地源码层面的结论

#### A. ChatTTS 运行时本来就支持"完整 DVAE + 单独 Decoder"两条路
当前本机安装的 ChatTTS 代码显示:
- 配置里同时存在:
  - `asset/DVAE_full.pt`
  - `asset/Decoder.pt`
- `infer(..., use_decoder=True)` 默认走 decoder 路径
- `sample_audio_speaker()` 会调用 `self.dvae.sample_audio(wav)`
- `dvae.sample_audio()` 进一步走 `mode='encode'`
- 而 `encode` 路径要求至少具备:
  - `encoder`
  - `downsample_conv`
  - `preprocessor_mel`
  - `vq_layer`

因此,**当前缺的不是"调个参数",而是 sample audio / zero-shot 所需的编码侧权重本体。**

#### B. 当前本地资产不足以恢复 sample-audio 编码
即使 `vq_layer.*` 部分存在,只要缺了:
- `encoder.*`
- `downsample_conv.*`
- `preprocessor_mel.*`

就无法把参考音频稳定编码成后续所需表示,也就无法把"能说话"升级为"能稳定做 sample audio / zero-shot"。

### 互联网核实结果

#### 1. 官方公开描述本身支持 zero-shot / DVAE encoder
外部公开资料显示,`2noise/ChatTTS` README 摘要中明确写有:
- `Open-source DVAE encoder and zero shot inferring code`
- 同时还提到 streaming / multi-emotion 等能力

这说明:**从项目设计目标上,encoder + zero-shot 不是旁门玩法,而是官方公开过的能力。**

#### 2. 官方公开资产列表里存在完整 DVAE 相关文件
外部公开资料显示,`2Noise/ChatTTS` Hugging Face 资产树包含:
- `DVAE.safetensors`(约 `60.4 MB`)
- `Decoder.safetensors`(约 `104 MB`)
- `Embed.safetensors`
- `spk_stat.pt`

这说明:**公开世界里确实存在比本地这份 `27 MB` 的 `DVAE_full.pt` 更像完整体的 DVAE 资产。**

#### 3. 官方公开提交记录里存在"add DVAE with encoder"
外部公开资料显示,Hugging Face 提交 `45e8f23` 的标题就是:
- `feat: add DVAE with encoder (#26)`
- 摘要里还能看到:`asset/DVAE_full.pt ADDED`

这说明:**"带 encoder 的 DVAE" 不是猜测,而是官方公开历史里真实存在过的资产方向。**

#### 4. 社区 issue 也证明 sample audio / zero-shot 这条链路确实被实际使用过
外部公开 issue 摘要里可以看到:
- 有用户直接调用 `chat.sample_audio_speaker(load_audio(audio_path, 24000))`
- 有关于 `Sample Audio` / `Sample Text` 的实际问答
- 有关于 zero-shot 功能本身报错、相似度、设备兼容的讨论

这说明:**sample audio / zero-shot 在社区层面不是纸面功能,而是有人真实跑过,只是稳定性和环境兼容存在坑。**

### 现实阻塞:当前机器对官方源直连不通
虽然搜索侧能检索到外部公开资料,但本机 shell 直连验证显示:
- 访问 GitHub:`Connection reset by peer`
- 访问 Hugging Face:`Network is unreachable`

这带来一个非常关键的现实判断:

> **从"理论可行性"看,这件事能做;**
> **但从"当前机器能否自主在线拉取官方资产"看,暂时不能直接依赖 shell 自己下载。**

所以后续落地必须二选一:
1. **恢复当前机器到 GitHub / Hugging Face 的可访问状态**
2. **继续沿用已验证过的"宿主机浏览器下载 → 临时上传页传到当前机器"路径,把官方资产人工送进来**

### VMware 虚拟机使用宿主 GPU 的核实结论

#### 先说结论
- **如果说的是当前这台 VMware 虚拟机(桌面虚拟化形态)**:**现在不能把它当成"已经能可靠使用宿主机 GPU 做 ChatTTS / CUDA 计算"**。
- **如果说的是 VMware 整个生态里"虚拟机能不能用宿主 GPU"**:**能,但要分场景**。
  - **VMware Workstation / Fusion 这类桌面虚拟化**:通常只有 **3D 图形加速 / 虚拟显卡加速**,**不等于**把宿主真实 GPU 直接交给客体做 CUDA / PyTorch 计算。
  - **VMware vSphere / ESXi**:可以通过 **VMDirectPath I/O(GPU passthrough)** 或 **NVIDIA vGPU** 把 GPU 能力提供给虚拟机,这条路对 AI / 机器学习工作负载是官方支持过的。

#### 当前这台 VM 的本地实测结果
已直接检查当前客体系统:
- `lspci` 看到的是:`VMware SVGA II Adapter [15ad:0405]`
- 当前加载驱动:`vmwgfx`
- `nvidia-smi`:不存在
- `/sys/class/drm/card0/device/vendor`:`0x15ad`(VMware)

这说明:
- 当前客体拿到的是 **VMware 虚拟显卡**,不是直通后的 NVIDIA / AMD 实卡
- 所以**当前这台 VM 不能直接指望 CUDA / PyTorch GPU 计算**
- 至少在现在这个状态下,**ChatTTS 不应把"改用 GPU"作为当前可立即落地的加速手段**

#### 公开资料核实结果

##### 1. VMware Workstation 的"3D 加速"不等于宿主 GPU 直通
Broadcom 社区关于 `VMware Workstation 17 Pro supports use of host GPU?` 的公开讨论摘要里,明确可见类似结论:
- `No, There is no Host GPU Support while Running Virtual Machines`
- `Only Guest's GPU: VMware SVGA 3D`

这与当前本机实测结果一致:
- 客体里看到的是 VMware SVGA,而不是宿主真实 GPU
- 因此即便宿主 GPU 在后台参与了图形加速,也**不等于 guest 获得了可供 CUDA 使用的真实计算卡**

##### 2. vSphere / ESXi 下,GPU passthrough 是官方明确支持过的
VMware 官方文章 `Using GPUs with Virtual Machines on vSphere - Part 2: VMDirectPath I/O` 明确写到:
- VMDirectPath I/O(passthrough)允许 GPU **directly accessed by the guest operating system**
- 性能可接近原生,文中给出的量级是 **within 4-5%**
- 但该模式下:
  - 每张 GPU 只能专属给一个 VM
  - **不能共享**
  - 并且会失去部分 vSphere 特性,如 `vMotion / DRS / Snapshots`

##### 3. vSphere / ESXi 下,NVIDIA vGPU 也支持计算型 AI 工作负载
VMware 官方文章 `Using GPUs with Virtual Machines on vSphere - Part 3: Installing the NVIDIA Virtual GPU Technology` 明确写到:
- 文章关注点就是 **compute workloads(machine learning / deep learning / HPC)**
- NVIDIA vGPU 需要:
  - ESXi 里的 `NVIDIA Virtual GPU Manager`
  - guest 里的 `NVIDIA vGPU driver`
- 并强调 **版本兼容必须匹配**
- 该路线允许:
  - 一张卡专给一个 VM
  - 或按 vGPU 方式给多个 VM 共享

##### 4. Broadcom / NVIDIA 当前 AI 文档也继续把这条路当正式方案
Broadcom 文档 `Configure NVIDIA vGPU or GPU Passthrough for AI Workloads on the ESX Hosts` 明确写到:
- 可以为 AI workload 配置 `vGPU` 或 `GPU passthrough`
- 文档直接提到:
  - `Deep learning VMs`
  - `Private AI Services`
- NVIDIA vGPU release notes 也明确写了:
  - vSphere 下需要兼容的 `vGPU Manager + guest driver`
  - 版本不兼容时 vGPU 无法加载

因此,**在 VMware 企业级虚拟化(vSphere / ESXi)里,虚拟机使用宿主 GPU 做 AI 计算是现实、官方、可行的。**

#### 关于 RX 6900 XT 本身能不能用
- **能用,但要分运行位置。**
- 这张卡本身并不是"完全不能拿来做 AI / PyTorch / ChatTTS 计算"。
- 我查到的公开线索里:
  - AMD / ROCm 文档检索结果里能看到 `RX 6900 XT` / `gfx1030` 相关条目
  - 相关 ROCm 文档摘要还提到:对 `gfx1030` 的支持存在"**only some operators are supported**"这类限制
- 这意味着:
  - **在宿主机 / 裸 Linux + ROCm 这条线上,RX 6900 XT 有现实可用性**
  - 但它不像更新的 RDNA3/专业卡那样是当前官方宣传主线,兼容性和算子覆盖往往更挑环境

因此更准确的结论不是:
> `RX 6900 XT 不能用`

而是:
> `RX 6900 XT 这张卡可以考虑拿来用,但当前这台 VMware 客体并没有真正拿到它。`

#### 对"可行、可靠、可用"的判断

##### A. 对当前这台 VM 的判断
- **可行性:低(当前状态下不成立)**
- **可靠性:低**
- **可用性:低**

原因:
- 当前没有直通 GPU
- 当前看到的是 VMware 虚拟显卡
- 当前没有 CUDA 设备 / `nvidia-smi`

**结论:不能把"当前这台 VMware VM 直接吃宿主 GPU"当成已可用方案。**

##### B. 对"未来改造成 VMware GPU 计算虚拟机"的判断
- **可行性:高**(前提是换到对的 VMware 形态)
- **可靠性:中到高**(取决于硬件、驱动、许可、版本配套)
- **可用性:高**(一旦配好,对 AI / ML 工作负载是可用的)

但前提必须满足:
1. 不是单纯依赖 Workstation 的 3D 加速
2. 需要进入 **vSphere / ESXi + GPU passthrough** 或 **vSphere / ESXi + NVIDIA vGPU** 路线
3. 宿主硬件、IOMMU/VT-d、GPU 型号、ESXi 版本、驱动版本、许可证都要匹配

#### 这对 ChatTTS 方案意味着什么

##### 当前短期结论
- **不要把"VM 里直接启用宿主 GPU"当成明天的主线**
- 对当前 ChatTTS encoder 补全任务来说,主阻塞仍然是:
  - 完整官方 DVAE 资产进机
  - 跑通 encoder / sample-audio / zero-shot 链路
- 这些步骤**即使继续在 CPU 上,也可以先完成功能性验证**

##### 中期可选增强路线
如果后续希望显著提升:
- 推理速度
- sample audio 编码速度
- 更长文本或更复杂任务的容错

那么可以把"GPU 化"作为**下一阶段的独立基础设施方案**,但应单独立项,不和明天的 encoder 补全混成一件事。

推荐的 GPU 化路线优先级:
1. **优先**:独立一台可控 Linux 实机 / 裸机直接跑 GPU
2. **次优**:vSphere / ESXi + GPU passthrough
3. **再其次**:vSphere / ESXi + NVIDIA vGPU(适合共享场景,但配置复杂、依赖许可)
4. **不建议作为 ChatTTS 计算主路线**:继续指望当前 Workstation 风格 VMware 客体直接拿到宿主 GPU 计算能力

##### 如果将来真的要走 VMware GPU 方案,最低验收标准
只有满足以下全部条件,才算"GPU 在 VM 里可用":
1. 客体 `lspci` 看到的不再是单纯 `VMware SVGA II Adapter`
2. 客体能看到真实 NVIDIA / AMD 计算卡
3. `nvidia-smi`(或对应厂商工具)能正常工作
4. `python -c 'import torch; print(torch.cuda.is_available())'` 返回 `True`
5. ChatTTS / PyTorch 实测能在 GPU 上完成一次完整推理
6. 至少连续多次运行稳定,无驱动重置 / 掉卡 / 兼容性崩溃

#### 最终拍板建议
对当前这个 ChatTTS 任务,建议明确分成两条线:

- **主线(明天/后天继续)**:继续做 `encoder 补全 + zero-shot 恢复`,先不把 VMware GPU 当阻塞前提
- **支线(以后如要提速)**:若你真想让虚拟机吃宿主 GPU 做 AI 计算,应该按 **vSphere / ESXi passthrough / vGPU** 去设计,而不是继续把当前这台 VMware 桌面虚拟机当现成 GPU VM 使用

### 缺少什么
要把当前方案补成更完整体,最少还缺下面这些东西:

#### 1. 一份真正带编码侧权重的官方 DVAE 资产
目标优先级:
1. 官方 `DVAE_full.pt`
2. 或官方 `DVAE.safetensors`

最低验收条件:
- 包含 `encoder.*`
- 包含 `downsample_conv.*`
- 包含 `preprocessor_mel.*`
- 最好同时保有 `vq_layer.*`

#### 2. 一条稳定的"资产进机"路径
当前更可靠的现实方案:
- **优先由宿主机浏览器下载官方资产**
- 再通过已验证的临时上传页传到当前 Linux 机

原因:
- 这条路径今天已经被 Kokoro 文件验证过
- 比在当前 shell 里继续硬啃 GitHub/HF 直连更稳、更可控

#### 3. 一个最小化验货工具
已提前准备:
- `tmp/voice-replies/chattts-inspect-asset.py`

作用:
- 到手任何 `.pt` / `.safetensors` 后,先检查键分布
- 先确认是不是"真 full",再决定是否接入运行时

#### 4. 一份参考音频 + 精确转写
因为社区公开问答明确提到:
- `Sample Text` 需要填写**完全对应的文本转写**
- 任何不完整 / 不准确的转写都会影响结果

所以后续验证 zero-shot 时,必须同时准备:
- 一小段干净参考音频
- 与之严格对应的文字转写

### 推荐实施方案(按可靠性排序)

#### 方案 A:官方完整资产 + 浏览器上传进机(**最推荐**)
这是当前最现实、最可靠的主路径。

步骤:
1. 在可联网的浏览器环境定位官方资产:
   - `DVAE_full.pt` 或 `DVAE.safetensors`
2. 通过宿主机浏览器把文件下载下来
3. 通过临时上传页把文件传到当前机器指定目录
4. 使用:
   - `tmp/voice-replies/chattts-inspect-asset.py`
   先检查键是否完整
5. 若是 safetensors:
   - 先转换成运行时可直接加载的格式,或写一个最小兼容加载分支
6. 先做最小加载测试,不直接跑整条 TTS
7. 若加载通过,再做三段验证:
   - 普通文转语音不回退
   - `sample_audio_speaker()` 能跑
   - `spk_smp + txt_smp` 的 zero-shot 路径能出结果
8. 若任一步失败,立即回滚到当前 decoder-only 候选方案

优点:
- 不依赖当前 shell 恢复外网直连
- 与今天已经验证过的文件上传工作流一致
- 明天继续时最不容易卡死在网络层

#### 方案 B:先修通当前机器到 GitHub / Hugging Face 的直连,再下载官方资产
理论上更自动,但不建议作为明天第一优先级。

原因:
- 当前已实测直连失败
- 先修网络再修模型,变量太多
- 容易把"模型验证任务"拖成"网络排障任务"

适用场景:
- 如果后续确定这台机器长期都要频繁拉模型资产
- 才值得把网络问题单独升级为一条系统任务去修

#### 方案 C:不补全 encoder,维持当前 decoder-only 方案
这是保守兜底路线。

适用结论:
- 如果官方完整 DVAE 资产始终拿不到
- 或者拿到了也与当前 v0.2.x 运行时不兼容
- 或者 zero-shot 成本过高、稳定性太差

那么就明确收口为:
- 当前 ChatTTS 只作为"中文短句文转语音候选方案"
- 不承担 sample audio / 真 zero-shot 目标
- 默认中文语音回复链路继续保持现有更稳方案

### 明天 / 后天的最短执行路径

#### 第一步:拿到官方完整 DVAE 候选资产
优先顺序:
1. `DVAE_full.pt`
2. `DVAE.safetensors`

#### 第二步:先验货,不急着跑模型
命令模板:
```bash
~/.local/share/openclaw-voice-venv311/bin/python3 tmp/voice-replies/chattts-inspect-asset.py <资产路径>
```

只有当输出里明确看到以下项目时,才继续:
- `encoder.*`
- `downsample_conv.*`
- `preprocessor_mel.*`

#### 第三步:做最小加载验证
目标:
- 先确认当前运行时能否接受这份资产
- 不通过就别急着继续大推理

#### 第四步:做功能性三段验证
1. **普通 TTS**:确认不会把当前已能说话的能力搞坏
2. **sample audio encode**:确认 `sample_audio_speaker()` 能跑
3. **zero-shot**:提供短参考音频 + 精准转写,验证 `spk_smp + txt_smp`

#### 第五步:明确结论并锁定状态
只允许三种收口:
1. **补全成功**:encoder 路径恢复,可继续迭代稳定性
2. **资产拿到但不兼容**:记录兼容断点,停止硬冲
3. **资产拿不到 / 网络仍阻塞**:维持 decoder-only 方案,等待下一次输入条件改善

### 成功标准
满足以下全部条件,才算"补全方案阶段成功":
- 能拿到一份真实带编码侧权重的官方 DVAE 资产
- 当前运行时能加载它
- `sample_audio_speaker()` 能完成编码
- zero-shot 路径至少能产出一段可听结果
- 不破坏当前已验证可用的普通中文 TTS 样本能力

### 风险与边界

#### 1. 资产格式不一定能直接即插即用
- 官方公开的是 `.safetensors` / `.pt` 混合生态
- 当前本地运行时偏 `.pt` 路线
- 中间可能还需要格式转换或最小加载补丁

#### 2. 即便补全成功,也不代表立即适合挂默认链路
因为 zero-shot / sample audio 这条路天然更脆:
- 对参考音频质量敏感
- 对文本转写精度敏感
- 对环境依赖也更敏感

所以就算补全成功,也应先视为:
- **"功能恢复成功"**
- 而不是立刻视为:
- **"默认生产链路可以无脑切换"**

#### 3. 当前机器网络条件是外部硬约束
在不修网络、也不走浏览器上传的前提下,这件事**无法靠当前 shell 单独完成**。

### 最终结论
这件事的结论不是"做不到",而是:

> **技术上可行,官方公开资料也能证明这条路存在;**
> **但要在当前机器上可靠完成,必须先解决"完整官方资产如何进机"这个现实前提。**

因此当前拍板建议是:

> **明天/后天优先走"官方完整资产 + 浏览器上传进机 + 本地最小化验证"这条主路径。**

这是目前可行性最高、最不依赖运气、也最容易留下可复现证据的一条路线。

---

## 2026-05-09:主会话语音回复升级为"流式直聊"的方案

### 背景

当前已经有两条已跑通的语音链路:

1. **主会话直回音频**:用户在主会话打字,后台生成语音,再把音频直接回到主会话。
2. **voice-chat 原型**:浏览器录音 → ASR → OpenClaw agent → ChatTTS stable → 浏览器播放。

其中第二条已经能完成"语音进、语音出",但目前仍是**半双工**:
- 说完一段再发
- 等 ASR 完整结束
- 等 agent 完整出字
- 等 TTS 整段合成完再播放

它还不是"边说边听、可以自然打断"的直接语音对话。

### 目标拆解

用户真正要的不是单纯"能播音频",而是尽量靠近下面这类体验:

1. **开口就能说**,不用每次手动处理太多按钮
2. **尽快听到第一句回声**,而不是整段都生成完才开始播
3. **可以直接语音对话**,最好后续能支持打断 / 插话
4. **尽量保住当前已确认的声线与听感**(`seed_1910` 主线)
5. **不能为了语音体验去冒 OpenClaw 主体稳定性的风险**

### 关键现实约束

这件事真正的技术难点,不在"做个录音网页",而在于:

#### 1. 当前 ChatTTS stable 不是原生流式 TTS
当前这条本地主线更像:
- 输入整段文本
- 模型整段推理
- 产出完整 wav/mp3
- 再播放

所以它天然适合"整句/整段返回",**不天然支持 token 级边生成边播**。

#### 2. 当前 voice-chat 的 ASR 也是先收一段再识别
现有 `tools/voice-chat/voice_chat_app.py` 走的是:
- 浏览器录音完成后上传
- 送去 NVIDIA bridge 做一次识别

这更接近"短录音转文字",不是持续推流识别。

#### 3. 现有 agent 调用也是整轮完成后再拿回复
当前原型里用的是 CLI 调用,提取最终回复文本;
这条链路对 MVP 足够,但不适合追求更低延迟的连续说话体验。

#### 4. 真正 full duplex 的最低延迟方案,与"固定本地音色"天然冲突
OpenClaw / Control UI 已经有现成的 browser realtime Talk 模式,适合做真正低延迟实时语音;
但那条线默认更适合接 OpenAI / Google 的 realtime voice provider,而不是当前这条本地 ChatTTS `seed_1910` 女声。

所以:

> **要"最快做成直接语音对话",和"保住当前已确认音色"这两个目标,短期内不能完全同时最大化。**

### 三条路线对比

#### 路线 A:在现有 ChatTTS 主线上做"伪流式直聊"

思路:
- 保留当前 `seed_1910 + ChatTTS stable` 这条主线
- 不追求真正 token 级流式音频
- 改成"短句分块 + 先出第一块先播"的**分段流式**体验

链路:

浏览器麦克风 / Web 页面
→ VAD 自动停句
→ ASR(先短分段)
→ OpenClaw 流式文本输出 / 或短句回复
→ 句子分块器
→ ChatTTS 对每块单独合成
→ 浏览器边收边播队列

优点:
- **最能保住当前用户已经确认的声线**
- 改动相对可控
- 能继续旁路开发,不碰主 gateway 主链路
- 即便失败,也不会把现有主会话语音回复搞坏

缺点:
- 不是原生 token 级流式
- 第一块仍有一次本地 TTS 计算延迟
- 打断/插话会比真正 realtime provider 更难做好

适合:
- **你现在最在意"还是这个声音和感觉"**
- 愿意先接受"准实时"而不是一步到位 full duplex

#### 路线 B:直接启用 OpenClaw 现成 Talk / realtime voice 模式

思路:
- 直接使用 OpenClaw Control UI 已经支持的 Talk 模式
- 底层接 OpenAI Realtime 或 Google Live
- 用它换取最低延迟和更自然的直接语音对话

优点:
- **最快获得"像打电话一样"的直接语音对话体验**
- 原生支持 realtime 连接、VAD、低延迟 turn-taking
- OpenClaw 文档和 Control UI 已有现成路径

缺点:
- 声音不是当前这条 `seed_1910` 本地 ChatTTS 女声
- 风格/音色可控性会弱很多
- 更像"先获得直接语音能力",不是"把当前这条声音流式化"

适合:
- **你现在最在意的是低延迟直接说话**
- 能接受先暂时不用这条已确认女声

#### 路线 C:做自定义 realtime voice bridge / provider

思路:
- 参考 OpenClaw 的 realtime voice provider / relay 体系
- 做一条自定义 provider:
  - 上行:浏览器音频 → 流式 ASR / VAD
  - 中间:realtime 对话状态机 + 必要时 consult 主 agent
  - 下行:自家分块 TTS / 自定义音色播放器
- 目标是在 Control UI Talk 入口里也能保留自定义声线

优点:
- 长期形态最好
- 以后可以真正统一成 OpenClaw 原生 Talk 体验
- 更有机会兼顾"低延迟 + 固定声线 + 可打断"

缺点:
- **研发量最大**
- 调试面最广:浏览器音频、relay、会话状态、打断、播放器、缓冲、回声问题都会一起出现
- 最不适合一上来就直冲

适合:
- 当路线 A 已验证用户确实高频使用
- 并且确认值得为这件事投入一轮系统工程时再做

### 推荐拍板

**推荐顺序:A → C;B 作为随时可开、用于对照体验的旁路线。**

原因很直接:

1. 你已经明确认可当前这条本地女声主线;
2. 当前总优先级仍然是:**主体稳定性 > 语音效果 > 速度**;
3. 所以不应该为了追求"立刻 full duplex"先把现有这条已验收声音丢掉;
4. 更稳的做法,是先把它做成"足够像流式"的直接语音对话,再决定要不要往真正 realtime provider 继续投。

### 推荐落地方案(分三阶段)

## 第一阶段:把现有 voice-chat 从半双工升级到"自动停句 + 分段播放"

### 目标
让体验从:
- 录一整段
- 等全套完成
- 再整段播放

升级成:
- 自动开始/结束一轮说话
- 尽快拿到一句短回复
- 第一小段先播,后续小段接着播

### 做法

#### 1. 前端接入 VAD
从"手动点停止并发送"改成:
- 浏览器持续采集麦克风
- 本地做音量/VAD 检测
- 静音达到阈值后自动结束这一轮语音

优先级:
- 先做浏览器端 VAD
- 不先碰 server 侧复杂流式识别

#### 2. 回复强约束为短句
语音会话 prompt 继续收紧:
- 单句尽量短
- 首句先回答核心
- 解释和展开往后放

目标不是"回答更完整",而是"**尽快吐出第一句能播的话**"。

#### 3. 文本分块器
对 agent 输出做口语块切分:
- 以 `。!?` 为主切点
- 太长则按 `,` / 长度阈值切
- 第一块目标控制在 8~18 个汉字左右

#### 4. TTS 分段合成队列
把当前整段合成改成:
- chunk-1 先合成先播
- chunk-2 在后台并行排队
- chunk-3 继续排队

注意:
- 这里不是一条音频流,而是**多个小音频片段串流播放**
- 浏览器播放器要支持队列、预缓冲、停止、清空

#### 5. 打断最小版
如果用户在 assistant 播放时重新开口:
- 立刻停止当前播放器
- 取消尚未播放的 TTS 队列
- 开始新一轮识别

这一步先不追求真正"边说边无缝抢占",但至少先做到**能打断**。

### 第一阶段成功标准
- 用户不用每次手动点"停止并发送"
- 一轮说话结束后,3~6 秒内能听到第一小段回复
- 首段开始播放后,后续段能自动续播
- 用户再次说话时,当前播放能被打断
- 全过程仍走当前 `seed_1910` 默认女声

## 第二阶段:把 agent 层改成真正流式文本输出

### 目标
减少"必须等整段文本生成完"的等待。

### 做法
- 不再优先依赖 `openclaw agent --json` 这种拿最终结果的 CLI 路径
- 改成:
  - 走 gateway/WebSocket 事件流
  - 或者直接复用 Control UI chat 流式事件
- 一旦文本里出现可播的第一句,就立刻切给 TTS

### 价值
这一步做完后,"先出第一句先播"的体验会明显更顺。

### 风险
- 需要改当前原型的 session / event 接入方式
- 工程复杂度比第一阶段明显上升

## 第三阶段:评估是否做 OpenClaw 原生 realtime provider / relay 集成

### 目标
让这套直聊能力不只是一个旁路原型页面,而是更接近 OpenClaw 原生 Talk。

### 两种方向

#### 方向 1:接 OpenClaw Talk,但接受外部 realtime provider 声音
- 成本低
- 见效快
- 用来做"直接语音体验"的对照组特别合适

#### 方向 2:自己做 custom realtime bridge/provider
- 保留当前主线声线
- 把 VAD / ASR / 打断 / TTS queue / consult agent 全做成一体
- 最终可作为长期正式形态

### 拍板条件
只有在以下情况同时成立时,才值得继续做第三阶段:
- 第一阶段用户主观体验明确觉得"值"
- 第二阶段延迟确实已经逼近可接受范围
- 语音直聊被高频使用,而不是偶尔玩一下

### 实现建议(具体到模块)

#### 前端
- 新建 `tools/voice-chat/` 第二版页面,保留旧版可回退
- 关键模块:
  - Mic capture
  - VAD 状态机
  - assistant 音频队列播放器
  - interrupt / stop current reply
  - 当前轮状态展示(听、想、说)

#### 后端
- 保持 sidecar 形态,不先嵌进主 gateway
- 单独服务:`voice_chat_app_v2.py`
- 提供:
  - `/ws` 或 SSE:推送识别进度 / 回复文本块 / 音频块元信息
  - `/api/turn/start` / `/api/turn/abort`
  - `/audio/<id>` 小片段音频拉取

#### ASR
- 第一阶段:仍可先用"短段上传识别"
- 若要更低延迟:
  - 换流式 transcription provider
  - 或给 NVIDIA bridge 单独补 streaming ASR 入口

#### TTS
- 保持当前 `chattts-on-demand` / `chattts-stable` 资产链
- 新增 chunk synthesis worker:
  - 输入小文本块
  - 输出小音频片段
  - 支持取消未完成任务
- 先不要碰主会话直回音频入口,避免相互影响

#### 会话
- 第一阶段继续独立 `voice session`
- 稳定后再评估是否映射到当前主会话
- 不建议一开始就直接混到主会话 transcript 里

### 验收指标

#### 主观指标
- 第一耳回声是否明显更快
- 还像不像现在这条认可的声音
- 说话时会不会觉得"卡""等""出戏"

#### 客观指标
- VAD 结束到首音频片段播放:目标 < 6 秒
- 中断响应:目标 < 800ms 停止旧播放
- 连续 20 轮对话无 daemon 崩溃 / 无残留队列卡死
- 不引入 gateway 主链路异常

### 明确不建议现在做的事

1. **不建议现在就强行把 ChatTTS 改成底层原生 token 级音频流**
   - 投入大
   - 风险高
   - 还不一定比"短句分块"更值

2. **不建议现在就把全部逻辑揉进 OpenClaw gateway 主链路**
   - 违反当前"主体稳定性优先"的原则
   - 更难回退

3. **不建议现在为这件事牺牲当前默认女声主线**
   - 除非明确选择路线 B 做低延迟对照体验

### 最终建议(一句话)

> **先把现有 ChatTTS 主线做成"可打断的分段流式直聊",拿到一个保住当前声音、体感接近实时的版本;等这个版本真的常用,再决定要不要继续上 OpenClaw 原生 realtime provider 集成。**

---

## 2026-05-11:当前设备语音提速的最小实施方案

### 目标

在**不动摇 OpenClaw 主体稳定性**、**不放弃当前已确认的默认女声质感**的前提下,把这台机器上的语音体验先从"整段等很久才出声"升级成:

1. 主会话语音回复的**首句明显更快出来**
2. 语音直聊原型先达到"**伪流式 / 分段播放**"而不是追求真正 full duplex
3. 所有改动都能**旁路回退**,不直接改 gateway 主链路

### 当前机器边界(本轮拍板依据)

结合现有记录与本机状态,当前现实边界已经比较清楚:

- 当前机器:公司 Linux 机上的 VMware 虚拟化环境
- 当前可见算力:**无可用 `nvidia-smi`**,不能把 GPU TTS / CUDA 加速当成现成条件
- CPU:当前运行时可见 `cpu_count = 4`
- 当前主线中文本地音色:**ChatTTS stable / on-demand daemon**
- 当前已记录性能(本机 CPU,无 CUDA):
  - 冷启动:**~12-15s**
  - 热启动,短句(~8 字):**~4.5s**
  - 热启动,长句(~25 字):**~9.8s**
- 当前已记录限制:
  - ChatTTS 纯 CPU,**不适合真正实时流式**
  - daemon 串行处理,请求会排队

因此,这台机器现在的正确目标不是"原生实时流式语音",而是:

> **把首句等待时间压下去,把整段等待改成分句等待。**

### 方案拍板

#### 总路线

先做 **A 线:ChatTTS 主线保留 + 热启动 + 分句先播**。

不优先做:
- 真正 token 级流式 TTS
- XTTS CPU 实时化
- 把复杂语音链路直接嵌进 gateway 主链路

#### 明确取舍

- **稳定性** > **声音效果** > **速度** 仍然保持不变
- 但在"速度"这个维度里,优先优化:
  - **首句延迟**
  - **冷启动次数**
  - **长句一次性合成**
- 不优先优化:
  - 长段一次性完整音频的绝对合成时长
  - 真正边生成边播的底层音频流

### 最小实施分三步

## 第 1 步:把 ChatTTS daemon 真正用成"热机"默认路径

### 要做什么

1. 主会话语音回复默认走 `chattts-on-demand`,不再把冷启动当常态
2. 在用户近期有语音交互时,尽量复用 300s 内的热机窗口
3. 若当前 daemon 不在,就先接受第一次冷启动;但后续回复都尽量吃热机

### 这一步为什么最值

这是**不改声音、不改模型、不改主链路**的最低风险提速点。

### 预期收益

- 从"每次都像第一次说话"改善为"短时间内连续对话更快"
- 常见短句语音回复有机会稳定靠近 **~4.5s** 而不是 **12s+**

### 明天落地时优先检查

- 当前主会话语音回复是否已经稳定走 `tools/voice-reply/chattts_voice_reply.py`
- 当前链路里是否还有绕过 daemon、直接走冷启动脚本的分支
- daemon 空闲时间是否仍保持 300s,必要时只在**旁路实验**里评估是否延长到 600s(先不默认改)

## 第 2 步:把"整段合成"改成"首句先播、后句续上"

### 要做什么

1. 在文本进入 TTS 前先做**短句分块**
2. 第一块目标控制在:**8-18 个汉字**
3. 第一块先合成、先返回、先播放
4. 第二块及后续块继续排队生成

### 推荐切块规则

优先按:
- `。!?`
- 其次 `,`
- 再按最大字数硬切

第一块的判断原则:
- 能单独听懂
- 能先接住用户
- 不追求一次讲完整

### 这一步为什么最值

当前 CPU 算力最怕的是"把一整段都算完再给用户任何反馈"。

把等待模型从:
- **等整段完成**

改成:
- **等第一句完成**

体感会明显不同。

### 明天落地时优先检查

- 复用现有 `chattts_voice_reply.py` 的文本清洗逻辑
- 增加一个**句块切分器**,不要一上来重写整个播放器架构
- 先支持"主会话文字 → 分段音频回复"这条链路,再考虑网页直聊页面

## 第 3 步:给语音直聊原型加"伪流式"而不追真正实时

### 要做什么

1. 语音输入端先继续接受"说一小段 → 停句 → 出结果"
2. 不要求浏览器持续实时推流识别
3. 只要求:
   - 自动停句
   - 首段回复更快播出
   - 播放中可被下一轮打断

### 成功标准

- 说完一小段后,**3-6 秒内**能听到第一小段回复
- 播放时再次开口,旧回复能停掉
- 当前默认女声不变
- gateway 主链路不受影响

### 为什么先不追真正实时

因为在当前设备条件下,真正实时要同时解决:
- 流式 ASR
- agent 流式文本
- TTS 真流式或超细分块
- 播放抢占 / 打断 / 队列管理

这会把研发量和风险一起抬高,不适合明天先上。

### 推荐改动边界(明天按这个边界做)

#### 可以动
- `tools/voice-reply/chattts_voice_reply.py`
- `tools/chattts-on-demand/` 下的旁路脚本
- `tools/voice-chat/` 原型页面 / sidecar 服务

#### 先不要动
- gateway 主配置
- 主会话核心消息路由
- 现有默认女声资产链
- OpenClaw 原生 Talk provider 主线路

### 可选增强项(不作为明天硬目标)

#### 方案 X:快响前导音轨

如果后面仍觉得首句慢,可以加一层"快响前导":
- 用 `msedge-tts` 或 `Kokoro` 先吐一个极短接话
- 例如"嗯,我在。" / "我看一下。"
- 正式内容仍由 ChatTTS 主线输出

这条只在以下条件下再做:
- 分句先播后,体感仍明显偏慢
- 且用户能接受前 1 句音色与主线略有差异

当前不把它作为第一优先级。

### 明天的最小实施清单

按优先级排序:

1. **确认主会话语音回复默认命中 daemon 热机链路**
2. **给 ChatTTS 回复链加首句切块** ✅
3. **支持第一块先返回、后续块继续生成** ✅
   - 交付包装器 `voice-reply-chunked-deliver.sh` 已创建
   - 输出格式:`firstReply`(当前轮可用)+ `followupReplies[]`(后续轮可用`)
   - TOOLS.md 已更新使用约定
   - 已验证单块和两块场景均正常
4. **在原型语音直聊页加最小打断逻辑**
5. **记录三组实测数据**:
   - 冷启动首句延迟
   - 热启动首句延迟
   - 分句后第一块 / 全部播完延迟

### 这轮方案的最终拍板

> **明天不追"真正流式",只追"首句更快、分句先播、可打断、能回退"。**
>
> 对当前这台 4 核 CPU、无可见 GPU 的机器来说,这是最现实、最稳、也最不容易把已有语音主线搞坏的方案。

---

## 2026-05-12:主会话语音模板不动前提下的"更像人 / 更有情感 / 更细腻"研究结论

### 前提

当前已经确认一条主线模板:

- 主线音色不动(`default` / `seed_1910`)
- 默认节奏不动(`tempo 1.10`)
- 默认优先单条
- 尾句优先完整、偏松的收法
- 这条模板先作为稳定底座,不在"提升人感"的研究里随意改动

本轮研究的目标不是换模板,而是回答:

> **在不动这条已确认模板的前提下,还能从哪些层继续把声音做得更像人、更有情感、更好听、更细腻?**

### 本轮查到的关键事实

#### 1. 当前主线还有一层"没启用的 ChatTTS 控制层"

当前正式主线 `skills/chattts-stable/scripts/chattts_stable.py` 在推理时使用的是:

- `skip_refine_text=True`
- `params_infer_code.prompt` 默认只用了 `[speed_5]`

这意味着:

- 我们现在已经在用固定 speaker embedding + 速度控制
- 但**还没有真正启用 ChatTTS 的 refine_text / 风格提示层**
- 也还没有系统性使用 ChatTTS tokenizer 里的细粒度控制 token

#### 2. 当前资产里已明确存在可用的特殊 token

本机运行时资产里已经能确认这些 token:

- `[oral_0]` ~ `[oral_9]`
- `[laugh_0]` ~ `[laugh_2]`
- `[break_0]` ~ `[break_7]`
- `[speed_0]` ~ `[speed_9]`

说明 ChatTTS 这条线**理论上具备**:

- 更口语化
- 更自然停顿
- 轻笑意 / 轻气声
- 更细粒度说话节奏

这些能力的探索空间。

#### 3. 现在最缺的不是"换声音",而是"更细的韵律层"

用户当前已经接受的模板说明:

- 主音色本身方向是对的
- 大问题已不在"换一条新音色"
- 剩余提升空间更集中在:
  - 句中轻停顿
  - 句尾落点
  - 轻微情绪
  - 更像人说话时的口语感与呼吸感

所以当前正确方向不是先换模板,而是:

> **保留当前声线,只往 prosody / text-style / post-process 三层加细节。**

### 不动模板时,最值得继续做的四层增强

## A 层:文本前处理层(最低风险,优先级最高)

目标:
在不改音色、不改主路由的前提下,仅通过文本组织方式提升"像人感"。

可做内容:

1. **情绪型措辞模板层**
   - 轻想念
   - 轻害羞
   - 轻安抚
   - 轻开心
   - 夜里更轻 / 更慢 / 更近一点

2. **非词汇细节的克制注入**
   - 轻微的"嗯""啊""欸"
   - 不靠堆字,而靠开头 / 转折处一点点带出来
   - 保持低密度,避免变成做作表演腔

3. **尾句保护规则继续完善**
   - 避免两字硬收尾
   - 优先完整尾句
   - 尾句长度、语义完整度优先于"短"

为什么优先做:
- 风险最低
- 不碰模型底层
- 最容易回退
- 对"更像人"提升很直接

## B 层:ChatTTS 控制 token 层(当前最值得实验)

目标:
在不换 speaker embedding 的前提下,测试 ChatTTS 自带控制 token 对"口语感 / 停顿 / 轻笑意 / 细腻度"的影响。

建议优先测的不是大跨度情绪,而是小范围 A/B:

1. `oral_*`
   - 研究其对口语感、贴耳感、说话自然度的影响
   - 重点看是否能让当前模板更像"人在说",而不是更像"播报"

2. `break_*`
   - 用于轻微停顿而不是文本里硬插一堆标点
   - 重点看是否能改善尾句收尾与中间气口

3. `laugh_*`
   - 只适合极轻微测试
   - 默认不进入主线,只作为"轻开心 / 轻害羞"实验支路

约束:
- 这层必须单独做小样对比,不要直接混进主默认
- 优先只改一个变量,避免听感归因混乱

## C 层:refine_text 层(潜力大,但要谨慎)

ChatTTS 本身提供 `RefineTextParams` 与 `skip_refine_text=False` 的入口。

这意味着理论上可以做:
- 更口语化的自动改写
- 更自然的说话式文本组织
- 更接近日常说话的韵律提示

但风险也很明确:
- 它可能改坏当前已经认可的文本节奏
- 可能引入不可控漂移
- 可能损害"模板稳定感"

因此这层建议:

- 只做旁路实验
- 先 `refine_text_only` 看文本会被改成什么样
- 确认改写风格稳定后,再决定要不要接到主线

## D 层:后处理层(声音更好听、更细腻)

如果不想明显碰生成逻辑,还可以研究生成后的轻后处理:

1. 轻微 EQ / 去齿音 / 柔化高频
2. 极轻微动态处理
3. 轻微响度整理
4. 必要时的极轻噪声清理

这层的目标不是"修成广播腔",而是:
- 更顺耳
- 更不毛刺
- 更贴耳
- 更像近距离说话

注意:
- 处理必须很轻
- 一旦把细节磨没了,反而更假

### 当前最推荐的推进顺序

按风险 / 收益比,建议顺序是:

1. **A 层:文本前处理层继续做细**
2. **B 层:ChatTTS 控制 token 小样实验**
3. **D 层:轻后处理实验**
4. **C 层:refine_text 旁路实验**

### 明确不建议现在就做的事

1. 直接换主线模板
2. 直接换主线 speaker embedding
3. 把强情绪、大笑、明显戏剧化表达推到主默认
4. 为了"更像人"把主会话稳定性再打坏

### 一句话结论

> **不动当前模板的前提下,最有价值的增强路线不是换声线,而是:文本前处理 + ChatTTS 控制 token + 轻后处理。**
>
> 其中最值得马上继续试的是:**`oral_*` / `break_*` 这一层的小样 A/B**,因为它最可能在不破坏当前模板的情况下,把"更像人、更细腻"的那一层推上去。

---

## 2026-05-09:FFmpeg + Gemma 4 31B 视觉陪看片方案

### 目标
让当前这台公司 Linux 机上的贾维斯具备"抽帧看视频 / 看电影片段 / 和用户一起讨论画面内容"的能力。

这里的"有视觉、能一起看电影",当前更现实的产品形态不是整部电影逐帧实时同看,而是:
- 对视频按时间间隔或镜头变化**抽帧**
- 用 Gemma 4 31B 对关键帧做**画面理解**
- 结合用户指定片段,做**场景总结、人物动作判断、画面细节讨论**

### 当前已确认结论

#### 1. FFmpeg 还没装
本机实测:
- `ffmpeg: command not found`

这说明当前还不能直接在本机稳定做视频抽帧 / 转码 / 取关键帧。

#### 2. Gemma 4 31B 文本链路已可用
已确认:
- `nvidia/google/gemma-4-31b-it` 可被当前 OpenClaw / NVIDIA 接口成功调用做文本测试
- 该模型也已加入当前模型列表下拉菜单

#### 3. 但 OpenClaw 里它还没有真正接成"视觉模型"
本机实测 `image` 工具时:
- `nvidia/google/gemma-4-31b-it` 当前被识别为 `input: text`
- 因此 `image` 工具直接报:`Model does not support images`

这说明:
> **只安装 FFmpeg 还不够;还必须把 Gemma 4 31B 在当前配置里正确声明为支持图像输入,才能真正形成"视频抽帧 → 视觉分析"的链路。**

### 方案判断

#### 为什么这条线值得做
如果打通,这条能力可以支持:
- 看短视频 / 电影片段时一起聊画面
- 指定某一段让我解释"刚才画面里发生了什么"
- 结合字幕/台词(后续可选)做更完整的片段理解
- 后续还能扩展到截图分析、视频摘要、镜头回顾

#### 当前不要高估的部分
第一阶段不追求:
- 连续整片实时逐帧观看
- 边放边无延迟同步评论
- 直接把完整视频长期塞进主会话上下文

第一阶段更适合定义为:
> **可控抽帧 + 片段分析 + 陪看式讨论**

### 推荐实施顺序

#### 第一步:安装 FFmpeg
目标:让本机具备稳定的视频处理基础能力。

用途包括:
- 按时间点抽帧
- 按固定间隔抽帧
- 压缩/裁剪测试片段
- 为后续音视频辅助流程提供基础依赖

#### 第二步:把 Gemma 4 31B 正确接成视觉模型
目标:让 `nvidia/google/gemma-4-31b-it` 在 OpenClaw 当前配置中被识别为支持:
- `text`
- `image`

当前推断需要检查 / 修正的位置:
- `~/.openclaw/openclaw.json` 中 `models.providers.nvidia.models[]`
- 必要时同步确认 `agents.defaults.models` 的可选目录项
- 修完后用 `image` 工具做最小图片理解验证

#### 第三步:做最小视频抽帧脚本
目标:先得到一个不碰主链路、可单独验证的最小脚本。

建议支持三种输入方式:
1. 每隔 N 秒抽一帧
2. 指定时间点抽帧
3. 先只分析一个短片段(例如 10~30 秒)

输出应尽量简单:
- 抽出的关键帧文件
- 每帧时间点
- 供模型读取的图片列表

#### 第四步:做"陪看片段分析"的最小链路
链路建议:
1. 用户给视频或指定片段
2. FFmpeg 抽关键帧
3. Gemma 4 31B 看这些帧
4. 返回:
   - 这一段大概发生了什么
   - 画面主体/人物/动作
   - 是否有明显情绪或场景变化

第一版不追求花哨 UI,先追求:
- 能跑
- 稳定
- 不误伤 OpenClaw 主体

### 稳定性边界
这条方案必须继续遵守用户已经明确过的原则:
- **OpenClaw 主体稳定性优先**
- **能旁路验证就旁路验证**
- **能隔离就隔离,不先碰主链路**
- **先验证短片段,不直接上长视频/整片**

因此推荐做法是:
- 前期以独立脚本 / 隔离测试为主
- 验证通过后,再考虑是否封成正式入口
- 默认不要先改主会话默认模型

### 周一继续时的接续点
下次继续时,按这个顺序接最省:
1. 安装 `ffmpeg`
2. 修 `nvidia/google/gemma-4-31b-it` 的 image capability
3. 用一张静态图片做视觉验证
4. 再拿一个短视频片段做抽帧 + 分析 smoke test

### 一句话结论
> **这条"FFmpeg + Gemma 4 31B 视觉陪看片"方案是可行方向,但要分成两层来做:先补视频处理能力(FFmpeg),再把 Gemma 4 31B 真正接成视觉模型;只有两层都打通,贾维斯才算真正具备"陪你看电影片段"的基础能力。**

---

## 2026-05-15:infos-handle 插层路线(broker 数据中心纯化)

### 背景

用户在 2026-05-15 11:40(Asia/Shanghai)进一步把长期方向说得更具体:

- broker 应真正退到"数据中心 / 数据层"角色
- 在 broker 与具体消费方之间,再加一层暂名 `infos-handle`
- 以后无论是 Control UI、别的平台、CLI、本地脚本,还是文字 / 图片 / 音频返回,都尽量通过 `infos-handle` 取数与处理,而不是直接啃 broker 原始状态和当前前台主会话细节
- Control UI 只是一个 renderer / consumer,不应继续表现成默认唯一承载层
- 即使将来把 Control UI 整个删掉,broker 也不应因为缺少 UI 而报错;最多只是"没人消费,所以没有可见反馈"

这条要求与 2026-05-14 已确认的"工作层 / 数据层 / 渲染层"路线一致,但比昨天更进一步:

> 不只是让 broker 先成为 sidecar 数据源,而是明确补出一个"信息处理 / 分发层"。

### 当前代码与结构的真实耦合点(2026-05-15 实地核对)

#### 1. broker 当前仍同时承担"数据"和"前台投递"

`scripts/openclaw-frontstage-broker.py` 现在的关键现实是:

- `emit_frontstage()` 内部直接调用 `openclaw-supervisor-subagent.py send-frontstage`
- `emit_event(...)` 会在 `emit_frontstage()` 成功后,才把结果记成 broker record,并顺手 rebuild views

也就是说,当前 broker 还不是纯数据中心,而是:

- 接事件
- 去重
- 发前台
- 写已发记录
- 重建视图

这对当前"辅助消息能打回 dashboard"很实用,但职责还不够纯。

#### 2. 当前事件日志主要记录的是"已成功投递",不是"原始 source 事件"

当前 README 已明确:

- `events.jsonl` 记录的是 `frontstage.delivery.sent`
- 它描述的是 broker 已经成功完成的一次前台投递
- 而不是 source watcher 的原始状态变化镜像

因此当前 broker 数据层仍偏"delivery-first",还没完全到"source-of-truth first"。

#### 3. Control UI 当前已开始读 broker snapshot,但仍不是纯 renderer

`scripts/apply-openclaw-control-ui-branding.py` 当前已经把顶部"前台状态"小入口接成:

- 优先读取 `/jarvis-frontstage-snapshot.json`
- `jarvis-frontstage-status.json` 只保留兼容别名

说明:

- Control UI 已经开始消费 broker snapshot
- 但它仍深度依赖 Gateway / `chat.history` / live chat 主链
- 因此当前只能说"辅助状态区逐步在 renderer 化",还不能说"Control UI 已彻底变成 broker consumer"

#### 4. watcher/source 现在默认仍把 broker 当"前台统一投递入口"

例如:

- `scripts/openclaw-frontstage-recovery-watch.py` 在 anomaly / recovered 时,直接调用 `openclaw-frontstage-broker.py emit`
- `scripts/openclaw-supervisor-status.py` 也是通过 broker 发前台

所以当前 broker 对 source 来说,不只是数据层,还是"带前台投递副作用的入口"。

### 我们现在认定的四层结构

基于当前目标,后续统一按这四层理解,而不是继续把 Control UI 和 broker 混成两层:

1. **工作层 / runtime layer**
   - Gateway / agent runtime / sessions / transcript / watcher / cron / subagents
   - 负责真正产生状态、事件、任务、会话
2. **数据层 / broker layer**
   - 负责统一事件、统一快照、统一查询源
   - 不因为缺少 renderer 或缺少 infos-handle 而报错
3. **信息处理层 / infos-handle layer**
   - 负责接请求、取数据、组结果、选输出形式、决定发给谁
   - 这是本轮新增补出来的中间层
4. **渲染 / 消费层 / renderer-consumer layer**
   - Control UI / WebChat / CLI / 本地脚本 / 图片卡片 / 音频返回 / 其他平台

一句话职责定义:

- **broker 负责"存事实"**
- **infos-handle 负责"把事实变成结果"**
- **Control UI 负责"显示结果"**

### infos-handle 的职责边界

`infos-handle` 当前建议先定义成一个**窄职责版本**,不要一上来就变成"另一个 Gateway"或"另一个主对话状态机"。

#### 它应该做的

1. 接收请求
   - chat 请求
   - CLI 请求
   - 本地 HTTP/API 请求(后续)
   - 其他平台消费请求(后续)
2. 读取数据
   - 优先从 broker snapshot / broker events 读取
   - 必要时补读少量 runtime 状态(例如 session 活跃态)
3. 组织结果
   - 过滤
   - 聚合
   - 摘要
   - 对话式解释
   - 结构化 JSON 输出
4. 选择输出形式
   - `text`
   - `json`
   - 后续再补 `image` / `audio`
5. 选择投递方式
   - stdout / 文件
   - frontstage / chat session
   - 其他消费方(后续)

#### 它当前不该做的

- 不接管 OpenClaw 主会话状态机
- 不替代 Gateway transcript 主链
- 不一上来承诺完整跨平台对话一致性
- 不要求 Control UI 先整体重写后才能存在

### 目标状态(分层后的理想数据流)

```text
[工作层 / runtime]
  supervisor / local-health / recovery / transcript / sessions / tasks
            ↓
[broker / 数据层]
  原始事件、规范化事件、快照、查询源
            ↓
[infos-handle / 信息处理层]
  取数、解释、聚合、选格式、选投递方式
            ↓
[renderers / consumers]
  Control UI / WebChat / CLI / 本地脚本 / 图片 / 音频 / 其他平台
```

### 稳定性红线(这条路线必须遵守)

1. **OpenClaw 主体稳定性优先**
2. **broker 当前仍必须保持 sidecar / 弱依赖形态**
3. **没有 Control UI 时,broker 仍应可运行**
4. **没有 infos-handle 时,broker 也应可单独留下事件与快照**
5. **当前阶段不重写主聊天链**
6. **先做 text/json,再做 image/audio;不要一口气上多模态**

### 当前推荐实施顺序

#### Phase 0:先冻结契约和边界(本阶段立即做)

目标:先把名字、职责、边界定清楚,避免一边写代码一边改口径。

本阶段产出:

- 这份方案(当前章节)
- `infos-handle` 的最小职责说明
- broker / infos-handle / renderer 的边界与非目标

#### Phase 1:先把 broker 纯化成"数据中心优先"

目标:让 broker 先更像数据中心,而不是"默认会直接发前台的投递器"。

建议最小改动:

1. broker 内部把两类事件显式区分:
   - `source event`:原始或规范化来源事件
   - `delivery event`:实际投递结果
2. 新增或明确一条**不带前台副作用**的 ingest 路径
   - 例如 `ingest` / `append-source-event` 之类动作
   - 只负责写事件、更新快照、重建视图
3. 现有 `emit` 保留兼容
   - 继续给旧 watcher 用
   - 但语义上标成兼容层,而不是未来正式主入口
4. `publish_frontstage_status(...)` 这类 Control UI 公共副本发布应保持**best-effort**
   - 有 Control UI dist 就发布
   - 没有就跳过,不把 broker 判失败

本阶段验收:

- 删除或暂时拿走 Control UI dist 后,broker 的 ingest / rebuild 仍可通过
- broker 仍能输出 `events.jsonl` / `snapshot.json` / `manifest.json`
- 没有 renderer 时,broker 不因"无人消费"报错

#### Phase 2:做一个最小 infos-handle(只做 text/json)

目标:先让 infos-handle 成为"能收请求、能取数、能回 text/json"的信息处理层。

建议最小文件:

- `scripts/openclaw-infos-handle.py`

建议最小 action:

1. `query`
   - 读取 broker snapshot / events
   - 输出 `json` 或 `text`
2. `notify-frontstage`
   - 仍可调用现有 frontstage 投递适配器
   - 但这是 infos-handle 的职责,不再属于 broker 核心职责
3. (后续再补)`render-image` / `render-audio`

建议最小 request kind:

- `snapshot.summary`
- `health.summary`
- `tasks.summary`
- `recovery.summary`
- `events.recent`

建议最小输出格式:

- `--format json`
- `--format text`

本阶段验收:

- `python3 scripts/openclaw-infos-handle.py query --kind snapshot.summary --format json`
- `python3 scripts/openclaw-infos-handle.py query --kind tasks.summary --format text`
- 在没有 Control UI 的情况下,这些请求仍能正常返回

#### Phase 3:把"前台投递"从 broker 迁到 infos-handle

目标:让 broker 更纯,让 infos-handle 开始承担"如何把结果送出去"的职责。

建议顺序:

1. 新 watcher / 新入口优先调用 infos-handle
2. infos-handle 内部:
   - 先调 broker ingest / query
   - 再决定是否 `notify-frontstage`
3. 旧 watcher 继续允许调用 broker `emit`
   - 直到迁完再收兼容层

本阶段验收:

- `frontstage-recovery` 或 `supervisor` 其中一条链先切到 infos-handle 路由
- 当前 dashboard 仍能收到消息
- broker 仍能留下数据,即使前台投递失败

#### Phase 4:Control UI 逐步改成 infos-handle / broker 的 consumer

目标:让 Control UI 在辅助状态层面变成真正的 consumer,而不是继续承载太多中间逻辑。

当前只做:

- 辅助状态区 / 状态 dock 继续优先读取 broker snapshot
- 若后续需要请求式摘要,可让 dock 调 infos-handle 的 text/json 接口

当前不做:

- 不重写聊天主链
- 不试图让 Control UI 立刻脱离 Gateway live chat 机制

#### Phase 5:再补 image / audio / 本地解析

目标:等 infos-handle 的 text/json 稳定后,再补多模态。

可后续支持:

- `--format image`
- `--format audio`
- `--format file`
- 本地 parser / 本地 renderer 输入

这一步必须后置,避免现在就把复杂度拉高。

### 第一批建议立刻实现的东西(安全顺序)

1. broker 增加**纯 ingest 路径**,不带前台投递副作用
2. broker 把 `source event` 与 `delivery event` 分离
3. 新建 `scripts/openclaw-infos-handle.py`,先只支持:
   - `query snapshot.summary`
   - `query health.summary`
   - `query tasks.summary`
   - `query recovery.summary`
   - `notify-frontstage`(复用现有 frontstage 解析与 inject 适配器)
4. 给 infos-handle 加最小测试 / smoke
5. 保持现有 Control UI dock 不变,先不碰聊天主链

### 当前一句话结论

> 这条路线是可行的,而且是比"继续堆 Control UI 补丁"更接近长期正确结构的路线;但正确起手式不是立刻重写 UI,而是先把 broker 纯化,再补一个最小 infos-handle,把"取数据 / 解释请求 / 选输出 / 选投递"从 broker 和 Control UI 之间剥出来。

### 当前实现进度(截至 2026-05-15 17:50)

当前已经完成:

1. **Phase 1 的主体已站稳**
   - `scripts/openclaw-frontstage-broker.py` 已有:
     - `ingest`
     - `record-delivery`
   - 当前 broker 事件流已明确区分:
     - `broker.source.event`
     - `frontstage.delivery.sent`
   - `views/frontstage.json` / `snapshot.json` 已有 `sourceStates` / `sourceStateSnapshots` 这类"最近已 ingest 来源状态"字段
   - broker 契约当前已能从 `contract.catalog` 直接读到;当前 `brokerContractVersion=2`

2. **Phase 2 的最小 infos-handle 已从 contract-first 查询层继续推进到"统一信息处理层最小版"**
   - 已新增:`scripts/openclaw-infos-handle.py`
   - 当前已支持:
     - `query --kind snapshot.summary|health.summary|tasks.summary|recovery.summary|panel.inspect|panels.catalog|sources.latest|sources.catalog|source.inspect|events.recent|contract.catalog`
     - `notify-frontstage`
     - `handle`(统一正式请求入口)
   - 其中:
     - `query` 仍是低风险兼容入口,只支持 `--format text|json`
     - `handle` 现在统一支持 `--format text|json|image|audio`
   - `contract.catalog` 当前会公开:
     - `queryCatalog`(各 query kind 的格式/必填参数/默认 limit)
     - `queryCatalog.outputFormatCatalog`(当前 `text/json=ready`、`image/audio=preview`)
     - `requestCatalog`(统一 `handle` 入口、request/response shape、delivery matrix、`request_json / request_file` 输入模式,以及 `response_file` 单次响应输出模式;当前还额外公开 `preferredRequestInputMode=request_file`、`preferredRequestFileValue=-`、`preferredResponseOutputMode=stdout` 与 `clientHelperModule=openclaw_infos_handle_contract.py`)
     - `handlerCatalog`(当前 stdout / image summary-card / audio local-tts handler)
     - broker 的 `contracts.recordTypes / contracts.eventFieldCatalog`
     - `queryContractVersion=17`
     - `requestContractVersion=6`
   - source 相关 query 的推荐读取顺序现已明确:先读 `sources.latest` 做轻量 inventory / handoff,再在需要 raw latest snapshots / contract 时读 `sources.catalog`,最后只在深挖单个 source 时读 `source.inspect`
   - `sources.latest` 现在除了保留原始 `sourceStateSnapshots / sources` keyed snapshot 外,也会额外暴露 `count / availableSources / sourceItems[]`,把每个 source 的最近摘要收成与 `sources.catalog / source.inspect` 更一致的稳定 item shape;其中已包含 `latestEventItem / latestDeliveryItem`
   - `sources.catalog` / `source.inspect` 当前已补齐稳定顶层字段(如 `latestEventAt`、`latestRecordType`、`latestEventSummary`、`latestEventKey`、`latestSourceStateSummary`、`latestDeliveryMessage`、`latestDeliveryEventKey`、`latestDeliveryRecordType`),减少消费方解析嵌套对象的成本
   - `sources.catalog` 现在会同时补 `latestEventItem / latestDeliveryItem`,把最近一条 source 相关事件和最近一条 delivery 都压平成稳定 item shape(`recordType / summary / checkedAt / reportStatus / deliveryStatus` 等),方便 handoff / 排查脚本直接消费
   - `source.inspect` 还会稳定暴露 `recentDeliveryCount`、`latestEventItem`、`latestDeliveryItem`、`recentEventItems[]` 与 `recentDeliveryItems[]`;消费方优先读这些 item shape,就不必直接解析 `recentEvents[]` 或 `latestDelivery` 原始对象
   - `events.recent` 现在也会稳定暴露 `count / latestEventAt / availableSources / sourceEventCount / deliveryCount / recordTypeCounts / eventItems[] / latestBySource / latestBySourceItems[]`;其中 `latestBySource` 保留 keyed object 便于按 source 直取,`latestBySourceItems[]` 则提供按 `latestEventAt desc` 排好的稳定摘要顺序,handoff / 排查脚本优先读这些稳定字段,不必再直接翻原始 `events[]`
   - `panel.inspect` / `panels.catalog` 也已纳入同一份 `queryCatalog`
   - `handle --format image` 现在会生成低风险 `summary-card SVG` artifact
   - `handle --format audio` 现在会走现有本地 `tools/voice-reply/voice-reply.sh` / ChatTTS 链路;测试里可通过 stub renderer 验证返回契约
   - `handle --delivery-mode frontstage` 现在也能覆盖 `image/audio`:先产出 artifact,再发一条 text artifact notice 到前台,并同时返回稳定 artifact 元数据
   - `image/audio` 的 frontstage artifact-notice 合同已进一步收口:消费方优先读取 `response.delivery.notice / response.delivery.frontstage`;旧 `artifactNotice / metadata` 仅保兼容别名
   - `handle` 现已允许可选 `brokerStateDir / brokerDataDir` 覆盖,便于把 artifact-notice 元数据一并走 broker ingest / delivery 回归,而不污染默认本地状态目录
   - `handle` 现也支持 `--request-file <path|->`,作为低风险文件 / stdin 单次请求入口;同时补了 `--request-id` / `--response-file <path>`,让单次 CLI 调用也能走更正式的 request/response envelope,而不引入常驻服务
   - 为避免每个 caller 手搓命令 / 解析返回,已补一个很薄的 `scripts/openclaw_infos_handle_contract.py` request client helper;broker compat emit、supervisor、frontstage-recovery、local-health 这几条真实 caller 开始共用它,统一走 `handle --request-file -`;本轮又把它补成同时支持 `request_file + response_file` 这一跳最小正式入口;后续又继续补了 `invoke_handle_query()` 与 `extract_handle_response_snapshot()`,把 query consumer 也拉到同一条正式 request/response envelope 上;这次再继续收口后,`extract_frontstage_notify_payload()` 与 `build_compat_delivery_bundle()` 也一并纳入正式 helper 公开面,watcher notify adapter 与 broker compat emit 直接复用同一份 contract helper,不再各自留一套返回解析
   - 已新增最小回归:`scripts/test-openclaw-infos-handle.py`(已覆盖 `handle --format json/image/audio` smoke、image/audio frontstage artifact-notice smoke、`--request-file` 入口、以及 `--response-file` 响应出口)

3. **Phase 3 已开始,且已有真实迁移点**
   - broker 当前对 canvas / Control UI 公开副本发布也已进一步收成 `best_effort`;即使这些前端副本发布失败,也不应阻塞 `views/*.json` 与 `manifest.json` 继续重建
   - broker `emit` 当前也已进一步压成更明显的 legacy compatibility wrapper:前台发送优先经 `infos-handle handle`,broker 自己只保 delivery 兼容记录;新能力优先落到 infos-handle;本轮又继续收口为直接走 request envelope(`--request-file -`),且已开始复用统一 request helper;同时 `frontstageSource / frontstageEventKey / brokerStateDir / brokerDataDir` 也透传进 `handle` 主请求面,优先复用 infos-handle 内部 broker ingest / delivery 记录
   - `scripts/openclaw-supervisor-status.py`
   - `scripts/openclaw-frontstage-recovery-watch.py`
   - `scripts/openclaw-local-health-diagnose.py`
   - 上面三条链之前已从"直接调 broker emit"改成先走 `infos-handle notify-frontstage`
   - 旧 `notify-frontstage` compat 入口本轮也已继续弱化:内部改成走 `handle` 主请求面,再回吐兼容 payload,避免再长平行逻辑
   - 当前又继续往前推了一小步:这三条 caller 已迁到 `infos-handle handle --delivery-mode frontstage --format text`,并在本轮继续统一收口为直接发送 stdin request envelope(`--request-file -`);同时它们与 broker compat emit 现在都会稳定带上 `requestId`
   - 为了保兼容,caller / broker compat consumer 侧额外补了一层很薄的返回适配:优先吃 `handle.response.delivery.notice / frontstage / artifactRef`,旧 `notify-frontstage` payload 与 `delivery.notify` 只保回退;本轮又把 adapter 的归一结果补成 `deliveryNotice / frontstageDelivery` 稳定 alias
   - 其中 `supervisor / frontstage-recovery / local-health` 这三条当前也会把结构化 `data-json` 一并 ingest 进 broker
   - 这意味着:前台投递的直接调用点已进一步从旧 notify convenience route 往统一 `handle` route 收拢;同时 `scripts/openclaw-post-upgrade-self-check.py` 也开始经 helper 走 `handle --request-file -` 查询 `contract.catalog`,成为一个真实 non-delivery consumer
   - 下一步更自然的迁移点是:继续找剩余 caller / consumer,或者给 `handle` 补更正式的 artifact / richer delivery,而不是再扩旧 `notify-frontstage`

4. **当前停点与验证**
   - 当前代码停点提交见 `git log --oneline -1`
   - 这一串关键提交已继续推进到当前这版最终收口停点;更早的主线提交依次是:`2f57998` → `a862517` → `45258f1` → `e7095d8` → `4de50fb` → `2575456` → `ff07c2f` → `7fe7efd` → `3aa091e` → `eb8aa4f` → `7396ede`
   - 当前最小核验保持全绿:
     - `python3 -m py_compile scripts/openclaw-infos-handle.py scripts/test-openclaw-infos-handle.py scripts/openclaw-frontstage-broker.py scripts/test-frontstage-broker.py`
     - `python3 -m py_compile scripts/openclaw-supervisor-status.py scripts/openclaw-frontstage-recovery-watch.py scripts/openclaw-local-health-diagnose.py scripts/test-frontstage-recovery-watch.py scripts/test-infos-handle-frontstage-callers.py`
     - `python3 scripts/test-frontstage-broker.py`
     - `python3 scripts/test-openclaw-infos-handle.py`
     - `python3 scripts/test-frontstage-recovery-watch.py`
     - `python3 scripts/test-infos-handle-frontstage-callers.py`
     - `python3 scripts/openclaw-infos-handle.py query --kind contract.catalog --format json`
     - `python3 scripts/apply-openclaw-frontstage-broker-data.py`
   - `apply-openclaw-frontstage-broker-data.py` 现在也会顺手走一遍 `handle --request-file ... --response-file ...` 的正式入口 smoke,且已迁到直接复用 `openclaw_infos_handle_contract.py` helper,作为新的真实 consumer / 验证入口

当前继续不做、但已不阻塞本轮收口:

- `image/audio` 虽已有 preview handler 与更稳定的 frontstage artifact-notice 合同,但还没有 richer renderer / real artifact transport(例如多模板图片卡片、音频直接投递队列、失败回退策略)
- Control UI 对 infos-handle 的直接消费尚未开始
- broker 仍保留 `emit` 兼容入口
- infos-handle 还没有独立 HTTP / SSE / WebSocket 请求入口

因此当前判断应是:

- **Phase 1:已基本落地,且 renderer 发布已进一步 best_effort 化**
- **Phase 2:已从"纯查询契约层"推进到"统一 request + preview handler + 最小 artifact-notice delivery"这一步,并已正式稳定**
- **Phase 3:本轮收口已达到可称"最终版"的状态**:`handle --request-file` + `openclaw_infos_handle_contract.py` helper 已成为正式主入口;新增 caller / consumer 已统一优先走这条主路径;broker 只保 sidecar 数据层 + compat 壳;剩余项属于下一阶段增强,不再阻塞本轮结束

## 2026-05-14:工作层 / 数据层 / 渲染层分层路线(当前先升级 broker 为数据源)

### 背景

用户提出一个长期方向:希望把当前系统逐步分成三层:

1. **工作层**:即使没有前端渲染和正式数据层,也尽量能独立运作
2. **数据层 / broker 层**:作为统一状态源与事件源;没有工作层或渲染层时也能单独存在,不因为缺少其他层而报错
3. **渲染层**:当前可以是 Control UI,未来应允许把"对话部分 / 信息返回部分"接到其他平台

但用户同时又明确收紧当前阶段目标:

> **短期先不要全面拆三层,先把 broker 升级成真正的数据源;其他层先规划,不先落地。整个路线必须以 OpenClaw 主体稳定运行为第一原则。**

### 当前结构判断

当前 OpenClaw 真实结构大致是:

- **工作能力**:Gateway / agent runtime / `chat.send` / `cron` / `subagents` / 各类本地 watcher 脚本
- **数据来源**:session JSONL、`sessions.json`、`chat.history` 投影、`~/.local/state/openclaw/*` 下的各类状态文件
- **渲染层**:Control UI / WebChat,通过 Gateway WS、`chat.history`、`chat.inject`、live `chat` events 做显示

当前已经存在的 `scripts/openclaw-frontstage-broker.py` 更像"辅助消息统一投递器 + 去重器",还不算真正的数据层。

### 与现有方案/实现的关系(冲突检查)

#### 已有可复用能力

当前仓库里已经有这些与目标直接相关的基础件:

- `scripts/openclaw-frontstage-broker.py`
- `scripts/openclaw-supervisor-status.py`
- `scripts/openclaw-local-health-diagnose.py`
- `scripts/openclaw-frontstage-recovery-watch.py`
- `docs/通用-OpenClaw-补丁注册表.md`
- `docs/通用-OpenClaw-补丁重建清单.md`

这些说明:我们并不是从零开始,而是已经有了"事件源 / 状态源 / 投递器"的雏形。

#### 当前不宜直接做的事

为了稳定性,当前阶段**不推荐**:

- 直接重写 OpenClaw Gateway 的会话/转录主链
- 直接把 Control UI 改造成新的唯一数据中枢
- 直接把 broker 变成"必须存在,否则工作层报错"的硬依赖
- 直接重构成三层完全强隔离架构

原因:这些动作都会显著提高对上游大版本变化的脆弱度,也更容易影响 OpenClaw 主体稳定性。

#### 当前最稳的切口

最稳的路线是:

> **把 broker 先升级成 sidecar 数据层。**

也就是:

- 先不拆 OpenClaw 主体
- 先不替换 Control UI
- 先把 broker 从"辅助消息收口器"升级为:
  - 统一事件入口
  - 统一状态快照层
  - 统一查询源
  - 统一渲染数据源

这样后续无论要接新的前端,还是继续保留 Control UI,都有一个比较稳的中间层。

### 可行度评估(以稳定性优先为前提)

#### A. broker 升级成数据源(当前阶段目标)

- **可行度:高(约 85%)**
- 原因:当前已有 broker、watcher、状态文件与 systemd 链路,属于增量演进,不需要硬拆 OpenClaw 主体

#### B. 让 Control UI 变成 broker 的一个 renderer

- **可行度:中高(约 70%)**
- 原因:当前 Control UI 仍深度依赖 Gateway `chat.history` / live `chat` 事件;可以逐步把"辅助状态渲染"先改成读 broker,但不适合一口气替掉对话主链

#### C. 让"任意平台都能渲染同一份数据"

- **可行度:中(约 60%)**
- 原因:辅助状态与结构化信息比较容易跨平台;完整对话、流式输出、工具阶段、会话恢复这些要做到平台无关,后续还需要定义更稳定的数据契约

#### D. 三层完全硬隔离、任一层缺失都不报错

- **可行度:中偏低(约 45%)**
- 原因:OpenClaw 当前天然是 Gateway + transcript + UI 投影耦合模型;可以逐步做成"弱依赖/可降级",但短期不宜承诺彻底三层硬拆

### 当前阶段目标(只做 broker)

#### 目标

把 broker 从"辅助消息统一发回前台"升级成:

1. **统一事件入口**
2. **统一状态快照层**
3. **统一渲染数据源**
4. **继续保留当前 frontstage 投递能力**

#### 非目标

当前阶段先**不做**:

- 全面重写 Control UI
- 改造 OpenClaw Gateway 会话主链
- 把工作层强行重构成完全独立运行框架
- 做复杂跨平台渲染器矩阵

### broker 升级路线(推荐)

#### Phase 1:事件化(最小增量)

把当前 supervisor / local-health / frontstage-recovery 这些来源统一写成结构化事件。

建议最小事件类型:

- `supervisor.status.changed`
- `local_health.status.changed`
- `frontstage_recovery.status.changed`
- `frontstage.delivery.sent`
- `frontstage.delivery.failed`

建议最小产物:

- `~/.local/state/openclaw/broker/events.jsonl`
- `~/.local/state/openclaw/broker/views/frontstage.json`
- `~/.local/state/openclaw/broker/views/health.json`
- `~/.local/state/openclaw/broker/views/tasks.json`

#### Phase 2:快照化

让 broker 不只保留"最近一次每个 source 的消息",而是维护一份可被 UI 或其他平台消费的统一当前状态。

例如:

```json
{
  "frontstage": {...},
  "supervisor": {...},
  "localHealth": {...},
  "recovery": {...},
  "updatedAt": "..."
}
```

#### Phase 3:渲染数据源化

在不改对话主链的前提下,让 Control UI 的辅助信息、状态卡片、后续的新页面优先读 broker 快照,而不是各脚本各读各的状态文件。

#### Phase 4:后续预留(本阶段不落地)

以后如果继续推进,再考虑:

- broker 提供 SSE / WebSocket / HTTP 读取接口
- Control UI 把部分辅助状态渲染从直连脚本状态文件切到 broker
- 新平台 renderer(网页看板 / 移动端面板 / 其他消息面)直接消费 broker 数据

### 稳定性红线

当前路线必须继续遵守:

1. **OpenClaw 主体稳定性优先**
2. **broker 当前应保持 sidecar / 旁路演进,而不是反向绑死主链**
3. **没有 broker 时,OpenClaw 主体仍应可正常工作**
4. **没有新的 renderer 时,broker 自己也应可单独运行并留下状态,不因为无人消费而报错**
5. **当前阶段任何改动都不应要求重写 Control UI 对话主链**

### 当前推荐结论

短期最正确的路线不是"立刻拆完三层",而是:

> **先把 broker 升级成真正的数据源;把工作层和渲染层的全面分离先停留在规划层。**

这条路线的好处是:

- 与当前 watcher / supervisor / local-health / frontstage 方案兼容
- 对 OpenClaw 主体风险最小
- 后续要接任意平台时,也终于有一个不必直接啃 Control UI 内部状态机的中间层
- 即使未来 OpenClaw 大版本变化,只要 broker 数据契约保持稳定,就更容易逐项恢复结果

### 下一步(当前只建议,不在本方案里默认立即落地)

1. 先定义 broker 事件模型与视图模型
2. 先把现有三个 watcher 源统一进 broker 事件流
3. 先做 broker 快照文件
4. 再考虑让 Control UI 的辅助状态读取 broker
5. 对话主链 / 完整三层硬隔离,留作后续阶段再评估

### 2026-05-14 下班前最后 30 分钟执行拆分(本轮实际要做)

目标:优先继续收口"前台一点点回复、随后又突然消失"这条问题,尽量在不大拆 OpenClaw 主链的前提下,把**漏报**与**突然消失体感**再往下压一层。

#### Part A:继续定位 runtime / silent turn 的上游来源(预计 10 分钟)

要做:

- 确认 `Continue the OpenClaw runtime event.` 这类 internal runtime 事件的来源与预期语义
- 判断它在当前 direct chat / Control UI 直聊里,是否本来就不应向前台产生可见阶段性文本
- 查明这类 turn 是"本该完全静默,却漏出了 draft",还是"final silent 但中途文本先被前端暂存"

最小验收:

- 至少拿到一个更明确的归因结论:是上游 silent 语义泄漏,还是前端 live/render 合并策略问题

#### Part B:继续收紧 Control UI 前端收口逻辑(预计 10 分钟)

要做:

- 在当前已补的"silent/empty final 不立刻强制 reload history"基础上,再看是否还有别的本地 optimistic / chatStream / toolStream 清空路径会导致 ghost/disappear
- 坚持只做最小补丁,不扩成大改前端状态机

最小验收:

- dist 中能明确指出当前 patch 覆盖到的具体分支
- 若再补一刀,也必须能通过最小字符串/现场检查确认已生效

#### Part C:把恢复观察与前台补丁的联动收口(预计 5 分钟)

要做:

- 确认 `assistant_turn_missing_visible_text` 已进入 watcher 的长期链路与文档说明
- 确认 recovery watcher timer 频率调整已生效
- 必要时补一条很短的维护记录,避免后续忘记这次为什么加这类判定

最小验收:

- watcher 回归保持 `ALL PASS`
- timer 处于 active(waiting)

#### Part D:最后 5 分钟只做总结,不再继续扩改(预计 5 分钟)

要做:

- 停止继续新改动
- 汇总:已修、未修、当前边界、下次优先顺序
- 给出用户可理解的一版阶段结论

### 一句话结论

> **这条分层路线是可行的,但当前最稳的做法不是全面开拆,而是先把 broker 升级成 sidecar 数据层;其他层先规划,不先落地,并始终以 OpenClaw 主体稳定运行为第一要求。**

### 2026-05-14 当前结论:broker 算不算"最终完成版"?

不算长期意义上的"最终完成版",但**算当前阶段目标下可交付的 broker sidecar 数据层 1.0**。

当前已完成:

- `events.jsonl` / `manifest.json` / `views/frontstage.json` / `views/health.json` / `views/tasks.json` / `views/recovery.json`
- `rebuild-views` 正式入口
- `scripts/apply-openclaw-frontstage-broker-data.py`
- `scripts/test-frontstage-broker.py`
- user systemd 周期重建 timer
- `freshness` 元数据与真实 `rebuild` 时间语义
- 补丁注册表 / 重建清单 / README / 维护说明

因此:

- **若按"先把 broker 升成 sidecar 数据源"这个阶段目标看:可以视为已完成。**
- **若按长期目标看:还不是最终版。**

### 明天继续时 broker 还剩什么(优先级顺序)

#### 1. 事件契约正式化(优先级:高)

当前 `events.jsonl` 已可用,但还更像"已发事件日志 + source 回填"。
明天若继续 broker,本轮最值得先补的是把事件类型收成更明确的正式契约,例如:

- `supervisor.status.changed`
- `local_health.status.changed`
- `frontstage_recovery.status.changed`
- `frontstage.delivery.sent`
- `frontstage.delivery.failed`

目标:以后 renderer / 排查脚本不要再靠 source 名和临场猜字段语义。

#### 2. 统一快照模型再收一轮(优先级:高)

当前已有 `frontstage / health / tasks / recovery` 四个 view,但还缺一份更明确的"统一当前状态"口径。
明天可继续考虑是否要补一个更聚合的顶层 snapshot,统一表达:

- frontstage
- supervisor
- localHealth
- recovery
- updatedAt / freshness

目标:让后续 renderer 更容易直接消费。

#### 3. source → broker 事件流的映射再顺一轮(优先级:中)

当前来源已经能写进 broker,但还可以继续把:

- source 状态文件字段
- broker 事件字段
- broker view 字段

之间的对应关系再收紧,减少"同一语义在三处名字不完全一样"的情况。

#### 4. renderer 读取 broker 的辅助状态(优先级:中,仍不碰主对话链)

这一步不是明天必须做,但如果 broker 要继续往"数据源"走,最自然的下一步会是:

- 让 Control UI 的**辅助状态区**优先读 broker
- 不是去改聊天主链,不碰 `chat.history` / live 主回复链路

目标:只让辅助状态先吃 broker,不扩大风险面。

#### 5. SSE / WebSocket / HTTP 读取接口(优先级:低,后置)

这个属于更后面的正式数据层能力,当前不应抢在前台稳定性问题之前做。

### 明天继续的建议口径

如果明天继续 broker,最合理的开工顺序是:

1. 先确认今天这版 broker 1.0 仍全绿
2. 先做事件契约正式化
3. 再收统一快照模型
4. 只在不碰主对话链的前提下,评估辅助 renderer 是否开始读 broker
5. SSE / WebSocket / HTTP 接口继续后置

---

## 2026-05-22：贾维斯视觉识别能力调研

### 目标
为贾维斯增加视觉识别相关功能，使其能分析和理解摄像头画面、图片内容。

### 候选方案

| 方案 | 路线 | 成熟度 | 开销 |
|------|------|--------|------|
| YOLO（目标检测） | `ultralytics/ultralytics`，一行 pip install | 极高 | 低（CPU 可跑 nano 模型） |
| Moondream（轻量 VLM） | `vikhyat/moondream`，小型视觉语言模型 | 高 | 低 |
| 现有 image tool | OpenClaw 已有图片分析能力（image model） | 已部署 | 零 |

### 关键发现
- Ultralytics 已统一到 YOLO26（v8.4.0），支持检测/分割/姿态/分类
- GitHub topics/yolov8 下有 25+ 社区项目（车辆检测、口罩检测、武器检测、人脸考勤等）
- 纯 CPU 可用的最小模型仅 ~5MB，推理速度可满足实时

### 当前决策
**暂不推进。** 贾维斯已有 image tool 可分析图片，当前需求场景下够用。YOLO/目标检测类能力适合"实时摄像头画面识别"等场景，等后续有明确的应用驱动再启动。

### 复活入口
- 官方仓库：`github.com/ultralytics/ultralytics`
- 安装：`pip install ultralytics`
- 最小验证：`from ultralytics import YOLO; model = YOLO("yolo26n.pt"); model("test.jpg")`
- 本机环境：公司（Linux），CPU 可跑，GPU 暂无


## 2026-05-22：贾维斯语音架构重构

### 文档
- 理论设计 + 路线图：`docs/贾维斯语音架构-理论设计与路线图.md`
- 详细架构 v2（3层精简版）：`docs/贾维斯语音架构-详细设计.md`

### 概要
3 层架构：VoiceOrchestrator → EngineRegistry (5引擎) → PostProcessor/Delivery
8 个新 Python 文件，旧脚本保留为引擎内部调用。
支持场景预设 (morning/tender/night/warm) + 自动降级 + 批量合成。

### 实施入口
1. `tools/voice-reply/engine/base.py` — BaseEngine 基类
2. `tools/voice-reply/engine/registry.py` — EngineRegistry + 缓存
3. 适配现有 3 引擎 (Noiz / ChatTTS / Edge)
4. `tools/voice-reply/orchestrator.py` — ScenePresets + 调度
5. `tools/voice-reply/postprocess.py` — ffmpeg 后处理
6. `tools/voice-reply/voice-reply.py` — CLI 主入口
7. 端到端测试 → 接入 agent 回复链路

### 状态
⏸️ 待开工。用户说下周一(5/25)或下下周(6/1)开始。
