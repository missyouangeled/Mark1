# OpenClaw Local Health

- 适用机器：公司（Linux）（脚本本身也可给其他 Linux 机器复用）
- 系统 / OS：Linux
- 用途：在不依赖 AI 模型回复的前提下，对本机 OpenClaw 做本地健康诊断，尽量把故障归类为 gateway、本机外联、或模型提供商路由问题。

## 当前产物

- 诊断脚本：`scripts/openclaw-local-health-diagnose.py`
- systemd service 模板：`tools/openclaw-local-health/openclaw-local-health-watch.service`
- systemd timer 模板：`tools/openclaw-local-health/openclaw-local-health-watch.timer`

## 诊断输出

默认会写到：

- `~/.local/state/openclaw/local-health/last-report.json`
- `~/.local/state/openclaw/local-health/last-summary.txt`
- `~/.local/state/openclaw/local-health/health-diagnostic.log`

当前输出规则：

- `last-summary.txt` 首行会尽量给出简明结论，例如：`本机网络不通`、`AI 模型路由不通`、`Gateway 不可达`
- `last-report.json` 会额外带 `issueOverview` 与 `issues` 字段，便于页面或后续脚本直接取简明概述 + 详细问题列表
- `health-diagnostic.log` 在检测到异常时会追加更详细的排查信息，包括 gateway 状态、失败探针、失败 provider、错误明细；恢复正常时会追加一条 `RECOVERED` 记录
  - 日志会做保守留存：超过约 2MB 时自动裁到最近约 1MB，避免长期涨大
- 还会同步生成一个固定的本地健康监督页面：`~/.openclaw/canvas/documents/local-health-status/index.html`
  - 控制台 / WebChat 可通过 `/__openclaw__/canvas/documents/local-health-status/index.html` 打开
  - 同目录还会生成 `status.json`，便于后续脚本或页面读取摘要状态
- 还会额外同步一份 **Control UI 公共静态副本** 到安装目录：
  - `jarvis-local-health-status.html`
  - `jarvis-local-health-status.json`
  - 用途：给 Control UI 固定入口卡片读取状态，避开 `/__openclaw__/canvas/...` 这类受保护路径的 401 未授权问题
- Control UI 当前默认入口已升级成一个统一的“前台状态”小圆角按钮：
  - 默认挂在顶部工具栏区域下方，并向下展开，尽量不遮住上方按钮
  - 按钮优先读取 broker 生成的 `jarvis-frontstage-snapshot.json`，并打开 `jarvis-frontstage-status.html`
  - `jarvis-frontstage-status.json` 这类旧名字当前只再作为兼容别名保留，不是新的正式入口
  - 本地健康自己的独立页面与 JSON 副本仍继续保留：`jarvis-local-health-status.html` / `jarvis-local-health-status.json`
  - 点击小按钮 → 展开详情卡片
  - 点击卡片右上角 `×` → 收起回小按钮
- 页面和卡片都会带一组**无 AI 的本地自救建议**：
  - 例如当状态正常但页面仍卡住时，会直接提示优先刷新页面 / 重开浏览器
  - 当 Gateway / 网络 / AI 模型异常时，会给出对应的确定性排查动作
  - 当前也会额外显示：`温度`、`负载 / 内存`
- 页面会把结果收敛成更直观的几类判断：`Gateway`、`网络`、`AI 模型`、`温度`、`负载 / 内存`
- 页面会根据 `checkedAt` 自动判断数据是否过期，超过约 12 分钟提示“可能过期”，超过约 20 分钟提示“可能已失效”

## 手工运行

```bash
python3 scripts/openclaw-local-health-diagnose.py --print-human
python3 scripts/openclaw-local-health-diagnose.py --print-json
python3 scripts/openclaw-local-health-diagnose.py --notify-frontstage --print-human
```

退出码：

- `0` = 正常
- `1` = 告警 / 部分路由不可达
- `2` = 严重异常 / Gateway 不可达 / 外网探测全部失败

## 检查项

当前最小实现会做：

1. `openclaw status --json` 本地探测
2. Gateway reachability / service runtime 判断
3. 通用外网探测（当前默认：GitHub API、百度首页）
4. `~/.openclaw/openclaw.json` 中已配置模型 provider 的 `baseUrl` 路由探测（其中当前默认主线 provider 作为核心告警对象，其他 provider 仅作补充参考）

说明：

- 这里的 provider 探测主要验证“网络和路由可达”，不是完整调用一次模型。
- 当前默认主线 provider 会在摘要里标成 `*`；非主线 provider 失败不会单独把整体状态拉成告警，只作为补充线索保留在报告里。
- 因此它更像“死因分类器”，而不是“端到端模型成功率证明器”。
- 即便 provider 返回 `401/404`，也会被视为“路由可达”。

## 宿主机温度桥接（A 路线）

当前 VM / 容器环境如果读不到真实 CPU 温度，可由**宿主机**把温度写入桥接 JSON，然后本地健康层直接读取。

默认桥接路径：

- `~/.local/state/openclaw/local-health/host-thermal-bridge.json`

也可用环境变量覆盖：

- `OPENCLAW_HOST_THERMAL_JSON=/path/to/host-thermal-bridge.json`
- `OPENCLAW_HOST_THERMAL_DIR=/path/to/bridge-dir`（脚本会自动拼上 `host-thermal-bridge.json`）

若 Linux 客体启用了 VMware 共享文件夹，当前也会自动尝试这些常见位置：

- `/mnt/hgfs/OpenClawBridge/host-thermal-bridge.json`
- `/mnt/hgfs/openclaw-bridge/host-thermal-bridge.json`
- `/mnt/hgfs/openclaw-local-health/host-thermal-bridge.json`
- 以及 `/mnt/hgfs/*/host-thermal-bridge.json`

最小字段约定：

- `tempC`: 单个代表性温度（支持摄氏度或毫摄氏度）
- `label`: 传感器名字，例如 `CPU Package`
- `updatedAt`: 宿主机采样时间（建议 ISO 时间）
- `summary` / `detail`: 可选，自定义摘要
- `probes`: 可选，多探针数组

示例文件见：

- `tools/openclaw-local-health/host-thermal-bridge.example.json`

Windows 宿主机可直接使用的采集脚本：

- `tools/openclaw-local-health/host-thermal-bridge-windows.ps1`
- `tools/openclaw-local-health/install-host-thermal-bridge-task-windows.ps1`
- `tools/openclaw-local-health/install-host-thermal-bridge-task-windows.cmd`

推荐做法：

- 在 Windows 宿主机上把输出目录放进一个 VMware 共享文件夹
- 推荐共享名：`OpenClawBridge`
- 这样 Linux 客体通常可直接从 `/mnt/hgfs/OpenClawBridge/host-thermal-bridge.json` 自动读到

Windows 宿主机最短落地步骤：

1. 在 Windows 宿主机的 workspace 里运行：
   - `tools\openclaw-local-health\install-host-thermal-bridge-task-windows.cmd`
2. 确认输出目录里已经持续生成：
   - `%USERPROFILE%\Documents\OpenClawBridge\host-thermal-bridge.json`
3. 在 VMware 里把该目录作为共享文件夹挂给 Linux 客体：
   - 共享名建议：`OpenClawBridge`
4. 在 Linux 客体确认：
   - `/mnt/hgfs/OpenClawBridge/host-thermal-bridge.json`

若当前客体里：

- `vmware-hgfsclient` 输出为空
- 或 `vmhgfs-fuse .host:/ <mountpoint>` 返回 `Error -107 cannot open connection!`

通常说明：**宿主机还没有真正启用/提供共享文件夹**，而不是 Linux 客体缺少 VMware 工具。

当前接入规则：

- 若桥接文件存在，则**优先使用宿主机桥接温度**
- 若桥接文件不存在，才退回当前机器自身可读传感器
- 若两边都不可读，则显示 `温度不可读`
- 若桥接文件约 **10 分钟**未更新，则提示“桥接可能过期”
- 若桥接文件约 **20 分钟**未更新，则不再把它当作实时温度，改为提示“宿主机温度桥接过期”

## systemd 接入（公司 Linux）

把模板复制到用户态 systemd 目录后启用：

```bash
mkdir -p ~/.config/systemd/user
cp tools/openclaw-local-health/openclaw-local-health-watch.service ~/.config/systemd/user/
cp tools/openclaw-local-health/openclaw-local-health-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-local-health-watch.timer
```

建议在 service 里保留：

```ini
SuccessExitStatus=1 2
```

这样 systemd 会把“诊断结果为告警/严重异常”视为**一次成功完成的诊断**，而不是把 service 本身误标成执行失败。

当前默认频率：

- 开机后约 2 分钟首次运行
- 之后约每 5 分钟运行一次

当前 service 模板默认会带上：

```ini
ExecStart=/usr/bin/python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-local-health-diagnose.py --notify-on-change --notify-frontstage --print-human
```

含义是：除了继续保留桌面通知能力，它也会在本地健康从 `ok -> warn/critical` 或 `warn/critical -> ok` 这些变化时，经由 frontstage broker 把一句摘要回到当前 dashboard 前台。

## 未来预留：本地 fallback 模型接口

当前**不实现自动切换**，但已经预留了接口位：诊断输出 JSON 里会带一个 `fallback` 字段，后续可在这里挂接本地备用小模型的接管信息。

未来建议形态：

- 当主线 provider 路由全部失败、但本机仍正常时
- 健康层只负责判断“是否满足切换条件”
- 真正的切换执行交给单独的小脚本 / 本地服务
- 例如未来可挂：
  - `backend`: `ollama` / `llama.cpp` / `vllm-local`
  - `endpoint`: `http://127.0.0.1:11434`
  - `command`: 某个本地接管脚本

当前不自动启用的原因：

- 还没有用户确认的本地备用模型
- 还没有确定切换后的对话路由策略
- 还没有定义“什么时候自动切、什么时候只提示不切”的策略

## 边界

- 该层不依赖 AI 回复，但仍依赖操作系统、用户态 systemd、网络栈、以及本机 Python / OpenClaw CLI。
- 当前默认频率已故意保持保守（5 分钟一次），优先降低长期资源占用与无意义探测噪音。
- 如果整机断网、系统挂死、前端完全断开或更底层组件也一起失效，它不能保证一定把原因送达用户。
- 它当前**只负责三类监听**：本地网络、Gateway 可达性、主线 provider 路由可达性。
- 它当前的前台回报也只覆盖**辅助健康摘要**，不接管正常主回复。
- **它不负责页面主会话消息超时监听**；主会话里“这条消息为什么还没回”的体感问题，继续由监工分身 `main-supervisor-lite` 负责。
- 它的价值是：**只要本机还剩一口气，就尽量把故障原因分类并留下本地证据。**
