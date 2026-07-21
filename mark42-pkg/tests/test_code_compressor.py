"""从 code_compressor.py 提取的单元测试。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.code_compressor import *


def run_tests():
    logger.info("=" * 60)
    logger.info("CodeCompressor 单元测试")
    logger.info("=" * 60)

    cc = CodeCompressor(language="auto", min_code_size=50)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            logger.info(f"  ✓ {name}")
            passed += 1
        else:
            logger.error(f"  ✗ {name} -- {detail}")
            failed += 1

    # ---- 测试 1: Python 函数 (含 docstring + 注释) ----
    py_code = '''
def foo(x, y):
    """这是一个很长的文档字符串"""
    # 这是注释
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    return a + b + c + d + e


class Bar:
    """类 docstring"""
    def __init__(self):
        self.x = 1

    def method1(self):
        return self.x
'''
    out, stats = cc.compress(py_code)
    logger.info("\n[测试 1] Python 函数+类 (含 docstring)")
    logger.info(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio'] * 100:.1f}%)")
    logger.info(f"  removed_docstrings={stats['removed_docstrings']}")
    check("1.1 is_code=True", stats["is_code"])
    check("1.2 language=python", stats["language"] == "python")
    check("1.3 docstring 被移除", "文档字符串" not in out)
    check("1.4 保留 def 签名", "def foo(x, y):" in out)
    check("1.5 保留类签名", "class Bar:" in out)
    check("1.6 docstring 计数 >= 2", stats["removed_docstrings"] >= 2)

    # ---- 测试 2: 大函数截断 ----
    big_func = "def big():\n"
    for i in range(50):
        big_func += f"    x_{i} = {i}\n"
    big_func += "    return x_49\n"
    out, stats = cc.compress(big_func)
    logger.info("\n[测试 2] 大函数截断 (50 条语句)")
    check("2.1 标记 truncated_functions", stats["truncated_functions"] >= 1)
    check("2.2 输出含截断标记", "more statements" in out)

    # ---- 测试 3: 装饰器 + async ----
    deco_code = """
@property
def my_prop(self):
    return self._x

@staticmethod
async def fetch():
    return await something()
"""
    out, stats = cc.compress(deco_code)
    logger.info("\n[测试 3] 装饰器 + async")
    check("3.1 保留装饰器", "@property" in out)
    check("3.2 保留 async", "async def fetch" in out)

    # ---- 测试 4: JavaScript (正则 fallback) ----
    js_code = """
// 这是注释
function foo(x) {
    // 内部注释
    const a = 1;
    return a + x;
}

/* 块注释 */
const bar = 42;
"""
    out, stats = cc.compress(js_code)
    logger.info("\n[测试 4] JavaScript 正则压缩")
    check("4.1 注释被移除", "这是注释" not in out)
    check("4.2 块注释被移除", "块注释" not in out)
    check("4.3 保留 function", "function foo" in out)

    # ---- 测试 5: 非代码 passthrough ----
    out, stats = cc.compress("hello world this is just text\nnothing here\n")
    logger.info("\n[测试 5] 非代码 passthrough")
    check("5.1 is_code=False", stats["is_code"] is False)
    check("5.2 mode=passthrough", stats["mode"] == "passthrough")

    # ---- 测试 6: 错误输入 (语法错误) 走 fail-safe ----
    # 多关键词, 超过 min_code_size, 强制走 AST 路径并报错
    bad_code = "def broken(:\n" + "    pass\n" * 20 + "\n"
    out, stats = cc.compress(bad_code)
    logger.info("\n[测试 6] 语法错误 fail-safe")
    logger.info(f"  mode={stats['mode']}, is_code={stats['is_code']}")
    check("6.1 不崩溃", stats["mode"] in ("error", "passthrough"))
    check("6.2 返回原文 (fail-safe)", "broken" in out)

    # ---- 测试 7: 小代码 passthrough ----
    small = "def f(): pass\n"
    out, stats = cc.compress(small)
    logger.info("\n[测试 7] 小代码 passthrough")
    check("7.1 mode=passthrough", stats["mode"] == "passthrough")

    # ---- 测试 8: 空内容 ----
    out, stats = cc.compress("")
    check("8.1 空内容 ratio=0", stats["ratio"] == 0.0)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"结果: {passed} 通过 / {failed} 失败")
    logger.info("=" * 60)
    return failed == 0
