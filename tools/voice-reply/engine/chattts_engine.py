"""ChatTTS 本地引擎 — 包装 chattts_voice_reply.py"""

from __future__ import annotations

import subprocess
import re
from pathlib import Path
from datetime import datetime

from .base import BaseEngine, EngineResult, VoiceProfile

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CHATTTS_PY = WORKSPACE / "tools" / "voice-reply" / "chattts_voice_reply.py"
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "voice-replies"


class ChatTTSEngine(BaseEngine):
    name = "chattts"
    priority = 2
    is_cloud = False

    def is_installed(self) -> bool:
        return CHATTTS_PY.exists()

    def health_check(self) -> bool:
        """轻量：检查 chattts-on-demand 环境存在。"""
        on_demand = WORKSPACE / "tools" / "chattts-on-demand" / "chattts-on-demand.sh"
        return on_demand.exists()

    def synthesize_all(
        self, texts: list[str], profile: VoiceProfile
    ) -> list[EngineResult]:
        results = []
        for text in texts:
            results.append(self._synthesize_one(text, profile))
        return results

    def _synthesize_one(self, text: str, profile: VoiceProfile) -> EngineResult:
        cmd = [
            "python3", str(CHATTTS_PY),
            "--text", text,
            "--preset", profile.preset,
            "--max-chars", "120",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            # chattts_voice_reply.py 成功时 stdout 最后一行是文件路径
            lines = stdout.splitlines()
            audio_path = ""
            for line in reversed(lines):
                line = line.strip()
                if line and Path(line).exists():
                    audio_path = line
                    break

            if not audio_path and result.returncode != 0:
                return EngineResult(
                    audio_path="",
                    engine_name=self.name,
                    success=False,
                    error=stderr or stdout or "synthesis failed",
                )

            if not audio_path:
                return EngineResult(
                    audio_path="",
                    engine_name=self.name,
                    success=False,
                    error="no output path found",
                )

            return EngineResult(
                audio_path=audio_path,
                engine_name=self.name,
                success=True,
            )
        except subprocess.TimeoutExpired:
            return EngineResult(
                audio_path="",
                engine_name=self.name,
                success=False,
                error="timeout (120s)",
            )
        except Exception as e:
            return EngineResult(
                audio_path="",
                engine_name=self.name,
                success=False,
                error=str(e),
            )
