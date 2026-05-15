#!/usr/bin/env python3
"""
chattts_gpu_first_wrapper.py — GPU-first TTS wrapper with local CPU fallback.

Purpose:
  Tries remote GPU (SeetaCloud) first for ChatTTS inference via the existing
  chattts_seeta_gpu.py entry. If the GPU route fails (credential missing,
  SSH timeout, remote error, etc.), falls back to local CPU stable via the
  existing chattts-on-demand.sh pipeline.

Architecture:
  chunked_voice_reply.py ────→ chattts_gpu_first_wrapper.synthesize(...)
                                          │
                                   ┌──────┴──────┐
                                   ▼              ▼
                           seeta_gpu.py    chattts-on-demand.sh
                           (remote GPU)    (local CPU stable)

Integration contract:
  - Exposes the same `synthesize()` API as `chattts_voice_reply.py`
  - Can be imported by `chunked_voice_reply.py` as a drop-in replacement
    by setting environment: OPENCLAW_VOICE_REPLY_BACKEND=gpu-first
  - The GPU route runs inside a subprocess + SSH paramiko session (non-blocking)
  - On GPU failure, falls through to the local stable path silently
  - No modifications to `chattts_voice_reply.py`, `chunked_voice_reply.py`,
    or any stable pipeline script

Usage (CLI — same interface as chattts_voice_reply.py):
  python3 tools/voice-reply/chattts_gpu_first_wrapper.py \
    --text "回复内容" \
    --preset default \
    --tempo 1.0

  # Or set env to switch the whole pipeline:
  OPENCLAW_VOICE_REPLY_BACKEND=gpu-first \
    bash tools/voice-reply/voice-reply-chunked.sh "你好" default

Design decisions:
  - GPU-first: prefer speed/quality of GPU over local CPU
  - Silent fallback: no error messages propagated to caller (matches existing
    "silence on failure" contract)
  - Timeout: 30s for GPU, 180s for CPU fallback
  - Only tries GPU if credential file exists, to avoid unnecessary SSH overhead
  - Does NOT modify the stable on-demand daemon or chattts_stable.py
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

# ── Reuse everything from chattts_voice_reply.py except synthesize() ──
from chattts_voice_reply import (  # noqa: E402
    WORKSPACE,
    DEFAULT_OUT_DIR,
    DEFAULT_PRESET,
    DEFAULT_TEMPO,
    MAX_TTS_CHARS,
    DEFAULT_MAX_NEW_TOKEN,
    TTS_TIMEOUT_SECONDS,
    clean_text_for_tts,
    choose_tempo,
    prune_expired_audio,
    stage_media_for_main_session,
)

GPU_SCRIPT = WORKSPACE / "scripts" / "chattts_seeta_gpu.py"
GPU_CRED_FILE = WORKSPACE / "credentials" / "ssh" / "seetacloud-chattts-westd.md"
GPU_TIMEOUT_SECONDS = 120  # 2 min for GPU cold-start + SSH + inference
STABLE_SH = WORKSPACE / "tools" / "chattts-on-demand" / "chattts-on-demand.sh"
STABLE_FALLBACK_SH = WORKSPACE / "tools" / "voice-reply" / "chattts-stable.sh"


def _synthesize_gpu(
    clean: str,
    preset: str,
    out_path: str,
) -> bool:
    """Try GPU synthesis via chattts_seeta_gpu.py subprocess.

    Returns True if GPU synthesis succeeded and out_path exists.
    """
    if not GPU_SCRIPT.exists():
        return False
    if not GPU_CRED_FILE.exists():
        return False

    try:
        gpu_py = str(GPU_SCRIPT.resolve())
        venv_py = Path.home() / ".local" / "share" / "openclaw-voice-venv311" / "bin" / "python3"

        if not venv_py.exists():
            venv_py = Path(sys.executable)

        result = subprocess.run(
            [str(venv_py), gpu_py, "--text", clean, "--preset", preset, "--tag", f"gpu-{uuid.uuid4().hex[:8]}"],
            capture_output=True,
            text=True,
            timeout=GPU_TIMEOUT_SECONDS,
        )

        if result.returncode != 0:
            return False

        # seeta_gpu.py prints the local output path as the last line of stdout
        gpu_output_path = None
        for line in reversed(result.stdout.strip().split("\n")):
            line = line.strip()
            if line and Path(line).exists():
                gpu_output_path = line
                break

        if not gpu_output_path:
            return False

        # Copy GPU output to the requested out_path
        import shutil
        shutil.copy2(gpu_output_path, out_path)
        return True

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError, Exception):
        # Any GPU error → fall back to local CPU
        return False


def _synthesize_local(
    clean: str,
    preset: str,
    tempo: float,
    max_new_token: int,
    out_path: str,
) -> bool:
    """Fallback: local CPU stable via on-demand.sh or stable.sh."""
    on_demand = str(STABLE_SH)
    if not Path(on_demand).exists():
        on_demand = str(STABLE_FALLBACK_SH)
        if not Path(on_demand).exists():
            return False

    try:
        result = subprocess.run(
            [
                on_demand, "--text", clean, "--out", out_path,
                "--preset", preset, "--tempo", str(tempo),
                "--max-new-token", str(max_new_token),
            ],
            capture_output=True,
            text=True,
            timeout=TTS_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and Path(out_path).exists():
            # on-demand.sh outputs "DONE: /path/to/file" on success
            return True
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def synthesize(
    text: str,
    preset: str = DEFAULT_PRESET,
    tempo: float = DEFAULT_TEMPO,
    max_new_token: int = DEFAULT_MAX_NEW_TOKEN,
    out_path: str | None = None,
    max_chars: int = MAX_TTS_CHARS,
) -> str | None:
    """
    GPU-first TTS synthesis with local CPU fallback.

    Same API contract as chattts_voice_reply.synthesize():
      - Returns path to generated audio, or None on complete failure
      - Silent on error — no crash logs propagated

    Strategy:
      1. Try remote GPU (SeetaCloud) first
      2. If GPU fails for any reason, fall back to local CPU stable
      3. If both fail, return None (caller falls back to text-only)
    """
    # 1. Preprocess text
    clean = clean_text_for_tts(text, max_chars=max_chars)
    if not clean:
        return None
    effective_tempo = choose_tempo(clean, tempo)

    # 2. Output path
    prune_expired_audio()
    if not out_path:
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = str(DEFAULT_OUT_DIR / f"voice-reply-{stamp}-{preset}-{uuid.uuid4().hex[:8]}.mp3")

    out_path = str(out_path)

    # 3. Try GPU first
    gpu_ok = _synthesize_gpu(clean, preset, out_path)
    if gpu_ok and Path(out_path).exists():
        return stage_media_for_main_session(out_path)

    # 4. GPU failed — fallback to local CPU stable
    local_ok = _synthesize_local(clean, preset, effective_tempo, max_new_token, out_path)
    if local_ok and Path(out_path).exists():
        return stage_media_for_main_session(out_path)

    # 5. Both failed
    return None


def main() -> None:
    """CLI entry point — same interface as chattts_voice_reply.py main()."""
    ap = argparse.ArgumentParser(
        description="ChatTTS GPU-first voice reply with local fallback",
    )
    ap.add_argument("--text", required=True, help="Reply text to synthesize")
    ap.add_argument("--preset", default=DEFAULT_PRESET,
                    help=f"Voice preset name (default: {DEFAULT_PRESET})")
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
        sys.exit(1)


if __name__ == "__main__":
    main()
