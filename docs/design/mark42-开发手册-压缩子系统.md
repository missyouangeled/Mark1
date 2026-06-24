# Mark42 压缩子系统开发手册

> 创建日期：2026-06-24
> 状态：🟡 设计手册（待实施）
> 目标读者：**接手这个项目的下一个模型 / 下一个人**
> 上一版：[mark42-压缩方案-阶段1实施计划-20260624.md](./mark42-压缩方案-阶段1实施计划-20260624.md)（阶段 1 Day 1-4 已完成）
> 本版本：**方向 A（5 个 Headroom 算法）+ Day 5（异步化）的详细设计 + 交接清单**

---

## 〇、给接手者的开场白

如果你正在读这份文档，你大概率是因为：

1. **点点**（用户）让我重启 Mark42 压缩子系统的工作
2. **上一个模型**（比如贾维斯 / DeepSeek / Kimi / GLM）做了一部分就停了
3. 现在 session 是新的，**前一个模型脑子里的东西全没了**

**不要慌**。这份文档就是你的"第二个脑子"。读完之后你应该能：

- ✅ 知道 Mark42 是什么、为什么要做压缩子系统
- ✅ 知道现在完成到哪（Day 1-4），剩下要做什么（Day 5+）
- ✅ 知道 5 个 Headroom 算法**真实怎么实现**（不是空想）
- ✅ 知道 Day 5 异步化的**真实约束**（不是天马行空）
- ✅ 知道改代码前要读哪些文件、改哪个函数、加什么测试
- ✅ 知道踩过的坑（Day 1-4 的坑、未来要避开的坑）

**约定**：
- 所有路径都是**绝对路径**或相对 `~/.openclaw/workspace/` 的相对路径
- 所有命令都**可以直接 copy-paste 跑**
- 所有"代码示例"都是**伪代码骨架**，不是完整代码——你需要根据上下文填实现

---

## 一、上下文速读（5 分钟）

### 1.1 Mark42 是什么

| 维度 | 内容 |
|---|---|
| 项目名 | **Mark42**（模块化智能铠甲）|
| 用途 | 给 OpenClaw 套一层"上下文铠甲"，主动守护会话不被撑爆 |
| 关系 | 是 OpenClaw 之上的**附加层**，不替代 OpenClaw 自己的压缩 |
| 代码入口 | `~/.openclaw/workspace/scripts/mark42.py`（CLI）+ `scripts/mark42_modules/`（13 个模块）|
| 配置 | `~/.local/state/openclaw/mark42/config.json` |
| 状态目录 | `~/.local/state/openclaw/mark42/` |

### 1.2 用户和场景

- **点点**（袁文涛，1991-11-29）：OpenClaw 的 owner，让 AI 助手帮他维护自己的 AI 系统
- **场景**：Mark42 是一个"内部项目"——不是产品，是点点自己用的工具
- **约束**：没有团队、没有 deadline、但点点对**稳定性要求极高**（"系统稳定运行"是第一原则）
- **决策模式**：点点偏"放权"（"不用等我拍板，继续做"），但对**关键改动会反复确认**

### 1.3 压缩子系统是什么

**一句话**：在 OpenClaw 自己的 `preflightCompaction` **之前**，先用借鉴 Headroom 的算法**预处理内容**。

```
[LLM 调用]  ← OpenClaw 自己在管
   ↑
[preflightCompaction]  ← OpenClaw 自带，自动按 token 触发
   ↑
[Mark42 内容层压缩]  ← 这是我们做的，今天的成果
   ↑
[内容来源] 工具调用输出 / 日志 / 代码 / RAG 检索片段
```

**为什么要在 OpenClaw 自己压缩之前再压一次？**

| 维度 | OpenClaw 自带压缩 | Mark42 内容层压缩 |
|---|---|---|
| 触发时机 | 文件 size 接近上限 | **在写文件之前**（pre-write hook）|
| 压缩方式 | LLM 摘要（保留语义）| 结构性压缩（数组截断、字符串截断、去重）|
| 丢失信息 | 摘要后的细节 | 仅冗余数据，**可逆**（保留 original 在 metadata）|
| 适合场景 | 长对话历史 | **大工具输出**（grep 结果 / API 响应 / 测试日志）|

**互补关系**：Mark42 减体积 → OpenClaw 摘要更快 → 总体 token 节省更多。

---

## 二、目录结构与关键文件（必读）

```
~/.openclaw/workspace/
├── scripts/
│   ├── mark42.py                          # CLI 入口（v2.3.0）
│   ├── mark42-tests.py                    # 主烟测脚本（27 项测试）
│   └── mark42_modules/
│       ├── __init__.py
│       ├── config.py                      # ★ 所有 ALGO_* 常量在这里
│       ├── armor.py                       # ★ 上下文铠甲主逻辑（含 pre_compact_hook）
│       ├── utils.py                       # 工具函数（_find_active_session 等）
│       ├── compression_algorithms.py      # ★ Day 1: SmartCrusher（已实现）
│       ├── algo_scheduler.py              # ★ Day 3: 算法调度器（已实现）
│       ├── pii_redactor.py                # ★ Day 2: PII 脱敏（已实现）
│       ├── session_fence_safe.py          # ★ Day 1: Session fence 安全工具
│       ├── test_session_fence.py          #   fence 专项测试
│       ├── test_day4_integration.py       #   Day 4 集成测试（7 个场景）
│       ├── engine.py                      # 循环引擎（5 个 Loop 在跑）
│       ├── heavy.py                       # 重型战甲
│       ├── compaction_diag.py             # 压缩诊断 v2.0
│       ├── logs.py                        # 日志管理
│       └── cli.py                         # CLI 子命令
├── docs/design/
│   ├── mark42-压缩方案借鉴Headroom-20260624.md     # 整体设计（Day 0）
│   ├── mark42-压缩方案-阶段1实施计划-20260624.md   # Day 1-4 实施计划
│   ├── mark42-开发手册-压缩子系统.md               # ★ 本文件
│   ├── mark42-更新日志.md                           # 每次改动都要追加
│   ├── mark42-开发经验.md                           # 20 个 bug 的根因总结（必读）
│   └── mark42-架构设计.md
├── memory/daily/                          # 每日聊天记录
└── .local/state/openclaw/mark42/          # 运行时状态
    ├── config.json
    ├── armor/actions.jsonl
    ├── armor/algo_history/
    └── ...

~/.local/state/openclaw/mark42/
└── config.json                            # 运行时配置（阈值、算法开关）
```

---

## 三、阶段 1 现状：Day 1-4 已完成 ✅

### 3.1 每日交付清单

| Day | 日期 | 交付物 | 关键文件 | 测试 |
|---|---|---|---|---|
| Day 1 | 06-24 上午 | SmartCrusher JSON 压缩 | `compression_algorithms.py` | 单元测试 |
| Day 1 | 06-24 下午 | Session Fence 修复（13:49 故障 → 14:30 修复）| `session_fence_safe.py` + armor.py 改 | `test_session_fence.py` 4 项 |
| Day 2 | 06-24 下午 | PII 脱敏（13 种）| `pii_redactor.py` | 13 个用例 |
| Day 3 | 06-24 下午 | 算法调度器（大小分层 + 护栏）| `algo_scheduler.py` | 10 个用例 |
| Day 4 | 06-24 下午 | 调度器接入 armor 主流程 | `armor.py`（_hook_via_scheduler）+ `test_day4_integration.py` | 7 个集成场景 |

**烟测结果**：`python3 scripts/mark42-tests.py` → **27/27 全绿** ✅

### 3.2 关键代码改动一览（接手前必看）

#### `armor.py` 的双路径架构
```python
def armor_pre_compact_hook(session_messages, dry_run=False):
    """压缩前 hook — Day 4 重构后"""
    
    # 双重门
    if not _COMPRESSION_AVAILABLE: return stats
    if not ALGO_SMARTCRUSH_ENABLED: return stats
    if not ALGO_EXPERIMENT_MODE: return stats
    
    # Day 4 路径选择
    if ALGO_USE_SCHEDULER and _SCHEDULER_AVAILABLE:
        return _hook_via_scheduler(...)    # 新路径（默认）
    else:
        return _hook_direct_smartcrush(...) # 旧路径（MARK42_ALGO_USE_SCHEDULER=false）
```

#### `algo_scheduler.py` 的核心决策
```python
def decide(content, config=None) -> ScheduleDecision:
    size = len(content.encode('utf-8'))
    if size < 1024: return skip          # tiny
    if size <= 10KB: return compress     # small (JSON only)
    if size <= 100KB: return compress+pii  # medium
    return review                        # large > 100KB

def process(content, config=None) -> dict:
    """按决策执行: PII → 压缩 → 护栏验证 → fail-safe"""
```

#### `config.py` 的开关
```python
ALGO_USE_SCHEDULER = os.environ.get("MARK42_ALGO_USE_SCHEDULER", "true").lower() == "true"
ALGO_PII_ENABLED   = os.environ.get("MARK42_ALGO_PII", "true").lower() == "true"
ALGO_FAIL_SAFE     = os.environ.get("MARK42_ALGO_FAIL_SAFE", "true").lower() == "true"
```

### 3.3 Day 1-4 踩过的坑（必看！）

| 坑 | 症状 | 教训 |
|---|---|---|
| Session fence | 直接 `open(session, "a")` 写 → EmbeddedAttemptSessionTakeoverError | **绝对禁止**直接写 active session |
| Import 找不到模块 | `python3 -m mark42_modules.X` 失败 | mark42_tests.py 改用**绝对路径**调用 |
| from .relative vs absolute | 直接 `python3 algo_scheduler.py` 报 ImportError | 顶部加 `sys.path.insert(0, str(_THIS_DIR))` |
| 配置改了不生效 | 改了 `cfg.ALGO_X` 但 armor 已 import | armor 用 `from .config import ALGO_X` **拷贝到模块顶部**，要 patch 的是 armor 模块不是 config |
| 测试和真实行为不一致 | 以为"session 没变"，结果它在自己变 | OpenClaw 主会话在持续写入，断言不能比对"绝对值" |

---

## 四、方向 A：5 个 Headroom 算法的详细设计

### 4.1 背景：Headroom 真实算法是什么

**关键事实**（2026-06-24 联网核实）：

| 维度 | 真相 |
|---|---|
| Headroom 是什么 | Proxy + Library，不是 Python 包 |
| 6 个算法 | JSON / Code / Logs / Diffs / Text / ML Router |
| 能否 pip install | `pip install "headroom-ai[all]"` 但依赖重（tree-sitter 编译 + HuggingFace 模型）|
| 能否离线跑 | **部分能**：JSON compressor 纯 Python；Code 需要 tree-sitter；Text 需要 HF 模型 |
| Mark42 策略 | **借鉴算法思路，纯 Python 实现，不引依赖** |

**为什么不用 Headroom 的 `[all]` 包？**

1. tree-sitter 编译依赖重（需要 C 编译器 + 头文件）
2. Kompress-base 需要下载 100MB+ HuggingFace 模型
3. CacheAligner / CCR 依赖 Anthropic 提示缓存（仅 Anthropic 支持）
4. Mark42 是本地工具，不应该有外部依赖

**所以策略是**：每个算法用**纯 Python 实现**，接口对齐 Headroom 思路，但不依赖任何外部包。

### 4.2 算法 1：SmartCrusher（已完成 ✅）

| 维度 | 内容 |
|---|---|
| 状态 | **Day 1 已实现** |
| 文件 | `scripts/mark42_modules/compression_algorithms.py` |
| 输入 | JSON 字符串 |
| 策略 | 数组截断 + 字符串截断 + 嵌套展开 + 数值数组稀疏化 |
| 压缩率 | 60-90% |
| 接口 | `smartcrush(content: str) -> tuple[str, dict]` |
| 测试 | `compression_algorithms.py` 内置 `_run_tests()` |

**关键实现细节**（不要重写，直接复用）：
- 递归深度限制 `max_depth=3`
- 数组截断保留前 `max_array_len=5` 个元素
- 字符串截断保留前 `max_string_len=200` 个字符
- 数值数组用 min/max/count 代替原始值
- 混合内容（非纯 JSON）走正则 fallback

### 4.3 算法 2：LogDeduplicator（待实现）

**设计目标**：压缩 bash/docker/pytest 日志，预期 80-95% 压缩率。

**Headroom 真实做法**：
1. 检测 log 风格（每行以时间戳或 DEBUG/INFO/ERROR 开头）
2. 行级 dedup：相同行合并为 `重复 N 次`
3. 保留最后 50 行原文（失败时 debug 用）
4. 提取关键事件（ERROR/FATAL/Exception）原样保留

**Mark42 实现方案**：

```python
# 新文件: scripts/mark42_modules/log_deduplicator.py

import re
from collections import Counter, OrderedDict
from typing import Any

class LogDeduplicator:
    """日志去重压缩器"""
    
    LOG_PATTERN = re.compile(
        r'^\s*(?:\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\.|'    # 时间戳
        r'\[(?:DEBUG|INFO|WARN|ERROR|FATAL|WARNING|CRITICAL)\]\s+'  # 级别
        r')'
    )
    
    def __init__(self,
                 keep_tail_lines: int = 50,      # 保留最后 N 行原文
                 dedup_min_repeat: int = 3,       # 重复 >= N 次才合并
                 max_unique_lines: int = 1000):   # 最多保留 N 个唯一行
        self.keep_tail_lines = keep_tail_lines
        self.dedup_min_repeat = dedup_min_repeat
        self.max_unique_lines = max_unique_lines
    
    def dedup(self, content: str) -> tuple[str, dict]:
        """
        Args:
            content: 原始日志文本
        
        Returns:
            (压缩后文本, 统计信息)
            统计信息: {
                "original_lines": int,
                "unique_lines": int,
                "merged_lines": int,
                "repeated_groups": int,
                "kept_tail_lines": int,
                "critical_events": list[str],  # 保留的关键事件
            }
        """
    
    def _classify_line(self, line: str) -> str:
        """分类一行日志"""
        # 返回: "critical" / "debug" / "info" / "other"
        ...
    
    def _extract_critical_events(self, lines: list[str]) -> list[str]:
        """提取 ERROR/FATAL/Exception 行"""
        ...
    
    def _deduplicate(self, lines: list[str]) -> tuple[list[str], dict]:
        """核心去重逻辑"""
        # 1. 分离 tail lines（最后 N 行）
        # 2. 对前面的行做 Counter 统计
        # 3. 重复 >= dedup_min_repeat 的行合并
        # 4. 保留 max_unique_lines 个唯一行
        ...
```

**实现步骤**：
1. 创建 `log_deduplicator.py`（预计 200 行）
2. 写 `_run_tests()`：至少 8 个用例
3. 在 `algo_scheduler.py` 的 `PII_PATTERNS` 旁加 `LOG_DEDUP_ENABLED` 开关
4. 在 `algo_scheduler.decide()` 中加 log 类型检测
5. 集成到 `test_day4_integration.py`

**关键测试用例**：
```python
# 1. 纯日志去重
inp = "INFO: loading module\n" * 100 + "ERROR: crash\n" * 50
out, stats = dedup(inp)
assert stats["repeated_groups"] == 2  # 2 组重复
assert stats["original_lines"] == 150
assert stats["unique_lines"] < 10  # 只剩 2 个唯一行 + 计数

# 2. 保留 tail 50 行
inp = "line\n" * 200 + "last line\n" * 60
out, stats = dedup(inp)
assert stats["kept_tail_lines"] == 60  # 最后 60 行全保留

# 3. 保留 critical events
inp = "DEBUG: x\n" * 100 + "ERROR: crash\n" + "FATAL: oops\n"
out, stats = dedup(inp)
assert "ERROR: crash" in stats["critical_events"]
assert "FATAL: oops" in stats["critical_events"]

# 4. 非日志文本不处理
inp = "hello world this is not a log"
out, stats = dedup(inp)
assert out == inp  # 原文返回
```

**复杂度**：O(n) 时间（一次遍历），O(u) 空间（u = 唯一行数）

---

### 4.4 算法 3：CodeCompressor（待实现）

**设计目标**：对源代码做 AST 级 token 化压缩，预期 70-85%。

**Headroom 真实做法**：
1. 用 tree-sitter 解析源代码为 AST
2. 移除注释、空白、格式化
3. 保留函数签名 + 关键逻辑
4. 用 token 序列代替源码文本

**Mark42 实现方案**（简化版，不依赖 tree-sitter）：

```python
# 新文件: scripts/mark42_modules/code_compressor.py

import re
from typing import Any

class CodeCompressor:
    """
    代码压缩器（简化版，不依赖 tree-sitter）
    
    策略：
    1. 移除注释（单行/多行）
    2. 移除空白（多余空格/空行）
    3. 移除格式化字符串（保留模板）
    4. 合并连续语句
    5. 保留函数签名和关键逻辑结构
    """
    
    def __init__(self,
                 language: str = "python",       # python / js / sh
                 preserve_functions: bool = True, # 保留函数签名
                 max_stmts_per_func: int = 20,   # 每函数最多保留 N 条语句
                 remove_comments: bool = True,   # 移除注释
                 remove_docstrings: bool = True, # 移除 docstring
                 ):
        ...
    
    def compress(self, code: str) -> tuple[str, dict]:
        """
        Args:
            code: 源代码字符串
        
        Returns:
            (压缩后代码, 统计信息)
        """
        ...
```

**关键约束**：
- **不依赖 tree-sitter**（编译太重）
- 用正则 + 语法分析做简化版
- Python 代码：用 `ast` 模块（stdlib）
- JS/shell 代码：用正则（不完美但够用）

**实现步骤**：
1. 创建 `code_compressor.py`（预计 250 行）
2. Python 代码：用 `ast.parse()` + `ast.unparse()` 做 AST 级处理
3. 其他语言：用正则 fallback
4. 集成到 `algo_scheduler.py`（按文件扩展名路由）
5. 写测试（至少 6 个用例）

**关键测试用例**：
```python
# 1. Python 函数压缩
inp = '''
def foo():
    """这是一个很长的文档字符串"""
    x = 1  # 注释
    y = 2
    return x + y
'''
out, stats = compress(inp)
assert "def foo" in out  # 保留签名
assert "文档字符串" not in out  # 移除 docstring
assert "注释" not in out  # 移除注释

# 2. 大函数截断
inp = "def big():\n    x = {}\n".format({i: i for i in range(100)}) + "    return x"
out, stats = compress(inp)
assert stats["statements_truncated"] > 0
```

**复杂度**：Python 代码 O(n)（ast 遍历）；其他语言 O(n)（正则）

---

### 4.5 算法 4：DiffCompressor（待实现）

**设计目标**：对 git diff 做结构化压缩，保留 hunks + 行号，预期 90% 压缩率。

**Headroom 真实做法**：
1. 解析 diff 格式（@@ -N,M +N,M @@）
2. 保留 hunk headers
3. 对连续相同行（context lines）做游程编码
4. 对删除行做差异压缩（保留共同前缀）

**Mark42 实现方案**：

```python
# 新文件: scripts/mark42_modules/diff_compressor.py

class DiffCompressor:
    """
    git diff 压缩器
    
    策略：
    1. 保留 @@ hunk headers（行号信息很重要）
    2. 连续 context lines 做游程编码（-5 lines → "-5L"）
    3. 连续删除行标记（-20 deletions）
    4. 连续添加行标记（+30 insertions）
    5. 保留差异行（+/- 开头的行）不压缩
    """
    
    def compress(self, diff_text: str) -> tuple[str, dict]:
        """
        Args:
            diff_text: git diff 输出
        
        Returns:
            (压缩后 diff, 统计信息)
        """
        ...
```

**关键测试用例**：
```python
# 1. 游程编码
inp = "@@ -1,5 +1,5 @@\n line1\n line2\n line3\n line4\n line5\n-removed\n+added\n"
out, stats = compress(inp)
assert "5L" in out  # 5 context lines encoded
assert stats["context_lines_merged"] == 5

# 2. 保留 hunk headers
assert "@@" in out  # hunk headers 必须保留
```

---

### 4.6 算法 5：TextCompressor（待实现）

**设计目标**：通用文本语义压缩，预期 50-80%。

**Headroom 真实做法**：
- 用 Kompress-v2-base（HuggingFace 模型）
- 基于 Encoder-Decoder 架构
- 需要 GPU 推理

**Mark42 实现方案**（轻量版）：

```python
# 新文件: scripts/mark42_modules/text_compressor.py

class TextCompressor:
    """
    通用文本压缩器（轻量版）
    
    策略：
    1. 同义词替换（小型词典）
    2. 句式压缩（被动→主动，长句→短句）
    3. 冗余信息移除（重复表述）
    4. 可选：接入外部 LLM 做语义压缩
    """
    
    def __init__(self,
                 method: str = "rule_based",  # rule_based | llm
                 synonym_file: str | None = None,  # 同义词词典路径
                 ):
        ...
    
    def compress(self, text: str) -> tuple[str, dict]:
        """
        Args:
            text: 通用文本
        
        Returns:
            (压缩后文本, 统计信息)
        """
        if method == "rule_based":
            return self._rule_compress(text)
        elif method == "llm":
            return self._llm_compress(text)
```

**关键约束**：
- **默认 rule_based**（不需要外部依赖）
- **可选 llm 模式**：调用 OpenClaw 已有的 LLM（LiteLLM）
- 两种模式都要有测试覆盖

---

### 4.7 算法调度器增强（Day 4 改进）

当前 `algo_scheduler.py` 已经做了**大小分层**，但还需要加**内容类型检测**：

```python
def detect_content_type(content: str) -> str:
    """检测内容类型，返回类型标签"""
    # 1. 尝试 JSON 解析 → "json"
    # 2. 检测 diff 格式（@@ ... @@） → "diff"
    # 3. 检测日志格式（时间戳/级别前缀） → "log"
    # 4. 检测代码格式（import/def/class/function/const） → "code"
    # 5. 默认 → "text"
    ...
```

**路由表**（更新 `algo_scheduler.py`）：

| 内容类型 | 算法 | 条件 |
|---|---|---|
| json | SmartCrusher | 当前已实现 ✅ |
| log | LogDeduplicator | Day 5 实现 |
| code | CodeCompressor | Day 5 实现 |
| diff | DiffCompressor | Day 5 实现 |
| text | TextCompressor | Day 5 实现 |
| mixed | SmartCrusher fallback | 混合内容 fallback |

---

## 五、Day 5：异步化改造

### 5.1 问题描述

**当前**：`armor_compress` 在 daemon 循环中调用 `armor_pre_compact_hook`，hook 内部调 `algo_scheduler.process()`，后者可能调 LLM 做语义压缩（未来扩展时）。

**问题**：
- 同步阻塞：LLM 调用 30-60 秒，期间 daemon 卡住
- 如果 LLM 超时或失败，整个 daemon tick 失败
- 用户体验：Mark42 守护进程偶尔"无响应"

**目标**：
- 压缩请求入队 → 后台 worker 处理 → 完成后写入结果
- daemon tick 立即返回，不阻塞
- worker 失败不传播到 daemon

### 5.2 架构设计

```
[armor tick]
    │
    ▼
[enqueue_compress_request()]  ← 非阻塞，立即返回
    │
    ▼
[asyncio.Queue]
    │
    ▼
[worker coroutine]
    ├── dequeue()
    ├── detect_content_type()
    ├── select_algorithm()
    ├── compress()
    ├── write_result()
    └── update_stats()
```

### 5.3 实现步骤

**Step 1：创建 `compress_queue.py`**
```python
# 新文件: scripts/mark42_modules/compress_queue.py

import asyncio
from dataclasses import dataclass, field
from typing import Any

@dataclass
class CompressRequest:
    session_id: str
    content: str
    content_type: str  # auto-detected
    priority: int = 0  # 0=normal, 1=urgent, 2=low
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())

class CompressQueue:
    """异步压缩队列"""
    
    def __init__(self, max_workers: int = 2, max_queue_size: int = 100):
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.workers = []
        self._running = False
    
    async def enqueue(self, request: CompressRequest) -> bool:
        """非阻塞入队"""
        try:
            self.queue.put_nowait(request)
            return True
        except asyncio.QueueFull:
            # 队列满 → 丢弃最低优先级
            ...
            return False
    
    async def start_workers(self):
        """启动 worker 协程"""
        self._running = True
        for _ in range(self.max_workers):
            w = asyncio.create_task(self._worker_loop())
            self.workers.append(w)
    
    async def _worker_loop(self):
        """worker 主循环"""
        while self._running:
            try:
                req = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                result = await self._process(req)
                self._write_result(req, result)
            except asyncio.TimeoutError:
                continue  # 等 5 秒，没任务就继续循环
            except Exception as e:
                self._log_error(req, e)
    
    async def _process(self, req: CompressRequest) -> dict:
        """处理单个压缩请求"""
        # 1. detect_content_type (同步，快)
        # 2. select_algorithm (同步，快)
        # 3. compress (可能慢：LLM 调用)
        # 4. validate (同步，快)
        ...
```

**Step 2：修改 `armor.py`**
```python
# 在 armor.py 中
from .compress_queue import CompressQueue, CompressRequest

# 全局单例
_compress_queue: CompressQueue | None = None

def get_compress_queue() -> CompressQueue:
    global _compress_queue
    if _compress_queue is None:
        _compress_queue = CompressQueue()
    return _compress_queue

async def armor_compress_async(dry_run: bool = False) -> dict:
    """异步版 armor_compress"""
    queue = get_compress_queue()
    content = _read_session_tail()  # 同步，快
    
    req = CompressRequest(
        session_id=_find_active_session().name,
        content=content,
        content_type="auto",
        priority=1 if len(content) > 50000 else 0,
    )
    
    enqueued = await queue.enqueue(req)
    if enqueued:
        return {"status": "queued", "request": req}
    else:
        return {"status": "dropped", "reason": "queue_full"}
```

**Step 3：修改 daemon 循环**
```python
# 在 engine.py 或 daemon 中
async def tick():
    # 原来: result = armor_compress(dry_run=False)
    # 现在: result = await armor_compress_async(dry_run=False)
    ...
```

### 5.4 风险点

| 风险 | 影响 | 缓解 |
|---|---|---|
| worker 崩溃 | 队列积压 | worker 异常捕获 + 重试 + 告警 |
| 队列满 | 请求丢弃 | 优先级队列 + 低优先级丢弃 |
| 结果写回冲突 | 多个 worker 同时写 | 单写者 + 锁 |
| 内存泄漏 | 大内容堆积 | 队列大小限制 + 内存监控 |

### 5.5 测试

```python
# scripts/mark42_modules/test_compress_queue.py

async def test_basic_enqueue_dequeue():
    q = CompressQueue(max_workers=1)
    req = CompressRequest(session_id="test", content="hello")
    assert await q.enqueue(req) is True
    # 验证队列中有 1 个 item
    ...

async def test_worker_processes():
    q = CompressQueue(max_workers=1)
    await q.start_workers()
    req = CompressRequest(session_id="test", content=json.dumps({"x": "y" * 1000}))
    await q.enqueue(req)
    await asyncio.sleep(1)  # 等 worker 处理
    # 验证结果已写入
    ...

async def test_queue_overflow():
    q = CompressQueue(max_queue_size=5)
    for i in range(10):
        req = CompressRequest(session_id="test", content=f"x" * 100)
        assert await q.enqueue(req) == (i < 5)  # 前 5 个成功，后 5 个丢弃
    ...
```

---

## 六、交接清单（接手者必读）

### 6.1 必须读的文件（按顺序）

1. `docs/design/mark42-开发手册-压缩子系统.md` ← 你正在读的
2. `docs/design/mark42-开发经验.md` ← 20 个 bug 的根因
3. `docs/design/mark42-更新日志.md` ← 最新改动记录
4. `docs/design/mark42-压缩方案借鉴Headroom-20260624.md` ← 整体设计
5. `docs/design/mark42-压缩方案-阶段1实施计划-20260624.md` ← Day 1-4 实施计划

### 6.2 必须跑的命令

```bash
# 1. 主烟测（确认所有模块正常）
cd ~/.openclaw/workspace
python3 scripts/mark42-tests.py

# 2. 压缩算法专项
cd scripts
python3 mark42_modules/compression_algorithms.py

# 3. PII 脱敏专项
python3 mark42_modules/pii_redactor.py

# 4. 算法调度器专项
python3 mark42_modules/algo_scheduler.py

# 5. Session Fence 专项
python3 mark42_modules/test_session_fence.py

# 6. Day 4 集成测试（需要环境变量）
MARK42_ALGO_SMARTCRUSH=true MARK42_ALGO_EXPERIMENT=true \
  python3 mark42_modules/test_day4_integration.py

# 7. 查看 Mark42 状态
python3 scripts/mark42.py status --json

# 8. 查看 CLI 帮助
python3 scripts/mark42.py --help
```

### 6.3 关键路径

| 什么 | 路径 |
|---|---|
| CLI 入口 | `~/.openclaw/workspace/scripts/mark42.py` |
| 主模块目录 | `~/.openclaw/workspace/scripts/mark42_modules/` |
| 配置文件 | `~/.local/state/openclaw/mark42/config.json` |
| 运行时状态 | `~/.local/state/openclaw/mark42/` |
| 日志 | `~/.local/state/openclaw/mark42/armor/actions.jsonl` |
| 设计文档 | `~/.openclaw/workspace/docs/design/mark42-*` |
| 更新日志 | `~/.openclaw/workspace/docs/design/mark42-更新日志.md` |
| 开发经验 | `~/.openclaw/workspace/docs/design/mark42-开发经验.md` |
| 每日记录 | `~/.openclaw/workspace/memory/daily/` |

### 6.4 关键常量（config.py）

```python
# 在 scripts/mark42_modules/config.py 中

# 压缩算法开关
ALGO_SMARTCRUSH_ENABLED = ...      # 默认 false，需 env MARK42_ALGO_SMARTCRUSH=true
ALGO_EXPERIMENT_MODE = ...         # 默认 false，需 env MARK42_ALGO_EXPERIMENT=true
ALGO_USE_SCHEDULER = ...           # 默认 true（Day 4 新增）
ALGO_PII_ENABLED = ...             # 默认 true（Day 4 新增）
ALGO_FAIL_SAFE = ...               # 默认 true（Day 4 新增）

# SmartCrusher 参数
ALGO_SMARTCRUSH_MAX_ARRAY_LEN = 5
ALGO_SMARTCRUSH_MAX_STRING_LEN = 200
ALGO_SMARTCRUSH_MAX_DEPTH = 3
ALGO_SMARTCRUSH_MIN_CONTENT_SIZE = 1024

# 阈值
THRESHOLD_WARN = 0.60              # 60% → 提示
THRESHOLD_ALERT = 0.80             # 80% → 建议压缩
THRESHOLD_CRIT = 0.95              # 95% → 强制压缩
```

### 6.5 已知限制

| 限制 | 说明 | 解决 |
|---|---|---|
| 只有 SmartCrusher 已实现 | 其余 5 个算法待 Day 5+ 实现 | 按计划推进 |
| 同步压缩 | armor_compress 是同步的，可能阻塞 daemon tick | Day 5 异步化 |
| 无 Web UI | 所有状态都是 CLI + JSON | 可选，非阻塞 |
| 无断点续跑 | heavy 大工程中途崩了要重来 | 可选，非阻塞 |
| 单节点 | 没有多机协同 | 可选，非阻塞 |

### 6.6 下一步建议

按优先级排列：

1. **Day 5-A：异步化**（compress_queue.py）← 解决阻塞问题
2. **Day 5-B：LogDeduplicator**（log_deduplicator.py）← 压缩率最高（80-95%）
3. **Day 5-C：CodeCompressor**（code_compressor.py）← 代码场景常用
4. **Day 5-D：DiffCompressor**（diff_compressor.py）← git diff 场景
5. **Day 5-E：TextCompressor**（text_compressor.py）← 通用文本
6. **Day 5-F：增强 algo_scheduler 路由** ← 自动检测内容类型 + 选算法

**建议顺序**：先异步化（Day 5-A），再逐个算法（5-B ~ 5-F）。
原因：异步化后，每个算法的 LLM 调用不会阻塞 daemon，体验更好。

---

## 七、常见问题 FAQ

### Q1: 为什么不用 Headroom 的 pip 包？

A: 见 4.1 节。核心原因是：
- tree-sitter 编译依赖重
- HuggingFace 模型 100MB+
- Mark42 是本地工具，不该有外部依赖
- 算法思路可以借鉴，实现可以用纯 Python

### Q2: 为什么不用 OpenClaw 自带的压缩？

A: OpenClaw 的 `preflightCompaction` 是**事后兜底**（文件大了才压）。
Mark42 做的是**事前预处理**（在内容写入之前先瘦身）。两者互补。

### Q3: 改了压缩算法会不会影响 LLM 回答质量？

A: 会，但通过以下机制控制：
1. `ALGO_EXPERIMENT_MODE` 默认 false（不启用）
2. `ALGO_FAIL_SAFE` 默认 true（出错回退原文）
3. 压缩率 < 10% 自动回退
4. 压缩后 > 原文 80% 自动回退
5. 所有压缩都保留 `original_size` 在 metadata（可逆）

### Q4: 怎么回退到 Day 1 的状态？

A: 
```bash
cd ~/.openclaw/workspace
git revert b6412f6  # session fence 修复
git revert c32e6c0  # Day 4 集成
```

### Q5: 怎么测试一个新实现的算法？

A:
```bash
# 1. 写单元测试（在算法文件内 _run_tests()）
# 2. 跑专项测试
python3 scripts/mark42_modules/log_deduplicator.py
# 3. 跑集成测试（确保 algo_scheduler 能路由到新算法）
MARK42_ALGO_SMARTCRUSH=true MARK42_ALGO_EXPERIMENT=true \
  python3 scripts/mark42_modules/test_day4_integration.py
# 4. 跑完整烟测
python3 scripts/mark42-tests.py
```

---

## 八、变更记录

| 日期 | 作者 | 变更 |
|---|---|---|
| 2026-06-24 16:11 | 贾维斯 | 创建本手册，包含方向 A（5 算法）+ Day 5（异步化）详细设计 |
| 2026-06-24 15:30 | 贾维斯 | Day 4 完成：algo_scheduler 接入 armor |
| 2026-06-24 14:30 | 贾维斯 | Session fence 修复完成 |
| 2026-06-24 13:43 | 贾维斯 | Day 1 SmartCrusher 落地 |
| 2026-06-24 12:30 | 贾维斯 | 借鉴 Headroom 开始设计 |

---

*本手册由 Mark42 v2.3 压缩子系统维护。*
*最后更新：2026-06-24 16:11*
