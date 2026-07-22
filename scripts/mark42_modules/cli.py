"""Mark42 CLI 入口。"""

import argparse
import sys

from .output_guard import trim_detail, trim_summary


def _trim_daemon_logs(log_dir):
    """检查 daemon 日志大小：单个文件超限则截尾保留最新部分。"""
    from .config import MAX_DAEMON_LOG_MB, MAX_DAEMON_LOG_LINES
    max_bytes = MAX_DAEMON_LOG_MB * 1024 * 1024
    for fpath in sorted(log_dir.glob("*.log")):
        try:
            size = fpath.stat().st_size
            if size <= max_bytes:
                continue
            # 读全部行，保留后一半（最新日志）
            with open(fpath) as f:
                lines = f.readlines()
            keep = min(MAX_DAEMON_LOG_LINES // 2, len(lines) // 2)
            with open(fpath, "w") as f:
                f.writelines(lines[-keep:])
            print(f"   🧹 截尾 {fpath.name}: {size/1024/1024:.1f}MB → {keep} 行")
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    """检查 PID 是否存活。"""
    import os
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _find_mark42_processes() -> dict:
    """兜底扫描 Mark42 守护相关进程。"""
    import subprocess

    result = {"parent": None, "children": []}
    try:
        out = subprocess.check_output(
            ["ps", "-eo", "pid=,ppid=,args="],
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


def assemble_status() -> dict:
    """查看 assemble / armor-guard / engine-daemon 当前状态。"""
    import json
    from .config import ARMOR_STATE
    from .utils import _load_json

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


def assemble_stop() -> dict:
    """优雅停止 assemble；若父进程不存在，则兜底停止子进程。"""
    import os
    import signal
    import time
    from .config import ARMOR_STATE
    from .utils import _load_json

    pid_file = ARMOR_STATE / "assemble.pids"
    data = _load_json(pid_file) if pid_file.exists() else {}
    parent = data.get("parent") or {}
    children = data.get("children") or []

    stopped = []
    missing = []

    if not parent.get("pid") and not children:
        scanned = _find_mark42_processes()
        parent = scanned.get("parent") or {}
        children = scanned.get("children") or []

    parent_pid = parent.get("pid")
    if parent_pid and _pid_alive(parent_pid):
        os.kill(parent_pid, signal.SIGTERM)
        deadline = time.time() + 8
        while time.time() < deadline and _pid_alive(parent_pid):
            time.sleep(0.2)
        if _pid_alive(parent_pid):
            os.kill(parent_pid, signal.SIGKILL)
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
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.2)
                if _pid_alive(pid):
                    os.kill(pid, signal.SIGKILL)
                stopped.append({"name": name, "pid": pid})
            except OSError:
                missing.append({"name": name, "pid": pid})
        else:
            missing.append({"name": name, "pid": pid})

    pid_file.unlink(missing_ok=True)
    print("🛑 Mark42 assemble 已停止")
    if stopped:
        for item in stopped:
            print(f"   已停止: {item['name']} (PID {item['pid']})")
    if missing:
        for item in missing:
            print(f"   已不在运行: {item['name']} (PID {item['pid']})")

    return {"stopped": stopped, "missing": missing}


def assemble_restart() -> dict:
    """重启 assemble：先停旧进程，再后台拉起新 assemble。"""
    import os
    import subprocess
    import sys
    import time
    from pathlib import Path
    from .config import LOG_DIR

    assemble_stop()
    time.sleep(1.0)

    script = str(Path(__file__).resolve().parent.parent / "mark42.py")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    restart_log = open(str(LOG_DIR / "assemble.log"), "a")
    proc = subprocess.Popen(
        [sys.executable, script, "assemble"],
        stdout=restart_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    print(f"🔄 Mark42 assemble 已重启")
    print(f"   新 PID: {proc.pid}")
    print(f"   日志: {LOG_DIR / 'assemble.log'}")
    return {"pid": proc.pid, "log": str(LOG_DIR / "assemble.log")}


def assemble() -> None:
    """全甲启动入口 — fork 子进程拉起 armor guard + engine daemon。"""
    import subprocess, sys, time, signal, os
    from pathlib import Path
    from .utils import _now_iso, _save_json, _load_json
    from .config import ARMOR_STATE, mark42_config, mark42_init
    from .utils import _now_iso, _save_json
    from .armor import armor_check

    if not ARMOR_STATE.exists():
        print("❌ 尚未初始化，请先运行: mark42.py --init\n")
        mark42_init()

    print("""
┌──────────────────────────────────────────┐
│         🦾 Mark42 完整战甲启动            │
│                                          │
│  🛡️ 上下文铠甲  → 守护模式               │
│  🔄 循环引擎    → daemon 模式             │
│  ⚙️ 重型战甲    → 按需激活                │
│                                          │
│  通过 broker 事件总线联动                 │
│  ~/.local/state/openclaw/broker/         │
└──────────────────────────────────────────┘
""")
    check = armor_check()
    print(f"📊 启动时上下文: {check.get('usagePercent', 0)}% — {trim_summary(check.get('summary', ''), 100)}\n")

    # ── Fork 子进程 ──
    script = str(Path(__file__).resolve().parent.parent / "mark42.py")
    children = []
    from .config import ARMOR_STATE, LOG_DIR, MAX_DAEMON_LOG_MB, MAX_DAEMON_LOG_LINES
    pid_file = ARMOR_STATE / "assemble.pids"
    log_dir = LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    # ── 日志大小检查（启动时先清一次旧日志） ──
    _trim_daemon_logs(log_dir)

    # 1. Armor 守护（间隔 300s）
    print("🛡️ 启动上下文铠甲守护...")
    armor_log = open(str(log_dir / "armor-guard.log"), "a")
    armor_proc = subprocess.Popen(
        [sys.executable, "-u", script, "armor", "--guard", "--interval", "300"],
        stdout=armor_log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    children.append(("armor-guard", armor_proc.pid, armor_log))
    print(f"   PID: {armor_proc.pid}")

    # 2. Engine daemon（扫描间隔 30s）
    print("🔄 启动循环引擎 daemon...")
    engine_log = open(str(log_dir / "engine-daemon.log"), "a")
    engine_proc = subprocess.Popen(
        [sys.executable, "-u", script, "engine", "--daemon", "--interval", "30"],
        stdout=engine_log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    children.append(("engine-daemon", engine_proc.pid, engine_log))
    print(f"   PID: {engine_proc.pid}")

    # 3. 健康检查（等 3 秒）
    print("\n⏳ 3 秒后健康检查...")
    time.sleep(3)
    alive = []
    dead = []
    for name, pid, _log_fd in children:
        try:
            os.kill(pid, 0)
            alive.append(name)
        except OSError:
            dead.append(name)
    if alive:
        print(f"✅ 存活: {', '.join(alive)}")
    if dead:
        print(f"❌ 死亡: {', '.join(dead)}")

    # 保存 PID 文件
    pid_data = {
        "startedAt": _now_iso(),
        "parent": {"name": "assemble", "pid": os.getpid()},
        "children": [{"name": n, "pid": p} for n, p, _ in children],
    }
    _save_json(pid_file, pid_data)
    # 校验写入
    verify_data = _load_json(pid_file)
    if not verify_data or not verify_data.get("children"):
        print(f"\n⚠️ PID 文件写入校验失败，但子进程已在运行")
    else:
        print(f"\n📄 PID 文件: {pid_file} (已验证)")

    # ── 优雅关闭 ──
    def _shutdown(sig, frame):
        print("\n\n🛑 收到信号，正在优雅关闭...")
        for name, pid, log_fd in children:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"   已发送 SIGTERM → {name} (PID {pid})")
            except OSError:
                print(f"   {name} 已退出")
            # 关闭父进程持有的日志文件句柄
            try:
                log_fd.close()
            except Exception:
                pass
        pid_file.unlink(missing_ok=True)
        print("👋 Mark42 战甲已关闭")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    print("\n✅ Mark42 战甲已启动。拆开是刀，拼上是甲。")
    print(f"   📋 日志: {log_dir}")
    print("   按 Ctrl+C 关闭所有守护进程")
    print(f"   查看状态: python3 scripts/mark42.py status")

    # 挂起主进程，非阻塞轮询子进程存活 + 心跳超时检测
    import signal as _sig
    engine_state = ARMOR_STATE.parent / "engine"
    heartbeat_file = engine_state / "daemon-heartbeat.json"
    heartbeat_timeout = 120  # 超过 120s 无心跳视为僵死
    print("\n👁️ assemble 监护中（30s 轮询）...")
    try:
        while True:
            # 检查所有子进程是否仍在运行
            all_alive = True
            for name, pid, _log_fd in children:
                try:
                    os.kill(pid, 0)
                except OSError:
                    all_alive = False
                    print(f"⚠️ {name} (PID {pid}) 已退出！")
                    # 检查心跳文件判断是否僵死已久
                    if name == "engine-daemon" and heartbeat_file.exists():
                        hb = _load_json(heartbeat_file)
                        if hb:
                            from datetime import datetime as _dt, timezone as _tz
                            try:
                                last_tick = _dt.fromisoformat(hb.get("lastTick", ""))
                                gap = (_dt.now(_tz.utc) - last_tick).total_seconds()
                                print(f"   最后一次心跳: {gap:.0f}s 前")
                            except Exception:
                                pass
            if not all_alive:
                print("🛑 子进程异常退出，assemble 退出")
                break
            time.sleep(30)
    except KeyboardInterrupt:
        _shutdown(None, None)


def status_dashboard(json_mode: bool = False, verbose: bool = False) -> dict | None:
    """一屏聚合 Armor/Engine/Heavy/Logs 状态。
    json_mode=True 返回 dict，不打印。
    """
    import json, os
    from datetime import datetime

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Armor ──
    from .armor import armor_check
    from .config import ARMOR_STATE, ENGINE_STATE, HEAVY_STATE, MARK42_BROKER_EVENTS, SCRATCH, THRESHOLD_WARN, THRESHOLD_ALERT, CONFIG_PATH
    from .utils import _load_json

    check = armor_check()
    usage = check.get("usagePercent", 0)
    status_icon = "🟢" if usage < THRESHOLD_WARN else ("🟠" if usage < THRESHOLD_ALERT else "🔴")

    # 版本号
    version = "?"
    if CONFIG_PATH.exists():
        version = _load_json(CONFIG_PATH).get("version", "?")

    # 记忆索引
    index_path = ARMOR_STATE / "memory-index.json"
    idx = None
    gen_time = None
    strat = None
    if index_path.exists():
        idx = _load_json(index_path)
        gen_time = idx.get("generatedAt", "?")
        strat = idx.get("strategyUsed", "?")

    # ── Engine ──
    loops = _load_json(ENGINE_STATE / "loops.json")
    active = sum(1 for l in loops.values() if l.get("status") in ("registered", "running"))
    total = len(loops)

    # ── Heavy ──
    heavy_tasks = list(HEAVY_STATE.glob("*.json"))

    # ── Logs ──
    from .logs import _load_state as _logs_state
    ls = _logs_state()
    last_rot = ls.get("lastRotation", "从未")
    count = ls.get("rotationCount", 0)

    # broker 事件
    broker_lines = 0
    broker_size = 0
    if MARK42_BROKER_EVENTS.exists():
        broker_size = MARK42_BROKER_EVENTS.stat().st_size
        broker_lines = sum(1 for _ in open(MARK42_BROKER_EVENTS))

    # scratch
    dirs = []
    kept = 0
    if SCRATCH.exists():
        dirs = [d for d in SCRATCH.iterdir() if d.is_dir()]
        kept = sum(1 for d in dirs if (d / ".keep").exists())

    # ── 人类可读输出 ──
    if not json_mode:
        print("\n" + "="*56)
        print("  🦾 Mark42 系统状态")
        print("="*56)
        print(f"  检查时间: {now_str}\n")
        print(f"  🛡️ 上下文铠甲")
        print(f"     {status_icon} {usage}% ({trim_summary(check.get('summary', ''), 100)})")
        if idx:
            print(f"     🧠 索引: {strat} ({gen_time[:16] if gen_time else '?'})")
        else:
            print(f"     🧠 索引: 无")
        print(f"\n  🔄 循环引擎")
        print(f"     Loop: {active} 活跃 / {total} 注册")
        if loops:
            for name, loop in sorted(loops.items()):
                cyc = loop.get("cycle", 0)
                max_c = loop.get("maxCycles")
                stat = loop.get("status")
                icon = "▶️" if stat == "running" else ("⏸️" if stat == "registered" else "⏹")
                print(f"     {icon} {name}: {stat} (cycle {cyc}/{max_c or '∞'})")
                if verbose and loop.get("task"):
                    print(f"        task: {trim_detail(loop.get('task'), 160)}")
        print(f"\n  ⚙️ 重型战甲")
        if heavy_tasks:
            for tf in sorted(heavy_tasks):
                ts = _load_json(tf)
                name = ts.get("taskName", "?")
                stat = ts.get("status", "?")
                tsum = ts.get("summary", "")
                icon = "🔄" if stat == "started" else ("✅" if stat == "finished" else "⏳")
                print(f"     {icon} {name}: {stat} — {trim_summary(tsum, 100)}")
                if verbose and ts.get("checkedAt"):
                    print(f"        checkedAt: {ts.get('checkedAt')}")
        else:
            print(f"     ℹ️ 无活跃任务")
        print(f"\n  🧹 日志轮替")
        print(f"     上次: {last_rot} (累计 {count} 次)")
        if MARK42_BROKER_EVENTS.exists():
            print(f"     Mark42 Broker: {broker_size/1024:.1f}KB ({broker_lines} 行)")
        if SCRATCH.exists():
            print(f"     Scratch: {len(dirs)} 目录 ({kept} 受保护)")
        print(f"\n  ── 快速操作 ──")
        if usage >= THRESHOLD_WARN:
            print(f"     ⚠️ 上下文偏高 → 建议: /compact")
        if active == 0:
            print(f"     💡 引擎空闲 → 注册: engine --start")
        print("="*56 + "\n")

    # ── 构建 JSON 输出数据 ──
    status_data = {
        "checkedAt": now_str,
        "version": version,
        "armor": {
            "usagePercent": usage,
            "status": check.get("status", "?"),
            "severity": check.get("severity", "?"),
            "summary": check.get("summary", ""),
            "contextWindow": check.get("contextWindow", 0),
            "estimatedTokens": check.get("estimatedTokens", 0),
            "memoryIndex": {
                "strategy": idx.get("strategyUsed", "?") if idx else "none",
                "generatedAt": idx.get("generatedAt") if idx else None,
                "modelGenerated": idx.get("modelGenerated", False) if idx else False,
            } if idx else None,
        },
        "engine": {
            "activeLoops": active,
            "totalLoops": total,
            "loops": {
                name: {
                    "status": loop.get("status"),
                    "template": loop.get("template"),
                    "cycle": loop.get("cycle", 0),
                    "maxCycles": loop.get("maxCycles"),
                    "task": loop.get("task"),
                    "lastRun": loop.get("lastRun"),
                }
                for name, loop in loops.items()
            },
        },
        "heavy": {
            "activeTasks": [
                {
                    "name": ts.get("taskName"),
                    "status": ts.get("status"),
                    "summary": ts.get("summary"),
                }
                for tf in heavy_tasks for ts in [_load_json(tf)]
            ],
        },
        "logs": {
            "lastRotation": last_rot,
            "rotationCount": count,
        },
        "broker": {
            "mark42Events": broker_lines if MARK42_BROKER_EVENTS.exists() else 0,
            "mark42SizeKB": round(broker_size / 1024, 1) if MARK42_BROKER_EVENTS.exists() else 0,
        },
        "scratch": {
            "totalDirs": len(dirs) if SCRATCH.exists() else 0,
            "keptDirs": kept if SCRATCH.exists() else 0,
        },
        "actions": [],
    }
    # 快速操作建议
    if usage >= THRESHOLD_WARN:
        status_data["actions"].append("建议 /compact")
    if active == 0:
        status_data["actions"].append("引擎空闲，建议注册 Loop")

    if json_mode:
        return status_data

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mark42 模块化智能铠甲系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  mark42.py --init
  mark42.py --config
  mark42.py logs --status
  mark42.py logs --rotate
  mark42.py armor --check
  mark42.py armor --compress --dry-run
  mark42.py armor --guard
  mark42.py engine --templates
  mark42.py engine --daemon
  mark42.py engine --start --task "监控上下文" --interval 300
  mark42.py engine --kill loop-name
  mark42.py engine --watch-task my-task
  mark42.py heavy --preflight /path/to/project
  mark42.py heavy --start /path/to/project --task-name my-task
  mark42.py heavy --finish --task-name my-task
  mark42.py heavy --cleanup --task-name my-task
  mark42.py context-safety status
  mark42.py context-safety apply
  mark42.py context-safety verify
  mark42.py assemble
        """,
    )
    parser.add_argument("--init", action="store_true", help="初始化 Mark42 配置")
    parser.add_argument("--config", action="store_true", help="查看当前配置")
    parser.add_argument("--tune-compaction", action="store_true", help="诊断并调优 OpenClaw 压缩配置")
    parser.add_argument("--apply", action="store_true", help="实际应用调优（默认仅预览）")
    parser.add_argument("--token-aware", action="store_true",
                       help="启用令牌感知检测 (v2.0)")
    parser.add_argument("--probe", action="store_true",
                       help="启用摘要质量探针 (v2.0)")
    parser.add_argument("--drift-check", action="store_true",
                       help="启用上下文降解检测 (v2.0)")

    sub = parser.add_subparsers(dest="module", help="模块选择")

    # ── Logs ──
    logs_p = sub.add_parser("logs", help="🧹 日志管理")
    logs_p.add_argument("--rotate", action="store_true", help="执行日志轮替（清理旧日志）")
    logs_p.add_argument("--status", action="store_true", help="查看日志轮替状态")

    # ── Armor ──
    armor_p = sub.add_parser("armor", help="🛡️ 上下文铠甲")
    armor_p.add_argument("--check", action="store_true", help="检查上下文健康度")
    armor_p.add_argument("--compress", action="store_true", help="触发智能压缩")
    armor_p.add_argument("--dry-run", action="store_true", help="压缩预览")
    armor_p.add_argument("--guard", action="store_true", help="启动守护模式")
    armor_p.add_argument("--interval", type=int, default=300, help="守护检查间隔秒数")
    armor_p.add_argument("--queue-stats", action="store_true", help="查看压缩队列统计")
    armor_p.add_argument("--smartcrush", action="store_true", help="对演示 JSON 跑一次 smartcrush 压测")

    # ── Engine ──
    engine_p = sub.add_parser("engine", help="🔄 循环引擎")
    engine_p.add_argument("--list", action="store_true", help="列出活跃 Loop")
    engine_p.add_argument("--start", action="store_true", help="注册新 Loop")
    engine_p.add_argument("--task", type=str, help="Loop 任务描述")
    engine_p.add_argument("--interval", type=int, default=300, help="周期秒数")
    engine_p.add_argument("--max-cycles", type=int, default=0, help="最大循环(0=无限)")
    engine_p.add_argument("--template", type=str, default="", help="模板名")
    engine_p.add_argument("--templates", action="store_true", help="列出模板")
    engine_p.add_argument("--run", type=str, help="手动触发 Loop")
    engine_p.add_argument("--kill", type=str, help="终止 Loop")
    engine_p.add_argument("--daemon", action="store_true", help="守护进程模式")
    engine_p.add_argument("--watch-task", type=str, help="监控大工程")

    # ── Heavy ──
    heavy_p = sub.add_parser("heavy", help="⚙️ 重型战甲")
    heavy_p.add_argument("--detect", type=str, help="自动检测工程是否为大工程")
    heavy_p.add_argument("--auto", type=str, choices=["ask","semi","full"], default="ask",
                        help="大工程检测后的行为：ask(默认,询问) / semi(半自动,30s倒计时) / full(全自动)")
    heavy_p.add_argument("--preflight", type=str, help="大工程预检")
    heavy_p.add_argument("--start", type=str, help="大工程开工")
    heavy_p.add_argument("--task-name", type=str, help="任务名")
    heavy_p.add_argument("--no-context-aware", action="store_true", help="禁用上下文感知")
    heavy_p.add_argument("--finish", action="store_true", help="大工程收工")
    heavy_p.add_argument("--execute", action="store_true", help="执行下一批次 (默认 dry-run)")
    heavy_p.add_argument("--execute-all", action="store_true", help="执行所有 pending 批次 (默认 dry-run)")
    heavy_p.add_argument("--batch", type=str, default="", help="指定批次ID (配合 --execute)")
    heavy_p.add_argument("--command", type=str, default="", help="每个文件执行的自定义命令，{f} 替换为文件路径")
    heavy_p.add_argument("--execute-now", action="store_true", help="【安全】--execute-now 才真跑后台进程；不加此 flag 仅入队不启动")
    heavy_p.add_argument("--cleanup", action="store_true", help="清理 scratch 目录")
    heavy_p.add_argument("--path", type=str, help="工作路径")

    # ── Cost ──
    cost_p = sub.add_parser("cost", help="💰 LLM 成本追踪")
    cost_p.add_argument("action", nargs="?", choices=["today", "month", "top"], default="today",
                       help="today(默认): 今日汇总 | month: 本月汇总 | top: 模块排名")
    cost_p.add_argument("--top-n", type=int, default=10, help="Top N 排名（仅用于 action=top）")
    cost_p.add_argument("--days", type=int, default=None, help="最近几天（仅用于 action=top，None=全部历史）")

    compaction_p = sub.add_parser("compaction", help="📊 OpenClaw 压缩配置诊断 & 调优 (v2.0)")
    compaction_p.add_argument("--token-aware", action="store_true",
                             help="启用令牌感知检测（从 session jsonl 读取实际 token 消耗）")
    compaction_p.add_argument("--probe", action="store_true",
                             help="启用摘要质量探针（检测压缩后关键信息留存率）")
    compaction_p.add_argument("--drift-check", action="store_true",
                             help="启用上下文降解检测（分析连续压缩趋势）")
    assemble_p = sub.add_parser("assemble", help="一键启动完整战甲")
    assemble_p.add_argument("--status", action="store_true", help="查看 assemble/guard/daemon 状态")
    assemble_p.add_argument("--stop", action="store_true", help="停止 assemble 及其子进程")
    assemble_p.add_argument("--restart", action="store_true", help="重启 assemble 及其子进程")
    context_p = sub.add_parser("context-safety", help="🧯 OpenClaw context 安全基线")
    context_p.add_argument("action", nargs="?", choices=["status", "apply", "verify"], default="status")
    context_p.add_argument("--verbose", action="store_true", help="输出更详细的检查/变更信息")
    status_p = sub.add_parser("status", help="一屏聚合系统状态")
    status_p.add_argument("--json", action="store_true", help="输出 JSON 格式")
    status_p.add_argument("--verbose", action="store_true", help="输出更详细的状态信息")

    # ── v3-2 错误档案（archive）──
    archive_p = sub.add_parser("archive", help="📚 错误档案管理（v3-2）")
    archive_p.add_argument("action", choices=["list", "show", "approve", "reject", "stats"], help="子动作")
    archive_p.add_argument("entry_id", nargs="?", default="", help="条目 ID（show/approve/reject 用）")
    archive_p.add_argument("--status", choices=["NEW", "RESOLVED", "AUTO_APPROVED", "REJECTED"], help="按状态过滤（list）")
    archive_p.add_argument("--category", help="按 category 过滤（list）")
    archive_p.add_argument("--limit", type=int, default=20, help="最多显示多少条（list）")
    archive_p.add_argument("--scope", choices=["exact_match", "similar_match"], default="exact_match", help="匹配范围（approve）")
    archive_p.add_argument("--notes", default="", help="备注（reject）")

    # ── v3-3/v3-4 战甲意识层（consciousness + advisor）──
    cs_p = sub.add_parser("consciousness", help="🧠 战甲意识层（C1-C5 · v3-3 + advisor · v3-4）")
    cs_p.add_argument("action", choices=["check", "eval", "handle", "advisor", "revalidate"], help="子动作")
    cs_p.add_argument("--source", help="issue source（eval/handle 用）")
    cs_p.add_argument("--category", help="issue category（eval/handle 用）")
    cs_p.add_argument("--msg", default="", help="issue 描述")
    cs_p.add_argument("--severity", default="warning", choices=["info", "warning", "critical"])
    cs_p.add_argument("--json", action="store_true", help="check JSON 输出")
    cs_p.add_argument("--execute-now", action="store_true", help="handle 真跑 auto_remediate（默认 dry-run）")

    # ── v3 §4.8 核心位注册表 ──
    cores_p = sub.add_parser("cores", help="🖥️ 核心位注册表（§4.8）")
    cores_p.add_argument("action", choices=["list", "probe", "quarantine", "restore"], help="子动作")
    cores_p.add_argument("--core-id", help="核心 ID")
    cores_p.add_argument("--reason", default="", help="隔离原因")

    # ── v3 R11 混沌工程 ──
    chaos_p = sub.add_parser("chaos", help="🔥 混沌工程（R11）")
    chaos_p.add_argument("action", choices=["list", "run", "history"], help="子动作")
    chaos_p.add_argument("--scenario", default="", help="场景 ID")
    chaos_p.add_argument("--execute-now", action="store_true", help="真实注入（默认 dry-run）")

    # ── v3 §3.7 模块级协议 ──
    mod_p = sub.add_parser("module", help="🔌 模块级协议（§3.7）")
    mod_p.add_argument("action", choices=["check", "summary"], help="子动作")

    # ── v3 R14 集群思维 ──
    clu_p = sub.add_parser("cluster", help="🏗️ 集群思维（R14）")
    clu_p.add_argument("action", choices=["list", "replace", "status"], help="子动作")
    clu_p.add_argument("--name", default="", help="集群名")
    clu_p.add_argument("--source", default="backup", choices=["backup", "git"], help="替换来源")

    # ── v3 R-CAND-02 熔断器 ──
    brk_p = sub.add_parser("breaker", help="⚡ 熔断器（R-CAND-02）")
    brk_p.add_argument("action", choices=["list", "status", "reset", "reset-all"], help="子动作")
    brk_p.add_argument("--core-id", default="", help="核心 ID（reset 时必填）")

    args = parser.parse_args()

    if not args.module:
        if args.init:
            from .config import mark42_init
            mark42_init()
            return
        if args.config:
            from .config import mark42_config
            mark42_config()
            return
        if args.tune_compaction:
            from .compaction_diag import compaction_diagnose, compaction_apply, print_diagnose, print_apply_result
            token_aware = getattr(args, 'token_aware', False)
            probe = getattr(args, 'probe', False)
            if token_aware or probe:
                # 先做一次 v2.0 诊断
                diag = compaction_diagnose(token_aware=token_aware, probe=probe)
                print_diagnose(diag)
                print()
                if args.apply:
                    result = compaction_apply(auto_confirm=True)
                else:
                    result = compaction_apply(auto_confirm=False)
            elif args.apply:
                result = compaction_apply(auto_confirm=True)
                print_apply_result(result)
            else:
                result = compaction_apply(auto_confirm=False)
                print_apply_result(result)
                print("  💡 使用 --apply 实际应用更改，或 --tune-compaction --apply")
            return
        parser.print_help()
        return

    if args.module == "logs":
        from .logs import log_rotate, log_rotate_status
        if args.rotate:
            log_rotate("all")
        elif args.status:
            log_rotate_status()
        else:
            log_rotate_status()
        return

    if args.module == "armor":
        from .armor import armor_check, armor_compress, armor_guard, armor_compress_queue_stats
        from .smart_crusher import smartcrush
        if args.check:
            result = armor_check()
            print(f"🛡️ 上下文铠甲")
            print(f"   状态: {result.get('status', '?').upper()} ({result.get('severity', '?')})")
            print(f"   使用率: {result.get('usagePercent', 0)}% "
                  f"({result.get('estimatedTokens', 0)/1000:.0f}K / {result.get('contextWindow', 0)/1000:.0f}K)")
            print(f"   {trim_summary(result.get('summary', ''), 100)}")
        elif args.dry_run or args.compress:
            result = armor_compress(dry_run=args.dry_run)
            import json as _j
            print(_j.dumps(result, indent=2, ensure_ascii=False))
        elif args.guard:
            armor_guard(args.interval)
        elif args.queue_stats:
            stats = armor_compress_queue_stats()
            print("📦 压缩队列统计")
            if "error" in stats:
                print(f"   ❌ {stats['error']}")
                return
            for k, v in stats.items():
                print(f"   {k}: {v}")
        elif args.smartcrush:
            import json as _sj
            demo = _sj.dumps({
                "users": [
                    {"id": i, "name": f"user_{i}", "bio": "x" * 300}
                    for i in range(40)
                ],
                "meta": {"version": "2.3.3", "note": "smartcrush CLI 演示"},
            }, ensure_ascii=False)
            crushed, cstats = smartcrush(demo)
            print("🧪 smartcrush 演示")
            print(f"   原始: {cstats.get('original_bytes', len(demo.encode()))} bytes")
            print(f"   压缩: {cstats.get('crushed_bytes', len(crushed.encode()))} bytes")
            print(f"   压缩率: {cstats.get('ratio', 0) * 100:.1f}%")
            print(f"   数组截断: {cstats.get('arrays_truncated', 0)}")
            print(f"   字符串截断: {cstats.get('strings_truncated', 0)}")
            print(f"   深度截断: {cstats.get('depth_truncated', 0)}")
        else:
            result = armor_check()
            print(f"🛡️ 上下文铠甲")
            print(f"   状态: {result.get('status', '?').upper()} ({result.get('severity', '?')})")
            print(f"   使用率: {result.get('usagePercent', 0)}% "
                  f"({result.get('estimatedTokens', 0)/1000:.0f}K / {result.get('contextWindow', 0)/1000:.0f}K)")
            print(f"   {trim_summary(result.get('summary', ''), 100)}")
        return

    if args.module == "engine":
        from .engine import (
            engine_daemon, engine_kill, engine_list, engine_run_loop,
            engine_start, engine_templates, engine_watch_task,
        )
        if args.templates:
            engine_templates()
        elif args.list:
            engine_list()
        elif args.start:
            engine_start(
                task=args.task or "未命名",
                interval_s=args.interval,
                max_cycles=args.max_cycles,
                template=args.template,
            )
        elif args.kill:
            engine_kill(args.kill)
        elif args.run:
            engine_run_loop(args.run)
        elif args.watch_task:
            engine_watch_task(args.watch_task, interval_s=args.interval)
        elif args.daemon:
            engine_daemon(args.interval)
        else:
            engine_list()
        return

    if args.module == "heavy":
        from .heavy import (
            heavy_cleanup, heavy_execute, heavy_execute_all,
            heavy_finish, heavy_preflight, heavy_start, heavy_detect_human,
        )
        path = args.path or args.detect or args.preflight or args.start or ""
        task_name = args.task_name or ""
        if args.detect:
            auto_mode = getattr(args, 'auto', 'ask') or 'ask'
            heavy_detect_human(args.detect, auto_mode=auto_mode)
        elif args.preflight:
            heavy_preflight(args.preflight)
        elif args.start and task_name:
            heavy_start(args.start, task_name,
                       context_aware=not args.no_context_aware)
        elif args.execute and task_name:
            heavy_execute(task_name, args.batch or None,
                          command=args.command or None,
                          execute_now=getattr(args, 'execute_now', False))
        elif args.execute_all and task_name:
            heavy_execute_all(task_name,
                              command=args.command or None,
                              execute_now=getattr(args, 'execute_now', False))
        elif args.finish and task_name:
            heavy_finish(task_name)
        elif args.cleanup and task_name:
            heavy_cleanup(task_name)
        elif args.start:
            print(f"❌ --task-name 不能为空")
        elif args.preflight:
            heavy_preflight(args.preflight)
        else:
            print("❌ 请指定 --preflight / --start / --execute / --execute-all / --finish / --cleanup")
        return

    if args.module == "cost":
        from .cost_tracker import cli_cost_today, cli_cost_month, cli_cost_top
        if args.action == "month":
            cli_cost_month()
        elif args.action == "top":
            cli_cost_top(n=args.top_n, days=args.days)
        else:
            cli_cost_today()
        return

    if args.module == "compaction":
        from .compaction_diag import compaction_diagnose, compaction_apply, print_diagnose, print_apply_result
        diag = compaction_diagnose(
            token_aware=getattr(args, 'token_aware', False),
            probe=getattr(args, 'probe', False),
        )
        print_diagnose(diag)
        if hasattr(args, 'drift_check') and args.drift_check and diag.get("issues"):
            # 如果显式启用 drift-check，额外提醒
            drift = [i for i in diag["issues"] if i.get("key") == "drift_detection"]
            if drift:
                d = drift[0]
                if d.get("severity") != "ok":
                    print(f"  🔍 降解检测: {d.get('status')} — {d.get('advice', '')}")
        if diag["actionable"]:
            print("  💡 如需自动调优: python3 scripts/mark42.py --tune-compaction")
            print("     直接应用: python3 scripts/mark42.py --tune-compaction --apply")
        return

    if args.module == "assemble":
        if args.status:
            assemble_status()
        elif args.stop:
            assemble_stop()
        elif args.restart:
            assemble_restart()
        else:
            assemble()
        return

    if args.module == "context-safety":
        from .context_safety import (
            context_safety_apply,
            context_safety_status,
            context_safety_verify,
        )
        if args.action == "apply":
            result = context_safety_apply(verbose=getattr(args, 'verbose', False))
            if not result.get("validateOk", False):
                sys.exit(1)
        elif args.action == "verify":
            sys.exit(context_safety_verify(verbose=getattr(args, 'verbose', False)))
        else:
            context_safety_status(verbose=getattr(args, 'verbose', False))
        return

    if args.module == "status":
        if getattr(args, 'json', False):
            import json as _j
            result = status_dashboard(json_mode=True)
            print(_j.dumps(result, indent=2, ensure_ascii=False))
        else:
            status_dashboard(verbose=getattr(args, 'verbose', False))
        return

    if args.module == "archive":
        # v3-2 错误档案 — 委派给 error_archive 子模块
        from .error_archive import (
            ErrorArchive, ALL_STATUSES, _print_entry_row,
        )
        arc = ErrorArchive()
        if args.action == "list":
            entries = arc.list_entries(status=args.status, category=args.category)[:args.limit]
            import json as _j2
            print(f"\n{'ID':32s} | {'CATEGORY':32s} | {'CNT':3s} | {'STATUS':15s} | LAST_SEEN")
            print("-" * 100)
            for e in entries:
                _print_entry_row(e)
            print(f"\n共 {len(entries)} 条（总 {arc.stats()['total']} 条）\n")
        elif args.action == "show":
            e = arc.get(args.entry_id)
            if e is None:
                print(f"❌ 找不到 {args.entry_id}")
                return 1
            import json as _j3
            print(_j3.dumps(e.to_dict(), indent=2, ensure_ascii=False))
        elif args.action == "approve":
            r = arc.approve_for_auto(args.entry_id, scope=args.scope)
            print(r["reason"])
            for w in r.get("warnings", []):
                print(w)
            return 0 if r["ok"] else 2
        elif args.action == "reject":
            r = arc.reject(args.entry_id, notes=args.notes)
            print(r["reason"])
            return 0 if r["ok"] else 2
        elif args.action == "stats":
            s = arc.stats()
            print(f"\n总条目: {s['total']}")
            print(f"按状态:")
            for k, v in s["by_status"].items():
                print(f"  {k:18s} {v}")
            print(f"已授权自动执行: {s['auto_approved_count']}\n")
        return

    if args.module == "consciousness":
        # v3-3 战甲意识层 — 委派给 consciousness 子模块
        from .consciousness import Consciousness
        import json as _j4
        cs = Consciousness()
        if args.action == "check":
            r = cs.self_check()
            if args.json:
                print(_j4.dumps(r.to_dict(), indent=2, ensure_ascii=False))
            else:
                icon = "🟢" if r.healthy else "🟠"
                print(f"\n{icon} C1 自检 [{r.checked_at}]")
                print(f"   健康: {r.healthy}")
                print(f"   发现 {len(r.issues)} 个问题:")
                for i, iss in enumerate(r.issues, 1):
                    print(f"     {i}. [{iss['severity']}] {iss['source']}/{iss['category']}: {iss.get('msg','-')}")
        elif args.action == "eval":
            if not args.source or not args.category:
                print("❌ --source 和 --category 必填")
                return 1
            issue = {"source": args.source, "category": args.category,
                     "msg": args.msg, "severity": args.severity}
            a = cs.assess_certainty(issue)
            print(_j4.dumps(a.to_dict(), indent=2, ensure_ascii=False))
        elif args.action == "handle":
            if not args.source or not args.category:
                print("❌ --source 和 --category 必填")
                return 1
            issue = {"source": args.source, "category": args.category,
                     "msg": args.msg, "severity": args.severity}
            result = cs.handle_issue(issue, dry_run=not args.execute_now)
            print(_j4.dumps(result, indent=2, ensure_ascii=False))
        elif args.action == "advisor":
            # v3-4 主动交流协议
            from .advisor_client import cli_advisor_status, cli_advisor_test
            print("🧠 Mark42 Advisor (v3-4)")
            print()
            status = cli_advisor_status()
            if status["enabled"]:
                print(f"  状态: ✅ 已启用")
                print(f"  模型: {status['model']}")
                print(f"  端点: {status['base_url']}")
                print(f"  API Key: {'✅ 有' if status['has_api_key'] else '❌ 无'}")
                print(f"  置信阈值: {status['confidence_threshold']}")
                print()
                print("正在 ping advisor...")
                test_result = cli_advisor_test()
                if test_result["success"]:
                    v = test_result.get("verdict", {})
                    print(f"  ✅ Ping 成功 ({test_result.get('elapsed_ms', 0)}ms)")
                    print(f"  verdict: {v.get('verdict', 'N/A')}")
                    print(f"  confidence: {v.get('confidence', 'N/A')}")
                else:
                    print(f"  ❌ Ping 失败: {test_result.get('reason', 'unknown')}")
            else:
                print(f"  状态: ⬜ 未启用")
                print()
                print("启用方法: 编辑 ~/.config/mark42/model.yaml")
                print("  mark42.advisor.enabled: true")
                print("  mark42.advisor.model: <模型名>")
                print("  mark42.advisor.base_url: <API 端点>")
                print("  mark42.advisor.api_key: <API Key>")
        elif args.action == "revalidate":
            # v3 R9 强制读协议验证
            import json as _j5
            result = cs.verify_read_protocol(force=True)
            if result.get("skipped"):
                print(f"⏭️ 跳过: {result.get('reason', '')}")
            elif result.get("passed"):
                print(f"✅ 读协议验证通过: {result.get('score')}/{result.get('total')} 题")
            else:
                print(f"❌ 读协议验证未通过: {result.get('score')}/{result.get('total')} 题")
                print(f"   需要答对 {result.get('min_correct')} 题")
            print()
            print(_j5.dumps(result, indent=2, ensure_ascii=False, default=str)[:500])
        return

    if args.module == "cores":
        from .core_registry import cli_cores_list, cli_cores_probe, cli_cores_quarantine, cli_cores_restore
        import json as _j6
        if args.action == "list":
            r = cli_cores_list()
            print(f"🖥️ 核心位注册表 ({r['summary']['total']} 核)\n")
            for c in r["cores"]:
                icon = {"healthy": "🟢", "degraded": "🟡", "down": "🔴", "quarantined": "⛔", "unknown": "⬜"}.get(c["status"], "?")
                print(f"  {icon} {c['core_id']:<35} {c['model_name']:<25} {c['status']}")
            s = r["summary"]
            print(f"\n  健康: {s['statuses'].get('healthy',0)} | 降级: {s['statuses'].get('degraded',0)} | 挂: {s['statuses'].get('down',0)} | 隔离: {s['statuses'].get('quarantined',0)}")
            if s["critical_down"]:
                print(f"  ⚠️ Critical 核心挂: {', '.join(s['critical_down'])}")
        elif args.action == "probe":
            r = cli_cores_probe()
            print(f"🔍 探活完成 ({len(r)} 核)\n")
            for cid, res in r.items():
                icon = "🟢" if res["status"] == "healthy" else "🔴" if res["status"] == "down" else "⬜"
                print(f"  {icon} {cid}: {res['status']} {res.get('reason','')}")
        elif args.action == "quarantine":
            if not args.core_id:
                print("❌ --core-id 必填")
                return 1
            r = cli_cores_quarantine(args.core_id, args.reason)
            print(f"{'✅' if r['ok'] else '❌'} 隔离 {args.core_id}: {r['ok']}")
        elif args.action == "restore":
            if not args.core_id:
                print("❌ --core-id 必填")
                return 1
            r = cli_cores_restore(args.core_id)
            print(f"{'✅' if r['ok'] else '❌'} 恢复 {args.core_id}: {r['ok']}")
        return

    if args.module == "chaos":
        from .chaos_engine import ChaosEngine
        import json as _j7
        ce = ChaosEngine()
        if args.action == "list":
            exps = ce.list_experiments()
            print(f"🔥 混沌工程实验 ({len(exps)} 个)\n")
            for e in exps:
                desc = e['description'][:40] + '...' if len(e['description']) > 40 else e['description']
                print(f"  {e['name']:<30} {desc}")
        elif args.action == "run":
            if not args.scenario:
                print("❌ --scenario 必填。可用实验:")
                for e in ce.list_experiments():
                    print(f"  {e['name']}")
                return 1
            r = ce.run_experiment(args.scenario, dry_run=not args.execute_now)
            icon = "✅" if r.status == "passed" else "❌"
            print(f"{icon} {r.experiment} [{r.status}]")
            print(f"  耗时: {r.duration_ms}ms")
            print(f"  setup: {'✅' if r.setup_ok else '❌'} | execute: {'✅' if r.execute_ok else '❌'} | verify: {'✅' if r.verify_ok else '❌'} | cleanup: {'✅' if r.cleanup_ok else '❌'}")
            print(f"  详情: {r.details}")
        elif args.action == "history":
            h = ce.get_results(limit=50)
            print(f"📜 Chaos Test 历史 ({len(h)} 条)\n")
            for r in h:
                icon = "✅" if r.get('status') == "passed" else "❌"
                print(f"  {icon} {r.get('experiment',''):<30} {r.get('started_at','')[:19]}  {r.get('duration_ms',0)}ms")
        return

    if args.module == "module":
        from .module_health import ModuleHealthMonitor
        import json as _j8
        mhm = ModuleHealthMonitor()
        if args.action == "check":
            results = mhm.check_all()
            print(f"🔌 模块级协议检查 ({len(results)} 模块)\n")
            for h in results:
                icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(h.status, "?")
                lat = f"{h.latency_ms}ms" if h.latency_ms is not None else "-"
                fb = f" [fallback: {h.fallback_active}]" if h.fallback_active else ""
                print(f"  {icon} {h.module_name:<15} {lat:<8} {h.status}{fb}")
        elif args.action == "summary":
            s = mhm.summary()
            print(f"🔌 模块级协议摘要\n")
            print(f"  总计: {s['total']} | 🟢 {s['green']} | 🟡 {s['yellow']} | 🔴 {s['red']}")
        return

    if args.module == "cluster":
        from .cluster_manager import ClusterManager
        import json as _j9
        cm = ClusterManager()
        if args.action == "list":
            clusters = cm.list_clusters()
            print(f"🏗️ 集群列表 ({len(clusters)} 个)\n")
            for c in clusters:
                print(f"  {c['name']:<30} {c['core_id']:<35} {c['criticality']}")
        elif args.action == "status":
            # 用 list_clusters + core_registry 获取状态
            from .core_registry import CoreRegistry
            reg = CoreRegistry()
            clusters = cm.list_clusters()
            print(f"🏗️ 集群状态 ({len(clusters)} 个)\n")
            for c in clusters:
                core = reg.get_core(c["core_id"])
                status = core.status if core else "unknown"
                model = core.model_name if core else ""
                icon = {"healthy": "🟢", "degraded": "🟡", "down": "🔴", "quarantined": "⛔", "unknown": "⬜"}.get(status, "?")
                print(f"  {icon} {c['name']:<30} {model:<25} {status}")
        elif args.action == "replace":
            if not args.name:
                print("❌ --name 必填。可用集群:")
                for c in cm.list_clusters():
                    print(f"  {c['name']}")
                return 1
            r = cm.replace(args.name, source=args.source)
            print(f"{'✅' if r.get('ok') else '❌'} {r.get('note','')} (action recorded)")
        return

    if args.module == "breaker":
        from .circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        if args.action == "list":
            states = cb.list_all()
            if not states:
                print("⚡ 熔断器状态\n  全部 closed（正常）")
            else:
                print(f"⚡ 熔断器状态（{len(states)} 个非 closed）\n")
                for s in states:
                    icon = {"open": "🔴", "half_open": "🟡"}.get(s["status"], "?")
                    print(f"  {icon} {s['core_id']:<35} {s['status']} (failures={s['consecutive_failures']})")
        elif args.action == "status":
            if args.core_id:
                st = cb.get_state(args.core_id)
                print(f"⚡ {args.core_id}: {st['status']} (failures={st['consecutive_failures']})")
            else:
                states = cb.list_all()
                if not states:
                    print("⚡ 熔断器状态\n  全部 closed（正常）")
                else:
                    for s in states:
                        icon = {"open": "🔴", "half_open": "🟡"}.get(s["status"], "?")
                        print(f"  {icon} {s['core_id']:<35} {s['status']}")
        elif args.action == "reset":
            if not args.core_id:
                print("❌ --core-id 必填")
                return 1
            cb.reset(args.core_id)
            print(f"✅ 熔断器 {args.core_id} 已重置")
        elif args.action == "reset-all":
            cb.reset_all()
            print("✅ 所有熔断器已重置")
        return


if __name__ == "__main__":
    main()
