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

## ✅ 已完成 (v2.8.1)

- [x] 核心模块稳定可用
  - `armor` 上下文压缩守护
  - `engine` 循环引擎
  - `heavy` 重型任务处理
  - `consciousness` 战甲意识层（C1-C5 + advisor）
  - `audit` 压缩后质量核对
  - `pii_redactor` 隐私脱敏
  - `cluster_manager` 集群思维（R14）
  - `compaction_diag` OpenClaw 压缩配置诊断
  - `chaos` 混沌工程、`breaker` 熔断器、`arclock` 通用适配层
- [x] 1737 个单元测试 100% 通过（28 skip）
- [x] CI 门禁转绿（ruff check + pytest + pip-audit + 安全扫描）
- [x] `/mnt/data` 路径可移植化（`MARK42_DATA_MOUNT` env 覆盖 + XDG_STATE 回退）
- [x] 完整中文文档体系（README / QUICKSTART / TUTORIAL / ARCHITECTURE / CONFIG-GUIDE）
- [x] MIT 许可证

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
