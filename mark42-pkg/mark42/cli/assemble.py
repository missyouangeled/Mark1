"""Mark42 CLI - assemble 模块。

包含 assemble 启动/停止/重启/监控相关的全部函数。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..log_setup import get_logger
from ..output_guard import trim_summary

logger = get_logger(__name__)


def _trim_daemon_logs(log_dir: Path) -> None:
    """检查 daemon 日志大小：单个文件超限则截尾保留最新部分。"""
    from ..config import MAX_DAEMON_LOG_LINES, MAX_DAEMON_LOG_MB

    max_bytes = MAX_DAEMON_LOG_MB * 1024 * 1024
    for fpath in sorted(log_dir.glob("*.log")):
        try:
            size = fpath.stat().st_size
            if size <= max_bytes:
                continue
            with open(fpath) as f:
                lines = f.readlines()
            keep = min(MAX_DAEMON_LOG_LINES // 2, len(lines) // 2)
            with open(fpath, "w") as f:
                f.writelines(lines[-keep:])
            logger.info(f"🧹 截尾 {fpath.name}: {size / 1024 / 1024:.1f}MB -> {keep} 行")
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    """检查 PID 是否存活。"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _find_mark42_processes() -> dict[str, Any]:
    """兜底扫描 Mark42 守护相关进程。"""
    result: dict[str, Any] = {"parent": None, "children": []}
    try:
        out = subprocess.check_output(
            [
                "bash",
                "-c",
                "ps -eo pid=,ppid=,args= | grep -E 'mark42.py (assemble|armor --guard|engine --daemon)' | grep -v grep",
            ],
            text=True,
        )
    except Exception:
        return result

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid = int(parts[0])
        ppid = int(parts[1])
        args = parts[2]
        if (
            "mark42.py assemble" in args
            and "assemble --stop" not in args
            and "assemble --status" not in args
            and "assemble --restart" not in args
        ):
            result["parent"] = {"name": "assemble", "pid": pid, "ppid": ppid, "alive": True}
        elif "mark42.py armor --guard" in args:
            result["children"].append({"name": "armor-guard", "pid": pid, "ppid": ppid, "alive": True})
        elif "mark42.py engine --daemon" in args:
            result["children"].append({"name": "engine-daemon", "pid": pid, "ppid": ppid, "alive": True})
    return result


def assemble_status() -> dict[str, Any]:
    """查看 assemble / armor-guard / engine-daemon 当前状态。"""
    from ..config import ARMOR_STATE
    from ..utils import _load_json

    pid_file = ARMOR_STATE / "assemble.pids"
    data = _load_json(pid_file) if pid_file.exists() else {}
    parent = data.get("parent") or {}
    children = data.get("children") or []

    result = {
        "pidFile": str(pid_file),
        "pidFileExists": pid_file.exists(),
        "parent": {
            "name": parent.get("name", "assemble"),
            "pid": parent.get("pid"),
            "alive": _pid_alive(parent.get("pid")) if parent.get("pid") else False,
        },
        "children": [
            {
                "name": c.get("name"),
                "pid": c.get("pid"),
                "alive": _pid_alive(c.get("pid")) if c.get("pid") else False,
            }
            for c in children
        ],
    }

    if (not result["parent"]["pid"] and not result["children"]) or (
        not result["parent"]["alive"] and not any(c["alive"] for c in result["children"])
    ):
        scanned = _find_mark42_processes()
        if scanned.get("parent"):
            result["parent"] = scanned["parent"]
        if scanned.get("children"):
            result["children"] = scanned["children"]

    print("🦾 Mark42 assemble 状态")
    print(f"   PID 文件: {result['pidFile']} ({'存在' if result['pidFileExists'] else '不存在'})")
    p = result["parent"]
    print(f"   父进程: {p['name']} pid={p['pid']} alive={p['alive']}")
    if result["children"]:
        for c in result["children"]:
            print(f"   子进程: {c['name']} pid={c['pid']} alive={c['alive']}")
    else:
        print("   子进程: 无记录")

    return result


def _stop_process(pid: int, name: str, timeout_s: float = 8.0) -> bool:
    """停止指定进程：先 SIGTERM，超时后 SIGKILL。返回是否成功停止。"""
    if not _pid_alive(pid):
        return False
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout_s
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.2)
    if _pid_alive(pid):
        os.kill(pid, signal.SIGKILL)
    return True


def _load_assemble_pids() -> tuple[dict, list, Path]:
    """加载 assemble PID 文件，返回 (parent, children, pid_file)。"""
    from ..config import ARMOR_STATE
    from ..utils import _load_json

    pid_file = ARMOR_STATE / "assemble.pids"
    data = _load_json(pid_file) if pid_file.exists() else {}
    parent = data.get("parent") or {}
    children = data.get("children") or []

    if not parent.get("pid") and not children:
        scanned = _find_mark42_processes()
        parent = scanned.get("parent") or {}
        children = scanned.get("children") or []

    return parent, children, pid_file


def assemble_stop() -> dict[str, Any]:
    """优雅停止 assemble；若父进程不存在，则兜底停止子进程。"""
    parent, children, pid_file = _load_assemble_pids()

    stopped = []
    missing = []

    parent_pid = parent.get("pid")
    if parent_pid and _pid_alive(parent_pid):
        _stop_process(parent_pid, parent.get("name", "assemble"))
        stopped.append({"name": parent.get("name", "assemble"), "pid": parent_pid})
    elif parent_pid:
        missing.append({"name": parent.get("name", "assemble"), "pid": parent_pid})

    for child in children:
        pid = child.get("pid")
        name = child.get("name", "child")
        if not pid:
            continue
        if _pid_alive(pid):
            try:
                _stop_process(pid, name, timeout_s=0.2)
                stopped.append({"name": name, "pid": pid})
            except OSError:
                missing.append({"name": name, "pid": pid})
        else:
            missing.append({"name": name, "pid": pid})

    pid_file.unlink(missing_ok=True)
    logger.info("🛑 Mark42 assemble 已停止")
    for item in stopped:
        logger.info(f"已停止: {item['name']} (PID {item['pid']})")
    for item in missing:
        logger.info(f"已不在运行: {item['name']} (PID {item['pid']})")

    return {"stopped": stopped, "missing": missing}


def assemble_restart() -> dict[str, Any]:
    """重启 assemble：先停旧进程，再后台拉起新 assemble。"""
    from ..config import LOG_DIR

    assemble_stop()
    time.sleep(1.0)

    script = str(Path(__file__).resolve().parent.parent.parent / "mark42.py")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    restart_log = open(str(LOG_DIR / "assemble.log"), "a")
    proc = subprocess.Popen(
        [sys.executable, script, "assemble"],
        stdout=restart_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent.parent),
    )
    logger.info("🔄 Mark42 assemble 已重启")
    logger.info(f"新 PID: {proc.pid}")
    logger.info(f"日志: {LOG_DIR / 'assemble.log'}")
    return {"pid": proc.pid, "log": str(LOG_DIR / "assemble.log")}


def _fork_daemon_children(script_path: str, log_dir: Path) -> list[tuple[str, int, Any]]:
    """Fork armor-guard 和 engine-daemon 子进程，返回 [(name, pid, log_fd), ...]。"""
    children = []

    logger.info("🛡️ 启动上下文铠甲守护...")
    armor_log = open(str(log_dir / "armor-guard.log"), "a")
    armor_proc = subprocess.Popen(
        [sys.executable, "-u", script_path, "armor", "--guard", "--interval", "300"],
        stdout=armor_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    children.append(("armor-guard", armor_proc.pid, armor_log))
    logger.info(f"armor-guard PID: {armor_proc.pid}")

    logger.info("🔄 启动循环引擎 daemon...")
    engine_log = open(str(log_dir / "engine-daemon.log"), "a")
    engine_proc = subprocess.Popen(
        [sys.executable, "-u", script_path, "engine", "--daemon", "--interval", "30"],
        stdout=engine_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    children.append(("engine-daemon", engine_proc.pid, engine_log))
    logger.info(f"engine-daemon PID: {engine_proc.pid}")

    return children


def _health_check_children(children: list[tuple[str, int, Any]]) -> tuple[list[str], list[str]]:
    """检查子进程存活状态，返回 (alive_names, dead_names)。"""
    logger.info("⏳ 3 秒后健康检查...")
    time.sleep(3)
    alive, dead = [], []
    for name, pid, _ in children:
        try:
            os.kill(pid, 0)
            alive.append(name)
        except OSError:
            dead.append(name)
    if alive:
        logger.info(f"✅ 存活: {', '.join(alive)}")
    if dead:
        logger.warning(f"❌ 死亡: {', '.join(dead)}")
    return alive, dead


def _save_assemble_pids(pid_file: Path, children: list[tuple[str, int, Any]]) -> bool:
    """保存 assemble PID 文件并校验。"""
    from ..utils import _load_json, _now_iso, _save_json

    pid_data = {
        "startedAt": _now_iso(),
        "parent": {"name": "assemble", "pid": os.getpid()},
        "children": [{"name": n, "pid": p} for n, p, _ in children],
    }
    _save_json(pid_file, pid_data)
    verify = _load_json(pid_file)
    if not verify or not verify.get("children"):
        logger.warning("PID 文件写入校验失败，但子进程已在运行")
        return False
    logger.info(f"📄 PID 文件: {pid_file} (已验证)")
    return True


def _assemble_monitor(children: list[tuple[str, int, Any]], pid_file: Path) -> None:
    """assemble 主循环：监控子进程存活 + 心跳超时检测。"""
    from ..config import ARMOR_STATE
    from ..utils import _load_json

    def _shutdown(sig, frame):
        logger.info("🛑 收到信号，正在优雅关闭...")
        for name, pid, log_fd in children:
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"已发送 SIGTERM -> {name} (PID {pid})")
            except OSError:
                logger.info(f"{name} 已退出")
            try:
                log_fd.close()
            except Exception:
                logger.exception("Unhandled exception")
        pid_file.unlink(missing_ok=True)
        logger.info("👋 Mark42 战甲已关闭")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("✅ Mark42 战甲已启动。拆开是刀，拼上是甲。")
    logger.info("按 Ctrl+C 关闭所有守护进程")
    logger.info("查看状态: mark42 status")

    engine_state = ARMOR_STATE.parent / "engine"
    heartbeat_file = engine_state / "daemon-heartbeat.json"
    logger.info("👁️ assemble 监护中（30s 轮询）...")

    try:
        while True:
            all_alive = True
            for name, pid, _ in children:
                try:
                    os.kill(pid, 0)
                except OSError:
                    all_alive = False
                    logger.warning(f"{name} (PID {pid}) 已退出！")
                    if name == "engine-daemon" and heartbeat_file.exists():
                        hb = _load_json(heartbeat_file)
                        if hb:
                            from datetime import datetime as _dt
                            from datetime import timezone as _tz

                            try:
                                last_tick = _dt.fromisoformat(hb.get("lastTick", ""))
                                gap = (_dt.now(_tz.utc) - last_tick).total_seconds()
                                logger.info(f"最后一次心跳: {gap:.0f}s 前")
                            except Exception:
                                logger.exception("Unhandled exception")
            if not all_alive:
                logger.error("子进程异常退出，assemble 退出")
                break
            time.sleep(30)
    except KeyboardInterrupt:
        _shutdown(None, None)


def assemble() -> None:
    """全甲启动入口 - fork 子进程拉起 armor guard + engine daemon。"""
    from ..armor import armor_check
    from ..config import ARMOR_STATE, LOG_DIR, mark42_init

    if not ARMOR_STATE.exists():
        logger.warning("尚未初始化，请先运行: mark42 --init")
        mark42_init()

    logger.info("""
┌──────────────────────────────────────────┐
│         🦾 Mark42 完整战甲启动            │
│                                          │
│  🛡️ 上下文铠甲  -> 守护模式               │
│  🔄 循环引擎    -> daemon 模式             │
│  ⚙️ 重型战甲    -> 按需激活                │
│                                          │
│  通过 broker 事件总线联动                 │
│  ~/.local/state/openclaw/broker/         │
└──────────────────────────────────────────┘
""")
    check = armor_check()
    logger.info(f"📊 启动时上下文: {check.get('usagePercent', 0)}% - {trim_summary(check.get('summary', ''), 100)}")

    script = str(Path(__file__).resolve().parent.parent.parent / "mark42.py")
    log_dir = LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    _trim_daemon_logs(log_dir)

    pid_file = ARMOR_STATE / "assemble.pids"
    children = _fork_daemon_children(script, log_dir)
    _health_check_children(children)
    _save_assemble_pids(pid_file, children)
    logger.info(f"📋 日志: {log_dir}")
    _assemble_monitor(children, pid_file)
