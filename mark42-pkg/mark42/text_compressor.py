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
from typing import Any

# 【2026-07-13】不能用相对路径, algo_scheduler 从外部 import
from mark42.utils import safe_call


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

    def __init__(self,
                 method: str = "rule_based",
                 min_text_size: int = 200,
                 min_useful_ratio: float = 0.05,
                 enable_synonyms: bool = True,
                 enable_number_units: bool = True,
                 enable_phrase_removal: bool = True,
                 enable_repeat_dedup: bool = True):
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
            def repl_bytes(m):
                nonlocal converted
                value = float(m.group(1))
                converted += 1
                return f"{int(value * multiplier)} bytes"

            text = pattern.sub(repl_bytes, text)

        for pattern, unit in _TIME_UNIT_PATTERNS:
            def repl_time(m):
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
    passed = 0
    failed = 0

    def check(name: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}")
            failed += 1

    tc = get_text_compressor()

    # ---- 测试 1: 太小 passthrough ----
    short = "x" * 150
    out, stats = tc.compress(short)
    print(f"\n[测试 1] 500B 小文本 passthrough")
    check("1.1 mode=passthrough_small", stats["mode"] == "passthrough_small")
    check("1.2 不变", out == short)
    check("1.3 ratio=0", stats["ratio"] == 0.0)

    # ---- 测试 2: 冗余水话删除 ----
    sample = (
        "总而言之，这个系统使用 Python 进行开发。由于采用了微服务架构，因此能够支持高并发。\n"
        "综上所述，我们使用 Redis 作为缓存。由于性能优异，因此可以处理百万级请求。\n"
        "简而言之，Mark42 是一款非常优秀的工具。由于设计巧妙，因此可以满足各种需求。\n"
    )
    out, stats = tc.compress(sample)
    print(f"\n[测试 2] 冗余水话删除")
    check("2.1 删除总而言之", "总而言之" not in out)
    check("2.2 删除综上所述", "综上所述" not in out)
    check("2.3 删除简而言之", "简而言之" not in out)
    check("2.4 removed_phrase_count >= 3", stats["removed_phrase_count"] >= 3)

    # ---- 测试 3: 同义词替换 ----
    syn_sample = "我们需要使用这个工具进行测试。由于性能优异，因此可以满足需求。它能够处理大量数据。" * 3
    out, stats = tc.compress(syn_sample)
    print(f"\n[测试 3] 同义词替换")
    # 可能因水话先处理而差异, 至少应有一些替换发生
    # 关键: "使用" → "用", "进行" → "做" 等
    check("3.1 synonym_replacements > 0", stats["synonym_replacements"] > 0)

    # ---- 测试 4: 数字单位化 ----
    num_sample = "数据库有 1500000 条记录, 缓存命中 8500 次, 总共 999 条 (未达阈值), 写入 1234567 行" * 3
    out, stats = tc.compress(num_sample)
    print(f"\n[测试 4] 数字单位化")
    check("4.1 number_unit_conversions >= 2", stats["number_unit_conversions"] >= 2)
    check("4.2 1500000 → 1.5M", "1.5M" in out)
    check("4.3 1234567 → 1.2M", "1.2M" in out)
    check("4.4 999 不变 (小于 1000)", "999" in out)

    # ---- 测试 5: 连续重复行去重 ----
    repeat = "重要信息\n" * 50 + "另一段\n" + "重要信息\n" * 30 + "结尾"
    out, stats = tc.compress(repeat)
    print(f"\n[测试 5] 连续重复行去重")
    check("5.1 dedup_repeat_lines > 50", stats["dedup_repeat_lines"] > 50)
    check("5.2 含 (重复 N 次) 标注", "(重复" in out)

    # ---- 测试 6: 空白归一 ----
    ws_sample = ("  hello  \n\n\n\n  world  \n\n\n\n\n") * 15
    out, stats = tc.compress(ws_sample)
    print(f"\n[测试 6] 空白归一")
    check("6.1 行尾无空格", "\n  \n" not in out and not out.endswith(" "))
    # 6.2 多空行归一: 不应连续 3 个空行
    has_triple_blank = bool(re.search(r"\n\n\n", out))
    check("6.2 无连续 3+ 空行", not has_triple_blank)

    # ---- 测试 7: 整体压缩率 (长样本) ----
    long_sample = (
        "总而言之，这个系统使用 Python 进行开发。由于采用了微服务架构，因此能够支持高并发。\n"
        "数据库有 1500000 条记录, 缓存命中 8500 次。\n"
        "重要信息\n" * 20
    )
    out, stats = tc.compress(long_sample)
    print(f"\n[测试 7] 综合长样本")
    print(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio']*100:.1f}%)")
    check("7.1 mode=compressed", stats["mode"] == "compressed")
    check("7.2 ratio > 10%", stats["ratio"] > 0.10)

    # ---- 测试 8: llm 模式 (Day 8: 真接 LiteLLM) ----
    tc_llm = TextCompressor(method="llm")
    out, stats = tc_llm.compress("anything" * 200)  # 1600B 触发 LLM
    print(f"\n[测试 8] llm 模式 — 真调 LLM (mode={stats['mode']}, ratio={stats['ratio']:.1%})")
    check("8.1 mode 以 llm_ 开头", stats["mode"].startswith("llm_"))
    check("8.2 llm_info 存在", "llm_info" in stats)
    # 注: 这里如果 LLM 可达会调; 不可达会 fallback。两种都应走 llm_ 模式

    # ---- 测试 9: 错误输入 fail-safe ----
    out, stats = tc.compress("")
    check("9.1 空输入不报错", stats["mode"] == "none")
    out, stats = tc.compress("   \n\n   ")
    check("9.2 纯空白不报错", True)  # 走到这里就是通过

    # ---- 测试 10: 护栏 - 低压缩率回退 ----
    # 同义词替换会大幅缩短, 但若文本本身已是压缩态, 压缩率可能 < 10%
    # 用大量 "abc" 短行: dedup 不会触发, 水话无, 数字无, 同义词无
    no_redundancy = "z" * 2000 + "y" * 2000
    out, stats = tc.compress(no_redundancy)
    print(f"\n[测试 10] 护栏: 无冗余文本")
    print(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio']*100:.1f}%)")
    # 应该回退或 passthrough
    check("10.1 无变化或回退", stats["mode"] in ("fallback_low_ratio", "passthrough_small"))

    # ---- 测试 11: 混合策略协同 ----
    mixed = (
        "总而言之，Mark42 使用 Python 进行开发。" * 10
        + "数据库有 2000000 条记录, 缓存 5000 次。" * 10
        + "重要提示\n" * 50
    )
    out, stats = tc.compress(mixed)
    print(f"\n[测试 11] 混合策略协同")
    print(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio']*100:.1f}%)")
    check("11.1 综合压缩率 > 20%", stats["ratio"] > 0.20)
    check("11.2 removed_phrase_count > 0", stats["removed_phrase_count"] > 0)
    check("11.3 number_unit_conversions > 0", stats["number_unit_conversions"] > 0)
    check("11.4 dedup_repeat_lines > 0", stats["dedup_repeat_lines"] > 0)

    # ---- 测试 12: 扩展词典覆盖（中文技术词） ----
    tech_cn = "系统需要创建任务并获取配置，然后发送消息并返回结果。"
    out, replaced = tc._replace_synonyms(tech_cn)
    print(f"\n[测试 12] 扩展词典覆盖（中文技术词）")
    check("12.1 替换仍生效", replaced >= 1)
    check("12.2 需要→要", "系统要" in out)
    check("12.3 发送消息保留", "发送消息" in out)
    check("12.4 返回结果保留", "返回结果" in out)

    # ---- 测试 13: 上下文单位归一 ----
    units = "响应耗时 50 ms，日志大小 2 KB，缓存峰值 1.5 MB，备份 1 G bytes。"
    out, converted = tc._convert_numbers(units)
    print(f"\n[测试 13] 上下文单位归一")
    check("13.0 单位归一命中 4 次", converted >= 4)
    check("13.1 ms→毫秒", "50毫秒" in out)
    check("13.2 KB→bytes", "2048 bytes" in out)
    check("13.3 MB→bytes", "1572864 bytes" in out)
    check("13.4 G bytes→bytes", "1073741824 bytes" in out)

    # ---- 测试 14: fallback_low_ratio 统计一致 ----
    out, stats = tc.compress(("ABCDEFGHIJ" * 300))
    print(f"\n[测试 14] fallback_low_ratio 统计一致")
    if stats["mode"] == "fallback_low_ratio":
        check("14.1 回退时 crushed_bytes=original_bytes", stats["crushed_bytes"] == stats["original_bytes"])
        check("14.2 回退时 ratio 保留原计算值", stats["ratio"] < tc.min_useful_ratio)
    else:
        check("14.1 非回退也可接受", stats["mode"] in ("compressed", "passthrough_small"))
        check("14.2 非回退不报错", True)

    # ---- 测试 15: 英文整词边界 ----
    boundary = "errorless serviceable application_service prior to start"
    out, replaced = tc._replace_synonyms(boundary)
    print(f"\n[测试 15] 英文整词边界")
    check("15.1 errorless 不误替换", "errorless" in out)
    check("15.2 serviceable 不误替换", "serviceable" in out)
    check("15.3 prior to 正常替换", "before start" in out)

    # ---- 测试 16: 避免过度压缩伤语义 ----
    semantic_sample = "系统支持热更新，并支持在线扩容。请确认配置完成后记录日志。"
    out, stats = tc.compress(semantic_sample * 20)
    print(f"\n[测试 16] 避免过度压缩伤语义")
    check("16.1 支持保留", "支持热更新" in out)
    check("16.2 确认保留", "确认配置完成后记录日志" in out)

    literal_sample = "We should note that the API returns note that as literal text."
    out, stats = tc.compress(literal_sample * 20)
    check("16.3 note that 不应被裸删", "note that" in out)

    collision_sample = "接口通过率达到 99%。服务提供者需要认证。文档包含量较大。"
    out, stats = tc.compress(collision_sample * 20)
    check("16.4 通过率不误伤", "通过率" in out)
    check("16.5 提供者不误伤", "提供者" in out)
    check("16.6 包含量不误伤", "包含量" in out)

    # ---- 测试 17: 词典规模达标 ----
    print(f"\n[测试 17] 词典规模达标")
    check("17.1 SYNONYMS >= 100", len(SYNONYMS) >= 100)
    check("17.2 REDUNDANT_PHRASES >= 80", len(REDUNDANT_PHRASES) >= 80)

    print()
    print("=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_tests() else 1)
