# Mark42 3天连续守护 — 监控日志

> 启动时间：2026-06-17 10:15
> 计划结束：2026-06-20 10:15
> 版本：v2.3

## 基线快照

| 指标 | 值 |
|:---|:---|
| 上下文使用率 | 54.2% |
| armor-guard cycle | 第 1 轮（新启动） |
| engine-daemon cycle | 3 |
| task-watch cycle | 31 |
| broker 事件 | 239 条 / 81.4KB |
| 日志位置 | `/mnt/data/openclaw/mark42/logs/` |
| 日志阈值 | 单文件 ≤50MB / ≤10000 行，超限自动截尾 |

## 检查点记录

### 2026-06-17 10:19 — 启动确认
- armor-guard: ✅ 运行中
- engine-daemon: ✅ 运行中（task-watch 正常）
- 心跳: ✅
- stderr: 无错误

### 2026-06-17 22:00 — 机器关机（预计）
- 用户端午节放假，2026-06-18 ~ 2026-06-22 不在
- 守护未跑满 3 天（实际运行约 12h），但逻辑已验证通过
- 下次开机后需手动启动 assemble 或等待 cron 触发

### 2026-06-18 11:40 — v2.3.1 审查 + 修复（终定）
- **版本**：v2.3.0 → v2.3.1
- **发现** 🔴 1 个关键 bug：`armor.py:168` LLM 压缩 provider 名不匹配 → 静默回退启发式
- **发现** 🟡 1 个精度隐患：token 估算仍用固定常数
- **修复**：LLM 压缩链路 → 最终定为 **MiniMax M3**（DeepSeek 留给主会话）
- **验证**：minimax apiKey 查找链路 ✅ | 烟测 18/18 ✅
- **审查范围**：8 模块全量代码 + 配置交叉验证 + 两项审查报告逐条对照 + 联网搜索最佳实践
- **结论**：代码质量健康，无安全风险
- **下次开机动作**：`python3 scripts/mark42.py assemble` 启动守护 → `python3 scripts/mark42.py status` 确认状态

### 2026-06-25 07:33 — Day 6 收尾 + 压缩子系统五大算法齐备

- **完成项**：code_compressor 类 docstring bug 修复 / diff_compressor 新建 (29 测试) / text_compressor 新建 (27 测试) / algo_scheduler 内容类型智能路由 / mark42-tests.py 30/30 全绿
- **未动现有守护**：armor-guard / engine-daemon / task-watch 全程未触碰，无重启需求
- **配置文件**：config.json / loops.json 未改，无 schema 漂移
- **下次开机动作**：如需重启 armor 路径，仅修改 `algo_scheduler.py` 单文件，下次 `armor_pre_compact_hook` 自动走新路由（5 个算法）

### 2026-06-25 07:34 — Mark42 全量烟测

（详见下一节：mark42-tests.py + 全模块 lint + 守护状态检查）

### 2026-06-25 07:45 — Day 7 异步化改造完成

- **完成项**：`compress_queue.py` 新建 (28 单元测试) / `armor_compress_async` 异步入口 / mark42-tests.py 30→32 全绿
- **未触动**：`armor_compress()` / `armor_pre_compact_hook()` / engine daemon / config.json / loops.json 全部保持 Day 4-6 状态
- **守护影响**：现有 armor-guard / engine-daemon 双进程**无需重启**；新异步入口仅在 `armor_compress_async()` 被显式调用时启用
- **下次开机动作**：如有代码模块在 monitor 范围内，下次 `armor_pre_compact_hook` 触发时会自动检测到 `compress_queue.py` 可用（不会被破坏）
- **新增可观测点**：`armor_compress_queue_stats()` 暴露 6 个统计字段

### 2026-06-25 07:45 — Day 7 全量烟测

- mark42-tests.py **32/32 全绿**（含 Day 7 新增 2 项）
- 10/10 模块 py_compile 零错误
- 5 Loop 全活跃、守护无新错
- 压缩子系统子测试累计 124 项全过（不含集成场景）

### 2026-06-25 07:48 — Day 8 LLM 接入完成

- **完成项**：`llm_text_compressor.py` 新建 (37 单元测试) / `config.py` 注册 `llmCompress` / `text_compressor.py` method="llm" 真接 / mark42-tests.py 32→34 全绿
- **真实 LLM 调用**：MiniMax-M3 模型，4.4s/次，90.8% 压缩率
- **模型/Key 路由**：沿用 OpenClaw minimax provider，与 `_llm_analyze` 同源 — 用户无需任何配置
- **失败降级**：4 层（LLM 错→rule_based→原文透传→永不崩）
- **未触动**：`algo_scheduler.py` 路由表（scheduler 仍默认 rule_based；LLM 通过 `TextCompressor(method="llm")` 显式 opt-in）
- **守护影响**：现有 armor-guard / engine-daemon 双进程**无需重启**；新模块 `llm_text_compressor.py` 独立存在
- **下次开机动作**：下次 `armor_pre_compact_hook` 触发时，`text_compressor(method="llm")` 路径已可用，失败自动回退

### 2026-06-25 07:48 — Day 8 全量烟测

- mark42-tests.py **34/34 全绿**（含 Day 8 新增 2 项：LLM 单元 + 集成）
- 11/11 模块 py_compile 零错误
- 5 Loop 全活跃、守护无新错
- LLM 真实调用：MiniMax-M3 / 4.4s / 90.8% 压缩率
- 压缩子系统子测试累计 161 项全过

### 2026-06-25 07:58 — 阶段 1 收官 + Phase 2 路线图

- **阶段 1 收官**: 8 天 5 算法 + 异步 + LLM + 智能路由全部完成
- **新文件**: `docs/design/mark42-阶段1收官README-20260625.md` (280 行) — 新会话接力入口
- **更新日志**: 累计 9 个 Day 全部记录在 `mark42-更新日志.md`
- **开发目标**: 7 项 Phase 2 任务记录在 README §六
- **当前最强能力**: LLM 语义压缩 (84-90% 压缩率) + 5 算法自动路由
- **下一会话 (优先级 P0)**:
  1. LLM 压缩走异步队列 (改 `text_compressor.py` ~30 行)
  2. `MARK42_TEXT_USE_LLM` 环境变量 (改 `algo_scheduler.py` ~20 行)
- **守护影响**: 零 (纯文档 + 规划, 无代码改动)
- **下次开机动作**: 无 (armor-guard / engine-daemon / config / loops 全保留 Day 9 状态)

### 2026-06-25 10:55 — Day 10: Phase 2 目标 1+2 收尾

- **目标 1 (P0)**: LLM 压缩走异步队列 ✅
  - 新增 `llm_text_compress_async()` 双入口 (wait=True/False, priority, timeout)
  - `compress_queue.py` worker 新增 `content_type="llm:*"` 路由
  - **实测 `wait=False` 入队 0.1ms 即返** — daemon tick 永不阻塞
- **目标 2 (P0)**: `MARK42_TEXT_USE_LLM` 环境变量 ✅
  - 三态: `true` / `false` (默认) / `auto` (按大小自动选)
  - 配套: `MARK42_LLM_MODE` (summarize/simplify/extract) + `MARK42_LLM_AUTO_THRESHOLD` (字节数)
  - text 嗅探阈值 4KB → 8KB (避免 Day 3 回归)
- **测试**: mark42-tests.py 34 → **40 集成测试**, 0 失败
- **LLM 单元测试**: 37 → 49 子测试
- **压缩子系统子测试累计**: 161 → **210**
- **改动文件**: llm_text_compressor.py / compress_queue.py / algo_scheduler.py / mark42-tests.py / 收官 README
- **守护影响**: 零 (代码改动不需重启守护)
- **下次开机动作**: 无

### 新增 env var 文档 (运维参考)

```bash
# LLM 压缩全局开关 (Day 10 起)
# - false: 维持现状, scheduler 走 rule_based
# - true:  scheduler 路由 text 时强制走 LLM (每次 4-5s)
# - auto:  scheduler 路由 text 时, 输入 >= 阈值自动走 LLM
export MARK42_TEXT_USE_LLM=false  # 默认

# LLM 模式选择 (Day 10 起)
# - summarize: 摘要 (默认, 最稳)
# - simplify: 简化措辞 (适合技术文档)
# - extract: 抽取关键信息 (最激进, 适合 log)
export MARK42_LLM_MODE=summarize

# auto 模式阈值 (字节, 默认 5120 = 5KB)
export MARK42_LLM_AUTO_THRESHOLD=5120
```

**使用场景**:
- 平时开发: 默认 (false) - 0 成本, daemon 极快
- 跑离线批处理: `MARK42_TEXT_USE_LLM=true` - 高压缩, 慢一点
- 在线长文本智能压缩: `MARK42_TEXT_USE_LLM=auto` - 自动平衡

**注意**: LLM 调走 OpenClaw minimax provider, 与 `_llm_analyze` 同源, 走 MiniMax-M3 模型。

### 2026-06-25 11:10 — Day 11: Phase 2 路线文档化

- **任务**: 按用户要求把 P1-3 → P2-7 完整技术路线写好
- **新文件**: `docs/design/mark42-Phase2路线-20260625.md` (947 行 / 23KB)
  - 9 章节, 覆盖 6 个目标详细实施步骤
  - 每个目标含: 背景 / 改动文件 / 关键设计决策 / 实施步骤 / 测试方案 / 完成定义
- **P2-7 更正**: Heavy 层已存在 427 行, 路线文档明确"集成"而非"实现"
- **README §六/§七 指针更新**: 交接清单 5 → 6 文件, §六 加独立路线文档指针
- **下次开机动作**: 无, 等用户决定是否开始 P1-4 (SmartCrusher 拆, 建议 1-2 小时)

### 2026-06-25 12:35 — Day 13: P2-6 性能基准

- 新增 `scripts/mark42_modules/perf_bench.py`
- 自动生成 `docs/design/mark42-压缩方案-性能基准-20260625.md`
- 结果覆盖: 5 类样本 × 4 尺寸 × 纯算法/scheduler + 2 条 queue 结果
- 关键结论:
  - `enqueue-only` P50 = 0.00ms
  - 最慢链路为 `scheduler/code_1024kb`
  - 最高内存也在 `scheduler/code_1024kb`
- 本次未测 LLM（未检测到可用 key），下次如需可在有 key 环境重跑
- 代码层面无运行时行为改动，仅新增基准与报告
