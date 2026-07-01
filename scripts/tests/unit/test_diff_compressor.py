"""diff_compressor.py 测试群。

覆盖:
  - get_diff_compressor() 工厂 (单例)
  - diff_compress(content) 包装函数
  - is_diff() 启发式

设计:
  - 纯函数为主, 不需要 mock
  - 用 sample_diff fixture (含 hunk header 的真实 diff)
  - 字段名按 diff_compressor.py 实际: algorithm / original_bytes /
    original_lines / is_diff / crushed_bytes / ratio / hunks /
    context_lines_merged / insertions / deletions / mode
"""

import pytest

from mark42_modules import diff_compressor


class TestDiffCompressorFactory:
    """get_diff_compressor() 工厂测试群。"""

    def test_factory_singleton(self):
        c1 = diff_compressor.get_diff_compressor()
        c2 = diff_compressor.get_diff_compressor()
        assert c1 is c2

    def test_factory_returns_instance(self):
        comp = diff_compressor.get_diff_compressor()
        assert comp is not None
        assert hasattr(comp, "compress")
        assert hasattr(comp, "is_diff")


class TestIsDiff:
    """is_diff() 启发式测试群。"""

    def test_real_diff_detected(self, sample_diff):
        comp = diff_compressor.get_diff_compressor()
        assert comp.is_diff(sample_diff) is True

    def test_plain_text_not_detected(self):
        comp = diff_compressor.get_diff_compressor()
        text = "今天天气很好。\n我和朋友去公园玩了很久。\n"
        assert comp.is_diff(text) is False

    def test_empty_not_detected(self):
        comp = diff_compressor.get_diff_compressor()
        assert comp.is_diff("") is False

    def test_diff_without_hunk_header_not_detected(self):
        """有 + - 标记但无 @@ 头的不算 diff。"""
        text = "+ 新增\n- 删除\n+ 又新增\n"
        comp = diff_compressor.get_diff_compressor()
        # is_diff 严格要求 hunk header
        assert comp.is_diff(text) is False


class TestDiffCompress:
    """diff_compress() 包装函数测试群。"""

    def test_diff_compress_normal(self, sample_diff):
        """标准 diff (有 hunk header) 应被识别为 diff。"""
        result, meta = diff_compressor.diff_compress(sample_diff)
        assert isinstance(result, str)
        assert isinstance(meta, dict)
        assert meta["is_diff"] is True
        # 至少有 1 个 hunk
        assert meta["hunks"] >= 1

    def test_diff_compress_plain_text_passthrough(self):
        """非 diff 内容 passthrough, is_diff=False。"""
        text = "今天天气很好。\n我和朋友去公园玩了很久。\n"
        result, meta = diff_compressor.diff_compress(text)
        assert meta["is_diff"] is False
        assert meta["mode"] == "passthrough"
        assert result == text

    def test_diff_compress_empty(self):
        """空字符串 -> 原文, mode='none'。"""
        result, meta = diff_compressor.diff_compress("")
        assert result == ""
        assert meta["mode"] == "none"

    def test_metadata_contains_counts(self, sample_diff):
        """meta 含 hunks / insertions / deletions 等计数。"""
        result, meta = diff_compressor.diff_compress(sample_diff)
        # 这些字段是 diff_compressor 统计项
        assert "hunks" in meta
        assert "insertions" in meta
        assert "deletions" in meta
        assert "context_lines_merged" in meta
        # 计数是非负整数
        assert meta["hunks"] >= 0
        assert meta["insertions"] >= 0
        assert meta["deletions"] >= 0

    def test_metadata_contains_saved_bytes(self, sample_diff):
        """meta 含 original_bytes / crushed_bytes / ratio。"""
        result, meta = diff_compressor.diff_compress(sample_diff)
        assert "original_bytes" in meta
        assert "crushed_bytes" in meta
        assert "ratio" in meta
        assert meta["original_bytes"] >= meta["crushed_bytes"]
        assert 0.0 <= meta["ratio"] <= 1.0

    def test_returns_tuple(self, sample_diff):
        """返回值必须是 2-tuple。"""
        result = diff_compressor.diff_compress(sample_diff)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)

    def test_diff_with_context_lines_merged(self):
        """含连续 5 行 context 的 diff, 应合并。"""
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,7 +1,7 @@\n"
            " line1\n"
            " line2\n"
            " line3\n"
            " line4\n"
            " line5\n"
            "-old line\n"
            "+new line\n"
        )
        result, meta = diff_compressor.diff_compress(diff)
        assert meta["is_diff"] is True
        assert "5 context" in result
        assert meta["context_lines_merged"] == 5

    def test_short_context_run_keeps_original_lines(self):
        comp = diff_compressor.DiffCompressor(merge_context_threshold=3)
        diff = (
            "@@ -1,3 +1,3 @@\n"
            " a\n"
            " b\n"
            "-old\n"
            "+new\n"
        )
        result, meta = comp.compress(diff)
        assert " a" in result
        assert " b" in result
        assert "context" not in result
        assert meta["context_lines_merged"] == 2

    def test_insertions_and_deletions_long_run_are_merged(self):
        diff = (
            "@@ -1,3 +1,8 @@\n"
            " keep\n"
            "+n1\n+n2\n+n3\n"
            "-o1\n-o2\n-o3\n"
        )
        result, meta = diff_compressor.diff_compress(diff)
        assert "3 insertions" in result
        assert "3 deletions" in result
        assert meta["insertions"] == 3
        assert meta["deletions"] == 3

    def test_preserve_file_headers_false_drops_file_headers(self):
        comp = diff_compressor.DiffCompressor(preserve_file_headers=False)
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "index 123..456 100644\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-old\n"
            "+new\n"
        )
        result, meta = comp.compress(diff)
        assert "diff --git" not in result
        assert "index 123..456 100644" not in result
        assert "--- a/foo.py" not in result
        assert "+++ b/foo.py" not in result
        assert "@@ -1,2 +1,2 @@" in result
        assert meta["hunks"] == 1

    def test_preserve_hunk_headers_false_drops_hunk_header(self):
        comp = diff_compressor.DiffCompressor(preserve_hunk_headers=False)
        diff = (
            "@@ -1,2 +1,2 @@\n"
            "-old\n"
            "+new\n"
        )
        result, meta = comp.compress(diff)
        assert "@@ -1,2 +1,2 @@" not in result
        assert "-old" in result
        assert "+new" in result
        assert meta["hunks"] == 1

    def test_backslash_no_newline_marker_preserved(self):
        diff = (
            "@@ -1,2 +1,2 @@\n"
            "-old\n"
            "+new\n"
            "\\ No newline at end of file\n"
        )
        result, meta = diff_compressor.diff_compress(diff)
        assert "\\ No newline at end of file" in result
        assert meta["mode"] == "compressed"

    def test_multiple_hunks_counted(self):
        diff = (
            "@@ -1,2 +1,2 @@\n"
            "-old1\n"
            "+new1\n"
            "@@ -10,2 +10,2 @@\n"
            "-old2\n"
            "+new2\n"
        )
        result, meta = diff_compressor.diff_compress(diff)
        assert meta["hunks"] == 2
        assert result.count("@@") == 4

    def test_compress_error_returns_original_and_error_mode(self, monkeypatch):
        comp = diff_compressor.DiffCompressor()

        def boom(*args, **kwargs):
            raise RuntimeError("explode")

        monkeypatch.setattr(comp, "_compress_diff", boom)
        diff = "@@ -1,1 +1,1 @@\n-old\n+new\n"
        result, meta = comp.compress(diff)
        assert result == diff
        assert meta["mode"] == "error"
        assert meta["error"] == "explode"


class TestRunTests:
    def test_run_tests_success(self, capsys):
        assert diff_compressor._run_tests() is True
        out = capsys.readouterr().out
        assert "结果:" in out
        assert "通过" in out
        assert "失败" in out

    def test_main_branch_exit_zero(self, monkeypatch):
        monkeypatch.setattr(diff_compressor, "_run_tests", lambda: True)
        with pytest.raises(SystemExit) as exc:
            exec(
                'import sys\nsys.exit(0 if _run_tests() else 1)',
                {"_run_tests": diff_compressor._run_tests, "sys": __import__("sys")},
            )
        assert exc.value.code == 0

    def test_main_branch_exit_one(self, monkeypatch):
        monkeypatch.setattr(diff_compressor, "_run_tests", lambda: False)
        with pytest.raises(SystemExit) as exc:
            exec(
                'import sys\nsys.exit(0 if _run_tests() else 1)',
                {"_run_tests": diff_compressor._run_tests, "sys": __import__("sys")},
            )
        assert exc.value.code == 1
