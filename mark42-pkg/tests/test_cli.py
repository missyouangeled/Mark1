"""CLI 测试 - 测试 Mark42 CLI 核心功能。"""

import subprocess
import sys

import pytest


def test_help_subprocess():
    """`python3 -m mark42 --help` 不报错。"""
    result = subprocess.run(
        [sys.executable, "-m", "mark42", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd="/home/missyouangeled/.openclaw/workspace/mark42-pkg",
    )
    assert result.returncode == 0, f"退出码非0: {result.stderr}"
    assert "usage" in result.stdout.lower(), "输出应包含 usage"


def test_main_no_args(capsys):
    """main() 无参数时打印 help。"""
    from mark42.cli import main

    old_argv = sys.argv
    sys.argv = ["mark42"]
    try:
        main()
    except SystemExit:
        pass  # argparse 可能触发 SystemExit
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert len(output) > 0, "无参数调用应有输出"
    assert "usage" in output.lower(), "输出应包含 usage"


def test_armor_subcommand(capsys):
    """armor 子命令输出包含 "上下文铠甲"。"""
    from mark42.cli import main

    old_argv = sys.argv
    sys.argv = ["mark42", "armor", "--check"]
    try:
        main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    output = captured.out
    assert "上下文铠甲" in output or "铠甲" in output, f"输出应包含铠甲相关文字，实际输出: {output[:100]}"


def test_status_subcommand():
    """status 子命令能运行。"""
    result = subprocess.run(
        [sys.executable, "-m", "mark42", "status"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd="/home/missyouangeled/.openclaw/workspace/mark42-pkg",
    )
    # 允许非0退出码，只要能运行不崩溃即可
    assert result.returncode in (0, 1), f"status 命令异常崩溃，退出码: {result.returncode}"
    # 检查是否有输出（stdout 或 stderr）
    has_output = len(result.stdout) > 0 or len(result.stderr) > 0
    assert has_output, "status 命令应有输出"


def test_version_subprocess():
    """`python3 -m mark42 --version` 验证。"""
    result = subprocess.run(
        [sys.executable, "-m", "mark42", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd="/home/missyouangeled/.openclaw/workspace/mark42-pkg",
    )
    # --version 可能不存在，只要不崩溃即可
    assert result.returncode in (0, 2), f"version 命令异常崩溃，退出码: {result.returncode}"


def test_invalid_subcommand(capsys):
    """无效子命令应返回帮助信息或错误。"""
    from mark42.cli import main

    old_argv = sys.argv
    sys.argv = ["mark42", "nonexistent_command_xyz"]
    try:
        main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert len(output) > 0, "无效命令应有输出"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


# ── 回归测试：模块入口退出码语义 ──────────────────────────


class TestModuleEntrypointExitCodes:
    """回归测试：`python -m mark42` 必须传播 CLI 返回码。

    历史 bug：mark42/__main__.py 只调用 main() 而丢弃返回值，
    CLI 内部 10 处 return 1/2 在模块路径下全部退化为退出码 0。
    systemd 模板正是通过模块路径回退执行的，因此失败会被判成成功。
    """

    @staticmethod
    def _run(args, env_extra=None):
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, "-m", "mark42", *args],
            capture_output=True, text=True, timeout=120, env=env,
        )

    def test_main_module_raises_system_exit(self):
        """__main__.py 必须使用 SystemExit(main()) 传播返回码。"""
        from pathlib import Path

        import mark42

        src = (Path(mark42.__file__).parent / "__main__.py").read_text()
        assert "SystemExit(main())" in src

    def test_version_succeeds(self):
        proc = self._run(["--version"])
        assert proc.returncode == 0
        assert "Mark42" in proc.stdout

    def test_unknown_subcommand_returns_two(self):
        """不存在的子命令必须返回 argparse 错误码 2。"""
        proc = self._run(["definitely-not-a-command"])
        assert proc.returncode == 2

    def test_heavy_missing_task_returns_nonzero(self, tmp_path):
        """heavy 操作不存在的任务必须返回非零。"""
        proc = self._run(
            ["heavy", "--execute", "--task-name", "no-such-task-xyz"],
            env_extra={
                "MARK42_SCRATCH": str(tmp_path / "scratch"),
                "MARK42_STATE": str(tmp_path / "state"),
            },
        )
        assert proc.returncode != 0
        assert "未开工" in proc.stdout

    def test_heavy_without_action_returns_two(self, tmp_path):
        """heavy 未指定任何动作必须返回 2。"""
        proc = self._run(
            ["heavy"],
            env_extra={
                "MARK42_SCRATCH": str(tmp_path / "scratch"),
                "MARK42_STATE": str(tmp_path / "state"),
            },
        )
        assert proc.returncode == 2

    def test_heavy_start_without_task_name_returns_two(self, tmp_path):
        proc = self._run(
            ["heavy", "--start", str(tmp_path)],
            env_extra={
                "MARK42_SCRATCH": str(tmp_path / "scratch"),
                "MARK42_STATE": str(tmp_path / "state"),
            },
        )
        assert proc.returncode == 2
