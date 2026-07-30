"""G10/G11 测试：LLM 统计 + metrics 输出。"""

import json
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

import pytest


class TestArmorLLMStats:
    """G10: LLM 压缩成功率统计 + fallback SLO 告警。"""

    def test_empty_actions_returns_zeros(self, tmp_path, mocker):
        """没有 actions.jsonl 时返回全零。"""
        mocker.patch("mark42.armor.ARMOR_STATE", tmp_path)
        from mark42.armor import armor_llm_stats
        result = armor_llm_stats()
        assert result["total"] == 0
        assert result["llmRate"] == 0.0
        assert result["sloBreached"] is False

    def test_llm_success_counted(self, tmp_path, mocker):
        """LLM 路径的压缩被正确计数。"""
        actions = tmp_path / "actions.jsonl"
        lines = []
        for _ in range(3):
            lines.append(json.dumps({"action": "compress", "compactMethod": "llm-analyze"}))
        for _ in range(1):
            lines.append(json.dumps({"action": "compress", "compactMethod": "heuristic-fallback"}))
        actions.write_text("\n".join(lines) + "\n")

        mocker.patch("mark42.armor.ARMOR_STATE", tmp_path)
        from mark42.armor import armor_llm_stats
        result = armor_llm_stats()
        assert result["llmSuccess"] == 3
        assert result["fallback"] == 1
        assert result["llmRate"] == 75.0
        assert result["fallbackRate"] == 25.0

    def test_slo_breach_detected(self, tmp_path, mocker):
        """fallback 率超阈值时 sloBreached=True。"""
        actions = tmp_path / "actions.jsonl"
        lines = []
        for _ in range(6):
            lines.append(json.dumps({"action": "compress", "compactMethod": "heuristic-fallback"}))
        for _ in range(2):
            lines.append(json.dumps({"action": "compress", "compactMethod": "llm-analyze"}))
        actions.write_text("\n".join(lines) + "\n")

        mocker.patch("mark42.armor.ARMOR_STATE", tmp_path)
        from mark42.armor import armor_llm_stats
        result = armor_llm_stats()
        assert result["sloBreached"] is True
        assert result["fallbackRate"] == 75.0

    def test_window_limit(self, tmp_path, mocker):
        """window 参数限制统计范围。"""
        actions = tmp_path / "actions.jsonl"
        lines = []
        for _ in range(10):
            lines.append(json.dumps({"action": "compress", "compactMethod": "llm-analyze"}))
        for _ in range(5):
            lines.append(json.dumps({"action": "compress", "compactMethod": "heuristic-fallback"}))
        actions.write_text("\n".join(lines) + "\n")

        mocker.patch("mark42.armor.ARMOR_STATE", tmp_path)
        from mark42.armor import armor_llm_stats
        result = armor_llm_stats(window=5)
        # 只看最后 5 条（全是 fallback）
        assert result["fallback"] == 5
        assert result["llmSuccess"] == 0

    def test_skips_non_compress_actions(self, tmp_path, mocker):
        """非 compress 的 action 行被跳过。"""
        actions = tmp_path / "actions.jsonl"
        lines = [
            json.dumps({"action": "check", "compactMethod": "llm-analyze"}),
            json.dumps({"action": "compress", "compactMethod": "llm-analyze"}),
        ]
        actions.write_text("\n".join(lines) + "\n")

        mocker.patch("mark42.armor.ARMOR_STATE", tmp_path)
        from mark42.armor import armor_llm_stats
        result = armor_llm_stats()
        assert result["total"] == 1
        assert result["llmSuccess"] == 1

    def test_none_method_treated_as_other(self, tmp_path, mocker):
        """compactMethod=None 归入 other。"""
        actions = tmp_path / "actions.jsonl"
        lines = [
            json.dumps({"action": "compress", "compactMethod": None}),
            json.dumps({"action": "compress", "compactMethod": "openclaw-sessions-compact"}),
        ]
        actions.write_text("\n".join(lines) + "\n")

        mocker.patch("mark42.armor.ARMOR_STATE", tmp_path)
        from mark42.armor import armor_llm_stats
        result = armor_llm_stats()
        assert result["other"] == 2
        assert result["llmSuccess"] == 0
        assert result["fallback"] == 0
