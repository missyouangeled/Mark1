"""Mark42 模块B：循环引擎 Engine。
Loop 注册/执行/终止 + daemon 守护 + 模板路由。
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import (
    ENGINE_STATE, HEAVY_STATE, MARK42_BROKER_EVENTS, BROKER_EVENTS, BROKER_DIR, SCRATCH, THRESHOLD_ALERT, THRESHOLD_WARN, WORKSPACE,
)
from .utils import (
    _append_broker, _load_json, _now_iso, _now_ts, _save_json,
)
from .armor import armor_check, armor_compress
from .logs import log_rotate

ENGINE_LOOPS = ENGINE_STATE / "loops.json"


def _engine_status_path() -> Path:
    return ENGINE_STATE


def _load_loops() -> dict[str, Any]:
    return _load_json(ENGINE_LOOPS)


def _save_loops(loops: dict[str, Any]) -> None:
    ENGINE_STATE.mkdir(parents=True, exist_ok=True)
    # ── 文件锁：防止 daemon 和 cli 并发写入互相覆盖 ──
    import fcntl
    lock_path = str(ENGINE_LOOPS) + ".lock"
    # 用 "a" 模式避免 truncate 已有内容；如文件不存在则创建
    with open(lock_path, "a") as lf:
        try:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            _save_json(ENGINE_LOOPS, loops)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def engine_templates() -> None:
    """列出所有可用 Loop 模板。"""
    print("🔄 可用 Loop 模板:\n")
    templates = [
        ("context-guard", "300s",
         "持续监控上下文健康 + 自动出手\n"
         "     Observe: armor --check\n"
         "     Decide:  if usage > 85% → trigger compress; if > 70% → warn\n"
         "     Act:     armor --compress"),
        ("health-watch", "600s",
         "系统健康监控（CPU/内存/磁盘）\n"
         "     Observe: free -h && df -h / /mnt/data\n"
         "     Decide:  if disk < 5GB or mem < 500MB → alert\n"
         "     Act:     write broker warning event"),
        ("model-fallback", "60s",
         "监测模型可用性状态\n"
         "     Observe: 扫描 broker 事件中 model.fallback 信号\n"
         "     Decide:  检测到故障 → 写 Mark42 broker 警告\n"
         "     Act:     在 status dashboard 展示 failover 历史\n"
         "     ⚠️ 模型切换由 OpenClaw 内置 failover 自动完成，铠甲不接管"),
        ("task-watch", "30s",
         "大工程执行 + 全程护航\n"
         "     Observe: heavy task status via scratch/{name}/status.json\n"
         "     Decide:  if stalled → alert; if done → verify; if failed → retry\n"
         "     Act:     notify frontstage via broker"),
        ("memory-index", "21600s",
         "记忆自动归类——扫描最近 daily 文件 + 更新 INDEX.md 锚点\n"
         "     Observe: 扫描最近 7 天 memory/daily/ 文件\n"
         "     Decide:  识别新主题/事件/改进要求 → 追加到 memory/INDEX.md\n"
         "     Act:     写入 memory/INDEX.md 主题锚点条目（去重）"),
    ]
    for name, period, desc in templates:
        print(f"  📋 {name}")
        print(f"     {desc}")
        print(f"     周期: {period}\n")


def engine_list() -> None:
    """列出所有活跃 Loop。"""
    loops = _load_loops()
    if not loops:
        print("🔄 暂无活跃 Loop")
        return
    print("🔄 活跃 Loop 清单:\n")
    for name, loop in loops.items():
        status = loop.get("status", "?")
        interval = loop.get("interval", "?")
        cycle = loop.get("cycle", 0)
        max_c = loop.get("maxCycles", 0)
        template = loop.get("template", "-")
        task = loop.get("task", "-")
        print(f"  📋 {name}")
        print(f"     状态: {status}  |  周期: {interval}s  |  循环: {cycle}/{max_c or '∞'}")
        if template:
            print(f"     模板: {template}")
        print(f"     任务: {task}\n")


def engine_start(task: str, interval_s: int = 300, max_cycles: int = 0, template: str = "") -> None:
    """注册一个新的 Loop。"""
    loops = _load_loops()
    name = template if template else f"loop-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if name in loops and not template:
        print(f"⚠️ Loop '{name}' 已存在，覆盖注册")
    elif name in loops:
        existing = loops[name]
        # 如果同名 Loop 仍在活跃状态（非 killed），提示用户并覆盖为活跃
        if existing.get("status", "killed") not in ("killed",):
            print(f"⚠️ Loop '{name}' 已存在且活跃（状态: {existing.get('status')})，将被覆盖")
    loops[name] = {
        "task": task,
        "interval": interval_s,
        "maxCycles": max_cycles or None,
        "template": template,
        "status": "registered",
        "cycle": 0,
        "lastRun": None,
        "lastResult": None,
        "createdAt": _now_iso(),
    }
    _save_loops(loops)
    template_desc = f" — {engine_templates.__doc__}" if template else ""
    print(f"🔄 Loop '{name}' 已注册")
    print(f"   任务: {task}")
    print(f"   周期: {interval_s}s  |  最大循环: {max_cycles or '无限'}")
    if template:
        print(f"   模板: {template}{template_desc}" if False else f"   模板: {template}")
    if template:
        print(f"   执行: python3 scripts/mark42.py engine --run {name}")
        print(f"   监控: python3 scripts/mark42.py engine --watch-task {name}")


def engine_kill(name: str) -> None:
    """终止一个 Loop。"""
    loops = _load_loops()
    if name not in loops:
        print(f"❌ Loop '{name}' 不存在")
        return
    old_status = loops[name].get("status", "?")
    loops[name]["status"] = "killed"
    loops[name]["killedAt"] = _now_iso()
    _save_loops(loops)
    print(f"💀 Loop '{name}' 已终止（原状态: {old_status})")


def engine_watch_task(task_name: str, interval_s: int = 30) -> None:
    """监控一个大工程任务的进度。"""
    task_dir = SCRATCH / task_name
    status_file = task_dir / "status.json"
    if not status_file.exists():
        print(f"❌ 任务状态文件不存在: {status_file}")
        return
    print(f"🔍 监控大工程: {task_name} (每 {interval_s}s)")
    print(f"   状态文件: {status_file}")
    try:
        while True:
            st = _load_json(status_file)
            if not st:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 状态文件为空")
                time.sleep(interval_s)
                continue
            subtasks = st.get("subtasks", {})
            total = len(subtasks)
            pending = sum(1 for s in subtasks.values() if s.get("status") == "pending")
            running = sum(1 for s in subtasks.values() if s.get("status") == "running")
            done = sum(1 for s in subtasks.values() if s.get("status") in ("done", "completed"))
            failed = sum(1 for s in subtasks.values() if s.get("status") in ("failed", "error"))
            ts = datetime.now().strftime("%H:%M:%S")
            pct = f"{(done + failed) / max(total, 1) * 100:.0f}%"
            print(f"[{ts}] {task_name}: {pct} | ✅ {done} ⏳ {pending} 🏃 {running} ❌ {failed}")
            if failed > 0:
                _append_broker("tasks", "heavy.subtask.failed",
                               f"子任务失败: {task_name}", "warn",
                               f"{failed}/{total} 子任务失败",
                               {"taskName": task_name, "failed": failed, "total": total})
            if pending == 0 and running == 0 and done + failed == total:
                print(f"\n🎉 任务 '{task_name}' 所有子任务已完成！")
                if failed == 0:
                    print(f"   ✅ 全部成功 ({total}/{total})")
                    print(f"   建议运行: python3 scripts/mark42.py heavy --finish --task-name {task_name}")
                else:
                    print(f"   ⚠️ {failed}/{total} 失败，需人工检查")
                _append_broker("tasks", "heavy.task.completed",
                               f"大工程完成: {task_name}", "ok",
                               f"{done}/{total} 成功, {failed} 失败",
                               {"taskName": task_name, "done": done, "failed": failed})
                break
            time.sleep(interval_s)
    except KeyboardInterrupt:
        print(f"\n🔍 监控已退出（任务 '{task_name}' 仍在运行中）")


def engine_run_loop(name: str, persist: bool = True, _loops: dict[str, Any] | None = None) -> None:
    """手动触发 Loop 执行 — Observe→Decide→Act→Verify 闭环。
    persist=True（默认）：执行后持久化到磁盘。daemon 应传 persist=False + _loops。
    _loops: daemon 传入当前 loops 引用，避免再 load（避免丢失并行修改）。
    """
    loops = _loops if _loops is not None else _load_loops()
    if name not in loops:
        print(f"❌ Loop '{name}' 不存在")
        return
    loop = loops[name]
    loop["status"] = "running"
    loop["lastRun"] = _now_iso()
    _save_loops(loops)
    template_name = loop.get("template", "")
    task = loop["task"]
    print(f"▶️ 执行 Loop '{name}': {task}")
    if template_name == "context-guard":
        check = armor_check()
        usage = check.get("usagePercent", 0)
        print(f"   🔍 Observe: 上下文 {usage}%")
        if usage >= THRESHOLD_ALERT:
            print(f"   🟠 Decide: 超 ALERT 阈值 ({THRESHOLD_ALERT}%)，触发压缩")
            result = armor_compress()
            verify = armor_check()
            new_usage = verify.get("usagePercent", 0)
            print(f"   ✅ Verify: {usage}% → {new_usage}%")
            loop["lastResult"] = {"action": "compress", "before": usage, "after": new_usage}
        else:
            print(f"   ✅ Decide: 未达阈值，继续监控")
            loop["lastResult"] = {"action": "monitor", "usage": usage}
    elif template_name == "task-watch":
        heavy_tasks = list(HEAVY_STATE.glob("*.json"))
        active_tasks = []
        for tf in heavy_tasks:
            ts = _load_json(tf)
            if ts.get("status") == "started":
                active_tasks.append(ts.get("taskName"))
        print(f"   🔍 Observe: {len(active_tasks)} 活跃重型任务")
        pending = 0
        failed = 0
        for tn in active_tasks:
            status_file = SCRATCH / tn / "status.json"
            st = _load_json(status_file) if status_file.exists() else {}
            p = sum(1 for s in st.get("subtasks", {}).values() if s.get("status") == "pending")
            f = sum(1 for s in st.get("subtasks", {}).values() if s.get("status") in ("failed", "error"))
            pending += p
            failed += f
            print(f"      {tn}: {p} pending, {f} failed")
        loop["lastResult"] = {"activeTasks": active_tasks, "pending": pending, "failed": failed}
    elif template_name == "health-watch":
        try:
            import shutil
            # 使用 shutil.disk_usage 替代脆弱的 df -h 解析
            root_usage = shutil.disk_usage("/")
            disk_root_gb = root_usage.free / (1024**3)
            disk_root = f"{disk_root_gb:.1f}G"
            data_usage = shutil.disk_usage("/mnt/data") if Path("/mnt/data").exists() else None
            disk_data = f"{data_usage.free / (1024**3):.1f}G" if data_usage else "N/A"
            with open("/proc/meminfo") as f:
                meminfo = {line.split()[0].rstrip(":"): int(line.split()[1]) for line in f if line}
            mem_avail_mb = meminfo.get("MemAvailable", 0) // 1024
            mem_avail = f"{mem_avail_mb}M"
        except Exception:
            disk_root, disk_data, mem_avail = "?", "?", "?"
            disk_root_gb, mem_avail_mb = 100, 1000
        print(f"   🩺 根盘: {disk_root} | 数据盘: {disk_data} | 可用内存: {mem_avail}")
        alerts = []
        if disk_root_gb < 5:
            alerts.append(f"磁盘不足 ({disk_root})")
        if mem_avail_mb < 500:
            alerts.append(f"内存紧张 ({mem_avail})")
        if alerts:
            print(f"   ⚠️ 告警: {', '.join(alerts)}")
            _append_broker("health", "engine.health.warn", "系统资源告警", "warn", ", ".join(alerts), {})
        loop["lastResult"] = {"diskRoot": disk_root, "diskData": disk_data, "memAvail": mem_avail, "alerts": alerts}
    elif template_name == "model-fallback":
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:18788/healthz", timeout=5)
            gw_ok = resp.status == 200
        except Exception:
            gw_ok = False
        print(f"   🔍 Gateway: {'✅ 正常' if gw_ok else '❌ 不可达'}")
        loop["lastResult"] = {"gatewayOk": gw_ok}
        if not gw_ok:
            _append_broker("health", "engine.model.fallback", "Gateway 不可达", "error",
                           "Gateway health check 失败", {})
    else:
        task_lower = task.lower()
        if "context" in task_lower or "armor" in task_lower or "上下文" in task_lower:
            result = armor_compress()
            loop["lastResult"] = {"action": result.get("action"), "usage": result.get("preCompressUsage")}
        else:
            loop["lastResult"] = {"action": "executed", "note": "通用任务"}
    
    # ── C 项：Loop 执行完成 → emit 标准化事件 ──
    _append_broker("engine", "mark42.engine.loop.completed",
                   f"Loop '{name}' 执行完成",
                   "ok" if not isinstance(loop.get("lastResult"), dict) or
                           not loop["lastResult"].get("alerts") else "warn",
                   f"模板: {template_name or '通用'} | cycle {loop.get('cycle',0)+1}",
                   {"loopName": name, "template": template_name or "generic",
                    "lastResult": loop.get("lastResult", {})})
    loop["cycle"] = loop.get("cycle", 0) + 1
    loop["status"] = "done"
    if loop.get("maxCycles") and loop["cycle"] >= loop["maxCycles"]:
        loop["status"] = "completed"
    else:
        loop["status"] = "registered"
    # 持久化策略：daemon 路径传 persist=False，由 daemon 统一写；CLI 手动路径默认持久化
    if persist:
        _save_loops(loops)
    max_display = loop.get("maxCycles") or "∞"
    print(f"✅ Loop '{name}' 完成 (cycle {loop['cycle']}/{max_display})")


def engine_daemon(interval_s: int = 30) -> None:
    """守护进程：扫描 broker 事件 + 执行 Loop。"""
    print("🔄 循环引擎守护模式启动")
    print(f"   扫描间隔: {interval_s}s")
    print(f"   按 Ctrl+C 退出\n")
    cursor_file = ENGINE_STATE / "daemon-cursor.json"
    cursor = _load_json(cursor_file) if cursor_file.exists() else {}
    rotation_check_count = 0
    try:
        while True:
            loops = _load_loops()
            ts = datetime.now().strftime("%H:%M:%S")
            # ── 1. 扫描 broker 事件 ──
            for event_file in [BROKER_EVENTS, MARK42_BROKER_EVENTS]:
                if not event_file.exists():
                    continue
                try:
                    file_key = str(event_file)
                    cursor_offset = cursor.get(file_key, 0)
                    with open(event_file, "r") as f:
                        f.seek(cursor_offset)
                        new_lines = f.readlines()
                        cursor[file_key] = f.tell()
                except OSError:
                    new_lines = []
                for line in new_lines:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    source_evt = event.get("sourceEventType", "")
                    metadata = event.get("metadata", {})
                    # ── C 项标准化事件桥接：Engine ↔ Armor ↔ Heavy ──
                    # 压缩完成 → 记录并评估是否需要触发 context-guard Loop
                    if source_evt == "mark42.armor.compress.done":
                        usage = metadata.get("usagePercent", 0)
                        strategy = metadata.get("strategy", "?")
                        print(f"[{ts}] 🧠 检测到铠甲压缩完成 (策略: {strategy}, 使用率: {usage}%)")
                        _append_broker("engine", "mark42.engine.bridge.armor_compress_seen",
                                       f"Engine 已收到压缩完成信号", "ok",
                                       f"策略: {strategy} | 使用率: {usage}%",
                                       {"bridgeEvent": "armor.compress.done", "usagePercent": usage})
                    # ── 压缩联动：上下文危险 → 建议 /compact ──
                    if "compaction.advised" in source_evt:
                        usage = metadata.get("usagePercent", 0)
                        print(f"[{ts}] 🚨 上下文 {usage}% — 强烈建议在聊天中执行 /compact")
                        _append_broker("health", "engine.compaction.alerted",
                                       f"建议压缩: {usage}%", "warn",
                                       f"Armor 建议手动执行 /compact",
                                       {"usagePercent": usage})
                    # ── 系统级上下文告警 → 异步触发压缩（不阻塞 daemon 主循环） ──
                    if "context_monitor.alert" in source_evt or "context_monitor.critical" in source_evt:
                        usage = metadata.get("usagePercent", 0)
                        if usage >= THRESHOLD_ALERT:
                            print(f"[{ts}] 🟠 收到上下文告警 ({usage}%)，启动压缩子进程")
                            script = str(Path(__file__).resolve().parent.parent / "mark42.py")
                            try:
                                subprocess.Popen(
                                    [sys.executable, "-u", script, "armor", "--compress"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True,
                                )
                            except subprocess.SubprocessError as e:
                                print(f"[{ts}] ❌ 启动压缩子进程失败: {e}")
                    # ── 模型故障检测（只感知，不切换 — OpenClaw 内置 failover 接管） ──
                    if "model.fallback" in source_evt or "engine.model.fallback" in source_evt:
                        summary = event.get("summary", "")
                        print(f"[{ts}] ⚠️ 检测到模型故障信号: {summary}")
                        print(f"      OpenClaw 内置 failover 将自动切换备用模型")
                        _append_broker("health", "engine.model.fallback.detected",
                                       f"模型故障: {summary}", "warn",
                                       f"已记录，failover 由 OpenClaw 接管",
                                       {"signal": source_evt, "summary": summary})
                    # ── Heavy 开工 → 自动创建 task-watch Loop（守卫：必须真实存在） ──
                    if "heavy.task.started" in source_evt:
                        task_name = metadata.get("taskName", "?")
                        # 守卫：检查 Heavy 任务文件是否确实存在且未过期（24h）
                        task_file = HEAVY_STATE / f"{task_name}.json"
                        task_valid = False
                        if task_file.exists():
                            td = _load_json(task_file)
                            td_ts = td.get("startedAt") or td.get("checkedAt", "")
                            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
                            try:
                                started_dt = _dt.fromisoformat(td_ts)
                                if _dt.now(_tz.utc) - started_dt < _td(hours=24):
                                    task_valid = True
                            except Exception:
                                pass
                        if not task_valid:
                            print(f"[{ts}] ℹ️ Heavy 开工信号但任务文件无效/过期 ({task_name})，跳过创建 watch")
                            continue
                        print(f"[{ts}] ⚙️ 检测到 Heavy 任务开工: {task_name}")
                        loops2 = _load_loops()
                        watch_name = f"watch-{task_name}"
                        if watch_name not in loops2:
                            engine_start(task=f"监控大工程: {task_name}", interval_s=30,
                                         template="task-watch")
                        _append_broker("engine", "mark42.engine.bridge.heavy_started",
                                       f"Engine 已为 Heavy 任务创建监控 Loop", "ok",
                                       f"任务: {task_name}",
                                       {"taskName": task_name})
            # ── 2. 重新加载 loops（处理 broker 事件中可能新增的） ──
            loops = _load_loops()
            # ── 3. 执行到期 Loop ──
            executed_any = False
            for name, loop in list(loops.items()):
                status = loop.get("status", "")
                if status not in ("registered",):
                    continue
                last_run = loop.get("lastRun", "")
                if last_run:
                    try:
                        last_ts = datetime.fromisoformat(last_run).timestamp()
                        if _now_ts() - last_ts < loop.get("interval", 300):
                            continue
                    except Exception:
                        pass
                # 每个 Loop 执行前重新加载最新状态（避免多 Loop 同 tick 竞态）
                fresh_loops = _load_loops()
                if name in fresh_loops:
                    loops[name] = fresh_loops[name]
                print(f"[{ts}] ▶️ 触发 Loop '{name}'")
                engine_run_loop(name, persist=False, _loops=loops)
                executed_any = True
            # 统一持久化：所有到期 Loop 执行完后一次性写入
            if executed_any:
                _save_loops(loops)
            # ── 4. 保存游标 ──
            _save_json(cursor_file, {**cursor, "lastScan": _now_iso()})
            # ── 5. 每 10 次循环做一次 log rotation + mark42 状态快照 ──
            rotation_check_count += 1
            if rotation_check_count % 10 == 0:
                log_rotate("all")
                # D 项：把 Mark42 状态 JSON 写入 broker views，供 Control UI 消费
                try:
                    from .cli import status_dashboard
                    status_json = status_dashboard(json_mode=True)
                    if status_json:
                        BROKER_VIEWS = BROKER_DIR / "views"
                        BROKER_VIEWS.mkdir(parents=True, exist_ok=True)
                        _save_json(BROKER_VIEWS / "mark42-status.json", {
                            "checkedAt": status_json["checkedAt"],
                            "armor": status_json["armor"],
                            "engine": status_json["engine"],
                            "heavy": status_json["heavy"],
                            "actions": status_json["actions"],
                        })
                except Exception:
                    pass  # 守护模式下静默失败
            # ── 写入心跳文件 ──
            heartbeat_file = ENGINE_STATE / "daemon-heartbeat.json"
            _save_json(heartbeat_file, {"lastTick": _now_iso(), "cycle": rotation_check_count, "loops": len(loops)})
            # ── 每 20 次循环检查 daemon 日志大小（超额截尾，防止磁盘撑爆） ──
            if rotation_check_count % 20 == 0:
                # daemon 日志截尾统一委托给 logs.py 的 rotate_daemon_logs
                # （每 10 周期/300s 已调用 log_rotate("all")，此处做额外检查）
                pass
            time.sleep(interval_s)
    except KeyboardInterrupt:
        _save_json(cursor_file, {**cursor, "lastScan": _now_iso()})
        print("\n🔄 守护模式已退出")
