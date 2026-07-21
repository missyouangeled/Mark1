"""从 diff_compressor.py 提取的单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.diff_compressor import *


def run_tests():
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

