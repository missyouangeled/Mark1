"""code_compressor.py 单元测试（pytest 形式）。

原为脚本式 run_tests()，转换为 pytest 可收集的 test_* 函数以纳入覆盖率统计。
"""

from mark42.code_compressor import CodeCompressor


def _cc():
    return CodeCompressor(language="auto", min_code_size=50)


# ── 测试 1: Python 函数+类（含 docstring + 注释）──

PY_CODE = '''
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


def test_python_is_code():
    _, stats = _cc().compress(PY_CODE)
    assert stats["is_code"] is True


def test_python_language_detected():
    _, stats = _cc().compress(PY_CODE)
    assert stats["language"] == "python"


def test_python_docstring_removed():
    out, _ = _cc().compress(PY_CODE)
    assert "文档字符串" not in out


def test_python_keeps_def_signature():
    out, _ = _cc().compress(PY_CODE)
    assert "def foo(x, y):" in out


def test_python_keeps_class_signature():
    out, _ = _cc().compress(PY_CODE)
    assert "class Bar:" in out


def test_python_docstring_count():
    _, stats = _cc().compress(PY_CODE)
    assert stats["removed_docstrings"] >= 2


# ── 测试 2: 大函数截断 ──

def test_big_function_truncated():
    big_func = "def big():\n"
    for i in range(50):
        big_func += f"    x_{i} = {i}\n"
    big_func += "    return x_49\n"
    out, stats = _cc().compress(big_func)
    assert stats["truncated_functions"] >= 1
    assert "more statements" in out


# ── 测试 3: 装饰器 + async ──

def test_decorator_and_async_preserved():
    deco_code = """
@property
def my_prop(self):
    return self._x

@staticmethod
async def fetch():
    return await something()
"""
    out, _ = _cc().compress(deco_code)
    assert "@property" in out
    assert "async def fetch" in out


# ── 测试 4: JavaScript 正则 fallback ──

def test_javascript_comment_removal():
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
    out, _ = _cc().compress(js_code)
    assert "这是注释" not in out
    assert "块注释" not in out
    assert "function foo" in out


# ── 测试 5: 非代码 passthrough ──

def test_non_code_passthrough():
    _, stats = _cc().compress("hello world this is just text\nnothing here\n")
    assert stats["is_code"] is False
    assert stats["mode"] == "passthrough"


# ── 测试 6: 语法错误 fail-safe ──

def test_syntax_error_failsafe():
    bad_code = "def broken(:\n" + "    pass\n" * 20 + "\n"
    out, stats = _cc().compress(bad_code)
    assert stats["mode"] in ("error", "passthrough")
    assert "broken" in out


# ── 测试 7: 小代码 passthrough ──

def test_small_code_passthrough():
    _, stats = _cc().compress("def f(): pass\n")
    assert stats["mode"] == "passthrough"


# ── 测试 8: 空内容 ──

def test_empty_content():
    _, stats = _cc().compress("")
    assert stats["ratio"] == 0.0
