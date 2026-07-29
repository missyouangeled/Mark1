"""报告生成器：将 AuditResult 写入文件 + 发告警。

报告路径：<ARMOR_STATE>/audit/audit-YYYYMMDD-HHMMSS.json
告警渠道：broker 事件 + （可选）用户通知
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ..config import ARMOR_STATE
from ..utils import _append_broker, _now_iso, _save_json
from . import AuditResult


# ── 报告目录 ──────────────────────────────────────────

AUDIT_DIR = ARMOR_STATE / "audit"


def write_report(
    result: AuditResult,
    pre_snapshot: Dict[str, Any],
    post_summary: Dict[str, Any],
) -> str:
    """将审计结果写入报告文件。

    Returns:
        报告文件路径
    """
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = AUDIT_DIR / f"audit-{ts}.json"

    report = {
        "timestamp": _now_iso(),
        "verdict": result.verdict,
        "score": result.score,
        "recommendation": result.recommendation,
        "error": result.error,
        "preSnapshot": pre_snapshot,
        "postSummary": post_summary,
        "findings": [
            {
                "category": f.category,
                "item": f.item,
                "status": f.status,
                "detail": f.detail,
            }
            for f in result.findings
        ],
    }

    _save_json(report_path, report)

    # 保留最近 20 份报告
    _cleanup_old_reports()

    return str(report_path)


def send_alert(result: AuditResult, report_path: str) -> None:
    """审计失败时发 broker 告警。"""
    if result.verdict == "pass":
        return

    level = "error" if result.verdict == "fail" else "warning"

    _append_broker(
        "armor",
        f"mark42.armor.audit.{result.verdict}",
        f"Post-Compact Audit: {result.verdict} (score={result.score})",
        level,
        result.recommendation,
        {
            "reportPath": report_path,
            "score": result.score,
            "lostCount": sum(1 for f in result.findings if f.status == "lost"),
            "degradedCount": sum(1 for f in result.findings if f.status == "degraded"),
            "preservedCount": sum(1 for f in result.findings if f.status == "preserved"),
        },
    )


def _cleanup_old_reports(keep: int = 20) -> None:
    """保留最近 N 份报告。"""
    if not AUDIT_DIR.exists():
        return

    reports = sorted(
        AUDIT_DIR.glob("audit-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for old in reports[keep:]:
        try:
            old.unlink()
        except OSError:
            pass
