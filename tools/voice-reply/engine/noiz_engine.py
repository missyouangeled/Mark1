"""Noiz 云端引擎 — 包装 noiz-reply.sh"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from datetime import datetime

from .base import BaseEngine, EngineResult, VoiceProfile

WORKSPACE = Path.home() / ".openclaw" / "workspace"
NOIZ_SH = WORKSPACE / "tools" / "voice-reply" / "noiz-reply.sh"
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "voice-replies"
REF_AUDIO = Path.home() / ".local" / "share" / "openclaw-voice-reply" / "default-ref.mp3"


class NoizEngine(BaseEngine):
    name = "noiz"
    priority = 0
    is_cloud = True

    def is_installed(self) -> bool:
        return NOIZ_SH.exists() and REF_AUDIO.exists()

    def health_check(self) -> bool:
        """快速连通性检查。"""
        if not self.is_installed():
            return False
        try:
            import urllib.request
            req = urllib.request.Request("https://noiz.ai", method="HEAD")
            urllib.request.urlopen(req, timeout=3)
            return True
        except Exception:
            return False

    def synthesize_all(
        self, texts: list[str], profile: VoiceProfile
    ) -> list[EngineResult]:
        results = []
        for text in texts:
            results.append(self._synthesize_one(text, profile))
        return results

    def _synthesize_one(self, text: str, profile: VoiceProfile) -> EngineResult:
        out_dir = Path(DEFAULT_OUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_file = out_dir / f"noiz-{profile.style}-{ts}-{uuid.uuid4().hex[:6]}.mp3"

        cmd = [
            "bash", str(NOIZ_SH),
            "--text", text,
            "--style", profile.style,
            "--pitch-semitones", str(profile.pitch_semitones),
            "--out", str(out_file),
        ]

        if profile.ref_audio:
            cmd += ["--ref-audio", profile.ref_audio]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "VOICE_STYLE": profile.style},
            )
            if result.returncode != 0 or not out_file.exists():
                return EngineResult(
                    audio_path="",
                    engine_name=self.name,
                    success=False,
                    error=result.stderr.strip() or "output not found",
                )
            return EngineResult(
                audio_path=str(out_file),
                engine_name=self.name,
                success=True,
            )
        except subprocess.TimeoutExpired:
            return EngineResult(
                audio_path="",
                engine_name=self.name,
                success=False,
                error="timeout (60s)",
            )
        except Exception as e:
            return EngineResult(
                audio_path="",
                engine_name=self.name,
                success=False,
                error=str(e),
            )
