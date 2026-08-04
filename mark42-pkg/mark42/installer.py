"""Mark42 安装器：渲染 systemd 服务并安装/卸载。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _find_openclaw() -> str | None:
    """查找 openclaw CLI 路径。"""
    path = shutil.which("openclaw")
    if path:
        return path
    for candidate in [
        Path.home() / ".npm-global" / "bin" / "openclaw",
        Path("/usr/local/bin/openclaw"),
        Path("/usr/bin/openclaw"),
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def _get_pkg_systemd_dir() -> Path:
    """获取包内 systemd 模板目录。"""
    import mark42

    pkg_dir = Path(mark42.__file__).parent
    return pkg_dir / "systemd"


def _is_mark42_unit(path: Path) -> bool:
    """判断目标 unit 是否属于 Mark42。

    判据（任一成立即认为属于 Mark42）：
      1. 文件名以 mark42- 开头（安装器只使用这组固定名称）；
      2. 文件内容提到 mark42。
    两者都不成立时视为第三方同名文件，不得静默删除。
    """
    if path.name.startswith("mark42-"):
        return True
    try:
        return "mark42" in path.read_text(encoding="utf-8").lower()
    except Exception:
        return False


def _backup_existing_unit(target: Path) -> Path | None:
    """覆写前备份已存在的 unit，避免静默丢弃用户自定义配置。"""
    if not target.exists():
        return None
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"{target.name}.bak-{stamp}")
    try:
        shutil.copy2(target, backup)
    except Exception as e:
        print(f"  ⚠️ 无法备份 {target.name}: {e}")
        return None
    if not _is_mark42_unit(target):
        print(f"  ⚠️ {target.name} 不像是 Mark42 创建的 unit，已备份到 {backup.name}")
    return backup


def install_systemd(workspace: str = "") -> int:
    """渲染 systemd 模板并安装到用户服务目录。

    Returns:
        0 = 全部步骤成功；非 0 = 有步骤失败（不得再宣告安装完成）。
    """
    print("📦 Mark42 systemd 服务安装")

    # 前置检查
    if not shutil.which("systemctl"):
        print("❌ 未检测到 systemctl，无法安装 systemd 服务")
        sys.exit(1)

    openclaw_bin = _find_openclaw()
    if not openclaw_bin:
        print("⚠️ 未找到 openclaw CLI，服务仍会安装但运行时需要 openclaw 可用")
        openclaw_bin = "openclaw"

    # 路径变量
    python_bin = sys.executable
    home = Path.home()
    ws = workspace or os.environ.get("MARK42_WORKSPACE", str(home / ".openclaw" / "workspace"))
    xdg_state = os.environ.get("XDG_STATE_HOME", str(home / ".local" / "state"))
    state_dir = f"{xdg_state}/openclaw/mark42"
    log_dir = f"{state_dir}/logs"

    # scratch 路径 - 使用环境变量或 XDG 回退，不硬编码 /mnt/data
    scratch = os.environ.get("MARK42_SCRATCH", str(Path(xdg_state) / "openclaw" / "scratch"))

    # mark42 命令路径
    mark42_bin = shutil.which("mark42") or str(home / ".local" / "bin" / "mark42")
    if not Path(mark42_bin).exists():
        # 用 python -m mark42 回退
        mark42_bin = f"{python_bin} -m mark42"

    systemd_dir = home / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    # 创建日志和 scratch 目录
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    Path(scratch).mkdir(parents=True, exist_ok=True)

    # 渲染模板
    tmpl_dir = _get_pkg_systemd_dir()
    if not tmpl_dir.exists():
        print(f"❌ 找不到 systemd 模板目录: {tmpl_dir}")
        sys.exit(1)

    replacements = {
        "__MARK42_BIN__": mark42_bin,
        "__MARK42_PYTHON__": python_bin,
        "__MARK42_WORKSPACE__": ws,
        "__MARK42_XDG_STATE__": xdg_state,
        "__MARK42_STATE_DIR__": state_dir,
        "__MARK42_LOG_DIR__": log_dir,
        "__MARK42_SCRATCH__": scratch,
    }

    installed = []
    for tmpl in sorted(tmpl_dir.glob("*.tmpl")):
        content = tmpl.read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)

        svc_name = tmpl.stem  # e.g. mark42-armor-guard.service
        target = systemd_dir / svc_name
        _backup_existing_unit(target)
        target.write_text(content, encoding="utf-8")
        print(f"  ✅ {svc_name}")
        installed.append(svc_name)

    # watchdog timer（直接复制）
    timer_src = tmpl_dir / "mark42-watchdog.timer"
    if timer_src.exists():
        timer_target = systemd_dir / "mark42-watchdog.timer"
        _backup_existing_unit(timer_target)
        shutil.copy(timer_src, timer_target)
        print("  ✅ mark42-watchdog.timer")
        # timer 也必须纳入 enable 清单，否则只有文件不会随 session 启用
        installed.append("mark42-watchdog.timer")

    # daemon-reload + enable（每一步都必须检查返回码）
    failures: list[str] = []

    reload_proc = subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        capture_output=True, text=True, check=False,
    )
    if reload_proc.returncode != 0:
        failures.append(f"daemon-reload: {reload_proc.stderr.strip()[:200]}")

    enabled = []
    for svc in installed:
        proc = subprocess.run(
            ["systemctl", "--user", "enable", svc],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            failures.append(f"enable {svc}: {proc.stderr.strip()[:200]}")
        else:
            enabled.append(svc)

    print()
    if failures:
        # 安装状态不得误报：systemctl 失败时绝不能输出“安装完成”
        print("❌ 安装未完全成功，以下步骤失败：")
        for f in failures:
            print(f"   • {f}")
        if enabled:
            print()
            print("已成功启用：")
            for svc in enabled:
                print(f"   • {svc}")
        print()
        print("请修正上述问题后重新执行安装。")
        return 1

    print("✅ 安装完成！已启用以下服务：")
    for svc in enabled:
        print(f"   • {svc}")
    print()
    print("启动服务：")
    print("  systemctl --user start mark42-bootstrap")
    print("  systemctl --user start mark42-armor-guard")
    print("  systemctl --user start mark42-engine-daemon")
    print()
    print("验证：")
    print("  mark42 status")
    return 0


def uninstall_systemd() -> int:
    """卸载 systemd 服务。

    Returns:
        0 = 成功；非 0 = 有步骤失败。
    """
    print("🗑️ 卸载 Mark42 systemd 服务")

    systemd_dir = Path.home() / ".config" / "systemd" / "user"

    services = [
        "mark42-armor-guard.service",
        "mark42-engine-daemon.service",
        "mark42-bootstrap.service",
        "mark42-watchdog.service",
        "mark42-watchdog.timer",
    ]

    failures: list[str] = []

    # stop + disable
    for svc in services:
        subprocess.run(["systemctl", "--user", "stop", svc], capture_output=True, check=False)
        subprocess.run(["systemctl", "--user", "disable", svc], capture_output=True, check=False)

    # 删除文件（只删 Mark42 自己的 unit，不误删同名用户文件）
    for svc in services:
        f = systemd_dir / svc
        if not f.exists():
            continue
        if not _is_mark42_unit(f):
            print(f"  ⚠️ 跳过 {svc}：不像是 Mark42 创建的 unit，为安全不删除")
            continue
        _backup_existing_unit(f)
        try:
            f.unlink()
            print(f"  🗑️ {svc}")
        except Exception as e:
            failures.append(f"删除 {svc}: {e}")

    reload_proc = subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        capture_output=True, text=True, check=False,
    )
    if reload_proc.returncode != 0:
        failures.append(f"daemon-reload: {reload_proc.stderr.strip()[:200]}")

    print()
    if failures:
        print("❌ 卸载未完全成功：")
        for f in failures:
            print(f"   • {f}")
        return 1

    print("✅ 卸载完成")
    print("如需重新安装：mark42 install")
    return 0
