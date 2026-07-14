# 系统规则

> 适用机器：通用（设备相关条目标注为 公司(Linux) 或 掌机(Windows)）
> 系统 / OS：通用

---

## 1. 监工服务

> 💡 系统操作相关的脚本路径、服务配置、凭据指针 → 详见 `TOOLS.md`。

### 控制语义
- 状态脚本：`python3 scripts/openclaw-supervisor-status.py`
- 模式：`policyMode=auto|force_on|force_off` + `taskActive=true|false`
- 默认基线：`auto + taskActive=false`
- 复杂工程：切到 `auto + taskActive=true`
- 用户显式指令：切到 `force_on` 或 `force_off`

### 开启/关闭时机
- 简单工作/纯日常聊天 → 不开
- 复杂工程/长耗时 → 开启
- 用户说"开监工"/"关监工" → 立即切换
- 上一轮后台任务完成后，进入约 10 分钟等待窗口：
  - 期间有新后台任务 → 继续盯
  - 10 分钟无新任务或继续信号 → 自动关闭（退回 `auto + taskActive=false`）

### 监工分身
- 使用 `sessions_spawn(mode:"run", context:"isolated")`
- 标签：`main-supervisor-lite@<runtime-host>`
- 数量原则：0 或 1（单例）
- 工作型任务期应为 1，无后台任务约 2 分钟后可回到 0
- 有普通任务分身**且当前轮需要前台协作/插播时**，必须同时存在一个监工分身
- 发现两个同标号监工→保留最新且健康的，其余删除

### 监工行为
- 每 3 分钟无可见产出→向前台补一句简短进度
- 任务分身空返回→监工先向主会话报告异常并接手检查
- 任务分身异常结束→监工先报告前台"异常结束，正在修复"，再排查修复
- 用 `send-frontstage + chat.inject` 回报前台，事件去重，不刷屏

### 监工能力边界
- 网络不好/与模型通信阻塞/底层链路出问题时，监工未必能单独救场
- 不能脱离 Gateway/渠道/模型链路假设万能保险

---

## 2. 前后台协作

### 硬性规定
- 主会话在任何情况下都必须保持沟通顺畅
- 长任务优先卸到后台分身（sessions_spawn），不长时间占住主会话
- 前台只负责正常对话，后台有结果再主动插播进度
- 不把主会话收成等待态，不让前端看起来像没反应

### 任务收尾
- 任务完成后主动汇报，不等用户追问
- 每轮任务做完收尾清理：关没任务的分身，清理陈旧/失败/僵尸会话
- 优先保留当前会话树（当前会话及其父 dashboard）+ 主会话

---

## 3. 设备识别

- 公司(Linux)：`missyouangeled-VMware-Virtual-Platform`，兜底 IP `192.168.233.130`
- 掌机(Windows)：`TABLET-EH5U3C01`
- 新机器自动登记到 `HOST_CONTEXT.md`：起临时设备名 + 环境标签
  - 高置信度写具体标签（公司/掌机/家里），没把握写 `未归类`
  - 登记后主动告知用户设备名和标签
- 不覆盖用户已确认的设备名或环境标签
- 机器/地点标签只标识当前设备，不拆分规则集
- 同一仓库同步后共享同一套规则

---

## 4. 磁盘规则（公司 Linux）

- 根盘 `/` 与数据盘 `/mnt/data` 双盘
- 下载大文件/解压模型/批量生成大体积产物/落大缓存前先预估大小
- 预计新增占用 ≥1G 或可能压到 8G 安全线以下→放 `/mnt/data`
- 按峰值占用做保守估算

---

## 5. 文件交付（跨设备）

- 给地址下载→起临时 HTTP 服务，发完整可访问 URL（不要只给本地路径）
- 收文件→起带随机 token 的临时上传页，让用户在浏览器里选文件上传

---

## 6. 升级与补丁检查

### 升级前

- 先读 `docs/通用-OpenClaw-升级记录.md`，了解历史升级中发生过的问题类型
- 备份当前 `dist/control-ui` 目录

### 升级后

- 首先读 `docs/通用-OpenClaw-升级记录.md`，逐条对照历史问题排查：
  1. 函数/变量名变化（Rolldown 打包后 minify 每次可能不同，如 `gz → Gz`、`$R → Oz`）
  2. Control UI 结构变化（从 `JA`→`ZA` 等渲染函数变更）
  3. 所有自定义补丁脚本是否仍然有效（branding / model-selector 等）
  4. systemd PATH 环境隔离
  5. infos-handle sidecar 协议兼容性
  6. session 索引兼容性
- 运行 `python3 scripts/openclaw-post-upgrade-self-check.py --print-human`
- 运行 `python3 scripts/verify-today-patches.py --print`
- 运行 `python3 scripts/openclaw-system-summary.py --print-human`
- 若发现新问题，事后追记到 `docs/通用-OpenClaw-升级记录.md`（含现象/根因/修复/验证）

> ⚠️ 这是硬规则：每次升级后必须走一遍以上流程，不能因为之前升级顺利就跳过。任何模型升级后都应先查历史记录再排查，而不是从零猜。

## 7. 关键脚本入口

| 用途 | 命令 |
|------|------|
| 监工状态 | `python3 scripts/openclaw-supervisor-status.py --print-human` |
| 健康诊断 | `python3 scripts/openclaw-local-health-diagnose.py --print-human` |
| Control UI 修复 | `python3 scripts/openclaw-control-ui-emergency.py --check/--repair --print-human` |
| 系统概览 | `python3 scripts/openclaw-system-summary.py --print-human` |
| 升级后自检 | `python3 scripts/openclaw-post-upgrade-self-check.py --print-human` |
| 变更流水 | `python3 scripts/openclaw-change-log.py capture/memo ...` |
| 前台 broker | `scripts/openclaw-frontstage-broker.py rebuild-views` |

---

## 7. 会话清理

> ⚠️ 此段与 `rules/operations/session-cleanup.md` 和 `rules/work.md` §12 重复定义——修改任一处时务必同步另外两处。

- 用户说"清会话"→按分层方案执行
- 先保留当前会话树与主会话
- 优先清陈旧 dashboard、已结束/失败/超时/僵尸 running 的 subagent、旧直聊会话
- 先移除 sessions 索引和对应主 jsonl，再清理 trajectory/checkpoint/bak/reset/deleted 残留
- 大扫除时可删非当前保留会话的旧归档与旧备份目录，不碰当前活跃会话自己的核心文件

---

## 8. 掌机（Windows）退出机制

- 用户说"关闭 OpenCLaw / 先停掉 / 关这个"→按"停用 OpenClaw 网关链路"理解
- 先禁用 `OpenClaw Gateway Watchdog` 与 `OpenClaw Gateway`，再停止当前 gateway 实例
- 不要把这类指令理解成关闭整个 Windows 系统


## 9. 工具使用红线

> 🚨 本节由 2026-07-14 CASE-007 触发:CASE-007 的根因是 `write` 工具被误用于"全覆写已存在的大文件"——任何"修改大文件一小段"的需求,默认禁止 `write` 全覆写。

### 9.1 核心铁律

> **当工具、路径、方案尝试失败时,默认停下来问人,而不是换更暴力的方案绕过去。**
> **任务交付压力下,最容易出错的"替代方案"恰恰是风险最高的方案。**

### 9.2 `write` 工具红线（最重要）

| 场景 | 动作 | 备注 |
|---|---|---|
| 写**新文件**(文件原本不存在) | ✅ 允许 `write` | 正常使用 |
| 覆写**小文件**(< 50 行 + 已存在) | ⚠️ `write` 需先 `cp` 备份 | 备份文件名 `.bak-yyyymmdd-hhmmss` |
| 覆写**大文件**(≥ 50 行 + 已存在) | ❌ **禁止** `write` 全覆写 | 改用 `edit` / `apply_patch` / sed / Python 行级操作 |
| `edit` 工具 oldText 匹配失败 | ⚠️ 不要跳到 `write` | 先 `grep -n` 定位 + `xxd` 看真实字节 + 用更短更独特的锚点 |

**自检清单（`write` 覆写前必过一遍）**：

```
[ ] 文件存在吗? → ls 确认
[ ] 文件多少行? → wc -l
[ ] > 50 行 + 已存在? → 禁止 write 全覆写
[ ] 必须 write? → cp 备份先(.bak-yyyymmdd-hhmmss)
[ ] 写完后 diff 一下,与备份对比,确认改动符合预期
```

### 9.3 其他工具的"次优解"陷阱

| 工具 | 误用模式 | 正确做法 |
|---|---|---|
| `exec rm -rf` | 删错目录 | 删之前 `ls` 看一遍,加 `-i` 确认;**禁止** `rm -rf /*` 类通配 |
| `exec pkill -f` | pattern 太宽,杀错进程 | 先 `ps -ef \| grep <name> \| awk '{print $2}'` 拿精确 PID,按 PID 杀(参 CASE-005) |
| `exec systemctl restart` | 在主会话里 restart 把自己打断 | 改用 `systemctl --user restart` + sleep 串行(参 CASE-003) |
| `exec > file` | 截断重要文件 | 改用 `>>` 追加,或先 `cp` 备份 |

### 9.4 暴力工具绕开正常路径 = 事故放大器

**核心警告**：当正常路径(`edit`、`apply_patch`、手动 `sed`、Python 脚本)走不通时,**下意识选用更"暴力"的方案**(`write` 全覆写、`rm -rf`、强制 `kill -9`、硬 `restart`)是事故放大器。

**反模式**：

- `edit` 报"找不到 oldText" → 直接跳到 `write` 全覆写(CASE-007)
- `pkill` 杀不掉 → 直接 `kill -9` 强杀(可能留半截状态)
- `systemctl restart` 超时 → 直接 `kill -9 systemd` 强重启
- `python script.py` 出错 → 直接 `python script.py --force` 强推

**正模式**：

- 卡住时,**先停下来**:`grep -n` / `xxd` / `cat -A` 看真实数据
- 看清楚后再试同一工具 / 换更精准的工具
- 还是不行 → **问用户**(而不是换更暴力的)
- 任务交付压力下,尤其要慢一拍,不要"加速"

### 9.5 相关案例(回查)

- **CASE-20260714-007**:`write` 工具覆写大文件差点清空文档(本红线直接来源)
- **CASE-20260706-005**:cron "自测" 把自己会话打断(暴力工具 = 救命 1 跑自测)
- **CASE-20260710-006**:watchdog dry-run 误触发 systemctl restart 链式事故(暴力工具 = 强制 restart)
- **CASE-20260706-003**:主会话内执行 `openclaw gateway restart` 把自己打断(暴力工具 = restart gateway)

四例的共同根因:**当正常路径走不通时,下意识选用更"暴力"的方案**。

### 9.6 红线落地的 4 件事

1. **写大文件前必看 9.2 自检清单**(强制)
2. **`edit` 失败时按 9.4 正模式处理**(问人 / 看真实数据,不要直接 `write`)
3. **每次"差点翻车"立即追记到崩坏案例**(本节就是 CASE-007 的产物)
4. **归档冗余设计**(`桌面 + 工作区归档` 双副本)继续维护——CASE-007 救回靠的就是这条

---

> 💡 这条红线 7/14 由 CASE-007 触发落地,以后任何"用 write 覆写大文件"的需求,先来这里看 9.2。

