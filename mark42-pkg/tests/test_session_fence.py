"""Session Fence 模块测试。"""

import time
from pathlib import Path

from mark42.session_fence import (
    fence_record_post,
    fence_record_pre,
    fence_verify,
)


class TestFenceVerify:
    """fence_verify 测试群。"""

    def test_verify_returns_ok_for_existing_session(self, tmp_path, mocker):
        """存在且新鲜的 session 文件应通过验证。"""
        fake_session = tmp_path / "test.jsonl"
        fake_session.write_text('{"key": "agent:main:main"}\n')
        import os
        os.utime(fake_session, (time.time(), time.time()))

        result = fence_verify(fake_session)
        assert result["ok"] is True
        assert result["sessionPath"] == str(fake_session)
        assert result["size"] > 0

    def test_verify_rejects_nonexistent_session(self):
        """不存在的 session 应失败。"""
        result = fence_verify(Path("/nonexistent/path.jsonl"))
        assert result["ok"] is False

    def test_verify_rejects_stale_session(self, tmp_path):
        """超过 1 小时未更新的 session 应被判定为 stale。"""
        stale = tmp_path / "stale.jsonl"
        stale.write_text("{}")
        old_time = time.time() - 7200
        import os
        os.utime(stale, (old_time, old_time))

        result = fence_verify(stale)
        assert result["ok"] is False
        assert result["reason"] == "session-stale"


class TestFenceRecordPre:
    """fence_record_pre 测试群。"""

    def test_pre_record_saves_state(self, tmp_path, mocker):
        """pre 记录应保存 session 状态。"""
        fake_session = tmp_path / "session.jsonl"
        fake_session.write_text("test content")
        import os
        os.utime(fake_session, (time.time(), time.time()))

        mocker.patch("mark42.session_fence.FENCE_STATE", tmp_path / "fence.json")

        record = fence_record_pre(fake_session)
        assert record["phase"] == "pre-compact"
        assert record["sessionPath"] == str(fake_session)
        assert record["size"] > 0
        assert (tmp_path / "fence.json").exists()


class TestFenceRecordPost:
    """fence_record_post 测试群。"""

    def test_post_record_detects_tampering(self, tmp_path, mocker):
        """压缩后文件显著变大（>10%）应检测为篡改。"""
        fake_session = tmp_path / "session.jsonl"
        fake_session.write_text("x" * 200)  # 200 bytes
        import os
        os.utime(fake_session, (time.time(), time.time()))

        mocker.patch("mark42.session_fence.FENCE_STATE", tmp_path / "fence.json")

        pre_record = {"size": 50, "mtime": time.time() - 60}
        result = fence_record_post(fake_session, pre_record)
        # 200 > 50 * 1.10 = 55, so tampered
        assert result["ok"] is False
        assert result["tampered"] is True

    def test_post_record_ok_when_shrunk(self, tmp_path, mocker):
        """压缩后文件变小应正常。"""
        fake_session = tmp_path / "session.jsonl"
        fake_session.write_text("short")
        import os
        os.utime(fake_session, (time.time(), time.time()))

        mocker.patch("mark42.session_fence.FENCE_STATE", tmp_path / "fence.json")

        pre_record = {"size": 1000, "mtime": time.time() - 60}
        result = fence_record_post(fake_session, pre_record)
        assert result["ok"] is True
        assert result["tampered"] is False
        assert result["delta"] < 0

    def test_post_record_ok_when_slightly_larger(self, tmp_path, mocker):
        """压缩后文件小幅度变大（<10%）不应误报篡改。"""
        fake_session = tmp_path / "session.jsonl"
        fake_session.write_text("x" * 52)  # 52 bytes, pre was 50, only 4% growth
        import os
        os.utime(fake_session, (time.time(), time.time()))

        mocker.patch("mark42.session_fence.FENCE_STATE", tmp_path / "fence.json")

        pre_record = {"size": 50, "mtime": time.time() - 60}
        result = fence_record_post(fake_session, pre_record)
        assert result["ok"] is True
        assert result["tampered"] is False

    def test_post_record_stat_exception_handled(self, tmp_path, mocker):
        """【session_fence.py】post_record 中 stat 异常时返回 size=0。"""
        mocker.patch("mark42.session_fence.FENCE_STATE", tmp_path / "fence.json")

        # mock Path.stat 抛出异常
        fake_session = tmp_path / "session.jsonl"
        mocker.patch.object(fake_session.__class__, "stat", side_effect=OSError("io error"))

        pre_record = {"size": 100, "mtime": time.time() - 60}
        result = fence_record_post(fake_session, pre_record)
        assert result["postSize"] == 0
        assert result["preSize"] == 100
        # tampered: 0 > 100 * 1.10 = False
        assert result["tampered"] is False

    def test_post_record_pre_size_zero_not_tampered(self, tmp_path, mocker):
        """【session_fence.py】pre_size = 0 时不检测篡改。"""
        fake_session = tmp_path / "session.jsonl"
        fake_session.write_text("x" * 1000)
        mocker.patch("mark42.session_fence.FENCE_STATE", tmp_path / "fence.json")

        pre_record = {"size": 0, "mtime": 0}  # 无 pre 记录
        result = fence_record_post(fake_session, pre_record)
        # pre_size = 0 时不触发 tampered 检测
        assert result["tampered"] is False


class TestFenceVerifyMissingPaths:
    """fence_verify 缺失路径补全。"""

    def test_verify_none_session_path_calls_find_active(self, mocker):
        """【session_fence.py】session_path=None 时调用 _find_active_session。"""
        # _find_active_session 返回 None
        mocker.patch("mark42.session_fence._find_active_session", return_value=None)

        result = fence_verify(None)
        assert result["ok"] is False
        assert result["reason"] == "no-active-session"

    def test_verify_file_too_large_detected(self, tmp_path, mocker):
        """【session_fence.py】文件 > 2GB 时返回 file-too-large。"""
        fake_session = tmp_path / "huge.jsonl"
        fake_session.write_text("a")

        # mock stat 返回非常大的 size (>2GB)
        class FakeStat:
            st_size = 3 * 1024 * 1024 * 1024  # 3GB
            st_mtime = time.time()
        mocker.patch.object(fake_session.__class__, "stat", return_value=FakeStat())

        result = fence_verify(fake_session)
        assert result["ok"] is False
        assert result["reason"] == "file-too-large"

    def test_verify_stat_exception_fail_open(self, tmp_path, mocker):
        """【session_fence.py】stat 异常时 fail-open（ok=True）。"""
        fake_session = tmp_path / "session.jsonl"
        fake_session.write_text("test")

        mocker.patch.object(fake_session.__class__, "stat", side_effect=OSError("disk error"))

        result = fence_verify(fake_session)
        # Fail-open: 异常时放行，ok=True
        assert result["ok"] is True
        assert result["reason"] == "stat-skipped"
        assert result["size"] == 0


class TestFenceRecordPreMissingPaths:
    """fence_record_pre 缺失路径补全。"""

    def test_pre_record_stat_exception_handled(self, tmp_path, mocker):
        """【session_fence.py】pre_record stat 异常时返回 size=0, mtime=0。"""
        # 用一个不是 Path 的对象，没有 stat 方法，会触发 AttributeError
        class FakePath:
            def __str__(self):
                return "fake/path"

        mocker.patch("mark42.session_fence.FENCE_STATE", tmp_path / "fence.json")

        record = fence_record_pre(FakePath())
        assert record["size"] == 0
        assert record["mtime"] == 0
        assert record["phase"] == "pre-compact"
