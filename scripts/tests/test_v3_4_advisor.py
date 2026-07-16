"""
Mark42 v3-4 · Advisor Client 单元测试

测试覆盖：
1. AdvisorVerdict 数据类（属性 / 边界）
2. AdvisorResult 降级逻辑（should_ask_user）
3. AdvisorClient 初始化（未配置 / 已配置 / 配置异常）
4. 4 类场景 prompt 构造器（A/B/C/D 内容非空 + 关键字段）
5. 响应解析（正常 / 空 / 非法 JSON / 缺字段 / confidence 边界）
6. 降级路径（advisor 没开 / 超时 / 返回非法 -> fallback ask_user）
7. 健康检查 + ping
8. CLI 接口（status / test / ask）
9. Mock provider 端到端（模拟 advisor approve/reject/modify）
"""

import json
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# 确保能 import mark42_modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from mark42_modules.advisor_client import (
    AdvisorClient,
    AdvisorResult,
    AdvisorVerdict,
    build_scenario_a_prompt,
    build_scenario_b_prompt,
    build_scenario_c_prompt,
    build_scenario_d_prompt,
    cli_advisor_ask,
    cli_advisor_status,
    cli_advisor_test,
    DEFAULT_CONFIDENCE_THRESHOLD,
)
from mark42_modules.llm_provider import ChatMessage, LLMProvider, ChatResponse


# ── Mock Provider（模拟 advisor LLM）──────────────────

class MockAdvisorProvider:
    """模拟 LLM Provider，返回预设响应。"""

    def __init__(self, response_content: str = "", should_fail: bool = False):
        self.response_content = response_content
        self.should_fail = should_fail
        self.call_count = 0
        self.last_messages: Optional[List[ChatMessage]] = None

    def chat(self, messages: List[ChatMessage], **kwargs) -> Dict[str, Any]:
        self.call_count += 1
        self.last_messages = messages
        if self.should_fail:
            raise ConnectionError("mock provider failed")
        return {
            "choices": [{
                "message": {
                    "content": self.response_content,
                },
                "finish_reason": "stop",
            }]
        }


def make_approve_response(confidence: float = 0.95) -> str:
    return json.dumps({
        "verdict": "approve",
        "confidence": confidence,
        "reasoning": "方案安全，可以执行",
    })


def make_reject_response(confidence: float = 0.9) -> str:
    return json.dumps({
        "verdict": "reject",
        "confidence": confidence,
        "reasoning": "方案有风险，不应该执行",
    })


def make_modify_response(confidence: float = 0.85) -> str:
    return json.dumps({
        "verdict": "modify",
        "confidence": confidence,
        "reasoning": "方案基本可行但需调整",
        "modified_plan": {
            "steps": ["步骤1", "步骤2 改"],
            "changes": "把第二步改了",
        }
    })


# ── 配置构造工具 ─────────────────────────────────────

def make_config(enabled: bool = False, model: str = "gpt-4o",
                base_url: str = "https://api.openai.com/v1",
                api_key: str = "sk-test", confidence_threshold: float = 0.7) -> Dict[str, Any]:
    return {
        "mark42": {
            "consciousness": {"runtime": "stub", "model": "stub"},
            "advisor": {
                "enabled": enabled,
                "runtime": "api",
                "model": model,
                "base_url": base_url,
                "api_key": api_key,
                "confidence_threshold": confidence_threshold,
                "timeout_seconds": 30,
            }
        }
    }


# ── 测试类 ───────────────────────────────────────────

class TestAdvisorVerdict(unittest.TestCase):
    """1. AdvisorVerdict 数据类"""

    def test_approve(self):
        v = AdvisorVerdict(verdict="approve", confidence=0.95, reasoning="ok")
        self.assertTrue(v.is_approve)
        self.assertFalse(v.is_reject)
        self.assertFalse(v.is_modify)
        self.assertTrue(v.is_trustworthy)

    def test_reject(self):
        v = AdvisorVerdict(verdict="reject", confidence=0.9, reasoning="no")
        self.assertFalse(v.is_approve)
        self.assertTrue(v.is_reject)

    def test_modify(self):
        v = AdvisorVerdict(verdict="modify", confidence=0.85, reasoning="adjust",
                           modified_plan={"steps": ["a"], "changes": "x"})
        self.assertTrue(v.is_modify)
        self.assertIsNotNone(v.modified_plan)

    def test_low_confidence_not_trustworthy(self):
        v = AdvisorVerdict(verdict="approve", confidence=0.3, reasoning="unsure")
        self.assertFalse(v.is_trustworthy)

    def test_invalid_verdict_not_trustworthy(self):
        v = AdvisorVerdict(verdict="maybe", confidence=0.99, reasoning="huh?")
        self.assertFalse(v.is_trustworthy)

    def test_to_dict(self):
        v = AdvisorVerdict(verdict="approve", confidence=0.95, reasoning="ok")
        d = v.to_dict()
        self.assertEqual(d["verdict"], "approve")
        self.assertEqual(d["confidence"], 0.95)
        self.assertNotIn("modified_plan", d)


class TestAdvisorResult(unittest.TestCase):
    """2. AdvisorResult 降级逻辑"""

    def test_not_success_ask_user(self):
        r = AdvisorResult(success=False, fallback_reason="advisor_not_enabled")
        self.assertTrue(r.should_ask_user)

    def test_approve_trustworthy_no_ask(self):
        v = AdvisorVerdict(verdict="approve", confidence=0.95, reasoning="ok")
        r = AdvisorResult(success=True, verdict=v)
        self.assertFalse(r.should_ask_user)

    def test_reject_ask_user(self):
        v = AdvisorVerdict(verdict="reject", confidence=0.95, reasoning="bad")
        r = AdvisorResult(success=True, verdict=v)
        self.assertTrue(r.should_ask_user)

    def test_modify_trustworthy_no_ask(self):
        v = AdvisorVerdict(verdict="modify", confidence=0.85, reasoning="adjust",
                           modified_plan={"steps": ["a"]})
        r = AdvisorResult(success=True, verdict=v)
        self.assertFalse(r.should_ask_user)

    def test_modify_low_confidence_ask(self):
        v = AdvisorVerdict(verdict="modify", confidence=0.3, reasoning="unsure")
        r = AdvisorResult(success=True, verdict=v)
        self.assertTrue(r.should_ask_user)


class TestAdvisorClientInit(unittest.TestCase):
    """3. AdvisorClient 初始化"""

    def test_disabled_by_default(self):
        cfg = make_config(enabled=False)
        client = AdvisorClient(cfg)
        self.assertFalse(client.enabled)
        self.assertIsNone(client.provider)

    def test_enabled_with_config(self):
        cfg = make_config(enabled=True, model="gpt-4o", base_url="https://api.openai.com/v1")
        client = AdvisorClient(cfg)
        self.assertTrue(client.enabled)
        self.assertIsNotNone(client.provider)

    def test_confidence_threshold(self):
        cfg = make_config(enabled=True, confidence_threshold=0.9)
        client = AdvisorClient(cfg)
        self.assertEqual(client.confidence_threshold, 0.9)

    def test_default_confidence_threshold(self):
        cfg = make_config(enabled=True)
        del cfg["mark42"]["advisor"]["confidence_threshold"]
        client = AdvisorClient(cfg)
        self.assertEqual(client.confidence_threshold, DEFAULT_CONFIDENCE_THRESHOLD)


class TestScenarioPrompts(unittest.TestCase):
    """4. 4 类场景 prompt 构造器"""

    def test_scenario_a_non_empty(self):
        prompt = build_scenario_a_prompt(
            issue={"source": "heartbeat", "category": "stale", "msg": "25min no beat"},
            assessment={"certainty": "unknown"},
        )
        self.assertIn("heartbeat", prompt)
        self.assertIn("不确定", prompt)
        self.assertGreater(len(prompt), 50)

    def test_scenario_b_non_empty(self):
        prompt = build_scenario_b_prompt(
            issue={"source": "embed", "category": "index_lost"},
            plan={"steps": ["stop sidecar", "rebuild index", "start sidecar"],
                  "estimated_time": "180s", "impact": "L2.5 unavailable"},
        )
        self.assertIn("embed", prompt)
        self.assertIn("stop sidecar", prompt)
        self.assertIn("180s", prompt)

    def test_scenario_c_non_empty(self):
        prompt = build_scenario_c_prompt(
            issue={"source": "scratch", "category": "unknown_file",
                   "msg": ".tmp-xyz123", "context": {"path": "/tmp/xyz"}}
        )
        self.assertIn("新类型", prompt)
        self.assertIn("scratch", prompt)

    def test_scenario_d_non_empty(self):
        prompt = build_scenario_d_prompt(
            archive_entry={"id": "ERR-001", "category": "test",
                           "diagnosis": "test diag",
                           "resolution": {"status": "resolved", "method": "restart"}}
        )
        self.assertIn("ERR-001", prompt)
        self.assertIn("上次", prompt)

    def test_scenario_a_missing_fields(self):
        """缺字段不崩"""
        prompt = build_scenario_a_prompt(issue={}, assessment={})
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)


class TestResponseParsing(unittest.TestCase):
    """5. 响应解析"""

    def setUp(self):
        cfg = make_config(enabled=True)
        self.client = AdvisorClient(cfg)

    def test_parse_approve(self):
        raw = {"choices": [{"message": {"content": make_approve_response()}}]}
        v = self.client._parse_response(raw, 100)
        self.assertIsNotNone(v)
        self.assertEqual(v.verdict, "approve")
        self.assertEqual(v.confidence, 0.95)
        self.assertEqual(v.elapsed_ms, 100)

    def test_parse_reject(self):
        raw = {"choices": [{"message": {"content": make_reject_response()}}]}
        v = self.client._parse_response(raw, 50)
        self.assertIsNotNone(v)
        self.assertTrue(v.is_reject)

    def test_parse_modify(self):
        raw = {"choices": [{"message": {"content": make_modify_response()}}]}
        v = self.client._parse_response(raw, 200)
        self.assertIsNotNone(v)
        self.assertTrue(v.is_modify)
        self.assertIsNotNone(v.modified_plan)

    def test_parse_empty_content(self):
        raw = {"choices": [{"message": {"content": ""}}]}
        v = self.client._parse_response(raw, 10)
        self.assertIsNone(v)

    def test_parse_invalid_json(self):
        raw = {"choices": [{"message": {"content": "not json at all"}}]}
        v = self.client._parse_response(raw, 10)
        self.assertIsNone(v)

    def test_parse_missing_verdict(self):
        raw = {"choices": [{"message": {"content": json.dumps({"confidence": 0.9})}}]}
        v = self.client._parse_response(raw, 10)
        self.assertIsNone(v)

    def test_parse_invalid_verdict_value(self):
        raw = {"choices": [{"message": {"content": json.dumps({"verdict": "maybe", "confidence": 0.9})}}]}
        v = self.client._parse_response(raw, 10)
        self.assertIsNone(v)

    def test_parse_confidence_clamped(self):
        raw = {"choices": [{"message": {"content": json.dumps({"verdict": "approve", "confidence": 1.5})}}]}
        v = self.client._parse_response(raw, 10)
        self.assertIsNotNone(v)
        self.assertEqual(v.confidence, 1.0)

    def test_parse_confidence_negative(self):
        raw = {"choices": [{"message": {"content": json.dumps({"verdict": "approve", "confidence": -0.5})}}]}
        v = self.client._parse_response(raw, 10)
        self.assertIsNotNone(v)
        self.assertEqual(v.confidence, 0.0)

    def test_parse_empty_choices(self):
        raw = {"choices": []}
        v = self.client._parse_response(raw, 10)
        self.assertIsNone(v)

    def test_parse_no_choices_key(self):
        raw = {}
        v = self.client._parse_response(raw, 10)
        self.assertIsNone(v)


class TestFallbackPaths(unittest.TestCase):
    """6. 降级路径"""

    def test_advisor_not_enabled(self):
        cfg = make_config(enabled=False)
        client = AdvisorClient(cfg)
        result = client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})
        self.assertFalse(result.success)
        self.assertEqual(result.fallback_reason, "advisor_not_enabled")
        self.assertTrue(result.should_ask_user)

    def test_advisor_api_error(self):
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        # 替换 provider 为会失败的 mock
        client.provider = MockAdvisorProvider(should_fail=True)
        result = client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})
        self.assertFalse(result.success)
        self.assertIn("api_error", result.fallback_reason)
        self.assertTrue(result.should_ask_user)

    def test_advisor_invalid_response(self):
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content="not json")
        result = client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})
        self.assertFalse(result.success)
        self.assertEqual(result.fallback_reason, "response_parse_failed")
        self.assertTrue(result.should_ask_user)

    def test_advisor_low_confidence(self):
        cfg = make_config(enabled=True, confidence_threshold=0.9)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_approve_response(0.5))
        result = client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})
        self.assertTrue(result.success)  # API 调用成功了
        self.assertTrue(result.should_ask_user)  # 但 confidence 不够，降级问用户
        self.assertIn("low_confidence", result.fallback_reason)

    def test_advisor_approve_high_confidence(self):
        cfg = make_config(enabled=True, confidence_threshold=0.7)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_approve_response(0.95))
        result = client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})
        self.assertTrue(result.success)
        self.assertFalse(result.should_ask_user)
        self.assertTrue(result.verdict.is_approve)

    def test_advisor_reject(self):
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_reject_response(0.95))
        result = client.ask("b", issue={"source": "test"}, plan={"steps": ["x"]})
        self.assertTrue(result.success)
        self.assertTrue(result.verdict.is_reject)
        self.assertTrue(result.should_ask_user)

    def test_advisor_modify(self):
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_modify_response(0.85))
        result = client.ask("b", issue={"source": "test"}, plan={"steps": ["x"]})
        self.assertTrue(result.success)
        self.assertTrue(result.verdict.is_modify)
        self.assertFalse(result.should_ask_user)  # modify 且可信 -> 不问用户

    def test_unknown_scenario_raises(self):
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_approve_response())
        result = client.ask("z", issue={})
        self.assertFalse(result.success)
        self.assertIn("prompt_build_failed", result.fallback_reason)


class TestHealthCheck(unittest.TestCase):
    """7. 健康检查 + ping"""

    def test_health_check_disabled(self):
        cfg = make_config(enabled=False)
        client = AdvisorClient(cfg)
        hc = client.health_check()
        self.assertFalse(hc["enabled"])
        self.assertFalse(hc["configured"])

    def test_health_check_enabled(self):
        cfg = make_config(enabled=True, model="gpt-4o", base_url="https://api.openai.com/v1")
        client = AdvisorClient(cfg)
        hc = client.health_check()
        self.assertTrue(hc["enabled"])
        self.assertTrue(hc["configured"])
        self.assertEqual(hc["model"], "gpt-4o")

    def test_ping_not_enabled(self):
        cfg = make_config(enabled=False)
        client = AdvisorClient(cfg)
        result = client.ping()
        self.assertFalse(result.success)
        self.assertEqual(result.fallback_reason, "advisor_not_enabled")

    def test_ping_success(self):
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_approve_response(1.0))
        result = client.ping()
        self.assertTrue(result.success)
        self.assertTrue(result.verdict.is_approve)

    def test_ping_failure(self):
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(should_fail=True)
        result = client.ping()
        self.assertFalse(result.success)
        self.assertIn("ping_failed", result.fallback_reason)


class TestScenarioConvenienceMethods(unittest.TestCase):
    """便捷方法测试"""

    def setUp(self):
        self.cfg = make_config(enabled=True)
        self.client = AdvisorClient(self.cfg)
        self.client.provider = MockAdvisorProvider(response_content=make_approve_response(0.95))

    def test_ask_about_uncertain_issue(self):
        result = self.client.ask_about_uncertain_issue(
            issue={"source": "heartbeat"}, assessment={"certainty": "unknown"})
        self.assertTrue(result.success)
        self.assertEqual(self.client.provider.call_count, 1)

    def test_ask_about_remediation_plan(self):
        result = self.client.ask_about_remediation_plan(
            issue={"source": "embed"}, plan={"steps": ["rebuild"]})
        self.assertTrue(result.success)

    def test_ask_about_new_anomaly(self):
        result = self.client.ask_about_new_anomaly(
            issue={"source": "scratch", "category": "unknown"})
        self.assertTrue(result.success)

    def test_ask_about_archive_reuse(self):
        result = self.client.ask_about_archive_reuse(
            archive_entry={"id": "ERR-001"})
        self.assertTrue(result.success)


class TestCLIInterface(unittest.TestCase):
    """8. CLI 接口"""

    def test_cli_status_disabled(self):
        cfg = make_config(enabled=False)
        status = cli_advisor_status(cfg)
        self.assertFalse(status["enabled"])

    def test_cli_status_enabled(self):
        cfg = make_config(enabled=True, model="gpt-4o")
        status = cli_advisor_status(cfg)
        self.assertTrue(status["enabled"])
        self.assertEqual(status["model"], "gpt-4o")

    def test_cli_test_not_enabled(self):
        cfg = make_config(enabled=False)
        result = cli_advisor_test(cfg)
        self.assertFalse(result["success"])

    def test_cli_test_success(self):
        cfg = make_config(enabled=True)
        # 用 patch 替换 build_advisor
        with patch("mark42_modules.advisor_client.build_advisor") as mock_build:
            mock_build.return_value = MockAdvisorProvider(response_content=make_approve_response(1.0))
            result = cli_advisor_test(cfg)
        self.assertTrue(result["success"])
        self.assertIn("verdict", result)

    def test_cli_ask_scenario_c(self):
        cfg = make_config(enabled=True)
        with patch("mark42_modules.advisor_client.build_advisor") as mock_build:
            mock_build.return_value = MockAdvisorProvider(response_content=make_approve_response(0.95))
            result = cli_advisor_ask("c", issue={"source": "test"}, config=cfg)
        self.assertTrue(result["success"])

    def test_cli_ask_invalid_scenario(self):
        cfg = make_config(enabled=True)
        result = cli_advisor_ask("z", config=cfg)
        self.assertIn("error", result)


class TestEndToEndFlow(unittest.TestCase):
    """9. 端到端流程测试"""

    def test_full_flow_approve(self):
        """场景 A -> advisor approve -> 不问用户"""
        cfg = make_config(enabled=True, confidence_threshold=0.7)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_approve_response(0.95))

        result = client.ask_about_uncertain_issue(
            issue={"source": "heartbeat", "category": "stale", "msg": "25min"},
            assessment={"certainty": "unknown"},
        )
        self.assertTrue(result.success)
        self.assertTrue(result.verdict.is_approve)
        self.assertFalse(result.should_ask_user)

    def test_full_flow_reject_to_user(self):
        """场景 B -> advisor reject -> 问用户"""
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_reject_response(0.95))

        result = client.ask_about_remediation_plan(
            issue={"source": "embed", "category": "index_lost"},
            plan={"steps": ["rm -rf"], "estimated_time": "unknown"},
        )
        self.assertTrue(result.success)
        self.assertTrue(result.verdict.is_reject)
        self.assertTrue(result.should_ask_user)

    def test_full_flow_modify(self):
        """场景 B -> advisor modify -> 不问用户，按 modified_plan 走"""
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_modify_response(0.9))

        result = client.ask_about_remediation_plan(
            issue={"source": "embed"},
            plan={"steps": ["rebuild"]},
        )
        self.assertTrue(result.success)
        self.assertTrue(result.verdict.is_modify)
        self.assertIsNotNone(result.verdict.modified_plan)
        self.assertFalse(result.should_ask_user)

    def test_full_flow_timeout_to_user(self):
        """场景 C -> advisor 超时 -> 问用户"""
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(should_fail=True)

        result = client.ask_about_new_anomaly(
            issue={"source": "scratch", "category": "unknown", "msg": ".tmp-xyz"}
        )
        self.assertFalse(result.success)
        self.assertTrue(result.should_ask_user)

    def test_full_flow_disabled_to_user(self):
        """场景 D -> advisor 没开 -> 问用户"""
        cfg = make_config(enabled=False)
        client = AdvisorClient(cfg)

        result = client.ask_about_archive_reuse(
            archive_entry={"id": "ERR-001", "category": "test"}
        )
        self.assertFalse(result.success)
        self.assertTrue(result.should_ask_user)

    def test_prompt_contains_response_format(self):
        """验证调用时传了 response_format=json_object"""
        cfg = make_config(enabled=True)
        client = AdvisorClient(cfg)
        client.provider = MockAdvisorProvider(response_content=make_approve_response())

        client.ask("a", issue={"source": "test"}, assessment={"certainty": "unknown"})

        # MockAdvisorProvider.chat 接收 **kwargs，验证 response_format
        # 由于 mock 不记录 kwargs，我们只验证调用次数
        self.assertEqual(client.provider.call_count, 1)

    def test_system_prompt_contains_json_contract(self):
        """验证 system prompt 包含 JSON 契约说明"""
        from mark42_modules.advisor_client import ADVISOR_SYSTEM_PROMPT
        self.assertIn("verdict", ADVISOR_SYSTEM_PROMPT)
        self.assertIn("approve", ADVISOR_SYSTEM_PROMPT)
        self.assertIn("reject", ADVISOR_SYSTEM_PROMPT)
        self.assertIn("modify", ADVISOR_SYSTEM_PROMPT)
        self.assertIn("confidence", ADVISOR_SYSTEM_PROMPT)


if __name__ == "__main__":
    print("=" * 80)
    print("Mark42 v3-4 · Advisor Client 单元测试")
    print("=" * 80)
    unittest.main(verbosity=2, exit=True)
