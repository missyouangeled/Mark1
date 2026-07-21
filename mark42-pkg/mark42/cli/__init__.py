"""Mark42 CLI 入口包。

包含 argparse 解析、命令分发、assemble 进程管理、状态面板等功能。
入口函数: mark42.cli.main
"""

from __future__ import annotations

from .assemble import (
    assemble,
    assemble_restart,
    assemble_status,
    assemble_stop,
)
from .parser import _build_parser, _cmd_context_safety, _cmd_status, main
from .status import status_dashboard

__all__ = [
    "main",
    "_build_parser",
    "_cmd_status",
    "_cmd_context_safety",
    "assemble",
    "assemble_status",
    "assemble_stop",
    "assemble_restart",
    "status_dashboard",
]
