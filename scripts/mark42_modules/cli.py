"""Mark42 CLI 入口。"""

import argparse
import sys


def assemble() -> None:
    """全甲启动入口。"""
    from .config import ARMOR_STATE, mark42_config, mark42_init
    from .armor import armor_check

    if not ARMOR_STATE.exists():
        print("❌ 尚未初始化，请先运行: mark42.py --init\n")
        mark42_init()
    print("""
┌──────────────────────────────────────────┐
│         🦾 Mark42 完整战甲启动            │
│                                          │
│  🛡️ 上下文铠甲  → 守护模式               │
│  🔄 循环引擎    → 待命                    │
│  ⚙️ 重型战甲    → 按需激活                │
│                                          │
│  通过 broker 事件总线联动                 │
│  ~/.local/state/openclaw/broker/         │
└──────────────────────────────────────────┘
""")
    check = armor_check()
    print(f"📊 启动时上下文: {check.get('usagePercent', 0)}% — {check.get('summary', '')}\n")
    print("🛡️ 上下文铠甲守护（通过 armor --guard 启动）")
    print("   手动守护: python3 scripts/mark42.py armor --guard")
    print("🔄 循环引擎待命（通过 --start 注册 Loop 或 engine --daemon 启动守护）")
    print("⚙️ 重型战甲按需激活（通过 heavy --start 开工）")
    print("\n✅ Mark42 就绪。拆开是刀，拼上是甲。")


def status_dashboard() -> None:
    """一屏聚合 Armor/Engine/Heavy/Logs 状态。"""
    import json, os
    from datetime import datetime

    print("\n" + "="*56)
    print("  🦾 Mark42 系统状态")
    print("="*56)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  检查时间: {now_str}\n")

    # ── Armor ──
    from .armor import armor_check
    from .config import ARMOR_STATE, ENGINE_STATE, HEAVY_STATE, MARK42_BROKER_EVENTS, SCRATCH, THRESHOLD_WARN, THRESHOLD_ALERT
    from .utils import _load_json

    check = armor_check()
    usage = check.get("usagePercent", 0)
    status_icon = "🟢" if usage < THRESHOLD_WARN else ("🟠" if usage < THRESHOLD_ALERT else "🔴")
    print(f"  🛡️ 上下文铠甲")
    print(f"     {status_icon} {usage}% ({check.get('summary', '')})")

    # 记忆索引
    index_path = ARMOR_STATE / "memory-index.json"
    if index_path.exists():
        idx = _load_json(index_path)
        gen_time = idx.get("generatedAt", "?")
        strat = idx.get("strategyUsed", "?")
        print(f"     🧠 索引: {strat} ({gen_time[:16] if gen_time else '?'})")
    else:
        print(f"     🧠 索引: 无")

    # ── Engine ──
    loops = _load_json(ENGINE_STATE / "loops.json")
    active = sum(1 for l in loops.values() if l.get("status") in ("registered", "running"))
    total = len(loops)
    print(f"\n  🔄 循环引擎")
    print(f"     Loop: {active} 活跃 / {total} 注册")
    if loops:
        for name, loop in sorted(loops.items()):
            cyc = loop.get("cycle", 0)
            max_c = loop.get("maxCycles")
            stat = loop.get("status")
            icon = "▶️" if stat == "running" else ("⏸️" if stat == "registered" else "⏹")
            print(f"     {icon} {name}: {stat} (cycle {cyc}/{max_c or '∞'})")

    # ── Heavy ──
    heavy_tasks = list(HEAVY_STATE.glob("*.json"))
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

    # ── Logs ──
    from .logs import _load_state as _logs_state
    ls = _logs_state()
    last_rot = ls.get("lastRotation", "从未")
    count = ls.get("rotationCount", 0)
    print(f"\n  🧹 日志轮替")
    print(f"     上次: {last_rot} (累计 {count} 次)")

    # broker 事件
    if MARK42_BROKER_EVENTS.exists():
        broker_size = MARK42_BROKER_EVENTS.stat().st_size
        broker_lines = sum(1 for _ in open(MARK42_BROKER_EVENTS))
        print(f"     Mark42 Broker: {broker_size/1024:.1f}KB ({broker_lines} 行)")

    # scratch
    if SCRATCH.exists():
        dirs = [d for d in SCRATCH.iterdir() if d.is_dir()]
        kept = sum(1 for d in dirs if (d / ".keep").exists())
        print(f"     Scratch: {len(dirs)} 目录 ({kept} 受保护)")

    # ── 快速操作 ──
    print(f"\n  ── 快速操作 ──")
    if usage >= THRESHOLD_WARN:
        print(f"     ⚠️ 上下文偏高 → 建议: /compact")
    if active == 0:
        print(f"     💡 引擎空闲 → 注册: engine --start")
    print("="*56 + "\n")


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
    heavy_p.add_argument("--preflight", type=str, help="大工程预检")
    heavy_p.add_argument("--start", type=str, help="大工程开工")
    heavy_p.add_argument("--task-name", type=str, help="任务名")
    heavy_p.add_argument("--no-context-aware", action="store_true", help="禁用上下文感知")
    heavy_p.add_argument("--finish", action="store_true", help="大工程收工")
    heavy_p.add_argument("--execute", action="store_true", help="执行下一批次")
    heavy_p.add_argument("--execute-all", action="store_true", help="执行所有 pending 批次")
    heavy_p.add_argument("--batch", type=str, default="", help="指定批次ID (配合 --execute)")
    heavy_p.add_argument("--cleanup", action="store_true", help="清理 scratch 目录")
    heavy_p.add_argument("--path", type=str, help="工作路径")

    sub.add_parser("assemble", help="一键启动完整战甲")
    sub.add_parser("status", help="一屏聚合系统状态")

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
            heavy_finish, heavy_preflight, heavy_start,
        )
        path = args.path or args.preflight or args.start or ""
        task_name = args.task_name or ""
        if args.preflight:
            heavy_preflight(args.preflight)
        elif args.start and task_name:
            heavy_start(args.start, task_name,
                       context_aware=not args.no_context_aware)
        elif args.execute and task_name:
            heavy_execute(task_name, args.batch or None)
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

    if args.module == "assemble":
        assemble()
        return

    if args.module == "status":
        status_dashboard()
        return


if __name__ == "__main__":
    main()
