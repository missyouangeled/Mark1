"""核对引擎：对比 compact 前关键信息与 compact 后摘要。

两种实现：
    LLMChecker  -- 用 LLM 做语义对比（默认，准确但耗 token）
    RuleChecker -- 用关键词匹配（fallback，快但浅层）

选择逻辑：优先 LLM，失败/超时降级到 Rule。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from . import AUDIT_CATEGORIES, Finding, AuditResult, VERDICT_PASS_THRESHOLD, VERDICT_FAIL_CATEGORIES


# ── 接口 ──────────────────────────────────────────────


@runtime_checkable
class Checker(Protocol):
    """核对引擎接口。"""

    def check(
        self,
        pre_info: Dict[str, List[str]],
        post_summary: str,
    ) -> AuditResult:
        """对比关键信息与摘要，返回核对结果。"""
        ...


# ── LLM 核对引擎 ─────────────────────────────────────


class LLMChecker:
    """用 LLM 逐项核对关键信息是否在摘要中保留。

    优点：语义理解强，能判断"换个说法但意思保留了"
    缺点：耗 token
    """

    def __init__(self) -> None:
        self._llm_call = None  # 延迟初始化

    def _get_llm(self):
        """延迟加载 LLM provider。"""
        if self._llm_call is not None:
            return self._llm_call
        try:
            from ..llm_provider import get_llm_provider
            provider = get_llm_provider()
            if provider:
                self._llm_call = provider
            return self._llm_call
        except Exception:
            return None

    def check(
        self,
        pre_info: Dict[str, List[str]],
        post_summary: str,
    ) -> AuditResult:
        """用 LLM 做语义对比。"""
        llm = self._get_llm()
        if llm is None:
            # 降级到规则引擎
            return RuleChecker().check(pre_info, post_summary)

        # 构造 LLM prompt
        prompt = self._build_prompt(pre_info, post_summary)

        try:
            response = llm.chat(
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=2000,
                timeout=60,  # 60 秒超时，避免审计线程长时间悬挂
            )
            return self._parse_llm_response(response, pre_info)
        except Exception as e:
            # LLM 失败或超时，降级到规则引擎
            rule_result = RuleChecker().check(pre_info, post_summary)
            rule_result.error = f"LLM 降级: {e}"
            return rule_result

    _SYSTEM_PROMPT = """你是 Mark42 战甲的压缩审计系统。你的任务是核对压缩后的摘要是否保留了压缩前的关键信息。

规则：
1. 逐项核对每个关键信息是否在摘要中保留
2. 判定标准：
   - preserved: 信息完整保留（允许换说法，语义等价）
   - degraded: 信息部分保留（有相关信息但不完整）
   - lost: 信息完全没有
3. 只输出 JSON，不要解释

输出格式：
```json
{
  "findings": [
    {"category": "identity", "item": "用户: 袁文涛", "status": "preserved", "detail": "摘要中提到了用户名"},
    {"category": "preferences", "item": "语言锁定: 中文", "status": "lost", "detail": "摘要中未提及语言规则"}
  ],
  "recommendation": "简要建议"
}
```"""

    def _build_prompt(self, pre_info: Dict[str, List[str]], post_summary: str) -> str:
        """构造 LLM 核对 prompt。"""
        lines = ["请核对以下压缩前的关键信息是否在压缩后的摘要中保留：\n"]
        lines.append("## 压缩前的关键信息\n")
        for cat in AUDIT_CATEGORIES:
            items = pre_info.get(cat, [])
            if items:
                lines.append(f"### {cat}")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

        lines.append("## 压缩后的摘要\n")
        lines.append(post_summary[:4000])  # 限制长度
        lines.append("\n\n请逐项核对并输出 JSON 结果。")

        return "\n".join(lines)

    def _parse_llm_response(self, response: str, pre_info: Dict[str, List[str]]) -> AuditResult:
        """解析 LLM 返回的 JSON。"""
        findings: List[Finding] = []

        # 尝试从 response 提取 JSON
        json_str = response
        if "```json" in response:
            m = re.search(r"```json\s*(.+?)```", response, re.DOTALL)
            if m:
                json_str = m.group(1)
        elif "```" in response:
            m = re.search(r"```\s*(.+?)```", response, re.DOTALL)
            if m:
                json_str = m.group(1)

        try:
            data = json.loads(json_str)
            for f in data.get("findings", []):
                findings.append(Finding(
                    category=f.get("category", ""),
                    item=f.get("item", ""),
                    status=f.get("status", "lost"),
                    detail=f.get("detail", ""),
                ))
            recommendation = data.get("recommendation", "")
        except (json.JSONDecodeError, TypeError):
            # JSON 解析失败，降级到规则
            return RuleChecker().check(pre_info, response)

        # 计算分数和 verdict
        return self._compute_result(findings, recommendation)

    def _compute_result(self, findings: List[Finding], recommendation: str = "") -> AuditResult:
        """从 findings 计算 verdict 和 score。"""
        if not findings:
            return AuditResult(
                verdict="pass",
                score=1.0,
                findings=[],
                recommendation="无关键信息需要核对",
            )

        preserved = sum(1 for f in findings if f.status == "preserved")
        degraded = sum(1 for f in findings if f.status == "degraded")
        lost = sum(1 for f in findings if f.status == "lost")

        total = len(findings)
        score = (preserved + 0.5 * degraded) / total if total > 0 else 1.0

        # verdict 判定
        verdict = "pass"
        if score < VERDICT_PASS_THRESHOLD:
            verdict = "partial"

        # 关键类别全 lost -> fail
        for cat in VERDICT_FAIL_CATEGORIES:
            cat_findings = [f for f in findings if f.category == cat]
            if cat_findings and all(f.status == "lost" for f in cat_findings):
                verdict = "fail"
                break

        if not recommendation:
            if verdict == "fail":
                recommendation = "关键信息严重丢失，建议从数据盘快照恢复记忆"
            elif verdict == "partial":
                recommendation = "部分信息丢失，关注 degraded/lost 项"
            else:
                recommendation = "信息保留完整"

        return AuditResult(
            verdict=verdict,
            score=round(score, 2),
            findings=findings,
            recommendation=recommendation,
        )


# ── 规则核对引擎（fallback）────────────────────────────


class RuleChecker:
    """用关键词匹配做浅层核对。

    优点：快、不耗 token
    缺点：只能做浅层匹配，不能理解语义等价
    """

    def check(
        self,
        pre_info: Dict[str, List[str]],
        post_summary: str,
    ) -> AuditResult:
        """用关键词匹配核对。"""
        findings: List[Finding] = []
        summary_lower = post_summary.lower()

        for cat in AUDIT_CATEGORIES:
            items = pre_info.get(cat, [])
            for item in items:
                # 提取关键词
                keywords = self._extract_keywords(item)
                if not keywords:
                    findings.append(Finding(
                        category=cat, item=item, status="degraded",
                        detail="无法提取关键词",
                    ))
                    continue

                # 检查关键词是否在摘要中
                matched = sum(1 for kw in keywords if kw.lower() in summary_lower)
                ratio = matched / len(keywords) if keywords else 0

                if ratio >= 0.8:
                    status = "preserved"
                    detail = f"关键词匹配 {matched}/{len(keywords)}"
                elif ratio >= 0.3:
                    status = "degraded"
                    detail = f"关键词匹配 {matched}/{len(keywords)}"
                else:
                    status = "lost"
                    detail = f"关键词匹配 {matched}/{len(keywords)}"

                findings.append(Finding(
                    category=cat, item=item, status=status, detail=detail,
                ))

        # 用 LLMChecker 的计算逻辑
        return LLMChecker()._compute_result(findings)

    def _extract_keywords(self, text: str) -> List[str]:
        """从信息项中提取关键词。"""
        # 移除标点和特殊字符
        cleaned = re.sub(r"[^\w\s]", " ", text)
        words = cleaned.split()

        # 过滤停用词和过短的词
        stop_words = {
            "的", "是", "在", "了", "和", "也", "都", "与", "或",
            "the", "a", "an", "is", "are", "was", "were",
            "to", "in", "on", "at", "by", "for", "of", "and", "or",
        }
        keywords = [
            w for w in words
            if len(w) >= 2 and w.lower() not in stop_words
        ]

        return keywords[:5]  # 最多 5 个关键词
