# OpenClaw 升级后自检清单

- 适用机器:通用
- 系统 / OS:通用
- 文档类型:升级后快速自检清单

> 📖 **关联文档**：每次升级的完整记录请查看 [`docs/通用-OpenClaw-升级记录.md`](通用-OpenClaw-升级记录.md)——包括升级了什么版本、出了什么问题、怎么修复的、有哪些经验教训。升级后如发现新问题，除了修复外，还应追加到升级记录中。

## 用途

这份清单只回答一个问题:

> **OpenClaw 更新后,现在这套"贾维斯 + broker + 前台恢复观察"还能不能正常用?**

它不是大修手册,也不是完整重建手册。

- 想快速确认"更新后还能不能用" → 看这份
- 想逐项重建所有补丁 → 看 `docs/通用-OpenClaw-补丁重建清单.md`
- 当前 broker / infos-handle 已开始分层:broker 更偏数据中心,infos-handle 负责最小 text/json 查询与前台通知

---

## 最短结论

升级后只要下面 8 条都通过，就可以把这次更新视为"基本正常"：

1. **Control UI 品牌/聊天补丁仍在**
2. **snapshot-first 入口仍在**
3. **broker / infos-handle contract 入口仍正常**
4. **infos-handle sidecar live 链仍正常**
5. **统一入口 proxy verify 仍正常**
6. **frontstage-guardian 测试通过**（替代旧 recovery-watch）
7. **5 个 watcher timer 处于 enabled+active**：health-collector(60s) / task-scheduler(60s) / guardian(20s) / lifecycle-maintainer(5min) / resume-watch(60s)
8. **sidecar / unified proxy service 仍 active**
9. **搜索短路验证通过**：本地预搜 "贾维斯" 应短路（0.1s），无匹配应降级
10. **耗时基线验证通过**：所有子检查含 elapsedMs
11. **boot-health-check 通过**：核心服务/定时器/磁盘/内存/端口扫描无异常

---

## 标准自检入口

优先使用:

```bash
python3 scripts/openclaw-post-upgrade-self-check.py --print-human
```

若需要机器可读结果:

```bash
python3 scripts/openclaw-post-upgrade-self-check.py --print-json
```

若需要把失败当成退出码:

```bash
python3 scripts/openclaw-post-upgrade-self-check.py --strict --print-human
```

---

## 这份自检实际核什么

### 1. 启动前自动重打入口仍在

检查:

- `~/.config/systemd/user/openclaw-gateway.service.d/branding.conf`
- 其中仍包含:

```ini
ExecStartPre=-/usr/bin/python3 /home/missyouangeled/.openclaw/workspace/scripts/apply-openclaw-control-ui-branding.py
```

含义:每次 gateway 启动前,都会自动重打一遍 Control UI 正式补丁。

---

### 2. live Control UI 关键补丁仍在

最小要求:

- live asset 里仍有 `JarvisProjectYieldedHistoryReply`
- live asset 里仍有 `JarvisShouldShowPendingReadingIndicator`
- live override 里仍优先指向 `/jarvis-frontstage-snapshot.json`

---

### 3. broker snapshot-first 仍可重建

标准检查:

```bash
python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-snapshot-dock
```

通过时应能确认:

- `snapshotFirst = true`
- `snapshotFirstReady = true`
- `jarvis-frontstage-snapshot.json` 存在
- `jarvis-frontstage-status.json` 仍作为兼容别名存在

---

### 4. 四个最小回归仍通过

```bash
python3 scripts/test-frontstage-broker.py
python3 scripts/test-openclaw-infos-handle.py
python3 scripts/test-infos-handle-frontstage-callers.py
python3 scripts/test-frontstage-recovery-watch.py
```

都应看到:

```text
ALL PASS
```

---

### 5. infos-handle sidecar live 链仍正常

标准检查:

```bash
python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar
```

至少应能确认:

- `controlUiInfosHandleSidecar.ok = true`
- `summaryHref / contractHref / sseHref` 正常
- `imageArtifactHref` 可取回

### 6. 统一入口 proxy verify 仍正常

标准检查:

```bash
python3 scripts/apply-openclaw-infos-handle-gateway-proxy.py --verify --print-json
```

当前最小要求:

- `localHealthzOk = true`
- `localSummaryCode = 200`
- 若当前机器存在可用 LAN IP:
  - `remoteNoAuthCode = 401`
  - `remoteWithAuthCode = 200`

### 7. 相关 watcher timer 仍正常

最少检查这 5 个：

- `openclaw-health-collector.timer`（60s，含监工管理+broker dirty+耗时基线）
- `openclaw-task-scheduler.timer`（60s，含闲时跳过）
- `openclaw-frontstage-guardian.timer`（20s，含紧急→broker dirty）
- `openclaw-lifecycle-maintainer.timer`（15min，含ChatTTS清理+flush同步）
- `openclaw-resume-watch.timer`（断线恢复）

理想状态：`UnitFileState=enabled`、`ActiveState=active`、`SubState=waiting`

### 8. sidecar / unified proxy service 仍正常

最少检查:

- `openclaw-infos-handle-sidecar.service`
- `openclaw-unified-proxy.service`(若已安装)

理想状态:

- `ActiveState=active`
- `SubState=running`

### 9. 搜索短路仍正常

检查：

```bash
python3 scripts/memory-search-local-first.py "贾维斯" | python3 -c "import json,sys; r=json.load(sys.stdin); assert r['shortCircuited']==True; print('PASS')"
python3 scripts/memory-search-local-first.py "xyz不存在xyz" | python3 -c "import json,sys; assert json.load(sys.stdin)['shortCircuited']==False; print('PASS')"
```

通过：精确搜索短路(true)，无匹配降级(false)。

### 10. 耗时基线监控仍正常

检查：

```bash
python3 scripts/openclaw-health-collector.py --print-json | python3 -c "import json,sys; [assert isinstance(c.get('elapsedMs'),int) for c in json.load(sys.stdin)['checks']]; print('PASS')"
```

通过：所有 checks 含 `elapsedMs` 字段，无报错。

---

## 如果自检没过

不要直接硬猜。

按这个顺序处理:

1. 先看 `docs/通用-OpenClaw-补丁注册表.md`
2. 再看 `docs/通用-OpenClaw-补丁重建清单.md`
3. 需要时运行:

```bash
python3 scripts/apply-openclaw-control-ui-branding.py
python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock --verify-control-ui-infos-handle-sidecar --require-control-ui-infos-handle-sidecar
python3 scripts/apply-openclaw-infos-handle-gateway-proxy.py --verify --print-json
```

---

## 现在的默认启动行为

当前已约定:

- OpenClaw 启动后,会通过 `BOOT.md` 先跑一遍升级后自检脚本
- **只有检测到 OpenClaw 版本变化**时,才会主动做一轮升级后核对并回报结果
- 若版本没变,仍按普通上线消息处理,不重复刷屏

---

## 和"补丁重建清单"的区别

- **升级后自检清单**:回答"现在还能不能正常用"
- **补丁重建清单**:回答"如果坏了,按什么顺序重建回来"
