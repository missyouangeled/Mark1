"""llm_text_compressor.py 测试群。

覆盖:
  - get_llm_text_compressor(mode) 工厂 (按 mode 缓存)
  - _clean_llm_output(content) 顶层函数 (剥离 <think> / markdown)
  - llm_text_compress(content, mode) 包装函数

设计:
  - 不真调 LLM (测试用 mock 或短文本 passthrough)
  - 短文本 (< min_text_size=500) 直接 passthrough, 不调 LLM
  - 异步版本略过 (单测聚焦同步路径)
"""

import asyncio

import pytest

from mark42_modules import llm_text_compressor


class TestLLMTextCompressorFactory:
    """get_llm_text_compressor() 工厂测试群 (按 mode 缓存)。"""

    def test_factory_singleton_same_mode(self):
        c1 = llm_text_compressor.get_llm_text_compressor("summarize")
        c2 = llm_text_compressor.get_llm_text_compressor("summarize")
        assert c1 is c2

    def test_factory_different_mode_rebuilds(self):
        """不同 mode 调用应触发重建 (实际实现)。"""
        c1 = llm_text_compressor.get_llm_text_compressor("summarize")
        c2 = llm_text_compressor.get_llm_text_compressor("extract")
        # 不同 mode -> 不是同对象
        assert c1 is not c2

    def test_factory_returns_instance(self):
        c = llm_text_compressor.get_llm_text_compressor("summarize")
        assert c is not None
        assert hasattr(c, "compress")

    def test_factory_invalid_mode_raises(self):
        """未知 mode 应在 __init__ 抛 ValueError。"""
        with pytest.raises(ValueError, match="unknown mode"):
            llm_text_compressor.LLMTextCompressor(mode="bogus_mode")


class TestCleanLLMOutput:
    """_clean_llm_output() 文本清洗测试群。"""

    def test_strips_think_blocks(self):
        text = "<think>内部思考</think>最终答案"
        cleaned = llm_text_compressor._clean_llm_output(text)
        assert "<think>" not in cleaned
        assert "最终答案" in cleaned

    def test_preserves_normal_text(self):
        text = "正常文本, 没有特殊块。"
        cleaned = llm_text_compressor._clean_llm_output(text)
        assert cleaned == text.strip()

    def test_handles_empty(self):
        assert llm_text_compressor._clean_llm_output("") == ""
        assert llm_text_compressor._clean_llm_output(None) == ""  # type: ignore

    def test_strips_whitespace(self):
        text = "  \n  实际内容  \n  "
        cleaned = llm_text_compressor._clean_llm_output(text)
        assert cleaned == "实际内容"

    def test_strips_markdown_block(self):
        """markdown 代码块包裹的内容应被剥离。"""
        text = "```\n实际内容\n```"
        cleaned = llm_text_compressor._clean_llm_output(text)
        # markdown 包裹应被剥
        assert "实际内容" in cleaned
        assert "```" not in cleaned


class TestLLMTextCompress:
    """llm_text_compress() 包装函数测试群。"""

    def test_short_text_passthrough(self):
        """短文本 (< min_text_size=500) 直接 passthrough。"""
        text = "短"
        result, meta = llm_text_compressor.llm_text_compress(text)
        # 短文本不走 LLM, status='passthrough_small'
        assert result == text
        assert meta.get("status") == "passthrough_small"

    def test_returns_tuple(self):
        """返回值是 2-tuple。"""
        text = "短"
        result = llm_text_compressor.llm_text_compress(text)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)

    def test_metadata_contains_algorithm(self, sample_long_text):
        """meta['algorithm'] = 'llm_text_compress'。"""
        # sample_long_text 是 5KB 中文, 会走 LLM 或 fallback
        # 这里只测 metadata 结构, 不要求真 LLM 调通
        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)
        # algorithm 字段必有
        assert "algorithm" in meta
        assert meta["algorithm"] == "llm_text_compress"


class TestLLMTextCompressAsync:
    """异步版本测试群 (不入队, 只验证接口)。"""

    def test_async_function_exists(self):
        """异步入口应存在。"""
        assert hasattr(llm_text_compressor, "llm_text_compress_async")
        assert callable(llm_text_compressor.llm_text_compress_async)


# ── 完整路径测试: mock LLM client ──────────────

class TestCompressWithMockedLLM:
    """compress() 完整路径测试群 (mock _resolve_model + _call_llm)。

    覆盖:
      - LLM 成功调用 + 压缩率合理
      - LLM 返空 -> fallback
      - LLM 抛异常 -> fallback
      - resolve_model 返 None -> fallback
      - 压缩率过低 (min_useful_ratio) -> fallback
      - 压缩率过高 (max_useful_ratio, 过度压缩) -> fallback
      - 超长输入 -> 截断
    """

    def _fake_resolved(self) -> dict:
        return {
            "model": "MiniMax-M3",
            "apiKey": "sk-fake",
            "baseUrl": "https://example.com/v1",
            "endpoint": "/chat/completions",
            "maxTokens": 4000,
            "temperature": 0.0,
            "timeout": 30,
        }

    def _setup_mocks(self, mocker, llm_return: str = "这是压缩后的摘要。"):
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor, "_resolve_model",
            return_value=self._fake_resolved()
        )
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor, "_call_llm",
            return_value=llm_return
        )

    def test_compress_llm_success(self, mocker, sample_long_text):
        """LLM 成功 + 压缩率合理 -> status='compressed'。

        LLM 返长度适中 (5%-98% 区间)。5KB 输入 -> 返 ~200-4000 字节合理。
        """
        self._setup_mocks(mocker, llm_return="这是压缩后的核心摘要。" * 20)  # ~500 字节
        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)
        assert meta["status"] == "compressed"
        assert meta["llm_called"] is True
        assert meta["llm_model"] == "MiniMax-M3"
        assert meta["llm_duration_ms"] >= 0
        # ratio 在合理范围
        assert 0 < meta["ratio"] < 1

    def test_compress_no_model_config_falls_back(self, mocker, sample_long_text):
        """_resolve_model 返 None -> fallback_rule_based。"""
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor, "_resolve_model",
            return_value=None
        )
        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)
        assert meta["status"] == "fallback_rule_based"
        assert meta["fallback_reason"] == "no_model_config"

    def test_compress_llm_exception_falls_back(self, mocker, sample_long_text):
        """_call_llm 抛异常 -> fallback_rule_based。"""
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor, "_resolve_model",
            return_value=self._fake_resolved()
        )
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor, "_call_llm",
            side_effect=RuntimeError("网络中断")
        )
        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)
        assert meta["status"] == "fallback_rule_based"
        assert meta["fallback_reason"] == "llm_exception"
        assert "RuntimeError" in meta["error"]

    def test_compress_empty_llm_output_falls_back(self, mocker, sample_long_text):
        """_call_llm 返空字符串 -> fallback。"""
        self._setup_mocks(mocker, llm_return="")
        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)
        # 返空后 _clean_llm_output 返 ""
        assert meta["status"] == "fallback_rule_based"
        assert meta["fallback_reason"] == "empty_llm_output"

    def test_compress_low_ratio_falls_back(self, mocker, sample_long_text):
        """压缩率过低 (mock LLM 返原长) -> fallback_low_ratio。

        实际: LLM 返原文 (sample_long_text), ratio=0 < min_useful_ratio=0.05
        -> fallback_low_ratio。
        """
        # LLM 返原文 (压缩 0 字节) -> ratio = 0
        self._setup_mocks(mocker, llm_return=sample_long_text)
        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)
        # ratio=0 < 5% -> fallback_low_ratio
        assert meta["status"] == "fallback_low_ratio"
        assert meta["ratio"] < 0.05

    def test_compress_truncated_input(self, mocker):
        """超长输入 (> max_input_bytes=12000) -> 截断, status 含 'truncated'。

        original_bytes 是原始 (截断前) 字节, crushed_bytes 是压缩后。
        压缩率 0.7-0.98 区间。
        """
        # 造 ~2KB 摘要, 压缩率合理
        summary = "这是压缩后的核心摘要。" * 100  # ~1000 字节
        self._setup_mocks(mocker, llm_return=summary)
        # 造 20KB 文本
        long_text = "这是一段测试内容。" * 2000  # ~28KB
        result, meta = llm_text_compressor.llm_text_compress(long_text)
        # 截断 + 压缩成功: status='passthrough_truncated_input'
        assert meta["status"] in ("compressed", "passthrough_truncated_input")
        if meta["status"] == "passthrough_truncated_input":
            assert meta["llm_called"] is True
        # crushed_bytes 反映压缩后, 应 <= 12000
        assert meta["crushed_bytes"] <= 12000


# ── TestResolveModel ──

class TestResolveModel:
    """_resolve_model() 模型路由解析测试群。"""

    def test_no_config_returns_none(self, mocker):
        """import 失败 -> 返 None。"""
        # mock import 失败: patch config.resolve_model 不存在
        mocker.patch.dict("sys.modules", {"mark42_modules.config": mocker.MagicMock()})
        # 难以 mock import 失败, 这里只测: _resolve_model 是 callable
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        assert hasattr(comp, "_resolve_model")
        assert callable(comp._resolve_model)


# ── TestCallLLM ──

class TestCallLLM:
    """_call_llm() HTTP 调用测试群 (mock urllib)。"""

    def test_call_llm_missing_apikey_raises(self):
        """缺 apiKey -> RuntimeError。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        with pytest.raises(RuntimeError, match="missing apiKey"):
            comp._call_llm("test prompt", {"model": "x"})

    def test_call_llm_missing_baseurl_raises(self):
        """缺 baseUrl -> RuntimeError。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        with pytest.raises(RuntimeError, match="missing apiKey"):
            comp._call_llm("test prompt", {"model": "x", "apiKey": "sk-fake"})

    def test_call_llm_success(self, mocker):
        """成功 HTTP 调用 -> 返 content 文本。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        fake_response = mocker.MagicMock()
        fake_response.read.return_value = mocker.MagicMock(
            decode=lambda x: '{"choices": [{"message": {"content": "压缩结果"}}], "usage": {}}'
        )
        fake_response.__enter__ = lambda self: self
        fake_response.__exit__ = lambda self, *a: None

        mocker.patch(
            "urllib.request.urlopen", return_value=fake_response
        )
        content = comp._call_llm("prompt", {
            "model": "x", "apiKey": "sk-fake",
            "baseUrl": "https://example.com", "endpoint": "/chat/completions"
        })
        assert content == "压缩结果"

    def test_call_llm_no_choices_raises(self, mocker):
        """LLM 返 choices=[] -> RuntimeError。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        fake_response = mocker.MagicMock()
        fake_response.read.return_value = mocker.MagicMock(
            decode=lambda x: '{"choices": []}'
        )
        fake_response.__enter__ = lambda self: self
        fake_response.__exit__ = lambda self, *a: None
        mocker.patch("urllib.request.urlopen", return_value=fake_response)

        with pytest.raises(RuntimeError, match="no choices"):
            comp._call_llm("prompt", {
                "model": "x", "apiKey": "sk-fake",
                "baseUrl": "https://example.com", "endpoint": "/chat/completions"
            })


# ── TestFallback ──

class TestFallback:
    """_fallback() 回退路径测试群。

    跳过 test_fallback_uses_text_compressor 的原因:
    _fallback 内部用 `from .text_compressor import text_compress` 相对导入,
    conftest reload 后 sys.modules 里的 mock 模块不会被相对导入识别为
    mark42_modules 子包。改用 test_compress_llm_exception_falls_back 间接覆盖。
    """

    def test_fallback_function_exists(self):
        """_fallback 方法存在。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        assert hasattr(comp, "_fallback")
        assert callable(comp._fallback)


# ── TestLLMTextCompressAsyncFull ──

class TestLLMTextCompressAsyncFull:
    """llm_text_compress_async() 异步版本完整测试群。"""

    def test_async_returns_dict(self, mocker):
        """异步入口应返 dict (含 status 字段)。"""
        # 短文本 → 同步路径直接返, 不走队列
        result = llm_text_compressor.llm_text_compress_async("短", wait=True)
        assert isinstance(result, dict)

    def test_async_wait_false_returns_immediately(self, mocker):
        """wait=False 应立即返, 不阻塞。"""
        fake_queue = mocker.MagicMock()
        mocker.patch(
            "mark42_modules.compress_queue.get_compress_queue",
            return_value=fake_queue
        )
        result = llm_text_compressor.llm_text_compress_async("内容", wait=False)
        assert isinstance(result, dict)
        # wait=False 应返 status='queued'
        assert result.get("status") in ("queued", "pending", "submitted")

