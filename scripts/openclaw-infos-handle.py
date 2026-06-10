#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）设计并验证最小入口）
# 系统 / OS：通用
# 用途：infos-handle 薄壳入口，实际逻辑已拆分至 scripts/core/ 子模块。

from __future__ import annotations

import sys
from pathlib import Path

# 确保 scripts/ 在 import 路径中，以便 core/ 子模块可被导入
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from core.main import main

if __name__ == "__main__":
    raise SystemExit(main())
