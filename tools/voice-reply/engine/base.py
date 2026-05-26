"""引擎基类 + 数据模型"""

from __future__ import annotations

import dataclasses
import abc
from typing import Optional


@dataclasses.dataclass
class VoiceProfile:
    """语音参数包。逐块合成时同一 profile 保证音色一致。"""

    tempo: float = 1.0
    pitch_semitones: float = 0.0
    style: str = "natural"
    preset: str = "default"
    ref_audio: Optional[str] = None


@dataclasses.dataclass
class EngineResult:
    """单次引擎合成的结果"""

    audio_path: str
    duration_s: float = 0.0
    engine_name: str = ""
    success: bool = True
    error: str = ""


@dataclasses.dataclass
class HealthCacheEntry:
    """健康检查缓存条目"""

    healthy: bool
    checked_at_s: float
    reason: str = ""


class BaseEngine(abc.ABC):
    """引擎基类。新引擎只需实现 3 个方法。"""

    name: str = "base"
    priority: int = 99
    is_cloud: bool = False

    @abc.abstractmethod
    def is_installed(self) -> bool:
        """检查依赖是否存在（不跑合成，纯文件/命令检查）。"""
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        """轻量检查：依赖可访问、环境正常。不真跑合成。超时 3s。"""
        ...

    @abc.abstractmethod
    def synthesize_all(
        self, texts: list[str], profile: VoiceProfile
    ) -> list[EngineResult]:
        """批量合成。同一引擎一次处理全部分块，保证音色一致。失败抛异常。"""
        ...

    def synthesize_one(self, text: str, profile: VoiceProfile) -> EngineResult:
        """单条合成（内部调 synthesize_all）。"""
        results = self.synthesize_all([text], profile)
        return results[0] if results else EngineResult(
            audio_path="", engine_name=self.name, success=False, error="no result"
        )
