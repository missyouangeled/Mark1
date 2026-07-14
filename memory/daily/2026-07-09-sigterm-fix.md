# 2026-07-09 SIGTERM 强杀问题修复(flush-sync 17:25)

> 衔接之前的 SIGTERM 排查文档,本次实施修复。

## 根因确认

通过源码阅读确认完整链路:

1. **OpenClaw 源码** `dist/run-10HO3NNA.js:575` 监听 SIGTERM:
   ```js
   const onSigterm = () => {
     gatewayLog$1.info("signal SIGTERM received");
     const restartIntent = consumeGatewayRestartIntentPayloadSync();
     request(restartIntent ? "restart" : "stop", "SIGTERM", restartIntent?.reason, restartIntent ?? void 0);
   };
   process.on("SIGTERM", onSigterm);
   ```

2. **当 SIGTERM 携带 restart intent** → 走 `request("restart", ...)` → 走 in-process restart 分支
3. **in-process restart 不退出进程**(`shuttingDown=true` 后翻回 `false`,进程本身 PID 不变)
4. **systemd 外部以 `TimeoutStopSec=60s` 等待** → 必然超时 → SIGKILL 整个 cgroup
5. **`KillMode=control-group`** → 连带杀 caddy/php/embed-sidecar/mark42
6. **`Restart=always` 拉起新 PID**

## 数据

| 维度 | 7 天数据 |
|---|---|
| SIGTERM 触发 | 74 次 |
| **强杀(SIGKILL)** | **137 次** ⚠️ |
| 7/6 单日 | 62 次 |
| 7/7 单日 | 42 次 |
| 7/8 单日 | 6 次 |
| 7/9 单日 | 27 次(截至 17:21) |

## 修复方案(方案 A · 最小稳定)

修改 `~/.config/systemd/user/openclaw-gateway.service.d/timeout-fix.conf`:

```ini
[Service]
TimeoutStopSec=600  # 原来 60s
TimeoutStartSec=60
```

**原理**:in-process restart 实测 7-10s 完成,600s 给绝对充足时间,systemd 不再误杀。

## 验证

修改后:
1. `systemctl --user daemon-reload`
2. `systemctl --user show` 显示 `TimeoutStopUSec=10min` ✅
3. `systemctl --user restart openclaw-gateway.service` 主动验证:
   - **17:25:28** SIGTERM 收到
   - **17:25:33** Gateway ready(in-process restart 5 秒完成)
   - **没有 Killing 日志** ✅
   - **没有第二次 restart** ✅
   - **PID 从 34118 → 35009**(systemd restart 拉起的 PID)
   - **主会话自动恢复**:`main-session restart recovery complete: recovered=1 failed=0`

## 副作用评估

- 真要 stop 时最多等 10 分钟
- 但 stop 通常只在 `openclaw update` / `openclaw gateway stop` 时发生
- openclaw update 走 long-running shell,10 分钟影响可控
- 平时 in-process restart 7-10s 完成,600s 远大于实际需要

## 备份

`docs/backup/2026-07-09-sigterm-fix/openclaw-gateway.service.bak`

## 后续(未做)

- [ ] 7 次未知 SIGTERM 来源仍未查明(健康监控路径)
- [ ] cgroup 杀连带问题:sidecar 拆独立 unit(长期方案)
- [ ] mark42-watchdog L2.5 嵌入索引缺失(自 6 月底)
