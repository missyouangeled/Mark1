# Mark42 输出 Token 优化最小设计（2026-07-09）

## 目标

把“输出 token 优化”从口头要求，沉淀为 Mark42 的正式能力，目标是：

- 减少无效长输出和工具结果回灌
- 降低主会话 token 增长速度
- 保持关键证据，但避免冗长复述
- 不牺牲需要详细说明的场景质量

---

## 先回答：这件事能不能做

可以。

而且应当做成 **Mark42 的策略层能力**，不是只靠聊天时临时提醒“说短点”。

---

## 优化对象

第一阶段只优化以下三类输出：

### 1. CLI / verify / 守护输出
目标：
- 只保留结论、摘要、关键告警
- 避免大段日志直接喷到前台 / systemd 日志

### 2. 工具结果摘要化
目标：
- 读大文件 / 网页 / 日志后，默认只保留结论 + 关键证据
- 不把长文本原样塞回主会话

### 3. Mark42 体检 / 验收输出模板
目标：
- `PASS / WARN / FAIL` 继续保留
- 但默认输出更短
- 详细信息需要显式 `--verbose`

---

## 不做什么

第一阶段不做：

- 不强行压缩所有用户可见回答
- 不改变需要详细方案说明时的输出长度
- 不自动改 OpenClaw 主模型参数
- 不试图拦截所有模型自然语言回答

也就是说，第一阶段针对的是 **Mark42 自己的输出面**，不是全局替代助手说话。

---

## 推荐能力名

建议新增能力：

- `output-token-guard`

也可作为 Mark42 子命令：

```bash
mark42.py token-guard status
mark42.py token-guard apply
mark42.py token-guard verify
```

但第一阶段不一定先做独立命令，也可以先把策略接入已有模块。

---

## 第一阶段具体改动建议

### A. install / verify 输出分层

现状问题：
- `verify.sh` 和部分 CLI 已经相对克制，但仍会把一些冗长结果暴露到终端

建议：
- 默认模式：只输出摘要
- `--verbose`：才输出详细行

适用文件：
- `tools/mark42-systemd/verify.sh`
- `scripts/mark42_modules/context_safety.py`
- `scripts/mark42_modules/cli.py`

### B. engine / armor / broker 事件写入瘦身

现状问题：
- broker 事件、日志 summary、健康提示里可能带入过长文本
- 长期运行后，这些文本既占日志，也可能反向进入上下文

建议：
- 事件 summary 控制在 80~160 字以内
- detail 控制在 200~300 字以内
- 超长内容写文件，不直接写 broker/event 正文

适用文件：
- `scripts/mark42_modules/engine.py`
- `scripts/mark42_modules/armor.py`
- `scripts/mark42_modules/utils.py`

### C. LLM 压缩 / 分析输出瘦身

现状问题：
- `_llm_analyze()`、压缩器、状态摘要可能生成过长结构
- 即使有价值，也未必需要全部落到用户可见面

建议：
- 状态输出层只展示关键字段
- 原始 JSON 分析结果保存在状态文件，不默认打印全量

适用文件：
- `scripts/mark42_modules/armor.py`
- `scripts/mark42_modules/llm_text_compressor.py`
- `scripts/mark42_modules/text_compressor.py`

---

## 第一阶段策略基线

### 1. 输出长度基线

- `summary`：建议 <= 120 字
- `detail`：建议 <= 280 字
- `preview`：建议 <= 160 字
- CLI 默认终端输出：单次 <= 40 行为目标

### 2. 事件字段策略

对于 broker / action / status：

- `summary`：一行结论
- `detail`：保留必要原因
- `metadata`：放结构化值，不塞大段文本

### 3. 长内容处理策略

当内容超阈值时：
- 用户可见面只显示摘要
- 原文写入文件/状态目录
- 需要时再单独读取

---

## 最小实现顺序

### 第 1 步
先做 **输出策略函数**，统一截断逻辑。

建议新增：
- `scripts/mark42_modules/output_guard.py`

建议函数：
- `trim_summary(text, limit=120)`
- `trim_detail(text, limit=280)`
- `compact_preview(text, limit=160)`
- `should_spill_to_file(text, limit=300)`

### 第 2 步
把这些函数接进：
- `engine.py`
- `armor.py`
- `context_safety.py`
- `cli.py`

### 第 3 步
给 `verify.sh` / 关键 CLI 增加 `--verbose` 模式。

---

## 验收标准

满足以下条件即可视为第一阶段完成：

1. Mark42 关键 CLI 默认输出明显更短
2. verify / status / context-safety 不丢失关键结论
3. broker / event summary 不再塞入长文本
4. 长内容会被摘要化，而不是直接打印
5. 遇到需要详细信息时，仍有 `--verbose` 或状态文件可追溯

---

## 风险提醒

输出 token 优化不能粗暴做成“所有东西都变短”。

需要避免两种坏结果：
- 该详细时不够详细，损伤可用性
- 为了节省 token，把证据链切断，影响排错

所以第一阶段必须优先做：
- Mark42 自身输出面
- 事件摘要化
- 详细信息后置

而不是直接全局限字数。

---

## 当前建议

现在适合继续做，而且建议先从 **output_guard 工具层 + engine/armor/context_safety 接入** 开始。
