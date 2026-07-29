"""Session Fence 模块测试。"""

import time
from pathlib import Path

import pytest

from mark42_modules.session_fence import (
    fence_verify,
    fence_record_pre,
    fence_record_post,
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

        mocker.patch("mark42_modules.session_fence.FENCE_STATE", tmp_path / "fence.json")

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

        mocker.patch("mark42_modules.session_fence.FENCE_STATE", tmp_path / "fence.json")

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

        mocker.patch("mark42_modules.session_fence.FENCE_STATE", tmp_path / "fence.json")

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

        mocker.patch("mark42_modules.session_fence.FENCE_STATE", tmp_path / "fence.json")

        pre_record = {"size": 50, "mtime": time.time() - 60}
        result = fence_record_post(fake_session, pre_record)
        assert result["ok"] is True
        assert result["tampered"] is False
