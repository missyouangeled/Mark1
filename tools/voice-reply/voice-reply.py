#!/usr/bin/env python3
"""
贾维斯语音回复 CLI 主入口

用法:
  python3 tools/voice-reply/voice-reply.py --text '你好' --scene warm
  python3 tools/voice-reply/voice-reply.py --text '想你了' --scene tender
  python3 tools/voice-reply/voice-reply.py --text '晚安' --scene night --prefer-local

输出: agentReply 字符串（可直接注入 OpenClaw 会话）
  --json-output 时输出 JSON
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 确保 tools/ 在 sys.path 中（voice_reply 是 voice-reply 的符号链接）
_TOOLS_DIR = str(Path(__file__).resolve().parent.parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from voice_reply.orchestrator import VoiceOrchestrator  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[voice-reply] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="贾维斯语音回复 — 统一 CLI 入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
场景预设:
  morning   tempo=0.85  warm    (早安/开场)
  tender    tempo=0.80  gentle  (想你了/温柔)
  night     tempo=0.78  late-night (晚安)
  warm      tempo=1.05  natural (默认/自然)
  default   tempo=1.10  natural (无场景时)

示例:
  python3 tools/voice-reply/voice-reply.py --text '早上好，我在呢。' --scene morning
  python3 tools/voice-reply/voice-reply.py --text '我也想你了。' --scene tender
  python3 tools/voice-reply/voice-reply.py --text '你好' --prefer-local
        """,
    )
    parser.add_argument(
        "--text", "-t", required=True, help="要合成的文本"
    )
    parser.add_argument(
        "--scene", "-s",
        choices=["morning", "tender", "night", "warm", "default"],
        default="default",
        help="场景预设（默认: default）",
    )
    parser.add_argument(
        "--prefer-local", action="store_true",
        help="优先本地引擎（跳过 Noiz 云端）",
    )
    parser.add_argument(
        "--json-output", action="store_true",
        help="以 JSON 格式输出结果",
    )
    parser.add_argument(
        "--print-reply", action="store_true",
        help="只打印 agentReply 字符串（适合脚本调用）",
    )

    args = parser.parse_args()

    orch = VoiceOrchestrator()
    result = orch.speak(
        text=args.text,
        scene=args.scene if args.scene != "default" else None,
        prefer_local=args.prefer_local,
    )

    if args.json_output:
        print(json.dumps({
            "success": result.success,
            "engine": result.engine_used,
            "audio_paths": result.audio_paths,
            "error": result.error,
            "agentReply": result.agent_reply,
        }, ensure_ascii=False, indent=2))
    elif args.print_reply:
        print(result.agent_reply)
    else:
        print(result.agent_reply)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
