"""
Mark42 v3 · 核心 5 · 代码理解引擎

按 v3 §3.6 钉死的核心 5 实现：
- 代码语义分析 / 找 bug / 代码审查
- 通过 GLM-5.2 API 实现（本机无 GPU，走云端 API）
- 可插拔（R1）：改 model.yaml 可换其他模型

分析能力：
  - bug 检测：发代码片段，让 LLM 找潜在 bug
  - 代码审查：分析代码质量、风格、安全
  - 语义理解：解释代码做什么、依赖关系
"""

from __future__ import annotations

from .log_setup import get_logger
logger = get_logger(__name__)

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# 复用 v3-1 的 LLM Provider
from .llm_provider import ChatMessage, LLMProvider, build_consciousness, load_config


# ── 常量 ─────────────────────────────────────────────

CODE_ANALYSIS_SYSTEM_PROMPT = """\
你是 Mark42 战甲的代码分析引擎。用户会给你代码片段，你需要分析并返回 JSON。

返回格式：
{
  "bugs": [{"line": 行号, "severity": "critical|warning|info", "desc": "问题描述"}],
  "quality_score": 0-10,
  "summary": "一句话总结这段代码做什么",
  "suggestions": ["改进建议1", "改进建议2"]
}

规则：
- bugs: 找到的潜在 bug（空数组如果没有）
- quality_score: 代码质量评分（0=极差, 10=完美）
- summary: 简洁描述代码功能
- suggestions: 改进建议（可以空）
- 只返回 JSON，不要加其他文字
"""


# ── 数据类 ───────────────────────────────────────────

@dataclass
class CodeBug:
    """单个 bug。"""
    line: int = 0
    severity: str = "info"     # critical | warning | info
    desc: str = ""


@dataclass
class AnalysisResult:
    """代码分析结果。"""
    bugs: List[CodeBug] = field(default_factory=list)
    quality_score: int = 0
    summary: str = ""
    suggestions: List[str] = field(default_factory=list)
    elapsed_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bugs": [asdict(b) for b in self.bugs],
            "quality_score": self.quality_score,
            "summary": self.summary,
            "suggestions": self.suggestions,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }

    @property
    def has_critical_bug(self) -> bool:
        return any(b.severity == "critical" for b in self.bugs)


# ── 代码分析器 ───────────────────────────────────────

class CodeAnalyzer:
    """核心 5 · 代码理解引擎。

    通过 LLM API 分析代码片段。
    支持多种分析模式：bug 检测 / 代码审查 / 语义理解。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化。

        Args:
            config: 配置字典。None -> 从 model.yaml 读。
                    默认用 consciousness 的 LLM provider（跟核心 2 共享）。
        """
        self.config = config or load_config()
        self.llm: Optional[LLMProvider] = build_consciousness(self.config)

    def analyze(self, code: str, language: str = "python") -> AnalysisResult:
        """分析代码片段。

        Args:
            code: 代码文本
            language: 编程语言（python / javascript / go / ...）

        Returns:
            AnalysisResult
        """
        if not self.llm:
            return AnalysisResult(error="LLM provider 不可用")

        if not code.strip():
            return AnalysisResult(error="代码为空")

        messages = [
            ChatMessage(role="system", content=CODE_ANALYSIS_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"语言: {language}\n\n```\n{code}\n```\n\n请分析这段代码。"
            ),
        ]

        t0 = time.monotonic()
        try:
            resp = self.llm.chat(messages, response_format={"type": "json_object"})
        except Exception as e:
            return AnalysisResult(error=f"LLM 调用失败: {e}",
                                  elapsed_ms=int((time.monotonic() - t0) * 1000))

        elapsed = int((time.monotonic() - t0) * 1000)

        # 解析响应（复用 advisor_client 的解析逻辑）
        content = ""
        if hasattr(resp, 'content'):
            content = resp.content or ""
        elif isinstance(resp, dict):
            choices = resp.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")

        if not content:
            return AnalysisResult(error="LLM 返回空", elapsed_ms=elapsed)

        # 剥离 markdown 包裹
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if len(lines) > 1:
                content = "\n".join(lines[1:])
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            return AnalysisResult(error=f"JSON 解析失败: {e}", elapsed_ms=elapsed)

        bugs = [CodeBug(line=b.get("line", 0),
                         severity=b.get("severity", "info"),
                         desc=b.get("desc", ""))
                for b in parsed.get("bugs", [])]

        return AnalysisResult(
            bugs=bugs,
            quality_score=int(parsed.get("quality_score", 0)),
            summary=parsed.get("summary", ""),
            suggestions=parsed.get("suggestions", []),
            elapsed_ms=elapsed,
        )

    def analyze_file(self, file_path: str, language: str = "") -> AnalysisResult:
        """分析文件。"""
        p = Path(file_path)
        if not p.exists():
            return AnalysisResult(error=f"文件不存在: {file_path}")

        code = p.read_text(encoding="utf-8", errors="replace")
        if not language:
            # 根据扩展名推断语言
            ext_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                       ".go": "go", ".rs": "rust", ".java": "java", ".c": "c", ".cpp": "cpp"}
            language = ext_map.get(p.suffix, "text")

        return self.analyze(code, language)

    def health_check(self) -> bool:
        """健康检查：分析一段简单代码。"""
        try:
            r = self.analyze("x = 1 + 1\nprint(x)", "python")
            return r.error is None
        except Exception as e:
            return False


# ── CLI 接口 ────────────────────────────────────────

def cli_analyze_code(code: str, language: str = "python") -> Dict[str, Any]:
    """CLI: 分析代码片段。"""
    analyzer = CodeAnalyzer()
    result = analyzer.analyze(code, language)
    return result.to_dict()

def cli_analyze_file(file_path: str, language: str = "") -> Dict[str, Any]:
    """CLI: 分析文件。"""
    analyzer = CodeAnalyzer()
    result = analyzer.analyze_file(file_path, language)
    return result.to_dict()
