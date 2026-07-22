"""Mark42 统一日志模块。

用法（各模块顶部）：
    from .log_setup import get_logger
    logger = get_logger(__name__)

    logger.info("普通信息")
    logger.warning("警告")
    logger.error("错误")
    logger.debug("调试信息")
    logger.exception("捕获异常时记录堆栈")  # 自动带 traceback
"""

import logging
import os
import sys

# ── 日志格式 ─────────────────────────────────────────────
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── 日志级别映射 ──────────────────────────────────────────
_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_initialized = False


def _init_logging():
    """初始化根日志配置。只执行一次。"""
    global _initialized
    if _initialized:
        return

    level_name = os.environ.get("MARK42_LOG_LEVEL", "INFO").upper()
    level = _LEVEL_MAP.get(level_name, logging.INFO)

    # 根 logger 配置
    root = logging.getLogger("mark42")
    if root.handlers:
        _initialized = True
        return

    root.setLevel(level)

    # stdout handler（systemd 会捕获到 journal）
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    handler.setLevel(level)
    root.addHandler(handler)

    # 防止向上传播到 root logging
    root.propagate = False

    _initialized = True


def get_logger(name: str = "mark42") -> logging.Logger:
    """获取一个 mark42 命名空间下的 logger。

    Args:
        name: 通常传 __name__，如 'mark42.armor'

    Returns:
        配置好的 logging.Logger 实例
    """
    _init_logging()

    # 确保 name 以 mark42 开头
    if not name.startswith("mark42"):
        name = f"mark42.{name}" if name != "__main__" else "mark42"

    return logging.getLogger(name)


# ── 便捷函数（向后兼容 print 风格）────────────────────────
def log_info(msg: str, *args, **kwargs):
    """等价于 logger.info()，兼容 print 风格调用。"""
    get_logger().info(msg, *args, **kwargs)


def log_warn(msg: str, *args, **kwargs):
    get_logger().warning(msg, *args, **kwargs)


def log_error(msg: str, *args, **kwargs):
    get_logger().error(msg, *args, **kwargs)


def log_debug(msg: str, *args, **kwargs):
    get_logger().debug(msg, *args, **kwargs)


def log_exception(msg: str, *args, **kwargs):
    """记录异常（自动带 traceback）。在 except 块中使用。"""
    get_logger().exception(msg, *args, **kwargs)
