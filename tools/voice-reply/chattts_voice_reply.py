#!/usr/bin/env python3
"""
ChatTTS voice reply — async subprocess wrapper for main-session integration.

Architecture:
  Main agent (any skill/chat context)
    └── chattts_voice_reply.py ──→ subprocess(chattts-on-demand.sh)
                                   └── on success → prints output path
                                   └── on failure → prints nothing, exits 1

Usage (from shell or agent tool call):
  python3 tools/voice-reply/chattts_voice_reply.py \
    --text "回复内容" \
    [--preset <presets.json 中的任意 preset 名>] \
    [--max-chars 60]

Integration contract:
  - Output path printed to stdout (or empty on failure)
  - Exit code 0 = success, 1 = failure
  - Designed to be called from Python subprocess / exec tool
  - No blocking: the subprocess spawn + wait pattern keeps the main session free

Constraints (hard):
  - Does NOT modify OpenClaw gateway config
  - Does NOT require a persistent daemon (uses on-demand.sh which auto-starts/exits)
  - Falls back to text-only silently on any error
  - Preserves approved voice quality (default tempo=1.15)
"""

import argparse
import os
import subprocess
import sys
import re
import uuid
from datetime import datetime
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
ON_DEMAND_SH = WORKSPACE / "tools" / "chattts-on-demand" / "chattts-on-demand.sh"
CLEANUP_SH = WORKSPACE / "tools" / "chattts-on-demand" / "cleanup-old-audio.sh"
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "voice-replies"
DEFAULT_PRESET = os.environ.get("OPENCLAW_VOICE_REPLY_PRESET", "default")
DEFAULT_TEMPO = float(os.environ.get("OPENCLAW_VOICE_REPLY_TEMPO", "1.32"))
GREETING_TEMPO_FACTOR = float(os.environ.get("OPENCLAW_VOICE_REPLY_GREETING_TEMPO_FACTOR", "0.85"))
MAX_TTS_CHARS = 120  # 用户已确认更看重说完整，其次才是速度
DEFAULT_MAX_NEW_TOKEN = int(os.environ.get("OPENCLAW_VOICE_REPLY_MAX_NEW_TOKEN", "768"))
TTS_TIMEOUT_SECONDS = 180

GREETING_OPENING_PREFIXES = (
    "好呀",
    "嗯，我在",
    "我在呢",
    "在呢",
    "你好呀",
    "嗨",
    "嘿",
    "早呀",
    "早安",
    "晚上好",
    "午安",
    "你来啦",
)

GREETING_OPENING_HINTS = (
    "想聊点什么",
    "想说点什么",
    "随便说说",
    "安静陪你",
    "陪你一会儿",
    "我听着",
    "慢慢说",
    "今天怎么样",
)


def clean_text_for_tts(text: str, max_chars: int = MAX_TTS_CHARS) -> str:
    """
    Preprocess agent reply text for TTS consumption.

    - Strip markdown formatting
    - Remove code blocks, list markers, inline code
    - Remove parenthetical annotations (like (笑), (停顿), etc. — common in companionship replies)
    - Remove excessive whitespace
    - Collapse to single line
    - Trim to max_chars, keeping the last complete sentence
    """
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    # Remove markdown links (keep link text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove bold/italic markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # Remove parenthetical annotations common in companion replies
    text = re.sub(r'[（(][^）)]*[）)]', '', text)
    # Remove list markers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+[.)]\s+', '', text, flags=re.MULTILINE)
    # Strip excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove empty and near-empty results
    if not text or len(text) < 2:
        return ""
    # Trim to max_chars, preferring last complete sentence boundary
    if len(text) > max_chars:
        truncated = text[:max_chars]
        # Find last sentence-ending punctuation within the truncated text
        for sep in ('。', '！', '？', '…', '.', '!', '?', '\n'):
            idx = truncated.rfind(sep)
            if idx > max_chars // 2:  # Only trim if we keep at least half
                truncated = truncated[:idx + 1]
                break
        text = truncated.strip()
    return text


def prune_expired_audio() -> None:
    """Best-effort cleanup for generated reply audio older than retention policy."""
    if not CLEANUP_SH.exists():
        return
    try:
        subprocess.run(
            [str(CLEANUP_SH), "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        pass


def is_greeting_opening(text: str) -> bool:
    """Heuristic: short greeting/opening turns should sound a bit slower and softer."""
    normalized = re.sub(r"\s+", "", text)
    if not normalized or len(normalized) > 80:
        return False

    starts_like_greeting = any(normalized.startswith(prefix) for prefix in GREETING_OPENING_PREFIXES)
    has_opening_hint = any(hint in normalized for hint in GREETING_OPENING_HINTS)
    question_count = normalized.count("？") + normalized.count("?")

    return starts_like_greeting and (has_opening_hint or question_count >= 1)


def choose_tempo(text: str, base_tempo: float) -> float:
    if is_greeting_opening(text):
        return round(base_tempo * GREETING_TEMPO_FACTOR, 4)
    return base_tempo


def synthesize(
    text: str,
    preset: str = DEFAULT_PRESET,
    tempo: float = DEFAULT_TEMPO,
    max_new_token: int = DEFAULT_MAX_NEW_TOKEN,
    out_path: str | None = None,
    max_chars: int = MAX_TTS_CHARS,
) -> str | None:
    """
    Synthesize text to audio via the on-demand ChatTTS pipeline.

    Returns:
        Path to the generated audio file (str), or None on failure.

    This function is designed to be called from the main agent context.
    It wraps the chattts-on-demand.sh CLI and handles:
    - Text preprocessing (clean + trim)
    - Subprocess execution with timeout
    - Output path management
    - Silence on failure (no crash logs propagated)
    """
    # 1. Preprocess text
    clean = clean_text_for_tts(text, max_chars=max_chars)
    if not clean:
        return None
    effective_tempo = choose_tempo(clean, tempo)

    # 2. Opportunistic cleanup + determine output path
    prune_expired_audio()
    if not out_path:
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = str(DEFAULT_OUT_DIR / f"voice-reply-{stamp}-{preset}-{uuid.uuid4().hex[:8]}.mp3")

    # 3. Run on-demand TTS
    on_demand = str(ON_DEMAND_SH)
    if not Path(on_demand).exists():
        # Fallback: try direct stable script
        stable_sh = str(WORKSPACE / "tools" / "voice-reply" / "chattts-stable.sh")
        if Path(stable_sh).exists():
            on_demand = stable_sh
        else:
            return None

    try:
        result = subprocess.run(
            [on_demand, "--text", clean, "--out", out_path, "--preset", preset, "--tempo", str(effective_tempo), "--max-new-token", str(max_new_token)],
            capture_output=True,
            text=True,
            timeout=TTS_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and Path(out_path).exists():
            # on-demand.sh outputs "DONE: /path/to/file" on success
            return out_path
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def main() -> None:
    """CLI entry point — designed for shell/exec calls from the main agent."""
    ap = argparse.ArgumentParser(
        description="ChatTTS voice reply wrapper for main-session integration",
    )
    ap.add_argument("--text", required=True, help="Reply text to synthesize")
    ap.add_argument("--preset", default=DEFAULT_PRESET,
                    help=f"Voice preset name from presets.json (default: {DEFAULT_PRESET})")
    ap.add_argument("--out", default="", help="Output path (auto-generated if omitted)")
    ap.add_argument("--tempo", type=float, default=DEFAULT_TEMPO,
                    help=f"Tempo multiplier (default: {DEFAULT_TEMPO})")
    ap.add_argument("--max-new-token", type=int, default=DEFAULT_MAX_NEW_TOKEN,
                    help=f"Max audio token budget (default: {DEFAULT_MAX_NEW_TOKEN})")
    ap.add_argument("--max-chars", type=int, default=MAX_TTS_CHARS,
                    help=f"Max chars for TTS (default: {MAX_TTS_CHARS})")
    args = ap.parse_args()

    out_path = synthesize(
        text=args.text,
        preset=args.preset,
        tempo=args.tempo,
        max_new_token=args.max_new_token,
        out_path=args.out or None,
        max_chars=args.max_chars,
    )
    if out_path:
        print(out_path)
        sys.exit(0)
    else:
        # Silent failure — caller knows to fall back to text-only
        sys.exit(1)


if __name__ == "__main__":
    main()
