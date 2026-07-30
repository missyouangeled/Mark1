"""diff_compressor.py 单元测试（pytest 形式）。

原为脚本式 run_tests()，转换为 pytest 可收集的 test_* 函数以纳入覆盖率统计。
"""

from mark42.diff_compressor import get_diff_compressor


def _dc():
    return get_diff_compressor()


# ── 测试 1: 简单 hunk + context 游程 ──

DIFF1 = """@@ -1,5 +1,5 @@
 line1
 line2
 line3
 line4
 line5
-removed
+added
"""


def test_1_1_保留_atat():
    out, _ = _dc().compress(DIFF1)
    assert "@@" in out


def test_1_2_5行context合并():
    out, _ = _dc().compress(DIFF1)
    assert "5 context" in out


def test_1_3_context_lines_merged_5():
    _, stats = _dc().compress(DIFF1)
    assert stats["context_lines_merged"] == 5


def test_1_4_insertions_1():
    _, stats = _dc().compress(DIFF1)
    assert stats["insertions"] == 1


def test_1_5_deletions_1():
    _, stats = _dc().compress(DIFF1)
    assert stats["deletions"] == 1


def test_1_6_保留added():
    out, _ = _dc().compress(DIFF1)
    assert "+added" in out


def test_1_7_保留removed():
    out, _ = _dc().compress(DIFF1)
    assert "-removed" in out


# ── 测试 2: 连续 insertions 合并 ──

DIFF2 = "@@ -1,3 +1,5 @@\n old1\n+new1\n+new2\n+new3\n+new4\n+new5\n old2\n"


def test_2_1_合并为insertions标记():
    out, _ = _dc().compress(DIFF2)
    assert "5 insertions" in out


def test_2_2_insertions_5():
    _, stats = _dc().compress(DIFF2)
    assert stats["insertions"] == 5


# ── 测试 3: 连续 deletions ──

DIFF3 = "@@ -1,7 +1,2 @@\n-old1\n-old2\n-old3\n-old4\n-old5\n keep1\n keep2\n"


def test_3_1_合并为deletions标记():
    out, _ = _dc().compress(DIFF3)
    assert "5 deletions" in out


def test_3_2_deletions_5():
    _, stats = _dc().compress(DIFF3)
    assert stats["deletions"] == 5


# ── 测试 4: file header 保留 ──

DIFF4 = """diff --git a/foo.py b/foo.py
index 1234..5678 100644
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
-old
+new
 unchanged
"""


def test_4_1_保留diff_git():
    out, _ = _dc().compress(DIFF4)
    assert "diff --git" in out


def test_4_2_保留_a_foo_py():
    out, _ = _dc().compress(DIFF4)
    assert "--- a/foo.py" in out


def test_4_3_保留_b_foo_py():
    out, _ = _dc().compress(DIFF4)
    assert "+++ b/foo.py" in out


def test_4_4_hunks_1():
    _, stats = _dc().compress(DIFF4)
    assert stats["hunks"] == 1


# ── 测试 5: 短 context 阈值 ──

DIFF5 = "@@ -1,2 +1,2 @@\n a\n b\n"


def test_5_1_2行刚好阈值合并():
    out, _ = _dc().compress(DIFF5)
    assert "2 context" in out


DIFF5B = "@@ -1,1 +1,1 @@\n a\n"


def test_5b_1_1行保留():
    out, _ = _dc().compress(DIFF5B)
    assert " a" in out


def test_5b_2_低于阈值不合并():
    out, _ = _dc().compress(DIFF5B)
    assert "context>" not in out


# ── 测试 6: 非 diff passthrough ──

def test_6_1_is_diff_False():
    _, stats = _dc().compress("just some text\nnothing here\n")
    assert stats["is_diff"] is False


def test_6_2_mode_passthrough():
    _, stats = _dc().compress("just some text\nnothing here\n")
    assert stats["mode"] == "passthrough"


# ── 测试 7: 空内容 ──

def test_7_1_空_ratio_0():
    _, stats = _dc().compress("")
    assert stats["ratio"] == 0.0


# ── 测试 8: 多个 hunks ──

DIFF8 = """@@ -1,3 +1,3 @@
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


def test_8_1_hunks_2():
    _, stats = _dc().compress(DIFF8)
    assert stats["hunks"] == 2


def test_8_2_两个hunk_header都在():
    out, _ = _dc().compress(DIFF8)
    assert out.count("@@") == 4


def test_8_3_第一个old1保留():
    out, _ = _dc().compress(DIFF8)
    assert "-old1" in out


def test_8_4_第二个old2保留():
    out, _ = _dc().compress(DIFF8)
    assert "-old2" in out


# ── 测试 9: No newline marker 保留 ──

DIFF9 = "@@ -1,2 +1,2 @@\n-old\n+new\n\\ No newline at end of file\n"


def test_9_1_保留_no_newline():
    out, _ = _dc().compress(DIFF9)
    assert "\\ No newline" in out


# ── 测试 10: 混合交替模式 ──

DIFF10 = "@@ -1,10 +1,10 @@\n a\n b\n-old1\n+new1\n c\n d\n-old2\n+new2\n e\n f\n"


def test_10_1_insertions_2():
    _, stats = _dc().compress(DIFF10)
    assert stats["insertions"] == 2


def test_10_2_deletions_2():
    _, stats = _dc().compress(DIFF10)
    assert stats["deletions"] == 2


def test_10_3_short_runs_保留原文():
    out, _ = _dc().compress(DIFF10)
    assert "+new1" in out and "-old1" in out
