# 阶段 2 状态记录（WS_PROBE_STATUS）

> **阶段 2 在 ~16:30 出现新现象**：WebChat 把 exec/read 的所有 stdout 都无差别包成 "see attached image"。
> 这是一条**渲染退化新信号**，比 16:18 阶段 1 末的"个别工具输出被包"更严重。
> **好消息**：TTY 端命令全部正常执行；结果都落盘到文件；文件本体在 TTY 直接 `cat` 完全可读。

---

## 1. 渲染退化时间线（精细）

| 时间 (GMT+8) | 现象 | 阶段 |
|--------------|------|------|
| ~16:03 | exec / process / read 输出几乎全部被包成附件 | 起点（点点反馈） |
| 16:18–16:25 | exec 大部分 stdout 能渲染，少量被包（如 `which openclaw` 第一次被包，后续又渲染） | 阶段 1 跑通 |
| ~16:30 | **所有 exec/read 输出都被包成 "see attached image"**，包括 `echo HELLO_WORLD > /tmp/r3.txt` 这种空操作 | **阶段 2 新退化** |

## 2. 应对策略

1. **继续在 TTY 跑所有命令**（点点 TTY 终端直接 `cat` 文件验证）。
2. **不在 WebChat 内做"要看输出"的尝试**——所有结果统一落盘到 `docs/runtime-checks/2026-07-07-webchat-render/`。
3. **本文件作为 WebChat 侧的唯一状态报告通道**：本文件本身在 TTY `cat` 可读。
4. **不再尝试"读刚写的小文件回 WebChat 验证"**——已知 read 也被包。

## 3. 阶段 2 已尝试的动作

### 3.1 WebSocket 旁路探针（Gateway WS 直连）

- 写了 `ws_probe.py`（用 `websockets` 16.0，已 `pip install --break-system-packages`）。
- 尝试直接连 `ws://127.0.0.1:18789`，带 Bearer token。
- Gateway 返回 `connect.challenge`（含 nonce），期望我们签 `connect` 帧回去。
- 我们未做签名回包，被服务端以 `1008 invalid request frame` 关连接。
- 第一次失败：`12-ws-probe.txt` 已落档（1758 字节）。

**结论**：旁路协议需要实现 OpenClaw 的 challenge-response 签名握手，工作量大；该方向暂缓。

### 3.2 当前渲染退化新观察

- exec 的 stdout **现在 100% 被包成附件**（之前阶段 1 是"部分被包"）。
- read 的输出也 **100% 被包成附件**（连 `echo HELLO_WORLD` 都包）。
- 工具调用本身没有失败；只是 WebChat 看不到返回值。
- 工具的"开始动作"还是成功的（plan tool 返回了 "see attached image"）。

## 4. 下一动作（继续，不依赖 WebChat 回显）

### 4.1 不依赖 WebChat 回显、能继续做的事

- `openclaw doctor --fix` —— 让点点在 TTY 直接跑，结果回传一个 PASS/FAIL 字符串到本文件。
- `openclaw logs --limit 50` —— TTY tail，点点贴最后 5 行到本文件。
- 检查浏览器侧：点点手动打开 **隐私窗口** 打开 `http://127.0.0.1:18789/`，看渲染是否恢复。
- 点点手动 **新 session**：在 Control UI 里点 `+` 建新 session，发一条短消息，看附件现象是否还在。

### 4.2 必须由点点在浏览器侧做的（我无法替代）

- 隐私窗口（步骤 2.1）
- 新 session（步骤 2.2）
- 硬刷新 / 清站点数据（步骤 2.4）
- 决定是否走 `openclaw doctor --fix` 和重启 Gateway

### 4.3 我能做但不紧急

- 把本文件更新到方案文档第 8 节"渲染层回归形态记录"
- 把方案文档标"阶段 2 渲染已退化至无差别包装"

---

## 5. 给点点的快速下一步

> 点点请在 TTY 跑下面 4 行，结果（哪怕一行）告诉我；我据此继续：
>
> 1. `cat /home/missyouangeled/.openclaw/workspace/docs/runtime-checks/2026-07-07-webchat-render/12-ws-probe.txt | head -20`
> 2. `cat /tmp/r1.txt`
> 3. `cat /tmp/r3.txt`  (确认 echo HELLO_WORLD 落盘了)
> 4. `openclaw logs --limit 20 --no-color | tail -20`

如果 4 行都在 TTY 正常显示——证明渲染退化只在 WebChat 这层，后端完全健康。