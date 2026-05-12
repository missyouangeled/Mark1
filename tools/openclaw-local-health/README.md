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

## 手工运行

```bash
python3 scripts/openclaw-local-health-diagnose.py --print-human
python3 scripts/openclaw-local-health-diagnose.py --print-json
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

## systemd 接入（公司 Linux）

把模板复制到用户态 systemd 目录后启用：

```bash
mkdir -p ~/.config/systemd/user
cp tools/openclaw-local-health/openclaw-local-health-watch.service ~/.config/systemd/user/
cp tools/openclaw-local-health/openclaw-local-health-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-local-health-watch.timer
```

当前默认频率：

- 开机后约 2 分钟首次运行
- 之后约每 5 分钟运行一次

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
- **它不负责页面主会话消息超时监听**；主会话里“这条消息为什么还没回”的体感问题，继续由监工分身 `main-supervisor-lite` 负责。
- 它的价值是：**只要本机还剩一口气，就尽量把故障原因分类并留下本地证据。**
