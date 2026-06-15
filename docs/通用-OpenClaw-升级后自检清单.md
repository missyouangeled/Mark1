# OpenClaw 升级后自检清单

- 适用机器:通用
- 系统 / OS:通用
- 文档类型:升级后快速自检清单

> 📖 **关联文档**：每次升级的完整记录请查看 [`docs/通用-OpenClaw-升级记录.md`](通用-OpenClaw-升级记录.md)——包括升级了什么版本、出了什么问题、怎么修复的、有哪些经验教训。升级后如发现新问题，除了修复外，还应追加到升级记录中。
>
> ⚠️ **v2026.6.6+ 注意**：Gateway 将 Control UI 静态文件服务限制为 `assets/` 子目录。非 HTML 文件（.js/.json/.svg/.webmanifest）只能从 `assets/` 提供服务。所有品牌自定义文件（override JS、snapshot JSON、favicon 等）必须放入 `assets/`，且相关脚本的写入/验证路径也已相应更新。

## 用途

这份清单只回答一个问题:

> **OpenClaw 更新后,现在这套"贾维斯 + broker + 前台恢复观察"还能不能正常用?**

它不是大修手册,也不是完整重建手册。

- 想快速确认"更新后还能不能用" → 看这份
- 想逐项重建所有补丁 → 看 `docs/通用-OpenClaw-补丁重建清单.md`
- 当前 broker / infos-handle 已开始分层:broker 更偏数据中心,infos-handle 负责最小 text/json 查询与前台通知

---

## 最短结论

升级后只要下面 12 条都通过，就可以把这次更新视为"基本正常"：

1. **Control UI 品牌/聊天补丁仍在**
2. **snapshot-first 入口仍在**
3. **broker / infos-handle contract 入口仍正常**
4. **infos-handle sidecar live 链仍正常**
5. **统一入口 proxy verify 仍正常**
6. **frontstage-guardian 测试通过**（替代旧 recovery-watch）
7. **4 个 watcher timer 处于 enabled+active**：health-collector(60s) / task-scheduler(60s) / guardian(20s) / lifecycle-maintainer(5min)（resume-watch 用户明确要求不启用）
8. **sidecar / unified proxy service 仍 active**
9. **搜索短路验证通过**：本地预搜 "贾维斯" 应短路（0.1s），无匹配应降级
10. **耗时基线验证通过**：所有子检查含 elapsedMs
11. **boot-health-check 通过**：核心服务/定时器/磁盘/内存/端口扫描无异常
12. **模型配置检测通过**：所有 provider 的 apiKey 是否到位、models 数组格式（id/name/input）是否正确、imageModel 指向的模型是否 supports image input

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
- `~/.config/systemd/user/openclaw-gateway.service.d/model-selector.conf`
- 其中仍包含:

```ini
ExecStartPre=-/usr/bin/python3 /home/missyouangeled/.openclaw/workspace/scripts/apply-openclaw-control-ui-branding.py
ExecStartPre=-/usr/bin/python3 /home/missyouangeled/.openclaw/workspace/scripts/apply-openclaw-session-model-selector-fix.py
```

含义:每次 gateway 启动前,都会自动重打一遍 Control UI 正式补丁。

---

### 2. live Control UI 关键补丁仍在

最小要求:

- live asset 里仍有 `JarvisProjectYieldedHistoryReply`（⚠️ v2026.6.6+ Rolldown 模块拆分后此项可能因注入目标迁移而缺失，属已知限制）
- live asset 里仍有 `JarvisShouldShowPendingReadingIndicator`（同上）
- live override 里 snapshotJsonHref 指向 `/__openclaw__/control-ui/assets/jarvis-frontstage-snapshot.json`（v2026.6.6+）
- live override 的 infos-handle Href 已改为同源 `/v1/...`（如 `/v1/query/snapshot.summary?format=json` / `/v1/query/contract.catalog?format=json` / `/v1/events/stream?kind=snapshot.summary`），且不再写死 `http://127.0.0.1:18790`
- live asset 里 reading-indicator 片段已使用 `let pendingIndicator=JarvisShouldShowPendingReadingIndicator(e)`，不再出现会触发重复声明的 `let c=...`
- 对当前 `dist/control-ui/assets/index-*.js` 执行 `node --check` 应通过
- live asset 里模型下拉仍带 `s?.resolved?.modelProvider` / `refresh-tools-effective`，且旧的 `if(_U(e)===t)return!0` 早退分支不存在
- live override 文件位于 `dist/control-ui/assets/jarvis-branding-override.js`（v2026.6.6+）且 HTTP 可访问（200）

---

### 3. broker snapshot-first 仍可重建

标准检查:

```bash
python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-snapshot-dock
```

通过时应能确认:

- `snapshotFirst = true`
- `snapshotFirstReady = true`
- `assets/jarvis-frontstage-snapshot.json` 存在（v2026.6.6+）
- `assets/jarvis-frontstage-status.json` 仍作为兼容别名存在（v2026.6.6+）

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
- `summaryHref / contractHref / sseHref` 当前默认是同源 `/v1/...` 相对路径，而不是重新退回 `http://127.0.0.1:18790/...`
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

---

## 第 12 条：模型配置检测（新增 2026-06-12）

### 来源

v2026.6.5 升级后出现两个模型配置相关故障：
1. `litellm.models` 格式错误导致 Gateway 拒绝启动（`expected array` / `expected string`）
2. `deepseek` provider 缺少 `apiKey` 导致主模型偶发报错

此后模型配置检测被纳入升级后自检固定项目。

### 检测内容

```bash
python3 -c "
import json
with open('\$HOME/.openclaw/openclaw.json') as f:
    cfg = json.load(f)

# 1. 检查所有 provider 的 apiKey
for pid, pdata in cfg['models']['providers'].items():
    has_key = bool(pdata.get('apiKey'))
    if not has_key and pid not in ('ollama','litellm','openrouter'):
        print(f'WARN: {pid} provider 缺少 apiKey')

# 2. 检查 litellm models 数组格式
lm = cfg['models']['providers'].get('litellm')
if lm and 'models' in lm:
    models = lm['models']
    assert isinstance(models, list), 'litellm.models 必须是数组'
    for m in models:
        assert 'id' in m and 'name' in m and 'input' in m
        print(f'OK: litellm model id={m[\"id\"]} input={m[\"input\"]}')

# 3. 检查 imageModel 指向的模型是否存在
im = cfg['agents']['defaults']['imageModel']['primary']
provider, model_id = im.split('/', 1)
assert provider in cfg['models']['providers']
print(f'OK: imageModel={im}')
"
```

### 常见问题

| 检测项 | 错误信息 | 修复 |
|--------|----------|------|
| provider 缺 apiKey | `WARN: xxx provider 缺少 apiKey` | 从 SQLite auth store 恢复或手动补写 `apiKey` |
| litellm.models 格式 | `expected array, received object` | 改为数组，每项含 `id`/`name`/`input` |
| litellm model 缺字段 | `expected string, received undefined` | 确保每个 model 条目含 `name` 字段 |
| imageModel 未注册 | `Unknown model: xxx` | provider 中声明 models 并包含 `input: ["image"]` |
