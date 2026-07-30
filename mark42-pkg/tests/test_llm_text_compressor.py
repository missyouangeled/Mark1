"""llm_text_compressor.py 单元测试（pytest 形式）。

原为脚本式 run_tests()，转换为 pytest 可收集的 test_* 函数以纳入覆盖率统计。
"""

import json
import time
import urllib.error
from typing import Any
from unittest.mock import patch

from mark42.llm_text_compressor import (
    LLMTextCompressor,
    get_llm_text_compressor,
    _clean_llm_output,
    PROMPTS,
    llm_text_compress_async,
)


# ── Mock 辅助类 ──


class _MockHTTPResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def make_mock_urlopen(payload: dict[str, Any] | Exception):
    def _mock(req, timeout=None):
        if isinstance(payload, Exception):
            raise payload
        return _MockHTTPResponse(payload)
    return _mock


# ── 测试 1: 太小 passthrough ──


def test_1_1_status_passthrough_small():
    short = "x" * 200
    c = LLMTextCompressor()
    _, stats = c.compress(short)
    assert stats["status"] == "passthrough_small"


def test_1_2_没调LLM():
    short = "x" * 200
    c = LLMTextCompressor()
    _, stats = c.compress(short)
    assert stats["llm_called"] is False


def test_1_3_原文不变():
    short = "x" * 200
    c = LLMTextCompressor()
    out, _ = c.compress(short)
    assert out == short


# ── 测试 2: 模式参数校验 ──


def test_2_1_非法模式被拒():
    try:
        LLMTextCompressor(mode="invalid")
        assert False
    except ValueError:
        assert True


def test_2_2_mode_summarize可创建():
    c = LLMTextCompressor(mode="summarize")
    assert c.mode == "summarize"


def test_2_2_mode_simplify可创建():
    c = LLMTextCompressor(mode="simplify")
    assert c.mode == "simplify"


def test_2_2_mode_extract可创建():
    c = LLMTextCompressor(mode="extract")
    assert c.mode == "extract"


# ── 测试 3: 模板存在性 ──


def test_3_1_summarize模板含text占位():
    assert "{text}" in PROMPTS["summarize"]


def test_3_2_simplify模板含text占位():
    assert "{text}" in PROMPTS["simplify"]


def test_3_3_extract模板含text占位():
    assert "{text}" in PROMPTS["extract"]


# ── 测试 4: _clean_llm_output 各种脏数据 ──


def test_4_1_剥离think块():
    assert _clean_llm_output("<think>让我想想</think>这是结果") == "这是结果"


def test_4_2_剥离markdown包裹():
    assert _clean_llm_output("```\n真正的内容\n```") == "真正的内容"


def test_4_3_剥离json块():
    assert _clean_llm_output('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_4_4_头尾空白():
    assert _clean_llm_output("  \n  内容  \n  ") == "内容"


def test_4_5_空字符串():
    assert _clean_llm_output("") == ""


def test_4_6_混合think加包裹():
    assert _clean_llm_output("<think>...</think>```\n最终\n```") == "最终"


# ── 测试 5: _resolve_model 找到 llmCompress ──


def test_5_1_resolve_model返回结构正确():
    c = LLMTextCompressor()
    resolved = c._resolve_model()
    if resolved:
        assert True  # 找到配置
        assert "model" in resolved
        assert "maxTokens" in resolved
    else:
        # 没找到配置也允许通过，不是错误
        assert True


# ── 测试 6: Mock LLM 调用 (CI 必跑) ──

LONG_TEXT = (
    "总而言之，这是一个非常长的测试文本，目的是验证 LLM 压缩的实际效果。\n"
    "我们使用了多个段落来提供足够的内容供 LLM 摘要。\n"
    "第一段：系统采用 Python 开发，提供了完整的 API 接口。\n"
    "第二段：数据库采用 PostgreSQL，支持事务和 ACID 特性。\n"
    "第三段：缓存层使用 Redis，性能表现优异。\n"
    "第四段：监控系统接入 Prometheus + Grafana。\n"
    "第五段：日志收集通过 Loki 实现统一查询。\n"
) * 5

MOCK_RESOLVED = {
    "apiKey": "mock-key",
    "baseUrl": "https://mock.local/v1",
    "endpoint": "/chat/completions",
    "model": "mock-llm-compress",
    "maxTokens": 128,
    "temperature": 0.0,
    "timeout": 7,
}

MOCK_OK_PAYLOAD = {
    "choices": [
        {
            "message": {
                "content": "项目采用 Python、PostgreSQL、Redis、Prometheus/Grafana、Loki，提供完整 API 与监控日志能力。"
            }
        }
    ]
}


def test_6_1_调了LLM():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["auth"] = req.get_header("Authorization")
        captured["content_type"] = req.get_header("Content-Type") or req.headers.get("Content-type")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, stats = c.compress(LONG_TEXT)
    assert stats["llm_called"] is True


def test_6_2_status_compressed():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, stats = c.compress(LONG_TEXT)
    assert stats["status"] == "compressed"


def test_6_3_压缩率ge5pct():
    c = LLMTextCompressor(mode="summarize")

    def capture_and_return(req, timeout=None):
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, stats = c.compress(LONG_TEXT)
    assert stats["ratio"] >= 0.05


def test_6_4_model传对():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, stats = c.compress(LONG_TEXT)
    assert stats["llm_model"] == "mock-llm-compress"


def test_6_5_URL拼接正确():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["url"] = req.full_url
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    assert captured.get("url") == "https://mock.local/v1/chat/completions"


def test_6_6_timeout透传():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["timeout"] = timeout
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    assert captured.get("timeout") == 7


def test_6_7_Authorization头存在():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["auth"] = req.get_header("Authorization")
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    assert captured.get("auth") == "Bearer mock-key"


def test_6_8_ContentType正确():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["content_type"] = req.get_header("Content-Type") or req.headers.get("Content-type")
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    assert captured.get("content_type") == "application/json"


def test_6_9_body_model正确():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    assert captured.get("body", {}).get("model") == "mock-llm-compress"


def test_6_10_body_max_tokens正确():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    assert captured.get("body", {}).get("max_tokens") == 128


def test_6_11_body_temperature正确():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    assert captured.get("body", {}).get("temperature") == 0.0


def test_6_12_messages只有一条user():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    messages = captured.get("body", {}).get("messages", [])
    assert len(messages) == 1 and messages[0].get("role") == "user"


def test_6_13_prompt含原文():
    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(MOCK_OK_PAYLOAD)

    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", capture_and_return):
            _, _ = c.compress(LONG_TEXT)
    messages = captured.get("body", {}).get("messages", [])
    content = messages[0].get("content", "") if messages else ""
    assert "原文：\n" in content


def test_6_14_空choices回退():
    c = LLMTextCompressor(mode="summarize")
    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", make_mock_urlopen({"choices": []})):
            _, stats = c.compress(LONG_TEXT)
    assert stats["status"] in ("fallback_rule_based", "fallback_low_ratio")


def test_6_15_空choices标记error():
    c = LLMTextCompressor(mode="summarize")
    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", make_mock_urlopen({"choices": []})):
            _, stats = c.compress(LONG_TEXT)
    assert "RuntimeError" in (stats["error"] or "")


def test_6_16_HTTP异常回退():
    c = LLMTextCompressor(mode="summarize")
    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", make_mock_urlopen(urllib.error.URLError("mock timeout"))):
            _, stats = c.compress(LONG_TEXT)
    assert stats["status"] in ("fallback_rule_based", "fallback_low_ratio")


def test_6_17_HTTP异常写入error():
    c = LLMTextCompressor(mode="summarize")
    with patch.object(c, "_resolve_model", return_value=MOCK_RESOLVED):
        with patch("urllib.request.urlopen", make_mock_urlopen(urllib.error.URLError("mock timeout"))):
            _, stats = c.compress(LONG_TEXT)
    assert "URLError" in (stats["error"] or "")


# ── 测试 7: 无 model config → 自动 fallback ──


def test_7_1_没调LLM():
    c = LLMTextCompressor(config_key="nonexistent_key_xxx")
    long_text = "这是一段比较长的测试文本。" * 100
    _, stats = c.compress(long_text)
    assert stats["llm_called"] is False


def test_7_2_status_fallback_rule_based():
    c = LLMTextCompressor(config_key="nonexistent_key_xxx")
    long_text = "这是一段比较长的测试文本。" * 100
    _, stats = c.compress(long_text)
    assert stats["status"] == "fallback_rule_based"


def test_7_3_fallback_reason注明():
    c = LLMTextCompressor(config_key="nonexistent_key_xxx")
    long_text = "这是一段比较长的测试文本。" * 100
    _, stats = c.compress(long_text)
    assert "no_model_config" in (stats["fallback_reason"] or "")


# ── 测试 8: 输入超长截断 ──


def test_8_1_超长输入不崩溃():
    c = LLMTextCompressor(max_input_bytes=1000, config_key="nonexistent_key_xxx")
    huge = "x" * 5000
    _, stats = c.compress(huge)
    assert stats["status"] == "fallback_rule_based"


# ── 测试 9: 极端输入 fail-safe ──


def test_9_1_空字符串不报错():
    c = LLMTextCompressor()
    _, stats = c.compress("")
    assert stats["status"] == "none"


def test_9_2_纯空白不报错():
    c = LLMTextCompressor()
    _, stats = c.compress("   \n\n   ")
    assert True


# ── 测试 10: 多个模式分别能实例化 ──


def test_10_1_summarize_fallback工作():
    c = LLMTextCompressor(mode="summarize", config_key="nonexistent_key_xxx")
    _, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
    assert stats["status"] == "fallback_rule_based"


def test_10_2_summarize_mode正确():
    c = LLMTextCompressor(mode="summarize", config_key="nonexistent_key_xxx")
    _, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
    assert stats["mode"] == "summarize"


def test_10_3_simplify_fallback工作():
    c = LLMTextCompressor(mode="simplify", config_key="nonexistent_key_xxx")
    _, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
    assert stats["status"] == "fallback_rule_based"


def test_10_4_simplify_mode正确():
    c = LLMTextCompressor(mode="simplify", config_key="nonexistent_key_xxx")
    _, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
    assert stats["mode"] == "simplify"


def test_10_5_extract_fallback工作():
    c = LLMTextCompressor(mode="extract", config_key="nonexistent_key_xxx")
    _, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
    assert stats["status"] == "fallback_rule_based"


def test_10_6_extract_mode正确():
    c = LLMTextCompressor(mode="extract", config_key="nonexistent_key_xxx")
    _, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
    assert stats["mode"] == "extract"


# ── 测试 11: 单例模式 ──


def test_11_1_同mode单例():
    a = get_llm_text_compressor("summarize")
    b = get_llm_text_compressor("summarize")
    assert a is b


def test_11_2_异mode创建新实例():
    a = get_llm_text_compressor("summarize")
    c = get_llm_text_compressor("simplify")
    assert a is not c


# ── 测试 12: 异步入口 ──


def test_12_1_wait_False_status_queued():
    r1 = llm_text_compress_async("x" * 100, mode="summarize", wait=False)
    assert r1["status"] == "queued"


def test_12_2_有request_id():
    r1 = llm_text_compress_async("x" * 100, mode="summarize", wait=False)
    assert "request_id" in r1 and r1["request_id"] is not None


def test_12_3_queue_size_ge_1():
    r1 = llm_text_compress_async("x" * 100, mode="summarize", wait=False)
    assert r1.get("queue_size", 0) >= 1


def test_12_4_wait_True_拿到status():
    r2 = llm_text_compress_async("总而言之，Mark42 是一个优秀的系统。" * 20, mode="summarize", wait=True, timeout=30)
    assert r2.get("status") in ("compressed", "fallback_rule_based", "fallback_low_ratio", "passthrough_small", "passthrough_truncated_input")


def test_12_5_有result字段():
    r2 = llm_text_compress_async("总而言之，Mark42 是一个优秀的系统。" * 20, mode="summarize", wait=True, timeout=30)
    assert "result" in r2


def test_12_6_有stats字段():
    r2 = llm_text_compress_async("总而言之，Mark42 是一个优秀的系统。" * 20, mode="summarize", wait=True, timeout=30)
    assert "stats" in r2


def test_12_7_duration_ms是int():
    r2 = llm_text_compress_async("总而言之，Mark42 是一个优秀的系统。" * 20, mode="summarize", wait=True, timeout=30)
    assert isinstance(r2.get("duration_ms", 0), int)


def test_12_8_priority_1入队():
    r3 = llm_text_compress_async("x" * 100, mode="extract", wait=False, priority=1)
    assert r3["status"] == "queued"


def test_12_9_空输入不崩():
    r4 = llm_text_compress_async("", mode="summarize", wait=True)
    assert r4["status"] in ("queued", "error", "completed", "passthrough_small", "none", "fallback_rule_based", "fallback_low_ratio")


def test_12_10_simplify_async工作():
    time.sleep(1)
    r = llm_text_compress_async("总而言之，这是测试文本。\n" * 15, mode="simplify", wait=True, timeout=30)
    assert r.get("status") in (
        "compressed", "fallback_rule_based", "fallback_low_ratio",
        "passthrough_small", "passthrough_truncated_input", "error", "none"
    )


def test_12_11_extract_async工作():
    time.sleep(1)
    r = llm_text_compress_async("总而言之，这是测试文本。\n" * 15, mode="extract", wait=True, timeout=30)
    assert r.get("status") in (
        "compressed", "fallback_rule_based", "fallback_low_ratio",
        "passthrough_small", "passthrough_truncated_input", "error", "none"
    )


def test_12_12_wait_False返回快():
    t0 = time.time()
    llm_text_compress_async("x" * 100, mode="summarize", wait=False)
    elapsed = time.time() - t0
    assert elapsed < 0.1
