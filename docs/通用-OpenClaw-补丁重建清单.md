# OpenClaw 补丁重建清单

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：跨机器共享的升级后重建流程

## 用途

当 OpenClaw 升级、重装、切换大版本，或怀疑正式补丁被覆盖时，按这份清单逐项恢复“结果不变”的补丁能力。

本清单和《`docs/通用-OpenClaw-补丁注册表.md`》配套使用：

- 注册表：回答“有哪些正式补丁、目标是什么”
- 本清单：回答“升级后按什么顺序逐项重建和验收”
- `docs/通用-OpenClaw-升级后自检清单.md`：回答“更新后现在还能不能正常用”

---

## 0. 重建前先做两件事

1. **先识别当前机器**
   - 先看 `HOST_CONTEXT.md`
   - 再按 `docs/多机器-读取与更新规则.md` 确认当前机器应优先读哪些维护文档
2. **先看补丁注册表**
   - `docs/通用-OpenClaw-补丁注册表.md`

不要一上来就凭记忆手工改 `dist/` 或乱补 systemd。

---

## 1. 先恢复“自动重打入口”

优先恢复那些会影响后续所有前端补丁是否还能自动存在的入口。

### 1.1 Control UI 补丁重打链路

目标：让 Control UI 品牌与前台状态补丁能在 gateway 启动前自动重打。

检查：

- `~/.config/systemd/user/openclaw-gateway.service.d/branding.conf`
- `scripts/apply-openclaw-control-ui-branding.py`
- `config/control-ui-branding.json`

动作：

```bash
python3 scripts/apply-openclaw-control-ui-branding.py
```

验收：

- 品牌仍是“贾维斯”
- 聊天页“进行中”逻辑仍包含 `loading / sending / stream / canAbort / queue / hasActiveRun / status=running`
- 前端资产里仍带 `JarvisProjectYieldedHistoryReply`

### 1.2 开机体检自愈（boot-health-check）

检查：`scripts/openclaw-boot-health-check.py` `~/.config/systemd/user/openclaw-boot-health-check.service`

动作：`python3 scripts/openclaw-boot-health-check.py --print-human`

验收：输出核心服务/定时器/磁盘/内存/端口状态，无报错。

---

## 2. 再恢复辅助消息基础设施

### 2.1 frontstage broker

检查：

- `scripts/openclaw-frontstage-broker.py`
- `scripts/test-frontstage-broker.py`
- `scripts/openclaw-supervisor-subagent.py`

动作：

```bash
python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock
python3 scripts/openclaw-frontstage-broker.py ingest --source broker-smoke --event-key broker-smoke-rebuild --session-key 'agent:main:main' --message 'broker source event smoke' --data-json '{"severity":"ok"}' --print-json
python3 scripts/openclaw-infos-handle.py query --kind snapshot.summary --format text
```

若当前机器是 Linux，且希望一并把 broker 周期重建 timer 装好，可直接改用：

```bash
python3 scripts/apply-openclaw-frontstage-broker-data.py --install-user-systemd
```

验收：

- `~/.local/state/openclaw/frontstage/broker-state.json` 更新
- `~/.local/state/openclaw/broker/events.jsonl` 更新
- `events.jsonl` 中应至少能看到 `broker.source.event`
- `~/.local/state/openclaw/broker/manifest.json` 存在
- `~/.local/state/openclaw/broker/views/frontstage.json` 存在
- `~/.local/state/openclaw/broker/views/snapshot.json` 存在
- `~/.local/state/openclaw/broker/views/overview.json` 继续存在（兼容别名）
- `snapshot.json` / `manifest.json` 里的 `snapshotContract.primaryView` 为 `snapshot`
- `snapshotContract.viewCatalog.snapshot.role = primary`，`overview.role = legacy_alias`，`frontstage / health / tasks / recovery.role = supporting_view`
- `snapshotContract.publishedJsonCatalog.frontstageStatusJson.role = legacy_alias`
- `~/.npm-global/lib/node_modules/openclaw/dist/control-ui/jarvis-frontstage-status.html` / `.json` 存在（其中 `.json` 只作为兼容别名保留）
- `~/.npm-global/lib/node_modules/openclaw/dist/control-ui/jarvis-frontstage-snapshot.json` 存在
- live `jarvis-branding-override.js` 里 `snapshotJsonHref` 已指向 `/jarvis-frontstage-snapshot.json`，`legacyStatusJsonHref` 已指向 `/jarvis-frontstage-status.json`
- apply 输出里的 `frontstagePublication.snapshotFirstReady` 为 `true`
- `rebuild-views` 能在不依赖新事件触发的情况下重建视图与前台状态页
- `python3 scripts/openclaw-infos-handle.py query --kind snapshot.summary --format text` 能直接返回摘要，不依赖 Control UI

### 2.2 broker 周期重建 timer

检查：

- `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service`
- `tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer`
- `~/.config/systemd/user/openclaw-frontstage-broker-rebuild.service`
- `~/.config/systemd/user/openclaw-frontstage-broker-rebuild.timer`

动作：

```bash
python3 scripts/apply-openclaw-frontstage-broker-data.py --install-user-systemd
# 或手工执行：
cp tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.service ~/.config/systemd/user/
cp tools/openclaw-frontstage-broker/openclaw-frontstage-broker-rebuild.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-frontstage-broker-rebuild.timer
systemctl --user start openclaw-frontstage-broker-rebuild.service
```

验收：

```bash
systemctl --user show openclaw-frontstage-broker-rebuild.service -p Result -p ExecMainStatus -p ActiveState -p SubState
systemctl --user show openclaw-frontstage-broker-rebuild.timer -p UnitFileState -p ActiveState -p SubState
```

---

### 2.3 infos-handle sidecar

检查：

- `scripts/openclaw-infos-handle-sidecar.py`
- `tools/openclaw-infos-handle-sidecar/README.md`
- `tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`
- `~/.config/systemd/user/openclaw-infos-handle-sidecar.service`

动作：

```bash
cp tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-infos-handle-sidecar.service
python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar --require-control-ui-infos-handle-sidecar
```

验收：

```bash
curl -s http://127.0.0.1:18790/healthz
curl -s 'http://127.0.0.1:18790/v1/query/snapshot.summary?format=json'
curl -s 'http://127.0.0.1:18790/v1/query/contract.catalog?format=json'
systemctl --user show openclaw-infos-handle-sidecar.service -p ActiveState -p SubState
```

### 2.4 infos-handle unified proxy

检查：

- `scripts/apply-openclaw-infos-handle-gateway-proxy.py`
- `tools/openclaw-infos-handle-gateway-proxy/README.md`
- `tools/openclaw-infos-handle-gateway-proxy/Caddyfile`
- `tools/openclaw-infos-handle-gateway-proxy/openclaw-unified-proxy.service`
- `~/.config/systemd/user/openclaw-unified-proxy.service`

动作：

```bash
python3 scripts/apply-openclaw-infos-handle-gateway-proxy.py --install-user-systemd --enable --restart --verify --print-json
```

验收：

- verify 输出中至少应有：
  - `localHealthzOk = true`
  - `localSummaryCode = 200`
- 若当前机器存在可用 LAN IP，还应有：
  - `remoteNoAuthCode = 401`
  - `remoteWithAuthCode = 200`

## 3. 恢复各类自动触发 watcher / service

### 3.1 supervisor 状态层 + 自动回报

检查：

- `tools/openclaw-supervisor/openclaw-supervisor-watch.service`
- `tools/openclaw-supervisor/openclaw-supervisor-watch.timer`
- `~/.config/systemd/user/openclaw-supervisor-watch.service`
- `~/.config/systemd/user/openclaw-supervisor-watch.timer`

动作：

```bash
cp tools/openclaw-supervisor/openclaw-supervisor-watch.service ~/.config/systemd/user/
cp tools/openclaw-supervisor/openclaw-supervisor-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-supervisor-watch.timer
python3 scripts/test-openclaw-supervisor-status.py
python3 scripts/openclaw-supervisor-status.py --print-json
```

验收：

```bash
systemctl --user show openclaw-supervisor-watch.service -p Result -p ExecMainStatus -p ActiveState -p SubState
systemctl --user show openclaw-supervisor-watch.timer -p UnitFileState -p ActiveState -p SubState
```

### 3.2 local-health 诊断层 + 前台回报

检查：

- `tools/openclaw-local-health/openclaw-local-health-watch.service`
- `tools/openclaw-local-health/openclaw-local-health-watch.timer`
- `~/.config/systemd/user/openclaw-local-health-watch.service`
- `~/.config/systemd/user/openclaw-local-health-watch.timer`

动作：

```bash
cp tools/openclaw-local-health/openclaw-local-health-watch.service ~/.config/systemd/user/
cp tools/openclaw-local-health/openclaw-local-health-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-local-health-watch.timer
python3 scripts/openclaw-local-health-diagnose.py --print-json
```

验收：

```bash
systemctl --user show openclaw-local-health-watch.service -p Result -p ExecMainStatus -p ActiveState -p SubState
systemctl --user show openclaw-local-health-watch.timer -p UnitFileState -p ActiveState -p SubState
ls -l ~/.local/state/openclaw/local-health/
```

### 3.3 frontstage recovery watcher

检查：

- `tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.service`
- `tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.timer`
- `~/.config/systemd/user/openclaw-frontstage-recovery-watch.service`
- `~/.config/systemd/user/openclaw-frontstage-recovery-watch.timer`

动作：

```bash
cp tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.service ~/.config/systemd/user/
cp tools/openclaw-frontstage-recovery/openclaw-frontstage-recovery-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-frontstage-recovery-watch.timer
```

验收：

```bash
python3 scripts/test-frontstage-recovery-watch.py
systemctl --user start openclaw-frontstage-recovery-watch.service
systemctl --user show openclaw-frontstage-recovery-watch.service -p Result -p ExecMainStatus -p ActiveState -p SubState
```

### 3.4 Linux resume-watch

检查：

- `scripts/openclaw-resume-watch.sh`
- `~/.config/systemd/user/openclaw-resume-watch.service`
- `~/.config/systemd/user/openclaw-resume-watch.timer`

动作：

```bash
systemctl --user daemon-reload
systemctl --user enable --now openclaw-resume-watch.timer
systemctl --user start openclaw-resume-watch.service
```

验收：

```bash
systemctl --user show openclaw-resume-watch.service -p Result -p ExecMainStatus -p ActiveState -p SubState
systemctl --user show openclaw-resume-watch.timer -p UnitFileState -p ActiveState -p SubState
```

### 3.5 daily-transcript-aggregator

检查：如上不变。

### 3.6 新版 Watcher 体系（v2 整合）

**背景**：watcher 从 7 timer 精简为 5（health-collector 合并 3 个，lifecycle-maintainer 合并 2 个，task-scheduler 监工管理内迁）。

检查：`scripts/openclaw-health-collector.py` `scripts/openclaw-task-scheduler.py` `scripts/openclaw-frontstage-guardian.py` `scripts/openclaw-lifecycle-maintainer.py` `scripts/flush-memory-sync.sh`

动作：
```bash
systemctl --user restart openclaw-health-collector.timer
systemctl --user restart openclaw-task-scheduler.timer
systemctl --user restart openclaw-frontstage-guardian.timer
systemctl --user restart openclaw-lifecycle-maintainer.timer
python3 scripts/openclaw-health-collector.py --print-human
python3 scripts/openclaw-task-scheduler.py --dry-run --print-human
```

验收：timer 数量 = 5；health-collector 日志 brocker rebuild skipped（非每次重建）；task-scheduler dry-run 输出 idle - fast skip。

### 3.7 搜索短路 + TTL 缓存

检查：`scripts/memory-search-local-first.py` `scripts/query-cache.py` `AGENTS.md`（三级搜索策略）

动作：
```bash
python3 scripts/memory-search-local-first.py "贾维斯" | python3 -c "import json,sys; r=json.load(sys.stdin); assert r['shortCircuited']==True; print('PASS: short-circuited')"
python3 scripts/memory-search-local-first.py "xyz不存在xyz" | python3 -c "import json,sys; assert json.load(sys.stdin)['shortCircuited']==False; print('PASS: fallback')"
python3 scripts/query-cache.py stats
```

验收：精确搜索短路 true (≥0.7)；无匹配短路 false；缓存 stats 正常。

### 3.8 耗时基线监控

检查：`scripts/openclaw-health-collector.py`（DURATION_BASELINE_MS）

动作：
```bash
python3 scripts/openclaw-health-collector.py --print-json | python3 -c "import json,sys; [assert isinstance(c.get('elapsedMs'),int) for c in json.load(sys.stdin)['checks']]; print('PASS')"
```

验收：所有 checks 含 `elapsedMs` 字段；无报错。

---

## 4. 最后恢复机器专用高级补丁

### 4.1 NVIDIA 音频 gateway patch（公司 Linux）

检查：

- `scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
- `tools/nvidia-audio-bridge/README.md`
- `~/.config/systemd/user/openclaw-nvidia-audio-bridge.service`

动作：

```bash
python3 scripts/apply-openclaw-nvidia-audio-gateway-patch.py
systemctl --user restart openclaw-nvidia-audio-bridge.service
```

验收：

- `/health`
- TTS
- ASR

按 `tools/nvidia-audio-bridge/README.md` 的步骤回归。

### 4.2 Windows battery policy（掌机）

检查：

- `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.ps1`
- `scripts/repair-openclaw-gateway-battery-policy-zhangji-windows.cmd`
- `docs/掌机-Windows-OpenClaw-维护说明.md`

动作（在掌机 Windows 上）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\repair-openclaw-gateway-battery-policy-zhangji-windows.ps1
```

验收：

- `DisallowStartIfOnBatteries = false`
- `StopIfGoingOnBatteries = false`

---

## 5. 如果某条补丁升级后失配

不要目标漂移。

正确做法是：

1. 先看注册表，确认这条补丁真正要保的**结果目标**
2. 再看当前实现入口和升级风险点
3. 若原实现入口失效（例如前端 hash / 注入点 / server impl 结构变了）
   - 允许调整实现方式
   - **但结果目标不能悄悄变**
4. 修改完成后：
   - 重新补最小验收
   - 更新注册表中的“当前实现 / 升级风险点 / 维护落点”

---

## 6. 当前推荐重建顺序（一句话版）

> 先恢复补丁自动重打入口 → 再恢复 broker / infos-handle sidecar / unified proxy → 再恢复 supervisor / local-health / recovery watcher / responsiveness watchdog / resume-watch 的 systemd 链路 → 最后恢复机器专用高级 patch，并逐项验收。
