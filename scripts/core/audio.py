#!/usr/bin/env python3
"""Infos-handle audio: TTS rendering, spoken text planning, segment building."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .catalog import DEFAULT_AUDIO_RENDER_TIMEOUT_SECONDS
from .snapshot import (
    first_text,
    trim_line,
    output_artifact_stem,
    file_size_bytes,
    guess_media_type,
    extract_last_nonempty_line,
)
from .query import normalize_render_lines


KIND_NATURAL_PREAMBLE: dict[str, str] = {
    "snapshot.summary": "系统状态汇报：",
    "health.summary": "健康检查结果：",
    "health.detail": "健康检查明细：",
    "tasks.summary": "后台任务情况：",
    "recovery.summary": "前台恢复状态：",
    "direct.message": "来自系统的消息：",
}

SPOKEN_CONNECTORS = ["——", "另外，", "当前来看，", "需要留意的是，", "同时，", "接下来，"]


def split_audio_phrases(text: str, *, max_chars: int = 36) -> list[str]:
    initial_parts = [part for part in re.split(r"[。！！?？；;\n]+", text) if part and part.strip()]
    if not initial_parts:
        initial_parts = [text]
    segments: list[str] = []
    for part in initial_parts:
        cleaned = re.sub(r"\s+", " ", str(part or "").replace("｜", "，").replace(" / ", "、").replace("/", "、")).strip(" ，。；;:：")
        if not cleaned:
            continue
        if len(cleaned) <= max_chars:
            segments.append(cleaned)
            continue
        secondary_parts = [item.strip(" ，。；;:：") for item in re.split(r"[，,:：]+", cleaned) if item and item.strip()]
        if len(secondary_parts) > 1:
            for item in secondary_parts:
                if len(item) <= max_chars:
                    segments.append(item)
                    continue
                for index in range(0, len(item), max_chars):
                    segments.append(item[index : index + max_chars].strip())
            continue
        for index in range(0, len(cleaned), max_chars):
            segments.append(cleaned[index : index + max_chars].strip())
    return [segment for segment in segments if segment]


def ensure_spoken_sentence(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = cleaned.strip(" ，；;")
    if not cleaned:
        return ""
    if cleaned[-1] in "。！？!?":
        return cleaned
    return cleaned + "。"


def estimate_spoken_duration_seconds(spoken_text: str) -> float:
    visible_chars = len(re.sub(r"\s+", "", spoken_text))
    return round(max(1.0, visible_chars / 4.6), 1)


def build_spoken_preamble(kind: str, summary: str) -> str:
    """Build a natural spoken preamble that identifies the context before delivering details."""
    base = KIND_NATURAL_PREAMBLE.get(kind)
    if base:
        return base
    if kind.endswith(".summary"):
        return "状态汇报："
    if kind == "direct.message":
        return "来自系统的消息："
    return ""


def apply_spoken_connectors(segments: list[str]) -> list[str]:
    """Insert natural spoken connectors between segments to avoid robotic list recitation."""
    if len(segments) <= 1:
        return segments
    result: list[str] = [segments[0]]
    for i, segment in enumerate(segments[1:], 1):
        if i <= len(SPOKEN_CONNECTORS):
            connector = SPOKEN_CONNECTORS[i - 1]
        else:
            connector = "还有，"
        if segment.startswith("建议") or segment.startswith("需要"):
            connector = "——"
        result.append(f"{connector}{segment}")
    return result


def build_audio_render_plan(query_payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(query_payload.get("kind") or "direct.message")
    text = str(query_payload.get("text") or "").strip()
    result = query_payload.get("result") if isinstance(query_payload.get("result"), dict) else {}
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    is_summary_kind = kind.endswith(".summary")
    max_segments = 3 if is_summary_kind else 6
    self_help_actions = [item for item in result.get("selfHelpActions", []) if isinstance(item, str) and item.strip()]
    if is_summary_kind:
        self_help_actions = self_help_actions[:1]
    structured_lines = normalize_render_lines(
        [
            result.get("summary"),
            result.get("issueOverview"),
            result.get("detail"),
            result.get("message"),
            *(f"建议：{item}" for item in self_help_actions),
        ],
        max_items=8,
        split_pipes=False,
    )
    candidate_lines = structured_lines or raw_lines
    if not candidate_lines:
        candidate_lines = [item for item in [result.get("summary"), result.get("issueOverview"), result.get("detail"), result.get("message")] if isinstance(item, str) and item.strip()]

    segments: list[str] = []
    seen: set[str] = set()
    section_label: str | None = None
    for raw_line in candidate_lines:
        stripped = raw_line.strip()
        if not stripped:
            section_label = None
            continue
        if stripped.endswith((":", "：")) and len(stripped) <= 8:
            section_label = stripped.rstrip(":： ")
            continue
        bullet = stripped.startswith(("-", "•", "·"))
        cleaned = re.sub(r"^\[[^\]]+\]\s*", "", stripped)
        cleaned = re.sub(r"^[-•·]\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            continue
        if section_label and bullet:
            cleaned = f"{section_label}：{cleaned}"
        elif section_label and not bullet and len(raw_lines) == 1:
            cleaned = f"{section_label}：{cleaned}"
        for part in split_audio_phrases(cleaned):
            normalized = part.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            segments.append(normalized)
            if len(segments) >= max_segments:
                break
        if len(segments) >= max_segments:
            break

    if not segments:
        raise RuntimeError("audio output requires non-empty text")

    spoken_segments = [ensure_spoken_sentence(segment) for segment in segments if ensure_spoken_sentence(segment)]
    preamble = build_spoken_preamble(kind, result.get("summary", ""))
    connected_segments = apply_spoken_connectors(spoken_segments)
    spoken_text = (preamble + " ") if preamble else ""
    spoken_text += " ".join(connected_segments)
    return {
        "textPlanVersion": 3,
        "strategy": "stable_lines_v3",
        "preamble": preamble,
        "connectorStyle": "natural_transitions",
        "segmentCount": len(connected_segments),
        "segments": connected_segments,
        "estimatedDurationSeconds": estimate_spoken_duration_seconds(spoken_text),
        "summary": spoken_segments[0].rstrip("。！？!?"),
        "sourceKind": kind,
        "sourceText": text,
        "spokenText": spoken_text,
    }


def render_audio_output(query_payload: dict[str, Any], output_root: Path, audio_renderer: str | None, audio_preset: str) -> dict[str, Any]:
    # DEFAULT_AUDIO_RENDERER is imported lazily to avoid circular import with main.py
    from .main import _get_default_audio_renderer

    renderer_path = Path(audio_renderer or str(_get_default_audio_renderer())).expanduser().resolve()
    if not renderer_path.exists():
        raise RuntimeError(f"audio renderer not found: {renderer_path}")

    plan = build_audio_render_plan(query_payload)
    spoken_text = str(plan.get("spokenText") or "").strip()
    if not spoken_text:
        raise RuntimeError("audio output requires non-empty text")

    completed = subprocess.run(
        [str(renderer_path), spoken_text, audio_preset],
        capture_output=True,
        text=True,
        timeout=DEFAULT_AUDIO_RENDER_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "audio renderer failed").strip()
        raise RuntimeError(stderr)

    source_path_text = extract_last_nonempty_line(completed.stdout)
    if not source_path_text:
        raise RuntimeError("audio renderer returned empty output path")

    source_path = Path(source_path_text).expanduser().resolve()
    if not source_path.exists():
        raise RuntimeError(f"audio renderer output missing: {source_path}")

    output_dir = output_root / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix or ".mp3"
    file_stem = output_artifact_stem(str(query_payload.get("kind") or "summary"), spoken_text, "audio")
    output_path = output_dir / f"{file_stem}{suffix}"
    shutil.copy2(source_path, output_path)

    return {
        "format": "audio",
        "status": "rendered",
        "handler": "audio.local-tts.v2",
        "delivery": "artifact_file",
        "mediaType": guess_media_type(output_path, "audio/mpeg"),
        "preset": audio_preset,
        "renderer": str(renderer_path),
        "artifactRef": f"infos-handle:audio:{file_stem}",
        "path": str(output_path),
        "fileName": output_path.name,
        "sizeBytes": file_size_bytes(output_path),
        "summary": plan.get("summary"),
        "sourceText": plan.get("sourceText"),
        "spokenText": spoken_text,
        "sourcePath": str(source_path),
        "result": {
            key: value
            for key, value in plan.items()
            if key not in {"summary", "sourceText", "spokenText"}
        },
    }
