# Unity Bridge 连接指南

> 适用机器：公司（Linux VM）↔ 宿主机 Windows Unity Editor
> 最后更新：2026-08-06（**已改为 systemd 管理，见下方「统一入口」**）
> 目标读者：任意 AI 模型，无上下文前提

---

## 🔴 先看这里：已改为 systemd 模块管理（2026-08-06）

Bridge 和 MCP **不再用 nohup 手动启动**。两者已合并为一个 systemd 模块，开机自启 + 崩溃自愈。

```
openclaw-unity.target                ← 总开关
├─ openclaw-unity-bridge.service     老 Bridge   :27182
└─ openclaw-unity-mcp.service        CoplayDev   :8080
```

**统一入口 `scripts/unity-stack-patch.sh`（默认 dry-run，加 `--apply` 才动手）：**

| 需求 | 命令 |
|------|------|
| 看状态 | `bash scripts/unity-stack-patch.sh status` |
| **实际调用验收** | `bash scripts/unity-stack-patch.sh verify` |
| 两个一起开 | `bash scripts/unity-stack-patch.sh start --apply` |
| 两个一起关 | `bash scripts/unity-stack-patch.sh stop --apply` |
| 重装 | `bash scripts/unity-stack-patch.sh install --apply` |
| 整个模块卸掉 | `bash scripts/unity-stack-patch.sh uninstall --apply` |

单元源文件在 `config/systemd/unity-stack/`（仓库内），安装到 `~/.config/systemd/user/`。

⚠️ **不要单独 enable 成员服务**，统一由 target 拉起，否则会出现半启动状态。
⚠️ **不要再用 `nohup` 手启**，会和 service 抢端口。要重启走上表的 `start/stop`。

### 为什么改（2026-08-06 事故，CASE-20260806-018）

两者原先都是 nohup 裸进程。当天一次意外重启把它俩双双带走：
Unity 插件报 `An error occurred while sending the request`，MCP 点 Connect 无反应。
用户一天内手动拉起两次。**裸进程 = 重启即失联、无自愈、无留痕。**

实测自愈已验证：`kill -9` Bridge 进程后 8 秒自动复活（pid 变更），`Restart=always` 生效。

### 开机自启的前提：Linger

user 级 systemd 默认「首次登录才启动」。本机已 `Linger=yes`（2026-08-06 确认）。
若哪天开机不自启，先查这个：

```bash
loginctl show-user $USER | grep Linger
# 为 no 则：sudo loginctl enable-linger $USER
```

---

## 架构（当前实际运行的）

```
宿主机 Windows                            公司 Linux VM
┌─────────────────────────┐             ┌──────────────────────┐
│ Unity Editor             │  HTTP      │ Unity Bridge Server   │
│ OpenClaw Unity Plugin    │◄──────────►│ (独立 Node.js 服务)   │
│ (主动连接 + Poll 命令)    │  :27182    │ 监听 0.0.0.0:27182    │
└─────────────────────────┘             │ token 可选，默认跳过  │
                                        └──────────────────────┘
                                               ▲
                                               │ localhost:27182
                                               │
                                        ┌──────┴─────────────┐
                                        │ AI / OpenClaw       │
                                        │ curl POST /unity/   │
                                        │       tool          │
                                        └────────────────────┘

另外，Gateway 插件也已修复（端口 18789 上 /unity/* 路由可用），
但 Unity Editor 插件实际连接走的是 Bridge（27182），不是 Gateway。
Gateway 插件用于 AI agent tools（unity_execute / unity_sessions）。
```

### 两套系统并存

| 系统 | 端口 | 用途 | 状态 |
|------|------|------|------|
| Bridge 独立服务 | 27182 | Unity Editor 连接 + AI 发命令 | ✅ 主要使用 |
| Gateway 插件 | 18789 | AI agent tools（unity_execute 等） | ✅ 已修复，可用但 session 与 Bridge 独立 |

⚠️ **Bridge 和 Gateway 插件有各自的 session 存储，互不共享。**
- Unity 通过 Bridge（27182）注册的 session，Gateway 插件的 `unity_execute` 工具看不到
- AI 发命令应通过 Bridge 的 `/unity/tool` 或 `/unity/tool-async` HTTP 端点
- Gateway 插件的 agent tools 是另一条路径，适合 OpenClaw 原生工具调用

**当前推荐方式：AI 通过 Bridge HTTP 端点发命令（同步 `/unity/tool` 或异步 `/unity/tool-async`）**

---

## 启动 Bridge

> ⚠️ **以下 nohup 方式已废弃**，保留仅作原理参考。
> 正常操作请用文首的 `scripts/unity-stack-patch.sh start --apply`。
> 手动 nohup 会和 systemd service 抢 27182 端口。

```bash
# 检查 Bridge 是否已在运行
curl -s http://localhost:27182/bridge/health

# ❌ 已废弃（会与 service 抢端口）：
# nohup node /home/missyouangeled/.openclaw/workspace/scripts/unity-bridge-server.js 27182 > /tmp/openclaw/unity-bridge.log 2>&1 &

# ✅ 现在用：
# systemctl --user start openclaw-unity.target
# 日志：~/.local/state/openclaw/unity-stack/unity-bridge.log

# 停止（已废弃的方式）：
pkill -f "unity-bridge-server.js"
# 或
curl -X POST http://localhost:27182/bridge/stop
```

---

## Unity 侧配置

Windows 宿主机 -> Unity Editor -> Window -> OpenClaw Plugin -> Settings：

| 设置 | 值 |
|------|-----|
| Gateway URL | `http://192.168.79.128:27182` |
| API Token | 留空 |
| Auto Connect | ✅ 勾选 |
| Show Status Overlay | ✅ 勾选 |
| Heartbeat Interval | 30 秒 |
| MCP Bridge Port | `27182`（不要用 18789） |
| Enable MCP Bridge | ✅ 勾选 |

### ⚠️ 端口不能设为 18789

18789 是 Gateway 端口。Unity 插件的 "Remote Gateway Connection" 连 Gateway 端口时
会报 "An error occurred while sending the request"（连接请求发不出去）。
必须用 27182（Bridge 端口）。

### 为什么无 token？

VM 到宿主机是 NAT 网络（192.168.79.0/24 子网），只有特定信任设备能连通。
Bridge 的 `checkAuth` 函数在没有 Authorization header 时跳过验证。

---

## Bridge API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/bridge/health` | GET | 健康检查 |
| `/bridge/stop` | POST | 停止服务 |
| `/unity/connect` | GET | 连接测试（不需 token） |
| `/unity/register` | POST | Unity 注册 session |
| `/unity/heartbeat` | POST | 心跳保活 |
| `/unity/status` | GET | 查看所有 session 状态 |
| `/unity/poll?sessionId=xxx` | GET | Unity 拉取待执行命令 |
| `/unity/result` | POST | Unity 回传命令结果 |
| `/unity/tool` | POST | AI 发送工具命令（同步，等 60s 结果） |
| `/unity/tool-async` | POST | AI 发送工具命令（异步，立即返回） |

---

## AI 发命令给 Unity

```bash
# 同步模式（等待 Unity 执行完返回结果，最多 60s）
curl -s -X POST http://localhost:27182/unity/tool \
  -H "Content-Type: application/json" \
  -d '{"tool":"debug.hierarchy","arguments":{"depth":2}}'

# 异步模式（立即返回，结果由 Unity poll 后执行）
curl -s -X POST http://localhost:27182/unity/tool-async \
  -H "Content-Type: application/json" \
  -d '{"tool":"gameobject.create","arguments":{"name":"MyCube","primitive":"Cube","position":{"x":0,"y":1,"z":0}}}'
```

---

## 工具名速查（已验证可用的）

| 操作 | 工具名 | 参数示例 |
|------|--------|----------|
| 查看场景层级 | `debug.hierarchy` | `{"depth":2}` |
| 截图 | `debug.screenshot` | `{}` |
| 查看控制台日志 | `console.getLogs` | `{"count":50}` |
| 查看控制台错误 | `console.getErrors` | `{"count":50}` |
| 获取活跃场景 | `scene.getActive` | `{}` |
| 列出所有场景 | `scene.list` | `{}` |
| 查找物体 | `gameobject.find` | `{"name":"Player"}` |
| 创建立方体 | `gameobject.create` | `{"name":"MyCube","primitive":"Cube","position":{"x":0,"y":1,"z":0}}` |
| 移动物体 | `transform.setPosition` | `{"objectName":"Player","x":10,"y":0,"z":5}` |
| 旋转物体 | `transform.setRotation` | `{"objectName":"Player","x":0,"y":90,"z":0}` |
| 缩放物体 | `transform.setScale` | `{"objectName":"Player","x":2,"y":2,"z":2}` |
| 获取组件 | `component.get` | `{"gameObject":"Player","type":"Transform"}` |
| Play 模式 | `app.play` | `{}` |
| Stop 模式 | `app.stop` | `{}` |
| 获取应用状态 | `app.getState` | `{}` |
| 编辑器状态 | `editor.getState` | `{}` |
| 编辑器 Play | `editor.play` | `{}` |
| 编辑器 Stop | `editor.stop` | `{}` |
| UI 点击 | `input.clickUI` | `{"path":"Canvas/Button"}` |
| 键盘输入 | `input.keyPress` | `{"key":"Space"}` |

**完整工具参考（~100 个）：** 见 `~/.openclaw/skills/openclaw-skills-openclaw-unity-skill/references/tools.md`

---

## 2026-08-06 修复记录（OpenClaw 2026.7.1-2）

### 背景

OpenClaw 从 2026.6.x 升级到 2026.7.1-2 后，Unity Bridge 连接断了。
排查发现多个层面的兼容性问题。

### 修复 1：Gateway 插件清单缺 `activation.onStartup`

- **现象**：Gateway 启动只加载 7 个插件，unity 不在列表
- **根因**：OpenClaw 2026.7.1 改了插件启动机制——`enabled: true` 只代表"允许启用"，
  不再代表"随 Gateway 启动"。新版要求清单显式声明 `"activation": {"onStartup": true}`
- **修复**：在 `~/.openclaw/extensions/unity/openclaw.plugin.json` 添加 `activation.onStartup`
- **文件**：`~/.openclaw/extensions/unity/openclaw.plugin.json`

### 修复 2：Gateway 插件缺 `contracts.tools` 声明

- **现象**：日志报 `plugin must declare contracts.tools before registering agent tools`
- **根因**：新版要求注册 Agent 工具前必须在清单声明工具归属
- **修复**：在 manifest 添加 `"contracts": {"tools": ["unity_execute", "unity_sessions"]}`

### 修复 3：`api.registerHttpHandler` 已移除

- **现象**：旧代码用 `api.registerHttpHandler(handleUnityHttpRequest)`，新版不存在
- **根因**：OpenClaw 2026.7.1 移除了 `registerHttpHandler`，改为 `registerHttpRoute`
- **修复**：改为 `api.registerHttpRoute({path:"/unity", match:"prefix", auth:"plugin", handler:...})`

### 修复 4：Bridge 端口与 Gateway 端口混淆

- **现象**：Unity 插件 "Remote Gateway Connection" 报 "An error occurred while sending the request"
- **根因**：MCP Bridge Port 被设为 18789（Gateway 端口），Unity 插件连不上 Gateway
- **修复**：Gateway URL 改为 `http://192.168.79.128:27182`，MCP Bridge Port 改为 `27182`

### 修复 5：清理定时器 `unref()`

- **现象**：`openclaw plugins inspect unity` 等 CLI 命令挂起不退出
- **根因**：`setInterval` 不调 `unref()` 会阻止 Node.js 进程退出
- **修复**：添加 `cleanupTimer.unref()`

### 修复 6：Gateway 插件补 `connect` / `tool` / `tool-async` 端点

- **现象**：Gateway 插件只有 register/heartbeat/poll/result/status，缺 connect/tool/tool-async
- **修复**：在 `handleUnityHttpRequest` 的 switch 语句中添加这三个端点

### 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `~/.openclaw/extensions/unity/openclaw.plugin.json` | 添加 `activation.onStartup` + `contracts.tools` |
| `~/.openclaw/extensions/unity/index.ts` | 改用 `registerHttpRoute` + 添加 connect/tool/tool-async 端点 + cleanupTimer.unref() |
| `~/.openclaw/extensions/unity/index.js` | 编译产物（esbuild ESM bundle, openclaw external） |

### 备份文件

| 文件 | 说明 |
|------|------|
| `index.ts.orig` | 原始版本（从 skill 安装的） |
| `index.ts.bad-ctx-20260806-1108` | 第一次修改失败版本 |

---

## 踩过的坑 & 解决方法（历史）

### 1. Gateway Plugin 无法加载（2026-06-04 弃用，2026-08-06 修复恢复）

- **现象**：Gateway 启动后日志只显示内置 plugins，unity 不在列表
- **根因**：`bundledDiscovery: "allowlist"` + 旧版没有 `activation.onStartup` 字段
- **解决**：2026-08-06 补齐 manifest 字段后 Gateway 插件已可正常加载

### 2. 404 - 路径不匹配

- **现象**：Unity 连接报 404
- **根因**：Unity Plugin 去连 Gateway 端口 18789，但 Gateway 没有 `/unity/*` 路由
- **解决**：确认 Unity Plugin 中 Gateway URL 端口为 `27182`（Bridge），不是 `18789`（Gateway）

### 3. 401 - Token 不匹配

- **现象**：Unity 连接报 401 Unauthorized
- **根因**：Bridge 的 `checkAuth` 函数严格要求 token 匹配
- **解决**：改为宽松模式：如果没有 Authorization header 就跳过验证

### 4. Unity 连接上了但发命令卡住不动

- **现象**：AI 发送工具命令后，Bridge 阻塞在同步等待
- **根因**：最初只实现了同步 `/unity/tool` 端点（长轮询 60s）
- **解决**：新增 `/unity/tool-async` 端点，命令入队后立即返回

### 5. 工具名错误

- **现象**：`Unknown tool: scene.createTerrain`
- **根因**：凭猜测构造工具名
- **解决**：必须先查 `references/tools.md`，确认工具名和参数格式

### 6. 工具名大小写错误

- **现象**：`Unknown tool: gameObject.createPrimitive`
- **根因**：大小写错误
- **解决**：所有工具名严格按 `tools.md` 里的实际标识符写（全部小写，点分隔）

### 7. MCP Bridge Port 设为 18789 导致连接失败

- **现象**：Unity 插件 "Remote Gateway Connection" 报 "An error occurred while sending the request"
- **根因**：MCP Bridge Port 被改成 18789（Gateway 端口），Unity 插件连不上 Gateway
- **解决**：MCP Bridge Port 改回 `27182`，Gateway URL 改为 `http://192.168.79.128:27182`

---

## 系统影响

| 组件 | 影响 | 说明 |
|------|------|------|
| OpenClaw Gateway | 零影响（Bridge）/ 已修复（插件） | Bridge 完全独立；Gateway 插件已修复 |
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
| Gateway 插件清单 | `~/.openclaw/extensions/unity/openclaw.plugin.json` |
| Gateway 插件源码 | `~/.openclaw/extensions/unity/index.ts` |
| Gateway 插件编译产物 | `~/.openclaw/extensions/unity/index.js` |
| 工具完整参考 | `~/.openclaw/skills/openclaw-skills-openclaw-unity-skill/references/tools.md` |
| 安装注册表 | `docs/install-registry.md` |
| 变更流水 | `docs/通用-OpenClaw-补丁变更流水.md` |
