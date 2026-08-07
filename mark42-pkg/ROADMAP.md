# Mark42 路线图

> ✅ 已完成 · 🚧 进行中 · 📅 计划中 · 🔮 远期规划
>
> 本路线图是动态的，会根据实际进展调整。最后更新：2026-07-30

## 时间线总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| v2.x 稳定化 | 核心功能稳定，测试全绿，CI 门禁转绿 | ✅ 已完成 |
| v2.9 质量提升 | 严格类型检查、覆盖率提升、PyPI 发布准备 | 📅 计划中 |
| v3.0 可观测性 | OpenTelemetry 集成、可选遥测 | 🔮 远期规划 |
| v3.x 商业化 | Open-Core 模式探索 | 🔮 远期规划 |

---

## ✅ 已完成 (v2.8.2)

### 核心模块稳定可用
- `armor` 上下文压缩守护
- `engine` 循环引擎
- `heavy` 重型任务处理
- `consciousness` 战甲意识层（C1-C5 + advisor）
- `audit` 压缩后质量核对
- `pii_redactor` 隐私脱敏
- `cluster_manager` 集群思维（R14）
- `compaction_diag` OpenClaw 压缩配置诊断
- `chaos` 混沌工程、`breaker` 熔断器、`arclock` 通用适配层

### 方案 44：全功能缺口补全（2026-08-07）

> 上游方案：`docs/plans/44-Mark42-全功能缺口补全方案-v1.md`
> 六条闭环全部落地，所有新增能力默认关闭 / shadow。

- [x] **Phase 0**：基线冻结 + ContextState/SourceCursor schema + 探针 schema + 4 个场景
- [x] **Phase 1**：约束身份/静态完整性 + 质量趋势 + 探针接入 builtin_audit（shadow）
- [x] **Phase 2**：增量合并引擎（5 种 patch 操作 + 零污染保证）+ 状态版本化持久化 + 接入 armor 三路分支
- [x] **Phase 3**：Hybrid Recall（BM25+Vector 并行 + RRF 融合）+ Cross-Encoder Reranker 接口 + QMD 适配器
- [x] **Phase 4**：Heavy DAG 依赖图 + 资源预算 + 图校验 + 局部重规划 + Checkpoint
- [x] **Phase 5**：混沌自动闭环（L0-L3 安全等级）+ 错误档案反馈学习（L3->L2 降级 + 有效性追踪）
- [x] **Phase 6**：Shadow 对比报告 + 回滚演练（6/6 通过）

### 数据
- 2545 个单元测试 100% 通过（25 skip）
- ruff 全绿 / mypy 89 文件 0 issues
- CI 门禁转绿
- `/mnt/data` 路径可移植化
- 完整中文文档体系
- MIT 许可证

---

## 📅 近期规划 (v2.9)

### 质量与可靠性
- [ ] 逐步启用 mypy `--strict`（从核心模块 config/utils/armor 开始）
- [ ] 测试覆盖率从当前基线逐步提升，CI 覆盖率门槛提高到 60%+
- [ ] 补齐 `text_compressor` / `llm_text_compressor` 的 `method="llm"` 真实实现（当前为占位接口）

### 发布与分发
- [ ] PyPI 正式发布（`pip install mark42`）
- [ ] setuptools-scm 从 Git tag 自动提取版本
- [ ] 发布制品生成 SBOM（CycloneDX）

### 开发者体验
- [ ] pre-commit 钩子（已提供配置，待推广到贡献流程）
- [ ] API 参考文档自动生成（pdoc / Sphinx）

---

## 🔮 远期规划 (v3.0+)

### 可观测性
- [ ] OpenTelemetry 集成（trace/metrics/logs）
- [ ] 扩展现有 `metrics-server`（Prometheus 端点已有雏形）
- [ ] 可选的匿名使用统计（默认关闭，遵守隐私合规）

### 商业化探索
- [ ] Open-Core 模式：核心开源（MIT），企业增值功能单独许可
- [ ] 边界规划：多租户 / RBAC / 审计日志 / SLA 支持

---

## 版本策略

- **SemVer**：严格遵循语义化版本（详见 [MIGRATION.md](MIGRATION.md)）
- **Deprecation**：废弃功能提前至少 1 个 minor 版本警告

---

## 如何参与

- 💡 提出想法：到 [Discussions](https://github.com/missyouangeled/Mark1/discussions) 分享建议
- 🔀 提交 PR：认领感兴趣的功能（先看 [CONTRIBUTING.md](CONTRIBUTING.md)）
- 🐛 报告 Bug：帮助我们发现问题
