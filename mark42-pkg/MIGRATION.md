# Mark42 版本迁移指南

本文档说明 Mark42 的版本策略，以及跨版本升级时的迁移方法。

## 版本策略（SemVer）

Mark42 遵循[语义化版本 2.0](https://semver.org/lang/zh-CN/)：`主版本.次版本.修订号`

- **主版本（MAJOR）**：包含不兼容的 API 变更（breaking change）
- **次版本（MINOR）**：向后兼容的新功能
- **修订号（PATCH）**：向后兼容的 Bug 修复

### Breaking Change 处理原则

1. 任何破坏性变更只在 **主版本** 引入
2. 计划废弃的功能，提前至少 1 个 minor 版本发出 `DeprecationWarning`
3. 废弃项在 CHANGELOG 的 `Deprecated` 段落明确列出
4. 每个主版本升级在本文档提供专门的迁移小节

---

## 兼容性说明

### v2.x 系列（当前）

v2.x 系列内部保持向后兼容。以下约定在整个 v2.x 稳定：

- **配置文件路径**：`~/.config/mark42/`（配置）+ `~/.local/state/openclaw/mark42/`（状态）
- **数据盘挂载点**：默认 `/mnt/data`，可用 `MARK42_DATA_MOUNT` 环境变量覆盖，不存在时自动回退到 `XDG_STATE`
- **CLI 命令结构**：`mark42 <module> [options]`，模块名保持稳定
- **状态文件格式**：`memory-index.json` / `actions.jsonl` / `history/` 结构稳定

### 环境变量

| 变量 | 作用 | 默认 |
|------|------|------|
| `MARK42_DATA_MOUNT` | 数据盘挂载点 | `/mnt/data`（不存在则回退 XDG_STATE） |
| `MARK42_SCRATCH` | scratch 目录 | `$MARK42_DATA_MOUNT/openclaw/scratch` |
| `XDG_STATE_HOME` | 状态根目录 | `~/.local/state` |

---

## 迁移小节模板（供未来大版本填充）

> 下面是 vX → vY 迁移小节的标准结构，发布主版本时按此填充。

### vX.0 → vY.0

**变更概览**
- <一句话说明本次主版本的核心变化>

**破坏性变更**

| 变更项 | 旧行为 | 新行为 | 迁移方法 |
|--------|--------|--------|----------|
| ... | ... | ... | ... |

**废弃项**
- <列出移除的功能及替代方案>

**迁移步骤**
1. 升级前备份状态目录：`cp -r ~/.local/state/openclaw/mark42 ~/mark42-state-backup`
2. 升级：`pip install -U mark42`（或 `bash install.sh`）
3. 运行 `mark42 --config` 确认配置兼容
4. 运行 `mark42 status` 验证系统状态

**回滚方法**
- `pip install mark42==X.Y.Z` 回退到旧版本
- 恢复状态目录备份

---

## 遇到迁移问题？

- 查阅 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- 在 [Discussions](https://github.com/missyouangeled/Mark1/discussions) 提问
- 提交 [Issue](https://github.com/missyouangeled/Mark1/issues)
