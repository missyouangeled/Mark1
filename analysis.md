# 会话备份 + Unity文件管理器 — 全面分析 & 设计方案

> 生成时间: 2026-06-09 16:15 CST
> 数据盘备份: `/mnt/data/openclaw/scratch/session-backup-and-ufm-design/analysis.md`

---

# 第一部分：会话压缩备份机制

## 1.1 当前现状

### 已有组件

| 组件 | 路径 | 状态 |
|------|------|------|
| 备份脚本 | `scripts/openclaw-session-backup.py` | ✅ 存在，功能完整 |
| 备份目录 | `/mnt/data/openclaw/session-backup/` | ✅ 22个快照（最新14:55） |
| 备份 cron | `session-backup-every-30min` | ❌ **连续2次超时失败** |
| 启动引用 | `AGENTS.md` 步骤 5.1 | ✅ 已集成 |
| 启动引用 | `BOOT_INDEX.md` 第 2 步 | ✅ 已集成 |
| 转录聚合 | `openclaw-lifecycle-maintainer.py` | ✅ 每15min生成 `daily-*-transcript.md` |

### 备份内容（每次快照 6 个文件）

| 文件 | 来源 | 作用 |
|------|------|------|
| `MEMORY.md` | workspace | 长期偏好/规则 |
| `SOUL.md` | workspace | persona |
| `USER.md` | workspace | 用户信息 |
| `daily-YYYY-MM-DD.md` | workspace | 今日记录摘要 |
| `daily-YYYY-MM-DD-1.md` | workspace | 昨日记录摘要 |
| `context-summary.md` | 自动生成 | AI恢复指南 (~39行) |

### 快照间隔

平均间隔 ~30min，与 cron 频率一致（每30min）。

---

## 1.2 发现的问题

### 🔴 致命：备份 cron 已失效

```
cron: session-backup-every-30min
状态: error (2次连续超时)
原因: "job execution timed out (last phase: model-call-started)"
上次成功: 未知（manifest中最后一个快照是14:55，但超时开始于更早）
超时设置: timeoutSeconds=30, 实际耗时 37209ms → 超时
```

**根因链**：
1. cron 的 payload 是 `agentTurn` → 需要启动一个子 agent session
2. 子 agent 需要模型调用 → 当前模型路由（deepseek-company/deepseek-v4-pro）响应时间可能超过 30s
3. 子 agent 内部再 exec 运行 python 脚本 → 多一层间接调用
4. 一个本应 0.5 秒跑完的 python 脚本，变成了"模型调用 + 子agent + exec"的链表，任何一个环节卡住就超时

**这是一个根本性的架构缺陷**：用 agentTurn 来运行一个无状态 python 脚本，就像用火箭发射来送一封信。

### 🔴 致命：不备份任何对话内容

备份的是「规则文件」和「规则文件的摘要」，但**不包含**：
- 会话聊天记录（jsonl）
- 每日转录全文（`daily-*-transcript.md`）
- 当前对话的最近 N 条消息
- session 的 trajectory 数据

当会话被压缩后，旧的消息从 jsonl 中消失。此时 `daily-*.md` 里只有**人工写的摘要**，没有完整的对话上下文。

用户在 AGENTS.md 中已明确写道：
> "This is the independent data-disk backup of recent context, MEMORY, SOUL, and USER files."
> "It survives workspace resets, session compression, and git issues."

但目前实际上**只有** MEMORY/SOUL/USER/daily 摘要，没有 recent context（对话本身）。

### 🟡 中危：崩溃最脆弱的28分钟窗口

会话压缩可能在任意时刻发生。如果压缩发生在备份后 2 分钟：
- 28 分钟内的对话上下文 → 丢失
- 备份里有 28 分钟前的静态规则 → 有用但不完整
- AI 醒来后只能从 MEMORY.md + daily.md 摘要推测发生了什么

### 🟡 中危：context-summary.md 过于简陋

- 只有 39 行
- 只从 MEMORY.md 提取含日期的行作为"最近规则"
- 不包含：当前话题、未完成任务、用户刚说了什么、打开了哪些项目
- 对 AI 恢复几乎不重要——真正的上下文在 daily 文件和对话本身

### 🟡 中危：transcript 没被纳入备份

`openclaw-lifecycle-maintainer.py` 每 15min 聚合当日所有模型的转录到 `daily-YYYY-MM-DD-transcript.md`。这个文件比 daily.md 包含更完整的对话内容，但**没有被备份脚本包含**。

### 🟢 低危：retention 只有 7 天

快照保留 7 天。如果用户隔一周问"上周三我们聊了什么"，7天前的快照已被清理。

---

## 1.3 设计方案

### 方案：彻底重构备份触发机制

**核心思路**：把备份触发从 OpenClaw cron (agentTurn) 迁移到 systemd timer（直接调用 python），消除"模型调用链路"的单点故障。

### 改动清单

```
1. 停用当前 agentTurn cron (session-backup-every-30min)
   └─ 降低 token 消耗 + 消除超时故障源

2. 新建 systemd timer: openclaw-session-backup.timer
   └─ 每 10 分钟直接运行 python3 scripts/openclaw-session-backup.py
   └─ 不经过模型路由/子agent/exec 链
   └─ 零 token 消耗

3. backup.py 增强：
   a. 备份 daily-*-transcript.md（当前最完整的对话记录）
   b. 备份 session 目录的元信息（sessionKey → 最近活跃时间 → jsonl 大小）
   c. context-summary.md 改为从 transcript.md 提取最近 50 行摘要
   d. 写入 last_state.json（session大小/最近主题/未关闭任务）
   e. 当根盘 / 余量 < 2GB 时自动从数据盘读取，不写根盘

4. 快照保留策略调整为 14 天（覆盖"上周三"的查询需求）

5. session-size-watcher 集成：
   在 FORCE_CLEAN (40MB) 触发前，自动调用一次 backup.py 快照
   确保"压缩即将发生"时上下文已经被保存

6. AGENTS.md 启动流程保持不变：
   启动时读 /mnt/data/openclaw/session-backup/ 最新快照
   现在能读到更完整的上下文（transcript + 对话元信息）
```

### 备份内容（增强后）

```
snapshot-YYYY-MM-DDTHHMMSS/
├── MEMORY.md              ← 不变
├── SOUL.md                ← 不变
├── USER.md                ← 不变
├── daily-YYYY-MM-DD.md    ← 不变
├── daily-YYYY-MM-DD-transcript.md  ← 🆕 当日转录全文
├── context-summary.md     ← 🆕 增强：从 transcript 提取最近50行
├── session-state.json     ← 🆕 {sessionKey, 大小, 最近主题, 活动时间}
└── last_state.json        ← 🆕 快照时刻的系统快照
```

### 触发体系（增强后）

```
┌─ systemd timer (每10min) ──── 直接 python3 backup.py ── 零token
├─ session-watcher FORCE_CLEAN前 ── 紧急快照（压缩前保护）
└─ 手动: python3 backup.py ── 按需快照
```

---

# 第二部分：Unity文件管理器 — 设计优先工作流

## 2.1 用户核心诉求

> "不管什么需求，都要先从设计开始。明确分析需求。然后给出详细的映射表。表示之前是什么样子。之后是什么样子。当然还有之前的路径和之后的路径。"

翻译成工程语言：

1. **每次操作前先设计** —— 不允许"想到哪改到哪"
2. **生成映射表** —— 原路径 → 新路径、原名 → 新名
3. **映射表要全面** —— 路径和名称都要有
4. **用户审阅后再执行** —— 不能跳过确认

## 2.2 当前 unity-file-manager.py 能力

| 命令 | 功能 | 设计先行？ |
|------|------|:---:|
| `index` | 扫描建索引 | ❌ |
| `find` | 查询文件 | ❌ |
| `snapshot` | git commit + 刷新索引 | ❌ |
| `status` | 状态一览 | ❌ |
| `verify` | .meta 一致性检查 | ❌ |
| `rollback` | git 回滚 | ❌ |
| `info` | 单文件详情 | ❌ |
| `export` | 导出报告 | ❌ |

**缺失的核心命令**：`plan`（设计/映射表生成）和 `apply`（执行设计好的映射表）。

## 2.3 设计方案

### 新增命令架构

```
unity-file-manager.py plan <目录> --rules <规则文件>     # 生成映射表
unity-file-manager.py apply <映射表文件> [--confirm]      # 执行映射表
```

### 2.3.1 `plan` 命令

**功能**：根据规则文件，扫描目录，生成完整的"原路径→新路径"映射表。

**输入**：
- 目标目录路径
- 规则文件（JSON/YAML），描述改名逻辑

**规则文件格式**：

```json
{
  "prefix": "RoadSide_",
  "directoryOps": [
    {"from": "ClockType02", "to": "Clock_02", "moveToParent": true},
    {"from": "RoadSide_Lamp", "to": "Lamp"}
  ],
  "renameRules": [
    {"scope": "Sign/", "pattern": "Road_", "replacement": "RoadSide_"},
    {"scope": "TelegraphPoleType01/", "pattern": "RoadObject_", "replacement": "RoadSide_"}
  ],
  "customRenames": {
    "TelegraphPoleType01": "TelegraphPole_01"
  }
}
```

**输出**：

1. 映射表 JSON（落 scratch + 打印到终端）
2. 冲突检测报告
3. 统计摘要（多少文件会被改名/移动/不变）

**映射表格式**：

```json
{
  "meta": {
    "root": "/media/.../RoadSide",
    "generatedAt": "2026-06-09T16:00:00",
    "totalFiles": 50,
    "wouldChange": 12,
    "unchanged": 38,
    "conflicts": 1
  },
  "changes": [
    {
      "before": {"path": "RoadSide_Clock/ClockType02/Prefab/Clock_Type_02.prefab", "name": "Clock_Type_02.prefab"},
      "after":  {"path": "RoadSide/Clock_02/Prefab/Clock_Type_02.prefab",       "name": "Clock_Type_02.prefab"},
      "type": "move",
      "reason": "ClockType02 → 上级 Clock_02"
    },
    {
      "before": {"path": "RoadSide_Lamp/Materials/A/Albedo.tif", "name": "Albedo.tif"},
      "after":  {"path": "Lamp/Materials/A/Albedo.tif",          "name": "Albedo.tif"},
      "type": "rename_dir",
      "reason": "RoadSide_Lamp → Lamp"
    },
    {
      "before": {"path": "Sign/Prefab/Road_Sign_01_H1m6.prefab", "name": "Road_Sign_01_H1m6.prefab"},
      "after":  {"path": "Sign/Prefab/RoadSide_Sign_01_H1m6.prefab", "name": "RoadSide_Sign_01_H1m6.prefab"},
      "type": "rename_prefix",
      "reason": "Road → RoadSide (Sign/)"
    }
  ]
}
```

**终端输出**（给人看）：

```
📋 映射表 — RoadSide 重命名计划
   根目录: /media/.../RoadSide
   📊 总文件 50 | 将变更 12 | 不变 38
   ⚠️ 冲突 1 项

📁 目录操作 (3 项)
   RoadSide_Clock/ClockType02/  →  RoadSide/Clock_02/（提升到上级）  [影响 4 文件]
   RoadSide_Lamp/               →  Lamp/                              [影响 8 文件]
   TelegraphPoleType01/          →  TelegraphPole_01/                  [影响 2 文件]

🔤 前缀替换 (2 组)
   Sign/*.prefab:              Road_xxx      → RoadSide_xxx    [7 文件]
   TelegraphPole_01/*.prefab:  RoadObject_xxx → RoadSide_xxx   [1 文件]

⚠️ 冲突 (1 项)
   Mat_Material.mat ← 4 来源:
     Lamp/Materials/A/Mat_Material.mat
     Sign/Materials/Mat_Material.mat
     Clock_02/Materials/A/Mat_Material.mat
     Clock_02/Materials/B/Mat_Material.mat

💡 下一步: unity-file-manager.py apply /mnt/data/scratch/.../plan.json [--confirm]
```

### 2.3.2 `apply` 命令

**功能**：读取映射表 JSON，执行所有 renaming/moving。

**安全设计**（继承自当前工具的安全层）：
- 默认 dry-run
- `--confirm` 才真正执行
- 执行前自动 git commit（失败则拒绝）
- .meta 自动配对同步
- 每步操作写入 journal

**输出**：
```
✅ 已执行 3/3 项目录操作
✅ 已执行 8/8 项前缀替换
✅ .meta 同步: 12/12 配对完整
📸 快照: git commit 已创建 (可 rollback)
⏱️ 耗时: 0.8s
```

### 2.3.3 与现有命令的关系

```
完整工作流:

1. unity-file-manager.py snapshot /path/to/Wall   ← 开工快照
2. 用户描述需求（"把Sign前缀Road→RoadSide..."）
3. 贾维斯/用户手写 rules.json（规则描述）
4. unity-file-manager.py plan /path/to/Wall --rules rules.json --output plan.json
   → 生成映射表
   → 打印摘要（给人看）
   → 落 JSON（给程序读）
5. 用户审阅映射表 → 确认/调整
6. unity-file-manager.py apply plan.json --confirm
   → 执行所有变更
7. unity-file-manager.py verify /path/to/Wall   ← .meta 验证
8. unity-file-manager.py status /path/to/Wall   ← 最终状态

如果出问题:
9. unity-file-manager.py rollback /path/to/Wall ← 秒级回滚
```

### 2.3.4 与 rename-conflict-check.py 的整合

当前 `rename-conflict-check.py` 是更专用的「改名冲突预扫」工具。`plan` 命令会**内部调用**它来做冲突检测，返回的结果嵌入到映射表中。二者不冲突，`plan` 是更高层的编排者。

---

## 2.4 风险评估

| 风险 | 缓解 |
|------|------|
| rules.json 格式复杂 | 提供模板 + `--interactive` 交互式引导 |
| 映射表太大（>1000 条目） | 摘要打印 + 完整 JSON 落文件 |
| apply 中途失败 | git rollback 秒级恢复 |
| .meta GUID 混乱 | verify 命令做最终验证 |

---

## 2.5 实施优先级

| 优先级 | 任务 | 理由 |
|--------|------|------|
| P0 | 新增 `plan` 命令 | 核心诉求 |
| P0 | 新增 `apply` 命令 | plan 的配套 |
| P1 | `--interactive` 规则引导 | 降低上手门槛 |
| P1 | 整合 rename-conflict-check 为子检测 | 复用已有能力 |
| P2 | rules.json 模板生成 | 便利性 |
| P2 | Markdown 格式映射表输出 | 给人看 |
