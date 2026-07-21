"""Mark42 通用文本压缩器（方向 A 算法 5）

设计文档:
- 开发手册: docs/design/mark42-开发手册-压缩子系统.md (4.6 节)

策略 (rule_based, 默认):
1. 行尾空白 / 多空行归一
2. 重复连续行去重
3. 冗余水话删除 ("总之" / "综上所述" / "简而言之" 等)
4. 数字单位化 (1234567 → 1.2M, 1024 → 1.0K)
5. 同义词替换 (小型词典)

可选 mode="llm": 占位接口, 调 LiteLLM 语义压缩 (实际调用留给上层)

接口风格: 与其他算法一致
  class TextCompressor + get_text_compressor() 单例 + text_compress(content) -> tuple[str, dict]

创建日期: 2026-06-25 07:25
"""

import re

# 【2026-07-13】不能用相对路径, algo_scheduler 从外部 import
from .log_setup import get_logger
from .utils import safe_call

logger = get_logger(__name__)


# 冗余水话清单 (中文 + 英文)
REDUNDANT_PHRASES = [
    # 中文
    "总而言之，",
    "总而言之 ",
    "综上所述，",
    "综上所述 ",
    "简而言之，",
    "简而言之 ",
    "简单来说，",
    "简单来说 ",
    "换句话说，",
    "换句话说 ",
    "也就是说，",
    "也就是说 ",
    "事实上，",
    "事实上 ",
    "一般来说，",
    "一般来说 ",
    "值得一提的是，",
    "值得一提的是 ",
    "不难发现，",
    "不难发现 ",
    "显而易见，",
    "显而易见 ",
    "不言而喻，",
    "不言而喻 ",
    "如上所述，",
    "如上所述 ",
    "下面让我们",
    "接下来让我们",
    "让我来",
    # 英文
    "in conclusion, ",
    "in summary, ",
    "to summarize, ",
    "as mentioned above, ",
    "as stated above, ",
    "in other words, ",
    "that is to say, ",
    "basically, ",
    "essentially, ",
    "please note, ",
    "it is worth noting that ",
    "it should be noted that ",
    "it is important to note that ",
    "needless to say, ",
    "as you can see, ",
    "first and foremost, ",
    "to sum up, ",
    "all in all, ",
    "that being said, ",
    "having said that, ",
    "with that in mind, ",
    "going forward, ",
    "moving forward, ",
    "at the end of the day, ",
    "the fact of the matter is ",
    "for all intents and purposes, ",
    "as a matter of fact, ",
    "for the most part, ",
    "in most cases, ",
    "more often than not, ",
    "without a doubt, ",
    "it turns out that ",
    "in many cases, ",
    "from this perspective, ",
    "from this point of view, ",
    "as far as we know, ",
    "as we all know, ",
    "as stated earlier, ",
    "as discussed above, ",
    "generally speaking, ",
    "strictly speaking, ",
    "on the other hand, ",
    "on the one hand, ",
    "from another perspective, ",
    "值得注意的是，",
    "值得注意的是 ",
    "需要注意的是，",
    "需要注意的是 ",
    "需要说明的是，",
    "需要说明的是 ",
    "需要指出的是，",
    "需要指出的是 ",
    "由此可见，",
    "由此可见 ",
    "总的来说，",
    "总的来说 ",
    "总的来讲，",
    "总的来讲 ",
    "众所周知，",
    "众所周知 ",
    "正如我们所知，",
    "正如我们所知 ",
    "不妨这样看，",
    "不妨这样看 ",
]

# 同义词替换词典 (保守版, 不会改变语义)
SYNONYMS = {
    "使用": "用",
    "进行": "做",
    "能够": "可",
    "因此": "所以",
    "然而": "但",
    "由于": "因为",
    "并且": "且",
    "或者": "或",
    "如果": "若",
    "为了": "为",
    "具有": "有",
    "需要": "要",
    "应该": "应",
    "可能会": "或会",
    "实际上": "其实",
    "一般情况下": "通常",
    "非常重要": "很重要",
    "一般情况下来说": "通常来说",
    "utilize": "use",
    "leverage": "use",
    "in order to": "to",
    "due to the fact that": "because",
    "at this point in time": "now",
    "a large number of": "many",
    "in the event that": "if",
    "with regard to": "about",
    "in spite of": "despite",
    "with respect to": "about",
    "a number of": "many",
    "a variety of": "many",
    "one of the": "a",
    "whether or not": "whether",
    "on a daily basis": "daily",
    "on a weekly basis": "weekly",
    "on a monthly basis": "monthly",
    "at an earlier point in time": "earlier",
    "at a later point in time": "later",
    "for the purpose of": "for",
    "in the process of": "during",
    "in the near future": "soon",
    "in the long term": "long-term",
    "in the short term": "short-term",
    "has the ability to": "can",
    "have the ability to": "can",
    "is able to": "can",
    "are able to": "can",
    "it is possible to": "can",
    "is required to": "must",
    "are required to": "must",
    "for this reason": "thus",
    "under the condition that": "if",
    "in many situations": "often",
    "make use of": "use",
    "make sure": "ensure",
    "priority": "prio",
    "approximately": "about",
    "subsequently": "then",
    "prior to": "before",
    "in regards to": "about",
    "commence": "start",
    "terminate": "end",
    "endeavor": "try",
    "facilitate": "help",
    "remainder": "rest",
    "subsequent": "next",
    "preceding": "previous",
    "configuration": "config",
    "information": "info",
    "documentation": "docs",
    "application": "app",
    "development": "dev",
    "implementation": "impl",
    "optimization": "opt",
    "environment": "env",
    "parameter": "param",
    "response": "resp",
    "request": "req",
    "successful": "ok",
    "failed": "fail",
    "error": "err",
    "temporary": "temp",
    "manager": "mgr",
    "service": "svc",
    "controller": "ctrl",
    "database": "db",
    "resource": "res",
    "execution": "exec",
    "analysis": "anal",
    "situation": "case",
    "additional": "extra",
    "required": "need",
    "optional": "opt",
    "generate": "gen",
    "initialize": "init",
    "maximum": "max",
    "minimum": "min",
    "message": "msg",
    "function": "func",
    "variable": "var",
    "repository": "repo",
    "directory": "dir",
    "command": "cmd",
    "operation": "op",
    "validate": "check",
    "verification": "check",
    "compress": "zip",
    "decompress": "unzip",
    "一般而言": "通常",
    "通常情况下": "通常",
    "在这种情况下": "此时",
    "在这个过程中": "过程中",
    "在大多数情况下": "通常",
    "在很多情况下": "常见",
    "换个角度看": "另看",
    "从结果来看": "结果看",
    "从实践来看": "实践看",
    "从经验来看": "经验看",
    "对于这个问题": "对此",
    "针对这个问题": "对此",
    "基于这个原因": "因此",
    "基于这一点": "据此",
    "在此基础上": "据此",
    "进一步来说": "进一步讲",
    "进一步地说": "进一步讲",
    "从整体上看": "整体看",
    "从局部上看": "局部看",
    "与之对应": "对应",
    "与此同时": "同时",
    "在一定程度上": "一定程度上",
    "相对来说": "相对看",
    "本质上来说": "本质上",
    "从某种意义上说": "某种意义上",
    "在默认情况下": "默认下",
}

# 数字单位化 (按千进制, 简单粗暴版)
_UNIT_PATTERN = re.compile(r"(\d{4,17})")
_BYTE_UNIT_PATTERNS = [
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*K\s*(?:bytes?|B)\b", re.IGNORECASE), 1024),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*M\s*(?:bytes?|B)\b", re.IGNORECASE), 1024 * 1024),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*G\s*(?:bytes?|B)\b", re.IGNORECASE), 1024 * 1024 * 1024),
]
_TIME_UNIT_PATTERNS = [
    (re.compile(r"\b(\d+)\s*ms\b", re.IGNORECASE), "毫秒"),
    (re.compile(r"\b(\d+)\s*s\b(?!\w)", re.IGNORECASE), "秒"),
]


class TextCompressor:
    """通用文本压缩器 (轻量版, 规则驱动)"""

    def __init__(
        self,
        method: str = "rule_based",
        min_text_size: int = 200,
        min_useful_ratio: float = 0.05,
        enable_synonyms: bool = True,
        enable_number_units: bool = True,
        enable_phrase_removal: bool = True,
        enable_repeat_dedup: bool = True,
    ):
        # 注: min_text_size 默认为 200 字节 以便小样本测试能跳到压缩逻辑
        # 调度器路由文本的阈值是 4KB, 这里只是算法本身的护栏

        """
        Args:
            method: "rule_based" (默认) 或 "llm" (占位, 不真调)
            min_text_size: 低于此字节数直接 passthrough
            min_useful_ratio: 压缩率 < 此值视为无效, 回退原文
            enable_synonyms: 是否启用同义词替换
            enable_number_units: 是否启用数字单位化
            enable_phrase_removal: 是否启用冗余水话删除
            enable_repeat_dedup: 是否启用连续重复行去重
        """
        self.method = method
        self.min_text_size = min_text_size
        self.min_useful_ratio = min_useful_ratio
        self.enable_synonyms = enable_synonyms
        self.enable_number_units = enable_number_units
        self.enable_phrase_removal = enable_phrase_removal
        self.enable_repeat_dedup = enable_repeat_dedup

    def compress(self, text: str) -> tuple[str, dict]:
        """压缩通用文本"""
        stats = {
            "algorithm": "text_compress",
            "original_bytes": 0,
            "original_lines": 0,
            "crushed_bytes": 0,
            "crushed_lines": 0,
            "ratio": 0.0,
            "mode": "none",
            "method": self.method,
            "removed_phrase_count": 0,
            "dedup_repeat_lines": 0,
            "synonym_replacements": 0,
            "number_unit_conversions": 0,
        }

        if not text or not text.strip():
            return text, stats

        stats["original_bytes"] = len(text.encode("utf-8"))
        stats["original_lines"] = text.count("\n") + (1 if not text.endswith("\n") else 0)

        # 太小直接 passthrough
        if stats["original_bytes"] < self.min_text_size:
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["crushed_lines"] = stats["original_lines"]
            stats["mode"] = "passthrough_small"
            return text, stats

        # llm 模式: 真接 LiteLLM (Day 8)
        if self.method == "llm":
            try:
                from llm_text_compressor import llm_text_compress
            except ImportError:
                try:
                    from .llm_text_compressor import llm_text_compress
                except ImportError:
                    stats["mode"] = "llm_module_unavailable"
                    stats["crushed_bytes"] = stats["original_bytes"]
                    stats["crushed_lines"] = stats["original_lines"]
                    return text, stats
            result, llm_stats = llm_text_compress(text)
            # 映射 LLM stats 到 rule_based stats 字段名
            stats["mode"] = "llm_" + llm_stats.get("status", "unknown")
            stats["crushed_bytes"] = llm_stats.get("crushed_bytes", len(result.encode("utf-8")))
            stats["crushed_lines"] = llm_stats.get("crushed_lines", 0)
            stats["ratio"] = llm_stats.get("ratio", 0.0)
            stats["llm_info"] = {
                "model": llm_stats.get("llm_model"),
                "tokens_in": llm_stats.get("llm_tokens_in", 0),
                "tokens_out": llm_stats.get("llm_tokens_out", 0),
                "duration_ms": llm_stats.get("llm_duration_ms", 0),
            }
            # 合并结构以供回退场景
            return result, stats

        # rule_based
        try:
            result = self._rule_compress(text, stats)
        except Exception as e:
            stats["mode"] = "error"
            stats["error"] = str(e)
            return text, stats

        # 护栏: 压缩率太低 → 回退原文
        crushed = len(result.encode("utf-8"))
        if stats["original_bytes"] > 0:
            ratio = 1.0 - crushed / stats["original_bytes"]
        else:
            ratio = 0.0
        if ratio < self.min_useful_ratio:
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["crushed_lines"] = stats["original_lines"]
            stats["mode"] = "fallback_low_ratio"
            stats["ratio"] = ratio
            return text, stats

        stats["crushed_bytes"] = crushed
        stats["crushed_lines"] = result.count("\n") + (1 if not result.endswith("\n") else 0)
        stats["ratio"] = ratio
        stats["mode"] = "compressed"
        return result, stats

    def _rule_compress(self, text: str, stats: dict) -> str:
        """规则压缩主体"""
        # 1. 连续重复行去重
        if self.enable_repeat_dedup:
            text, deduped = self._dedup_repeat_lines(text)
            stats["dedup_repeat_lines"] = deduped

        # 2. 冗余水话删除
        if self.enable_phrase_removal:
            text, removed = self._remove_redundant_phrases(text)
            stats["removed_phrase_count"] = removed

        # 3. 行尾空白 + 多空行归一
        text = self._normalize_whitespace(text)

        # 4. 数字单位化
        if self.enable_number_units:
            text, converted = self._convert_numbers(text)
            stats["number_unit_conversions"] = converted

        # 5. 同义词替换 (放最后, 避免误伤水话和数字)
        if self.enable_synonyms:
            text, replaced = self._replace_synonyms(text)
            stats["synonym_replacements"] = replaced

        return text

    def _dedup_repeat_lines(self, text: str) -> tuple[str, int]:
        """连续重复行去重: AAA -> A (连续 ≥3 次算重复, 跳过空行)"""
        lines = text.split("\n")
        out = []
        deduped = 0
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            # 跳过空行 (交给 _normalize_whitespace 处理)
            if not line.strip():
                out.append(line)
                i += 1
                continue
            j = i
            while j < n and lines[j] == line:
                j += 1
            count = j - i
            if count >= 3:
                out.append(f"{line}  (重复 {count} 次)")
                deduped += count - 1
            else:
                out.extend(lines[i:j])
            i = j
        return "\n".join(out), deduped

    def _remove_redundant_phrases(self, text: str) -> tuple[str, int]:
        """删除冗余水话短语"""
        removed = 0
        for phrase in REDUNDANT_PHRASES:
            count = text.count(phrase)
            if count > 0:
                text = text.replace(phrase, "")
                removed += count
        return text, removed

    def _normalize_whitespace(self, text: str) -> str:
        """行尾空白去除 + 连续空行归一"""
        lines = text.split("\n")
        lines = [ln.rstrip() for ln in lines]
        # 多空行 → 单空行
        out = []
        prev_empty = False
        for ln in lines:
            is_empty = not ln.strip()
            if is_empty and prev_empty:
                continue
            out.append(ln)
            prev_empty = is_empty
        return "\n".join(out)

    def _convert_numbers(self, text: str) -> tuple[str, int]:
        """数字单位化: 纯数字缩写 + 上下文单位归一"""
        converted = 0

        def repl(m):
            nonlocal converted
            n = int(m.group(1))
            if n < 1000:
                return m.group(0)  # 不动小数字
            if n < 1_000_000:
                v = n / 1000
                converted += 1
                return f"{v:.1f}K"
            if n < 1_000_000_000:
                v = n / 1_000_000
                converted += 1
                return f"{v:.1f}M"
            v = n / 1_000_000_000
            converted += 1
            return f"{v:.1f}B"

        text = _UNIT_PATTERN.sub(repl, text)

        for pattern, multiplier in _BYTE_UNIT_PATTERNS:

            def repl_bytes(m, multiplier=multiplier):
                nonlocal converted
                value = float(m.group(1))
                converted += 1
                return f"{int(value * multiplier)} bytes"

            text = pattern.sub(repl_bytes, text)

        for pattern, unit in _TIME_UNIT_PATTERNS:

            def repl_time(m, unit=unit):
                nonlocal converted
                converted += 1
                return f"{int(m.group(1))}{unit}"

            text = pattern.sub(repl_time, text)

        return text, converted

    def _replace_synonyms(self, text: str) -> tuple[str, int]:
        """同义词替换 (按 token 边界)"""
        replaced = 0
        for src, dst in SYNONYMS.items():
            if src.isascii():
                pattern = rf"(?<![A-Za-z0-9_]){re.escape(src)}(?![A-Za-z0-9_])"
            else:
                pattern = re.escape(src)
            new_text, n = re.subn(pattern, dst, text)
            if n > 0:
                text = new_text
                replaced += n
        return text, replaced


# 单例 + 函数式接口
_instance: TextCompressor | None = None


def get_text_compressor() -> TextCompressor:
    global _instance
    if _instance is None:
        _instance = TextCompressor()
    return _instance


@safe_call(default=("", {"error": "text_compress failed"}), label="text_compress")
def text_compress(content: str) -> tuple[str, dict]:
    return get_text_compressor().compress(content)


# 自检 / 烟测
def _run_tests() -> bool:
    """运行测试（已提取到 tests/test_text_compressor.py）。"""
    from tests.test_text_compressor import run_tests
    return run_tests()



if __name__ == "__main__":
    import sys

    sys.exit(0 if _run_tests() else 1)
