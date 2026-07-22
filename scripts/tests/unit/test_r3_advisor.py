"""
R3 验收测试 · 战甲主动交流意识

验证 v3 §3.3-3.5 的 4 类对话场景和 advisor 调用链路：
- 场景 A: 自检后不确定是不是真问题
- 场景 B: 知道坏了但修法不确定
- 场景 C: 新类型异常（第一次见）
- 场景 D: 学过的错误走档案
- advisor 未开启 -> 降级到问用户
- advisor 响应解析（verdict/confidence/reasoning/modified_plan）
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from mark42_modules.advisor_client import (
    AdvisorClient,
    AdvisorResult,
    AdvisorVerdict,
    build_scenario_a_prompt,
    build_scenario_b_prompt,
    build_scenario_c_prompt,
    build_scenario_d_prompt,
    ADVISOR_SYSTEM_PROMPT,
)
from mark42_modules.llm_provider import ChatMessage, ChatResponse


# ── 辅助函数 ──


def _make_config(advisor_enabled: bool = False, **advisor_kwargs) -> dict:
    """构造测试配置。"""
    advisor = {
        "enabled": advisor_enabled,
        "runtime": "api",
        "model": advisor_kwargs.get("model", "gpt-4o"),
        "base_url": advisor_kwargs.get("base_url", "https://api.openai.com/v1"),
        "api_key": advisor_kwargs.get("api_key", "sk-test"),
        "confidence_threshold": advisor_kwargs.get("confidence_threshold", 0.7),
        "timeout_seconds": advisor_kwargs.get("timeout_seconds", 10),
    }
    return {
        "mark42": {
            "consciousness": {"runtime": "stub", "model": "stub"},
            "fallback_chain": ["stub"],
            "advisor": advisor,
        }
    }


def _make_chat_response(verdict: str = "approve", confidence: float = 0.9, reasoning: str = "OK", modified_plan=None) -> ChatResponse:
    """构造模拟的 ChatResponse。"""
    content = json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "modified_plan": modified_plan,
    })
    return ChatResponse(content=content, model="test-model")


# ── R3 验收测试 ──


class TestR3AdvisorScenarios:
    """R3: 战甲主动交流 4 类场景。"""

    def test_scenario_a_prompt(self):
        """场景 A: 构造不确定问题的 prompt。"""
        issue = {"source": "heartbeat", "category": "stale", "msg": "25分钟没动"}
        assessment = {"certainty": "unknown"}
        prompt = build_scenario_a_prompt(issue, assessment)
        assert "heartbeat" in prompt
        assert "25分钟没动" in prompt
        assert "不确定" in prompt or "不确定" in prompt.lower()

    def test_scenario_b_prompt(self):
        """场景 B: 构造修复方案确认的 prompt。"""
        issue = {"source": "embed", "category": "index_missing", "msg": "索引丢失"}
        plan = {"steps": ["停 sidecar", "重建索引", "启 sidecar"], "estimated_time": "180秒"}
        prompt = build_scenario_b_prompt(issue, plan)
        assert "停 sidecar" in prompt
        assert "180秒" in prompt

    def test_scenario_c_prompt(self):
        """场景 C: 构造新类型异常的 prompt。"""
        issue = {"source": "scratch", "category": "unknown_file", "msg": "出现 .tmp-xyz 文件"}
        prompt = build_scenario_c_prompt(issue)
        assert ".tmp-xyz" in prompt
        assert "新类型" in prompt or "第一次" in prompt

    def test_scenario_d_prompt(self):
        """场景 D: 构造档案复用的 prompt。"""
        entry = {"id": "ERR-007", "category": "index_truncated", "diagnosis": "索引截断", "resolution": {"method": "重建"}}
        prompt = build_scenario_d_prompt(entry)
        assert "ERR-007" in prompt
        assert "索引截断" in prompt


class TestR3AdvisorClient:
    """R3: AdvisorClient 核心功能。"""

    def test_advisor_disabled_returns_fallback(self):
        """advisor 未开启 -> 返回 fallback（问用户）。"""
        cfg = _make_config(advisor_enabled=False)
        client = AdvisorClient(cfg)
        result = client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})
        assert not result.success
        assert result.fallback_action == "ask_user"
        assert result.should_ask_user

    def test_advisor_enabled_with_mock_response(self):
        """advisor 开启 + mock 响应 -> 解析成功。"""
        cfg = _make_config(advisor_enabled=True)
        client = AdvisorClient(cfg)

        # mock provider
        client.provider = MagicMock()
        client.provider.chat.return_value = _make_chat_response(
            verdict="approve", confidence=0.9, reasoning="安全"
        )

        result = client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})
        assert result.success
        assert result.verdict.is_approve
        assert result.verdict.confidence == 0.9
        assert not result.should_ask_user

    def test_advisor_reject_verdict(self):
        """advisor 返回 reject -> 问用户。"""
        cfg = _make_config(advisor_enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MagicMock()
        client.provider.chat.return_value = _make_chat_response(
            verdict="reject", confidence=0.95, reasoning="危险"
        )

        result = client.ask("b", issue={"source": "test"}, plan={"steps": ["危险操作"]})
        assert result.success
        assert result.verdict.is_reject
        assert result.should_ask_user

    def test_advisor_modify_verdict(self):
        """advisor 返回 modify -> 有 modified_plan。"""
        cfg = _make_config(advisor_enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MagicMock()
        client.provider.chat.return_value = _make_chat_response(
            verdict="modify",
            confidence=0.8,
            reasoning="需要调整",
            modified_plan={"steps": ["改后步骤"], "changes": "改了第二步"},
        )

        result = client.ask("b", issue={"source": "test"}, plan={"steps": ["原步骤"]})
        assert result.success
        assert result.verdict.is_modify
        assert result.verdict.modified_plan is not None
        assert not result.should_ask_user

    def test_advisor_low_confidence_falls_back(self):
        """advisor 低置信度 -> 降级到问用户。"""
        cfg = _make_config(advisor_enabled=True, confidence_threshold=0.9)
        client = AdvisorClient(cfg)
        client.provider = MagicMock()
        client.provider.chat.return_value = _make_chat_response(
            verdict="approve", confidence=0.5, reasoning="不太确定"
        )

        result = client.ask("a", issue={"source": "test"}, assessment={})
        assert result.success
        assert result.should_ask_user  # 低置信度问用户

    def test_advisor_api_error_falls_back(self):
        """advisor API 调用失败 -> 降级到问用户。"""
        cfg = _make_config(advisor_enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MagicMock()
        client.provider.chat.side_effect = Exception("API 超时")

        result = client.ask("c", issue={"source": "test"})
        assert not result.success
        assert result.should_ask_user
        assert "api_error" in (result.fallback_reason or "")

    def test_advisor_parse_invalid_json(self):
        """advisor 返回非法 JSON -> 降级到问用户。"""
        cfg = _make_config(advisor_enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MagicMock()
        client.provider.chat.return_value = ChatResponse(content="这不是JSON", model="test")

        result = client.ask("a", issue={"source": "test"}, assessment={})
        assert not result.success
        assert result.should_ask_user

    def test_advisor_parse_markdown_wrapped_json(self):
        """advisor 返回 markdown 包裹的 JSON -> 正常解析。"""
        cfg = _make_config(advisor_enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MagicMock()

        json_content = json.dumps({"verdict": "approve", "confidence": 0.9, "reasoning": "OK"})
        wrapped = f"```json\n{json_content}\n```"
        client.provider.chat.return_value = ChatResponse(content=wrapped, model="test")

        result = client.ask("a", issue={"source": "test"}, assessment={})
        assert result.success
        assert result.verdict.is_approve


class TestR3AdvisorHealthCheck:
    """R3: advisor 健康检查。"""

    def test_health_check_disabled(self):
        """未开启时健康检查返回 disabled。"""
        cfg = _make_config(advisor_enabled=False)
        client = AdvisorClient(cfg)
        health = client.health_check()
        assert health["enabled"] is False
        assert health["configured"] is False

    def test_health_check_enabled(self):
        """开启时健康检查返回正确配置。"""
        cfg = _make_config(advisor_enabled=True, model="gpt-4o", base_url="https://api.openai.com/v1")
        client = AdvisorClient(cfg)
        health = client.health_check()
        assert health["enabled"] is True
        assert health["configured"] is True
        assert health["model"] == "gpt-4o"
        assert health["has_api_key"] is True


class TestR3ConsciousnessIntegration:
    """R3: consciousness.py 与 advisor 集成。"""

    def test_consciousness_init_without_advisor(self):
        """consciousness 没配 advisor 时正常初始化。"""
        from mark42_modules.consciousness import Consciousness

        cfg = _make_config(advisor_enabled=False)
        c = Consciousness(config=cfg)
        assert c is not None

    def test_consciousness_init_with_advisor(self):
        """consciousness 配了 advisor 时正常初始化。"""
        from mark42_modules.consciousness import Consciousness

        cfg = _make_config(advisor_enabled=True)
        c = Consciousness(config=cfg)
        assert c is not None

    def test_consciousness_self_check(self):
        """C1 自检能力正常。"""
        from mark42_modules.consciousness import Consciousness

        cfg = _make_config()
        c = Consciousness(config=cfg)
        result = c.self_check()
        assert result is not None

    def test_consciousness_handle_issue_unknown(self):
        """handle_issue 处理未知问题。"""
        from mark42_modules.consciousness import Consciousness

        cfg = _make_config()
        c = Consciousness(config=cfg)
        issue = {"source": "test", "category": "unknown", "msg": "测试"}
        result = c.handle_issue(issue, dry_run=True)
        assert result is not None
        assert "path" in result or "action" in result
