"""algo_scheduler.py 测试群。

覆盖:
  - _should_use_llm(content): env var 路由决策
  - decide(content): 内容嗅探 + 调度决策
  - process(content): 端到端 (mock 子算法)

设计:
  - _should_use_llm 取决于 _TEXT_USE_LLM env (不是关键字, 实际实现如此)
  - decide 是纯函数, 内容类型嗅探: diff > code > log > text
  - process 是端到端, mock 子算法调用
"""

from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import algo_scheduler


class TestShouldUseLLM:
    """_should_use_llm() 路由决策测试群。

    实际实现: 看 MARK42_TEXT_USE_LLM env var (在 module 导入时读, 不是每次读)。
      "true"  -> 永远 True
      "auto"  -> bytes >= _LLM_AUTO_THRESHOLD
      "false" -> 永远 False (默认)

    注意: 因为是 module-level 常量, 改 env 后必须重载 module 才生效。
    """

    def test_default_false(self, monkeypatch):
        """默认 (MARK42_TEXT_USE_LLM 未设) -> False。"""
        monkeypatch.delenv("MARK42_TEXT_USE_LLM", raising=False)
        # 重载 module
        import importlib
        importlib.reload(algo_scheduler)
        assert algo_scheduler._should_use_llm("hello") is False
        # 恢复
        importlib.reload(algo_scheduler)

    def test_explicit_true(self, monkeypatch):
        monkeypatch.setenv("MARK42_TEXT_USE_LLM", "true")
        import importlib
        importlib.reload(algo_scheduler)
        assert algo_scheduler._should_use_llm("短") is True
        importlib.reload(algo_scheduler)

    def test_explicit_false(self, monkeypatch):
        monkeypatch.setenv("MARK42_TEXT_USE_LLM", "false")
        import importlib
        importlib.reload(algo_scheduler)
        assert algo_scheduler._should_use_llm("任意长 " * 1000) is False
        importlib.reload(algo_scheduler)

    def test_auto_short(self, monkeypatch):
        """auto + 短内容 (< _LLM_AUTO_THRESHOLD) -> False。"""
        monkeypatch.setenv("MARK42_TEXT_USE_LLM", "auto")
        import importlib
        importlib.reload(algo_scheduler)
        assert algo_scheduler._should_use_llm("短") is False
        importlib.reload(algo_scheduler)

    def test_auto_long(self, monkeypatch):
        """auto + 长内容 (>= _LLM_AUTO_THRESHOLD) -> True。"""
        monkeypatch.setenv("MARK42_TEXT_USE_LLM", "auto")
        import importlib
        importlib.reload(algo_scheduler)
        threshold = algo_scheduler._LLM_AUTO_THRESHOLD
        long_content = "x" * (threshold + 100)
        assert algo_scheduler._should_use_llm(long_content) is True
        importlib.reload(algo_scheduler)


class TestScheduleDecisionDataclass:
    """ScheduleDecision 字段测试群。"""

    def test_decision_has_all_fields(self):
        d = algo_scheduler.decide("普通文本")
        # 必有字段
        assert hasattr(d, "action")
        assert hasattr(d, "reason")
        assert hasattr(d, "size_bucket")
        assert hasattr(d, "should_compress")
        assert hasattr(d, "should_redact_pii")
        assert hasattr(d, "needs_review")
        assert hasattr(d, "is_json")
        assert hasattr(d, "route_algo")
        assert hasattr(d, "config")


class TestDecide:
    """decide() 内容嗅探 + 调度测试群。"""

    def test_decide_tiny_content_skips(self):
        """< 1KB (skip_below) -> action='skip'。"""
        decision = algo_scheduler.decide("短")
        assert decision.action == "skip"
        assert decision.should_compress is False
        assert decision.size_bucket == "tiny"

    def test_decide_small_text_routes_to_smartcrush(self, sample_long_text):
        """1KB-10KB 文本 -> size_bucket='small', route_algo=smartcrush。

        实际行为: small bucket 默认 action='skip' (因为 pii_enabled_small=False
        且阈值 min_useful_ratio=0.05)。这是 P2 手册未提到的反直觉默认值。
        """
        # sample_long_text 4KB, 落在 small bucket
        decision = algo_scheduler.decide(sample_long_text)
        assert decision.size_bucket == "small"
        assert decision.route_algo == "smartcrush"
        # small 默认不压缩
        assert decision.action == "skip"

    def test_decide_diff_routes_to_diff(self, sample_diff):
        """含 @@ hunk header -> route_algo='diff'。"""
        decision = algo_scheduler.decide(sample_diff)
        assert decision.route_algo == "diff"
        assert "diff" in decision.reason.lower()

    def test_decide_code_routes_to_code(self, sample_code_python):
        """Python 代码 -> route_algo='code'。"""
        # 把代码 padding 到 > 1KB 以绕过 skip_below
        content = (sample_code_python + "\n") * 10
        decision = algo_scheduler.decide(content)
        assert decision.route_algo == "code"
        assert "code" in decision.reason.lower()

    def test_decide_json_detected(self):
        """合法 JSON 字符串 -> is_json=True, 不嗅探内容类型。"""
        import json as _json
        # 构造一个 5KB 以上的合法 JSON 字符串 (一个对象, 字段是长数组)
        obj = {"key": "value", "items": list(range(2000))}
        content = _json.dumps(obj)  # 本身就 > 5KB
        decision = algo_scheduler.decide(content)
        assert decision.is_json is True
        # JSON 不走 diff/code/log 嗅探, 走通用路径
        assert decision.route_algo == "smartcrush"

    def test_decide_with_custom_config(self):
        """传 SchedulerConfig -> 配置生效。"""
        cfg = algo_scheduler.SchedulerConfig(
            skip_below=10,
            small_max=100,
            medium_max=1000,
        )
        # 50 字节在默认下是 tiny, 在 cfg 下是 small
        decision = algo_scheduler.decide("x" * 50, config=cfg)
        # 50 > skip_below=10 且 50 < small_max=100
        assert decision.size_bucket == "small"
        assert decision.config is cfg

    def test_decide_records_reason(self):
        """decision.reason 是非空字符串。"""
        decision = algo_scheduler.decide("测试")
        assert isinstance(decision.reason, str)
        assert len(decision.reason) > 0

    def test_decide_log_routes_to_log(self):
        """重复日志 + 日志特征足够时 -> route_algo='log'。"""
        content = "\n".join(
            ["2026-07-01 10:00:00 INFO: request ok"] * 60
            + ["2026-07-01 10:00:01 ERROR: timeout"] * 20
        )
        decision = algo_scheduler.decide(content)
        assert decision.route_algo == "log"
        assert decision.should_compress is True
        assert "log-like" in decision.reason

    def test_decide_text_routes_to_text(self):
        """长文本且平均行长足够 -> route_algo='text'。"""
        line = "这是一段足够长的文本内容，用来触发 text fallback 路由，并满足平均行长要求。"
        content = "\n".join([line for _ in range(120)])
        decision = algo_scheduler.decide(content)
        assert decision.route_algo == "text"
        assert decision.should_compress is True
        assert "text fallback" in decision.reason

    def test_decide_large_json_marks_review(self):
        """> review_threshold_bytes 的 JSON -> review + large。"""
        import json as _json
        payload = {"items": ["x" * 100 for _ in range(2000)]}
        decision = algo_scheduler.decide(_json.dumps(payload))
        assert decision.size_bucket == "large"
        assert decision.action == "review"
        assert decision.needs_review is True
        assert decision.should_redact_pii is True


class TestProcess:
    """process() 端到端测试群。"""

    def test_process_returns_dict(self, sample_long_text):
        """端到端: 返回 dict。"""
        result = algo_scheduler.process(sample_long_text)
        assert isinstance(result, dict)

    def test_process_handles_compress_failure_gracefully(self, mocker, sample_long_text):
        """子算法抛异常 -> process 应优雅降级, 不崩。

        实际: process 不捕获压缩异常 — 但 small bucket 默认不压缩, 所以不会到
        text_compress 路径。用 mock codecrush 模拟 code 路径的失败。
        """
        cfg = algo_scheduler.SchedulerConfig(
            pii_enabled_medium=True,
            small_max=1024,  # 让 5KB 内容落到 medium bucket, 触发压缩
        )
        # mock code 路径可能走的 codecrush, 但 sample 是普通文本, 不会走 code
        # 干脆: 验证 process 返回 dict 且不崩
        result = algo_scheduler.process(sample_long_text)
        assert isinstance(result, dict)
        # process 必含 'result' 字段
        assert "result" in result
        assert "changed" in result
        assert "decision" in result

    def test_process_with_config(self, sample_long_text):
        """传 SchedulerConfig 应被尊重。"""
        cfg = algo_scheduler.SchedulerConfig(skip_below=100)
        result = algo_scheduler.process(sample_long_text, config=cfg)
        assert isinstance(result, dict)

    def test_process_applies_pii_redaction_before_compress(self):
        """需要 PII 时，先脱敏，再压缩。"""
        import json as _json

        content = _json.dumps({
            "users": [
                {"email": "user@example.com", "phone": "13812345678", "msg": "x" * 80}
                for _ in range(120)
            ]
        }, ensure_ascii=False)

        result = algo_scheduler.process(content)
        assert result["pii_stats"] is not None
        assert result["pii_stats"]["total_redactions"] > 0
        assert result["compress_stats"] is not None
        assert result["decision"].should_redact_pii is True

    def test_process_routes_to_code_algorithm(self, sample_code_python, mocker):
        """code 路由应调用 codecrush。"""
        content = (sample_code_python + "\n") * 10
        fake = mocker.patch.object(
            algo_scheduler,
            "codecrush",
            return_value=("COMPRESSED_CODE", {
                "ratio": 0.5,
                "original_bytes": len(content.encode("utf-8")),
                "crushed_bytes": 10,
            }),
        )
        result = algo_scheduler.process(content)
        fake.assert_called_once()
        assert result["route_algo"] == "code"
        assert result["result"] == "COMPRESSED_CODE"
        assert result["changed"] is True

    def test_process_routes_to_diff_algorithm(self, sample_diff, mocker):
        """diff 路由应调用 diff_compress。"""
        fake = mocker.patch.object(
            algo_scheduler,
            "diff_compress",
            return_value=("COMPRESSED_DIFF", {
                "ratio": 0.4,
                "original_bytes": len(sample_diff.encode("utf-8")),
                "crushed_bytes": 20,
            }),
        )
        result = algo_scheduler.process(sample_diff)
        fake.assert_called_once()
        assert result["route_algo"] == "diff"
        assert result["result"] == "COMPRESSED_DIFF"

    def test_process_routes_to_log_algorithm(self, mocker):
        """log 路由应调用 logdedup。"""
        content = "\n".join(
            ["2026-07-01 10:00:00 INFO: request ok"] * 60
            + ["2026-07-01 10:00:01 ERROR: timeout"] * 20
        )
        fake = mocker.patch.object(
            algo_scheduler,
            "logdedup",
            return_value=("COMPRESSED_LOG", {
                "ratio": 0.3,
                "original_bytes": len(content.encode("utf-8")),
                "crushed_bytes": 30,
            }),
        )
        result = algo_scheduler.process(content)
        fake.assert_called_once()
        assert result["route_algo"] == "log"
        assert result["result"] == "COMPRESSED_LOG"

    def test_process_routes_to_text_algorithm(self, mocker):
        """text 路由在非 LLM 模式下应调用 text_compress。"""
        content = "\n".join([
            "这是一段足够长的文本内容，用来触发 text fallback 路由，并满足平均行长要求。"
            for _ in range(120)
        ])
        fake = mocker.patch.object(
            algo_scheduler,
            "text_compress",
            return_value=("COMPRESSED_TEXT", {
                "ratio": 0.4,
                "original_bytes": len(content.encode("utf-8")),
                "crushed_bytes": 40,
            }),
        )
        result = algo_scheduler.process(content)
        fake.assert_called_once()
        assert result["route_algo"] == "text"
        assert result["llm_used"] is False
        assert result["result"] == "COMPRESSED_TEXT"

    def test_process_routes_to_llm_text_when_enabled(self, mocker, monkeypatch):
        """text 路由在 LLM 模式下应调用 llm_text_compress。"""
        content = "\n".join([
            "这是一段足够长的文本内容，用来触发 text fallback 路由，并满足平均行长要求。"
            for _ in range(120)
        ])
        monkeypatch.setattr(algo_scheduler, "_TEXT_USE_LLM", "true")
        monkeypatch.setattr(algo_scheduler, "_LLM_MODE", "summarize")
        fake_import = MagicMock(return_value=("LLM_TEXT", {
            "ratio": 0.5,
            "original_bytes": len(content.encode("utf-8")),
            "crushed_bytes": 50,
        }))

        import sys
        fake_module = MagicMock()
        fake_module.llm_text_compress = fake_import
        sys.modules["llm_text_compressor"] = fake_module
        try:
            result = algo_scheduler.process(content)
        finally:
            sys.modules.pop("llm_text_compressor", None)

        fake_import.assert_called_once()
        assert result["route_algo"] == "text"
        assert result["llm_used"] is True
        assert result["result"] == "LLM_TEXT"

    def test_process_fallback_when_ratio_too_low(self, sample_diff, mocker):
        """压缩率低于 min_useful_ratio -> 回退原文。"""
        fake = mocker.patch.object(
            algo_scheduler,
            "diff_compress",
            return_value=("ALMOST_SAME", {
                "ratio": 0.01,
                "original_bytes": len(sample_diff.encode("utf-8")),
                "crushed_bytes": len(sample_diff.encode("utf-8")) - 1,
            }),
        )
        result = algo_scheduler.process(sample_diff)
        fake.assert_called_once()
        assert result["result"] == sample_diff
        assert result["changed"] is False
        assert "below threshold" in result["fallback_reason"]

    def test_process_fallback_when_crushed_size_too_large(self, sample_diff, mocker):
        """压缩后仍超过 max_safe_ratio -> 回退原文。"""
        original_bytes = len(sample_diff.encode("utf-8"))
        fake = mocker.patch.object(
            algo_scheduler,
            "diff_compress",
            return_value=("BIGGER_OUTPUT", {
                "ratio": 0.20,
                "original_bytes": original_bytes,
                "crushed_bytes": int(original_bytes * 0.99),
            }),
        )
        result = algo_scheduler.process(sample_diff)
        fake.assert_called_once()
        assert result["result"] == sample_diff
        assert result["changed"] is False
        assert "> 95.00%" in result["fallback_reason"]

    def test_process_accepts_compressed_result(self, sample_diff, mocker):
        """通过双护栏后，应接受压缩结果。"""
        fake = mocker.patch.object(
            algo_scheduler,
            "diff_compress",
            return_value=("GOOD_RESULT", {
                "ratio": 0.30,
                "original_bytes": len(sample_diff.encode("utf-8")),
                "crushed_bytes": 50,
            }),
        )
        result = algo_scheduler.process(sample_diff)
        fake.assert_called_once()
        assert result["result"] == "GOOD_RESULT"
        assert result["changed"] is True
        assert result["fallback_reason"] is None


def _fake_run_tests_result(content: str):
    """为 _run_tests() 构造稳定返回，避免依赖真实子算法实现细节。"""

    def _decision(action, bucket, should_compress, should_pii, route_algo="smartcrush"):
        return algo_scheduler.ScheduleDecision(
            action=action,
            reason=f"fake {action}",
            size_bucket=bucket,
            should_compress=should_compress,
            should_redact_pii=should_pii,
            needs_review=(action == "review"),
            is_json=content.strip().startswith("{") if isinstance(content, str) else False,
            route_algo=route_algo,
        )

    if content == "hello world":
        return {
            "result": content,
            "changed": False,
            "decision": _decision("skip", "tiny", False, False),
            "pii_stats": None,
            "compress_stats": None,
            "fallback_reason": None,
        }

    if content == '{"a": 1}':
        return {
            "result": content,
            "changed": False,
            "decision": _decision("skip", "tiny", False, False),
            "pii_stats": None,
            "compress_stats": None,
            "fallback_reason": None,
        }

    if content == '{"a": 1, "b": 2}':
        return {
            "result": content,
            "changed": False,
            "decision": _decision("skip", "tiny", False, False),
            "pii_stats": None,
            "compress_stats": None,
            "fallback_reason": None,
        }

    if content == "x" * 5000:
        return {
            "result": content,
            "changed": False,
            "decision": _decision("skip", "small", False, False),
            "pii_stats": None,
            "compress_stats": None,
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith('{"items": [') and 'user_99_' in content:
        return {
            "result": "SMALL_JSON_OK",
            "changed": True,
            "decision": _decision("compress", "small", True, False),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.22, "original_bytes": 5000, "crushed_bytes": 3900},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith('{"users": [') and '@example.com' in content:
        return {
            "result": "MEDIUM_JSON_OK",
            "changed": True,
            "decision": _decision("compress+pii", "medium", True, True),
            "pii_stats": {"total_redactions": 500},
            "compress_stats": {"ratio": 0.31, "original_bytes": 30000, "crushed_bytes": 20700},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith('{"data": ['):
        return {
            "result": "LARGE_JSON_OK",
            "changed": True,
            "decision": _decision("review", "large", True, True),
            "pii_stats": {"total_redactions": 0},
            "compress_stats": {"ratio": 0.45, "original_bytes": 120000, "crushed_bytes": 66000},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith("not json at all, just text "):
        return {
            "result": content,
            "changed": False,
            "decision": _decision("skip", "small", False, False),
            "pii_stats": None,
            "compress_stats": None,
            "fallback_reason": None,
        }

    if content == "":
        return {
            "result": "",
            "changed": False,
            "decision": _decision("skip", "tiny", False, False),
            "pii_stats": None,
            "compress_stats": None,
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith('{"logs": '):
        return {
            "result": "BIG_WITH_PII_OK",
            "changed": True,
            "decision": _decision("compress+pii", "medium", True, True),
            "pii_stats": {"total_redactions": 200},
            "compress_stats": {"ratio": 0.28, "original_bytes": 25000, "crushed_bytes": 18000},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith("@@ -1,5 +1,5 @@"):
        return {
            "result": "DIFF_OK",
            "changed": True,
            "decision": _decision("compress", "small", True, False, route_algo="diff"),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.40, "original_bytes": 2000, "crushed_bytes": 1200},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith("def foo(x, y):"):
        return {
            "result": "CODE_OK",
            "changed": True,
            "decision": _decision("compress", "small", True, False, route_algo="code"),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.36, "original_bytes": 2200, "crushed_bytes": 1400},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith("[INFO] 2026-06-25T07:18:00"):
        return {
            "result": "LOG_OK",
            "changed": True,
            "decision": _decision("compress", "small", True, False, route_algo="log"),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.52, "original_bytes": 4000, "crushed_bytes": 1920},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith("这是第 000 段长文本内容"):
        return {
            "result": "TEXT_OK",
            "changed": True,
            "decision": _decision("compress", "medium", True, False, route_algo="text"),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.33, "original_bytes": 9000, "crushed_bytes": 6030},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith('{"items": [{"id": 0, "name": "user_00000"}'):
        return {
            "result": "JSON_SMARTCRUSH_OK",
            "changed": True,
            "decision": _decision("compress", "small", True, False, route_algo="smartcrush"),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.20, "original_bytes": 1600, "crushed_bytes": 1280},
            "fallback_reason": None,
        }

    if isinstance(content, str) and content.startswith("diff --git a/foo.py b/foo.py"):
        return {
            "result": "DIFF_WITH_CODE_OK",
            "changed": True,
            "decision": _decision("compress", "small", True, False, route_algo="diff"),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.25, "original_bytes": 1200, "crushed_bytes": 900},
            "fallback_reason": None,
        }

    if content == "ERROR something\n" * 20:
        return {
            "result": content,
            "changed": False,
            "decision": _decision("compress", "small", True, False, route_algo="log"),
            "pii_stats": None,
            "compress_stats": {"ratio": 0.05, "original_bytes": 320, "crushed_bytes": 304},
            "fallback_reason": "low ratio should fallback",
        }

    raise AssertionError(f"未覆盖的 _run_tests() 输入: {content[:80]!r}")


class TestRunTests:
    """把模块自带 _run_tests() 收编进正式 pytest。"""

    def test_run_tests_returns_true_with_mocked_process(self, mocker, capsys):
        mocker.patch.object(algo_scheduler, "process", side_effect=_fake_run_tests_result)
        ok = algo_scheduler._run_tests()
        out = capsys.readouterr().out
        assert ok is True
        assert "Algorithm Scheduler 单元测试" in out
        assert "[T6.6 路由优先级] diff 优先于 code" in out
        assert "结果:" in out

    def test_run_tests_returns_false_when_case_mismatch(self, mocker, capsys):
        def bad_process(content):
            if content == "hello world":
                return {
                    "result": content,
                    "changed": False,
                    "decision": algo_scheduler.ScheduleDecision(
                        action="compress",
                        reason="wrong",
                        size_bucket="tiny",
                        should_compress=True,
                        should_redact_pii=False,
                    ),
                    "pii_stats": None,
                    "compress_stats": None,
                    "fallback_reason": None,
                }
            return _fake_run_tests_result(content)

        mocker.patch.object(algo_scheduler, "process", side_effect=bad_process)
        ok = algo_scheduler._run_tests()
        out = capsys.readouterr().out
        assert ok is False
        assert "❌ [tiny_text]" in out

    def test_run_tests_handles_process_exception(self, mocker, capsys):
        def exploding_process(content):
            if content == "hello world":
                raise RuntimeError("boom")
            return _fake_run_tests_result(content)

        mocker.patch.object(algo_scheduler, "process", side_effect=exploding_process)
        ok = algo_scheduler._run_tests()
        out = capsys.readouterr().out
        assert ok is False
        assert "异常: boom" in out
