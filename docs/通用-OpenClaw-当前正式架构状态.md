# OpenClaw 当前正式架构状态

- 适用机器：通用
- 系统 / OS：通用（具体机器差异见 `HOST_CONTEXT.md` 与机器专用维护说明）
- 文档类型：当前正式架构的权威状态源
- 最后更新：2026-06-01

## 用途

这份文件回答一个问题：**现在到底哪些组件属于正式架构、哪些只是历史回退、哪些是可选支路？**

以后更新以下入口时，优先对齐本文件：

- `scripts/openclaw-patch-repair.py`
- `scripts/openclaw-post-upgrade-self-check.py`
- `scripts/verify-today-patches.py`
- `scripts/openclaw-system-summary.py`
- `docs/通用-OpenClaw-总控面板.md`
- `docs/通用-OpenClaw-补丁注册表.md`
- `docs/通用-OpenClaw-补丁重建清单.md`

## 正式运行组件

### 1. OpenClaw Gateway 主体

| 项 | 当前状态 | 说明 | 最小验收 |
|---|---|---|---|
| Gateway | 必需 | 主聊天 / API / Control UI 主体 | `openclaw status` |
| Control UI 品牌补丁 | 必需补丁 | 启动前自动重打 | `python3 scripts/apply-openclaw-control-ui-branding.py` |
| Control UI 运行信号补丁 | 必需补丁 | 显示进行中状态 | 同上 |
| 当前会话模型选择器补丁 | 必需补丁 | 模型下拉应应用到当前会话 | `python3 scripts/apply-openclaw-session-model-selector-fix.py` |

### 2. 前台辅助数据层

| 项 | 当前状态 | 说明 | 最小验收 |
|---|---|---|---|
| frontstage broker | 正式数据中心 | 收口 supervisor / health / tasks / recovery 事件 | `python3 scripts/openclaw-frontstage-broker.py rebuild-views --print-json` |
| infos-handle sidecar | 正式服务 | HTTP/SSE 查询 broker 视图 | `curl -fsS http://127.0.0.1:18790/healthz` |
| unified proxy | 正式服务 | `:18788` 统一代理 sidecar + gateway | `curl -fsS http://127.0.0.1:18788/healthz` |

### 3. Watcher v2 正式定时器

当前正式 timer 数量应为 **5 个**：

| timer | 角色 | 当前语义 |
|---|---|---|
| `openclaw-frontstage-guardian.timer` | 前台保护器 | 合并 frontstage-recovery + responsiveness 子检查 |
| `openclaw-health-collector.timer` | 健康采集器 | 合并 supervisor / local-health / broker dirty flag 重建 |
| `openclaw-task-scheduler.timer` | 任务调度器 | 任务状态扫描、监工开关、僵尸/静默任务处理 |
| `openclaw-lifecycle-maintainer.timer` | 生命周期维护器 | daily transcript 聚合、flush 同步、daily 骨架、临时文件与语音清理 |
| `openclaw-resume-watch.timer` | 休眠恢复 | Linux 唤醒后检测 / 恢复 gateway |

最小验收：

```bash
systemctl --user list-timers 'openclaw-*' --no-pager
python3 scripts/verify-today-patches.py --print
```

## 历史回退 / 不应自动复活的组件

以下组件可以保留模板或脚本作为历史回退，但**不应由修复器默认恢复为独立 timer**：

| 历史组件 | 当前状态 | 说明 |
|---|---|---|
| `openclaw-supervisor-watch.timer` | retired timer | 监工状态由 `health-collector` 子检查承载 |
| `openclaw-local-health-watch.timer` | retired timer | local-health 由 `health-collector` 周期调用 |
| `openclaw-frontstage-recovery-watch.timer` | retired timer | recovery 子逻辑由 `frontstage-guardian` 调用 |
| `openclaw-responsiveness-watch.timer` | retired timer | responsiveness 子逻辑由 `frontstage-guardian` 调用 |
| `daily-transcript-aggregator.timer` | retired timer | 转录聚合由 `lifecycle-maintainer` 承载 |
| `openclaw-frontstage-broker-rebuild.timer` | disabled fallback | 当前资源有限，默认保持 disabled；broker 由 dirty flag 事件驱动重建 |

## 可选 / 手动组件

| 组件 | 默认状态 | 说明 |
|---|---|---|
| `openclaw-nvidia-audio-bridge.service` | 可 disabled | NVIDIA 音频桥是辅助/实验语音支路，禁用不算主体错误；只有用户明确要求恢复语音桥时再启用 |

## 当前安全基线

个人本机 Control UI 使用场景下，当前期望：

- `openclaw security audit`：`0 critical / 0 warn`
- `tools.elevated.allowFrom.webchat` 不应包含 `"*"`
- `gateway.controlUi.allowInsecureAuth` 应为 `false`
- `gateway.trustedProxies` 至少包含 `127.0.0.1` / `::1`

本机实际配置期望见：`docs/公司-Linux-OpenClaw-本机配置期望.md`。

## 应急入口

| 入口 | 用途 | 命令 |
|---|---|---|
| Control UI 黑屏应急修复器 | 页面黑屏 / 打不开时逐层诊断和低风险修复 | `python3 scripts/openclaw-control-ui-emergency.py --check --print-human` |

## 当前总体验收入口

优先使用：

```bash
python3 scripts/openclaw-system-summary.py --print-human
python3 scripts/verify-today-patches.py --print
openclaw security audit
openclaw tasks audit
```

若这些入口与本文件描述冲突，优先按本文件修正入口逻辑，再运行验证。
