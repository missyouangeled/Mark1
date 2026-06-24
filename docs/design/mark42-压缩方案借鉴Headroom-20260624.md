# Mark42 上下文压缩方案借鉴 Headroom 设计

> 设计日期：2026-06-24
> 设计人：贾维斯
> 触发原因：点点要求"学习 Headroom 的压缩技术，用于 Mark42 项目上"
> 状态：🟡 设计方案，未实施

---

## 一、背景

### 1.1 调研对象：Headroom

- **GitHub**：[chopratejas/headroom](https://github.com/chopratejas/headroom)
- **作者**：Tejas Chopra
- **类型**：OSS SDK（Apache 2.0，5.4K stars，v0.22.4）
- **定位**：LLM 上下文压缩层（在 LLM 调用前压缩 60-95% token）
- **不安装**：仅学习其算法思路，**不引入依赖**

### 1.2 Headroom 的 6 大压缩算法

| # | 算法 | 用途 | 压缩率 |
|---|---|---|---|
| 1 | **SmartCrusher** | JSON 工具调用输出 | 60-90% |
| 2 | **CodeCompressor** | AST 级代码 | 70-85% |
| 3 | **Log Deduplicator** | bash / docker / pytest 日志 | 80-95% |
| 4 | **Search Ranker** | RAG 检索片段排序 | 50-70% |
| 5 | **ModernBERT** | 通用文本语义压缩 | 50-80% |
| 6 | **Git-Diff Preserver** | git diff 保留 | 90% |
| - | **ML Router** | 图片智能路由 | - |

---

## 二、Mark42 铠甲当前实现回顾

代码位置：`scripts/mark42_modules/armor.py`

| 维度 | 现状 |
|---|---|
| **检测方式** | 文件字节数 ÷ `BYTES_PER_KTOKEN`（粗略估算） |
| **触发压缩** | 写 `/compact` 命令到 JSONL，触发 OpenClaw 内部压缩 |
| **启发式分类** | 关键词白名单（PRESERVE_KW）+ 黑名单（DISCARD_KW）+ 长度判断（>200 保留） |
| **生成方式** | 先 LLM 驱动（保留语义），失败回退启发式 |
| **架构** | Python 单文件（`mark42_modules/armor.py`） |

### 2.1 关键阈值（config.json）

| 阈值 | 数值 | 动作 |
|---|---|---|
| THRESHOLD_WARN | 60% | 仅提示 |
| THRESHOLD_ALERT | 80% | 建议压缩 |
| THRESHOLD_CRIT | 95% | 强制压缩 |

### 2.2 最近触发记录

- 6/23 16:39: 88.3% → compress（armor/actions.jsonl）

---

## 三、关键差距分析

### 3.1 架构差异：事后 vs 事前

```
Mark42 现状:  [写完对话] → [文件变大] → [超过 80%] → [注入 /compact] → [OpenClaw 压缩]
                                              ↑ 事后
Headroom:    [要送 LLM] → [SmartCrusher 等 6 个算法] → [压缩后送] → [LLM 收到 30-40% 体积]
                  ↑ 事前
```

**根本差异不是算法，是触发点**：
- Mark42 是"事后兜底"——发现文件太大才介入
- Headroom 是"LLM 上游压缩"——在送进 LLM 之前就压

### 3.2 算法缺失矩阵

| 维度 | Mark42 现状 | Headroom 是否有 | 差距 |
|---|---|---|---|
| 工具输出 JSON 处理 | ❌ 无 | ✅ SmartCrusher | **缺** |
| 代码 AST 压缩 | ❌ 无 | ✅ CodeCompressor | 缺 |
| 日志去重 | ❌ 无（整体打包） | ✅ Log Dedup 80-95% | **缺最关键** |
| RAG 片段排序 | ❌ 无 | ✅ Search Ranker | 缺 |
| 图片智能路由 | ❌ 无 | ✅ ML Router | 缺 |
| Git diff 保留 | ❌ 无 | ✅ | 缺 |
| 启发式黑白名单 | ✅ 简单 | ✅ 更精细 | **Mark42 弱** |
| LLM 驱动分类 | ✅ 有 | ✅ 有 | 同 |

---

## 四、可借鉴的 4 个方向

### 方向 1：工具输出 JSON 压缩（SmartCrusher 思路）

**Headroom 思路**：
- 工具调用输出（grep 结果、API 响应、文件列表）通常高度冗余
- 算法：JSON 结构保留 + 字段去重 + 数组截断 + 嵌套展开

**Mark42 借鉴方案**：
- 在写入 JSONL **之前**，对 `function_call` / `tool_use` 输出做 JSON 瘦身
- 实现：
  - 数组超过 20 元素 → 保留前 10 + 标记"共 N 个"
  - 字符串值 > 500 字节 → 保留前 200 + 标记"省略"
  - 重复字段名 → JSON Lines 化（每行只保留必要字段）
- 预期压缩率：60-80%

**风险**：可能丢失关键调试信息
**缓解**：保留"原值"在 metadata，遇到 error 自动恢复

### 方向 2：bash/docker/pytest 日志去重（Log Dedup 思路）

**Headroom 思路**：
- 80-95% 的日志是重复行（`DEBUG: loading module X` 出现 1000 次）
- 算法：行级 dedup + 重复计数

**Mark42 借鉴方案**：
- 检测 JSONL 中 `tool_result.content` 字段
- 如果是 log 风格（重复行 > 5）：
  - 保留所有唯一行
  - 重复行用 `<N repeated>` 标记
- 预期压缩率：70-90%（贾维斯一次长 test 输出可能 50-200KB）

**风险**：测试失败时可能丢失关键 stack trace
**缓解**：失败上下文（最后 50 行）原样保留

### 方向 3：RAG 检索片段排序（Search Ranker 思路）

**Headroom 思路**：
- RAG 返回的 N 个片段，不是全部都跟当前 query 相关
- 算法：query-vs-chunk 相似度排序 + top-K 截断

**Mark42 借鉴方案**：
- 配合 L1/L2.5 记忆系统，对 `memory_search` 返回结果：
  - 全部返回（默认 5 个）→ 改 top-3 + 总数标记
  - 长片段（>1000 token）→ 截断到 300 token + 文件:行号标记
- 预期压缩率：50-70%

**风险**：可能丢失边缘相关上下文
**缓解**：保留完整 ID，可在 compact 后反查

### 方向 4：整体架构改造（上游压缩）⚠️ 高风险

**思路**：
- 改 Mark42 写 JSONL 的时机
- **不**等文件变大，而是**写入前**先压缩

**风险**：
- 改 OpenClaw 内部 session 格式
- 第三方工具读 JSONL 会出错
- debug 时看不到原文
- **建议暂缓**

---

## 五、3 阶段实施路线

### 阶段 1：算法移植 + 实验模式（1-2 周）

**目标**：把 SmartCrusher 思路移植到 Mark42，加 `--experiment` 标志

```python
# mark42_modules/armor.py 新增
def smartcrush_tool_output(content: str, max_bytes: int = 4096) -> str:
    """借鉴 Headroom SmartCrusher：JSON 工具输出压缩"""
    # 数组截断
    # 字符串截断
    # 重复字段处理
    ...

def armor_compress_experiment():
    """实验模式：先尝试新算法，跟原算法对比"""
    # 1. 读当前 session 尾部 60 行
    # 2. 对 tool_result 跑 smartcrush
    # 3. 跟原 armor_compress 对比压缩率
    # 4. 写对比报告到 /tmp/mark42-experiment.log
    ...
```

**验证指标**：
- 压缩率（目标 60%+）
- LLM 回答质量（人工评估，3 个测试场景）
- 不破坏 JSONL 结构（外部工具仍能读）

**风险控制**：
- **不**改主流程，仅加 `--experiment` 标志
- 默认关闭，需手动 `--experiment=true` 启动
- 实验日志独立（不影响 `actions.jsonl`）

### 阶段 2：上线 + 监控（1 周）

**目标**：实测效果，收集数据

```python
# mark42_modules/armor.py
# 加到 config.json:
{
  "experiment": {
    "smartcrush_enabled": true,  # 阶段 2 才开
    "log_dedup_enabled": false,  # 暂未实施
    "compression_log": "/tmp/mark42-experiment.jsonl"
  }
}
```

**监控项**：
- 每天压缩率统计
- LLM 回答质量异常
- JSONL 兼容性
- 工具调用成功率

**回滚条件**：
- 压缩率 < 30% → 停
- LLM 回答质量明显下降 → 停
- 任何工具调用失败 → 立即停

### 阶段 3：架构改造（待评估）

**目标**：改写时机，从"事后"变"事前"

**前置条件**：
- 阶段 1 + 2 稳定运行 2 周
- 压缩率持续 > 50%
- 零质量事故

**风险**：高，必须有充分测试覆盖

**预计改动范围**：
- `mark42_modules/armor.py`：新增 `pre_write_hook()`
- `mark42_modules/writer.py`（如果存在）：钩子集成
- OpenClaw 内部 session 格式：可能要扩展 metadata
- 第三方工具：可能受影响

**建议**：先在子项目试点，不要直接改主会话

---

## 六、风险评估（按点点两条原则）

| 原则 | 评估 | 实施 |
|---|---|---|
| **一、系统稳定运行** | 改 Mark42 是改核心基础设施 | 3 阶段渐进，每阶段独立可回滚 |
| **二、避免风险 skill / 风险操作** | 借鉴算法思路，**不**引入 Headroom 依赖 | 纯 Python 实现，不 pip install headroom-ai |

---

## 七、为什么不直接用 Headroom？

| 原因 | 说明 |
|---|---|
| 1. 设计目标不同 | Headroom 是"LLM 调用前压缩"，Mark42 是"事后兜底"——直接用会破坏 Mark42 架构 |
| 2. OpenClaw 集成复杂 | Headroom 的"透明代理"模式（`headroom wrap claude`）要劫持所有 LLM 流量——风险高 |
| 3. 算法可以白嫖 | Headroom 的核心是 6 个算法，**算法思路可以移植**到 Mark42，但**不必引依赖** |
| 4. 维护成本 | 自己实现可控，引依赖要追上游版本 |

---

## 八、关联文档

- 灵感来源：Headroom（GitHub `chopratejas/headroom`）
- 当前实现：`scripts/mark42_modules/armor.py`
- 配置：`~/.local/state/openclaw/mark42/config.json`
- 历史分析：`docs/design/mark42-compaction-analysis-20260616.md`
- 运维日志：`docs/design/mark42-运维日志.md`
- 架构设计：`docs/design/mark42-架构设计.md`

---

## 九、待办

- [ ] 阶段 1：实现 `smartcrush_tool_output()` + 实验模式
- [ ] 阶段 1：3 个测试场景（grep 输出 / API 响应 / 大文件读取）
- [ ] 阶段 2：配置开关 + 监控埋点
- [ ] 阶段 2：2 周稳定运行
- [ ] 阶段 3：架构改造（待评估）

---

**最后更新**：2026-06-24 12:30
**设计人**：贾维斯（响应点点："先保存一下，把这个修改设计方案保存在 mark42 项目中的相关的开发文档中"）