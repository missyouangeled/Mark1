"""log_deduplicator.py 测试群。

覆盖:
  - get_log_deduplicator() 工厂单例
  - is_log() 日志检测启发式
  - logdedup(content) 包装函数
  - 关键边界: keep_tail_lines=0 / critical 去重保序 / max_unique_lines 截断

设计:
  - 纯函数为主, 不需要 mock
  - 用真实日志样本, 不走脆弱 patch
  - 断言字段名按 log_deduplicator.py 当前实现
"""

from mark42_modules import log_deduplicator


class TestLogDeduplicatorFactory:
    """get_log_deduplicator() 工厂测试群。"""

    def test_factory_singleton(self):
        d1 = log_deduplicator.get_log_deduplicator()
        d2 = log_deduplicator.get_log_deduplicator()
        assert d1 is d2

    def test_factory_returns_instance(self):
        dedup = log_deduplicator.get_log_deduplicator()
        assert dedup is not None
        assert hasattr(dedup, "dedup")
        assert hasattr(dedup, "is_log")


class TestIsLog:
    """is_log() 启发式测试群。"""

    def test_detects_timestamp_logs(self):
        dedup = log_deduplicator.LogDeduplicator()
        text = "\n".join([
            f"2026-07-01 10:00:{i:02d} INFO: event {i}" for i in range(10)
        ])
        assert dedup.is_log(text) is True

    def test_detects_level_prefix_logs(self):
        dedup = log_deduplicator.LogDeduplicator()
        text = "\n".join([
            "[INFO] booting",
            "[WARN] retrying",
            "[ERROR] failed once",
            "[INFO] booting",
            "[WARN] retrying",
            "[ERROR] failed once",
            "[INFO] booting",
            "[WARN] retrying",
            "[ERROR] failed once",
            "[INFO] done",
        ])
        assert dedup.is_log(text) is True

    def test_short_content_not_treated_as_log(self):
        dedup = log_deduplicator.LogDeduplicator()
        text = "\n".join([
            "2026-07-01 10:00:00 INFO: one",
            "2026-07-01 10:00:01 INFO: two",
            "2026-07-01 10:00:02 INFO: three",
            "2026-07-01 10:00:03 INFO: four",
        ])
        assert dedup.is_log(text) is False

    def test_natural_text_not_detected(self):
        dedup = log_deduplicator.LogDeduplicator()
        text = "\n".join([
            "今天天气不错，我们下午继续做 Mark42。",
            "这段文字没有时间戳，也没有日志级别。",
            "只是普通自然语言说明，不应该被当成日志。",
            "继续补测试和文档，避免漂移。",
            "最后再统一运行口径。",
            "这样可信度会更高。",
        ])
        assert dedup.is_log(text) is False


class TestLogDedup:
    """logdedup() 与 dedup() 行为测试群。"""

    def test_empty_content_returns_none_mode(self):
        result, meta = log_deduplicator.logdedup("")
        assert result == ""
        assert meta["mode"] == "none"
        assert meta["ratio"] == 0.0

    def test_non_log_passthrough(self):
        text = (
            "这是普通说明文。\n"
            "没有时间戳，没有级别，没有异常栈。\n"
            "不应该触发日志去重。\n"
            "保持原文返回。\n"
            "这是第五行。\n"
            "这是第六行。"
        )
        result, meta = log_deduplicator.logdedup(text)
        assert result == text
        assert meta["is_log"] is False
        assert meta["mode"] == "passthrough"
        assert meta["crushed_bytes"] == meta["original_bytes"]

    def test_repeated_log_lines_are_merged(self):
        dedup = log_deduplicator.LogDeduplicator(keep_tail_lines=5)
        text = "\n".join(
            ["2026-07-01 10:00:00 INFO: loading module"] * 20
            + ["2026-07-01 10:00:01 ERROR: database timeout"] * 10
            + [f"2026-07-01 10:00:02 DEBUG: tail {i}" for i in range(8)]
        )
        result, meta = dedup.dedup(text)
        assert meta["is_log"] is True
        assert meta["mode"] == "dedup"
        assert meta["merged_groups"] >= 1
        assert meta["ratio"] > 0.0
        assert "[×20] 2026-07-01 10:00:00 INFO: loading module" in result
        assert any("ERROR: database timeout" in e for e in meta["critical_events"])

    def test_critical_events_dedup_and_order_preserved(self):
        dedup = log_deduplicator.LogDeduplicator(keep_tail_lines=5)
        text = "\n".join([
            "2026-07-01 10:00:00 INFO: start",
            "2026-07-01 10:00:01 ERROR: first failure",
            "2026-07-01 10:00:02 ERROR: first failure",
            "2026-07-01 10:00:03 Traceback (most recent call last):",
            "2026-07-01 10:00:04 ValueError: bad input",
            "2026-07-01 10:00:05 ERROR: later failure",
            "2026-07-01 10:00:06 ERROR: later failure",
            "2026-07-01 10:00:07 INFO: done",
            "2026-07-01 10:00:08 INFO: done",
            "2026-07-01 10:00:09 INFO: done",
        ])
        _, meta = dedup.dedup(text)
        assert meta["critical_events"] == [
            "2026-07-01 10:00:01 ERROR: first failure",
            "2026-07-01 10:00:02 ERROR: first failure",
            "2026-07-01 10:00:03 Traceback (most recent call last):",
            "2026-07-01 10:00:04 ValueError: bad input",
            "2026-07-01 10:00:05 ERROR: later failure",
            "2026-07-01 10:00:06 ERROR: later failure",
        ]

    def test_keep_tail_zero_does_not_turn_all_lines_into_tail(self):
        dedup = log_deduplicator.LogDeduplicator(keep_tail_lines=0, dedup_min_repeat=2)
        text = "\n".join([
            "2026-07-01 10:00:00 INFO: repeat",
            "2026-07-01 10:00:00 INFO: repeat",
            "2026-07-01 10:00:00 INFO: repeat",
            "2026-07-01 10:00:01 INFO: other",
            "2026-07-01 10:00:01 INFO: other",
            "2026-07-01 10:00:02 INFO: last",
            "2026-07-01 10:00:03 INFO: end",
            "2026-07-01 10:00:04 INFO: end2",
            "2026-07-01 10:00:05 INFO: end3",
            "2026-07-01 10:00:06 INFO: end4",
        ])
        result, meta = dedup.dedup(text)
        assert meta["kept_tail_lines"] == 0
        assert "--- 最后" not in result
        assert meta["merged_groups"] >= 2
        assert "[×3] 2026-07-01 10:00:00 INFO: repeat" in result

    def test_max_unique_lines_truncates_head(self):
        dedup = log_deduplicator.LogDeduplicator(keep_tail_lines=2, max_unique_lines=3, dedup_min_repeat=99)
        head = [f"2026-07-01 10:00:{i:02d} INFO: unique {i}" for i in range(8)]
        tail = [
            "2026-07-01 10:00:08 INFO: tail a",
            "2026-07-01 10:00:09 INFO: tail b",
        ]
        result, meta = dedup.dedup("\n".join(head + tail))
        assert meta["unique_lines"] == 3
        assert "unique 0" in result
        assert "unique 1" in result
        assert "unique 2" in result
        assert "unique 3" not in result
        assert "tail a" in result
        assert "tail b" in result

    def test_returns_tuple_and_expected_fields(self):
        text = "\n".join([f"2026-07-01 10:00:{i:02d} INFO: line" for i in range(10)])
        result = log_deduplicator.logdedup(text)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)
        meta = result[1]
        for key in [
            "algorithm",
            "original_bytes",
            "original_lines",
            "unique_lines",
            "merged_groups",
            "repeated_lines_total",
            "kept_tail_lines",
            "critical_events",
            "is_log",
            "crushed_bytes",
            "ratio",
            "mode",
        ]:
            assert key in meta
