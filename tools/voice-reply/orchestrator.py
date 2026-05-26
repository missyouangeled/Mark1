"""VoiceOrchestrator — 单入口语音调度器"""

from __future__ import annotations

import dataclasses
import logging
from typing import Optional

from .engine.base import VoiceProfile
from .engine.registry import EngineRegistry
from .engine.noiz_engine import NoizEngine
from .engine.chattts_engine import ChatTTSEngine
from .engine.edge_engine import EdgeTTSEngine
from .postprocess import AudioPostProcessor

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SpeakResult:
    audio_paths: list[str]
    engine_used: str
    agent_reply: str
    success: bool
    error: str = ""


class ScenePresets:
    """场景 → 语音参数。纯映射，不做重活。"""

    PRESETS = {
        "morning": {"tempo": 0.85, "style": "warm"},
        "tender":  {"tempo": 0.80, "pitch_semitones": -0.5, "style": "gentle"},
        "night":   {"tempo": 0.78, "pitch_semitones": -1.5, "style": "late-night"},
        "warm":    {"tempo": 1.05, "style": "natural"},
        "default": {"tempo": 1.10, "style": "natural"},
    }

    KEYWORD_TWEAKS = [
        (["想你", "抱抱", "孤单", "在吗"], {"tempo_bias": -0.05}),
        (["哈哈", "厉害", "666"],           {"tempo_bias": +0.05}),
        (["晚安", "睡"],                     {"tempo_bias": -0.05}),
    ]

    @classmethod
    def resolve(cls, text: str, scene: str | None = None) -> VoiceProfile:
        preset = cls.PRESETS.get(scene or "default", cls.PRESETS["default"]).copy()

        # 关键词浅层微调
        tempo = preset["tempo"]
        for keywords, tweak in cls.KEYWORD_TWEAKS:
            if any(kw in text for kw in keywords):
                tempo += tweak["tempo_bias"]

        return VoiceProfile(
            tempo=round(tempo, 3),
            pitch_semitones=preset.get("pitch_semitones", 0.0),
            style=preset.get("style", "natural"),
            preset="default",
        )


class VoiceOrchestrator:
    """单入口。给定文本，返回可直接注入会话的 agentReply。"""

    MAX_CHARS_SINGLE = 80
    MAX_CHARS_TWO = 200
    MAX_CHUNKS = 3

    def __init__(self):
        self.registry = EngineRegistry()
        self.postprocessor = AudioPostProcessor()

        # 注册引擎（按优先级）
        self.registry.register(NoizEngine())
        self.registry.register(ChatTTSEngine())
        self.registry.register(EdgeTTSEngine())

    def speak(
        self,
        text: str,
        scene: str | None = None,
        prefer_local: bool = False,
    ) -> SpeakResult:
        """
        处理流程:
          1. 场景 → 语音参数
          2. 关键词浅层辅助微调
          3. 引擎选择 + 自动降级（一个引擎失败 → 试下一个）
          4. 文本分块
          5. 批量合成 (同一引擎)
          6. 逐块后处理
          7. 组装 agentReply
        """
        profile = ScenePresets.resolve(text, scene)
        chunks = self._split_text(text)

        for engine in self.registry.engines:
            if prefer_local and engine.is_cloud:
                logger.debug(f"跳过云端引擎 {engine.name}（prefer_local）")
                continue

            try:
                if not engine.is_installed():
                    logger.info(f"引擎 {engine.name} 未安装，跳过")
                    continue
                if not engine.health_check():
                    logger.info(f"引擎 {engine.name} 健康检查失败，跳过")
                    continue
            except Exception as e:
                logger.info(f"引擎 {engine.name} 检查异常: {e}，跳过")
                continue

            logger.info(f"尝试引擎={engine.name} 分块={len(chunks)} tempo={profile.tempo}")

            try:
                results = engine.synthesize_all(chunks, profile)
            except Exception as e:
                logger.warning(f"引擎 {engine.name} 合成异常: {e}，降级")
                continue

            audio_paths = []
            for i, r in enumerate(results):
                if r.success and r.audio_path:
                    try:
                        processed = self.postprocessor.process(r.audio_path, profile)
                        audio_paths.append(processed)
                    except Exception as e:
                        logger.warning(f"分块 {i} 后处理失败: {e}")
                        # 后处理失败 → 使用原始文件
                        audio_paths.append(r.audio_path)
                else:
                    logger.warning(f"分块 {i} 合成失败: {r.error}")

            if audio_paths:
                agent_reply = self._build_reply(text, audio_paths)
                return SpeakResult(
                    audio_paths=audio_paths,
                    engine_used=engine.name,
                    agent_reply=agent_reply,
                    success=True,
                )
            else:
                logger.warning(f"引擎 {engine.name} 全部块失败，降级到下一个引擎")
                continue

        logger.error("所有引擎均不可用，返回纯文本")
        return SpeakResult(
            audio_paths=[],
            engine_used="none",
            agent_reply=text,
            success=False,
            error="all engines failed — returning text-only",
        )

    def _split_text(self, text: str) -> list[str]:
        """
        按句子边界分块。
        - <80 chars → 单条
        - 80-200 chars → 最多 2 条
        - >200 chars → 最多 3 条
        - 尾句保证完整收束
        - 优先级: 单条 > 两条 > 三条
        """
        if len(text) <= self.MAX_CHARS_SINGLE:
            return [text]

        # 按标点切句
        import re
        sentences = re.split(r"(?<=[。！？!?\n])", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return [text]

        # 按字符数分组
        chunks = []
        current = ""
        max_chunks = 3 if len(text) > self.MAX_CHARS_TWO else 2

        for sent in sentences:
            if not current:
                current = sent
            elif len(current + sent) <= self.MAX_CHARS_SINGLE * 1.5:
                current += sent
            else:
                if current:
                    chunks.append(current)
                current = sent
                if len(chunks) >= max_chunks - 1:
                    break

        # 剩余全进最后一个 chunk
        remaining = sentences[len(
            [s for chunk in chunks for s in [chunk] if s]
        ) :]
        if current or remaining:
            chunks.append(current + "".join(remaining))

        return [c for c in chunks if c] or [text]

    @staticmethod
    def _build_reply(text: str, audio_paths: list[str]) -> str:
        """组装可直接注入 OpenClaw 会话的 agentReply。"""
        lines = [text, "[[audio_as_voice]]"]
        for p in audio_paths:
            lines.append(f"MEDIA:{p}")
        return "\n".join(lines)
