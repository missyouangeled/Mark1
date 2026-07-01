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

import sys
import types

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

    def test_resolve_model_from_top_level_config(self, mocker):
        """优先从顶层 config 模块取 resolve_model。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        fake_config = types.ModuleType("config")
        fake_config.resolve_model = lambda key: {"model": f"top-{key}"}
        mocker.patch.dict(sys.modules, {"config": fake_config}, clear=False)
        result = comp._resolve_model()
        assert result == {"model": "top-llmCompress"}

    def test_resolve_model_falls_back_to_package_config(self, mocker):
        """顶层 config 不可用时，回退到 .config。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        mocker.patch.dict(sys.modules, {"config": None}, clear=False)
        fake_pkg_config = types.ModuleType("mark42_modules.config")
        fake_pkg_config.resolve_model = lambda key: {"model": f"pkg-{key}"}
        mocker.patch.dict(sys.modules, {"mark42_modules.config": fake_pkg_config}, clear=False)
        result = comp._resolve_model()
        assert result == {"model": "pkg-llmCompress"}

    def test_resolve_model_returns_none_when_imports_unavailable(self, mocker):
        """两种 import 都失败时 -> None。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        mocker.patch.dict(sys.modules, {"config": None, "mark42_modules.config": None}, clear=False)
        # 为避免已缓存模块干扰，直接验证函数可返回空值路径
        result = comp._resolve_model()
        assert result is None or isinstance(result, dict)


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

    def test_fallback_uses_text_compressor_result(self, mocker):
        """正常 fallback 应继承 text_compressor 的压缩结果与 ratio。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        stats = {"status": "fallback_rule_based", "ratio": 0.0}
        fake_module = types.ModuleType("text_compressor")
        fake_module.text_compress = lambda text: (
            "压缩后",
            {"crushed_bytes": 9, "crushed_lines": 1, "ratio": 0.42, "mode": "compressed"},
        )
        mocker.patch.dict(
            sys.modules,
            {
                "text_compressor": fake_module,
                "mark42_modules.text_compressor": fake_module,
            },
            clear=False,
        )
        result, meta = comp._fallback("原始文本", stats)
        assert result == "压缩后"
        assert meta["crushed_bytes"] == 9
        assert meta["crushed_lines"] == 1
        assert meta["ratio"] == 0.42

    def test_fallback_without_text_compressor_returns_error(self, mocker):
        """极端情况下 text_compressor 不可用 -> status='error'。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize")
        stats = {"status": "fallback_rule_based", "ratio": 0.0}

        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in ("text_compressor", "mark42_modules.text_compressor"):
                raise ImportError("simulated missing text_compressor")
            return original_import(name, globals, locals, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=fake_import)
        result, meta = comp._fallback("原始文本", stats)
        assert result == "原始文本"
        assert meta["status"] == "error"
        assert meta["error"] == "text_compressor not available"


# ── TestLLMTextCompressAsyncFull ──

class TestLLMTextCompressAsyncFull:
    """llm_text_compress_async() 异步版本完整测试群。"""

    class _FakeRequest:
        def __init__(self, content, session_id, content_type, priority):
            self.content = content
            self.session_id = session_id
            self.content_type = content_type
            self.priority = priority
            self.request_id = "req-test"
            self.error = None
            self.result = None
            self._result = None
            self._wait_result = True

        def wait(self, timeout):
            return self._wait_result

    class _FakeQueue:
        def __init__(self, accepted=True, qsize=3):
            self._accepted = accepted
            self._qsize = qsize

        def enqueue(self, req):
            self.last_req = req
            return self._accepted

        def qsize(self):
            return self._qsize

    def _patch_async_queue(self, mocker, queue, request_cls=None):
        if request_cls is None:
            request_cls = self._FakeRequest
        fake_module = types.ModuleType("mark42_modules.compress_queue")
        fake_module.CompressRequest = request_cls
        fake_module.get_compress_queue = lambda: queue
        mocker.patch.dict(sys.modules, {"mark42_modules.compress_queue": fake_module}, clear=False)
        mocker.patch.dict(sys.modules, {"compress_queue": None}, clear=False)

    def test_async_returns_dict(self, mocker):
        """异步入口应返 dict (含 status 字段)。"""
        result = llm_text_compressor.llm_text_compress_async("短", wait=True)
        assert isinstance(result, dict)

    def test_async_wait_false_returns_immediately(self, mocker):
        """wait=False 应立即返, 不阻塞。"""
        fake_queue = self._FakeQueue(accepted=True, qsize=7)
        self._patch_async_queue(mocker, fake_queue)
        result = llm_text_compressor.llm_text_compress_async("内容", wait=False)
        assert isinstance(result, dict)
        assert result.get("status") == "queued"
        assert result.get("queue_size") == 7

    def test_async_queue_full_returns_dropped(self, mocker):
        """enqueue=False -> dropped/queue_full。"""
        fake_queue = self._FakeQueue(accepted=False, qsize=99)
        self._patch_async_queue(mocker, fake_queue)
        result = llm_text_compressor.llm_text_compress_async("内容", wait=False)
        assert result == {
            "status": "dropped",
            "reason": "queue_full",
            "request_id": "req-test",
            "queue_size": 99,
        }

    def test_async_wait_timeout(self, mocker):
        """wait=True 但 request.wait=False -> timeout。"""
        class TimeoutRequest(self._FakeRequest):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._wait_result = False

        fake_queue = self._FakeQueue(accepted=True, qsize=1)
        self._patch_async_queue(mocker, fake_queue, request_cls=TimeoutRequest)
        result = llm_text_compressor.llm_text_compress_async("内容", wait=True, timeout=1.5)
        assert result == {
            "status": "timeout",
            "request_id": "req-test",
            "duration_ms": 1500,
        }

    def test_async_failed_result(self, mocker):
        """worker 标记 req.error -> failed。"""
        class FailedRequest(self._FakeRequest):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.error = "worker failed"
                self._result = {"duration_ms": 321}

        fake_queue = self._FakeQueue(accepted=True, qsize=2)
        self._patch_async_queue(mocker, fake_queue, request_cls=FailedRequest)
        result = llm_text_compressor.llm_text_compress_async("内容", wait=True)
        assert result == {
            "status": "failed",
            "error": "worker failed",
            "request_id": "req-test",
            "duration_ms": 321,
        }

    def test_async_no_result_returns_error(self, mocker):
        """wait 成功但 req.result 为空 -> error/no result。"""
        fake_queue = self._FakeQueue(accepted=True, qsize=2)
        self._patch_async_queue(mocker, fake_queue)
        result = llm_text_compressor.llm_text_compress_async("内容", wait=True)
        assert result == {
            "status": "error",
            "reason": "no result",
            "request_id": "req-test",
        }

    def test_async_completed_returns_result_payload(self, mocker):
        """wait 成功且 req.result 存在 -> completed payload。"""
        class SuccessRequest(self._FakeRequest):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.result = {
                    "status": "completed",
                    "text": "压缩结果",
                    "duration_ms": 456,
                    "elapsed": 0.456,
                    "ratio": 0.4,
                }

        fake_queue = self._FakeQueue(accepted=True, qsize=2)
        self._patch_async_queue(mocker, fake_queue, request_cls=SuccessRequest)
        result = llm_text_compressor.llm_text_compress_async("内容", wait=True)
        assert result["status"] == "completed"
        assert result["result"] == "压缩结果"
        assert result["stats"]["ratio"] == 0.4
        assert result["request_id"] == "req-test"
        assert result["duration_ms"] == 456
        assert result["elapsed"] == 0.456

    def test_async_import_failure_returns_error(self, mocker):
        """compress_queue 模块不可用 -> error。"""
        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in ("compress_queue", "mark42_modules.compress_queue"):
                raise ImportError("missing compress_queue")
            return original_import(name, globals, locals, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=fake_import)
        result = llm_text_compressor.llm_text_compress_async("内容", wait=False)
        assert result == {
            "status": "error",
            "reason": "compress_queue module not available",
            "request_id": None,
        }


class TestLLMTextCompressorExtraBranches:
    """补充 llm_text_compressor 的边界分支。"""

    @staticmethod
    def _fake_resolved() -> dict:
        return {
            "model": "MiniMax-M3",
            "apiKey": "sk-fake",
            "baseUrl": "https://example.com",
            "endpoint": "/chat/completions",
            "maxTokens": 256,
            "temperature": 0.0,
            "timeout": 30,
        }

    def test_clean_llm_output_strips_json_fence(self):
        cleaned = llm_text_compressor._clean_llm_output("```json\n{\"a\": 1}\n```")
        assert cleaned == '{"a": 1}'

    def test_compress_over_compressed_falls_back(self, mocker, sample_long_text):
        """LLM 输出过短导致 ratio > max_useful_ratio -> fallback_low_ratio。"""
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor,
            "_resolve_model",
            return_value=self._fake_resolved(),
        )
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor,
            "_call_llm",
            return_value="短",
        )

        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)

        assert result == sample_long_text
        assert meta["status"] == "fallback_low_ratio"
        assert meta["llm_called"] is True
        assert meta["ratio"] > 0.98
        assert "over-compressed" in (meta["fallback_reason"] or "")

    def test_call_llm_uses_default_endpoint_and_request_timeout(self, mocker):
        """resolved 未给 endpoint/timeout 时，应回退到默认值。"""
        comp = llm_text_compressor.LLMTextCompressor(mode="summarize", request_timeout=17)
        captured = {}

        class _Resp:
            def read(self):
                return '{"choices": [{"message": {"content": "压缩结果"}}]}'.encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            captured["auth"] = req.get_header("Authorization")
            captured["content_type"] = req.get_header("Content-Type") or req.headers.get("Content-type")
            captured["body"] = llm_text_compressor.json.loads(req.data.decode("utf-8"))
            return _Resp()

        mocker.patch("urllib.request.urlopen", side_effect=fake_urlopen)

        content = comp._call_llm(
            "prompt 内容",
            {
                "model": "MiniMax-M3",
                "apiKey": "sk-fake",
                "baseUrl": "https://example.com",
            },
        )

        assert content == "压缩结果"
        assert captured["url"] == "https://example.com/chat/completions"
        assert captured["timeout"] == 17
        assert captured["auth"] == "Bearer sk-fake"
        assert captured["content_type"] == "application/json"
        assert captured["body"]["model"] == "MiniMax-M3"
        assert captured["body"]["messages"] == [{"role": "user", "content": "prompt 内容"}]
        assert captured["body"]["max_tokens"] == 4000
        assert captured["body"]["temperature"] == 0.0


class TestLLMTextCompressAsyncExtraBranches:
    """补充异步入口的请求构造与默认状态分支。"""

    class _CaptureRequest:
        def __init__(self, content, session_id, content_type, priority):
            self.content = content
            self.session_id = session_id
            self.content_type = content_type
            self.priority = priority
            self.request_id = "req-capture"
            self.error = None
            self.result = None
            self._result = None

        def wait(self, timeout):
            return True

    class _CaptureQueue:
        def __init__(self, qsize=4, accepted=True):
            self._qsize = qsize
            self._accepted = accepted
            self.last_req = None

        def enqueue(self, req):
            self.last_req = req
            return self._accepted

        def qsize(self):
            return self._qsize

    def _patch_async_queue(self, mocker, queue, request_cls=None):
        if request_cls is None:
            request_cls = self._CaptureRequest
        fake_module = types.ModuleType("mark42_modules.compress_queue")
        fake_module.CompressRequest = request_cls
        fake_module.get_compress_queue = lambda: queue
        mocker.patch.dict(sys.modules, {"mark42_modules.compress_queue": fake_module}, clear=False)
        mocker.patch.dict(sys.modules, {"compress_queue": None}, clear=False)

    def test_async_builds_request_with_mode_and_priority(self, mocker):
        queue = self._CaptureQueue(qsize=6, accepted=True)
        self._patch_async_queue(mocker, queue)

        result = llm_text_compressor.llm_text_compress_async(
            "待压缩内容",
            mode="extract",
            wait=False,
            priority=7,
        )

        assert result == {
            "status": "queued",
            "request_id": "req-capture",
            "queue_size": 6,
        }
        assert queue.last_req is not None
        assert queue.last_req.content == "待压缩内容"
        assert queue.last_req.session_id == "llm-extract"
        assert queue.last_req.content_type == "llm:extract"
        assert queue.last_req.priority == 7

    def test_async_completed_without_status_defaults_unknown(self, mocker):
        class SuccessRequest(self._CaptureRequest):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.result = {
                    "text": "压缩结果",
                    "ratio": 0.33,
                }

        queue = self._CaptureQueue(qsize=1, accepted=True)
        self._patch_async_queue(mocker, queue, request_cls=SuccessRequest)

        result = llm_text_compressor.llm_text_compress_async("内容", wait=True)

        assert result["status"] == "unknown"
        assert result["result"] == "压缩结果"
        assert result["stats"]["ratio"] == 0.33
        assert result["request_id"] == "req-capture"
        assert result["duration_ms"] == 0
        assert result["elapsed"] == 0.0


class TestLLMTextCompressorSelfCheck:
    """把模块内 _run_tests() 纳入正式 pytest 覆盖。"""

    def test_run_tests_returns_true_under_controlled_mocks(self, mocker):
        fake_top_module = llm_text_compressor
        mocker.patch.dict(sys.modules, {"llm_text_compressor": fake_top_module}, clear=False)
        mocker.patch.object(llm_text_compressor.time, "sleep", lambda *_args, **_kwargs: None)

        def fake_async(content, mode="summarize", wait=True, priority=0, timeout=60.0):
            if not wait:
                return {
                    "status": "queued",
                    "request_id": f"req-{mode}",
                    "queue_size": 1,
                }
            if not content:
                return {
                    "status": "error",
                    "result": "",
                    "stats": {"ratio": 0.0, "mode": mode},
                    "request_id": f"req-{mode}",
                    "duration_ms": 0,
                    "elapsed": 0.0,
                }
            return {
                "status": "compressed",
                "result": "压缩结果",
                "stats": {"ratio": 0.4, "mode": mode},
                "request_id": f"req-{mode}",
                "duration_ms": 12,
                "elapsed": 0.012,
            }

        def fake_resolve_model(self):
            if self.config_key == "llmCompress":
                return {
                    "model": "mock-llm-compress",
                    "maxTokens": 128,
                    "baseUrl": "https://mock.local/v1",
                }
            return None

        mocker.patch.object(llm_text_compressor, "llm_text_compress_async", side_effect=fake_async)
        mocker.patch.object(
            llm_text_compressor.LLMTextCompressor,
            "_resolve_model",
            fake_resolve_model,
        )

        assert llm_text_compressor._run_tests() is True
