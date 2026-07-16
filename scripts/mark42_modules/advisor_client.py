"""
Mark42 v3-4 · 主动交流协议 (Advisor Client)

按 v3 §3.4 钉死的主动交流协议实现：
- OpenAI Chat Completions 兼容调用
- response_format: json_object 强制结构化返回
- 响应契约: verdict / confidence / reasoning / modified_plan
- advisor 没开 / 超时 / 返回不合法 -> fallback 到"问用户"（不卡住战甲）

设计原则（R 编号引用 v3 §0.2）：
- R3 小模型能主动发起对话（问用户 / 问外部大模型）
- R4 确定性：advisor 返回 approve 且 confidence >= 阈值才走；否则问用户
- R5 边界：advisor 只是顾问，不是操作员（§3.5 第 7 条）
- R8 小模型不参与最终决策：advisor 的 verdict 由意识层引用，不直接执行
- R13 故障隔离：advisor 挂了 -> 降级到问用户，不崩

4 类对话场景（§3.3）：
  A. 自检后不确定是不是真问题
  B. 知道坏了但修法不确定
  C. 新类型异常（第一次见）
  D. 学过的错误走档案（C5 路径，本模块仅提供"按上次方案确认"接口）
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# 复用 v3-1 的基础设施
from .llm_provider import (
    ChatMessage,
    LLMProvider,
    build_advisor,
    load_config,
)

logger = logging.getLogger(__name__)


# ── 常量 ─────────────────────────────────────────────

# advisor 响应契约的 system prompt（§3.4 钉死）
ADVISOR_SYSTEM_PROMPT = """\
你是 Mark42 战甲的外部顾问。战甲会带着上下文问你技术方案的安全性。

你必须返回 JSON 对象，格式如下：
{
  "verdict": "approve" | "reject" | "modify",
  "confidence": 0.0-1.0,
  "reasoning": "你的推理过程（简洁）",
  "modified_plan": {
    "steps": ["步骤1", "步骤2"],
    "changes": "如果 verdict=modify，说明改了什么"
  }
}

规则：
- verdict=approve: 方案安全，可以执行
- verdict=reject: 方案不安全，不应该执行
- verdict=modify: 方案基本可行但需要调整，在 modified_plan 里给出调整后的方案
- confidence: 你对 verdict 的确信度（0.0=完全不确定, 1.0=绝对确定）
- 只返回 JSON，不要加其他文字
"""

# 默认置信度阈值（高于这个才信 advisor）
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

# 默认超时（秒）
DEFAULT_TIMEOUT = 30


# ── 数据类 ───────────────────────────────────────────

@dataclass
class AdvisorVerdict:
    """advisor 返回的响应契约（§3.4 钉死）。"""
    verdict: str           # "approve" | "reject" | "modify"
    confidence: float      # 0.0 - 1.0
    reasoning: str         # 推理过程
    modified_plan: Optional[Dict[str, Any]] = None   # verdict=modify 时才有
    raw_response: Optional[str] = None               # 原始返回（调试用）
    elapsed_ms: int = 0   # 耗时

    @property
    def is_approve(self) -> bool:
        return self.verdict == "approve"

    @property
    def is_reject(self) -> bool:
        return self.verdict == "reject"

    @property
    def is_modify(self) -> bool:
        return self.verdict == "modify"

    @property
    def is_trustworthy(self) -> bool:
        """confidence 达标且 verdict 合法。

        注意：这里用全局常量 DEFAULT_CONFIDENCE_THRESHOLD 做基础判断。
        AdvisorClient.ask() 内部会用实例级 self.confidence_threshold 做二次判断，
        所以即使这里返回 True，ask() 仍可能因低置信度降级。
        """
        return self.confidence >= DEFAULT_CONFIDENCE_THRESHOLD and self.verdict in ("approve", "reject", "modify")

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }
        if self.modified_plan:
            d["modified_plan"] = self.modified_plan
        return d


@dataclass
class AdvisorResult:
    """一次 advisor 调用的完整结果（含降级信息）。"""
    success: bool                         # advisor 是否成功返回
    verdict: Optional[AdvisorVerdict] = None
    fallback_reason: Optional[str] = None  # success=False 时的原因
    fallback_action: str = "ask_user"     # 降级行为: "ask_user" | "execute_anyway"

    @property
    def should_ask_user(self) -> bool:
        """是否需要问用户。"""
        if not self.success:
            return True
        if self.verdict and self.verdict.is_trustworthy and self.verdict.is_approve:
            return False
        if self.verdict and self.verdict.is_reject:
            return True
        # modify 且可信 -> 不问用户，按 modified_plan 走（但意识层有权覆盖）
        if self.verdict and self.verdict.is_modify and self.verdict.is_trustworthy:
            return False
        return True


# ── 场景 prompt 构造器（§3.3 四类场景）────────────────

def build_scenario_a_prompt(issue: Dict[str, Any], assessment: Dict[str, Any]) -> str:
    """场景 A: 自检后不确定是不是真问题。"""
    return (
        f"我在自检时发现了一个信号，但不确定它是不是真问题。\n\n"
        f"信号来源: {issue.get('source', 'unknown')}\n"
        f"类型: {issue.get('category', 'unknown')}\n"
        f"描述: {issue.get('msg', 'N/A')}\n"
        f"我的评估: 确定性={assessment.get('certainty', 'unknown')}\n\n"
        f"请帮我判断：这是真问题还是可以忽略？如果需要处理，你建议怎么做？"
    )


def build_scenario_b_prompt(issue: Dict[str, Any], plan: Dict[str, Any]) -> str:
    """场景 B: 知道坏了但修法不确定。"""
    steps = plan.get("steps", [])
    steps_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps))
    return (
        f"我检测到一个故障，有一个修复方案但不确定是否安全。\n\n"
        f"故障: {issue.get('source', '')}:{issue.get('category', '')}\n"
        f"描述: {issue.get('msg', 'N/A')}\n\n"
        f"我的修复方案:\n{steps_str}\n\n"
        f"环境信息:\n"
        f"  - 历史耗时: {plan.get('estimated_time', 'unknown')}\n"
        f"  - 影响范围: {plan.get('impact', 'unknown')}\n\n"
        f"这个方案安全吗？有什么我需要注意的？"
    )


def build_scenario_c_prompt(issue: Dict[str, Any]) -> str:
    """场景 C: 新类型异常（第一次见）。"""
    return (
        f"我发现了一种新类型的异常，我的规则表里没有见过。\n\n"
        f"类型: {issue.get('source', 'unknown')}:{issue.get('category', 'unknown')}\n"
        f"描述: {issue.get('msg', 'N/A')}\n"
        f"上下文: {json.dumps(issue.get('context', {}), ensure_ascii=False, default=str)[:500]}\n\n"
        f"我不敢动这个。请帮我判断：这是什么？有没有风险？应该怎么处理？"
    )


def build_scenario_d_prompt(archive_entry: Dict[str, Any]) -> str:
    """场景 D: 学过的错误走档案。"""
    return (
        f"这条异常和我在错误档案里见过的一条很像。\n\n"
        f"档案 ID: {archive_entry.get('id', 'N/A')}\n"
        f"上次分类: {archive_entry.get('category', 'N/A')}\n"
        f"上次诊断: {archive_entry.get('diagnosis', 'N/A')}\n"
        f"上次方案: {json.dumps(archive_entry.get('resolution', {}), ensure_ascii=False, default=str)[:300]}\n\n"
        f"我准备按上次的方案走。你确认这个方案在当前情况下还适用吗？"
    )


# ── AdvisorClient 主类 ───────────────────────────────

class AdvisorClient:
    """主动交流协议客户端。

    封装 §3.4 的 OpenAI 兼容调用 + 响应契约解析。
    advisor 没开 / 超时 / 返回不合法 -> 降级到"问用户"。

    使用方式:
        client = AdvisorClient()             # 从 model.yaml 读配置
        client = AdvisorClient(config_dict)  # 传配置字典

        result = client.ask(scenario="a", issue={...}, assessment={...})
        if result.should_ask_user:
            # 问用户
        else:
            # 按 advisor 的 verdict 走
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 advisor client。

        Args:
            config: 配置字典（model.yaml 格式）。None -> 从文件读。
        """
        self.config = config or load_config()
        self.provider: Optional[LLMProvider] = build_advisor(self.config)
        self.advisor_cfg = self.config.get("mark42", {}).get("advisor", {})
        self.enabled = self.advisor_cfg.get("enabled", False)
        self.timeout = self.advisor_cfg.get("timeout_seconds", DEFAULT_TIMEOUT)
        self.confidence_threshold = self.advisor_cfg.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)

    # ── 核心调用 ──

    def ask(self, scenario: str, **kwargs) -> AdvisorResult:
        """发起一次 advisor 对话。

        Args:
            scenario: "a" | "b" | "c" | "d"（对应 §3.3 四类场景）
            **kwargs: 场景需要的参数
                - a: issue, assessment
                - b: issue, plan
                - c: issue
                - d: archive_entry

        Returns:
            AdvisorResult: 包含 verdict 或 fallback 原因
        """
        if not self.enabled or self.provider is None:
            return AdvisorResult(
                success=False,
                fallback_reason="advisor_not_enabled",
                fallback_action="ask_user",
            )

        # 构造 prompt
        try:
            user_content = self._build_prompt(scenario, **kwargs)
        except Exception as e:
            logger.error("构造 advisor prompt 失败: %s", e)
            return AdvisorResult(
                success=False,
                fallback_reason=f"prompt_build_failed: {e}",
                fallback_action="ask_user",
            )

        # 调用 advisor
        messages = [
            ChatMessage(role="system", content=ADVISOR_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

        t0 = time.monotonic()
        try:
            raw = self.provider.chat(messages, response_format={"type": "json_object"})
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.warning("advisor 调用失败 (%dms): %s", elapsed, e)
            return AdvisorResult(
                success=False,
                fallback_reason=f"api_error: {e}",
                fallback_action="ask_user",
            )

        elapsed = int((time.monotonic() - t0) * 1000)

        # 解析响应
        verdict = self._parse_response(raw, elapsed)
        if verdict is None:
            return AdvisorResult(
                success=False,
                fallback_reason="response_parse_failed",
                fallback_action="ask_user",
            )

        # 检查置信度
        if verdict.confidence < self.confidence_threshold:
            logger.info("advisor confidence %.2f < 阈值 %.2f, 降级到问用户",
                       verdict.confidence, self.confidence_threshold)
            return AdvisorResult(
                success=True,
                verdict=verdict,
                fallback_reason=f"low_confidence: {verdict.confidence:.2f}",
                fallback_action="ask_user",
            )

        return AdvisorResult(success=True, verdict=verdict)

    # ── 场景便捷方法 ──

    def ask_about_uncertain_issue(self, issue: Dict[str, Any], assessment: Dict[str, Any]) -> AdvisorResult:
        """场景 A: 自检后不确定是不是真问题。"""
        return self.ask("a", issue=issue, assessment=assessment)

    def ask_about_remediation_plan(self, issue: Dict[str, Any], plan: Dict[str, Any]) -> AdvisorResult:
        """场景 B: 知道坏了但修法不确定。"""
        return self.ask("b", issue=issue, plan=plan)

    def ask_about_new_anomaly(self, issue: Dict[str, Any]) -> AdvisorResult:
        """场景 C: 新类型异常。"""
        return self.ask("c", issue=issue)

    def ask_about_archive_reuse(self, archive_entry: Dict[str, Any]) -> AdvisorResult:
        """场景 D: 学过的错误走档案。"""
        return self.ask("d", archive_entry=archive_entry)

    # ── 内部方法 ──

    def _build_prompt(self, scenario: str, **kwargs) -> str:
        """根据场景构造 user prompt。"""
        if scenario == "a":
            return build_scenario_a_prompt(kwargs["issue"], kwargs["assessment"])
        elif scenario == "b":
            return build_scenario_b_prompt(kwargs["issue"], kwargs["plan"])
        elif scenario == "c":
            return build_scenario_c_prompt(kwargs["issue"])
        elif scenario == "d":
            return build_scenario_d_prompt(kwargs["archive_entry"])
        else:
            raise ValueError(f"未知场景: {scenario}（只支持 a/b/c/d）")

    def _parse_response(self, raw: Any, elapsed_ms: int) -> Optional[AdvisorVerdict]:
        """解析 advisor 返回的 JSON 响应。

        支持两种输入格式:
        1. ChatResponse 对象（llm_provider.py 返回的统一结构，用 .content）
        2. 原始 dict（OpenAI 格式，用 choices[0].message.content）
        """
        try:
            # 判断是 ChatResponse 对象还是原始 dict
            if hasattr(raw, 'content'):
                content = raw.content or ""
            elif isinstance(raw, dict):
                choices = raw.get("choices", [])
                if not choices:
                    logger.warning("advisor 返回空 choices")
                    return None
                content = choices[0].get("message", {}).get("content", "")
            else:
                logger.warning("advisor 返回未知类型: %s", type(raw).__name__)
                return None

            if not content:
                logger.warning("advisor 返回空 content")
                return None

            # 剥离 markdown 代码块包裹（```json ... ```）
            content = content.strip()
            if content.startswith("```"):
                # 去掉第一行（```json 或 ```）
                lines = content.split("\n")
                if len(lines) > 1:
                    content = "\n".join(lines[1:])
                # 去掉末尾的 ```
                if content.rstrip().endswith("```"):
                    content = content.rstrip()[:-3].strip()

            # content 应该是 JSON 字符串
            parsed = json.loads(content)

            verdict_str = parsed.get("verdict", "").lower().strip()
            if verdict_str not in ("approve", "reject", "modify"):
                logger.warning("advisor verdict 非法: %s", verdict_str)
                return None

            confidence = float(parsed.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))  # clamp

            reasoning = parsed.get("reasoning", "")
            modified_plan = parsed.get("modified_plan")  # 可能为 None

            return AdvisorVerdict(
                verdict=verdict_str,
                confidence=confidence,
                reasoning=reasoning,
                modified_plan=modified_plan,
                raw_response=content,
                elapsed_ms=elapsed_ms,
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("advisor 响应解析失败: %s (raw: %s)", e, str(raw)[:200])
            return None

    # ── 健康检查 ──

    def health_check(self) -> Dict[str, Any]:
        """检查 advisor 状态（不真正调用 API）。

        Returns:
            {"enabled": bool, "configured": bool, "model": str, "base_url": str}
        """
        return {
            "enabled": self.enabled,
            "configured": bool(self.enabled and self.advisor_cfg.get("model") and self.advisor_cfg.get("base_url")),
            "model": self.advisor_cfg.get("model", ""),
            "base_url": self.advisor_cfg.get("base_url", ""),
            "has_api_key": bool(self.advisor_cfg.get("api_key")),
            "confidence_threshold": self.confidence_threshold,
            "timeout": self.timeout,
        }

    def ping(self) -> AdvisorResult:
        """发一个最简单的 ping 请求，确认 advisor 可达。

        用于 `mark42 consciousness advisor --test` 烟测。
        """
        if not self.enabled or self.provider is None:
            return AdvisorResult(
                success=False,
                fallback_reason="advisor_not_enabled",
            )

        messages = [
            ChatMessage(role="system", content="你是 Mark42 战甲的外部顾问。只返回 JSON。"),
            ChatMessage(
                role="user",
                content='请返回 {"verdict": "approve", "confidence": 1.0, "reasoning": "ping ok"}',
            ),
        ]

        t0 = time.monotonic()
        try:
            raw = self.provider.chat(messages, response_format={"type": "json_object"})
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            return AdvisorResult(
                success=False,
                fallback_reason=f"ping_failed ({elapsed}ms): {e}",
            )

        elapsed = int((time.monotonic() - t0) * 1000)
        verdict = self._parse_response(raw, elapsed)

        if verdict and verdict.is_approve:
            return AdvisorResult(success=True, verdict=verdict)
        else:
            return AdvisorResult(
                success=False,
                verdict=verdict,
                fallback_reason="ping_response_invalid",
            )


# ── CLI 接口（供 mark42.py consciousness advisor 调用）────────

def cli_advisor_status(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """CLI: 查看 advisor 配置状态。"""
    client = AdvisorClient(config)
    return client.health_check()


def cli_advisor_test(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """CLI: advisor 烟测 ping。

    返回:
        {"success": bool, "verdict": ..., "elapsed_ms": int, "reason": ...}
    """
    client = AdvisorClient(config)
    result = client.ping()
    d: Dict[str, Any] = {
        "success": result.success,
        "elapsed_ms": result.verdict.elapsed_ms if result.verdict else 0,
    }
    if result.verdict:
        d["verdict"] = result.verdict.to_dict()
    if result.fallback_reason:
        d["reason"] = result.fallback_reason
    return d


def cli_advisor_ask(
    scenario: str,
    issue: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """CLI: 发起一次 advisor 对话（调试用）。

    Args:
        scenario: "a" | "b" | "c" | "d"
        issue: 故障信息字典
        config: 配置字典
        **kwargs: 场景额外参数
    """
    client = AdvisorClient(config)
    issue = issue or {"source": "cli", "category": "test", "msg": "CLI 调试请求"}

    if scenario == "a":
        result = client.ask_about_uncertain_issue(issue, kwargs.get("assessment", {"certainty": "unknown"}))
    elif scenario == "b":
        result = client.ask_about_remediation_plan(issue, kwargs.get("plan", {"steps": ["test"]}))
    elif scenario == "c":
        result = client.ask_about_new_anomaly(issue)
    elif scenario == "d":
        result = client.ask_about_archive_reuse(kwargs.get("archive_entry", {"id": "ERR-TEST"}))
    else:
        return {"error": f"未知场景: {scenario}"}

    d: Dict[str, Any] = {
        "success": result.success,
        "should_ask_user": result.should_ask_user,
    }
    if result.verdict:
        d["verdict"] = result.verdict.to_dict()
        d["elapsed_ms"] = result.verdict.elapsed_ms
    if result.fallback_reason:
        d["fallback_reason"] = result.fallback_reason
    return d
