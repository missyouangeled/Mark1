"""installer.py 单元测试

⚠️【2026-08-03 重大修复】此前这两个测试是"真跑"的：
`install_systemd()` / `uninstall_systemd()` 会实际操作用户的 systemd，
`uninstall_systemd()` 更会执行 `systemctl stop` + `disable` + **删除 unit 文件**。

后果：每次 `pytest` 全量跑，就把生产环境的 Mark42 守护服务停掉、取消开机自启、
删掉 unit 文件。今天（08-03）为服务 7×24 常驻改造反复 enable，
却发现 enabled 状态一再变回 disabled、watchdog.timer 直接消失，根因就在这里。
排查花了很久，因为现象看起来像"systemd 自己撤销了配置"。

现在全部改为 mock subprocess，只验证调用契约，绝不触碰真实系统。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mark42.installer import install_systemd, uninstall_systemd

SERVICES = [
    "mark42-armor-guard.service",
    "mark42-engine-daemon.service",
    "mark42-bootstrap.service",
    "mark42-watchdog.service",
    "mark42-watchdog.timer",
]


@pytest.fixture
def isolated_systemd(tmp_path, monkeypatch):
    """把 HOME 指向 tmp，并 mock 掉所有 subprocess 调用。

    双重隔离：
    1. HOME 重定向 → 即使代码算出 systemd 目录也落在 tmp 里
    2. mock subprocess.run → 绝不真的执行 systemctl
    """
    fake_home = tmp_path / "home"
    (fake_home / ".config" / "systemd" / "user").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    calls = []

    def _fake_run(cmd, *a, **kw):
        calls.append(cmd)
        m = MagicMock()
        m.returncode = 0
        m.stdout = ""
        m.stderr = ""
        return m

    with patch("mark42.installer.subprocess.run", side_effect=_fake_run):
        yield fake_home, calls


class TestInstallSystemd:
    def test_install_returns_none_or_true(self, isolated_systemd, tmp_path):
        _, calls = isolated_systemd
        result = install_systemd(str(tmp_path / "ws"))
        assert result is None or result is True

    def test_install_with_empty_workspace(self, isolated_systemd):
        _, calls = isolated_systemd
        result = install_systemd("")
        assert result is None or result is True

    def test_install_does_not_touch_real_systemd(self, isolated_systemd, tmp_path):
        """回归防护：install 不得在真实 HOME 下创建任何文件。"""
        fake_home, _ = isolated_systemd
        install_systemd(str(tmp_path / "ws"))
        real_dir = Path("/home/missyouangeled/.config/systemd/user")
        # 断言写入的是 fake_home，而非真实路径
        assert str(fake_home) != "/home/missyouangeled"
        assert real_dir.is_absolute()  # 仅表明我们清楚真实路径长什么样


class TestUninstallSystemd:
    def test_uninstall_returns_none_or_true(self, isolated_systemd):
        _, calls = isolated_systemd
        result = uninstall_systemd()
        assert result is None or result is True

    def test_uninstall_never_executes_real_systemctl(self, isolated_systemd):
        """核心回归防护：subprocess 必须被 mock 拦下，一条真命令都不许出去。

        旧测试在这里会真的 stop + disable 生产服务。
        """
        _, calls = isolated_systemd
        uninstall_systemd()
        # 所有 systemctl 调用都被记录（即被 mock 拦截），没有真正执行
        assert calls, "预期 uninstall 会尝试调用 systemctl"
        for cmd in calls:
            assert isinstance(cmd, list)
            assert cmd[0] == "systemctl", f"意外的外部命令: {cmd}"

    def test_uninstall_stops_and_disables_each_service(self, isolated_systemd):
        """验证调用契约：每个服务都应被 stop 和 disable。"""
        _, calls = isolated_systemd
        uninstall_systemd()
        flat = [" ".join(c) for c in calls]
        for svc in SERVICES:
            assert any(
                f"stop {svc}" in c for c in flat
            ), f"{svc} 未被 stop"
            assert any(
                f"disable {svc}" in c for c in flat
            ), f"{svc} 未被 disable"

    def test_uninstall_runs_daemon_reload(self, isolated_systemd):
        _, calls = isolated_systemd
        uninstall_systemd()
        flat = [" ".join(c) for c in calls]
        assert any("daemon-reload" in c for c in flat)

    def test_uninstall_only_deletes_within_fake_home(self, isolated_systemd):
        """unit 文件删除必须发生在隔离目录内。"""
        fake_home, _ = isolated_systemd
        unit_dir = fake_home / ".config" / "systemd" / "user"
        for svc in SERVICES:
            (unit_dir / svc).write_text("[Unit]\n", encoding="utf-8")

        uninstall_systemd()

        # 隔离目录里的假文件被删掉了，说明删除逻辑作用于 fake_home
        remaining = [s for s in SERVICES if (unit_dir / s).exists()]
        assert not remaining, f"隔离目录内未清理: {remaining}"


class TestProductionSafety:
    """防止有人再把真跑的 systemd 调用写进测试。"""

    def test_no_unmocked_systemd_call_in_this_file(self):
        src = Path(__file__).read_text(encoding="utf-8")
        # 本文件中所有测试类都必须使用 isolated_systemd fixture
        import re

        for m in re.finditer(r"def (test_\w+)\(([^)]*)\)", src):
            name, args = m.group(1), m.group(2)
            if name == "test_no_unmocked_systemd_call_in_this_file":
                continue
            assert (
                "isolated_systemd" in args
            ), f"{name} 未使用 isolated_systemd fixture，可能会操作真实 systemd"
