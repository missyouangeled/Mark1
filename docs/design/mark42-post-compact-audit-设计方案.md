# Post-Compact Audit：压缩后自动核对机制

> 设计日期：2026-07-29
> 状态：**📝 设计方案（待审核）**
> 设计者：贾维斯
> 审核人：点点

---

## 一、问题背景

### 1.1 点点的担忧

> "compact 后发现上下文丢失"

OpenClaw auto-compaction 会把长对话摘要成短文本，但摘要过程由平台 LLM 执行，Mark42 无法控制摘要质量。如果摘要丢失了关键信息（用户偏好、项目状态、重要决策），用户可能不知道，直到后续对话出现断裂才发现。

### 1.2 现有安全网

| 层 | 机制 | 状态 |
|---|---|---|
| 数据盘快照 | 每 30 分钟备份 context-summary + transcript | ✅ 已有 |
| compact 文件锁 | 防止多个 compact 同时跑 | ✅ 已有 |
| Session Fence | 记录 compact 前后文件状态 | ✅ 已有 |
| memory-index.json | 记录每次 compact 的 before/after | ✅ 已有 |
| **compact 后核对** | **对比 compact 前快照与 compact 后摘要** | **❌ 缺失** |

### 1.3 点点的想法

> "给 Mark42 加一个核对机制，咱不是把 7 天内对话数据完整保存在数据盘了么，
> 自动压缩以后，Mark42 读取保存的对话内容，然后自动核对，给出一个是否丢失的回答"

---

## 二、设计目标

### 2.1 核心目标

compact 完成后，自动对比 **compact 前的完整上下文快照** 与 **compact 后的 compaction 摘要**，
判断关键信息是否丢失，输出核对报告。

### 2.2 设计约束（点点要求）

1. **跨平台兼容** -- 不写死 OpenClaw，以后换到别的平台也能用
2. **极低耦合** -- 遵循 Mark42 ArcLock 设计理念，独立模块 + 接口契约
3. **不阻塞** -- 核对在 compact 完成后异步执行，不影响 compact 流程

### 2.3 核心设计原则

> **平台负责 compact，Mark42 负责审计**

平台（OpenClaw / Headroom / 其他）执行 compact 并生成摘要。
Mark42 只做"事后审计"：拿 compact 前的快照和 compact 后的摘要对比，判断是否丢失。
Mark42 不参与 compact 过程本身，只读不写。

---

## 三、架构设计

### 3.1 在 ArcLock 体系中的位置

```
ArcLock 接口层
├── CompressLock        (压缩：armor / Headroom / ...)
├── MemoryLock          (记忆：向量搜索 / 关键词)
├── ConsciousnessLock   (意识：自愈 / 降级)
├── ...
└── AuditLock  ← 新增   (审计：compact 后核对)
```

新增一个 **AuditLock** 接口契约，与 CompressLock 平级。
不修改 CompressLock 接口，不修改 armor_compress 函数。

### 3.2 模块结构

```
mark42_modules/
├── interfaces/
│   ├── audit.py          ← 新增：AuditLock Protocol
│   └── __init__.py        (注册器加 "audit" 条目)
├── plugins/
│   └── builtin_audit.py   ← 新增：默认实现（用 LLM 对比）
├── audit/
│   ├── __init__.py
│   ├── snapshot_reader.py ← 快照读取器（数据盘 / 本地 / 远程）
│   ├── summary_extractor.py ← 摘要提取器（从 session 读 compaction 条目）
│   ├── checker.py          ← 核对引擎（LLM 判断 / 规则判断）
│   └── report.py           ← 报告生成器
└── armor.py               (compact 后 hook 调 audit，不改 armor 逻辑)
```

### 3.3 接口契约

```python
# interfaces/audit.py

@runtime_checkable
class AuditLock(Protocol):
    """压缩后审计锁扣。

    实现方可以是 Mark42 内置 LLM 审计、规则审计、或第三方审计方案。
    """

    def audit_compact(
        self,
        pre_compact_snapshot: SnapshotRef,
        post_compact_summary: SummaryRef,
        **kwargs: Any,
    ) -> AuditResult:
        """对比 compact 前快照与 compact 后摘要，返回核对报告。

        Args:
            pre_compact_snapshot: compact 前的上下文快照引用
            post_compact_summary: compact 后的摘要引用
            **kwargs: 扩展参数（如指定关注重点）

        Returns:
            AuditResult: 核对结果
        """
        ...
```

### 3.4 数据模型

```python
# audit/__init__.py

@dataclass
class SnapshotRef:
    """compact 前快照引用 -- 抽象的快照定位器，不绑定具体存储。"""
    source: str          # "data-disk" | "local" | "remote" | "custom"
    path: str            # 快照路径 / URL / 标识符
    timestamp: str       # ISO-8601 快照时间
    metadata: dict       # 平台特定的元数据（如 session_id, model 等）


@dataclass
class SummaryRef:
    """compact 后摘要引用 -- 抽象的摘要定位器。"""
    source: str          # "openclaw-session" | "headroom-api" | "custom"
    path: str            # 摘要路径 / API 端点 / 标识符
    timestamp: str       # compact 完成时间
    metadata: dict       # 平台特定的元数据


@dataclass
class AuditResult:
    """核对结果。"""
    verdict: str         # "pass" | "partial" | "fail"
    score: float         # 0.0 ~ 1.0（保留完整度）
    findings: list[Finding]  # 逐项核对结果
    recommendation: str  # 建议操作
    timestamp: str       # 核对时间

    @dataclass
    class Finding:
        """单项核对。"""
        category: str     # "identity" | "preferences" | "projects" | "decisions" | "recent_topics"
        item: str         # 具体项名称
        status: str       # "preserved" | "lost" | "degraded"
        detail: str       # 说明


@dataclass
class AuditReport:
    """完整审计报告 -- 可序列化写入文件。"""
    result: AuditResult
    pre_snapshot: SnapshotRef
    post_summary: SummaryRef
    report_path: str     # 报告文件路径
```

### 3.5 快照读取器（SnapshotReader）-- 平台解耦的关键

```python
# audit/snapshot_reader.py

class SnapshotReader(Protocol):
    """快照读取器接口 -- 不同平台实现不同。

    OpenClaw 平台：读数据盘 session-backup/
    其他平台：读自己的快照存储
    """

    def find_latest_before(self, timestamp: str) -> SnapshotRef | None:
        """找到指定时间之前最新的快照。"""
        ...

    def extract_key_info(self, snapshot: SnapshotRef) -> dict[str, list[str]]:
        """从快照中提取关键信息。

        返回分类信息：
        {
            "identity": ["用户名", "AI名", ...],
            "preferences": ["规则1", "规则2", ...],
            "projects": ["项目状态1", ...],
            "decisions": ["决策1", ...],
            "recent_topics": ["最近话题1", ...],
        }
        """
        ...
```

**内置实现** `OpenClawSnapshotReader`：
- 从 `/mnt/data/openclaw/session-backup/` 读最新快照
- 解析 `context-summary.md` 提取对话摘要
- 解析 `daily-*-transcript.md` 提取对话原文
- 解析 `MEMORY.md` / `SOUL.md` / `USER.md` 提取身份/偏好/规则

### 3.6 摘要提取器（SummaryExtractor）-- 平台解耦的关键

```python
# audit/summary_extractor.py

class SummaryExtractor(Protocol):
    """摘要提取器接口 -- 不同平台实现不同。

    OpenClaw 平台：从 session SQLite/JSONL 读 compaction 条目
    其他平台：从自己的存储读摘要
    """

    def find_post_compact_summary(self, compact_timestamp: str) -> SummaryRef | None:
        """找到 compact 后的摘要。"""
        ...

    def extract_summary_text(self, summary: SummaryRef) -> str:
        """提取摘要文本。"""
        ...
```

**内置实现** `OpenClawSummaryExtractor`：
- 从 OpenClaw session 存储读 compaction 条目
- 提取 LLM 生成的摘要文本

### 3.7 核对引擎（Checker）-- 可替换的判断逻辑

```python
# audit/checker.py

class Checker(Protocol):
    """核对引擎接口 -- 可用 LLM 或规则引擎实现。"""

    def check(
        self,
        pre_info: dict[str, list[str]],  # 快照提取的关键信息
        post_summary: str,                # compact 后的摘要文本
    ) -> AuditResult:
        """对比关键信息与摘要，返回核对结果。"""
        ...
```

**内置实现 1** `LLMChecker`：
- 用 LLM 逐项核对：从快照提取的关键信息是否在摘要中保留
- 优点：语义理解强，能判断"换个说法但意思保留了"
- 缺点：耗 token

**内置实现 2** `RuleChecker`（fallback）：
- 用关键词匹配 + embedding 相似度
- 优点：快、不耗 token
- 缺点：只能做浅层匹配

### 3.8 调用时机 -- hook 机制

```
armor_compress 完成
    ↓
finally 块释放 compact 锁后
    ↓
触发 post_compact_audit hook（异步，不阻塞）
    ↓
AuditLock.audit_compact(pre_snapshot, post_summary)
    ↓
核对完成 -> 写报告到 armor_state/audit/
    ↓
如果 verdict == "fail" -> 发 broker 告警 + 通知用户
```

**hook 实现**：在 armor.py 的 compact 完成处加一行：

```python
# armor.py compact 完成后
from .interfaces import get_audit
audit = get_audit()
if audit:
    audit.audit_compact_async(pre_snapshot_ref, post_summary_ref)
```

如果 audit 接口未注册（第三方不实现），静默跳过，不影响 compact。

### 3.9 配置

```yaml
# openclaw.json 里 mark42.audit 配置
{
  "mark42": {
    "audit": {
      "enabled": true,              // 默认 true
      "engine": "llm",              // "llm" | "rule" | "both"
      "async": true,                // 异步执行
      "report_dir": "armor/audit",  // 报告目录
      "alert_on_fail": true,        // fail 时告警
      "snapshot_reader": "openclaw", // "openclaw" | "custom"
      "summary_extractor": "openclaw"
    }
  }
}
```

---

## 四、数据流

```
                    ┌─────────────────────────────────┐
                    │       compact 前                 │
                    │  数据盘快照（每30min自动备份）     │
                    │  context-summary.md (32KB)       │
                    │  daily-YYYY-MM-DD-transcript.md  │
                    │  MEMORY.md / SOUL.md / USER.md   │
                    └──────────┬──────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  SnapshotReader      │
                    │  (find_latest_before)│
                    │  (extract_key_info)  │
                    └──────────┬───────────┘
                               │
                               │   pre_info = {
                               │     "identity": [...],
                               │     "preferences": [...],
                               │     "projects": [...],
                               │     "decisions": [...],
                               │     "recent_topics": [...]
                               │   }
                               │
  compact 完成 ──────────────► │
                               │
                    ┌──────────▼───────────┐
                    │  SummaryExtractor    │
                    │  (find_post_compact) │
                    │  (extract_text)      │
                    └──────────┬───────────┘
                               │
                               │   post_summary = "compact 后的摘要文本"
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Checker             │
                    │  (LLM 或 Rule)       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  AuditResult         │
                    │  verdict: pass/fail  │
                    │  score: 0.85         │
                    │  findings: [...]     │
                    │  recommendation     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Report              │
                    │  armor/audit/        │
                    │  audit-YYYYMMDD-HH   │  ──►  fail → broker 告警
                    │  .json               │       + 通知用户
                    └─────────────────────┘
```

---

## 五、核对维度

### 5.1 五大核对类别

| 类别 | 内容 | 数据来源 |
|------|------|----------|
| **身份** | 用户名、AI 名、称呼方式 | SOUL.md / USER.md / MEMORY.md |
| **偏好** | 规则、习惯、禁忌 | MEMORY.md / memory/rules/ |
| **项目** | 当前项目状态、决策、TODO | context-summary.md / daily transcript |
| **决策** | 技术方案、架构决策 | PLANS.md / context-summary.md |
| **近期话题** | 今天/昨天聊了什么 | daily-transcript.md |

### 5.2 判定标准

| 状态 | 含义 | 判定 |
|------|------|------|
| `preserved` | 信息完整保留 | LLM 判断"摘要中明确包含此信息" |
| `degraded` | 信息部分保留 | LLM 判断"摘要中有相关信息但不完整" |
| `lost` | 信息丢失 | LLM 判断"摘要中完全没有此信息" |

### 5.3 verdict 判定

| verdict | 条件 | 处置 |
|---------|------|------|
| `pass` | 所有关键类别 ≥ 80% preserved | 记日志 |
| `partial` | 有类别 < 80% 但无关键项完全丢失 | 记日志 + 低优先级告警 |
| `fail` | 关键项（身份/偏好）完全丢失 | 告警 + 通知用户 |

---

## 六、跨平台兼容设计

### 6.1 适配新平台只需实现两个接口

```python
# 适配 Headroom 平台的示例
class HeadroomSnapshotReader:
    """Headroom 平台的快照读取器。"""
    def find_latest_before(self, timestamp: str) -> SnapshotRef | None:
        # 从 Headroom 的存储读快照
        ...
    def extract_key_info(self, snapshot: SnapshotRef) -> dict[str, list[str]]:
        # 用 Headroom 的格式解析
        ...

class HeadroomSummaryExtractor:
    """Headroom 平台的摘要提取器。"""
    def find_post_compact_summary(self, ts: str) -> SummaryRef | None:
        # 从 Headroom API 读 compact 摘要
        ...
    def extract_summary_text(self, summary: SummaryRef) -> str:
        ...
```

### 6.2 配置切换

```yaml
# arclock 配置文件
arclock:
  audit:
    module: "headroom.audit"
    class: "HeadroomAuditLock"
    config:
      snapshot_reader: "headroom.audit.HeadroomSnapshotReader"
      summary_extractor: "headroom.audit.HeadroomSummaryExtractor"
```

不配就用 Mark42 默认实现（OpenClaw 版）。

### 6.3 不依赖任何平台 API

AuditLock 接口本身只定义输入输出：
- 输入：`SnapshotRef`（抽象快照引用）+ `SummaryRef`（抽象摘要引用）
- 输出：`AuditResult`（核对结果）

不知道也不关心快照从哪来、摘要怎么存的。
平台适配由 `SnapshotReader` 和 `SummaryExtractor` 两个子接口完成。

---

## 七、失败处理与安全网

### 7.1 审计自身失败

| 场景 | 处置 |
|------|------|
| 快照不存在 | 跳过审计，记日志（不告警，因为快照可能因新环境缺失） |
| 摘要提取失败 | 跳过审计，记日志 + 低优先级告警 |
| LLM 调用失败 | 降级到 RuleChecker |
| RuleChecker 也失败 | 跳过审计，告警 |
| 审计超时 | 跳过审计，告警（不影响主流程） |

### 7.2 审计不是安全机制

> **重要**：审计只做"事后检查 + 告警"，不做"事前阻止"。
> compact 的执行不依赖审计结果。
> 审计失败 = 信息可能丢失，但 compact 已经完成了，不能回滚。
> 审计的价值在于：**让用户知道丢了什么，而不是阻止 compact。**

### 7.3 恢复路径

如果审计发现严重丢失，提供恢复建议：
1. 报告中列出丢失项
2. 指向数据盘快照路径（compact 前的完整上下文）
3. 建议 AI 读快照恢复记忆

---

## 八、实现计划

### 阶段 1：骨架（接口 + 默认实现）
- [ ] 新建 `interfaces/audit.py` -- AuditLock Protocol
- [ ] 新建 `plugins/builtin_audit.py` -- 默认实现
- [ ] 新建 `audit/` 目录 -- 4 个子模块
- [ ] `interfaces/__init__.py` 注册 "audit"

### 阶段 2：快照读取器
- [ ] `audit/snapshot_reader.py` -- OpenClawSnapshotReader
- [ ] 从数据盘读快照 + 解析关键信息

### 阶段 3：摘要提取器
- [ ] `audit/summary_extractor.py` -- OpenClawSummaryExtractor
- [ ] 从 session 读 compaction 摘要

### 阶段 4：核对引擎
- [ ] `audit/checker.py` -- LLMChecker + RuleChecker
- [ ] LLM 核对逻辑

### 阶段 5：集成
- [ ] armor.py compact 后 hook 调 audit
- [ ] 报告写入 + 告警
- [ ] CLI: `mark42 audit --last` 查看最近审计报告

### 阶段 6：测试
- [ ] 单测：各子模块
- [ ] 集成测试：compact → audit → 报告
- [ ] 测试：快照缺失 / LLM 失败 / 超时等异常路径

---

## 九、设计哲学总结

> 点点的比喻："就像钢铁侠的战甲，每一块已经做到能独立了，但还要确保能换能随时插上。"

Post-Compact Audit 就是战甲里的"自检系统"：
- 它不参与战斗（不参与 compact）
- 战斗结束后自动运行（compact 完成后异步触发）
- 检查战甲完整性（对比 compact 前后信息）
- 发现损坏就告警（丢失关键信息就通知）
- 损坏件可追溯（指向快照路径恢复）

**ArcLock 适配**：换平台时只需换"自检探头"（SnapshotReader + SummaryExtractor），
"自检大脑"（Checker + Report）平台无关。
