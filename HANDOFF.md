# HANDOFF.md — 2026-05-29 上午

## 状态：QMD 语义搜索排查 — ✅ 已完成

### 背景
QMD 的 memory_search 长期返回 0 结果。

### 排查过程
1. **embedInterval=0** → 向量功能根本未开启 → 已修复（改 30m）
2. **模型下载** → embedding (319MB) + reranker (610MB) + LLM (1.2GB) 全部就绪
3. **vsearch 超时** → 根因：vsearch 也调用 expandQuery() 加载 1.2GB LLM
4. **禁用 LLM** → CLI 3.2s 可跑（走缓存），但 OpenClaw 集成时缓存不命中
5. **切换 builtin** → ✅ 最终方案

### 最终方案
- 引擎：builtin + github-copilot embeddings
- 索引：121 文件 / 1493 chunk
- 搜索：4-6s，vectorScore 0.54-0.63
- QMD 保留为备用（BM25 search 可用）

### 配置要点
- `memory.backend: "builtin"`
- `memorySearch.provider: "github-copilot"`
- systemd drop-in `qmd-cpu.conf` 已清理废弃的 QMD_GENERATE_MODEL

### 详细存档
- PLANS.md → QMD 语义搜索排查结论
- 变更流水 → docs/通用-OpenClaw-补丁变更流水.md
