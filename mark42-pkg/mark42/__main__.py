#!/usr/bin/env python3
"""Mark42 模块化智能铠甲系统 - 模块入口。

使用: mark42 --help
  或: python3 -m mark42 --help
"""

from mark42.cli import main

if __name__ == "__main__":
    # 必须将 main() 返回码传给 SystemExit，否则
    # `python3 -m mark42` 与 console script `mark42` 退出语义不一致：
    # CLI 内部的 return 1/2 会被静默丢弃，失败仍报退出码 0，
    # 而 systemd 模板正是通过模块路径回退执行的。
    raise SystemExit(main())
