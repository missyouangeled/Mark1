"""Mark42 CLI - 状态面板模块。

收集和展示 Armor/Engine/Heavy/Logs 全系统状态。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..output_guard import trim_detail, trim_summary


def _collect_status_data() -> dict[str, Any]:
    """收集所有子系统状态数据，返回统一 dict。"""
    from ..armor import armor_check
    from ..config import (
        ARMOR_STATE,
        CONFIG_PATH,
        ENGINE_STATE,
        HEAVY_STATE,
        MARK42_BROKER_EVENTS,
        SCRATCH,
        THRESHOLD_ALERT,
        THRESHOLD_WARN,
    )
    from ..utils import _load_json

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    check = armor_check()
    usage = check.get("usagePercent", 0)
    status_icon = "🟢" if usage < THRESHOLD_WARN else ("🟠" if usage < THRESHOLD_ALERT else "🔴")

    version = "?"
    if CONFIG_PATH.exists():
        version = _load_json(CONFIG_PATH).get("version", "?")

    index_path = ARMOR_STATE / "memory-index.json"
    idx = None
    gen_time = None
    strat = None
    if index_path.exists():
        idx = _load_json(index_path)
        gen_time = idx.get("generatedAt", "?")
        strat = idx.get("strategyUsed", "?")

    loops = _load_json(ENGINE_STATE / "loops.json")
    active = sum(1 for _l in loops.values() if _l.get("status") in ("registered", "running"))
    total = len(loops)

    heavy_tasks = list(HEAVY_STATE.glob("*.json"))

    from ..logs import _load_state as _logs_state

    ls = _logs_state()
    last_rot = ls.get("lastRotation", "从未")
    count = ls.get("rotationCount", 0)

    broker_lines = 0
    broker_size = 0
    if MARK42_BROKER_EVENTS.exists():
        broker_size = MARK42_BROKER_EVENTS.stat().st_size
        broker_lines = sum(1 for _ in open(MARK42_BROKER_EVENTS))

    dirs: list[Any] = []
    kept = 0
    if SCRATCH.exists():
        dirs = [d for d in SCRATCH.iterdir() if d.is_dir()]
        kept = sum(1 for d in dirs if (d / ".keep").exists())

    return {
        "now_str": now_str,
        "check": check,
        "usage": usage,
        "status_icon": status_icon,
        "version": version,
        "idx": idx,
        "gen_time": gen_time,
        "strat": strat,
        "loops": loops,
        "active": active,
        "total": total,
        "heavy_tasks": heavy_tasks,
        "last_rot": last_rot,
        "count": count,
        "broker_lines": broker_lines,
        "broker_size": broker_size,
        "dirs": dirs,
        "kept": kept,
    }


def _format_status_text(d: dict[str, Any], verbose: bool = False) -> str:
    """将状态数据格式化为人类可读文本。"""
    from ..config import THRESHOLD_WARN
    from ..utils import _load_json

    lines = []
    lines.append("\n" + "=" * 56)
    lines.append("  🦾 Mark42 系统状态")
    lines.append("=" * 56)
    lines.append(f"  检查时间: {d['now_str']}\n")
    lines.append("  🛡️ 上下文铠甲")
    lines.append(f"     {d['status_icon']} {d['usage']}% ({trim_summary(d['check'].get('summary', ''), 100)})")
    if d["idx"]:
        lines.append(f"     🧠 索引: {d['strat']} ({d['gen_time'][:16] if d['gen_time'] else '?'})")
    else:
        lines.append("     🧠 索引: 无")
    lines.append("\n  🔄 循环引擎")
    lines.append(f"     Loop: {d['active']} 活跃 / {d['total']} 注册")
    if d["loops"]:
        for name, loop in sorted(d["loops"].items()):
            cyc = loop.get("cycle", 0)
            max_c = loop.get("maxCycles")
            stat = loop.get("status")
            icon = "▶️" if stat == "running" else ("⏸️" if stat == "registered" else "⏹")
            lines.append(f"     {icon} {name}: {stat} (cycle {cyc}/{max_c or '∞'})")
            if verbose and loop.get("task"):
                lines.append(f"        task: {trim_detail(loop.get('task'), 160)}")
    lines.append("\n  ⚙️ 重型战甲")
    if d["heavy_tasks"]:
        for tf in sorted(d["heavy_tasks"]):
            ts = _load_json(tf)
            name = ts.get("taskName", "?")
            stat = ts.get("status", "?")
            tsum = ts.get("summary", "")
            icon = "🔄" if stat == "started" else ("✅" if stat == "finished" else "⏳")
            lines.append(f"     {icon} {name}: {stat} - {trim_summary(tsum, 100)}")
            if verbose and ts.get("checkedAt"):
                lines.append(f"        checkedAt: {ts.get('checkedAt')}")
    else:
        lines.append("     ℹ️ 无活跃任务")
    lines.append("\n  🧹 日志轮替")
    lines.append(f"     上次: {d['last_rot']} (累计 {d['count']} 次)")
    from ..config import MARK42_BROKER_EVENTS, SCRATCH

    if MARK42_BROKER_EVENTS.exists():
        lines.append(f"     Mark42 Broker: {d['broker_size'] / 1024:.1f}KB ({d['broker_lines']} 行)")
    if SCRATCH.exists():
        lines.append(f"     Scratch: {len(d['dirs'])} 目录 ({d['kept']} 受保护)")
    lines.append("\n  ── 快速操作 ──")
    if d["usage"] >= THRESHOLD_WARN:
        lines.append("     ⚠️ 上下文偏高 -> 建议: /compact")
    if d["active"] == 0:
        lines.append("     💡 引擎空闲 -> 注册: engine --start")
    lines.append("=" * 56 + "\n")
    return "\n".join(lines)


def _build_status_json(d: dict[str, Any]) -> dict[str, Any]:
    """从状态数据构建 JSON 输出结构。"""
    from ..config import MARK42_BROKER_EVENTS, SCRATCH, THRESHOLD_WARN
    from ..utils import _load_json

    check = d["check"]
    idx = d["idx"]
    loops = d["loops"]
    heavy_tasks = d["heavy_tasks"]

    status_data: dict[str, Any] = {
        "checkedAt": d["now_str"],
        "version": d["version"],
        "armor": {
            "usagePercent": check.get("usagePercent", 0),
            "status": check.get("status", "?"),
            "severity": check.get("severity", "?"),
            "summary": check.get("summary", ""),
            "contextWindow": check.get("contextWindow", 0),
            "estimatedTokens": check.get("estimatedTokens", 0),
            "memoryIndex": {
                "strategy": idx.get("strategyUsed", "?") if idx else "none",
                "generatedAt": idx.get("generatedAt") if idx else None,
                "modelGenerated": idx.get("modelGenerated", False) if idx else False,
            }
            if idx
            else None,
        },
        "engine": {
            "activeLoops": d["active"],
            "totalLoops": d["total"],
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
                for tf in heavy_tasks
                for ts in [_load_json(tf)]
            ],
        },
        "logs": {
            "lastRotation": d["last_rot"],
            "rotationCount": d["count"],
        },
        "broker": {
            "mark42Events": d["broker_lines"] if MARK42_BROKER_EVENTS.exists() else 0,
            "mark42SizeKB": round(d["broker_size"] / 1024, 1) if MARK42_BROKER_EVENTS.exists() else 0,
        },
        "scratch": {
            "totalDirs": len(d["dirs"]) if SCRATCH.exists() else 0,
            "keptDirs": d["kept"] if SCRATCH.exists() else 0,
        },
        "actions": [],
    }
    if d["usage"] >= THRESHOLD_WARN:
        status_data["actions"].append("建议 /compact")
    if d["active"] == 0:
        status_data["actions"].append("引擎空闲，建议注册 Loop")
    return status_data


def status_dashboard(json_mode: bool = False, verbose: bool = False) -> dict[str, Any] | None:
    """一屏聚合 Armor/Engine/Heavy/Logs 状态。

    json_mode=True 返回 dict，不打印。
    """
    d = _collect_status_data()
    if json_mode:
        return _build_status_json(d)
    print(_format_status_text(d, verbose=verbose))
    return None
