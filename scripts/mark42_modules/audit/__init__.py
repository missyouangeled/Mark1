"""Post-Compact Audit：压缩后自动核对子系统。

架构：
    SnapshotReader    -> 从数据盘读 compact 前快照，提取关键信息
    SummaryExtractor  -> 从 session 读 compact 后摘要
    Checker           -> 对比关键信息与摘要（LLM / Rule）
    Report            -> 生成报告 + 告警

设计原则：
    - 平台负责 compact，Mark42 负责审计
    - 只读不写（不改 compact 结果）
    - 异步执行（不阻塞 compact）
    - 失败安全（审计自身失败不影响主流程）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# ── 数据模型 ──────────────────────────────────────────


@dataclass
class Finding:
    """单项核对结果。"""
    category: str      # identity | preferences | projects | decisions | recent_topics
    item: str          # 具体项名称
    status: str        # preserved | degraded | lost
    detail: str = ""   # 说明


@dataclass
class AuditResult:
    """核对结果。"""
    verdict: str       # pass | partial | fail
    score: float       # 0.0 ~ 1.0
    findings: List[Finding] = field(default_factory=list)
    recommendation: str = ""
    timestamp: str = ""
    error: str = ""    # 审计自身失败时的错误信息


# ── 五大核对类别 ──────────────────────────────────────

AUDIT_CATEGORIES = [
    "identity",        # 用户名、AI名、称呼方式
    "preferences",      # 规则、习惯、禁忌
    "projects",         # 当前项目状态、决策、TODO
    "decisions",        # 技术方案、架构决策
    "recent_topics",    # 今天/昨天聊了什么
]

# verdict 判定阈值
VERDICT_PASS_THRESHOLD = 0.8    # >= 80% preserved -> pass
VERDICT_FAIL_CATEGORIES = {"identity", "preferences"}  # 这些类别全 lost -> fail
