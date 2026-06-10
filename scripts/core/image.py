#!/usr/bin/env python3
"""Infos-handle image: SVG card rendering for snapshot dashboards."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any

from .catalog import DEFAULT_IMAGE_PRESET
from .snapshot import (
    first_text,
    trim_line,
    output_artifact_stem,
    file_size_bytes,
    write_text,
)
from .query import (
    pick_response_severity,
    normalize_render_lines,
)


TONE_SEVERITY_MAP: dict[str, str] = {
    "summary": "ok",
    "focus": "warn",
    "meta": "ok",
    "health": "ok",
    "supervisor": "warn",
    "recovery": "critical",
}

TONE_ICON_MAP: dict[str, str] = {
    "summary": "📋",
    "focus": "🔍",
    "meta": "ℹ️",
    "health": "💚",
    "supervisor": "⚙️",
    "recovery": "🔄",
}

TONE_BADGE_MAP: dict[str, str] = {
    "ok": "正常",
    "warn": "注意",
    "critical": "异常",
}


def _build_snapshot_dashboard_panels(snapshot: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    """Build richer per-source panels from the real snapshot when available."""
    snapshot_panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
    if not snapshot_panels:
        return []
    panels: list[dict[str, Any]] = []
    for panel_key in ("health", "supervisor", "recovery"):
        panel = snapshot_panels.get(panel_key) if isinstance(snapshot_panels.get(panel_key), dict) else None
        if not panel:
            continue
        panel_summary = str(panel.get("summary") or "-")
        panel_severity = str(panel.get("severity") or TONE_SEVERITY_MAP.get(panel_key, "ok"))
        panel_detail = str(panel.get("detail") or "").strip()
        panel_checked = str(panel.get("checkedAt") or "-")
        lines = normalize_render_lines(
            [panel_summary, panel_detail, f"时间：{panel_checked}"],
            max_items=3,
        )
        panels.append({
            "label": TONE_ICON_MAP.get(panel_key, "📌") + " " + {"health": "健康", "supervisor": "任务", "recovery": "恢复"}.get(panel_key, panel_key),
            "title": trim_line(panel_summary, 28),
            "tone": panel_key,
            "severity": panel_severity,
            "lines": lines,
        })
    return panels


def build_image_render_model(query_payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(query_payload.get("kind") or "direct.message")
    text = str(query_payload.get("text") or "").strip()
    result = query_payload.get("result") if isinstance(query_payload.get("result"), dict) else {}
    snapshot = query_payload.get("snapshot") if isinstance(query_payload.get("snapshot"), dict) else {}
    severity = pick_response_severity(query_payload)
    raw_lines = normalize_render_lines(text.splitlines(), max_items=12)
    summary = first_text(
        result.get("summary"),
        result.get("issueOverview"),
        result.get("detail"),
        raw_lines[0] if raw_lines else None,
        query_payload.get("message"),
        kind,
    ) or kind
    checked_at = first_text(result.get("checkedAt"), snapshot.get("checkedAt"), snapshot.get("updatedAt")) or "-"
    recent_actions = result.get("selfHelpActions") if isinstance(result.get("selfHelpActions"), list) else []
    overview_lines = normalize_render_lines(
        [
            summary,
            result.get("issueOverview"),
            result.get("detail"),
            result.get("message"),
            snapshot.get("issueOverview"),
        ],
        max_items=3,
    )
    focus_lines = normalize_render_lines(
        [
            *raw_lines[1:],
            *(f"建议：{item}" for item in recent_actions[:3] if isinstance(item, str) and item.strip()),
            result.get("latestDeliveryMessage"),
            result.get("latestEventSummary"),
            result.get("latestSourceStateSummary"),
        ],
        max_items=5,
    )
    context_lines = normalize_render_lines(
        [
            f"kind={kind}",
            f"severity={severity or 'preview'}",
            f"source={first_text(result.get('source'), query_payload.get('sourceName'), snapshot.get('latestSource')) or '-'}",
            f"panel={first_text(result.get('panelName'), query_payload.get('panelName')) or '-'}",
            f"checkedAt={checked_at}",
        ],
        max_items=4,
        split_pipes=False,
    )
    dashboard_panels = _build_snapshot_dashboard_panels(snapshot, result)
    panels: list[dict[str, Any]] = []
    if dashboard_panels:
        panels = dashboard_panels
    else:
        panels = [
            {
                "label": "📋 概览",
                "title": trim_line(summary, 28),
                "tone": "summary",
                "severity": severity,
                "lines": overview_lines[:3] or [summary],
            }
        ]
        if focus_lines:
            panels.append({
                "label": "🔍 重点",
                "title": trim_line(focus_lines[0], 28),
                "tone": "focus",
                "severity": "warn",
                "lines": focus_lines[:4],
            })
        if context_lines:
            panels.append({
                "label": "ℹ️ 上下文",
                "title": trim_line(context_lines[0], 28),
                "tone": "meta",
                "severity": "ok",
                "lines": context_lines[:4],
            })
    layout = "headline"
    if len(panels) >= 3:
        layout = "activity-grid"
    elif len(panels) == 2:
        layout = "focus-columns"
    if dashboard_panels and len(panels) >= 2:
        layout = "dashboard"
    footer_lines = [
        f"kind={kind}",
        f"checkedAt={checked_at}",
        f"snapshot={Path(str(query_payload.get('snapshotPath') or '-')).name}",
    ]
    badge = {
        "ok": "正常",
        "warn": "告警",
        "critical": "严重",
    }.get(str(severity or ""), "预览")
    return {
        "cardVersion": 3,
        "layout": layout,
        "title": trim_line(kind, 48),
        "summary": summary,
        "severity": severity,
        "badge": badge,
        "panels": panels,
        "footerLines": footer_lines,
        "sourceText": text,
    }


def build_image_render_model_v3(query_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a v3 render model with richer per-panel metadata, gradient flags, and status sparkline data."""
    base = build_image_render_model(query_payload)
    panels = base.get("panels") if isinstance(base.get("panels"), list) else []
    snapshot = query_payload.get("snapshot") if isinstance(query_payload.get("snapshot"), dict) else {}
    snapshot_panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
    source_state_snapshots = snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {}

    # Enrich each panel with checkedAt timestamps and richer detail
    richer_panels: list[dict[str, Any]] = []
    for panel in panels:
        tone = str(panel.get("tone") or "summary")
        panel_label = str(panel.get("label") or "")
        # Try to pull timestamp from snapshot panels
        panel_checked_at: str | None = None
        for panel_key in ("health", "supervisor", "recovery"):
            if tone == panel_key or (TONE_ICON_MAP.get(panel_key, "") + " ") in panel_label:
                sp = snapshot_panels.get(panel_key) if isinstance(snapshot_panels.get(panel_key), dict) else None
                if sp:
                    panel_checked_at = str(sp.get("checkedAt") or "")
                break
        # Also try sourceStateSnapshots for timestamp
        if not panel_checked_at:
            for src_key in ("local-health", "frontstage-recovery", "supervisor"):
                ss = source_state_snapshots.get(src_key) if isinstance(source_state_snapshots.get(src_key), dict) else None
                if ss and ss.get("sourceView") == tone:
                    panel_checked_at = str(ss.get("recordedAt") or "")
                    break
        richer_panel = dict(panel)
        richer_panel["checkedAt"] = panel_checked_at or "-"
        richer_panels.append(richer_panel)

    # Sparkline data: map severity to a mini progress bar width percentage
    severity_spark_map = {"ok": 100, "warn": 50, "critical": 20}
    sparkline_data = [
        severity_spark_map.get(str(p.get("severity") or "ok"), 80)
        for p in richer_panels
    ]

    return {
        **base,
        "cardVersion": 4,
        "panels": richer_panels,
        "gradientShell": True,
        "panelGradients": True,
        "statusSparkLine": True,
        "sparklineData": sparkline_data,
    }


def build_image_panel_positions(layout: str, panel_count: int) -> list[tuple[int, int, int, int]]:
    if layout == "focus-columns" and panel_count >= 2:
        return [
            (36, 246, 584, 286),
            (660, 246, 584, 286),
        ]
    if layout == "dashboard" and panel_count >= 2:
        if panel_count == 2:
            return [
                (36, 246, 584, 286),
                (660, 246, 584, 286),
            ]
        return [
            (36, 246, 376, 286),
            (452, 246, 376, 286),
            (868, 246, 376, 286),
        ]
    if layout == "headline" or panel_count <= 1:
        return [(36, 246, 1208, 286)]
    return [
        (36, 246, 376, 286),
        (452, 246, 376, 286),
        (868, 246, 376, 286),
    ]


def build_image_card_svg(model: dict[str, Any]) -> str:
    accent = {
        "ok": "#4ade80",
        "warn": "#f59e0b",
        "critical": "#ef4444",
    }.get(str(model.get("severity") or ""), "#60a5fa")
    panel_accent_map = {
        "ok": "#4ade80",
        "warn": "#f59e0b",
        "critical": "#ef4444",
    }
    tone_accent_map = {
        "summary": "#60a5fa",
        "focus": "#f59e0b",
        "meta": "#94a3b8",
        "health": "#4ade80",
        "supervisor": "#f59e0b",
        "recovery": "#ef4444",
    }
    bg = "#081018"
    shell = "#0f172a"
    panel_fill = "#132236"
    panel_stroke = "rgba(150,180,220,.14)"
    text_main = "#eaf2ff"
    text_sub = "#b9c7d8"
    text_muted = "#7f98b5"
    badge_bg = "rgba(255,255,255,.08)"

    panels = model.get("panels") if isinstance(model.get("panels"), list) else []
    panel_positions = build_image_panel_positions(str(model.get("layout") or "headline"), len(panels))
    panel_svg: list[str] = []
    for panel, (x, y, width, height) in zip(panels, panel_positions, strict=False):
        label = trim_line(str(panel.get("label") or ""), 16)
        title = trim_line(str(panel.get("title") or ""), 28)
        lines = panel.get("lines") if isinstance(panel.get("lines"), list) else []
        panel_tone = str(panel.get("tone") or "summary")
        panel_severity = str(panel.get("severity") or "")
        panel_accent = panel_accent_map.get(panel_severity) or tone_accent_map.get(panel_tone, "#60a5fa")
        panel_badge_text = TONE_BADGE_MAP.get(panel_severity, "") or {
            "ok": "正常",
            "warn": "注意",
            "critical": "异常",
        }.get(TONE_SEVERITY_MAP.get(panel_tone, "ok"), "")
        line_svg: list[str] = []
        line_y = y + 120
        for item in lines[:6]:
            text = trim_line(item, 34 if width < 500 else 58)
            if not text:
                continue
            line_svg.append(f"<text x='{x + 20}' y='{line_y}' font-size='20' fill='{text_sub}'>{escape(text)}</text>")
            line_y += 28
        badge_svg = ""
        if panel_badge_text:
            badge_x = x + width - 72
            badge_svg = (
                f"<rect x='{badge_x}' y='{y + 16}' width='56' height='28' rx='14' fill='{panel_accent}' opacity='0.18' />"
                f"<text x='{badge_x + 28}' y='{y + 35}' font-size='14' text-anchor='middle' fill='{panel_accent}'>{escape(trim_line(panel_badge_text, 6))}</text>"
            )
        panel_svg.append(
            f"<rect x='{x}' y='{y}' width='{width}' height='{height}' rx='24' fill='{panel_fill}' stroke='{panel_stroke}' />"
            f"<rect x='{x + 4}' y='{y + 4}' width='{width - 8}' height='6' rx='3' fill='{panel_accent}' opacity='0.5' />"
            f"{badge_svg}"
            f"<text x='{x + 20}' y='{y + 46}' font-size='16' fill='{text_muted}'>{escape(label)}</text>"
            f"<text x='{x + 20}' y='{y + 84}' font-size='26' font-weight='700' fill='{text_main}'>{escape(title)}</text>"
            f"{''.join(line_svg)}"
        )

    footer_svg: list[str] = []
    footer_y = 0
    footer_lines = model.get("footerLines") if isinstance(model.get("footerLines"), list) else []
    for item in footer_lines[:3]:
        line = trim_line(item, 60)
        if not line:
            continue
        footer_y += 20
        footer_svg.append(f"<text x='36' y='{620 + footer_y}' font-size='16' fill='{text_muted}'>{escape(line)}</text>")

    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='720' viewBox='0 0 1280 720'>
  <rect width='1280' height='720' fill='{bg}' />
  <rect x='24' y='24' width='1232' height='672' rx='28' fill='{shell}' stroke='rgba(150,180,220,.18)' />
  <rect x='36' y='36' width='1208' height='10' rx='5' fill='{accent}' />
  <text x='36' y='88' font-size='22' fill='{text_muted}'>infos-handle v2 richer image output</text>
  <rect x='1084' y='62' width='132' height='40' rx='20' fill='{badge_bg}' stroke='rgba(255,255,255,.08)' />
  <text x='1150' y='88' font-size='18' text-anchor='middle' fill='{text_sub}'>{escape(trim_line(str(model.get('badge') or '预览'), 10))}</text>
  <text x='36' y='146' font-size='38' font-weight='700' fill='{text_main}'>{escape(trim_line(str(model.get('title') or 'infos-handle'), 46))}</text>
  <text x='36' y='194' font-size='28' fill='{text_sub}'>{escape(trim_line(str(model.get('summary') or ''), 66))}</text>
  {''.join(panel_svg)}
  {''.join(footer_svg)}
</svg>
"""


def build_image_card_svg_v3(model: dict[str, Any]) -> str:
    """Build a richer v3 SVG card with gradient accents, per-panel timestamps, status sparklines, and enhanced visual hierarchy."""
    accent = {
        "ok": "#4ade80",
        "warn": "#f59e0b",
        "critical": "#ef4444",
    }.get(str(model.get("severity") or ""), "#60a5fa")
    panel_severity_accent = {
        "ok": "#4ade80",
        "warn": "#f59e0b",
        "critical": "#ef4444",
    }
    tone_accent_map = {
        "summary": "#60a5fa",
        "focus": "#a78bfa",
        "meta": "#94a3b8",
        "health": "#4ade80",
        "supervisor": "#f59e0b",
        "recovery": "#c084fc",
    }
    bg = "#060d18"
    shell = "#0d1525"
    panel_fill = "#111b2e"
    panel_stroke = "rgba(140,170,210,.16)"
    text_main = "#eaf2ff"
    text_sub = "#b9c7d8"
    text_muted = "#7f98b5"
    text_faint = "#5b718a"
    badge_bg = "rgba(255,255,255,.08)"

    panels = model.get("panels") if isinstance(model.get("panels"), list) else []
    sparkline_data = model.get("sparklineData") if isinstance(model.get("sparklineData"), list) else []
    panel_positions = build_image_panel_positions(str(model.get("layout") or "headline"), len(panels))

    # SVG defs for gradients
    defs_parts: list[str] = []
    # Shell gradient
    defs_parts.append(
        "<linearGradient id='shellGrad' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#0d1525' /><stop offset='100%' stop-color='#10192d' /></linearGradient>"
    )
    # Accent gradient
    defs_parts.append(
        f"<linearGradient id='accentGrad' x1='0' y1='0' x2='1' y2='0'>"
        f"<stop offset='0%' stop-color='{accent}' stop-opacity='0.9' />"
        f"<stop offset='100%' stop-color='{accent}' stop-opacity='0.3' /></linearGradient>"
    )
    # Per-tone panel gradients
    for i, panel in enumerate(panels):
        tone = str(panel.get("tone") or "summary")
        panel_accent = tone_accent_map.get(tone, "#60a5fa")
        defs_parts.append(
            f"<linearGradient id='panelGrad{i}' x1='0' y1='0' x2='0' y2='1'>"
            f"<stop offset='0%' stop-color='{panel_accent}' stop-opacity='0.15' />"
            f"<stop offset='100%' stop-color='{panel_accent}' stop-opacity='0.03' /></linearGradient>"
        )
        defs_parts.append(
            f"<linearGradient id='panelBar{i}' x1='0' y1='0' x2='1' y2='0'>"
            f"<stop offset='0%' stop-color='{panel_accent}' stop-opacity='0.7' />"
            f"<stop offset='100%' stop-color='{panel_accent}' stop-opacity='0.2' /></linearGradient>"
        )

    panel_svg: list[str] = []
    for i, (panel, (x, y, width, height)) in enumerate(zip(panels, panel_positions, strict=False)):
        label = trim_line(str(panel.get("label") or ""), 16)
        title = trim_line(str(panel.get("title") or ""), 28)
        lines = panel.get("lines") if isinstance(panel.get("lines"), list) else []
        panel_tone = str(panel.get("tone") or "summary")
        panel_severity = str(panel.get("severity") or "")
        panel_checked_at = str(panel.get("checkedAt") or "-")
        panel_accent = panel_severity_accent.get(panel_severity) or tone_accent_map.get(panel_tone, "#60a5fa")

        # Sparkline (mini status bar) showing severity level
        spark_pct = sparkline_data[i] if i < len(sparkline_data) else 80
        spark_svg = ""
        if model.get("statusSparkLine"):
            spark_x = x + 20
            spark_y = y + height - 24
            spark_w = width - 40
            spark_svg = (
                f"<rect x='{spark_x}' y='{spark_y}' width='{spark_w}' height='4' rx='2' fill='rgba(255,255,255,0.06)' />"
                f"<rect x='{spark_x}' y='{spark_y}' width='{spark_w * spark_pct / 100:.0f}' height='4' rx='2' fill='{panel_accent}' opacity='0.6' />"
            )

        line_svg: list[str] = []
        line_y = y + 114
        for item in lines[:5]:
            text = trim_line(item, 34 if width < 500 else 56)
            if not text:
                continue
            line_svg.append(f"<text x='{x + 20}' y='{line_y}' font-size='18' fill='{text_sub}'>{escape(text)}</text>")
            line_y += 26

        # Timestamp
        ts_svg = ""
        if panel_checked_at and panel_checked_at != "-":
            ts_y = y + height - 40
            ts_svg = f"<text x='{x + 20}' y='{ts_y}' font-size='13' fill='{text_faint}'>{escape('🕐 ' + panel_checked_at[-8:])}</text>"

        panel_svg.append(
            f"<rect x='{x}' y='{y}' width='{width}' height='{height}' rx='20' fill='url(#panelGrad{i})' stroke='{panel_stroke}' stroke-width='1.2' />"
            f"<rect x='{x + 6}' y='{y + 6}' width='{width - 12}' height='5' rx='2.5' fill='url(#panelBar{i})' />"
            f"<text x='{x + 20}' y='{y + 44}' font-size='14' fill='{text_muted}' letter-spacing='0.5'>{escape(label)}</text>"
            f"<text x='{x + 20}' y='{y + 78}' font-size='24' font-weight='700' fill='{text_main}'>{escape(title)}</text>"
            f"{''.join(line_svg)}"
            f"{spark_svg}"
            f"{ts_svg}"
        )

    footer_svg: list[str] = []
    footer_lines = model.get("footerLines") if isinstance(model.get("footerLines"), list) else []
    footer_text_items: list[str] = []
    for item in footer_lines[:3]:
        line = trim_line(item, 58)
        if not line:
            continue
        footer_text_items.append(escape(line))

    if footer_text_items:
        footer_svg.append(
            f"<rect x='36' y='598' width='1208' height='56' rx='16' fill='rgba(255,255,255,.03)' stroke='rgba(255,255,255,.05)' />"
            f"<text x='56' y='632' font-size='15' fill='{text_faint}'>{'  ·  '.join(footer_text_items)}</text>"
        )

    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='720' viewBox='0 0 1280 720'>
  <defs>{''.join(defs_parts)}</defs>
  <rect width='1280' height='720' fill='{bg}' />
  <rect x='20' y='20' width='1240' height='680' rx='32' fill='url(#shellGrad)' stroke='rgba(140,170,210,.18)' stroke-width='1.5' />
  <rect x='36' y='36' width='1208' height='8' rx='4' fill='url(#accentGrad)' />
  <text x='36' y='86' font-size='20' fill='{text_muted}'>infos-handle v3 richer dashboard</text>
  <rect x='1090' y='62' width='126' height='38' rx='19' fill='{badge_bg}' stroke='rgba(255,255,255,.08)' />
  <text x='1153' y='87' font-size='16' text-anchor='middle' fill='{text_sub}'>{escape(trim_line(str(model.get('badge') or '预览'), 10))}</text>
  <text x='36' y='148' font-size='40' font-weight='700' fill='{text_main}'>{escape(trim_line(str(model.get('title') or 'infos-handle'), 46))}</text>
  <text x='36' y='198' font-size='26' fill='{text_sub}' opacity='0.9'>{escape(trim_line(str(model.get('summary') or ''), 66))}</text>
  {''.join(panel_svg)}
  {''.join(footer_svg)}
</svg>
"""


def render_image_output(query_payload: dict[str, Any], output_root: Path, *, image_preset: str = "summary-card") -> dict[str, Any]:
    output_dir = output_root / "image"
    output_dir.mkdir(parents=True, exist_ok=True)

    use_v3 = image_preset == "summary-card-v3"
    model = build_image_render_model_v3(query_payload) if use_v3 else build_image_render_model(query_payload)
    handler = "image.summary-card.v3" if use_v3 else "image.summary-card.v2"
    svg = build_image_card_svg_v3(model) if use_v3 else build_image_card_svg(model)

    summary = str(model.get("summary") or query_payload.get("kind") or "summary")
    file_stem = output_artifact_stem(str(query_payload.get("kind") or "summary"), str(model.get("sourceText") or summary), "image")
    output_path = output_dir / f"{file_stem}.svg"
    write_text(output_path, svg)
    return {
        "format": "image",
        "status": "rendered",
        "handler": handler,
        "delivery": "artifact_file",
        "mediaType": "image/svg+xml",
        "preset": image_preset,
        "artifactRef": f"infos-handle:image:{file_stem}",
        "path": str(output_path),
        "fileName": output_path.name,
        "sizeBytes": file_size_bytes(output_path),
        "summary": summary,
        "sourceText": model.get("sourceText"),
        "result": {
            key: value
            for key, value in model.items()
            if key not in {"sourceText"}
        },
    }
