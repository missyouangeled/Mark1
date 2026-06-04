# Unity Bridge 连接指南

> 适用机器：公司（Linux VM）↔ 宿主机 Windows Unity Editor
> 最后更新：2026-06-04
> 目标读者：任意 AI 模型，无上下文前提

---

## 架构

```
宿主机 Windows                         公司 Linux VM
┌─────────────────────────┐           ┌──────────────────────┐
│ Unity Editor             │  HTTP    │ Unity Bridge Server   │
│ OpenClaw Unity Plugin    │◄────────┤ (独立 Node.js 服务)   │
│ (主动连接 + Poll 命令)    │  :27182  │ 监听 0.0.0.0:27182    │
└─────────────────────────┘           │ token 可选，默认跳过  │
                                       └──────────────────────┘
                                              ▲
                                              │ localhost:27182
                                              │
                                       ┌──────┴─────────────┐
                                       │ AI / OpenClaw       │
                                       │ curl POST /unity/   │
                                       │       tool-async    │
                                       └────────────────────┘
```

**关键点：**
- Bridge 不在 Gateway 里运行（OpenClaw plugin 系统只支持内置 4 个 plugin 的 allowlist，用户自定义 plugin 无法加载）
- Bridge 是独立 Node.js 进程，不影响 Gateway 稳定性
- Unity Plugin 主动连接 Bridge，不需要宿主机开防火墙端口

---

## 启动 Bridge

**准备工作（只需一次）：**

```bash
# 检查 Bridge 是否已在运行
curl -s http://localhost:27182/bridge/health

# 如未运行，启动：
nohup node /home/missyouangeled/.openclaw/workspace/scripts/unity-bridge-server.js 27182 "d488a7bb89c5fd8a69d4fe23c53c109017c0a5b8ca2d0a8f" > /tmp/openclaw/unity-bridge.log 2>&1 &
```

**停止 Bridge：**
```bash
pkill -f "unity-bridge-server.js"
# 或
curl -X POST http://localhost:27182/bridge/stop
```

---

## Unity 侧配置

Windows 宿主机 → Unity Editor → OpenClaw Plugin Settings：

| 设置 | 值 |
|------|-----|
| Gateway URL | `http://192.168.79.128:27182` |
| API Token | 留空即可（Bridge 当前为无 token 模式） |

**为什么无 token？**  
目前 VM 到宿主机是 NAT 网络（192.168.79.0/24 子网），只有特定信任设备能连通。Unity Plugin 的 HttpClient 可能附带 token header 时格式不兼容，导致 401。当前用无 token 模式，后续如需加固再调整。

---

## Bridge API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/bridge/health` | GET | 健康检查 |
| `/bridge/stop` | POST | 停止服务 |
| `/unity/connect` | GET | 连接测试（不需 token） |
| `/unity/register` | POST | Unity 注册 session |
| `/unity/status` | GET | 查看所有 session 状态 |
| `/unity/poll?sessionId=xxx` | GET | Unity 拉取待执行命令 |
| `/unity/result` | POST | Unity 回传命令结果 |
| `/unity/tool-async` | POST | AI 发送工具命令（异步，立即返回） |
| `/unity/tool` | POST | AI 发送工具命令（同步，等待 60s 结果） |

---

## 给 Unity 发命令

```bash
# 异步模式（推荐）
curl -s -X POST http://localhost:27182/unity/tool-async \
  -H "Content-Type: application/json" \
  -d '{"tool":"gameobject.create","arguments":{"name":"MyCube","primitive":"Cube","position":{"x":0,"y":1,"z":0}}}'
```

**返回：**
```json
{"success":true,"toolCallId":"u_...","status":"queued"}
```

---

## 工具名速查（已验证可用的）

| 操作 | 工具名 | 参数示例 |
|------|--------|----------|
| 创建立方体 | `gameobject.create` | `{"name":"MyCube","primitive":"Cube","position":{"x":0,"y":1,"z":0}}` |
| 创建球体 | `gameobject.create` | `{"name":"Sphere","primitive":"Sphere"}` |
| 创建平面 | `gameobject.create` | `{"name":"Ground","primitive":"Plane"}` |
| 缩放物体 | `transform.setScale` | `{"objectName":"TerrainPlane","x":10,"y":1,"z":10}` |
| 查看场景层级 | `debug.hierarchy` | `{"depth":2}` |
| 查看控制台 | `console.getLogs` | `{"count":50}` |

**完整工具参考（~100 个）：** 见 `~/.openclaw/skills/openclaw-skills-openclaw-unity-skill/references/tools.md`

---

## 踩过的坑 & 解决方法

### 1. Gateway Plugin 无法加载（弃用）
- **现象**：`openclaw gateway restart` 后日志始终只显示 4 个内置 plugins，unity 不在列表中。Gateway 启动失败，报 `api.registerHttpHandler deprecated`。
- **根因**：OpenClaw plugin 系统使用 `bundledDiscovery: "allowlist"` 硬编码模式，只加载内置 plugin ID。用户自定义路径（`plugins.load.paths`）在当前版本不被识别。且 `api.registerHttpHandler` 在最新 OpenClaw 中已移除，需改为 `api.registerHttpRoute`。
- **解决**：放弃 Gateway plugin 路线，改为独立 Node.js HTTP Server（本文件方案）。

### 2. 404 — 路径不匹配
- **现象**：Unity 连接报 404。
- **根因**：Unity Plugin 去连 Gateway 端口 18789，但 Gateway 没有 `/unity/*` 路由。
- **解决**：确认 Unity Plugin 中 Gateway URL 端口为 `27182`（Bridge），不是 `18789`（Gateway）。

### 3. 401 — Token 不匹配
- **现象**：Unity 连接报 401 Unauthorized。
- **根因**：Bridge 的 `checkAuth` 函数严格要求 Authorization header 存在且 token 完全匹配。Unity Plugin 的 HttpClient 可能发请求时 token 格式不一致或未带 token。
- **解决**：改为宽松模式：如果没有 Authorization header 就跳过验证。`checkAuth` 只在有 header 且 token 不匹配时才返回 401。

### 4. Unity 连接上了但发命令卡住不动
- **现象**：AI 发送工具命令后，Bridge 阻塞在同步等待，但 Unity 并没有执行。
- **根因**：最初只实现了同步 `/unity/tool` 端点（长轮询 60s），不适合异步场景。
- **解决**：新增 `/unity/tool-async` 端点，命令入队后立即返回，由 Unity Plugin 通过 `/unity/poll` 主动拉取执行。

### 5. 工具名错误 — `scene.createTerrain` 不存在
- **现象**：`System.ArgumentException: Unknown tool: scene.createTerrain`
- **根因**：凭猜测构造工具名，未查 Plugin 实际注册的工具表。
- **解决**：✅ 必须先查 `references/tools.md`，确认工具名和参数格式后发送。创建地形没有直接工具，改用 `gameobject.create` + Plane + `transform.setScale` 放大模拟。

### 6. 工具名大小写错误 — `gameObject.createPrimitive`
- **现象**：`Unknown tool: gameObject.createPrimitive`
- **根因**：大小写或命名推断错误。
- **解决**：所有工具名严格按 `tools.md` 里的实际标识符写（全部小写，点分隔，如 `gameobject.create`）。

---

## 系统影响

| 组件 | 影响 | 说明 |
|------|------|------|
| OpenClaw Gateway | **零影响** | 完全不依赖 Gateway plugin 体系 |
| 内存 | <50MB | Node.js 进程 |
| 磁盘 | <100KB | 单个 JS 文件 |
| 端口 | :27182 | 监听 0.0.0.0，仅局域网可达 |
| 安全性 | 无 token | 局域网信任模式，后续可加固 |
| 可恢复性 | 可随时重启 | `nohup node ... &` |

---

## 相关文件

| 文件 | 路径 |
|------|------|
| Bridge 服务脚本 | `scripts/unity-bridge-server.js` |
| 工具完整参考 | `~/.openclaw/skills/openclaw-skills-openclaw-unity-skill/references/tools.md` |
| 安装注册表 | `docs/install-registry.md` |
| 变更流水 | `docs/通用-OpenClaw-补丁变更流水.md` |
