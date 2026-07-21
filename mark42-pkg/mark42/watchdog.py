"""Mark42 Watchdog - 检查 daemon 存活并自动重启。

由 mark42-watchdog.timer 每 2 分钟触发一次。
行为：
  1. 检查 daemon-heartbeat.json 的 lastTick 是否超时
  2. 检查 mark42-engine-daemon / mark42-armor-guard 进程是否存在
  3. 如果心跳超时或进程死了 -> restart service
  4. 都正常 -> 静默退出

原 shell 脚本: tools/mark42-watchdog/mark42-watchdog.sh
Python 重写: 2026-07-20 (pip 化后 shell 脚本不再使用)
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _log(msg: str, logfile: str | Path) -> None:
    """写入日志文件（追加模式）。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        import logging
        logging.debug("watchdog 日志写入失败", exc_info=True)  # 日志写入失败不影响主流程


def _check_heartbeat(heartbeat_path: Path, warn_threshold: int = 300) -> tuple[bool, str]:
    """检查心跳文件。返回 (ok, reason)。"""
    if not heartbeat_path.exists():
        return False, "心跳文件不存在"
    try:
        data = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        last_str = data.get("lastTick", "")
        if not last_str:
            return False, "心跳文件无 lastTick 字段"
        # 解析 ISO 时间
        last = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last).total_seconds()
        if age > warn_threshold:
            return False, f"心跳超时 {int(age)}s (>{warn_threshold}s)"
        return True, ""
    except Exception as e:
        return False, f"心跳文件不可解析: {e}"


def _check_process(pattern: str) -> bool:
    """检查进程是否存在。"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def _restart_service(svc_name: str, logfile: str | Path) -> None:
    """重启 systemd 用户服务。"""
    _log(f"  重启 {svc_name} ...", logfile)
    result = subprocess.run(
        ["systemctl", "--user", "restart", svc_name],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        _log(f"  {svc_name} 重启失败: {result.stderr.strip()[:200]}", logfile)


def watchdog_check() -> None:
    """执行一次 watchdog 检查。"""
    # 路径
    xdg_state = _get_env("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    state_dir = _get_env("MARK42_STATE_DIR", f"{xdg_state}/openclaw/mark42")
    log_dir = _get_env("MARK42_LOG_DIR", f"{state_dir}/logs")
    logfile = Path(log_dir) / "watchdog.log"

    heartbeat = Path(
        _get_env(
            "HEARTBEAT",
            f"{state_dir}/engine/daemon-heartbeat.json",
        )
    )

    warn_threshold = 300  # 5 分钟心跳超时

    # ── 1. 心跳检查 ──
    hb_ok, reason = _check_heartbeat(heartbeat, warn_threshold)

    # ── 2. 进程检查 ──
    engine_alive = _check_process("mark42.*engine --daemon")
    armor_alive = _check_process("mark42.*armor --guard")

    # ── 3. 处置 ──
    need_restart = False
    reasons = []

    if not hb_ok:
        need_restart = True
        reasons.append(reason)

    if not engine_alive:
        need_restart = True
        reasons.append("engine-daemon 进程不在")

    if not armor_alive:
        need_restart = True
        reasons.append("armor-guard 进程不在")

    if need_restart:
        msg = f"⚠️ 检测到异常: {'; '.join(reasons)} -> 重启 service"
        _log(msg, logfile)

        if not engine_alive:
            _restart_service("mark42-engine-daemon.service", logfile)
        if not armor_alive:
            _restart_service("mark42-armor-guard.service", logfile)

        # 等待 5 秒后验证
        time.sleep(5)

        new_engine = _check_process("mark42.*engine --daemon")
        new_armor = _check_process("mark42.*armor --guard")

        if new_engine and new_armor:
            _log("✅ 重启成功", logfile)
        else:
            _log(
                f"❌ 重启后仍有进程缺失: engine={'✅' if new_engine else '❌'}, armor={'✅' if new_armor else '❌'}",
                logfile,
            )
    # 正常情况静默退出（避免日志爆量）


if __name__ == "__main__":
    watchdog_check()
