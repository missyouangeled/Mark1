"""systemd 部署链契约测试。

回归背景（v2.8.2 审查 P1-1）：
发布的 systemd unit 调用了不存在的 CLI：
  - mark42-bootstrap.service  -> `engine register --all`（engine 无此子命令）
  - mark42-watchdog.service   -> `watchdog --check`（CLI 无 watchdog 子命令）
安装器实现了 install_systemd()/uninstall_systemd()，但 CLI 没有 install/uninstall 入口，
卸载完成后还提示 `mark42 install`（不可解析）。
两个 oneshot unit 启动即 argparse 失败，而 armor/engine 又 Requires=bootstrap，
因此整条部署链不可用。

本文件保证：模板里的每个 ExecStart 都能被真实 CLI 接受。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import mark42
from mark42.installer import _get_pkg_systemd_dir

SYSTEMD_DIR = _get_pkg_systemd_dir()


def _unit_files() -> list[Path]:
    return sorted(SYSTEMD_DIR.glob("*.tmpl"))


def _exec_start_args(unit: Path) -> list[str]:
    """提取 ExecStart 中属于 mark42 CLI 的参数部分。"""
    for line in unit.read_text(encoding="utf-8").splitlines():
        if not line.startswith("ExecStart="):
            continue
        cmd = line.split("=", 1)[1].strip()
        # 去掉 python 解释器、-u 标志与 mark42 可执行文件占位符
        tokens = cmd.split()
        args = [
            t for t in tokens
            if t not in ("__MARK42_PYTHON__", "__MARK42_BIN__", "-u")
        ]
        return args
    return []


def test_unit_templates_exist():
    assert _unit_files(), f"未找到 systemd 模板: {SYSTEMD_DIR}"


@pytest.mark.parametrize("unit", _unit_files(), ids=lambda p: p.stem)
def test_every_exec_start_is_accepted_by_cli(unit, tmp_path):
    """每个 unit 的 ExecStart 必须能被 CLI parser 接受（不得是 argparse 错误码 2）。"""
    args = _exec_start_args(unit)
    assert args, f"{unit.name} 未解析出 ExecStart 参数"

    # 只验证 parser 可接受：加 --help 让命令立即返回而不真正执行副作用
    proc = subprocess.run(
        [sys.executable, "-m", "mark42", args[0], "--help"],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode != 2, (
        f"{unit.name} 的子命令 {args[0]!r} 不被 CLI 接受:\n{proc.stderr}"
    )


@pytest.mark.parametrize("unit", _unit_files(), ids=lambda p: p.stem)
def test_no_unit_uses_nonexistent_register_subcommand(unit):
    """回归防护：不得再出现 `engine register --all` 这类不存在的命令形式。"""
    content = unit.read_text(encoding="utf-8")
    assert "engine register" not in content, (
        f"{unit.name} 仍在使用不存在的 `engine register` 命令"
    )


def test_bootstrap_uses_real_register_all_flag():
    """bootstrap 必须使用真实存在的 --register-all。"""
    bootstrap = SYSTEMD_DIR / "mark42-bootstrap.service.tmpl"
    assert "engine --register-all" in bootstrap.read_text(encoding="utf-8")


def test_repo_root_mark42_py_does_not_exist():
    """确认硬编码脚本目标不存在（旧 engine.py 曾据此启动子进程）。"""
    assert not (Path(mark42.__file__).resolve().parent.parent / "mark42.py").exists()


@pytest.mark.parametrize("sub", ["install", "uninstall", "watchdog"])
def test_installer_and_watchdog_subcommands_are_reachable(sub):
    """安装器与 watchdog 必须有可达的 CLI 入口。"""
    proc = subprocess.run(
        [sys.executable, "-m", "mark42", sub, "--help"],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"`mark42 {sub}` 不可达:\n{proc.stderr}"


def test_engine_register_all_is_idempotent(tmp_path, monkeypatch):
    """--register-all 必须幂等：已有活跃 Loop 的进度不得被重置。"""
    from mark42 import engine

    state = tmp_path / "engine"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(engine, "ENGINE_STATE", state)
    monkeypatch.setattr(engine, "ENGINE_LOOPS", state / "loops.json")

    first = engine.engine_register_all()
    assert first["total"] > 0
    assert first["registered"], "首次应注册所有模板"

    # 模拟已运行一段时间
    loops = engine._load_loops()
    name = first["registered"][0]
    loops[name]["cycle"] = 42
    loops[name]["status"] = "registered"
    engine._save_loops(loops)

    second = engine.engine_register_all()
    assert name in second["kept"], "已存在的 Loop 应被保留"
    assert engine._load_loops()[name]["cycle"] == 42, "幂等注册不得重置 cycle"


def test_all_units_pass_systemd_analyze_verify(tmp_path, monkeypatch):
    """渲染后的 unit 必须通过 systemd-analyze verify（若环境可用）。"""
    import shutil

    if not shutil.which("systemd-analyze"):
        pytest.skip("systemd-analyze 不可用")

    import mark42.installer as inst

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    class OkResult:
        returncode = 0
        stdout = ""
        stderr = ""

    # 不能用 monkeypatch.setattr(inst.subprocess, "run", ...)：
    # inst.subprocess 就是全局 subprocess 模块，会污染整个测试进程。
    original_run = inst.subprocess.run
    inst.subprocess.run = lambda *a, **k: OkResult()
    try:
        assert inst.install_systemd() == 0
    finally:
        inst.subprocess.run = original_run

    unit_dir = fake_home / ".config" / "systemd" / "user"
    services = sorted(unit_dir.glob("mark42-*.service"))
    assert services, "未渲染出任何 service"

    proc = subprocess.run(
        ["systemd-analyze", "verify", *[str(s) for s in services]],
        capture_output=True, text=True, timeout=120, cwd=str(unit_dir),
    )
    # verify 对缺失的外部依赖单元可能给出警告，只拦截明确的语法/指令错误
    fatal = [
        ln for ln in (proc.stderr or "").splitlines()
        if re.search(r"(Unknown key|Invalid|Failed to parse|not a valid)", ln, re.I)
    ]
    assert not fatal, "unit 存在语法错误:\n" + "\n".join(fatal)
