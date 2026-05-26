"""msedge-tts 兜底引擎 — 包装 tts.mjs"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from datetime import datetime

from .base import BaseEngine, EngineResult, VoiceProfile

WORKSPACE = Path.home() / ".openclaw" / "workspace"
TTS_MJS = WORKSPACE / "tools" / "voice-reply" / "tts.mjs"
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "voice-replies"


class EdgeTTSEngine(BaseEngine):
    name = "edge-tts"
    priority = 3
    is_cloud = True  # 调微软云端 TTS

    VOICES: dict[str, str] = {
        "default": "zh-CN-XiaoxiaoNeural",
        "warm": "zh-CN-XiaoxiaoNeural",
        "gentle": "zh-CN-XiaoxiaoNeural",
        "bright": "zh-CN-XiaoyiNeural",
        "late-night": "zh-CN-XiaoxiaoNeural",
    }

    def is_installed(self) -> bool:
        return TTS_MJS.exists()

    def health_check(self) -> bool:
        # msedge-tts 是 Node.js 包，检查 node_modules 存在即可
        node_modules = WORKSPACE / "tools" / "voice-reply" / "node_modules" / "msedge-tts"
        return node_modules.exists()

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
        out_file = out_dir / f"edge-{profile.style}-{ts}-{uuid.uuid4().hex[:6]}.mp3"

        voice = self.VOICES.get(profile.style, self.VOICES["default"])
        rate = self._tempo_to_rate(profile.tempo)

        cmd = [
            "node", str(TTS_MJS),
            "--text", text,
            "--out", str(out_file),
            "--voice", voice,
            "--rate", rate,
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
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
                error="timeout (30s)",
            )
        except Exception as e:
            return EngineResult(
                audio_path="",
                engine_name=self.name,
                success=False,
                error=str(e),
            )

    @staticmethod
    def _tempo_to_rate(tempo: float) -> str:
        """tempo 1.0 → rate +0%, 0.8 → -20%, 1.2 → +20%"""
        pct = int((tempo - 1.0) * 100)
        return f"+{pct}%" if pct >= 0 else f"{pct}%"
