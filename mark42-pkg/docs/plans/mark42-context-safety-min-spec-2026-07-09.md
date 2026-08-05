# Mark42 Context Safety 最小可执行设计（2026-07-09）

## 目标

把 `~/Desktop/Context-安全防护方案-v1.md` 的核心防线，沉淀为 Mark42 的正式能力：

- 安装 Mark42 时自动补齐 OpenClaw context 安全基线
- 运行中可用 `status / apply / verify` 做体检、修复、验收
- 不改当前会话模型选择，不干扰用户在模型选择列表里的选择

---

## 设计边界

### 做
- 检查并补齐 `~/.openclaw/openclaw.json` 的 context 安全相关字段
- 备份配置 → 合并 patch → validate → verify
- 接入 Mark42 install / verify 链路

### 不做
- 不直接改 OpenClaw 源码
- 不改当前 session 的 `modelOverride`
- 不删除当前会话
- 不自动重启 gateway
- 不擅自覆盖无关 provider / route / agent 配置

---

## 建议命令面

```bash
mark42.py context-safety status
mark42.py context-safety apply
mark42.py context-safety verify
```

### 1) status
只读体检，输出 PASS/WARN/FAIL：

检查项：
- `~/.openclaw/openclaw.json` 是否存在且 JSON 合法
- `agents.defaults.contextPruning` 是否存在且符合基线
- `agents.defaults.compaction` 是否存在且符合基线
- `agents.defaults.compaction.memoryFlush` 是否存在且符合基线
- `session.maintenance` 是否存在且符合基线
- 当前 session 是否存在 `modelOverride`（仅提示，不修改）

### 2) apply
自动补齐 / 修复基线：

步骤：
1. 读取 `~/.openclaw/openclaw.json`
2. 生成时间戳备份
3. 以合并 patch 方式补齐以下字段
4. 写回配置
5. 执行 `openclaw config validate`
6. 打印本次变更摘要

### 3) verify
安装后验收：

在 `status` 基础上额外做：
- 运行 `openclaw config validate`
- 可选做极简烟测（read / web_fetch）
- 返回码用于 `verify.sh` 集成

---

## 推荐默认基线

> 以今天已验证稳定的现状为准，而不是完全照搬 v1 原文。

### A. `agents.defaults.contextPruning`

```json
{
  "mode": "cache-ttl",
  "ttl": "10m",
  "keepLastAssistants": 4,
  "softTrimRatio": 0.65,
  "hardClearRatio": 0.88,
  "minPrunableToolChars": 1200,
  "tools": {
    "allow": ["exec", "read", "process", "web_search", "web_fetch", "image"]
  }
}
```

### B. `agents.defaults.compaction`

必须满足：
- `mode = "safeguard"`（若当前已有兼容值，谨慎处理）
- `truncateAfterCompaction = true`
- `keepRecentTokens = 12000`
- `maxHistoryShare = 0.4`
- `model = "litellm/agnes-2.0-flash"`

### C. `agents.defaults.compaction.memoryFlush`

必须满足：
- `enabled = true`
- `softThresholdTokens = 15000`
- `model = "litellm/agnes-2.0-flash"`
- `prompt` / `systemPrompt`：已有则保留；缺失则补默认安全值

### D. `session.maintenance`

```json
{
  "mode": "enforce",
  "pruneAfter": "14d",
  "maxEntries": 120
}
```

---

## 冲突处理原则

### 可以直接覆盖的字段
- `agents.defaults.contextPruning.*`
- `agents.defaults.compaction.model`
- `agents.defaults.compaction.keepRecentTokens`
- `agents.defaults.compaction.maxHistoryShare`
- `agents.defaults.compaction.truncateAfterCompaction`
- `agents.defaults.compaction.memoryFlush.model`
- `agents.defaults.compaction.memoryFlush.softThresholdTokens`
- `session.maintenance.mode`
- `session.maintenance.pruneAfter`
- `session.maintenance.maxEntries`

### 只能“缺失时补齐”的字段
- `agents.defaults.compaction.memoryFlush.prompt`
- `agents.defaults.compaction.memoryFlush.systemPrompt`

### 明确不碰的字段
- 当前 session `modelOverride`
- provider 的 `apiKey`
- 用户的自定义 model routing
- 非 context 安全相关的 agent 配置

---

## 建议代码落点

### 新增
- `scripts/mark42_modules/context_safety.py`

建议函数：
- `context_safety_status()`
- `context_safety_apply()`
- `context_safety_verify()`
- `_load_openclaw_config()`
- `_save_openclaw_config()`
- `_merge_context_safety_patch()`
- `_validate_openclaw_config()`

### 修改
- `scripts/mark42_modules/cli.py`
  - 增加 `context-safety` 子命令
- `tools/mark42-systemd/install.sh`
  - `--apply` 时调用 `python3 scripts/mark42.py context-safety apply`
- `tools/mark42-systemd/verify.sh`
  - 调用 `python3 scripts/mark42.py context-safety verify`

---

## install / verify 接入建议

### install.sh

在真正写 unit 前调用：

```bash
"$PYTHON_BIN" "$MARK42_CLI" context-safety apply
```

理由：
- 先把 OpenClaw context 安全基线拉到稳态，再启动 Mark42 daemon

### verify.sh

增加：

```bash
if "$PYTHON_BIN" "$MARK42_CLI" context-safety verify; then
  pass "Mark42 context safety verify 通过"
else
  fail "Mark42 context safety verify 未通过"
fi
```

---

## 第一阶段验收标准

以下条件满足即可：

1. `mark42.py context-safety status` 能跑
2. `mark42.py context-safety apply` 能安全写配置并通过 `openclaw config validate`
3. `mark42.py context-safety verify` 能输出明确结果并带返回码
4. `install.sh --apply` 自动接入 `context-safety apply`
5. `verify.sh` 自动接入 `context-safety verify`
6. 当前会话模型不会被这套逻辑擅自改写

---

## 备注

- `Context-安全防护方案-v1` 的思想成立，但其中 `keepRecentTokens = 25000` 已不作为当前默认基线
- 当前实机验证下，`12000` 更保守，更符合“先稳住、先防爆”的目标
- 后续如需做 v2，可再引入 drift report / watchdog 告警 / auto-heal 模式
