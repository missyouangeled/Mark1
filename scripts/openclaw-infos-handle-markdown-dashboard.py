#!/usr/bin/env python3
# 适用机器：通用
# 系统 / OS：Linux / macOS / Windows
# 用途：通过 infos-handle 查询 broker 数据，输出富文本 Markdown 仪表盘报告。
# 这是 broker / infos-handle 增强轮 5 方向 1 的新 consumer 场景。

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
INFOS_HANDLE = WORKSPACE / "scripts" / "openclaw-infos-handle.py"
DEFAULT_SNAPSHOT = Path.home() / ".local" / "state" / "openclaw" / "broker" / "views" / "snapshot.json"
DEFAULT_EVENTS = Path.home() / ".local" / "state" / "openclaw" / "broker" / "events.jsonl"


def _run(*args: str, input_text: str | None = None) -> dict[str, Any]:
    cmd = [sys.executable, str(INFOS_HANDLE), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, input=input_text)
    if result.returncode != 0:
        raise SystemExit(f"infos-handle failed: {result.stderr or result.stdout}".strip())
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str | None:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _emoji_severity(severity: str | None) -> str:
    return {"ok": "🟢", "warn": "🟡", "critical": "🔴"}.get(str(severity or ""), "⚪")


def _severity_badge(severity: str | None) -> str:
    labels = {"ok": "正常", "warn": "注意", "critical": "严重"}
    return labels.get(str(severity or ""), "未知")


def _format_ts(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts)
        local = dt.astimezone()
        return local.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ts


def _panel_name(label: str) -> str:
    mapping = {"健康": "本地健康诊断", "任务": "监工服务", "恢复": "前台恢复观察"}
    for key, name in mapping.items():
        if key in label:
            return name
    return label


def _truncate(text: str, max_len: int = 80) -> str:
    return text[:max_len] + "…" if len(text) > max_len else text


def build_markdown_dashboard(
    snapshot_path: str,
    events_path: str,
    *,
    output_root: str | None = None,
) -> str:
    """Query broker data via infos-handle and return a rich Markdown dashboard report."""
    snapshot = _run(
        "query", "--kind", "snapshot.summary", "--format", "json",
        "--snapshot-path", snapshot_path, "--events-path", events_path,
    )

    health = _run(
        "query", "--kind", "health.summary", "--format", "json",
        "--snapshot-path", snapshot_path, "--events-path", events_path,
    )

    # panels.catalog for quick panel overview
    panels_catalog = _run(
        "query", "--kind", "panels.catalog", "--format", "json",
        "--snapshot-path", snapshot_path, "--events-path", events_path,
    )

    # events.recent for latest broker events
    events_recent = _run(
        "query", "--kind", "events.recent", "--format", "json", "--limit", "4",
        "--snapshot-path", snapshot_path, "--events-path", events_path,
    )

    # sources.catalog for source overview
    sources_catalog = _run(
        "query", "--kind", "sources.catalog", "--format", "json",
        "--snapshot-path", snapshot_path, "--events-path", events_path,
    )

    # --- Build report ---
    lines: list[str] = []
    now = datetime.now(timezone.utc).astimezone()
    lines.append(f"# 📊 Broker Dashboard 报告")
    lines.append(f"> 生成时间：{now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append(f"> 快照路径：`{snapshot_path}`")
    lines.append("")

    # --- Overall Status ---
    sev = _first_text(snapshot.get("severity"), snapshot.get("summarySeverity"))
    summary_text = _first_text(snapshot.get("summary"), snapshot.get("text"))
    lines.append("## 🏠 总体状态")
    lines.append(f"> {_emoji_severity(sev)} **{_severity_badge(sev)}** — {summary_text or '-'}")
    issue_overview = snapshot.get("issueOverview")
    if issue_overview:
        lines.append(f"> 📋 {_truncate(str(issue_overview), 100)}")
    lines.append("")

    # --- Help Text ---
    help_text = _first_text(snapshot.get("helpText"))
    if help_text:
        lines.append("📝 **说明**：")
        for line in str(help_text).splitlines()[:4]:
            if line.strip():
                lines.append(f"> {line.strip()}")
        lines.append("")

    # --- Panels ---
    catalog_data = panels_catalog.get("result", {}) if isinstance(panels_catalog.get("result"), dict) else {}
    panel_items = catalog_data.get("items", []) if isinstance(catalog_data.get("items"), list) else []
    lines.append("## 📦 面板概览")
    lines.append("")
    lines.append("| 面板 | 状态 | 可用 | 最近检查 |")
    lines.append("|------|------|------|----------|")
    for item in panel_items[:8]:
        name = _panel_name(str(item.get("name") or "-"))
        severity = _first_text(item.get("severity")) or "ok"
        available = "✅" if item.get("available") else "❌"
        checked = _format_ts(item.get("checkedAt"))
        lines.append(f"| {name} | {_emoji_severity(severity)} {_severity_badge(severity)} | {available} | {checked} |")
    lines.append("")

    # --- Sources ---
    src_catalog = sources_catalog.get("result", {}) if isinstance(sources_catalog.get("result"), dict) else {}
    src_items = src_catalog.get("items", []) if isinstance(src_catalog.get("items"), list) else []
    if src_items:
        lines.append("## 🔌 数据源")
        lines.append("")
        for src in src_items[:6]:
            name = str(src.get("source") or "-")
            etype = str(src.get("sourceEventType") or "-")
            view = str(src.get("sourceView") or "-")
            latest_msg = _first_text(
                src.get("latestDeliveryMessage"),
                src.get("latestEventMessage"),
            ) or "-"
            lines.append(f"### {name}")
            lines.append(f"- 事件类型：`{etype}`")
            lines.append(f"- 关联视图：`{view}`")
            lines.append(f"- 最近消息：{_truncate(latest_msg, 60)}")
            lines.append("")

    # --- Recent Events ---
    ev_result = events_recent.get("result", {}) if isinstance(events_recent.get("result"), dict) else {}
    ev_items = ev_result.get("items", []) if isinstance(ev_result.get("items"), list) else []
    if ev_items:
        lines.append("## 📜 最近事件")
        lines.append("")
        for ev in ev_items[:4]:
            record_type = str(ev.get("recordType") or "-")
            source = str(ev.get("source") or "-")
            msg = _first_text(ev.get("message")) or "-"
            ts = _format_ts(ev.get("recordedAt"))
            lines.append(f"- `{ts}` | [{source}] `{record_type}` — {_truncate(msg, 50)}")
        lines.append("")

    # --- Health Detail ---
    health_detail = health.get("detail")
    health_actions = health.get("selfHelpActions", []) if isinstance(health.get("selfHelpActions"), list) else []
    lines.append("## 💚 健康详情")
    lines.append(f"> 结果：**{_first_text(health.get('summary')) or '-'}**")
    if health_detail:
        lines.append(f"> {_truncate(str(health_detail), 100)}")
    if health_actions:
        lines.append("")
        lines.append("**建议操作：**")
        for act in health_actions[:3]:
            lines.append(f"- {act}")
    lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append(f"*由 infos-handle Markdown Dashboard consumer 生成 · `{now.isoformat(timespec='seconds')}`*")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rich Markdown dashboard report from broker/infos-handle data")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT), help="Broker snapshot.json path")
    parser.add_argument("--events-path", default=str(DEFAULT_EVENTS), help="Broker events.jsonl path")
    parser.add_argument("--output", "-o", help="Write report to file (default: stdout)")
    parser.add_argument("--output-root", help="Directory for image/audio artifacts (default: infos-handle default)")
    args = parser.parse_args()

    try:
        report = build_markdown_dashboard(
            snapshot_path=args.snapshot_path,
            events_path=args.events_path,
            output_root=args.output_root,
        )
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"dashboard build failed: {exc}") from exc

    if args.output:
        Path(args.output).expanduser().resolve().write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
