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
import re
import time
import urllib.error
import urllib.request
from typing import Any

# 【2026-07-13】不能用相对路径, perf_bench/algo_scheduler 从外部 import
from .utils import safe_call

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

    def __init__(
        self,
        mode: str = "summarize",
        min_text_size: int = 500,
        max_input_bytes: int = 12000,
        min_useful_ratio: float = 0.05,
        max_useful_ratio: float = 0.98,
        request_timeout: int = 60,
        config_key: str = "llmCompress",
    ):
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
            "status": "none",  # "compressed" | "passthrough_small" | "fallback_rule_based" | "fallback_low_ratio" | "error" | "passthrough_truncated_input"
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
            text = text.encode("utf-8")[: self.max_input_bytes].decode("utf-8", errors="ignore")
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

        body = json.dumps(
            {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        ).encode("utf-8")

        req = urllib.request.Request(  # noqa: S310
            f"{base_url}{endpoint}",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        # 顺便记 token 用量
        _usage = data.get("usage", {})  # noqa: F841
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
def llm_text_compress_async(
    content: str, mode: str = "summarize", wait: bool = True, priority: int = 0, timeout: float = 60.0
) -> dict:
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
            return {"status": "error", "reason": "compress_queue module not available", "request_id": None}

    req = CompressRequest(
        content=content,
        session_id=f"llm-{mode}",
        content_type=f"llm:{mode}",  # 告诉 worker 走 LLM
        priority=priority,
    )

    queue = get_compress_queue()
    accepted = queue.enqueue(req)
    if not accepted:
        return {"status": "dropped", "reason": "queue_full", "request_id": req.request_id, "queue_size": queue.qsize()}

    if not wait:
        return {"status": "queued", "request_id": req.request_id, "queue_size": queue.qsize()}

    # 同步等结果 (LLM 跑在 worker 线程里)
    completed = req.wait(timeout=timeout)
    if not completed:
        return {"status": "timeout", "request_id": req.request_id, "duration_ms": int(timeout * 1000)}

    if req.error:
        return {
            "status": "failed",
            "error": req.error,
            "request_id": req.request_id,
            "duration_ms": req._result.get("duration_ms", 0) if req._result else 0,
        }

    if not req.result:
        return {"status": "error", "reason": "no result", "request_id": req.request_id}

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
    """运行测试（已提取到 tests/test_llm_text_compressor.py）。"""
    from tests.test_llm_text_compressor import run_tests

    return run_tests()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    import sys

    sys.exit(0 if _run_tests() else 1)
