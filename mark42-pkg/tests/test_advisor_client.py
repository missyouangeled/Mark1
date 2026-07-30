"""AdvisorClient 主动交流协议客户端单元测试。

测试范围:
  - AdvisorVerdict 数据类
  - AdvisorResult 数据类和 should_ask_user()
  - AdvisorClient 类 ask() 方法
  - ask_about_uncertain_issue / ask_about_remediation_plan
  - ask_about_new_anomaly / ask_about_archive_reuse
  - HTTP 请求失败时返回合适的 AdvisorResult
  - mock 所有 HTTP 请求
"""

import json
from unittest.mock import MagicMock, patch

# ── AdvisorVerdict 数据类测试 ───────────────────────────

class TestAdvisorVerdict:
    """测试 AdvisorVerdict 数据类。"""

    def test_can_create_approve(self):
        from mark42.advisor_client import AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="approve",
            confidence=0.9,
            reasoning="方案安全",
        )
        assert verdict.verdict == "approve"
        assert verdict.confidence == 0.9
        assert verdict.is_approve is True
        assert verdict.is_reject is False
        assert verdict.is_modify is False

    def test_can_create_reject(self):
        from mark42.advisor_client import AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="reject",
            confidence=0.8,
            reasoning="方案不安全",
        )
        assert verdict.is_reject is True
        assert verdict.is_approve is False

    def test_can_create_modify(self):
        from mark42.advisor_client import AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="modify",
            confidence=0.7,
            reasoning="需要调整",
            modified_plan={"steps": ["调整步骤"]},
        )
        assert verdict.is_modify is True
        assert verdict.modified_plan is not None

    def test_is_trustworthy_high_confidence(self):
        from mark42.advisor_client import AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="approve",
            confidence=0.8,  # >= 0.7
            reasoning="ok",
        )
        assert verdict.is_trustworthy is True

    def test_is_trustworthy_low_confidence(self):
        from mark42.advisor_client import AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="approve",
            confidence=0.5,  # < 0.7
            reasoning="not sure",
        )
        assert verdict.is_trustworthy is False

    def test_to_dict_works(self):
        from mark42.advisor_client import AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="approve",
            confidence=0.9,
            reasoning="方案安全",
            modified_plan={"steps": ["1", "2"]},
            raw_response='{"verdict":"approve"}',
            elapsed_ms=100,
        )
        d = verdict.to_dict()
        assert d["verdict"] == "approve"
        assert d["confidence"] == 0.9
        assert d["reasoning"] == "方案安全"
        assert "modified_plan" in d


# ── AdvisorResult 数据类测试 ────────────────────────────

class TestAdvisorResult:
    """测试 AdvisorResult 数据类和 should_ask_user。"""

    def test_should_ask_user_when_not_success(self):
        from mark42.advisor_client import AdvisorResult

        result = AdvisorResult(
            success=False,
            fallback_reason="advisor_not_enabled",
        )
        assert result.should_ask_user is True

    def test_should_ask_user_when_verdict_reject(self):
        from mark42.advisor_client import AdvisorResult, AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="reject",
            confidence=0.9,
            reasoning="不行",
        )
        result = AdvisorResult(success=True, verdict=verdict)
        assert result.should_ask_user is True

    def test_should_not_ask_user_when_approve_and_trustworthy(self):
        from mark42.advisor_client import AdvisorResult, AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="approve",
            confidence=0.9,
            reasoning="可以",
        )
        result = AdvisorResult(success=True, verdict=verdict)
        assert result.should_ask_user is False

    def test_should_not_ask_user_when_modify_and_trustworthy(self):
        from mark42.advisor_client import AdvisorResult, AdvisorVerdict

        verdict = AdvisorVerdict(
            verdict="modify",
            confidence=0.8,
            reasoning="调整一下",
            modified_plan={"steps": ["1"]},
        )
        result = AdvisorResult(success=True, verdict=verdict)
        # modify 可信时不问用户
        assert result.should_ask_user is False


# ── AdvisorClient 初始化测试 ───────────────────────────

class TestAdvisorClientInit:
    """测试 AdvisorClient 初始化。"""

    def test_init_with_default_config(self):
        from mark42.advisor_client import AdvisorClient

        with patch("mark42.advisor_client.build_advisor", return_value=MagicMock()):
            AdvisorClient()
            # 不抛异常就是通过

    def test_init_with_custom_config(self):
        from mark42.advisor_client import AdvisorClient

        custom_cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "model": "test-model",
                    "base_url": "http://test",
                    "api_key": "test-key",
                    "timeout_seconds": 10,
                    "confidence_threshold": 0.8,
                }
            }
        }
        with patch("mark42.advisor_client.build_advisor", return_value=MagicMock()):
            client = AdvisorClient(custom_cfg)
            assert client.enabled is True
            assert client.timeout == 10
            assert client.confidence_threshold == 0.8

    def test_disabled_when_no_advisor_config(self):
        from mark42.advisor_client import AdvisorClient

        cfg = {"mark42": {}}
        with patch("mark42.advisor_client.build_advisor", return_value=None):
            client = AdvisorClient(cfg)
            assert client.enabled is False


# ── ask() 方法测试 ──────────────────────────────────────

class TestAdvisorClientAsk:
    """测试 AdvisorClient.ask() 方法。"""

    def _make_client(self, enabled=True):
        from mark42.advisor_client import AdvisorClient

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": enabled,
                    "model": "test-model",
                    "base_url": "http://test",
                    "api_key": "test-key",
                    "timeout_seconds": 10,
                    "confidence_threshold": 0.7,
                }
            }
        }
        mock_provider = MagicMock()
        with patch("mark42.advisor_client.build_advisor", return_value=mock_provider):
            client = AdvisorClient(cfg)
            client.provider = mock_provider
            return client

    def test_ask_disabled_returns_fallback(self):
        client = self._make_client(enabled=False)
        result = client.ask("a", issue={}, assessment={})
        assert result.success is False
        assert result.fallback_reason == "advisor_not_enabled"

    def test_ask_scenario_a_returns_approve(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "approve",
            "confidence": 0.9,
            "reasoning": "方案安全",
        })
        client.provider.chat.return_value = mock_response

        issue = {"source": "armor", "category": "context_alert", "msg": "告警"}
        assessment = {"certainty": "100%"}

        result = client.ask("a", issue=issue, assessment=assessment)
        assert result.success is True
        assert result.verdict.is_approve is True
        assert result.verdict.confidence == 0.9

    def test_ask_scenario_b_returns_modify(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "modify",
            "confidence": 0.85,
            "reasoning": "需要调整",
            "modified_plan": {"steps": ["调整步骤 1", "调整步骤 2"]},
        })
        client.provider.chat.return_value = mock_response

        issue = {"source": "engine", "category": "loop_not_registered"}
        plan = {"steps": ["步骤 1"], "estimated_time": "5m", "impact": "低"}

        result = client.ask("b", issue=issue, plan=plan)
        assert result.success is True
        assert result.verdict.is_modify is True
        assert result.verdict.modified_plan["steps"] == ["调整步骤 1", "调整步骤 2"]

    def test_ask_scenario_c_new_anomaly(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "reject",
            "confidence": 0.95,
            "reasoning": "新类型异常，需要人工确认",
        })
        client.provider.chat.return_value = mock_response

        issue = {"source": "new_module", "category": "new_problem", "msg": "未知问题"}

        result = client.ask("c", issue=issue)
        assert result.success is True
        assert result.verdict.is_reject is True

    def test_ask_scenario_d_archive_reuse(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "approve",
            "confidence": 0.88,
            "reasoning": "档案方案适用",
        })
        client.provider.chat.return_value = mock_response

        archive_entry = {
            "id": "ERR-123",
            "category": "context_alert",
            "diagnosis": "上下文告警",
            "resolution": {"status": "resolved", "method": "compress"},
        }

        result = client.ask("d", archive_entry=archive_entry)
        assert result.success is True
        assert result.verdict.is_approve is True

    def test_ask_unknown_scenario_returns_fallback(self):
        client = self._make_client()
        result = client.ask("z", issue={})
        assert result.success is False
        assert "prompt_build_failed" in result.fallback_reason

    def test_ask_api_error_returns_fallback(self):
        client = self._make_client()
        client.provider.chat.side_effect = Exception("API 调用失败")

        issue = {"source": "armor", "category": "context_alert"}
        result = client.ask("a", issue=issue, assessment={})

        assert result.success is False
        assert "api_error" in result.fallback_reason
        assert result.should_ask_user is True

    def test_ask_low_confidence_fallback(self):
        """置信度低于阈值时降级到问用户。"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "approve",
            "confidence": 0.5,  # < 0.7
            "reasoning": "不太确定",
        })
        client.provider.chat.return_value = mock_response

        issue = {"source": "armor", "category": "context_alert"}
        result = client.ask("a", issue=issue, assessment={})

        assert result.success is True  # API 调用成功了
        assert result.fallback_reason == "low_confidence: 0.50"
        assert result.should_ask_user is True

    def test_ask_invalid_verdict_returns_none(self):
        """verdict 非法时返回 None。"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "something_else",  # 非法
            "confidence": 0.9,
            "reasoning": "test",
        })
        client.provider.chat.return_value = mock_response

        issue = {"source": "armor", "category": "context_alert"}
        result = client.ask("a", issue=issue, assessment={})

        # _parse_response 返回 None，ask 会认为失败
        assert result.success is False
        assert result.fallback_reason == "response_parse_failed"


# ── 便捷方法测试 ─────────────────────────────────────────

class TestAdvisorClientConvenienceMethods:
    """测试 ask_about_* 便捷方法。"""

    def _make_client(self):
        from mark42.advisor_client import AdvisorClient

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "model": "test-model",
                    "base_url": "http://test",
                    "api_key": "test-key",
                    "timeout_seconds": 10,
                    "confidence_threshold": 0.7,
                }
            }
        }
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "approve",
            "confidence": 0.9,
            "reasoning": "ok",
        })
        mock_provider.chat.return_value = mock_response

        with patch("mark42.advisor_client.build_advisor", return_value=mock_provider):
            client = AdvisorClient(cfg)
            client.provider = mock_provider
            return client

    def test_ask_about_uncertain_issue(self):
        client = self._make_client()
        issue = {"source": "armor", "category": "context_alert"}
        assessment = {"certainty": "100%"}

        result = client.ask_about_uncertain_issue(issue, assessment)
        assert result.success is True

    def test_ask_about_remediation_plan(self):
        client = self._make_client()
        issue = {"source": "engine", "category": "loop_not_registered"}
        plan = {"steps": ["step1"], "estimated_time": "1m", "impact": "low"}

        result = client.ask_about_remediation_plan(issue, plan)
        assert result.success is True

    def test_ask_about_new_anomaly(self):
        client = self._make_client()
        issue = {"source": "new", "category": "new"}

        result = client.ask_about_new_anomaly(issue)
        assert result.success is True

    def test_ask_about_archive_reuse(self):
        client = self._make_client()
        archive_entry = {"id": "ERR-123", "category": "c1"}

        result = client.ask_about_archive_reuse(archive_entry)
        assert result.success is True


# ── 响应解析测试 ─────────────────────────────────────────

class TestParseResponse:
    """测试 _parse_response 响应解析。"""

    def _make_client(self):
        from mark42.advisor_client import AdvisorClient

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "confidence_threshold": 0.7,
                }
            }
        }
        with patch("mark42.advisor_client.build_advisor", return_value=MagicMock()):
            return AdvisorClient(cfg)

    def test_parse_valid_json(self):
        client = self._make_client()
        raw = MagicMock()
        raw.content = json.dumps({
            "verdict": "approve",
            "confidence": 0.9,
            "reasoning": "test",
        })

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict is not None
        assert verdict.verdict == "approve"
        assert verdict.confidence == 0.9
        assert verdict.elapsed_ms == 100

    def test_parse_with_markdown_code_block(self):
        """剥离 markdown 代码块。"""
        client = self._make_client()
        raw = MagicMock()
        raw.content = '''```json
{
  "verdict": "approve",
  "confidence": 0.9,
  "reasoning": "test"
}
```'''

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict is not None
        assert verdict.verdict == "approve"

    def test_parse_invalid_json_returns_none(self, caplog):
        client = self._make_client()
        raw = MagicMock()
        raw.content = "not valid json"

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict is None

    def test_parse_missing_verdict_returns_none(self):
        client = self._make_client()
        raw = MagicMock()
        raw.content = json.dumps({
            "confidence": 0.9,
            "reasoning": "test",
        })

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict is None

    def test_parse_confidence_clamped(self):
        """confidence 超出 [0,1] 范围时被 clamp。"""
        client = self._make_client()
        raw = MagicMock()
        raw.content = json.dumps({
            "verdict": "approve",
            "confidence": 1.5,  # 超出范围
            "reasoning": "test",
        })

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict.confidence == 1.0  # clamp 到 1.0

    def test_parse_dict_input(self):
        """支持 dict 格式的原始响应（OpenAI 格式）。"""
        client = self._make_client()
        raw = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "verdict": "approve",
                            "confidence": 0.9,
                            "reasoning": "test",
                        })
                    }
                }
            ]
        }

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict is not None
        assert verdict.verdict == "approve"

    def test_parse_empty_content_returns_none(self):
        client = self._make_client()
        raw = MagicMock()
        raw.content = ""

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict is None

    def test_parse_empty_choices_returns_none(self):
        client = self._make_client()
        raw = {"choices": []}

        verdict = client._parse_response(raw, elapsed_ms=100)
        assert verdict is None


# ── 健康检查测试 ─────────────────────────────────────────

class TestHealthCheck:
    """测试 health_check() 和 ping()。"""

    def test_health_check_disabled(self):
        from mark42.advisor_client import AdvisorClient

        cfg = {"mark42": {"advisor": {"enabled": False}}}
        with patch("mark42.advisor_client.build_advisor", return_value=None):
            client = AdvisorClient(cfg)
            status = client.health_check()
            assert status["enabled"] is False

    def test_health_check_enabled(self):
        from mark42.advisor_client import AdvisorClient

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "model": "test-model",
                    "base_url": "http://test",
                    "api_key": "test-key",
                }
            }
        }
        with patch("mark42.advisor_client.build_advisor", return_value=MagicMock()):
            client = AdvisorClient(cfg)
            status = client.health_check()
            assert status["enabled"] is True
            assert status["configured"] is True
            assert status["model"] == "test-model"
            assert status["base_url"] == "http://test"

    def test_ping_success(self):
        from mark42.advisor_client import AdvisorClient

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "confidence_threshold": 0.7,
                }
            }
        }
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "verdict": "approve",
            "confidence": 1.0,
            "reasoning": "ping ok",
        })
        mock_provider.chat.return_value = mock_response

        with patch("mark42.advisor_client.build_advisor", return_value=mock_provider):
            client = AdvisorClient(cfg)
            client.provider = mock_provider

        result = client.ping()
        assert result.success is True
        assert result.verdict.is_approve is True

    def test_ping_failure(self):
        from mark42.advisor_client import AdvisorClient

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                }
            }
        }
        mock_provider = MagicMock()
        mock_provider.chat.side_effect = Exception("连接失败")

        with patch("mark42.advisor_client.build_advisor", return_value=mock_provider):
            client = AdvisorClient(cfg)
            client.provider = mock_provider

        result = client.ping()
        assert result.success is False
        assert "ping_failed" in result.fallback_reason


# ── CLI 接口测试 ─────────────────────────────────────────

class TestCliAdvisor:
    """测试 cli_advisor_* CLI 接口。"""

    def test_cli_advisor_status(self):
        from mark42.advisor_client import cli_advisor_status

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "model": "test",
                    "base_url": "http://test",
                }
            }
        }
        with patch("mark42.advisor_client.build_advisor", return_value=MagicMock()):
            result = cli_advisor_status(cfg)
            assert result["enabled"] is True

    def test_cli_advisor_test(self):
        from mark42.advisor_client import cli_advisor_test

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "confidence_threshold": 0.7,
                }
            }
        }

        with patch("mark42.advisor_client.AdvisorClient.ping") as mock_ping:
            from mark42.advisor_client import AdvisorResult, AdvisorVerdict
            mock_ping.return_value = AdvisorResult(
                success=True,
                verdict=AdvisorVerdict(
                    verdict="approve", confidence=1.0, reasoning="ok", elapsed_ms=100
                ),
            )
            result = cli_advisor_test(cfg)
            assert result["success"] is True
            assert result["elapsed_ms"] == 100

    def test_cli_advisor_ask(self):
        from mark42.advisor_client import cli_advisor_ask

        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "confidence_threshold": 0.7,
                }
            }
        }

        with patch("mark42.advisor_client.AdvisorClient.ask_about_uncertain_issue") as mock_ask:
            from mark42.advisor_client import AdvisorResult, AdvisorVerdict
            mock_ask.return_value = AdvisorResult(
                success=True,
                verdict=AdvisorVerdict(
                    verdict="approve", confidence=0.9, reasoning="ok", elapsed_ms=100
                ),
            )
            result = cli_advisor_ask("a", issue={}, config=cfg)
            assert result["success"] is True
            assert result["should_ask_user"] is False
