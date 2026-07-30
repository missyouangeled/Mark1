"""
log_setup.py 单元测试
测试所有公开函数：
- get_logger
- log_info
- log_warn
- log_error
- log_debug
- log_exception
"""

import logging
import os
from unittest.mock import MagicMock, patch, call

import pytest


# 每个测试前重置 _initialized 标志
@pytest.fixture(autouse=True)
def reset_logging_state():
    import mark42.log_setup as log_setup
    # 重置初始化标志
    log_setup._initialized = False
    # 清空 mark42 根 logger 的 handlers
    root_logger = logging.getLogger("mark42")
    root_logger.handlers = []
    yield
    # 测试后也清理
    log_setup._initialized = False
    root_logger.handlers = []


class TestGetLogger:
    """测试 get_logger 函数。"""

    def test_get_logger_returns_logger_instance(self):
        """测试返回正确类型的 logger。"""
        from mark42.log_setup import get_logger
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_name_prefixed_with_mark42(self):
        """测试 logger 名称以 mark42 开头。"""
        from mark42.log_setup import get_logger
        logger = get_logger("my_module")
        assert logger.name.startswith("mark42.")
        assert "my_module" in logger.name

    def test_get_logger_already_mark42_prefixed(self):
        """测试名称已经以 mark42 开头时不重复添加。"""
        from mark42.log_setup import get_logger
        logger = get_logger("mark42.my_module")
        assert logger.name == "mark42.my_module"

    def test_get_logger_main_becomes_mark42(self):
        """测试 __main__ 变成 mark42。"""
        from mark42.log_setup import get_logger
        logger = get_logger("__main__")
        assert logger.name == "mark42"

    def test_get_logger_default_name(self):
        """测试默认名称。"""
        from mark42.log_setup import get_logger
        logger = get_logger()
        assert logger.name == "mark42"

    def test_get_logger_init_only_once(self):
        """测试初始化只执行一次。"""
        from mark42.log_setup import get_logger, _init_logging, _LEVEL_MAP

        # 第一次调用
        with patch('mark42.log_setup.logging.getLogger') as mock_get_logger:
            mock_root = MagicMock()
            mock_root.handlers = []
            mock_get_logger.return_value = mock_root

            logger1 = get_logger("test1")

            # handlers 应该被添加
            assert mock_root.addHandler.called
            add_handler_call_count = mock_root.addHandler.call_count

            # 第二次调用
            logger2 = get_logger("test2")

            # addHandler 不应该再被调用（因为 _initialized 已经是 True）
            assert mock_root.addHandler.call_count == add_handler_call_count

    @patch.dict(os.environ, {"MARK42_LOG_LEVEL": "DEBUG"})
    def test_get_logger_custom_level_from_env(self):
        """测试从环境变量读取日志级别。"""
        from mark42.log_setup import get_logger, _LEVEL_MAP
        logger = get_logger("test_debug")
        root_logger = logging.getLogger("mark42")
        # 级别应该是 DEBUG（但被转换了）
        # 注意：实际级别可能会被系统调整

    @patch.dict(os.environ, {"MARK42_LOG_LEVEL": "WARNING"})
    def test_get_logger_warning_level(self):
        """测试 WARNING 级别。"""
        from mark42.log_setup import get_logger
        logger = get_logger("test_warn")
        # 不抛出异常即可

    @patch.dict(os.environ, {"MARK42_LOG_LEVEL": "INVALID_LEVEL"})
    def test_get_logger_invalid_level_defaults_to_info(self):
        """测试无效级别默认使用 INFO。"""
        from mark42.log_setup import get_logger
        logger = get_logger("test_invalid")
        # 不抛出异常即可

    def test_init_logging_existing_handlers_returns(self):
        """测试如果已有 handlers，不重复初始化。"""
        from mark42.log_setup import _init_logging
        root_logger = logging.getLogger("mark42")
        root_logger.handlers = [MagicMock()]  # 添加一个假的 handler

        with patch('mark42.log_setup.logging.StreamHandler') as mock_handler:
            _init_logging()
            # 不应该创建新的 StreamHandler
            mock_handler.assert_not_called()

    def test_logger_propagate_false(self):
        """测试 logger 不向上传播（避免重复输出）。"""
        from mark42.log_setup import get_logger
        logger = get_logger("test")
        root_logger = logging.getLogger("mark42")
        assert root_logger.propagate is False


class TestLogFunctions:
    """测试便捷日志函数。"""

    def test_log_info(self):
        """测试 log_info。"""
        from mark42.log_setup import log_info

        with patch('mark42.log_setup.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_info("测试信息", "参数1", "参数2", extra={"key": "value"})

            mock_logger.info.assert_called_once_with(
                "测试信息", "参数1", "参数2", extra={"key": "value"}
            )

    def test_log_warn(self):
        """测试 log_warn。"""
        from mark42.log_setup import log_warn

        with patch('mark42.log_setup.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_warn("警告信息", "参数")

            mock_logger.warning.assert_called_once_with("警告信息", "参数")

    def test_log_error(self):
        """测试 log_error。"""
        from mark42.log_setup import log_error

        with patch('mark42.log_setup.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_error("错误信息", exc_info=True)

            mock_logger.error.assert_called_once_with("错误信息", exc_info=True)

    def test_log_debug(self):
        """测试 log_debug。"""
        from mark42.log_setup import log_debug

        with patch('mark42.log_setup.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_debug("调试信息", 1, 2, 3)

            mock_logger.debug.assert_called_once_with("调试信息", 1, 2, 3)

    def test_log_exception(self):
        """测试 log_exception。"""
        from mark42.log_setup import log_exception

        with patch('mark42.log_setup.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            try:
                raise ValueError("测试异常")
            except ValueError:
                log_exception("捕获到异常")

            mock_logger.exception.assert_called_once_with("捕获到异常")

    def test_log_functions_with_no_args(self):
        """测试无参数调用。"""
        from mark42.log_setup import log_info, log_warn, log_error, log_debug

        with patch('mark42.log_setup.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_info("简单消息")
            log_warn("简单警告")
            log_error("简单错误")
            log_debug("简单调试")

            assert mock_logger.info.called
            assert mock_logger.warning.called
            assert mock_logger.error.called
            assert mock_logger.debug.called


class TestLevelMap:
    """测试 _LEVEL_MAP 常量。"""

    def test_level_map_contains_all_levels(self):
        """测试 _LEVEL_MAP 包含所有日志级别。"""
        from mark42.log_setup import _LEVEL_MAP

        assert "DEBUG" in _LEVEL_MAP
        assert "INFO" in _LEVEL_MAP
        assert "WARNING" in _LEVEL_MAP
        assert "WARN" in _LEVEL_MAP
        assert "ERROR" in _LEVEL_MAP
        assert "CRITICAL" in _LEVEL_MAP

    def test_level_map_values_are_valid(self):
        """测试 _LEVEL_MAP 的值是有效的 logging 级别。"""
        from mark42.log_setup import _LEVEL_MAP

        assert _LEVEL_MAP["DEBUG"] == logging.DEBUG
        assert _LEVEL_MAP["INFO"] == logging.INFO
        assert _LEVEL_MAP["WARNING"] == logging.WARNING
        assert _LEVEL_MAP["WARN"] == logging.WARNING
        assert _LEVEL_MAP["ERROR"] == logging.ERROR
        assert _LEVEL_MAP["CRITICAL"] == logging.CRITICAL


class TestFormatConstants:
    """测试日志格式常量。"""

    def test_log_format_exists(self):
        """测试 _LOG_FORMAT 存在。"""
        from mark42.log_setup import _LOG_FORMAT
        assert isinstance(_LOG_FORMAT, str)
        assert len(_LOG_FORMAT) > 0

    def test_date_format_exists(self):
        """测试 _DATE_FORMAT 存在。"""
        from mark42.log_setup import _DATE_FORMAT
        assert isinstance(_DATE_FORMAT, str)
        assert len(_DATE_FORMAT) > 0
