#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

# GPU-first backend: if OPENCLAW_VOICE_REPLY_BACKEND=gpu-first, import from
# the GPU-first wrapper that falls back to CPU stable on failure.
# Otherwise, default to the existing local CPU stable path.
_BACKEND = os.environ.get("OPENCLAW_VOICE_REPLY_BACKEND", "local-stable").strip()
if _BACKEND == "gpu-first":
    from chattts_gpu_first_wrapper import (  # type: ignore  # noqa: E402
        synthesize,
    )
else:
    from chattts_voice_reply import (  # noqa: E402
        synthesize,
    )

from chattts_voice_reply import (  # noqa: E402
    DEFAULT_FIRST_CHUNK_TARGET,
    DEFAULT_MAX_CHUNK_CHARS,
    DEFAULT_MAX_NEW_TOKEN,
    DEFAULT_PRESET,
    DEFAULT_TEMPO,
    DEFAULT_OUT_DIR,
    MAX_TTS_CHARS,
    split_text_for_tts_chunks,
)


DEFAULT_AUDIO_EXT = os.environ.get("OPENCLAW_VOICE_REPLY_FORMAT", "wav").strip().lower() or "wav"
if DEFAULT_AUDIO_EXT not in {"wav", "mp3"}:
    DEFAULT_AUDIO_EXT = "wav"


def build_chunk_out_path(base_dir: Path, preset: str, index: int, chunk_count: int) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    token = uuid.uuid4().hex[:8]
    return str(base_dir / f"voice-reply-chunked-{stamp}-{preset}-{token}-part{index + 1:02d}-of-{chunk_count:02d}.{DEFAULT_AUDIO_EXT}")


def build_media_reply_text(text: str, path: str) -> str:
    lines = [text.strip(), "", "[[audio_as_voice]]", f"MEDIA:{path}"]
    return "\n".join(line for line in lines if line is not None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize chunked voice reply with first chunk emitted early")
    parser.add_argument("--text", required=True)
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    parser.add_argument("--tempo", type=float, default=DEFAULT_TEMPO)
    parser.add_argument("--max-new-token", type=int, default=DEFAULT_MAX_NEW_TOKEN)
    parser.add_argument("--max-chars", type=int, default=MAX_TTS_CHARS)
    parser.add_argument("--first-chunk-target", type=int, default=DEFAULT_FIRST_CHUNK_TARGET)
    parser.add_argument("--max-chunk-chars", type=int, default=DEFAULT_MAX_CHUNK_CHARS)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--message-plan", action="store_true", help="Emit main-session-ready reply payloads in JSON")
    args = parser.parse_args()

    chunks = split_text_for_tts_chunks(
        args.text,
        first_chunk_target=args.first_chunk_target,
        max_chunk_chars=args.max_chunk_chars,
    )
    if not chunks:
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, str]] = []

    for index, chunk in enumerate(chunks):
        out_path = build_chunk_out_path(out_dir, args.preset, index, len(chunks))
        rendered_path = synthesize(
            text=chunk,
            preset=args.preset,
            tempo=args.tempo,
            max_new_token=args.max_new_token,
            out_path=out_path,
            max_chars=max(len(chunk), args.max_chars),
        )
        if not rendered_path:
            print(json.dumps({
                "ok": False,
                "failedChunkIndex": index,
                "failedChunkText": chunk,
                "rendered": rendered,
            }, ensure_ascii=False), flush=True)
            return 1

        item = {
            "index": str(index),
            "text": chunk,
            "path": rendered_path,
        }
        rendered.append(item)
        if index == 0 and not args.message_plan:
            print(json.dumps({
                "event": "first_chunk_ready",
                "chunk": item,
                "chunkCount": len(chunks),
            }, ensure_ascii=False), flush=True)

    payload = {
        "ok": True,
        "chunkCount": len(chunks),
        "firstChunk": rendered[0],
        "remainingChunks": rendered[1:],
        "allChunks": rendered,
    }

    if args.message_plan:
        payload["firstReply"] = build_media_reply_text(rendered[0]["text"], rendered[0]["path"])
        payload["followupReplies"] = [
            build_media_reply_text(item["text"], item["path"])
            for item in rendered[1:]
        ]

    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
