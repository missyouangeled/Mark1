# Mark42 Frontstage / Control UI 集成调研 (2026-07-20)

## 现状

OpenClaw 已有一套完整的前台状态广播系统：

```
事件源 -> events.jsonl -> broker 重建视图 -> snapshot.json
                                          -> canvas 面页 (HTML)
                                          -> infos-handle sidecar (HTTP/SSE API)
                                          -> Control UI 前端
```

### 已有基础设施

| 组件 | 路径 | 状态 |
|---|---|---|
| frontstage-broker | `scripts/openclaw-frontstage-broker.py` | ✅ 运行中 |
| infos-handle sidecar | `scripts/openclaw-infos-handle-sidecar.py` | ✅ 监听 127.0.0.1:18790 |
| broker 视图 | `~/.local/state/openclaw/broker/views/snapshot.json` | ✅ 4 个 panel (frontstage/health/supervisor/recovery) |
| canvas 页面 | `~/.openclaw/canvas/documents/frontstage-status/index.html` | ✅ 自动渲染 |
| 事件源 | `~/.local/state/openclaw/broker/events.jsonl` | ✅ 支持 source 事件注入 |

### broker 已有 panel

| panel | severity | 用途 |
|---|---|---|
| frontstage | ok | 最近辅助投递状态 |
| health | ok | 本地健康检查 |
| supervisor | ok | 后台任务/监工 |
| recovery | warn | 前台投影异常检测 |

**mark42 已作为 source 出现在 events.jsonl 里**，但没有独立 panel。

## 集成方案

### 方案 A：事件注入（最小可用，0.5 天）

Mark42 的 armor-guard / engine-daemon 定期把状态写入 broker events.jsonl，利用现有 broker 基础设施自动渲染。

**实现**：
1. 在 `engine.py` 的 daemon 循环里加一步：写 broker 事件
2. 事件格式：
```json
{
  "source": "mark42",
  "event": "mark42.status",
  "summary": "Mark42 v2.4.0 | 上下文 68.5% | armor+engine active",
  "severity": "info",
  "data": {
    "version": "2.4.0",
    "contextPercent": 68.5,
    "armor": "active",
    "engine": "active",
    "loops": {"active": 4, "registered": 4}
  }
}
```
3. broker 自动重建视图 -> snapshot.json -> canvas 页面 -> Control UI

**优点**：零侵入，不改 broker/sidecar 代码
**缺点**：mark42 状态只出现在事件流里，没有独立 panel 卡片

### 方案 B：独立 Panel（1-2 天）

在 broker 的 `panels` 字典里注册一个 `mark42` panel，和 health/supervisor/recovery 平级。

**实现**：
1. 写一个 `mark42-frontstage-source.py` 脚本，定期输出 panel 数据
2. 在 broker 的 source 配置里注册 mark42
3. 修改 canvas HTML 模板加一个 mark42 卡片
4. 或者通过 `[embed ...]` 指令在聊天消息里嵌入 mark42 状态卡片

**优点**：Control UI 上有独立的 Mark42 状态卡片
**缺点**：需要改 broker 配置和 canvas 模板

### 方案 C：Status JSON API（0.5 天）

`mark42 status --json` 已有 JSON 输出能力。让 infos-handle sidecar 把它作为自定义 source 暴露：

```
GET /v1/query/mark42.status?format=json
```

**优点**：API 可编程访问，任何前端都能拉
**缺点**：需要改 infos-handle sidecar 注册逻辑

## 推荐路径

**先 A 后 B**：
1. 现在花 30 分钟做方案 A（事件注入），让 Mark42 状态出现在 broker 事件流里
2. 后续再做方案 B（独立 panel），等 OpenClaw 的 panel 注册机制稳定后

## 技术风险

- broker 的事件格式和 panel 注册机制是 OpenClaw 内部 API，可能在升级时变化
- canvas HTML 模板每次 OpenClaw 升级可能被覆盖（已有 branding 脚本处理）
- infos-handle sidecar 的 contract 版本可能变化

## 结论

**可行。现有基础设施足够，不需要改 OpenClaw 核心。最小方案 30 分钟可完成。**
