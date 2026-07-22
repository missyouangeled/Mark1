"""Mark42 CLI 入口包。

入口函数: mark42.cli.main
所有 dispatch 逻辑在 parser.py 中（单文件版）。
"""

from __future__ import annotations

from .parser import main

__all__ = ["main"]
