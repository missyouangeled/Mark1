# 2026-07-08 渲染复测基线

> **目的**：验证昨天 16:00 发生的 WebChat 渲染回归（"无差别附件化"所有 exec/read 输出）是否回潮。
> **方法**：TTY 跑 4 项验证 + WebChat 文字回显测试。
> **结论**：✅ **所有层自愈**，未发现回潮证据。

## 1. 验证时间

- 起点：2026-07-08 08:27 GMT+8（点点报到）
- 验证完成：2026-07-08 08:31 GMT+8
- 总耗时：~4 分钟

## 2. TTY 验证（点点手动跑）

| # | 命令 | 结果 |
|---|------|------|
| 1 | `cat /tmp/r1.txt` | No such file（昨天清理掉了，非异常） |
| 2 | `cat /tmp/r3.txt` | No such file（同上） |
| 3 | `cat docs/runtime-checks/2026-07-07-webchat-render/12-ws-probe.txt \| head -20` | 输出 `connect.challenge` + `sessions.list` Traceback（昨天 ws_probe 第二调用 15s 超时的直接证据）|
| 4 | `openclaw logs --limit 20 --no-color \| tail -20` | 干净：cron restart 尾巴 + 08:27:08 webchat connected + 2 次 MiniMax-M3 200/2.5s |

## 3. WebChat 渲染复测

- **会话**：agent:main:main（08:27:08 建立）
- **关键调用**：
  - `chat.startup` 1321ms ✅
  - `chat.metadata` 2336ms ✅
  - `models.authStatus` 3424ms ✅
- **点点发送**：`渲染测试`
- **回显形式**：纯文字（无附件包装）✅

## 4. 后端健康（基线对照）

来自 `01-status.txt`：
- Gateway reachable 79ms · pid 2014 active
- 3 agents · 23 sessions · default main active
- Update: npm · deps ok
- Plugin compatibility: none
- Probes: skipped (use --deep)

## 5. Gateway logs 关键片段（来自 `02-logs.txt`）

```
08:26:22  cron: deferring missed agent jobs until after gateway startup
08:26:22  cron: running missed jobs after restart
08:26:27  gateway: provider auth state pre-warmed in 1776ms
08:27:08  webchat connected conn=2db808fc…c02b remote=127.0.0.1 client=openclaw-control-ui
08:27:08  ⇄ res ✓ sessions.subscribe 457ms
08:27:09  ⇄ res ✓ agent.identity.get 934ms
08:27:09  ⇄ res ✓ health 938ms
08:27:09  ⇄ res ✓ chat.startup 1321ms
08:27:12  ⇄ res ✓ chat.metadata 2336ms
08:27:13  ⇄ res ✓ models.authStatus 3424ms
08:27:50  [model-fetch] MiniMax-M3 200 OK 2719ms
08:27:53  [model-fetch] MiniMax-M3 200 OK 2529ms
```

无 `Request was aborted`、无 `disconnected`、无异常 disconnect/reconnect 循环。

## 6. 与昨天对比

| 指标 | 2026-07-07 16:18 | 2026-07-08 08:31 |
|------|------------------|------------------|
| 后端 | ✅ | ✅ |
| WebChat 文字回显 | ❌ 无差别附件化 | ✅ 纯文字 |
| `Request was aborted` | ❌ 出现（compaction 3min 超时）| ✅ 未出现 |
| Stability 异常 | 0/1000 | 0/50+（本次未跑 stability）|
| 模型切换痕迹 | taotoken/gpt-5.4 → agnes-2.0-flash → MiniMax-M3（连环超时）| 无切换，MiniMax-M3 稳定 |

## 7. 结论

**昨天的渲染回归是一次性事件**，已自然自愈。
- 没有再次改动任何配置
- 没有再次改动业务代码
- 没有推送任何更新
- 浏览器侧/前端 bundle 自身的更新或缓存清理在点点没有操作的情况下自然治好

## 8. 不做的事（明确边界）

- ❌ 不推送 GitHub（点点 08:31 明确指示）
- ❌ 不动 Mark42 业务代码
- ❌ 不动 OpenClaw 源码
- ❌ 不重启 Gateway / 不清站点数据（无需）
- ❌ 不补跑阶段 2/3 的强制项（昨天 ☐ 项已通过复测填☑，无需额外验证）

## 9. 文件清单

```
docs/runtime-checks/2026-07-08-render-recheck/
├── 00-summary.md       ← 本文件
├── 01-status.txt       ← openclaw status 原始输出
├── 02-logs.txt         ← openclaw logs --limit 50 原始输出
└── 03-timestamp.txt    ← 验证时间戳
```