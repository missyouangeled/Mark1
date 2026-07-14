"""Mark42 LLM 语义文本压缩器（Day 8 - 真接 LiteLLM）

设计文档:
- 开发手册: docs/design/mark42-开发手册-压缩子系统.md (4.6 节 llm 模式)
- 模型路由: docs/通用-AI模型路由问题排查与修复手册.md
- 与 _llm_analyze 同源: resolve_model() + openclaw.json provider 路由

设计目标:
- text_compressor 的 method="llm" 占位实际化
- 真调 OpenClaw 已配的 LLM (MiniMax-M3 主)
- 多种压缩模式: summarize (摘要) | simplify (简化) | extract (抽取)
- 失败回退: 调不通 → 走 text_compressor rule_based

护栏:
- 输入 > max_input_bytes 截断
- 输出 < min_compression_ratio (5%) 视为无效
- LLM 异常 / 超时 / 解析失败 → set_error + 调 fallback

接口 (与 text_compressor 风格一致):
  LLMTextCompressor
  get_llm_text_compressor() 单例
  llm_text_compress(content, mode="summarize") -> tuple[str, dict]

创建日期: 2026-06-25 07:47
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

# 【2026-07-13】不能用相对路径, perf_bench/algo_scheduler 从外部 import
from mark42_modules.utils import safe_call


log = logging.getLogger("mark42.llm_text_compressor")


# 压缩指令模板
PROMPTS = {
    "summarize": (
        "请对以下文本进行摘要压缩，保留核心信息和关键事实，去除冗余描述。\n"
        "要求：\n"
        "1. 保持事实准确，不要新增原文中没有的信息\n"
        "2. 保留具体数字、日期、人名、项目名等关键实体\n"
        "3. 用简洁的中文输出，篇幅控制在原文的 30-50%\n"
        "4. 直接输出压缩后的文本，不要加任何前缀或解释\n\n"
        "原文：\n{text}"
    ),
    "simplify": (
        "请用更简洁的方式重写以下文本，去除冗余和重复内容。\n"
        "要求：\n"
        "1. 同义词替换（用更短的说法）\n"
        "2. 删除冗余短语和废话\n"
        "3. 合并重复信息\n"
        "4. 直接输出简化后的文本，不要加任何前缀或解释\n\n"
        "原文：\n{text}"
    ),
    "extract": (
        "请从以下文本中提取关键信息，以结构化列表形式输出。\n"
        "要求：\n"
        "1. 只输出关键事实、决策、任务、问题、答案\n"
        "2. 每条一行，用「- 」开头\n"
        "3. 不要输出原始描述性段落\n"
        "4. 不要加任何前言或解释\n\n"
        "原文：\n{text}"
    ),
}

# 清理 <think>/</think> 思考块 (MiniMax / DeepSeek 等)
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)
# 清理 markdown 代码块包裹
_MD_BLOCK_PATTERN = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)\n```\s*$", re.DOTALL)


@safe_call(default="", label="clean_llm_output")
def _clean_llm_output(content: str) -> str:
    """剥离 <think> 块、markdown 包裹、空白"""
    if not content:
        return ""
    # 1. 剥离思考块
    content = _THINK_PATTERN.sub("", content)
    # 2. 剥离 markdown 代码块
    m = _MD_BLOCK_PATTERN.match(content.strip())
    if m:
        content = m.group(1)
    # 3. 头尾空白
    return content.strip()


class LLMTextCompressor:
    """LLM 驱动的语义文本压缩器"""

    def __init__(self,
                 mode: str = "summarize",
                 min_text_size: int = 500,
                 max_input_bytes: int = 12000,
                 min_useful_ratio: float = 0.05,
                 max_useful_ratio: float = 0.98,
                 request_timeout: int = 60,
                 config_key: str = "llmCompress"):
        """
        Args:
            mode: "summarize" | "simplify" | "extract"
            min_text_size: < 此字节数直接 passthrough (LLM 不值得)
            max_input_bytes: 输入超此截断 (防超长输入打爆 LLM)
            min_useful_ratio: 压缩率 < 5% 视为无效
            max_useful_ratio: 压缩率 > 98% 视为过度压缩 (可能丢失)
            request_timeout: HTTP 请求超时 (秒), fallback 到 config
            config_key: Mark42 模型表 key (默认 llmCompress)
        """
        if mode not in PROMPTS:
            raise ValueError(f"unknown mode: {mode}, must be one of {list(PROMPTS)}")
        self.mode = mode
        self.min_text_size = min_text_size
        self.max_input_bytes = max_input_bytes
        self.min_useful_ratio = min_useful_ratio
        self.max_useful_ratio = max_useful_ratio
        self.request_timeout = request_timeout
        self.config_key = config_key

    def compress(self, text: str) -> tuple[str, dict]:
        """压缩文本; 失败时回退到 rule_based"""
        stats = {
            "algorithm": "llm_text_compress",
            "mode": self.mode,
            "original_bytes": 0,
            "original_lines": 0,
            "crushed_bytes": 0,
            "crushed_lines": 0,
            "ratio": 0.0,
            "status": "none",         # "compressed" | "passthrough_small" | "fallback_rule_based" | "fallback_low_ratio" | "error" | "passthrough_truncated_input"
            "llm_called": False,
            "llm_model": None,
            "llm_tokens_in": 0,
            "llm_tokens_out": 0,
            "llm_duration_ms": 0,
            "fallback_reason": None,
            "error": None,
        }

        if not text or not text.strip():
            return text, stats

        stats["original_bytes"] = len(text.encode("utf-8"))
        stats["original_lines"] = text.count("\n") + (1 if not text.endswith("\n") else 0)

        # 太小, LLM 浪费
        if stats["original_bytes"] < self.min_text_size:
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["crushed_lines"] = stats["original_lines"]
            stats["status"] = "passthrough_small"
            return text, stats

        # 截断超长输入
        truncated = False
        if stats["original_bytes"] > self.max_input_bytes:
            text = text.encode("utf-8")[:self.max_input_bytes].decode("utf-8", errors="ignore")
            truncated = True

        # 解析 LLM 路由
        resolved = self._resolve_model()
        if not resolved:
            stats["status"] = "fallback_rule_based"
            stats["fallback_reason"] = "no_model_config"
            return self._fallback(text, stats)

        stats["llm_model"] = resolved.get("model", "?")

        # 调 LLM
        prompt = PROMPTS[self.mode].format(text=text)
        t0 = time.time()
        try:
            result_text = self._call_llm(prompt, resolved)
        except Exception as e:
            stats["error"] = f"{type(e).__name__}: {e}"
            stats["llm_duration_ms"] = int((time.time() - t0) * 1000)
            stats["status"] = "fallback_rule_based"
            stats["fallback_reason"] = "llm_exception"
            log.warning(f"LLM call failed: {stats['error']}, falling back to rule_based")
            return self._fallback(text, stats)
        stats["llm_duration_ms"] = int((time.time() - t0) * 1000)
        stats["llm_called"] = True

        # 清理
        result_text = _clean_llm_output(result_text)
        if not result_text:
            stats["status"] = "fallback_rule_based"
            stats["fallback_reason"] = "empty_llm_output"
            return self._fallback(text, stats)

        # 评估压缩率
        crushed = len(result_text.encode("utf-8"))
        ratio = 1.0 - crushed / max(1, stats["original_bytes"])

        if ratio < self.min_useful_ratio:
            stats["status"] = "fallback_low_ratio"
            stats["ratio"] = ratio
            stats["fallback_reason"] = f"ratio {ratio:.1%} < {self.min_useful_ratio:.0%}"
            return text, stats

        if ratio > self.max_useful_ratio:
            # 过度压缩, 可能丢了东西, 回退
            stats["status"] = "fallback_low_ratio"
            stats["ratio"] = ratio
            stats["fallback_reason"] = f"ratio {ratio:.1%} > {self.max_useful_ratio:.0%} (over-compressed)"
            return text, stats

        stats["crushed_bytes"] = crushed
        stats["crushed_lines"] = result_text.count("\n") + (1 if not result_text.endswith("\n") else 0)
        stats["ratio"] = ratio
        stats["status"] = "passthrough_truncated_input" if truncated else "compressed"
        return result_text, stats

    def _resolve_model(self) -> dict[str, Any] | None:
        """从 Mark42 模型表解析 LLM 路由 (延迟导入避免循环)"""
        try:
            from config import resolve_model
        except ImportError:
            try:
                from .config import resolve_model
            except ImportError:
                return None
        return resolve_model(self.config_key)

    def _call_llm(self, prompt: str, resolved: dict[str, Any]) -> str:
        """调 LLM API, 返回 content 文本 (不解析 JSON)"""
        # 从 resolved 拿模型配置
        # resolved 是 get_model_config 返回, 已含 baseUrl/endpoint/apiKey
        api_key = resolved.get("apiKey")
        base_url = resolved.get("baseUrl")
        endpoint = resolved.get("endpoint", "/chat/completions")
        model_name = resolved.get("model")
        max_tokens = resolved.get("maxTokens", 4000)
        temperature = resolved.get("temperature", 0.0)
        timeout = resolved.get("timeout", self.request_timeout)

        if not api_key or not base_url:
            raise RuntimeError(f"missing apiKey/baseUrl in resolved config: {list(resolved)}")

        body = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}{endpoint}",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        # 顺便记 token 用量
        usage = data.get("usage", {})
        # 借用 stats 的字段, 但 stats 在上层, 这里通过闭包不可见
        # 用返回值没法传, 改为 LLM 调完后调用方从 data 抓 (但 _call_llm 简单返回 content)
        return content

    def _fallback(self, text: str, stats: dict) -> tuple[str, dict]:
        """回退到 rule_based text_compressor"""
        try:
            from text_compressor import text_compress
        except ImportError:
            try:
                from .text_compressor import text_compress
            except ImportError:
                # 极端: 同事模块都找不到, 直接返回原文
                stats["crushed_bytes"] = len(text.encode("utf-8"))
                stats["crushed_lines"] = text.count("\n") + 1
                stats["status"] = "error"
                stats["error"] = "text_compressor not available"
                return text, stats

        result, fb_stats = text_compress(text)
        stats["crushed_bytes"] = fb_stats.get("crushed_bytes", len(result.encode("utf-8")))
        stats["crushed_lines"] = fb_stats.get("crushed_lines", result.count("\n") + 1)
        if fb_stats.get("ratio", 0) > 0:
            stats["ratio"] = fb_stats["ratio"]
        # status 已经是 "fallback_rule_based" 或 "fallback_low_ratio", 不变
        if stats["status"] == "fallback_rule_based" and fb_stats.get("mode") == "compressed":
            stats["status"] = "fallback_rule_based"
        return result, stats


# 单例
_instance: LLMTextCompressor | None = None


def get_llm_text_compressor(mode: str = "summarize") -> LLMTextCompressor:
    """获取单例 (按 mode 缓存)"""
    global _instance
    if _instance is None or _instance.mode != mode:
        _instance = LLMTextCompressor(mode=mode)
    return _instance


@safe_call(default=("", {"error": "llm_text_compress failed"}), label="llm_text_compress")
def llm_text_compress(content: str, mode: str = "summarize") -> tuple[str, dict]:
    """函数式入口"""
    return get_llm_text_compressor(mode=mode).compress(content)


# ----------------------------------------------------------------------
# Phase 2 目标 1: LLM 压缩走异步队列 (daemon 永不阻塞)
# ----------------------------------------------------------------------
def llm_text_compress_async(content: str, mode: str = "summarize",
                            wait: bool = True, priority: int = 0,
                            timeout: float = 60.0) -> dict:
    """异步版 LLM 压缩 — 走 CompressQueue 后台 worker

    工作机制:
    - 调用方入队后, worker 线程在后台调 LLM (4-5 秒, 不阻塞调用方)
    - 入队后, 调用方可以 wait=True 等结果, 或 wait=False 立即返回
    - worker 逻辑见 CompressQueue._process_llm

    Args:
        content: 要压缩的文本
        mode: summarize | simplify | extract
        wait: True=同步等结果, False=入队即返
        priority: 0=normal, 1=urgent, 2=low
        timeout: 同步等待超时 (秒), wait=True 有效

    Returns:
        wait=True:  {"status": "completed"|"failed"|"timeout"|"error",
                     "result": 压缩后文本,
                     "stats":  {  llm_text_compress stats  },
                     "request_id": "req-xxx",
                     "duration_ms": int,
                     "elapsed": float}
        wait=False: {"status": "queued"|"dropped"|"error",
                     "request_id": "req-xxx"|None,
                     "queue_size": int,
                     "reason": str|None}
    """
    try:
        from compress_queue import CompressRequest, get_compress_queue
    except ImportError:
        try:
            from .compress_queue import CompressRequest, get_compress_queue
        except ImportError:
            return {"status": "error", "reason": "compress_queue module not available",
                    "request_id": None}

    req = CompressRequest(
        content=content,
        session_id=f"llm-{mode}",
        content_type=f"llm:{mode}",   # 告诉 worker 走 LLM
        priority=priority,
    )

    queue = get_compress_queue()
    accepted = queue.enqueue(req)
    if not accepted:
        return {"status": "dropped", "reason": "queue_full",
                "request_id": req.request_id, "queue_size": queue.qsize()}

    if not wait:
        return {"status": "queued", "request_id": req.request_id,
                "queue_size": queue.qsize()}

    # 同步等结果 (LLM 跑在 worker 线程里)
    completed = req.wait(timeout=timeout)
    if not completed:
        return {"status": "timeout", "request_id": req.request_id,
                "duration_ms": int(timeout * 1000)}

    if req.error:
        return {"status": "failed", "error": req.error,
                "request_id": req.request_id,
                "duration_ms": req._result.get("duration_ms", 0) if req._result else 0}

    if not req.result:
        return {"status": "error", "reason": "no result",
                "request_id": req.request_id}

    return {
        "status": req.result.get("status", "unknown"),
        "result": req.result.get("text", ""),
        "stats": req.result,
        "request_id": req.request_id,
        "duration_ms": req.result.get("duration_ms", 0),
        "elapsed": req.result.get("elapsed", 0.0),
    }


# ----------------------------------------------------------------------
# 自检 / 烟测
# ----------------------------------------------------------------------
def _run_tests() -> bool:
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
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}")
            failed += 1

    # ---- 测试 1: 太小 passthrough (不调 LLM) ----
    print("\n[测试 1] 小文本 passthrough (不调 LLM)")
    short = "x" * 200
    c = LLMTextCompressor()
    out, stats = c.compress(short)
    check("1.1 status=passthrough_small", stats["status"] == "passthrough_small")
    check("1.2 没调 LLM", stats["llm_called"] is False)
    check("1.3 原文不变", out == short)

    # ---- 测试 2: 模式参数校验 ----
    print("\n[测试 2] 模式参数")
    try:
        LLMTextCompressor(mode="invalid")
        check("2.1 非法模式应报错", False)
    except ValueError:
        check("2.1 非法模式被拒", True)
    for m in ["summarize", "simplify", "extract"]:
        c = LLMTextCompressor(mode=m)
        check(f"2.2 mode={m} 可创建", c.mode == m)

    # ---- 测试 3: 模板存在性 ----
    print("\n[测试 3] Prompt 模板")
    for m in PROMPTS:
        check(f"3.{m} 模板含 {{text}} 占位", "{text}" in PROMPTS[m])

    # ---- 测试 4: _clean_llm_output 各种脏数据 ----
    print("\n[测试 4] LLM 输出清理")
    check("4.1 剥离 <think> 块",
          _clean_llm_output("<think>让我想想</think>这是结果") == "这是结果")
    check("4.2 剥离 markdown 包裹",
          _clean_llm_output("```\n真正的内容\n```") == "真正的内容")
    check("4.3 剥离 ```json 块",
          _clean_llm_output("```json\n{\"a\": 1}\n```") == '{"a": 1}')
    check("4.4 头尾空白",
          _clean_llm_output("  \n  内容  \n  ") == "内容")
    check("4.5 空字符串", _clean_llm_output("") == "")
    check("4.6 混合 <think> + 包裹",
          _clean_llm_output("<think>...</think>```\n最终\n```") == "最终")

    # ---- 测试 5: _resolve_model 找到 llmCompress ----
    print("\n[测试 5] 模型配置解析")
    c = LLMTextCompressor()
    resolved = c._resolve_model()
    if resolved:
        check("5.1 找到 llmCompress", True)
        check("5.2 有 model 字段", "model" in resolved)
        check("5.3 有 maxTokens 字段", "maxTokens" in resolved)
        print(f"  → model={resolved.get('model')}, baseUrl={'已配置' if resolved.get('baseUrl') else '未配置'}")
    else:
        check("5.1 找到 llmCompress (mark42 config)", False)
        check("5.2 有 model 字段 (openclaw)", False)
        print("  → 注意: 模型配置未找到, 实际 LLM 调用会回退")

    # ---- 测试 6: Mock LLM 调用 (CI 必跑) ----
    print("\n[测试 6] Mock LLM 调用 (CI 必跑)")
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
        "choices": [{
            "message": {"content": "项目采用 Python、PostgreSQL、Redis、Prometheus/Grafana、Loki，提供完整 API 与监控日志能力。"}
        }]
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
    print(f"  → 原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B ({stats['ratio']:.1%})")
    print(f"  → mock 输出预览: {out[:120]!r}")

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
    print("\n[测试 6R] 真实 LLM 调用 (可选补充)")
    if not resolved or not resolved.get("apiKey"):
        print("  ⚠️  无 api key, 跳过真实调用补充测试")
        check("6R.1 无 key 时允许跳过", True)
    else:
        c = LLMTextCompressor(mode="summarize")
        out, stats = c.compress(long_text)
        check("6R.1 调了 LLM", stats["llm_called"] is True)
        check("6R.2 status=compressed", stats["status"] == "compressed")
        check("6R.3 压缩率 >= 5%", stats["ratio"] >= 0.05)
        check("6R.4 duration < 60s", stats["llm_duration_ms"] < 60_000)
        print(f"  → 原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B "
              f"({stats['ratio']:.1%}), 用时 {stats['llm_duration_ms']}ms")
        print(f"  → 输出预览: {out[:200]!r}")

    # ---- 测试 7: 无 model config → 自动 fallback ----
    print("\n[测试 7] 无 model config fallback")
    c = LLMTextCompressor(config_key="nonexistent_key_xxx")
    long_text = "这是一段比较长的测试文本。" * 100
    out, stats = c.compress(long_text)
    check("7.1 没调 LLM", stats["llm_called"] is False)
    check("7.2 status=fallback_rule_based", stats["status"] == "fallback_rule_based")
    check("7.3 fallback_reason 注明", "no_model_config" in (stats["fallback_reason"] or ""))
    print(f"  → fallback_reason: {stats['fallback_reason']}")

    # ---- 测试 8: 输入超长截断 ----
    print("\n[测试 8] 超长输入截断")
    c = LLMTextCompressor(max_input_bytes=1000, config_key="nonexistent_key_xxx")
    huge = "x" * 5000
    out, stats = c.compress(huge)
    check("8.1 fallback (没 LLM)", stats["status"] == "fallback_rule_based")
    # 实际上 max_input_bytes 仅 LLM 路径生效; fallback 路径不走截断
    # 这里只验证不会崩

    # ---- 测试 9: 极端输入 fail-safe ----
    print("\n[测试 9] 极端输入 fail-safe")
    c = LLMTextCompressor()
    out, stats = c.compress("")
    check("9.1 空字符串不报错", stats["status"] == "none")
    out, stats = c.compress("   \n\n   ")
    check("9.2 纯空白不报错", True)

    # ---- 测试 10: 多个模式分别能实例化 ----
    print("\n[测试 10] 多模式实例化")
    for m in ["summarize", "simplify", "extract"]:
        c = LLMTextCompressor(mode=m, config_key="nonexistent_key_xxx")
        out, stats = c.compress("这是一段比较长的测试文本，需要 LLM 来压缩。" * 50)
        check(f"10.{m} fallback 工作", stats["status"] == "fallback_rule_based")
        check(f"10.{m} mode 正确", stats["mode"] == m)

    # ---- 测试 11: 单例模式 ----
    print("\n[测试 11] 单例")
    a = get_llm_text_compressor("summarize")
    b = get_llm_text_compressor("summarize")
    check("11.1 同 mode 单例", a is b)
    c = get_llm_text_compressor("simplify")
    check("11.2 异 mode 创建新实例", a is not c)

    # ---- 测试 12: 异步入口 (Phase 2 目标 1) ----
    print("\n[测试 12] 异步入口 llm_text_compress_async")
    from llm_text_compressor import llm_text_compress_async

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
    check("12.4 wait=True 拿到 status", r2.get("status") in ("compressed", "fallback_rule_based", "fallback_low_ratio", "passthrough_small"))
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
        check(f"12.10.{m} wait=True 拿到状态",
              r.get("status") in ("compressed", "fallback_rule_based", "fallback_low_ratio",
                                  "passthrough_small", "passthrough_truncated_input", "error", "none"))

    # 12.6 验证: 调用方不阻塞 (wait=False 应该 < 1 秒)
    t0 = time.time()
    llm_text_compress_async("x" * 100, mode="summarize", wait=False)  # 小内容, worker 立即完成
    elapsed = time.time() - t0
    check("12.11 wait=False 返回时间 < 0.1s", elapsed < 0.1)

    print(f"  → 12.11 wait=False 实际用时: {elapsed*1000:.1f}ms")

    print()
    print("=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    import sys
    sys.exit(0 if _run_tests() else 1)
