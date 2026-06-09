# HANDOFF.md — 跨模型/跨会话接力地图

> 最后更新: 2026-06-09 18:10 CST
> 当前会话: 贾维斯主会话 (deepseek-company/deepseek-v4-pro)
> 状态: 多项任务进行中，明天继续

## 🟢 已完成项（本轮）

### 1. timer/service 深度审查 + 修复
- **误解澄清**：oneshot 服务的 "inactive dead" 是正常行为（跑完即退出），不是挂了
- **真问题修复 4 项**：
  - 新 `session-size-watcher.timer` 从 disabled → enabled（OnBootSec=3min, 每2min）
  - 旧 `session-watcher.timer` 已 disable + stop（避免空触）
  - `frontstage-guardian.timer` 降频: 20s → 60s（省 ~25% 单核 CPU）
  - `resume-watch.timer` 降频: 1min → 5min（过度检查）
- 所有 timer 已验证 active

### 2. CPU 过载处理方案建设
- 文档: `docs/通用-CPU负载过高临时处理方案.md`（Stop→Shrink→Single）
- 脚本: `scripts/openclaw-cpu-emergency.py` (--diagnose/--repair/--light-clean)
- 三层索引穿透: BOOT_INDEX/RULES_INDEX/WORKSPACE_INDEX

### 3. Unity 路径过长风险分析
- 文档: `docs/通用-Unity资产路径过长风险分析与应对方案.md`
- 实测最长路径 215 字符，Windows 临界

### 4. UFM plan/apply 烟测通过
- Wall 130文件 plan → 5变更 0冲突

## 🟡 进行中（CPU 过载自动响应）

任务：检测到 CPU critical → 自动跑 `cpu-emergency --light-clean`

已分析清楚：
- `health-collector.py` 每 5 轮调 `local-health-diagnose --notify-frontstage`
- `local-health` JSON 输出包含 `severity` / `resource.loadRatio` / `resource.load1`
- `LOAD_CRITICAL_RATIO = 1.8` (load1 > 1.8×核心数 = critical)
- 当前缺：health-collector 拿到 full check 的 local-health 结果后 → 判断 loadRatio > 1.8 → 自动 subprocess.run cpu-emergency --light-clean

**下一步**：在 `health-collector.py` 的 `do_full` 分支里，local-health 调用后解析其 JSON 输出（已有 --print-json 但 health-collector 传了 --print-human），改为传 --print-json，读 loadRatio > 1.8 则触发自动清理，append_log 记录。

## 📋 待做

### 3. 废弃/冗余清理
- 扫描点：
  - `chattts_seeta_smoke` 1-16 实验脚本（16个）
  - `military-rename-v1.py` / `wall-rename-v3.py`（UFM plan/apply 已覆盖？）
  - 旧 `openclaw-session-watcher` timer/service（如果已彻底废弃）
  - `scripts/` 下其他可能的重复/废弃脚本

### 4. infos-handle 结构分析（只读，不动）
- 文件清单：脚本 + systemd 服务 + 补丁 + 子模块
- 目标：画结构图，说明现状

### 5. 收尾
- git push 所有改动
- 变更流水记录
- 关闲置分身/定时器清理

## ⚡ 明天要做的

1. **配新机器**（GTX 1070 + 8GB VRAM + 8GB RAM）→ 可跑轻量本地模型推理
   - 需要先确认那台机器的系统、网络、OpenClaw 安装状态
   - 可能用途：本地 TTS/ChatTTS 推理，减轻主机 CPU 压力
2. 继续 CPU 过载自动响应
3. 废弃冗余清理
4. infos-handle 结构分析

## 📍 关键文件位置速查

| 用途 | 路径 |
|------|------|
| CPU 过载 | `scripts/openclaw-cpu-emergency.py --diagnose` / `docs/通用-CPU负载过高临时处理方案.md` |
| 路径过长 | `docs/通用-Unity资产路径过长风险分析与应对方案.md` |
| 健康采集器（改） | `scripts/openclaw-health-collector.py`（在 do_full 分支补 CPU 自动响应） |
| Timer 配置 | `tools/openclaw-systemd/` (workspace 副本) / `~/.config/systemd/user/` (runtime) |
| 问题记录 | `docs/通用-系统运行问题记录.md` |
| 审查结论 | `/mnt/data/openclaw/scratch/timer-audit-conclusion.md` |
| 今日日志 | `memory/daily/2026-06-09.md` |
