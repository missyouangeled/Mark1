"""Mark42 代码压缩器（方向 A 算法 3）

设计文档:
- 开发手册: docs/design/mark42-开发手册-压缩子系统.md (4.4 节)

借鉴 Headroom code compressor, 纯 Python 实现 (不依赖 tree-sitter):
1. Python 代码: 用 ast.parse 解析, 移除 docstring/注释/空行, 保留函数签名 + body 骨架
2. 其他语言 (js/sh/go): 用正则 fallback (移除注释 + 空行 + 连续缩进)

接口风格: 与 compression_algorithms.py 对齐
  class Xxx + get_xxx() 单例 + xxx(code) -> tuple[str, dict]

创建日期: 2026-06-24 17:38
"""

import ast
import re
from typing import Any

from mark42_modules.utils import safe_call


class CodeCompressor:
    """代码压缩器"""

    def __init__(self,
                 language: str = "python",
                 preserve_signatures: bool = True,
                 remove_docstrings: bool = True,
                 remove_comments: bool = True,
                 max_stmts_per_func: int = 20,
                 min_code_size: int = 200):
        self.language = language
        self.preserve_signatures = preserve_signatures
        self.remove_docstrings = remove_docstrings
        self.remove_comments = remove_comments
        self.max_stmts_per_func = max_stmts_per_func
        self.min_code_size = min_code_size

    def is_code(self, content: str) -> bool:
        """启发式: 是否像代码 (不是看头看尾, 而是看关键词密度)"""
        if not content or len(content) < 50:
            return False
        # python 关键 token
        py_kw = sum(1 for kw in ["def ", "class ", "import ", "from ", "return ",
                                  "if __name__", "    self.", "lambda ", "yield ",
                                  "raise ", "except ", "with "]
                    if kw in content)
        # js / shell
        other_kw = sum(1 for kw in ["function ", "const ", "let ", "var ",
                                     "console.log", "echo ", "export "]
                       if kw in content)
        return (py_kw >= 2) or (other_kw >= 2)

    def compress(self, content: str) -> tuple[str, dict]:
        """压缩代码

        Args:
            content: 源代码字符串

        Returns:
            (压缩后代码, 统计信息)
        """
        stats = {
            "algorithm": "code_compress",
            "language": self.language,
            "original_bytes": len(content.encode("utf-8")),
            "original_lines": content.count("\n") + (1 if content and not content.endswith("\n") else 0),
            "is_code": False,
            "crushed_bytes": 0,
            "ratio": 0.0,
            "removed_docstrings": 0,
            "removed_comments": 0,
            "truncated_functions": 0,
            "mode": "none",
        }

        if not content or not content.strip():
            return content, stats

        # 自动检测语言
        if self.language == "auto":
            lang = self._detect_language(content)
            stats["language"] = lang
        else:
            lang = self.language

        # 检测是否像代码
        if not self.is_code(content):
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["mode"] = "passthrough"
            return content, stats
        stats["is_code"] = True

        # 小于阈值不处理
        if stats["original_bytes"] < self.min_code_size:
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["mode"] = "passthrough_small"
            return content, stats

        try:
            if lang == "python":
                result = self._compress_python(content, stats)
            else:
                result = self._compress_regex(content, stats)
        except Exception as e:
            # 出错回退原文 (fail-safe)
            stats["mode"] = "error"
            stats["error"] = str(e)
            return content, stats

        stats["crushed_bytes"] = len(result.encode("utf-8"))
        stats["ratio"] = 1.0 - stats["crushed_bytes"] / max(1, stats["original_bytes"])
        stats["mode"] = "compressed"
        return result, stats

    def _detect_language(self, content: str) -> str:
        """自动检测语言"""
        if any(kw in content for kw in ["def ", "import ", "from ", "class "]):
            return "python"
        if any(kw in content for kw in ["function ", "const ", "let ", "=>"]):
            return "javascript"
        if content.lstrip().startswith("#!") and "sh" in content.split("\n", 1)[0]:
            return "shell"
        return "generic"

    def _compress_python(self, code: str, stats: dict) -> str:
        """Python AST 级压缩。异常不上传装饰器（上层 compress() 有 try/except 拾回)"""
        tree = ast.parse(code)
        out_lines = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out_lines.extend(self._process_function(node, stats))
            elif isinstance(node, ast.ClassDef):
                out_lines.extend(self._process_class(node, stats))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                out_lines.append(ast.unparse(node))
            else:
                # 模块级其他语句: 常量赋值/表达式/if __name__
                src = ast.unparse(node)
                out_lines.append(src)

        return "\n".join(out_lines)

    def _process_function(self, node, stats: dict) -> list[str]:
        """处理函数定义"""
        lines = []

        # 函数签名
        if self.preserve_signatures:
            # 装饰器
            for dec in node.decorator_list:
                lines.append(f"@{ast.unparse(dec)}")
            # async 前缀
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            # args
            args_str = ast.unparse(node.args)
            # 返回类型
            returns = ""
            if node.returns:
                returns = f" -> {ast.unparse(node.returns)}"
            sig = f"{prefix}def {node.name}({args_str}){returns}:"
            lines.append(sig)
        else:
            lines.append(f"def {node.name}(...):")

        # docstring
        if (self.remove_docstrings and node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, (ast.Constant, ast.Str))):
            stats["removed_docstrings"] += 1
            body = node.body[1:]
        else:
            body = node.body

        # 处理 body
        if not body:
            lines.append("    pass")
            return lines

        # 截断大函数
        if len(body) > self.max_stmts_per_func:
            stats["truncated_functions"] += 1
            shown = body[:self.max_stmts_per_func]
            for stmt in shown:
                try:
                    src = ast.unparse(stmt)
                    lines.append(f"    {src}")
                except Exception:
                    lines.append("    ...")
            lines.append(f"    # ... {len(body) - self.max_stmts_per_func} more statements")
        else:
            for stmt in body:
                try:
                    src = ast.unparse(stmt)
                    lines.append(f"    {src}")
                except Exception:
                    lines.append("    ...")

        return lines

    def _process_class(self, node, stats: dict) -> list[str]:
        """处理类定义"""
        bases = ('(' + ', '.join(ast.unparse(b) for b in node.bases) + ')') if node.bases else ''
        lines = [f"class {node.name}{bases}:"]
        # 类自己的 docstring 剥离 (与 _process_function 同样的判定)
        body = node.body
        if (self.remove_docstrings and body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, (ast.Constant, ast.Str))):
            stats["removed_docstrings"] += 1
            body = body[1:]
        # 类体: 简单展开 (不递归处理方法)
        if not body:
            lines.append("    pass")
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.preserve_signatures:
                    args_str = ast.unparse(stmt.args)
                    lines.append(f"    def {stmt.name}({args_str}): ...")
                stats["truncated_functions"] += 1
            else:
                try:
                    lines.append(f"    {ast.unparse(stmt)}")
                except Exception:
                    pass
        return lines

    def _compress_regex(self, content: str, stats: dict) -> str:
        """正则 fallback（其他语言)。同上不上传装饰器，上层 compress() 拾回"""
        result = content

        if self.remove_comments:
            # 行注释 (//, #)
            result = re.sub(r'(?m)^\s*(?:#|//).*?$', '', result)
            # 块注释 /* ... */ 和 """ ... """
            result = re.sub(r'/\*.*?\*/', '', result, flags=re.DOTALL)
            result = re.sub(r'"""[\s\S]*?"""', '', result)
            stats["removed_comments"] = content.count('#') + content.count('//')

        # 移除连续空行 (留一行)
        result = re.sub(r'\n\s*\n+', '\n\n', result)
        return result


# 单例 + 公开 API
_code_singleton: CodeCompressor | None = None


def get_code_compressor() -> CodeCompressor:
    global _code_singleton
    if _code_singleton is None:
        _code_singleton = CodeCompressor()
    return _code_singleton


@safe_call(default=("", {"error": "codecrush failed"}), label="codecrush")
def codecrush(content: str) -> tuple[str, dict]:
    """公开 API: 代码压缩"""
    return get_code_compressor().compress(content)


# ============================================================================
# 单元测试
# ============================================================================

def _run_tests():
    print("=" * 60)
    print("CodeCompressor 单元测试")
    print("=" * 60)

    cc = CodeCompressor(language="auto", min_code_size=50)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name} -- {detail}")
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
    print(f"\n[测试 1] Python 函数+类 (含 docstring)")
    print(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio']*100:.1f}%)")
    print(f"  removed_docstrings={stats['removed_docstrings']}")
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
    print(f"\n[测试 2] 大函数截断 (50 条语句)")
    check("2.1 标记 truncated_functions", stats["truncated_functions"] >= 1)
    check("2.2 输出含截断标记", "more statements" in out)

    # ---- 测试 3: 装饰器 + async ----
    deco_code = '''
@property
def my_prop(self):
    return self._x

@staticmethod
async def fetch():
    return await something()
'''
    out, stats = cc.compress(deco_code)
    print(f"\n[测试 3] 装饰器 + async")
    check("3.1 保留装饰器", "@property" in out)
    check("3.2 保留 async", "async def fetch" in out)

    # ---- 测试 4: JavaScript (正则 fallback) ----
    js_code = '''
// 这是注释
function foo(x) {
    // 内部注释
    const a = 1;
    return a + x;
}

/* 块注释 */
const bar = 42;
'''
    out, stats = cc.compress(js_code)
    print(f"\n[测试 4] JavaScript 正则压缩")
    check("4.1 注释被移除", "这是注释" not in out)
    check("4.2 块注释被移除", "块注释" not in out)
    check("4.3 保留 function", "function foo" in out)

    # ---- 测试 5: 非代码 passthrough ----
    out, stats = cc.compress("hello world this is just text\nnothing here\n")
    print(f"\n[测试 5] 非代码 passthrough")
    check("5.1 is_code=False", stats["is_code"] is False)
    check("5.2 mode=passthrough", stats["mode"] == "passthrough")

    # ---- 测试 6: 错误输入 (语法错误) 走 fail-safe ----
    # 多关键词, 超过 min_code_size, 强制走 AST 路径并报错
    bad_code = "def broken(:\n" + "    pass\n" * 20 + "\n"
    out, stats = cc.compress(bad_code)
    print(f"\n[测试 6] 语法错误 fail-safe")
    print(f"  mode={stats['mode']}, is_code={stats['is_code']}")
    check("6.1 不崩溃", stats["mode"] in ("error", "passthrough"))
    check("6.2 返回原文 (fail-safe)", "broken" in out)

    # ---- 测试 7: 小代码 passthrough ----
    small = "def f(): pass\n"
    out, stats = cc.compress(small)
    print(f"\n[测试 7] 小代码 passthrough")
    check("7.1 mode=passthrough", stats["mode"] == "passthrough")

    # ---- 测试 8: 空内容 ----
    out, stats = cc.compress("")
    check("8.1 空内容 ratio=0", stats["ratio"] == 0.0)

    print()
    print("=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_tests() else 1)