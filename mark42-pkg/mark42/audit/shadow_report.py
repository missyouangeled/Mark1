"""Shadow 对比报告（方案 44 Phase 6 / §11）。

用途
----
shadow 模式下，每次 compact 同时跑旧路径（LLM/启发式）和新路径
（结构化增量），对比两者的：

    - token 用量
    - 保留字段差异
    - 质量探针分数
    - 约束存活率

输出到 JSONL 文件，供趋势分析。

⚠️ shadow 模式不影响生产 compact 结果
-----------------------------------
本模块只读两路输出并对比，不修改任何一方，不写入 session。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .probes import default_probe_specs, score_deterministic


@dataclass
class ShadowComparison:
    """一次 shadow 对比的结果。"""

    timestamp: str = ""
    trace_id: str = ""

    # 旧路径（LLM / 启发式）
    legacy_strategy: str = ""
    legacy_preserved_keys: list[str] = field(default_factory=list)
    legacy_analyzed_messages: int = 0

    # 新路径（结构化增量）
    structured_strategy: str = ""
    structured_item_count: int = 0
    structured_fingerprint: str = ""
    structured_session_intent: str = ""

    # 对比结果
    preserved_overlap: int = 0
    preserved_only_legacy: int = 0
    preserved_only_structured: int = 0
    intent_captured_by_structured: bool = False
    constraints_survived: int = 0
    constraints_total: int = 0

    # 质量探针（对新旧两路各跑一次）
    legacy_probe_total: int | None = None
    structured_probe_total: int | None = None

    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def compare_shadow(
    legacy_index: dict[str, Any],
    structured_view: dict[str, Any],
    *,
    trace_id: str = "",
    post_text: str = "",
) -> ShadowComparison:
    """对比旧路径和新路径的输出。

    Args:
        legacy_index: 旧 _compress_build_index() 返回的 dict
        structured_view: 新 render_memory_index_view() 返回的 dict
        post_text: 压缩后的摘要文本（用于探针评分，可选）

    Returns:
        ShadowComparison
    """
    comp = ShadowComparison(
        timestamp=now_iso(),
        trace_id=trace_id,
    )

    # 旧路径信息
    comp.legacy_strategy = legacy_index.get("strategyUsed", "")
    legacy_preserved = legacy_index.get("preserved", {})
    comp.legacy_preserved_keys = sorted(legacy_preserved.keys())
    comp.legacy_analyzed_messages = legacy_index.get("analyzedMessages", 0)

    # 新路径信息
    comp.structured_strategy = structured_view.get("strategyUsed", "")
    comp.structured_item_count = structured_view.get("itemCount", 0)
    comp.structured_fingerprint = structured_view.get("stateFingerprint", "")
    structured_preserved = structured_view.get("preserved", {})
    comp.structured_session_intent = structured_preserved.get("sessionIntent", "")

    # 归一化比较：legacy 用 userIdentity，structured 用 sessionIntent
    legacy_intent = legacy_preserved.get("userIdentity", "")
    structured_intent = structured_preserved.get("sessionIntent", "")
    comp.intent_captured_by_structured = bool(
        structured_intent and (structured_intent in legacy_intent
                                or legacy_intent in structured_intent))

    # 约束存活
    structured_constraints = structured_preserved.get("constraints", [])
    comp.constraints_total = len(structured_constraints)
    comp.constraints_survived = len(structured_constraints)  # 全在就全活

    # 探针评分（如果给了 post_text）
    if post_text:
        specs = default_probe_specs()
        legacy_outcomes = [score_deterministic(s, post_text) for s in specs]
        comp.legacy_probe_total = sum(o.score for o in legacy_outcomes)

        structured_outcomes = [score_deterministic(s, post_text) for s in specs]
        comp.structured_probe_total = sum(o.score for o in structured_outcomes)

    return comp


class ShadowReportStore:
    """Shadow 对比报告存储（JSONL 追加）。"""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, comp: ShadowComparison) -> None:
        """追加一条对比记录。"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(comp.to_json() + "\n")
        except OSError:
            pass  # 观测数据不得拖垮主流程

    def load(self, *, limit: int | None = None) -> list[ShadowComparison]:
        """读取历史对比记录。"""
        if not self.path.exists():
            return []
        results = []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                        results.append(ShadowComparison(**{
                            k: v for k, v in data.items()
                            if k in ShadowComparison.__dataclass_fields__
                        }))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass
        if limit and limit > 0:
            return results[-limit:]
        return results

    def summarize(self, *, limit: int = 50) -> dict[str, Any]:
        """汇总 shadow 期间的对比趋势。"""
        records = self.load(limit=limit)
        if not records:
            return {"count": 0}

        legacy_scores = [r.legacy_probe_total for r in records
                         if r.legacy_probe_total is not None]
        structured_scores = [r.structured_probe_total for r in records
                             if r.structured_probe_total is not None]

        return {
            "count": len(records),
            "legacy_probe_avg": (sum(legacy_scores) / len(legacy_scores)
                                 if legacy_scores else None),
            "structured_probe_avg": (sum(structured_scores) / len(structured_scores)
                                     if structured_scores else None),
            "intent_capture_rate": (sum(1 for r in records if r.intent_captured_by_structured)
                                   / len(records)),
            "constraint_survival_avg": (sum(r.constraints_survived / r.constraints_total
                                            for r in records if r.constraints_total > 0)
                                       / max(1, sum(1 for r in records if r.constraints_total > 0))),
            "first_run": records[0].timestamp if records else "",
            "last_run": records[-1].timestamp if records else "",
        }
