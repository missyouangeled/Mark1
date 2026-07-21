"""从 llm_text_compressor.py 提取的单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.llm_text_compressor import *
from mark42.llm_text_compressor import _clean_llm_output


def run_tests():
    passed = 0
    failed = 0

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

    def check(name: str, cond: bool):
        nonlocal passed, failed
        if cond:
            log.info(f"  ✓ {name}")
            passed += 1
        else:
            log.info(f"  ✗ {name}")
            failed += 1

    # ---- 测试 1: 太小 passthrough (不调 LLM) ----
    log.info("\n[测试 1] 小文本 passthrough (不调 LLM)")
    short = "x" * 200
    c = LLMTextCompressor()
    out, stats = c.compress(short)
    check("1.1 status=passthrough_small", stats["status"] == "passthrough_small")
    check("1.2 没调 LLM", stats["llm_called"] is False)
    check("1.3 原文不变", out == short)

    # ---- 测试 2: 模式参数校验 ----
    log.info("\n[测试 2] 模式参数")
    try:
        LLMTextCompressor(mode="invalid")
        check("2.1 非法模式应报错", False)
    except ValueError:
        check("2.1 非法模式被拒", True)
    for m in ["summarize", "simplify", "extract"]:
        c = LLMTextCompressor(mode=m)
        check(f"2.2 mode={m} 可创建", c.mode == m)

    # ---- 测试 3: 模板存在性 ----
    log.info("\n[测试 3] Prompt 模板")
    for m in PROMPTS:
        check(f"3.{m} 模板含 {{text}} 占位", "{text}" in PROMPTS[m])

    # ---- 测试 4: _clean_llm_output 各种脏数据 ----
    log.info("\n[测试 4] LLM 输出清理")
    check("4.1 剥离 <think> 块", _clean_llm_output("<think>让我想想</think>这是结果") == "这是结果")
    check("4.2 剥离 markdown 包裹", _clean_llm_output("```\n真正的内容\n```") == "真正的内容")
    check("4.3 剥离 ```json 块", _clean_llm_output('```json\n{"a": 1}\n```') == '{"a": 1}')
    check("4.4 头尾空白", _clean_llm_output("  \n  内容  \n  ") == "内容")
    check("4.5 空字符串", _clean_llm_output("") == "")
    check("4.6 混合 <think> + 包裹", _clean_llm_output("<think>...</think>```\n最终\n```") == "最终")

    # ---- 测试 5: _resolve_model 找到 llmCompress ----
    log.info("\n[测试 5] 模型配置解析")
    c = LLMTextCompressor()
    resolved = c._resolve_model()
    if resolved:
        check("5.1 找到 llmCompress", True)
        check("5.2 有 model 字段", "model" in resolved)
        check("5.3 有 maxTokens 字段", "maxTokens" in resolved)
        log.info(f"  → model={resolved.get('model')}, baseUrl={'已配置' if resolved.get('baseUrl') else '未配置'}")
    else:
        check("5.1 找到 llmCompress (mark42 config)", False)
        check("5.2 有 model 字段 (openclaw)", False)
        log.info("  → 注意: 模型配置未找到, 实际 LLM 调用会回退")

    # ---- 测试 6: Mock LLM 调用 (CI 必跑) ----
    log.info("\n[测试 6] Mock LLM 调用 (CI 必跑)")
    from unittest.mock import patch

    long_text = (
        "总而言之，这是一个非常长的测试文本，目的是验证 LLM 压缩的实际效果。\n"
        "我们使用了多个段落来提供足够的内容供 LLM 摘要。\n"
        "第一段：系统采用 Python 开发，提供了完整的 API 接口。\n"
        "第二段：数据库采用 PostgreSQL，支持事务和 ACID 特性。\n"
        "第三段：缓存层使用 Redis，性能表现优异。\n"
        "第四段：监控系统接入 Prometheus + Grafana。\n"
        "第五段：日志收集通过 Loki 实现统一查询。\n"
    ) * 5

    mock_resolved = {
        "apiKey": "mock-key",
        "baseUrl": "https://mock.local/v1",
        "endpoint": "/chat/completions",
        "model": "mock-llm-compress",
        "maxTokens": 128,
        "temperature": 0.0,
        "timeout": 7,
    }
    mock_ok_payload = {
        "choices": [
            {
                "message": {
                    "content": "项目采用 Python、PostgreSQL、Redis、Prometheus/Grafana、Loki，提供完整 API 与监控日志能力。"
                }
            }
        ]
    }

    c = LLMTextCompressor(mode="summarize")
    captured: dict[str, Any] = {}

    def capture_and_return(req, timeout=None):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["auth"] = req.get_header("Authorization")
        captured["content_type"] = req.get_header("Content-Type") or req.headers.get("Content-type")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockHTTPResponse(mock_ok_payload)

    with patch.object(c, "_resolve_model", return_value=mock_resolved):
        with patch("urllib.request.urlopen", capture_and_return):
            out, stats = c.compress(long_text)

    check("6.1 调了 LLM", stats["llm_called"] is True)
    check("6.2 status=compressed", stats["status"] == "compressed")
    check("6.3 压缩率 >= 5%", stats["ratio"] >= 0.05)
    check("6.4 model 传对", stats["llm_model"] == "mock-llm-compress")
    check("6.5 URL 拼接正确", captured.get("url") == "https://mock.local/v1/chat/completions")
    check("6.6 timeout 透传", captured.get("timeout") == 7)
    check("6.7 Authorization 头存在", captured.get("auth") == "Bearer mock-key")
    check("6.8 Content-Type 正确", captured.get("content_type") == "application/json")
    check("6.9 body.model 正确", captured.get("body", {}).get("model") == "mock-llm-compress")
    check("6.10 body.max_tokens 正确", captured.get("body", {}).get("max_tokens") == 128)
    check("6.11 body.temperature 正确", captured.get("body", {}).get("temperature") == 0.0)
    messages = captured.get("body", {}).get("messages", [])
    check("6.12 messages 只有一条 user", len(messages) == 1 and messages[0].get("role") == "user")
    check("6.13 prompt 含原文", "原文：\n" in (messages[0].get("content", "") if messages else ""))
    log.info(f"  → 原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B ({stats['ratio']:.1%})")
    log.info(f"  → mock 输出预览: {out[:120]!r}")

    c = LLMTextCompressor(mode="summarize")
    with patch.object(c, "_resolve_model", return_value=mock_resolved):
        with patch("urllib.request.urlopen", make_mock_urlopen({"choices": []})):
            out, stats = c.compress(long_text)
    check("6.14 空 choices 回退", stats["status"] in ("fallback_rule_based", "fallback_low_ratio"))
    check("6.15 空 choices 标记 error", "RuntimeError" in (stats["error"] or ""))

    c = LLMTextCompressor(mode="summarize")
    with patch.object(c, "_resolve_model", return_value=mock_resolved):
        with patch("urllib.request.urlopen", make_mock_urlopen(urllib.error.URLError("mock timeout"))):
            out, stats = c.compress(long_text)
    check("6.16 HTTP 异常回退", stats["status"] in ("fallback_rule_based", "fallback_low_ratio"))
    check("6.17 HTTP 异常写入 error", "URLError" in (stats["error"] or ""))

    # ---- 测试 6R: 真实 LLM 调用 (可选补充) ----
    log.info("\n[测试 6R] 真实 LLM 调用 (可选补充)")
    if not resolved or not resolved.get("apiKey"):
        log.info("  ⚠️  无 api key, 跳过真实调用补充测试")
        check("6R.1 无 key 时允许跳过", True)
    else:
        c = LLMTextCompressor(mode="summarize")
        out, stats = c.compress(long_text)
        check("6R.1 调了 LLM", stats["llm_called"] is True)
        check("6R.2 status=compressed", stats["status"] == "compressed")
        check("6R.3 压缩率 >= 5%", stats["ratio"] >= 0.05)
        check("6R.4 duration < 60s", stats["llm_duration_ms"] < 60_000)
        log.info(
            f"  → 原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B "
            f"({stats['ratio']:.1%}), 用时 {stats['llm_duration_ms']}ms"
        )
        log.info(f"  → 输出预览: {out[:200]!r}")

    # ---- 测试 7: 无 model config → 自动 fallback ----
    log.info("\n[测试 7] 无 model config fallback")
    c = LLMTextCompressor(config_key="nonexistent_key_xxx")
    long_text = "这是一段比较长的测试文本。" * 100
    out, stats = c.compress(long_text)
    check("7.1 没调 LLM", stats["llm_called"] is False)
    check("7.2 status=fallback_rule_based", stats["status"] == "fallback_rule_based")
    check("7.3 fallback_reason 注明", "no_model_config" in (stats["fallback_reason"] or ""))
    log.info(f"  → fallback_reason: {stats['fallback_reason']}")

    # ---- 测试 8: 输入超长截断 ----
    log.info("\n[测试 8] 超长输入截断")
    c = LLMTextCompressor(max_input_bytes=1000, config_key="nonexistent_key_xxx")
    huge = "x" * 5000
    out, stats = c.compress(huge)
    check("8.1 fallback (没 LLM)", stats["status"] == "fallback_rule_based")
    # 实际上 max_input_bytes 仅 LLM 路径生效; fallback 路径不走截断
    # 这里只验证不会崩

    # ---- 测试 9: 极端输入 fail-safe ----
    log.info("\n[测试 9] 极端输入 fail-safe")
    c = LLMTextCompressor()
    out, stats = c.compress("")
    check("9.1 空字符串不报错", stats["status"] == "none")
    out, stats = c.compress("   \n\n   ")
    check("9.2 纯空白不报错", True)

    # ---- 测试 10: 多个模式分别能实例化 ----
    log.info("\n[测试 10] 多模式实例化")
    for m in ["summarize", "simplify", "extract"]:
        c = LLMTextCompressor(mode=m, config_key="nonexistent_key_xxx")
        out, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
        check(f"10.{m} fallback 工作", stats["status"] == "fallback_rule_based")
        check(f"10.{m} mode 正确", stats["mode"] == m)

    # ---- 测试 11: 单例模式 ----
    log.info("\n[测试 11] 单例")
    a = get_llm_text_compressor("summarize")
    b = get_llm_text_compressor("summarize")
    check("11.1 同 mode 单例", a is b)
    c = get_llm_text_compressor("simplify")
    check("11.2 异 mode 创建新实例", a is not c)

    # ---- 测试 12: 异步入口 (Phase 2 目标 1) ----
    log.info("\n[测试 12] 异步入口 llm_text_compress_async")
    from mark42.llm_text_compressor import llm_text_compress_async

    # 注: 12.1/12.3 用意是不堵 LLM 调用 — 所以用小内容 (< min_text_size=500),
    # worker 会立即走 passthrough_small, 不发 LLM 请求
    # 这样不污染后面 wait=True 的结果判定

    # 12.1 wait=False 入队即返
    r1 = llm_text_compress_async("x" * 100, mode="summarize", wait=False)  # 100B 不调 LLM
    check("12.1 wait=False status=queued", r1["status"] == "queued")
    check("12.2 有 request_id", "request_id" in r1 and r1["request_id"] is not None)
    check("12.3 queue_size >= 1", r1.get("queue_size", 0) >= 1)

    # 12.2 wait=True 同步等结果 (真调 LLM, 5 秒)
    r2 = llm_text_compress_async("总而言之，Mark42 是一个优秀的系统。" * 20, mode="summarize", wait=True, timeout=30)
    check(
        "12.4 wait=True 拿到 status",
        r2.get("status") in ("compressed", "fallback_rule_based", "fallback_low_ratio", "passthrough_small"),
    )
    check("12.5 有 result 字段", "result" in r2)
    check("12.6 有 stats 字段", "stats" in r2)
    check("12.7 duration_ms 是 int", isinstance(r2.get("duration_ms", 0), int))

    # 12.3 priority 参数
    r3 = llm_text_compress_async("x" * 100, mode="extract", wait=False, priority=1)
    check("12.8 priority=1 入队", r3["status"] == "queued")

    # 12.4 极端输入
    r4 = llm_text_compress_async("", mode="summarize", wait=True)
    check("12.9 空输入不崩", r4["status"] in ("queued", "error", "completed", "passthrough_small", "none"))
    # 注: 空内容走 LLM 会在 worker 内部 fallback, status 由 worker 决定

    # 12.5 跨模式 — 测试间加等 queue 清空 (避免 4 调 LLM 互相争)
    for m in ["simplify", "extract"]:
        # 等上次请求走完, 避免 2 个 LLM 调用同 worker 冲突
        time.sleep(1)
        r = llm_text_compress_async("总而言之，这是测试文本。\n" * 15, mode=m, wait=True, timeout=30)
        check(
            f"12.10.{m} wait=True 拿到状态",
            r.get("status")
            in (
                "compressed",
                "fallback_rule_based",
                "fallback_low_ratio",
                "passthrough_small",
                "passthrough_truncated_input",
                "error",
                "none",
            ),
        )

    # 12.6 验证: 调用方不阻塞 (wait=False 应该 < 1 秒)
    t0 = time.time()
    llm_text_compress_async("x" * 100, mode="summarize", wait=False)  # 小内容, worker 立即完成
    elapsed = time.time() - t0
    check("12.11 wait=False 返回时间 < 0.1s", elapsed < 0.1)

    log.info(f"  → 12.11 wait=False 实际用时: {elapsed * 1000:.1f}ms")

    log.info("")
    log.info("=" * 60)
    log.info(f"结果: {passed} 通过 / {failed} 失败")
    log.info("=" * 60)
    return failed == 0

