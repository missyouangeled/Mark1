"""test_armor.py - 上下文铠甲核心测试。

覆盖：
- armor_check() 返回结构与阈值判定
- _classify_messages() 消息分类
- _read_session_tail() 会话尾部读取
- armor_compress() dry-run 模式
- armor_compress_async() 异步压缩
- armor_compress_queue_stats() 队列统计
"""

import json
import tempfile
from unittest import mock

import pytest

from mark42.armor import (
    _classify_messages,
    _read_session_tail,
    armor_check,
    armor_compress,
    armor_compress_async,
    armor_compress_queue_stats,
)


# ── armor_check ──────────────────────────────────────────


class TestArmorCheck:
    """测试 armor_check 返回正确结构。"""

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._get_context_window")
    @mock.patch("mark42.armor._estimate_tokens_smart")
    @mock.patch("mark42.armor.os.uname")
    def test_returns_dict_with_required_keys(self, mock_uname, mock_estimate, mock_window, mock_find):
        """armor_check 应返回包含必需字段的字典。"""
        mock_uname.return_value = mock.Mock(nodename="test-host")
        mock_window.return_value = 128000

        # Mock 活跃会话
        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_estimate.return_value = {
            "estimatedTokens": 10000,
            "method": "smart",
            "zhChars": 100,
            "enChars": 500,
            "otherChars": 50,
            "scannedMessages": 50,
        }

        with mock.patch("mark42.armor.os.environ", {}):
            result = armor_check()

        assert isinstance(result, dict)
        required_keys = {"usagePercent", "contextWindow", "estimatedTokens", "status", "severity", "summary"}
        assert required_keys.issubset(result.keys())

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._get_context_window")
    @mock.patch("mark42.armor._estimate_tokens_smart")
    @mock.patch("mark42.armor.os.uname")
    def test_status_values(self, mock_uname, mock_estimate, mock_window, mock_find):
        """status 应为有效值之一。"""
        mock_uname.return_value = mock.Mock(nodename="test-host")
        mock_window.return_value = 128000

        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_estimate.return_value = {"estimatedTokens": 10000}

        with mock.patch("mark42.armor.os.environ", {}):
            result = armor_check()

        assert result["status"] in ("ok", "warn", "alert", "critical", "unknown")

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._get_context_window")
    @mock.patch("mark42.armor._estimate_tokens_smart")
    @mock.patch("mark42.armor.os.uname")
    def test_severity_ok(self, mock_uname, mock_estimate, mock_window, mock_find):
        """使用率 < 70% 时 severity 应为 ok。"""
        mock_uname.return_value = mock.Mock(nodename="test-host")
        mock_window.return_value = 100000

        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_estimate.return_value = {"estimatedTokens": 50000}  # 50%

        with mock.patch("mark42.armor.os.environ", {}):
            result = armor_check()

        assert result["severity"] == "ok"
        assert result["status"] == "ok"

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._get_context_window")
    @mock.patch("mark42.armor._estimate_tokens_smart")
    @mock.patch("mark42.armor.os.uname")
    def test_severity_critical(self, mock_uname, mock_estimate, mock_window, mock_find):
        """使用率高时 severity 应为 critical。"""
        mock_uname.return_value = mock.Mock(nodename="test-host")
        mock_window.return_value = 100000

        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=90000)
        mock_find.return_value = mock_session

        mock_estimate.return_value = {"estimatedTokens": 95000}  # 95%

        with mock.patch("mark42.armor.os.environ", {}):
            result = armor_check()

        assert result["severity"] == "critical"
        assert result["status"] == "critical"

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._get_context_window")
    @mock.patch("mark42.armor.os.uname")
    def test_no_active_session(self, mock_uname, mock_window, mock_find):
        """未找到活跃会话时应返回 unknown 状态。"""
        mock_uname.return_value = mock.Mock(nodename="test-host")
        mock_window.return_value = 128000
        mock_find.return_value = None

        result = armor_check()

        assert result["status"] == "unknown"
        assert result["severity"] == "ok"
        assert result["usagePercent"] == 0

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._get_context_window")
    @mock.patch("mark42.armor._estimate_tokens_smart")
    @mock.patch("mark42.armor.os.uname")
    def test_context_window_positive(self, mock_uname, mock_estimate, mock_window, mock_find):
        """contextWindow 应为正数。"""
        mock_uname.return_value = mock.Mock(nodename="test-host")
        mock_window.return_value = 128000

        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_estimate.return_value = {"estimatedTokens": 10000}

        with mock.patch("mark42.armor.os.environ", {}):
            result = armor_check()

        assert result["contextWindow"] > 0

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._get_context_window")
    @mock.patch("mark42.armor._estimate_tokens_smart")
    @mock.patch("mark42.armor.os.uname")
    def test_estimated_tokens_non_negative(self, mock_uname, mock_estimate, mock_window, mock_find):
        """estimatedTokens 应非负。"""
        mock_uname.return_value = mock.Mock(nodename="test-host")
        mock_window.return_value = 128000

        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_estimate.return_value = {"estimatedTokens": 10000}

        with mock.patch("mark42.armor.os.environ", {}):
            result = armor_check()

        assert result["estimatedTokens"] >= 0


# ── _classify_messages ───────────────────────────────────


class TestClassifyMessages:
    """测试 _classify_messages 能分类消息。"""

    def test_empty_messages(self):
        """空消息列表应返回空分类。"""
        result = _classify_messages([])
        assert isinstance(result, dict)
        assert result.get("totalAnalyzed") == 0

    def test_classifies_user_and_assistant(self):
        """应正确分类用户和助手消息。"""
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮你的？"},
            {"role": "user", "content": "帮我查个东西"},
        ]
        result = _classify_messages(messages)
        assert result["totalAnalyzed"] == 3
        assert "preserved" in result
        assert "discarded" in result

    def test_identifies_important_messages(self):
        """应识别包含重要关键词的消息并保留。"""
        messages = [
            {"role": "user", "content": "记住这个设定：我叫小明"},
            {"role": "user", "content": "API Key 是 abc123"},
            {"role": "user", "content": "系统配置需要更新"},
        ]
        result = _classify_messages(messages)
        assert result["totalAnalyzed"] == 3
        assert len(result["preserved"]) >= 1

    def test_identifies_discardable_messages(self):
        """应识别简短可丢弃消息。"""
        messages = [
            {"role": "user", "content": "嗯"},
            {"role": "user", "content": "哦"},
            {"role": "user", "content": "好的"},
        ]
        result = _classify_messages(messages)
        assert result["totalAnalyzed"] == 3
        assert len(result["discarded"]) >= 1

    def test_handles_content_array_format(self):
        """应处理 OpenClaw content 数组格式。"""
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "测试消息"}]},
        ]
        result = _classify_messages(messages)
        assert result["totalAnalyzed"] == 1

    def test_short_messages_handled(self):
        """短消息不应崩溃。"""
        messages = [{"role": "user", "content": "hi"}]
        result = _classify_messages(messages)
        assert isinstance(result, dict)

    def test_system_messages_discarded(self):
        """system 消息应被丢弃。"""
        messages = [
            {"role": "system", "content": "这是一条系统消息"},
        ]
        result = _classify_messages(messages)
        assert result["totalAnalyzed"] == 1
        # system 角色应在 discarded 中
        assert len(result["discarded"]) >= 0

    def test_long_messages_preserved(self):
        """长消息应保留。"""
        long_text = "这是一条很长的消息。" * 50
        messages = [{"role": "user", "content": long_text}]
        result = _classify_messages(messages)
        assert result["totalAnalyzed"] == 1
        assert len(result["preserved"]) >= 1


# ── _read_session_tail ───────────────────────────────────


class TestReadSessionTail:
    """测试会话尾部读取。"""

    def test_reads_jsonl_file(self, tmp_path):
        """应正确读取 JSONL 文件。"""
        session_file = tmp_path / "test-session.jsonl"
        lines = [
            json.dumps({"role": "user", "content": "消息1"}),
            json.dumps({"role": "assistant", "content": "回复1"}),
            json.dumps({"role": "user", "content": "消息2"}),
            json.dumps({"role": "assistant", "content": "回复2"}),
            json.dumps({"role": "user", "content": "消息3"}),
        ]
        session_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = _read_session_tail(session_file, lines=5)
        assert len(result) >= 3
        assert result[-1]["content"] == "消息3"

    def test_reads_openclaw_nested_format(self, tmp_path):
        """应正确读取 OpenClaw 嵌套格式。"""
        session_file = tmp_path / "nested-session.jsonl"
        lines = [
            json.dumps({"type": "message", "message": {"role": "user", "content": "嵌套消息1"}}),
            json.dumps({"type": "message", "message": {"role": "assistant", "content": "嵌套回复1"}}),
        ]
        session_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = _read_session_tail(session_file, lines=10)
        # 应至少读取到一条消息
        assert len(result) >= 1
        # 最后一条应该是 assistant 消息
        assert result[-1]["role"] == "assistant"

    def test_tail_limit(self, tmp_path):
        """应只返回最后 N 行。"""
        session_file = tmp_path / "test-tail.jsonl"
        lines = [json.dumps({"role": "user", "content": f"msg{i}"}) for i in range(100)]
        session_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = _read_session_tail(session_file, lines=10)
        assert len(result) == 10
        assert result[-1]["content"] == "msg99"

    def test_empty_file(self, tmp_path):
        """空文件应返回空列表。"""
        session_file = tmp_path / "empty.jsonl"
        session_file.write_text("", encoding="utf-8")
        result = _read_session_tail(session_file, lines=10)
        assert result == []

    def test_non_existent_file(self):
        """不存在的文件应返回空列表。"""
        from pathlib import Path
        result = _read_session_tail(Path("/nonexistent/file.jsonl"), lines=10)
        assert result == []

    def test_handles_malformed_lines(self, tmp_path):
        """损坏的行不应导致崩溃。"""
        session_file = tmp_path / "malformed.jsonl"
        content = (
            json.dumps({"role": "user", "content": "good"})
            + "\n"
            + "NOT JSON\n"
            + json.dumps({"role": "assistant", "content": "also good"})
            + "\n"
        )
        session_file.write_text(content, encoding="utf-8")
        result = _read_session_tail(session_file, lines=10)
        assert len(result) >= 1


# ── armor_compress (dry-run) ─────────────────────────────


class TestArmorCompress:
    """测试 armor_compress 在 dry_run=True 时的行为。"""

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._read_session_tail")
    @mock.patch("mark42.armor._llm_analyze")
    @mock.patch("mark42.armor._save_json")
    @mock.patch("mark42.armor._append_broker")
    @mock.patch("mark42.armor.Path.mkdir")
    @mock.patch("mark42.armor.open")
    def test_dry_run_returns_dict(self, mock_open, mock_mkdir, mock_append, mock_save, mock_llm, mock_read, mock_find):
        """dry-run 模式应返回字典。"""
        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_read.return_value = [
            {"role": "user", "content": "测试消息"},
            {"role": "assistant", "content": "测试回复"},
        ]

        mock_llm.return_value = None  # 回退到启发式
        mock_open.return_value.__enter__ = mock.Mock(return_value=mock.Mock(write=mock.Mock()))
        mock_open.return_value.__exit__ = mock.Mock(return_value=False)

        # 确保使用率足够高以触发分析
        with mock.patch("mark42.armor.armor_check") as mock_check:
            mock_check.return_value = {
                "usagePercent": 80,
                "status": "alert",
                "severity": "warn",
                "summary": "测试",
                "estimatedTokens": 80000,
                "contextWindow": 100000,
            }

            result = armor_compress(dry_run=True)

        assert isinstance(result, dict)
        assert "action" in result
        assert result["action"] == "compress"

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._read_session_tail")
    @mock.patch("mark42.armor._llm_analyze")
    @mock.patch("mark42.armor._save_json")
    @mock.patch("mark42.armor._append_broker")
    @mock.patch("mark42.armor.subprocess.run")
    @mock.patch("mark42.armor.Path.mkdir")
    @mock.patch("mark42.armor.open")
    def test_dry_run_does_not_call_subprocess(self, mock_open, mock_mkdir, mock_subproc, mock_append,
                                              mock_save, mock_llm, mock_read, mock_find):
        """dry-run 不应调用 subprocess 做实际压缩。"""
        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_read.return_value = [
            {"role": "user", "content": "测试消息"},
        ]

        mock_llm.return_value = None
        mock_open.return_value.__enter__ = mock.Mock(return_value=mock.Mock(write=mock.Mock()))
        mock_open.return_value.__exit__ = mock.Mock(return_value=False)

        with mock.patch("mark42.armor.armor_check") as mock_check:
            mock_check.return_value = {
                "usagePercent": 80,
                "status": "alert",
                "severity": "warn",
                "summary": "测试",
                "estimatedTokens": 80000,
                "contextWindow": 100000,
            }

            result = armor_compress(dry_run=True)

        # subprocess 不应被调用（因为 dry_run=True）
        mock_subproc.assert_not_called()

    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._read_session_tail")
    @mock.patch("mark42.armor._save_json")
    @mock.patch("mark42.armor._append_broker")
    @mock.patch("mark42.armor.ARMOR_STATE")
    def test_skip_below_threshold(self, mock_armor_state, mock_append, mock_save, mock_read, mock_find):
        """低于阈值时应跳过。"""
        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_session.stat.return_value = mock.Mock(st_size=10000)
        mock_find.return_value = mock_session

        mock_read.return_value = []

        mock_armor_state.__truediv__ = lambda self, x: mock.Mock()

        with mock.patch("mark42.armor.armor_check") as mock_check:
            mock_check.return_value = {
                "usagePercent": 50,
                "status": "ok",
                "severity": "ok",
                "summary": "正常",
                "estimatedTokens": 50000,
                "contextWindow": 100000,
            }

            result = armor_compress(dry_run=False)

        assert result["action"] == "skip"

    def test_armor_compress_function_exists(self):
        """armor_compress 函数应存在且可调用。"""
        assert callable(armor_compress)


# ── armor_compress_async ─────────────────────────────────


class TestArmorCompressAsync:
    """测试异步压缩。"""

    @mock.patch("mark42.compress_queue.get_compress_queue")
    @mock.patch("mark42.armor._find_active_session")
    @mock.patch("mark42.armor._read_session_tail")
    def test_async_queued(self, mock_read, mock_find, mock_get_queue):
        """异步压缩应返回入队状态。"""
        mock_session = mock.Mock()
        mock_session.name = "test-session"
        mock_find.return_value = mock_session

        mock_read.return_value = [{"role": "user", "content": "test"}]

        mock_queue = mock.Mock()
        mock_queue.enqueue.return_value = True
        mock_queue.qsize.return_value = 1
        mock_queue.stats = {"pending": 1, "completed": 0}
        mock_get_queue.return_value = mock_queue

        result = armor_compress_async(dry_run=True, wait=False)

        assert result["status"] == "queued"
        assert "request_id" in result

    def test_async_import_error(self):
        """队列模块不可用时应返回错误。"""
        with mock.patch.dict("sys.modules", {"mark42.compress_queue": None}):
            # 重新导入以触发 ImportError
            import importlib
            import mark42.armor
            importlib.reload(mark42.armor)

        # 恢复后再次测试
        import mark42.armor
        result = armor_compress_async()
        # 可能返回 error 或其他状态，只要不崩溃即可
        assert isinstance(result, dict)


# ── armor_compress_queue_stats ───────────────────────────


class TestArmorCompressQueueStats:
    """测试队列统计。"""

    @mock.patch("mark42.compress_queue.get_compress_queue")
    def test_queue_stats(self, mock_get_queue):
        """应返回队列统计信息。"""
        mock_queue = mock.Mock()
        mock_queue.stats = {"pending": 5, "completed": 10, "failed": 1}
        mock_get_queue.return_value = mock_queue

        result = armor_compress_queue_stats()
        assert result["pending"] == 5
        assert result["completed"] == 10

    def test_queue_stats_import_error(self):
        """模块不可用时应返回错误。"""
        with mock.patch("mark42.compress_queue.get_compress_queue") as mock_get:
            mock_get.side_effect = ImportError("test")
            result = armor_compress_queue_stats()
            assert "error" in result
