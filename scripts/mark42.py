#!/usr/bin/env python3
"""Mark42 模块化智能铠甲系统 v2.2

模块拆分：
  mark42_modules/
    ├── config.py    # 常量 + 配置系统
    ├── utils.py     # 工具函数（JSON/文件/broker）
    ├── armor.py     # 模块A：上下文铠甲
    ├── engine.py    # 模块B：循环引擎
    ├── heavy.py     # 模块C：重型战甲
    ├── logs.py      # 日志轮替
    └── cli.py       # CLI 入口 + assemble

使用: python3 scripts/mark42.py --help
"""

import sys
import os

# 确保模块可导入
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from mark42_modules.cli import main

if __name__ == "__main__":
    main()
