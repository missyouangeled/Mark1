"""Mark42 diff 压缩器（方向 A 算法 4）

设计文档:
- 开发手册: docs/design/mark42-开发手册-压缩子系统.md (4.5 节)

策略:
1. 保留 hunk header (@@ -N,M +N,M @@) 和 file headers (diff --git / --- / +++)
2. 连续 context lines (以 ' ' 开头) 做游程编码: N>=2 时合并成 " <N>L"
3. 连续删除行 ('-') 和添加行 ('+') 单独计数, hunk 末尾输出 "+M / -N" 汇总
4. 单条 +/- 不动, 保留可读性

接口风格: 与 compression_algorithms.py 对齐
  class Xxx + get_xxx() 单例 + xxx(code) -> tuple[str, dict]

创建日期: 2026-06-25 07:18
"""

import re

from .log_setup import get_logger
from .utils import safe_call

logger = get_logger(__name__)


class DiffCompressor:
    """git diff 压缩器"""

    def __init__(
        self, merge_context_threshold: int = 2, preserve_hunk_headers: bool = True, preserve_file_headers: bool = True
    ):
        # 连续 context 行数 >= 此值才合并为 " <N>L"
        self.merge_context_threshold = merge_context_threshold
        self.preserve_hunk_headers = preserve_hunk_headers
        self.preserve_file_headers = preserve_file_headers

    def is_diff(self, content: str) -> bool:
        """启发式: 是否像 git diff 输出"""
        if not content:
            return False
        # 必须有 hunk header 才是真 diff
        return bool(re.search(r"^@@\s+-\d+", content, re.MULTILINE))

    def compress(self, content: str) -> tuple[str, dict]:
        """压缩 diff

        Args:
            content: git diff 输出字符串

        Returns:
            (压缩后 diff, 统计信息)
        """
        stats = {
            "algorithm": "diff_compress",
            "original_bytes": len(content.encode("utf-8")),
            "original_lines": 0,
            "is_diff": False,
            "crushed_bytes": 0,
            "ratio": 0.0,
            "hunks": 0,
            "context_lines_merged": 0,
            "insertions": 0,
            "deletions": 0,
            "mode": "none",
        }

        if not content or not content.strip():
            return content, stats

        stats["original_lines"] = content.count("\n") + (1 if not content.endswith("\n") else 0)

        if not self.is_diff(content):
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["mode"] = "passthrough"
            return content, stats
        stats["is_diff"] = True

        try:
            result = self._compress_diff(content, stats)
        except Exception as e:
            stats["mode"] = "error"
            stats["error"] = str(e)
            return content, stats

        stats["crushed_bytes"] = len(result.encode("utf-8"))
        stats["ratio"] = 1.0 - stats["crushed_bytes"] / max(1, stats["original_bytes"])
        stats["mode"] = "compressed"
        return result, stats

    @safe_call(default="", label="compress_diff")
    def _compress_diff(self, content: str, stats: dict) -> str:
        """主体压缩逻辑"""
        out_lines = []
        # 按 hunk 切分
        hunks = self._split_hunks(content, stats)

        for hunk in hunks:
            out_lines.extend(self._process_hunk(hunk, stats))

        return "\n".join(out_lines)

    def _split_hunks(self, content: str, stats: dict) -> list[str]:
        """把 diff 切成若干 hunk 块 (含 file header + @@ ... @@ + body)"""
        blocks = []
        current = []

        for line in content.splitlines():
            if line.startswith("@@"):
                # 新的 hunk 开始
                if current:
                    blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)

        # hunks 计数按 @@ 出现次数 (语义上的 hunk 数, 不算 file header 块)
        stats["hunks"] = sum(1 for ln in content.splitlines() if ln.startswith("@@"))
        return blocks

    def _process_hunk(self, hunk_lines: list[str], stats: dict) -> list[str]:
        """处理单个 hunk block"""
        out = []
        body = []
        hunk_header_added = False

        # 先扫一遍: 区分 file header / hunk header / body
        for line in hunk_lines:
            if line.startswith("@@"):
                if self.preserve_hunk_headers and not hunk_header_added:
                    out.append(line)
                    hunk_header_added = True
                # 如果有第二个 @@ (理论上 split_hunks 不会产生), 忽略
            elif (
                line.startswith("diff ")
                or line.startswith("--- ")
                or line.startswith("+++ ")
                or line.startswith("index ")
            ):
                if self.preserve_file_headers:
                    out.append(line)
            else:
                body.append(line)

        # body 压缩: 连续同类型合并
        out_body = []
        n = len(body)
        i = 0
        while i < n:
            line = body[i]
            tag = line[:1] if line else ""
            if tag in (" ", "+", "-"):
                j = i
                while j < n and body[j][:1] == tag:
                    j += 1
                count = j - i
                if tag == " ":
                    stat_key = "context_lines_merged"
                elif tag == "+":
                    stat_key = "insertions"
                else:
                    stat_key = "deletions"

                if count >= self.merge_context_threshold:
                    label = {" ": "context", "+": "insertions", "-": "deletions"}[tag]
                    out_body.append(f"{tag} ... <{count} {label}>")
                else:
                    # 短 run 保留原文, 但仍计入总数
                    out_body.extend(body[i:j])
                # 不论长短, 都累加到统计 (含短 run)
                stats[stat_key] += count
                i = j
            elif tag == "\\":
                # "\ No newline at end of file" 保留
                out_body.append(line)
                i += 1
            else:
                # 空行 / 其他
                out_body.append(line)
                i += 1

        out.extend(out_body)
        return out


# 单例 + 函数式接口 (与 compression_algorithms.py 对齐)
_instance: DiffCompressor | None = None


def get_diff_compressor() -> DiffCompressor:
    global _instance
    if _instance is None:
        _instance = DiffCompressor()
    return _instance


@safe_call(default=None, label="diff_compress")
def diff_compress(content: str) -> tuple[str, dict]:
    return get_diff_compressor().compress(content)


# 自检 / 烟测
def _run_tests() -> bool:
    passed = 0
    failed = 0

    def check(name: str, cond: bool):
        nonlocal passed, failed
        if cond:
            logger.info(f"  ✓ {name}")
            passed += 1
        else:
            logger.error(f"  ✗ {name}")
            failed += 1

    dc = get_diff_compressor()

    # ---- 测试 1: 简单 hunk + context 游程 ----
    diff1 = """@@ -1,5 +1,5 @@
 line1
 line2
 line3
 line4
 line5
-removed
+added
"""
    out, stats = dc.compress(diff1)
    logger.info("\n[测试 1] 简单 hunk 5 行 context 游程")
    logger.info(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio'] * 100:.1f}%)")
    logger.info(f"  输出:\n{out}")
    check("1.1 保留 @@", "@@" in out)
    check("1.2 5 行 context 合并", "5 context" in out)
    check("1.3 context_lines_merged=5", stats["context_lines_merged"] == 5)
    check("1.4 insertions=1", stats["insertions"] == 1)
    check("1.5 deletions=1", stats["deletions"] == 1)
    check("1.6 保留 added", "+added" in out)
    check("1.7 保留 removed", "-removed" in out)

    # ---- 测试 2: 连续 insertions 合并 ----
    diff2 = "@@ -1,3 +1,5 @@\n old1\n+new1\n+new2\n+new3\n+new4\n+new5\n old2\n"
    out, stats = dc.compress(diff2)
    logger.info("\n[测试 2] 连续 5 行 + 合并")
    check("2.1 合并为 insertions 标记", "5 insertions" in out)
    check("2.2 insertions=5", stats["insertions"] == 5)

    # ---- 测试 3: 连续 deletions ----
    diff3 = "@@ -1,7 +1,2 @@\n-old1\n-old2\n-old3\n-old4\n-old5\n keep1\n keep2\n"
    out, stats = dc.compress(diff3)
    logger.info("\n[测试 3] 连续 5 行 - 合并")
    check("3.1 合并为 deletions 标记", "5 deletions" in out)
    check("3.2 deletions=5", stats["deletions"] == 5)

    # ---- 测试 4: file header 保留 ----
    diff4 = """diff --git a/foo.py b/foo.py
index 1234..5678 100644
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
-old
+new
 unchanged
"""
    out, stats = dc.compress(diff4)
    logger.info("\n[测试 4] 完整 file headers")
    check("4.1 保留 diff --git", "diff --git" in out)
    check("4.2 保留 --- a/foo.py", "--- a/foo.py" in out)
    check("4.3 保留 +++ b/foo.py", "+++ b/foo.py" in out)
    check("4.4 hunks=1", stats["hunks"] == 1)

    # ---- 测试 5: 短 context 不合并 (阈值=2) ----
    diff5 = "@@ -1,2 +1,2 @@\n a\n b\n"
    out, stats = dc.compress(diff5)
    logger.info("\n[测试 5] 2 行 context (刚好阈值, 应合并)")
    check("5.1 2 行 threshold 合并", "2 context" in out)

    diff5b = "@@ -1,1 +1,1 @@\n a\n"
    out, stats = dc.compress(diff5b)
    logger.info("\n[测试 5b] 1 行 context (低于阈值, 不合并)")
    check("5b.1 1 行保留", " a" in out)
    check("5b.2 不出现 context 合并", "context>" not in out)

    # ---- 测试 6: 非 diff passthrough ----
    out, stats = dc.compress("just some text\nnothing here\n")
    logger.info("\n[测试 6] 非 diff passthrough")
    check("6.1 is_diff=False", stats["is_diff"] is False)
    check("6.2 mode=passthrough", stats["mode"] == "passthrough")

    # ---- 测试 7: 空内容 ----
    out, stats = dc.compress("")
    check("7.1 空 ratio=0", stats["ratio"] == 0.0)

    # ---- 测试 8: 多个 hunks ----
    diff8 = """@@ -1,3 +1,3 @@
 a
-old1
+new1
 b
@@ -10,3 +10,3 @@
 c
-old2
+new2
 d
"""
    out, stats = dc.compress(diff8)
    logger.info("\n[测试 8] 多个 hunks")
    check("8.1 hunks=2", stats["hunks"] == 2)
    check("8.2 两个 hunk header 都在 (4 个 @@)", out.count("@@") == 4)
    check("8.3 第一个 old1 保留", "-old1" in out)
    check("8.4 第二个 old2 保留", "-old2" in out)

    # ---- 测试 9: "\ No newline at end of file" 保留 ----
    diff9 = "@@ -1,2 +1,2 @@\n-old\n+new\n\\ No newline at end of file\n"
    out, stats = dc.compress(diff9)
    logger.info("\n[测试 9] No newline marker 保留")
    check("9.1 保留 \\ No newline", "\\ No newline" in out)

    # ---- 测试 10: 混合 (context + + - 交替) ----
    diff10 = "@@ -1,10 +1,10 @@\n a\n b\n-old1\n+new1\n c\n d\n-old2\n+new2\n e\n f\n"
    out, stats = dc.compress(diff10)
    logger.info("\n[测试 10] 交替模式")
    check("10.1 insertions=2 (各 1 行)", stats["insertions"] == 2)
    check("10.2 deletions=2 (各 1 行)", stats["deletions"] == 2)
    check("10.3 short runs 保留原文", "+new1" in out and "-old1" in out)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"结果: {passed} 通过 / {failed} 失败")
    logger.info("=" * 60)
    return failed == 0


if __name__ == "__main__":
    import sys

    sys.exit(0 if _run_tests() else 1)
