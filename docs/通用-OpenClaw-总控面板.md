# OpenClaw 总控面板 — 全补丁/修复/自定义统一管理

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：总控（单文件索引所有补丁/修复/Skill/自定义）
- 最后更新：2026-05-29 14:08 CST

## 用途

打开这个文件，就知道：

> 现在有多少补丁、多少修复、多少自定义？哪个归哪个管？出问题先看哪？

它是**总目录**，不是正文。每个条目都指向对应的注册表/备忘录/脚本位置。

---

## 一、全量清单（总 32 项：22 正式补丁 + 3 非正式修复 + 4 维护备忘 + 3 待处理）

### 🏗️ 基础设施（infrastructure）

| ID | 类型 | 名称 | 一句话 | 位置 |
|----|------|------|--------|------|
| P01 | `patch` | Control UI 品牌补丁 | 所有 Control UI 页面的 "OpenClaw" → "贾维斯" 品牌替换 | [注册表](#patch-ctrlui-branding) |
| P02 | `patch` | Control UI "进行中" 信号 | loading/sending/stream/canAbort/queue/有活跃run → 显示"进行中" | [注册表](#patch-ctrlui-running-signal) |
| P03 | `patch` | frontstage broker | 监工/健康/任务/恢复 四类辅助消息 → broker 数据中心 → Control UI 前台 | [注册表](#patch-frontstage-broker) |
| P04 | `patch` | infos-handle sidecar | broker 数据提供最小 HTTP/SSE API，供 Control UI 直连 | [注册表](#patch-infos-handle-sidecar) |
| P05 | `patch` | infos-handle unified proxy | Caddy 反代：18788 端口 → sidecar(18790) + Gateway(18789) | [注册表](#patch-infos-handle-unified-proxy) |

### ⏱️ Watcher / 自动监控系统

| ID | 类型 | 名称 | 一句话 | 位置 |
|----|------|------|--------|------|
| P06 | `patch` | supervisor 服务状态 | 监工可开关（auto/force_on/force_off）+ 自动回报 | [注册表](#patch-supervisor-service-state) |
| P07 | `patch` | supervisor 自动通知 | 监工状态变化（stalled/failed/done）→ 自动通知前台 | [注册表](#patch-supervisor-auto-notify) |
| P08 | `patch` | local-health 诊断层 | 不依赖 AI 回复，对 gateway/外联/provider 做周期探测 | [注册表](#patch-local-health-diagnostic-layer) |
| P09 | `patch` | local-health 前台回报 | 健康状态变化（warn/critical/recovered）→ 前台通知 | [注册表](#patch-local-health-frontstage) |
| P10 | `patch` | responsiveness watchdog | 主会话超时 → 自动注入提醒（30s/60s） | [注册表](#patch-responsiveness-watchdog) |
| P11 | `patch` | daily-transcript 聚合 | 每日转录跨模型自动聚合 | [注册表](#patch-daily-transcript-aggregator) |
| P12 | `patch` | **Watcher v2 整合** 🔄 | 7→5 timer；broker 事件驱动（dirty flag）；监工内迁到 health-collector；guardian 紧急通道；ChatTTS 清理 + flush 同步并入 lifecycle-maintainer | [注册表](#patch-watcher-v2) |

### ⚡ 性能优化

| ID | 类型 | 名称 | 一句话 | 位置 |
|----|------|------|--------|------|
| P13 | `patch` | 搜索短路 | memory_search 先本地 grep（0.1s），置信度≥0.7 跳过云端 API | [注册表](#patch-search-shortcircuit) |
| P14 | `patch` | task-scheduler 闲时跳过 | 无活跃任务时 0.1s SQLite 快速预检，跳过全量扫描 | [注册表](#patch-task-scheduler-idle) |
| P15 | `patch` | TTL 查询缓存 | 重复查询 60s 缓存命中，零开销 | [注册表](#patch-ttl-cache) — 注：当前未独立注册，与 P13 合并 |
| P16 | `patch` | 耗时基线监控 | 每个子检查记录耗时，超基线标 degraded | [注册表](#patch-latency-baseline) |

### 🔧 平台/机器专用修复

| ID | 类型 | 名称 | 一句话 | 位置 |
|----|------|------|--------|------|
| P17 | `patch` | Linux resume 恢复 | 机器休眠唤醒后自动检测 gateway → 重启 | [注册表](#patch-linux-resume-recovery) |
| P18 | `patch` | 掌机 battery 策略 | 禁止 Windows 电池模式自动停 gateway | [注册表](#patch-windows-gateway-battery-policy) |
| P19 | `patch` | NVIDIA 音频 gateway bridge | 公司 Linux 的 NVIDIA 音频到 gateway 桥接 | [注册表](#patch-nvidia-audio-gateway-bridge) |

### 🛡️ 升级保护

| ID | 类型 | 名称 | 一句话 | 位置 |
|----|------|------|--------|------|
| P20 | `patch` | 升级后自检 | 版本变化时自动跑自检；升级记录回溯历史教训 | [注册表](#patch-post-upgrade-self-check) |
| P21 | `patch` | 语言锁定 | 所有模型强制中文输出 | [注册表](#patch-language-lock) |

### 📝 非正式修复（MEMO）

| ID | 类型 | 名称 | 一句话 | 位置 |
|----|------|------|--------|------|
| M01 | `memo` | 掌机微信 Content-Length 兼容 | fetch failed → invalid content-length 兼容修复 | [备忘录](#掌机微信-content-length) |
| M02 | `memo` | 掌机微信通道手工补配 | 扫码成功但通道没拉起的手工配置补齐 | [备忘录](#掌机微信通道手工补配) |
| M03 | `memo` | watcher systemd PATH 修复 | ~/.npm-global/bin 加入 watcher service 的环境 PATH | [备忘录](#watcher-systemd-path) |

### 📋 维护备忘（不涉及代码修改）

| ID | 类型 | 名称 | 一句话 | 位置 |
|----|------|------|--------|------|
| N01 | `note` | 掌机 watchdog 保持卸载 | 不自动重装兜底，优先追根因 | [备忘录](#掌机-watchdog-卸载) |
| N02 | `note` | 硬件审查前置规则 | 问"能不能用" → 自动审查 CPU/GPU/RAM/磁盘/依赖 | [备忘录](#硬件审查规则) |
| N03 | `note` | GPT-5.5 已可用 | 可用但未切为默认模型 | [备忘录](#gpt55-可用) |
| N04 | `note` | thinkingDefault + reasoning 双关 | OpenClaw 层 + 模型层双重关 thinking | [备忘录](#thinking-双重修复) |

### 🎯 自定义 Skill

| ID | 类型 | 名称 | 位置 |
|----|------|------|------|
| S01 | `skill` | chattts-stable | `~/.openclaw/workspace/skills/chattts-stable/` |
| S02 | `skill` | noizai-tts | `~/.openclaw/workspace/skills/noizai-tts/` |
| S03 | `skill` | warm-companion-zh | `~/.openclaw/workspace/skills/warm-companion-zh/` |
| S04 | `skill` | ex-qianqian | `~/.openclaw/workspace/skills/ex-qianqian/` |
| S05 | `skill` | humanizer-zh | `~/.openclaw/workspace/skills/humanizer-zh/` |
| S06 | `skill` | characteristic-voice | `~/.openclaw/workspace/skills/characteristic-voice/` |
| S07 | `skill` | douyin | `~/.agents/skills/douyin/` |
| S08 | `skill` | multi-search-engine | `~/.agents/skills/multi-search-engine/` |

> 以上 8 个 Skill 有自定义内容。其余 Skill 为默认安装，列于 `SKILL_CATALOG.md`。

### 🧹 待处理（清理/整合）

| ID | 类型 | 名称 | 说明 |
|----|------|------|------|
| C01 | `cleanup` | 淘汰旧 watcher 脚本 | `openclaw-responsiveness-watch.py` / `openclaw-frontstage-recovery-watch.py` / `openclaw-stuck-session-detector.py` — 已被 watcher v2 取代，systemd 不再引用，可归档 |
| C02 | `cleanup` | ChatTTS 烟雾测试脚本 | `chattts_seeta_smoke*.py` × 17 个测试脚本，可归档到 `tmp/` |
| C03 | `todo` | boot-health-check 晋升 | `openclaw-boot-health-check.py` 已稳定运行多日，可升级为正式补丁 PATCH-BOOT-HEALTH-CHECK |

---

## 二、依赖关系图

```
                    ┌─────────────────────────────────────┐
                    │         OpenClaw Gateway             │
                    │         (18789)                      │
                    └────┬───────┬───────┬────────────────┘
                         │       │       │
              ┌──────────┘       │       └──────────┐
              ▼                  ▼                   ▼
     ┌──────────────┐  ┌──────────────┐   ┌──────────────┐
     │ P01 Branding │  │ P02 进行中   │   │ P21 语言锁定 │
     │ P20 升级自检 │  │   信号       │   │              │
     └──────────────┘  └──────────────┘   └──────────────┘
              │                  │
              ▼                  ▼
     ┌────────────────────────────────────────────┐
     │              P03 broker 数据中心             │
     │   ← P06/P07 监工  ← P08/P09 健康           │
     │   ← P10 响应性    ← P12 watcher-v2 整合    │
     │   ← P16 耗时基线                           │
     └──────┬─────────────────────────────────────┘
            │
    ┌───────┼──────────┐
    ▼       ▼           ▼
┌──────┐ ┌──────────┐ ┌──────────────┐
│ P04  │ │ P05      │ │ P11 转录聚合 │
│sidecar│ │unified   │ │ P13 搜索短路 │
│:18790│ │proxy:88  │ │ P14 闲时跳过 │
└──────┘ └──────────┘ │ P15 TTL缓存  │
                      └──────────────┘

系统级（独立于以上链路）:
  P17 resume-recovery → Linux 唤醒后自愈
  P18 battery-policy  → 掌机不因电池停 gateway
  P19 nvidia-audio    → 音频桥接（公司 Linux 专用）
```

**关键依赖链**：P03(broker) ← P04(sidecar) ← P05(proxy) ← Control UI 前台

---

## 三、升级后恢复优先级（从高到低）

### 🔴 第一优先（前端不可用则啥都看不到）

1. **P01 + P02**：Control UI 品牌 + 进行中信号
   ```bash
   python3 scripts/apply-openclaw-control-ui-branding.py
   ```

### 🟠 第二优先（前台辅助消息中断）

2. **P03**：broker 数据中心
   ```bash
   python3 scripts/apply-openclaw-frontstage-broker-data.py --apply-control-ui-branding --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock
   ```
3. **P04 + P05**：sidecar + unified proxy
   ```bash
   python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar --require-control-ui-infos-handle-sidecar
   python3 scripts/apply-openclaw-infos-handle-gateway-proxy.py --install-user-systemd --enable --restart --verify --print-json
   ```

### 🟡 第三优先（自动监控恢复）

4. **P12**：watcher v2 整合（5 timer）
   ```bash
   systemctl --user restart openclaw-health-collector.timer
   systemctl --user restart openclaw-task-scheduler.timer
   systemctl --user restart openclaw-frontstage-guardian.timer
   systemctl --user restart openclaw-lifecycle-maintainer.timer
   # resume-watch 第五个
   ```

### 🟢 第四优先（性能优化 + 机器专用 + Skill）

5. **P13-P15**：搜索短路 + 闲时跳过 + TTL 缓存（无需单独恢复，脚本在 workspace 即生效）
6. **P17-P19**：机器专用补丁（按当前机器判断是否需要）

---

## 四、自愈策略（自动 vs 手动）

| 策略 | 范围 | 说明 |
|------|------|------|
| 🤖 **自动** | P01-P02 品牌补丁 | gateway 启动前 ExecStartPre 自动重打 |
| 🤖 **自动** | P20 升级自检 | BOOT.md → 版本变化时自动跑 self-check |
| 🤖 **自动** | P12 watcher timer | systemd timer 开机自启 |
| 🤖 **自动** | P17 resume 恢复 | timer 检测唤醒后自动重启 gateway |
| 🔄 **半自动** | P03-P05 broker/sidecar/proxy | timer 周期重建，但升级后需手工 apply 一次 |
| 🔄 **半自动** | P13 搜索短路 | 脚本在 workspace，但依赖 AGENTS.md 规则引导 agent |
| ✋ **手动** | M01-M03 非正式修复 | 只在特定场景触发，不自动 |
| ✋ **手动** | S01-S08 自定义 Skill | Skill 文件在 workspace，不需要恢复 |

---

## 五、文档入口 map

```
想看某个补丁的完整信息（目标/实现/验收/落点）
  → docs/通用-OpenClaw-补丁注册表.md  （按 ID 查找）

想知道升级后先修什么、怎么逐项恢复
  → docs/通用-OpenClaw-补丁重建清单.md

想快速确认升级后还能不能用（30 秒自检）
  → docs/通用-OpenClaw-升级后自检清单.md

想一条命令验证今天全部改动
  → python3 scripts/verify-today-patches.py --print

想查某一笔临时修复/手工改动的背景
  → docs/通用-OpenClaw-非正式修改备忘录.md

想回顾历次升级的经验教训
  → docs/通用-OpenClaw-升级记录.md

想知道最近改了什么
  → docs/通用-OpenClaw-补丁变更流水.md

想找全貌
  → 就是这个文件：docs/通用-OpenClaw-总控面板.md
```

---

## 六、一键验证入口

```bash
# 全量验证（覆盖所有可自动检测的补丁）
python3 scripts/verify-today-patches.py --print

# 升级后完整自检
python3 scripts/openclaw-post-upgrade-self-check.py --print-human

# 只检查 watcher timer 健康
python3 scripts/openclaw-health-collector.py --print-human
python3 scripts/openclaw-task-scheduler.py --dry-run --print-human
```

---

## 七、维护纪律

1. 新补丁 → 必须同时更新：注册表 + 重建清单 + 必要时更新自检清单 + 本总控面板
2. 补丁被废弃 → 标记状态，不移除条目（保留历史可查）
3. 非正式修改 → 先进备忘录；稳定后再升正式补丁
4. 本文件每次补丁变更后同步更新「全量清单」的计数和分类

---

_本文件是活的。每次加补丁、改架构、做修复，同步更新这里。_
