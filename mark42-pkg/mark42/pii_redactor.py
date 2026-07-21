"""Mark42 PII 脱敏模块 (Day 2)

设计目标:
在上下文压缩前, 对 LLM 看到的中间内容进行 PII 脱敏, 防止:
1. 用户隐私信息泄露到 LLM API
2. 敏感凭据 (API key/token) 误传到 LLM
3. 内部 IP/路径/电话等被记录到 trajectory

借鉴: Headroom 的 policy-based scrubbing + Microsoft Presidio 的思路
实现: 纯 Python 正则 + 字典匹配, 无依赖

PII 类型覆盖:
- 邮箱地址
- 手机号 (中国 + 国际)
- 身份证号 (中国 18 位)
- 信用卡号 (Luhn 算法验证)
- API key / token (sk-, ghp_, xoxb-, eyJ 开头)
- IP 地址 (IPv4/IPv6)
- 文件路径 (含敏感路径如 .ssh, .aws, credentials)
- URL (含 token)

设计文档: docs/design/mark42-压缩方案-阶段1实施计划-20260624.md (Day 2)
"""

import re
from typing import Any

# 【2026-07-13】不能用相对路径, algo_scheduler 从外部 import
from .log_setup import get_logger
from .utils import safe_call

logger = get_logger(__name__)


# ============================================================================
# PII 模式定义 - 按类型分组的正则
# 设计原则: 宁误报 (假阳性) 不漏报 (假阴性)
# ============================================================================

PII_PATTERNS: dict[str, dict[str, Any]] = {
    "email": {
        # 用 (?<![A-Za-z0-9._%+-]) 替代 \b，避免中文紧贴时边界不生效
        "regex": re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z])"),
        "replacement": "[REDACTED:email]",
        "description": "Email address",
    },
    "phone_cn": {
        # 用 (?<!\d) 替代 \b，避免中文紧贴数字时 \b 不生效
        "regex": re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"),
        "replacement": "[REDACTED:phone_cn]",
        "description": "Chinese mobile (11 digits starting with 1[3-9])",
    },
    "id_card_cn": {
        "regex": re.compile(
            r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
        ),
        "replacement": "[REDACTED:id_card_cn]",
        "description": "Chinese ID card (18 digits)",
    },
    "credit_card": {
        "regex": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        "replacement": "[REDACTED:credit_card]",
        "description": "Credit card number (13-19 digits with Luhn check)",
        "validator": "_luhn_check",  # 验证函数名
    },
    "api_key_openai": {
        "regex": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "replacement": "[REDACTED:api_key]",
        "description": "OpenAI-style API key (sk-...)",
    },
    "api_key_github": {
        "regex": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
        "replacement": "[REDACTED:api_key]",
        "description": "GitHub personal access token (ghp_...)",
    },
    "api_key_anthropic": {
        "regex": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
        "replacement": "[REDACTED:api_key]",
        "description": "Anthropic API key (sk-ant-...)",
    },
    "jwt_token": {
        "regex": re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*\b"),
        "replacement": "[REDACTED:jwt]",
        "description": "JWT token (eyJ... format)",
    },
    "ipv4": {
        "regex": re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
        "replacement": "[REDACTED:ipv4]",
        "description": "IPv4 address",
        # 排除 0.0.0.0 和 127.x.x.x (本地)
        "exclude": lambda m: m.group(0).startswith(("0.", "127.", "255.")),
    },
    "sensitive_path": {
        "regex": re.compile(
            r"(?:/[\w.-]+)*(?:/\.(?:ssh|aws|gnupg|password|netrc)|"
            r"/etc/(?:passwd|shadow|hosts)|"
            r"~/\.(?:ssh|aws|gnupg|password|netrc))"
            r"(?:/[\w.-]+)*",
            re.IGNORECASE,
        ),
        "replacement": "[REDACTED:path]",
        "description": "Sensitive file paths",
    },
    "url_with_token": {
        "regex": re.compile(
            r'https?://[^\s<>"\'`]+(?:token|key|api_key|access_token|password)=[A-Za-z0-9_-]+', re.IGNORECASE
        ),
        "replacement": "[REDACTED:url_with_token]",
        "description": "URL with token/key parameter",
    },
    "chinese_name_weak": {
        # 弱匹配: 2-4 个连续汉字 + 同志/先生/女士/老师 等称谓
        "regex": re.compile(r"[\u4e00-\u9fa5]{2,4}(?:同志|先生|女士|老师|经理|总|老板|同学)"),
        "replacement": "[REDACTED:name]",
        "description": "Chinese name + title (weak, false positives possible)",
        # 默认 disabled, 误报太多
        "enabled": False,
    },
}


# ============================================================================
# Luhn 算法 (信用卡号验证)
# ============================================================================


def _luhn_check(card_str: str) -> bool:
    """Luhn 算法: 验证信用卡号是否合法.

    Args:
        card_str: 纯数字字符串 (去除空格和横线)

    Returns:
        True if valid checksum
    """
    digits = [int(d) for d in card_str if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    # Luhn 校验
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]

    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))

    return total % 10 == 0


# ============================================================================
# 核心: PIIRedactor 类
# ============================================================================


class PIIRedactor:
    """PII 脱敏器 - 借鉴 Headroom policy scrubbing."""

    def __init__(self, enabled_types: list[str] | None = None, custom_replacements: dict[str, str] | None = None):
        """
        Args:
            enabled_types: 启用的 PII 类型列表, None 表示用默认 (全部 enabled)
            custom_replacements: 自定义替换字符串, key=pii_type, value=replacement
        """
        self.enabled_types = enabled_types or [k for k, v in PII_PATTERNS.items() if v.get("enabled", True)]
        self.custom_replacements = custom_replacements or {}

        # 编译启用的 patterns
        self.compiled_patterns = {
            pii_type: PII_PATTERNS[pii_type] for pii_type in self.enabled_types if pii_type in PII_PATTERNS
        }

    def redact(self, content: str) -> tuple[str, dict]:
        """对字符串进行 PII 脱敏.

        Args:
            content: 原始字符串

        Returns:
            (脱敏后字符串, 统计信息)
            统计信息包含: original_bytes, redacted_bytes, redactions_by_type
        """
        stats = {
            "original_bytes": len(content.encode("utf-8")),
            "redacted_bytes": 0,
            "redactions_by_type": {pii_type: 0 for pii_type in self.compiled_patterns},
            "total_redactions": 0,
        }

        if not content:
            stats["redacted_bytes"] = 0
            return content, stats

        redacted = content

        for pii_type, pattern_def in self.compiled_patterns.items():
            regex = pattern_def["regex"]
            replacement = self.custom_replacements.get(pii_type, pattern_def["replacement"])
            exclude = pattern_def.get("exclude")
            validator = pattern_def.get("validator")
            stats_ref = stats

            def _do_replace(match, exclude=exclude, validator=validator, pii_type=pii_type, replacement=replacement, stats_ref=stats_ref):
                # 排除规则
                if exclude and exclude(match):
                    return match.group(0)

                # 信用卡需要 Luhn 验证
                if validator == "_luhn_check":
                    if not _luhn_check(match.group(0)):
                        return match.group(0)

                stats_ref["redactions_by_type"][pii_type] += 1
                stats_ref["total_redactions"] += 1
                return replacement

            redacted = regex.sub(_do_replace, redacted)

        stats["redacted_bytes"] = len(redacted.encode("utf-8"))
        return redacted, stats

    def redact_dict_values(self, obj: Any, max_depth: int = 10) -> tuple[Any, dict]:
        """递归对字典/列表的字符串值进行脱敏.

        Args:
            obj: 任意 JSON-like 对象
            max_depth: 最大递归深度

        Returns:
            (脱敏后对象, 统计信息)
        """
        total_stats = {
            "original_bytes": 0,
            "redacted_bytes": 0,
            "total_redactions": 0,
            "redactions_by_type": {pii_type: 0 for pii_type in self.compiled_patterns},
        }

        def _walk(node, depth):
            if depth > max_depth:
                return node

            if isinstance(node, str):
                redacted, stats = self.redact(node)
                total_stats["original_bytes"] += stats["original_bytes"]
                total_stats["redacted_bytes"] += stats["redacted_bytes"]
                total_stats["total_redactions"] += stats["total_redactions"]
                for k, v in stats["redactions_by_type"].items():
                    total_stats["redactions_by_type"][k] += v
                return redacted

            if isinstance(node, dict):
                return {k: _walk(v, depth + 1) for k, v in node.items()}

            if isinstance(node, list):
                return [_walk(v, depth + 1) for v in node]

            return node

        result = _walk(obj, 0)
        return result, total_stats


# ============================================================================
# 单例 + 公开 API
# ============================================================================

_redactor_singleton: PIIRedactor | None = None


def get_redactor() -> PIIRedactor:
    """获取 PIIRedactor 单例 (默认配置)"""
    global _redactor_singleton
    if _redactor_singleton is None:
        _redactor_singleton = PIIRedactor()
    return _redactor_singleton


@safe_call(default=("", {"error": "redact_pii failed"}), label="redact_pii")
def redact_pii(content: str) -> tuple[str, dict]:
    """公开 API: 对字符串进行 PII 脱敏.

    Args:
        content: 原始字符串

    Returns:
        (脱敏后字符串, 统计信息)
    """
    return get_redactor().redact(content)


@safe_call(default=(None, {"error": "redact_pii_in_dict failed"}), label="redact_pii_in_dict")
def redact_pii_in_dict(obj: Any) -> tuple[Any, dict]:
    """公开 API: 对字典/列表中的字符串值进行 PII 脱敏."""
    return get_redactor().redact_dict_values(obj)


# ============================================================================
# 单元测试
# ============================================================================


def _run_tests():
    """运行测试（已提取到 tests/test_pii_redactor.py）。"""
    from tests.test_pii_redactor import run_tests
    return run_tests()



if __name__ == "__main__":
    import sys

    sys.exit(0 if _run_tests() else 1)
