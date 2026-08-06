# Unity MCP (CoplayDev) 使用指南

> 装于 2026-08-06。适用：公司 Linux VM ↔ Windows 宿主机 Unity Editor
> 项目：ArmoredFortress，Unity 2021.3.32f1c1
> 目标读者：任意 AI 模型，无上下文前提
> ⚠️ 本文所有"可用/不可用"都是**实测结论**，不是 README 抄的

---

## 🔴 启动方式已变（2026-08-06 改为 systemd 管理）

本服务已与老 Bridge 合并为**一个 systemd 模块**，开机自启 + 崩溃自愈，不再用 nohup：

```
openclaw-unity.target                ← 总开关
├─ openclaw-unity-bridge.service     老 Bridge   :27182
└─ openclaw-unity-mcp.service        本服务     :8080
```

统一入口（默认 dry-run，加 `--apply` 才动手）：

```bash
bash ~/.openclaw/workspace/scripts/unity-stack-patch.sh status           # 看状态
bash ~/.openclaw/workspace/scripts/unity-stack-patch.sh verify           # 实际调用验收
bash ~/.openclaw/workspace/scripts/unity-stack-patch.sh start --apply    # 两个一起开
bash ~/.openclaw/workspace/scripts/unity-stack-patch.sh stop  --apply    # 两个一起关
```

日志：`~/.local/state/openclaw/unity-stack/unity-mcp.log`
单元源文件：`config/systemd/unity-stack/`（仓库内）

⚠️ **不要再手动 nohup**，会和 service 抢 8080 端口。下文原启动命令仅作原理参考。

### 启动耗时特性（实测）

本服务启动比老 Bridge 慢：**6 秒时端口尚未 listen，约 8-14 秒才绑上 8080**。
属 `Type=simple`，systemd 报 Started 仅代表 fork 成功，不代表已 listen。
**探测时勿在 6 秒内判定失败。**

---

## 与老 Bridge 的关系

**两套系统并存，各有用途，不要混：**

| 系统 | 端口 | 用途 | 状态 |
|------|------|------|------|
| 老 Bridge (TomLeeLive) | 27182 | 简单读写、场景操作 | ✅ 可用 |
| 新 MCP (CoplayDev) | 8080 | reflect / 搜索 / 测试 / 校验 | ✅ 可用 |

两者 session 独立，互不干扰。

---

## 启动新 MCP 服务（Linux 侧）

> ⚠️ **以下 nohup 方式已废弃**（见文首），保留作原理参考。
> 正常操作用 `bash scripts/unity-stack-patch.sh start --apply`。

```bash
# ❌ 已废弃（会与 systemd service 抢 8080 端口）
cd ~/.openclaw/workspace/tools/unity-mcp-coplay/Server
nohup .venv/bin/mcp-for-unity --transport http --http-host 0.0.0.0 --http-port 8080 \
  > /tmp/openclaw/unity-mcp-coplay.log 2>&1 & disown
```

**必须绑 `0.0.0.0`**，绑 127.0.0.1 则 Windows 上的 Unity 连不进来。

验证：
```bash
cd ~/.openclaw/workspace/tools/unity-mcp-coplay/Server
.venv/bin/unity-mcp --host 127.0.0.1 --port 8080 status
# 期望：✅ Connected + 实例列表
```

停止：
```bash
pkill -f 'mcp-for-unity'
```

---

## Unity 侧配置（关键，顺序不能错）

`Window` → `MCP for Unity` → `Toggle MCP Window`（快捷键 Ctrl+Shift+M）

### 第 1 步：Advanced 页签，先开明文 HTTP

勾选 **`Allow insecure HTTP for HTTP Remote`**

⚠️ **必须先做这步。** 源码 `HttpEndpointUtility.cs:276-284` 写死：HTTP Remote 默认强制 HTTPS，
用明文 `http://` 不开这个开关会被直接拒绝。

### 第 2 步：Connect 页签，传输模式选 `HTTP Remote`

❌ **不能用 `HTTP Local`** —— 它假设 Python 服务和 Unity 在同一台机器，
点 Start Server 会在 Windows 本机找 Python 服务，而服务在 Linux VM 上，必然 `No Session`。

### 第 3 步：URL 填

```
http://192.168.79.128:8080
```

只填到端口。**不要加 `/mcp` 或 `/hub/plugin`**，Unity 会自己拼 `/hub/plugin`
（源码 `WebSocketTransportClient.BuildWebSocketUri`）。

### 第 4 步：API Key 随便填

例如 `local-dev-no-auth`

⚠️ **Connect 按钮为灰色是正常的**，不是没找对按钮。
源码 `McpConnectionSection.cs:457`：

```csharp
bool httpRemoteNeedsKey = httpRemoteSelected
    && string.IsNullOrEmpty(EditorPrefs.GetString(EditorPrefKeys.ApiKey, ""));
bool canStartSession = !httpRemoteNeedsKey && ...;
```

HTTP Remote 模式下 API Key 为空 → 按钮强制禁用。这是给 Coplay 云服务设计的。
**我们自建服务端没开 key 校验**（启动时没传 `--http-remote-hosted`），
所以填任意字符串都能过 —— 已实测：假 key 一样返回 `101 Switching Protocols` + welcome 帧。

❌ 不要点 `Get API Key` —— 那是去 Coplay 云服务申请，我们不用云服务。

### 第 5 步：点 Connect

成功标志（服务端日志）：
```
Plugin registered: <项目名> (<hash>)
Registered 35 tools for session <uuid>
```

---

## ✅ 实测可用的能力

| 能力 | 命令 | 备注 |
|------|------|------|
| 连接状态 | `unity-mcp status` | |
| 实例列表 | `unity-mcp instance list` | |
| 场景层级 | `unity-mcp scene hierarchy` | 支持分页，大场景不爆 |
| 读脚本 | `unity-mcp script read <path>` | |
| 改脚本 | `unity-mcp script edit <path> -e '<json>'` | |
| **正则搜索** | `unity-mcp code search <pattern> <文件路径>` | ⚠️ PATH 必须是**文件**，给目录会失败 |
| **Unity API 反射** | `unity-mcp reflect search <类型名>` | ⭐ 价值最高，防写出幻觉 API |
| 控制台 | `unity-mcp editor console --count N` | |
| 跑测试 | `unity-mcp editor tests` | 在 editor 子命令下，不是顶层 |
| 轮询测试 | `unity-mcp editor poll-test` | |
| 原始命令 | `unity-mcp raw <工具名> '<json>'` | 绕过 CLI bug 的万能出口 |

### ⭐ reflect 是这套最大的增益

项目是 Unity 2021.3，很多新 API 不存在。写 C# 前先 `reflect search` 验证 API 真实存在，
能挡住模型凭训练数据编造 API 的问题。

---

## ⚠️ 坏掉的 / 有坑的

### 1. `script validate` CLI 是坏的 —— 用 raw 绕过

```bash
# ❌ 坏的（上游 bug）
unity-mcp script validate <path>
# → error: Unknown or unsupported command type: validate_script

# ✅ 可用（绕过 CLI）
unity-mcp raw manage_script '{"action":"validate","name":"Pool","path":"Assets/Scripts/Game/Pool","level":"comprehensive"}'
# → status: success / diagnostics: [...]
```

**根因（2026-08-06 核实）**：不是版本错位。已下载 `v10.1.2` 正式版 tarball 核对，
里面**同样没有** `validate_script` handler。Unity 侧脚本工具只注册了 `manage_script` 一个。
服务端 CLI 发了一个 Unity 侧从来不存在的命令名 —— **上游自己的 bug，换版本无解**。

**参数要点**：用 `name`（类名，不带 .cs）+ `path`（**目录**，不含文件名），不是 `uri`。

**校验等级**（源码 `ManageScript.cs:243`）：
`basic` / `standard`（默认）/ `strict` / `comprehensive`

实测 `comprehensive` 能查出："Consider null checking"、"Creating objects in Update" 这类问题。

### 2. Roslyn 精确校验默认是关的

README 列了 Roslyn 校验，但**不是开箱可用**。源码 `ManageScript.cs:38-52` 要求：
1. 装 `Microsoft.CodeAnalysis.CSharp` NuGet 包
2. Player Settings → Scripting Define Symbols 加 `USE_ROSLYN`
3. 重启 Unity

不开 Roslyn 时降级为结构化校验（上面那个，可用，但不精确到行号）。

⚠️ **改 Scripting Define Symbols 会影响整个项目编译**，公司项目慎动。目前决定不开。

### 3. `code search` 的 PATH 必须是文件

```bash
# ❌ 给目录会失败
code search "class Pool_Manager" "Assets/Scripts"
# → ❌ Could not read file content

# ✅ 给具体文件
code search "class" "Assets/Scripts/Game/Pool/Pool.cs"
```

### 4. `resource read` 子命令不存在

CLI 没有 `resource` 命令，且它的错误处理自身会崩
（`click.exceptions.NoSuchCommand` 在新版 click 已移除）。用 `raw` 代替。

### 5. 版本错位（当前状态，暂不影响）

| 组件 | 版本 |
|------|------|
| Unity 包 | `10.1.3-beta.3`（beta 分支） |
| Server | `10.1.2` |

握手和 35 个工具都正常。已确认 `validate_script` 与此**无关**。
若后续出现其他工具调用异常，此错位是第一嫌疑。

### 6. 实例名显示为日期

实例名显示 `2026-04-28` 而非 `ArmoredFortress`（插件从项目文件夹名派生）。
**已核实是同一个项目** —— `scene hierarchy` 返回的 7 个根物体
（Canvas / SingleMode_Room_01 / StaticLightingSky / Sky and Fog Volume /
MainCamera / SceneIDMap ×2）与老 Bridge 完全一致。

---

## 改代码标准流程

1. `reflect search <API>` —— 先验证 Unity API 真实存在（防幻觉）
2. `script read <path>` —— 读现有代码
3. `code search <pattern> <file>` —— 定位要改的位置
4. `script edit <path> -e '<json>'` —— 改
5. `raw manage_script '{"action":"validate",...}'` —— 校验
6. `editor console` —— 看 Unity 编译错误
7. `editor tests` —— 跑测试
8. `editor play` / `editor stop` —— 运行验证

---

## 教训（写给未来的自己）

**README 的功能列表 ≠ 默认可用。**

2026-08-06 我推荐这套时说了三个卖点，实测两个不成立：
- ❌ "有 Roslyn 语法校验" → 默认关闭，需手动装 NuGet + 改编译符号
- ❌ "能跑 Unity Test Runner"（说没有）→ 我看漏了，其实在 `editor tests` 下面，**这条是我看错**
- ✅ "明确测过 2021.3" → 成立

**下次推荐工具前必须做的：**
1. 不只读功能列表，要读源码确认**启用条件**（`#if XXX` 编译符号、默认值、opt-in 开关）
2. 命令清单要看**全部层级**，不能只看顶层（我因此误报"没有测试功能"）
3. 装完先跑一遍**关键能力实测**，再向用户汇报能力边界

---

## 相关文件

| 文件 | 路径 |
|------|------|
| 安装目录 | `~/.openclaw/workspace/tools/unity-mcp-coplay/` |
| CLI | `Server/.venv/bin/unity-mcp` |
| 服务日志 | `/tmp/openclaw/unity-mcp-coplay.log` |
| 老 Bridge 指南 | `docs/通用-Unity-Bridge-连接指南.md` |
| 安装注册表 | `docs/install-registry.md` |
