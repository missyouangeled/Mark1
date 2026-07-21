"""Mark42 CLI - 参数解析与命令分发。

包含 argparse 解析器构建和所有子命令的 dispatch 函数。
"""

from __future__ import annotations

import argparse
import sys

from .. import __version__
from ..output_guard import trim_summary
from .assemble import assemble, assemble_restart, assemble_status, assemble_stop
from .status import status_dashboard


def _build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器。"""
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
    parser.add_argument("--force", action="store_true", help="强制覆盖现有配置")
    parser.add_argument("--config", action="store_true", help="查看当前配置")
    parser.add_argument("--tune-compaction", action="store_true", help="诊断并调优 OpenClaw 压缩配置")
    parser.add_argument("--apply", action="store_true", help="实际应用调优（默认仅预览）")
    parser.add_argument("--token-aware", action="store_true", help="启用令牌感知检测 (v2.0)")
    parser.add_argument("--probe", action="store_true", help="启用摘要质量探针 (v2.0)")
    parser.add_argument("--drift-check", action="store_true", help="启用上下文降解检测 (v2.0)")

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
    heavy_p.add_argument(
        "--auto",
        type=str,
        choices=["ask", "semi", "full"],
        default="ask",
        help="大工程检测后的行为：ask(默认,询问) / semi(半自动,30s倒计时) / full(全自动)",
    )
    heavy_p.add_argument("--preflight", type=str, help="大工程预检")
    heavy_p.add_argument("--start", type=str, help="大工程开工")
    heavy_p.add_argument("--task-name", type=str, help="任务名")
    heavy_p.add_argument("--no-context-aware", action="store_true", help="禁用上下文感知")
    heavy_p.add_argument("--finish", action="store_true", help="大工程收工")
    heavy_p.add_argument("--execute", action="store_true", help="执行下一批次 (默认 dry-run)")
    heavy_p.add_argument("--execute-all", action="store_true", help="执行所有 pending 批次 (默认 dry-run)")
    heavy_p.add_argument("--batch", type=str, default="", help="指定批次ID (配合 --execute)")
    heavy_p.add_argument("--command", type=str, default="", help="每个文件执行的自定义命令，{f} 替换为文件路径")
    heavy_p.add_argument(
        "--execute-now", action="store_true", help="【安全】--execute-now 才真跑后台进程；不加此 flag 仅入队不启动"
    )
    heavy_p.add_argument("--cleanup", action="store_true", help="清理 scratch 目录")
    heavy_p.add_argument("--path", type=str, help="工作路径")

    compaction_p = sub.add_parser("compaction", help="📊 OpenClaw 压缩配置诊断 & 调优 (v2.0)")
    compaction_p.add_argument(
        "--token-aware", action="store_true", help="启用令牌感知检测（从 session jsonl 读取实际 token 消耗）"
    )
    compaction_p.add_argument("--probe", action="store_true", help="启用摘要质量探针（检测压缩后关键信息留存率）")
    compaction_p.add_argument("--drift-check", action="store_true", help="启用上下文降解检测（分析连续压缩趋势）")
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
    archive_p.add_argument(
        "--status", choices=["NEW", "RESOLVED", "AUTO_APPROVED", "REJECTED"], help="按状态过滤（list）"
    )
    archive_p.add_argument("--category", help="按 category 过滤（list）")
    archive_p.add_argument("--limit", type=int, default=20, help="最多显示多少条（list）")
    archive_p.add_argument(
        "--scope", choices=["exact_match", "similar_match"], default="exact_match", help="匹配范围（approve）"
    )
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

    # install 子命令：渲染 systemd 服务并安装
    install_p = sub.add_parser("install", help="📦 安装/更新 systemd 服务")
    install_p.add_argument("--uninstall", action="store_true", help="卸载 systemd 服务")
    install_p.add_argument("--workspace", default="", help="OpenClaw 工作区路径（默认 ~/.openclaw/workspace）")

    # watchdog 子命令：检查 daemon 存活并自动重启
    watchdog_p = sub.add_parser("watchdog", help="🐕 Watchdog - 检查 daemon 存活")
    watchdog_p.add_argument("--check", action="store_true", help="执行一次检查")

    parser.add_argument("--version", action="version", version=f"Mark42 v{__version__}")
    return parser


def _cmd_default(args) -> None:
    """处理无子命令时的 --init/--config/--tune-compaction。"""
    if args.init:
        from ..config import mark42_init
        from ..user_config import init_user_config

        config_path = init_user_config(force=args.force if hasattr(args, "force") else False)
        print(f"✅ 配置文件: {config_path}")
        mark42_init()
        return
    if args.config:
        from ..config import mark42_config
        from ..user_config import get_config_path

        config_path = get_config_path()
        print(f"📋 配置文件: {config_path}")
        if config_path.exists():
            print(f"   大小: {config_path.stat().st_size} bytes")
        else:
            print("   (未创建，运行 mark42 --init 生成)")
        print()
        mark42_config()
        return
    if args.tune_compaction:
        from ..compaction_diag import compaction_apply, compaction_diagnose, print_apply_result, print_diagnose

        token_aware = getattr(args, "token_aware", False)
        probe = getattr(args, "probe", False)
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
    # 无匹配子命令时打印帮助
    _build_parser().print_help()
    return


def _cmd_install(args) -> None:
    """处理 install 子命令。"""
    from ..installer import install_systemd, uninstall_systemd

    if args.uninstall:
        uninstall_systemd()
    else:
        ws = args.workspace if args.workspace else ""
        install_systemd(workspace=ws)
    return


def _cmd_watchdog(args) -> None:
    """处理 watchdog 子命令。"""
    from ..watchdog import watchdog_check

    watchdog_check()
    return


def _cmd_logs(args) -> None:
    """处理 logs 子命令。"""
    from ..logs import log_rotate, log_rotate_status

    if args.rotate:
        log_rotate("all")
    elif args.status:
        log_rotate_status()
    else:
        log_rotate_status()
    return


def _cmd_armor(args) -> None:
    """处理 armor 子命令。"""
    from ..armor import armor_check, armor_compress, armor_compress_queue_stats, armor_guard
    from ..smart_crusher import smartcrush

    if args.check:
        result = armor_check()
        print("🛡️ 上下文铠甲")
        print(f"   状态: {result.get('status', '?').upper()} ({result.get('severity', '?')})")
        print(
            f"   使用率: {result.get('usagePercent', 0)}% "
            f"({result.get('estimatedTokens', 0) / 1000:.0f}K / {result.get('contextWindow', 0) / 1000:.0f}K)"
        )
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

        demo = _sj.dumps(
            {
                "users": [{"id": i, "name": f"user_{i}", "bio": "x" * 300} for i in range(40)],
                "meta": {"version": "2.3.3", "note": "smartcrush CLI 演示"},
            },
            ensure_ascii=False,
        )
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
        print("🛡️ 上下文铠甲")
        print(f"   状态: {result.get('status', '?').upper()} ({result.get('severity', '?')})")
        print(
            f"   使用率: {result.get('usagePercent', 0)}% "
            f"({result.get('estimatedTokens', 0) / 1000:.0f}K / {result.get('contextWindow', 0) / 1000:.0f}K)"
        )
        print(f"   {trim_summary(result.get('summary', ''), 100)}")
    return


def _cmd_engine(args) -> None:
    """处理 engine 子命令。"""
    from ..engine import (
        engine_daemon,
        engine_kill,
        engine_list,
        engine_run_loop,
        engine_start,
        engine_templates,
        engine_watch_task,
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


def _cmd_heavy(args) -> None:
    """处理 heavy 子命令。"""
    from ..heavy import (
        heavy_cleanup,
        heavy_detect_human,
        heavy_execute,
        heavy_execute_all,
        heavy_finish,
        heavy_preflight,
        heavy_start,
    )

    _ = args.path or args.detect or args.preflight or args.start or ""
    task_name = args.task_name or ""
    if args.detect:
        auto_mode = getattr(args, "auto", "ask") or "ask"
        heavy_detect_human(args.detect, auto_mode=auto_mode)
    elif args.preflight:
        heavy_preflight(args.preflight)
    elif args.start and task_name:
        heavy_start(args.start, task_name, context_aware=not args.no_context_aware)
    elif args.execute and task_name:
        heavy_execute(
            task_name,
            args.batch or None,
            command=args.command or None,
            execute_now=getattr(args, "execute_now", False),
        )
    elif args.execute_all and task_name:
        heavy_execute_all(task_name, command=args.command or None, execute_now=getattr(args, "execute_now", False))
    elif args.finish and task_name:
        heavy_finish(task_name)
    elif args.cleanup and task_name:
        heavy_cleanup(task_name)
    elif args.start:
        print("❌ --task-name 不能为空")
    elif args.preflight:
        heavy_preflight(args.preflight)
    else:
        print("❌ 请指定 --preflight / --start / --execute / --execute-all / --finish / --cleanup")
    return


def _cmd_compaction(args) -> None:
    """处理 compaction 子命令。"""
    from ..compaction_diag import compaction_diagnose, print_diagnose

    diag = compaction_diagnose(
        token_aware=getattr(args, "token_aware", False),
        probe=getattr(args, "probe", False),
    )
    print_diagnose(diag)
    if hasattr(args, "drift_check") and args.drift_check and diag.get("issues"):
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


def _cmd_assemble(args) -> None:
    """处理 assemble 子命令。"""
    if args.status:
        assemble_status()
    elif args.stop:
        assemble_stop()
    elif args.restart:
        assemble_restart()
    else:
        assemble()
    return


def _cmd_context_safety(args) -> None:
    """处理 context-safety 子命令。"""
    from ..context_safety import (
        context_safety_apply,
        context_safety_status,
        context_safety_verify,
    )

    if args.action == "apply":
        result = context_safety_apply(verbose=getattr(args, "verbose", False))
        if not result.get("validateOk", False):
            sys.exit(1)
    elif args.action == "verify":
        sys.exit(context_safety_verify(verbose=getattr(args, "verbose", False)))
    else:
        context_safety_status(verbose=getattr(args, "verbose", False))
    return


def _cmd_status(args) -> None:
    """处理 status 子命令。"""
    if getattr(args, "json", False):
        import json as _j

        result = status_dashboard(json_mode=True)
        print(_j.dumps(result, indent=2, ensure_ascii=False))
    else:
        status_dashboard(verbose=getattr(args, "verbose", False))
    return


def _cmd_archive(args) -> None:
    """处理 archive 子命令。"""
    # v3-2 错误档案 — 委派给 error_archive 子模块
    from ..error_archive import (
        ErrorArchive,
        _print_entry_row,
    )

    arc = ErrorArchive()
    if args.action == "list":
        entries = arc.list_entries(status=args.status, category=args.category)[: args.limit]
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
        print("按状态:")
        for k, v in s["by_status"].items():
            print(f"  {k:18s} {v}")
        print(f"已授权自动执行: {s['auto_approved_count']}\n")
    return


def _cmd_consciousness(args) -> None:
    """处理 consciousness 子命令。"""
    # v3-3 战甲意识层 — 委派给 consciousness 子模块
    import json as _j4

    from ..consciousness import Consciousness

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
                print(f"     {i}. [{iss['severity']}] {iss['source']}/{iss['category']}: {iss.get('msg', '-')}")
    elif args.action == "eval":
        if not args.source or not args.category:
            print("❌ --source 和 --category 必填")
            return 1
        issue = {"source": args.source, "category": args.category, "msg": args.msg, "severity": args.severity}
        a = cs.assess_certainty(issue)
        print(_j4.dumps(a.to_dict(), indent=2, ensure_ascii=False))
    elif args.action == "handle":
        if not args.source or not args.category:
            print("❌ --source 和 --category 必填")
            return 1
        issue = {"source": args.source, "category": args.category, "msg": args.msg, "severity": args.severity}
        result = cs.handle_issue(issue, dry_run=not args.execute_now)
        print(_j4.dumps(result, indent=2, ensure_ascii=False))
    elif args.action == "advisor":
        # v3-4 主动交流协议
        from ..advisor_client import cli_advisor_status, cli_advisor_test

        print("🧠 Mark42 Advisor (v3-4)")
        print()
        status = cli_advisor_status()
        if status["enabled"]:
            print("  状态: ✅ 已启用")
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
            print("  状态: ⬜ 未启用")
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


def _cmd_cores(args) -> None:
    """处理 cores 子命令。"""
    from ..core_registry import cli_cores_list, cli_cores_probe, cli_cores_quarantine, cli_cores_restore

    if args.action == "list":
        r = cli_cores_list()
        print(f"🖥️ 核心位注册表 ({r['summary']['total']} 核)\n")
        for c in r["cores"]:
            icon = {"healthy": "🟢", "degraded": "🟡", "down": "🔴", "quarantined": "⛔", "unknown": "⬜"}.get(
                c["status"], "?"
            )
            print(f"  {icon} {c['core_id']:<35} {c['model_name']:<25} {c['status']}")
        s = r["summary"]
        print(
            f"\n  健康: {s['statuses'].get('healthy', 0)} | 降级: {s['statuses'].get('degraded', 0)} | 挂: {s['statuses'].get('down', 0)} | 隔离: {s['statuses'].get('quarantined', 0)}"
        )
        if s["critical_down"]:
            print(f"  ⚠️ Critical 核心挂: {', '.join(s['critical_down'])}")
    elif args.action == "probe":
        r = cli_cores_probe()
        print(f"🔍 探活完成 ({len(r)} 核)\n")
        for cid, res in r.items():
            icon = "🟢" if res["status"] == "healthy" else "🔴" if res["status"] == "down" else "⬜"
            print(f"  {icon} {cid}: {res['status']} {res.get('reason', '')}")
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


def _cmd_chaos(args) -> None:
    """处理 chaos 子命令。"""
    from ..governance import ChaosTester

    ct = ChaosTester()
    if args.action == "list":
        scenarios = ct.list_scenarios()
        print(f"🔥 混沌工程场景 ({len(scenarios)} 个)\n")
        for s in scenarios:
            print(f"  {s['id']:<20} {s['name']:<20} -> {s['target']}")
    elif args.action == "run":
        if not args.scenario:
            print("❌ --scenario 必填。可用场景:")
            for s in ct.list_scenarios():
                print(f"  {s['id']}")
            return 1
        r = ct.run(args.scenario, dry_run=not args.execute_now)
        print(f"{'✅' if r.passed else '❌'} {r.test_name}")
        print(f"  检测: {r.detection_time_ms}ms | 恢复: {r.recovery_time_ms or 'N/A'}ms")
        print(f"  备注: {r.notes}")
    elif args.action == "history":
        h = ct.history()
        print(f"📜 Chaos Test 历史 ({len(h)} 条)\n")
        for r in h:
            print(
                f"  {r.get('test_id', '')} | {r.get('test_name', '')} | {'✅' if r.get('passed') else '❌'} | {r.get('started_at', '')}"
            )
    return


def _cmd_module(args) -> None:
    """处理 module 子命令。"""
    from ..governance import ModuleHealthMonitor

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
        print("🔌 模块级协议摘要\n")
        print(f"  总计: {s['total']} | 🟢 {s['green']} | 🟡 {s['yellow']} | 🔴 {s['red']}")
    return


def _cmd_cluster(args) -> None:
    """处理 cluster 子命令。"""
    from ..governance import ClusterManager

    cm = ClusterManager()
    if args.action == "list":
        clusters = cm.list_clusters()
        print(f"🏗️ 集群列表 ({len(clusters)} 个)\n")
        for c in clusters:
            print(f"  {c['name']:<30} {c['core_id']:<35} {c['criticality']}")
    elif args.action == "status":
        statuses = cm.status()
        print(f"🏗️ 集群状态 ({len(statuses)} 个)\n")
        for s in statuses:
            icon = {"healthy": "🟢", "degraded": "🟡", "down": "🔴", "quarantined": "⛔", "unknown": "⬜"}.get(
                s["status"], "?"
            )
            print(f"  {icon} {s['cluster']:<30} {s['model']:<25} {s['status']}")
    elif args.action == "replace":
        if not args.name:
            print("❌ --name 必填。可用集群:")
            for c in cm.list_clusters():
                print(f"  {c['name']}")
            return 1
        r = cm.replace(args.name, source=args.source)
        print(f"{'✅' if r['ok'] else '❌'} {r.get('note', '')} (action recorded)")
    return


def _cmd_breaker(args) -> None:
    """处理 breaker 子命令。"""
    from ..circuit_breaker import CircuitBreaker

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


def main() -> None:
    """Mark42 CLI 入口 - 解析参数并分发到对应子命令处理函数。"""
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "default": _cmd_default,
        "install": _cmd_install,
        "watchdog": _cmd_watchdog,
        "logs": _cmd_logs,
        "armor": _cmd_armor,
        "engine": _cmd_engine,
        "heavy": _cmd_heavy,
        "compaction": _cmd_compaction,
        "assemble": _cmd_assemble,
        "context-safety": _cmd_context_safety,
        "status": _cmd_status,
        "archive": _cmd_archive,
        "consciousness": _cmd_consciousness,
        "cores": _cmd_cores,
        "chaos": _cmd_chaos,
        "module": _cmd_module,
        "cluster": _cmd_cluster,
        "breaker": _cmd_breaker,
    }

    if not args.module:
        _cmd_default(args)
        return

    handler = dispatch.get(args.module)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
