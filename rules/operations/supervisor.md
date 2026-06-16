# 监工服务 / 前台常驻 / 后台插播 操作规则

> 按需加载：当任务涉及后台执行、监工服务、或主会话稳定性保障时读取。
> 触发条件：复杂工程 / 长耗时 / 需要后台分身 / 用户说"开监工"

## 当前架构

**监工服务脚本（底座）+ 前台状态面板（可见性兜底）+ `main-supervisor-lite`（按需协作层）**

## 启动判断

- 纯日常聊天：`auto + taskActive=false`，不开监工分身
- 简单工作：`auto + taskActive=false`，先短反馈再直接做
- 复杂工程：切 `auto + taskActive=true`；可能阻塞时先短反馈
- 用户说"开/关监工服务"：直接切 `force_on/force_off`
- **10 分钟等待窗口**：后台任务完成后进入约 10 分钟等待接续窗口 → 有新任务继续盯 → 10 分钟无新任务自动退回 `auto + taskActive=false`
- **切到 force_on 或 taskActive=true 后**：若对用户说"开始处理/正在推进"，必须立刻核对是否有 activeTaskCount>0；若没有则马上真卸后台或明说这轮仍在前台做

## 任务分流

- 重活给普通任务分身做
- 监工分身（`main-supervisor-lite`）只负责监工/兜底/补位，不做常规工作
- 需要前台协作时必须有监工分身
- 监工分身用 `sessions_spawn(mode:"run", context:"isolated")`，不用 session 绑定

## 检查顺序

1. 区分对象：普通分身 vs 监工分身
2. 普通分身按任务状态处理
3. 监工服务按 `policyMode + taskActive` 处理
4. 监工分身只在确实需要时存在

## 收尾

1. 先关普通任务分身
2. 不再需要监工 → 恢复 `auto + taskActive=false`
3. 不需要协作 → 收掉监工分身
4. **Dashboard 会话移动**：若用户在 WebChat 点 `+` 切到新 dashboard，前台回报应跟随最新 dashboard 会话，不绑死旧页面

## 异常处理

- **重复监工**：比较宿主唯一标号 `main-supervisor-lite@<host>`，保留最新健康的一个
- **任务空返回**：监工先向主会话报告"异常，正在接手"，可重试 1 次
- **任务异常结束**：立刻报告"后台任务异常"，再修复
- **3 分钟无产出**：监工链路主动补状态（不是任务必须 3 分钟完成，是前台必须有可见反馈）

## 能力边界

- 监工是兜底机制，不是万能保险
- Gateway/渠道/模型全挂时监工也可能一起失效
- 不把希望押在单一点上

## 场景判定表

| 场景 | 监工服务 | 监工分身 | 任务分身 | 前台要求 |
|---|---|---|---|---|
| 日常聊天 | auto+taskActive=false | 0 | 不开 | 正常聊天 |
| 简单工作 | auto+taskActive=false | 0 | 不开 | 先短反馈 |
| 复杂工程不阻塞 | auto+taskActive=true | 0 | 不开 | 先短反馈 |
| 复杂工程阻塞前台 | auto+taskActive=true | 1 | 视需要 | 短反馈+监工补进度 |
| 用户说开监工 | force_on | 按需 | 视任务 | 前台可回复 |
| 用户说关监工 | force_off | 收尾后为0 | 视任务 | 前台可回复 |
| 拿不准 | 按工作型处理 | 视需要 | 视阻塞 | 先短反馈 |

> ⚠️ 「不阻塞前台」的判定：若预计单轮工作可能超过 3 分钟且中间无自然产出，即视为会阻塞前台，按「复杂工程阻塞前台」处理。宁可多开一层监工，不赌不会卡住。

## 关键脚本

- 监工状态：`scripts/openclaw-supervisor-status.py`
- 状态文件：`~/.local/state/openclaw/supervisor/supervisor-status.json`
- 控制文件：`~/.local/state/openclaw/supervisor/service-control.json`
- 前台 broker：`scripts/openclaw-frontstage-broker.py`
