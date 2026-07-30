"""
log_classifier.py 单元测试
测试所有公开函数和类：
- ClassificationResult 数据类
- LogClassifier
- CLI 函数
"""

import json
from unittest.mock import patch

from mark42.log_classifier import (
    LEVEL_RULES,
    SOURCE_RULES,
    ClassificationResult,
    LogClassifier,
    cli_classify_recent,
    cli_classify_stats,
    cli_classify_test,
)


class TestClassificationResult:
    """测试 ClassificationResult 数据类。"""

    def test_classification_result_default(self):
        """测试默认值创建。"""
        result = ClassificationResult()
        assert result.category == "unknown"
        assert result.level == "info"
        assert result.action == "monitor"
        assert result.matched_rule is None
        assert result.matched_keyword is None
        assert result.confidence == 0.0

    def test_classification_result_custom(self):
        """测试自定义值。"""
        result = ClassificationResult(
            category="health",
            level="warning",
            action="alert",
            matched_rule="R-HEALTH",
            matched_keyword="health",
            confidence=0.8,
        )
        assert result.category == "health"
        assert result.level == "warning"
        assert result.action == "alert"
        assert result.matched_rule == "R-HEALTH"
        assert result.matched_keyword == "health"
        assert result.confidence == 0.8

    def test_to_dict(self):
        """测试 to_dict 方法。"""
        result = ClassificationResult(
            category="system",
            level="error",
            action="auto_fix",
            matched_rule="R-SYSTEM",
            matched_keyword="disk",
            confidence=0.8,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["category"] == "system"
        assert d["level"] == "error"
        assert d["action"] == "auto_fix"
        assert d["matched_rule"] == "R-SYSTEM"
        assert d["matched_keyword"] == "disk"
        assert d["confidence"] == 0.8


class TestLogClassifier:
    """测试 LogClassifier 主类。"""

    def setup_method(self):
        """每个测试前的准备。"""
        self.classifier = LogClassifier()

    def test_classifier_init(self):
        """测试初始化。"""
        assert self.classifier.rules == SOURCE_RULES
        assert self.classifier.level_rules == LEVEL_RULES
        assert self.classifier._stats == {"total": 0, "classified": 0, "unknown": 0}

    def test_classify_health_category(self):
        """测试 health 分类。"""
        event = {"source": "health_monitor", "sourceEventType": "check.completed"}
        result = self.classifier.classify(event)
        assert result.category == "health"
        assert result.matched_rule == "R-HEALTH"
        assert result.confidence == 0.8

    def test_classify_tasks_category(self):
        """测试 tasks 分类。"""
        event = {"source": "task_manager", "sourceEventType": "subtask.started"}
        result = self.classifier.classify(event)
        assert result.category == "tasks"
        assert result.matched_rule == "R-TASKS"

    def test_classify_engine_category(self):
        """测试 engine 分类。"""
        event = {"source": "engine", "sourceEventType": "daemon.loop"}
        result = self.classifier.classify(event)
        assert result.category == "engine"
        assert result.matched_rule == "R-ENGINE"

    def test_classify_security_category(self):
        """测试 security 分类。"""
        event = {"source": "security", "sourceEventType": "auth.denied"}
        result = self.classifier.classify(event)
        assert result.category == "security"
        assert result.matched_rule == "R-SECURITY"

    def test_classify_system_category(self):
        """测试 system 分类。"""
        event = {"source": "systemd", "sourceEventType": "service.restart"}
        result = self.classifier.classify(event)
        assert result.category == "system"
        assert result.matched_rule == "R-SYSTEM"

    def test_classify_user_category(self):
        """测试 user 分类。"""
        event = {"source": "webchat", "sourceView": "user_input"}
        result = self.classifier.classify(event)
        assert result.category == "user"
        assert result.matched_rule == "R-USER"

    def test_classify_unknown_category(self):
        """测试 unknown 分类（无匹配规则）。"""
        event = {"source": "something_unknown", "sourceEventType": "random.event"}
        result = self.classifier.classify(event)
        assert result.category == "unknown"
        assert result.matched_rule is None
        assert result.confidence == 0.3

    def test_classify_level_critical(self):
        """测试 critical 级别。"""
        event = {"source": "system", "message": "process crashed with panic"}
        result = self.classifier.classify(event)
        assert result.level == "critical"

    def test_classify_level_error(self):
        """测试 error 级别。"""
        event = {"source": "system", "message": "operation failed due to timeout"}
        result = self.classifier.classify(event)
        assert result.level == "error"

    def test_classify_level_warning(self):
        """测试 warning 级别。"""
        event = {"source": "health", "message": "disk space is low, retry needed"}
        result = self.classifier.classify(event)
        assert result.level == "warning"

    def test_classify_level_info(self):
        """测试 info 级别。"""
        event = {"source": "tasks", "message": "task completed successfully"}
        result = self.classifier.classify(event)
        assert result.level == "info"

    def test_classify_level_uses_source_rule_default(self):
        """测试无级别关键词时使用 source 规则的默认级别。"""
        # security 规则的默认级别是 error
        event = {"source": "security", "message": "something happened"}  # 无级别关键词
        result = self.classifier.classify(event)
        assert result.level == "error"  # 来自 R-SECURITY 的 default_level

    def test_classify_level_unknown_defaults_to_info(self):
        """测试未知分类时默认级别为 info。"""
        event = {"source": "unknown_source", "message": "something happened"}
        result = self.classifier.classify(event)
        assert result.level == "info"

    def test_classify_action_security_alert(self):
        """测试 security 分类的 action 是 alert。"""
        event = {"source": "security", "sourceEventType": "auth"}
        result = self.classifier.classify(event)
        assert result.action == "alert"

    def test_classify_action_system_auto_fix(self):
        """测试 system 分类的 action 是 auto_fix。"""
        event = {"source": "system", "sourceEventType": "disk"}
        result = self.classifier.classify(event)
        assert result.action == "auto_fix"

    def test_classify_action_unknown_monitor(self):
        """测试 unknown 分类的 action 是 monitor。"""
        event = {"source": "unknown", "message": "test"}
        result = self.classifier.classify(event)
        assert result.action == "monitor"

    def test_classify_multiple_text_fields(self):
        """测试多个字段组合匹配。"""
        event = {
            "source": "some_source",
            "sourceEventType": "health_check",  # 这里有 health
            "sourceView": "something",
            "recordType": "log",
            "message": "disk usage high"  # 这里有 disk
        }
        result = self.classifier.classify(event)
        # 应该匹配 health（第一个规则）
        assert result.category in ["health", "system"]
        assert result.matched_rule is not None

    def test_classify_non_string_fields(self):
        """测试非字符串字段的处理。"""
        event = {"source": 123, "sourceEventType": None, "message": ["list", "not", "string"]}
        # 不应抛出异常
        result = self.classifier.classify(event)
        assert result is not None
        assert isinstance(result.category, str)

    def test_classify_batch(self):
        """测试批量分类。"""
        events = [
            {"source": "health", "message": "check completed"},
            {"source": "security", "message": "auth denied"},
            {"source": "unknown", "message": "test"},
        ]
        results = self.classifier.classify_batch(events)
        assert len(results) == 3
        assert results[0].category == "health"
        assert results[1].category == "security"
        assert results[2].category == "unknown"

    def test_stats_tracking(self):
        """测试统计跟踪。"""
        initial_stats = self.classifier.stats()
        assert initial_stats["total"] == 0

        # 分类 2 个已知，1 个未知
        self.classifier.classify({"source": "health"})
        self.classifier.classify({"source": "system"})
        self.classifier.classify({"source": "completely_unknown"})

        stats = self.classifier.stats()
        assert stats["total"] == 3
        assert stats["classified"] == 2
        assert stats["unknown"] == 1

    def test_health_check_success(self):
        """测试健康检查成功。"""
        assert self.classifier.health_check() is True

    def test_health_check_not_match(self):
        """测试健康检查结果不匹配。"""
        # 注意：如果实现改变，这个测试可能需要调整
        # 目前 health_check 测试 engine 分类，只要分类成功就返回 True
        result = self.classifier.health_check()
        assert isinstance(result, bool)


class TestCLI:
    """测试 CLI 接口函数。"""

    def test_cli_classify_test_with_json(self):
        """测试 CLI 分类带 JSON 字符串。"""
        event_json = json.dumps({"source": "health_monitor", "message": "check ok"})
        result = cli_classify_test(event_json)
        assert isinstance(result, dict)
        assert result["category"] == "health"

    def test_cli_classify_test_with_plain_string(self):
        """测试 CLI 分类带普通字符串（非 JSON）。"""
        result = cli_classify_test("security_alert")
        assert isinstance(result, dict)
        # 会被包装成 {"source": "security_alert", ...}
        # security_alert 包含 security，所以应该匹配 security 分类
        assert result["category"] == "security"

    def test_cli_classify_stats(self):
        """测试 CLI 统计。"""
        result = cli_classify_stats()
        assert isinstance(result, dict)
        assert "total" in result
        assert "classified" in result
        assert "unknown" in result

    @patch('mark42.log_classifier.Path.exists')
    def test_cli_classify_recent_file_not_exists(self, mock_exists):
        """测试 broker 文件不存在时返回空列表。"""
        mock_exists.return_value = False
        result = cli_classify_recent(limit=10)
        assert result == []

    @patch('mark42.log_classifier.Path.exists')
    @patch('mark42.log_classifier.open')
    def test_cli_classify_recent_with_events(self, mock_open_file, mock_exists):
        """测试有事件文件时分类。"""
        mock_exists.return_value = True
        # 模拟读取事件
        events = [
            {"source": "health", "sourceEventType": "check"},
            {"source": "security", "sourceEventType": "auth"},
        ]
        lines = "\n".join(json.dumps(e) for e in events) + "\n"
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = lines.split("\n")

        result = cli_classify_recent(limit=20)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["category"] == "health"
        assert result[1]["category"] == "security"

    @patch('mark42.log_classifier.Path.exists')
    @patch('mark42.log_classifier.open')
    def test_cli_classify_recent_invalid_json(self, mock_open_file, mock_exists):
        """测试事件中有无效 JSON 时跳过。"""
        mock_exists.return_value = True
        lines = '{"source": "health"}\ninvalid json line\n{"source": "system"}\n'
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = lines.split("\n")

        result = cli_classify_recent()

        assert isinstance(result, list)
        # 应该跳过无效的 JSON 行
        assert len(result) == 2
        categories = [r["category"] for r in result]
        assert "health" in categories
        assert "system" in categories
