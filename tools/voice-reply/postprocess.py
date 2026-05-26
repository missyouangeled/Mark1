"""音频后处理管道 — 纯 ffmpeg 调用，无模型依赖"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from .engine.base import VoiceProfile


class AudioPostProcessor:
    """后处理管道：tempo / pitch / 静音裁剪 / 响度归一化。"""

    def __init__(self):
        self.FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

    def process(self, audio_path: str, profile: VoiceProfile) -> str:
        """
        输入原始音频 → 输出后处理后的 wav 路径。

        管道:
          1. tempo 调整 (rubberband, formant=preserved)
          2. pitch 校正 (semitone shift)
          3. 静音裁剪
          4. 响度归一化 (loudnorm)
        """
        in_path = Path(audio_path)
        if not in_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        out_path = in_path.with_suffix(".proc.wav")

        filters = []
        filter_labels = []

        # 1. tempo（需要调整时）
        if abs(profile.tempo - 1.0) > 0.01:
            filters.append(f"rubberband=tempo={profile.tempo:.3f}:formant=preserved")
            filter_labels.append(f"tempo={profile.tempo:.2f}")

        # 2. pitch（需要校正时）
        if abs(profile.pitch_semitones) > 0.05:
            filters.append(
                f"rubberband=pitch={profile.pitch_semitones:.2f}:formant=preserved"
            )
            filter_labels.append(f"pitch={profile.pitch_semitones:+.1f}semi")

        # 3. 静音裁剪
        filters.append("silenceremove=start_periods=1:stop_periods=-1")
        filter_labels.append("trim")

        # 4. 响度归一化
        filters.append("loudnorm=I=-16:LRA=11:TP=-1.5:linear=true")
        filter_labels.append("loudnorm")

        filter_chain = ",".join(filters)

        cmd = [
            self.FFMPEG, "-y",
            "-i", str(in_path),
            "-af", filter_chain,
            "-ar", "24000",
            "-ac", "1",
            str(out_path),
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                # 后处理失败 → 回退到原文件
                import shutil
                shutil.copy(in_path, out_path)
        except Exception:
            shutil.copy(in_path, out_path)

        if out_path.exists():
            return str(out_path)

        return audio_path
