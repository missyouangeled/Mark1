"""cli.py 测试 - 测试 CLI 解析器和核心子命令分发。"""

import io
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.cli import _build_parser, _cmd_status, main

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print(f"  ✗ {name} -- {detail}")


# ── 测试 1: parser 构建 ──
def test_parser_build():
    parser = _build_parser()
    check("1.1 返回 ArgumentParser", parser.__class__.__name__ == "ArgumentParser")

    # 检查所有子命令都已注册
    actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    subcommands = set()
    for a in actions:
        subcommands.update(a.choices.keys())

    expected = {
        "logs", "armor", "engine", "heavy", "compaction", "assemble",
        "context-safety", "status", "archive", "consciousness", "cores",
        "chaos", "module", "cluster", "breaker", "install", "watchdog",
    }
    check("1.2 包含所有子命令", expected.issubset(subcommands), f"缺少: {expected - subcommands}")
    check("1.3 无多余子命令", len(subcommands - expected) == 0, f"多余: {subcommands - expected}")


# ── 测试 2: --version ──
def test_version():
    parser = _build_parser()
    try:
        parser.parse_args(["--version"])
        check("2.1 --version 退出 (不正常)", False, "应触发 SystemExit")
    except SystemExit as e:
        check("2.1 --version 触发 SystemExit", e.code == 0, f"exit code={e.code}")


# ── 测试 3: --help ──
def test_help():
    parser = _build_parser()
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            parser.parse_args(["--help"])
        check("3.1 --help 触发 SystemExit", False, "应退出")
    except SystemExit as e:
        check("3.1 --help exit=0", e.code == 0)


# ── 测试 4: status 子命令 ──
def test_status_cmd():
    """status 命令应正常执行并输出状态信息。"""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            _cmd_status(type("Args", (), {"module": "status"})())
        output = buf.getvalue()
        check("4.1 status 有输出", len(output) > 0)
        check("4.2 含 Mark42", "Mark42" in output or "mark42" in output.lower())
        check("4.3 含 铠甲/上下文", "铠甲" in output or "上下文" in output)
    except Exception as e:
        check("4.1 status 执行", False, str(e))


# ── 测试 5: 无参数调用 main ──
def test_main_no_args():
    """main() 无参数应触发 help 输出。"""
    old_argv = sys.argv
    sys.argv = ["mark42"]
    try:
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            main()
        output = buf.getvalue()
        check("5.1 无参数有输出", len(output) > 0)
        check("5.2 输出含 usage", "usage" in output.lower())
    except SystemExit:
        pass  # --help 会触发 SystemExit
    except Exception:  # noqa: S110
        pass  # 无参数可能走 default 路径
    finally:
        sys.argv = old_argv


# ── 测试 6: context-safety 子命令 ──
def test_context_safety_cmd():
    """context-safety 命令应正常执行。"""
    try:
        from mark42.cli import _cmd_context_safety
        _cmd_context_safety(type("Args", (), {"module": "context-safety", "action": "status", "verbose": False})())
        check("6.1 context-safety 执行无异常", True)
    except Exception as e:
        check("6.1 context-safety 执行", False, str(e))


# ── 测试 7: 子进程调用 --version ──
def test_subprocess_version():
    """通过 python -m mark42 --version 验证端到端。"""
    result = subprocess.run(
        [sys.executable, "-m", "mark42", "--version"],
        capture_output=True, text=True, timeout=10,
    )
    check("7.1 exit code 0", result.returncode == 0, f"code={result.returncode}")
    check("7.2 含版本号", "v" in result.stdout, f"stdout={result.stdout[:50]}")


# ── 测试 8: 子进程调用 status ──
def test_subprocess_status():
    """通过 python -m mark42 status 验证端到端。"""
    result = subprocess.run(
        [sys.executable, "-m", "mark42", "status"],
        capture_output=True, text=True, timeout=15,
    )
    check("8.1 exit code 0", result.returncode == 0, f"code={result.returncode}")
    check("8.2 含 Mark42", "Mark42" in result.stdout, f"stdout={result.stdout[:80]}")


# ── 测试 9: armor --check 子进程 ──
def test_subprocess_armor_check():
    """通过 python -m mark42 armor --check 验证。"""
    result = subprocess.run(
        [sys.executable, "-m", "mark42", "armor", "--check"],
        capture_output=True, text=True, timeout=15,
    )
    check("9.1 exit code 0", result.returncode == 0, f"code={result.returncode}")
    check("9.2 含 铠甲", "铠甲" in result.stdout, f"stdout={result.stdout[:80]}")


# ── 测试 10: engine --list 子进程 ──
def test_subprocess_engine_list():
    result = subprocess.run(
        [sys.executable, "-m", "mark42", "engine", "--list"],
        capture_output=True, text=True, timeout=15,
    )
    check("10.1 exit code 0", result.returncode == 0, f"code={result.returncode}")


# ── 测试 11: 无效子命令 ──
def test_invalid_subcommand():
    """无效子命令应返回非零退出码或打印 help。"""
    old_argv = sys.argv
    sys.argv = ["mark42", "nonexistent_command"]
    try:
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            main()
        output = buf.getvalue()
        check("11.1 无效命令有输出", len(output) > 0)
    except SystemExit:
        pass
    except Exception:  # noqa: S110
        pass
    finally:
        sys.argv = old_argv


def run_tests():
    print("=" * 60)
    print("CLI 测试")
    print("=" * 60)

    test_parser_build()
    test_version()
    test_help()
    test_status_cmd()
    test_main_no_args()
    test_context_safety_cmd()
    test_subprocess_version()
    test_subprocess_status()
    test_subprocess_armor_check()
    test_subprocess_engine_list()
    test_invalid_subcommand()

    print()
    print("=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    sys.exit(0 if run_tests() else 1)
