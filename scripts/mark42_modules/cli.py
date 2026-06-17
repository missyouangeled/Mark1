"""Mark42 CLI 入口。"""

import argparse
import sys


def assemble() -> None:
    """全甲启动入口 — fork 子进程拉起 armor guard + engine daemon。"""
    import subprocess, sys, time, signal, os
    from pathlib import Path
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
    print(f"📊 启动时上下文: {check.get('usagePercent', 0)}% — {check.get('summary', '')}\n")

    # ── Fork 子进程 ──
    script = str(Path(__file__).resolve().parent.parent / "mark42.py")
    children = []
    pid_file = ARMOR_STATE / "assemble.pids"
    log_dir = ARMOR_STATE / "daemon-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

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
    pid_data = {"startedAt": _now_iso(), "children": [{"name": n, "pid": p} for n, p, _ in children]}
    _save_json(pid_file, pid_data)
    print(f"\n📄 PID 文件: {pid_file}")

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


def status_dashboard(json_mode: bool = False) -> dict | None:
    """一屏聚合 Armor/Engine/Heavy/Logs 状态。
    json_mode=True 返回 dict，不打印。
    """
    import json, os
    from datetime import datetime

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Armor ──
    from .armor import armor_check
    from .config import ARMOR_STATE, ENGINE_STATE, HEAVY_STATE, MARK42_BROKER_EVENTS, SCRATCH, THRESHOLD_WARN, THRESHOLD_ALERT
    from .utils import _load_json

    check = armor_check()
    usage = check.get("usagePercent", 0)
    status_icon = "🟢" if usage < THRESHOLD_WARN else ("🟠" if usage < THRESHOLD_ALERT else "🔴")

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
        print(f"     {status_icon} {usage}% ({check.get('summary', '')})")
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
        print(f"\n  ⚙️ 重型战甲")
        if heavy_tasks:
            for tf in sorted(heavy_tasks):
                ts = _load_json(tf)
                name = ts.get("taskName", "?")
                stat = ts.get("status", "?")
                tsum = ts.get("summary", "")
                icon = "🔄" if stat == "started" else ("✅" if stat == "finished" else "⏳")
                print(f"     {icon} {name}: {stat} — {tsum}")
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
    heavy_p.add_argument("--execute", action="store_true", help="执行下一批次")
    heavy_p.add_argument("--execute-all", action="store_true", help="执行所有 pending 批次")
    heavy_p.add_argument("--batch", type=str, default="", help="指定批次ID (配合 --execute)")
    heavy_p.add_argument("--command", type=str, default="", help="每个文件执行的自定义命令，{f} 替换为文件路径")
    heavy_p.add_argument("--cleanup", action="store_true", help="清理 scratch 目录")
    heavy_p.add_argument("--path", type=str, help="工作路径")

    compaction_p = sub.add_parser("compaction", help="📊 OpenClaw 压缩配置诊断 & 调优 (v2.0)")
    compaction_p.add_argument("--token-aware", action="store_true",
                             help="启用令牌感知检测（从 session jsonl 读取实际 token 消耗）")
    compaction_p.add_argument("--probe", action="store_true",
                             help="启用摘要质量探针（检测压缩后关键信息留存率）")
    compaction_p.add_argument("--drift-check", action="store_true",
                             help="启用上下文降解检测（分析连续压缩趋势）")
    sub.add_parser("assemble", help="一键启动完整战甲")
    status_p = sub.add_parser("status", help="一屏聚合系统状态")
    status_p.add_argument("--json", action="store_true", help="输出 JSON 格式")

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
        from .armor import armor_check, armor_compress, armor_guard
        if args.check:
            result = armor_check()
            print(f"🛡️ 上下文铠甲")
            print(f"   状态: {result.get('status', '?').upper()} ({result.get('severity', '?')})")
            print(f"   使用率: {result.get('usagePercent', 0)}% "
                  f"({result.get('estimatedTokens', 0)/1000:.0f}K / {result.get('contextWindow', 0)/1000:.0f}K)")
            print(f"   {result.get('summary', '')}")
        elif args.dry_run or args.compress:
            result = armor_compress(dry_run=args.dry_run)
            import json as _j
            print(_j.dumps(result, indent=2, ensure_ascii=False))
        elif args.guard:
            armor_guard(args.interval)
        else:
            result = armor_check()
            print(f"🛡️ 上下文铠甲")
            print(f"   状态: {result.get('status', '?').upper()} ({result.get('severity', '?')})")
            print(f"   使用率: {result.get('usagePercent', 0)}% "
                  f"({result.get('estimatedTokens', 0)/1000:.0f}K / {result.get('contextWindow', 0)/1000:.0f}K)")
            print(f"   {result.get('summary', '')}")
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
            heavy_execute(task_name, args.batch or None, command=args.command or None)
        elif args.execute_all and task_name:
            heavy_execute_all(task_name)
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
        assemble()
        return

    if args.module == "status":
        if getattr(args, 'json', False):
            import json as _j
            result = status_dashboard(json_mode=True)
            print(_j.dumps(result, indent=2, ensure_ascii=False))
        else:
            status_dashboard()
        return


if __name__ == "__main__":
    main()
