"""Mark42 模块B：循环引擎 Engine。
Loop 注册/执行/终止 + daemon 守护 + 模板路由。
"""

import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None

from .config import (
    ENGINE_STATE, HEAVY_STATE, MARK42_BROKER_EVENTS, BROKER_EVENTS, BROKER_DIR, SCRATCH, THRESHOLD_ALERT, THRESHOLD_WARN, WORKSPACE,
    LOOP_TEMPLATES_PATH, USER_LOOP_TEMPLATES_PATH,
)
from .utils import (
    _append_broker, _load_json, _now_iso, _now_ts, _save_json,
)
from .interfaces import get_compress

from .output_guard import trim_detail, trim_summary
from .logs import log_rotate

ENGINE_LOOPS = ENGINE_STATE / "loops.json"


# ── 内置默认模板（代码兜底） ──
_BUILTIN_TEMPLATES = {
    "context-guard": {"period": 300, "description": "持续监控上下文健康 + 自动出手"},
    "task-watch": {"period": 30, "description": "大工程执行 + 全程护航"},
    "health-watch": {"period": 600, "description": "系统健康监控（CPU/内存/磁盘）"},
    "model-fallback": {"period": 60, "description": "监测模型可用性状态"},
    "memory-index": {"period": 21600, "description": "记忆自动归类——扫描最近 daily 文件 + 更新 INDEX.md 锚点"},
}


def _load_templates() -> dict[str, Any]:
    """加载 Loop 模板配置。
    
    优先级：
    1. 用户自定义模板（WORKSPACE/loop_templates.yaml）- 覆盖同名内置模板
    2. 内置模板配置文件（SCRIPTS/mark42/loop_templates.yaml）
    3. 代码硬编码兜底模板
    """
    templates = dict(_BUILTIN_TEMPLATES)
    
    # 加载内置配置文件
    if yaml and LOOP_TEMPLATES_PATH.exists():
        try:
            with open(LOOP_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict) and "templates" in data:
                    for name, cfg in data["templates"].items():
                        if isinstance(cfg, dict):
                            templates[name] = {
                                "period": cfg.get("period", 300),
                                "description": cfg.get("description", ""),
                            }
        except Exception:
            pass
    
    # 加载用户自定义配置（覆盖同名）
    if yaml and USER_LOOP_TEMPLATES_PATH.exists():
        try:
            with open(USER_LOOP_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict) and "templates" in data:
                    for name, cfg in data["templates"].items():
                        if isinstance(cfg, dict):
                            templates[name] = {
                                "period": cfg.get("period", 300),
                                "description": cfg.get("description", ""),
                            }
        except Exception:
            pass
    
    return templates


# ── G 项：Loop 模板热加载 ──
# 记录上次加载时的文件 mtime，daemon 用来检测变更
_template_cache: dict[str, Any] = {}
_template_mtimes: dict[str, float] = {}


def _check_template_files_changed() -> bool:
    """检查模板配置文件是否有变更（mtime 变化）。"""
    changed = False
    for path in [LOOP_TEMPLATES_PATH, USER_LOOP_TEMPLATES_PATH]:
        try:
            current_mtime = path.stat().st_mtime if path.exists() else 0.0
            stored_mtime = _template_mtimes.get(str(path), 0.0)
            if current_mtime != stored_mtime:
                _template_mtimes[str(path)] = current_mtime
                if stored_mtime > 0:  # 不是第一次加载
                    changed = True
        except OSError:
            pass
    return changed


def _get_templates_cached() -> dict[str, Any]:
    """获取模板（带缓存，文件变更时自动重载）。"""
    global _template_cache
    if not _template_cache or _check_template_files_changed():
        _template_cache = _load_templates()
        # 无论模板是否为空，都初始化 mtime 防止无限重载
        for path in [LOOP_TEMPLATES_PATH, USER_LOOP_TEMPLATES_PATH]:
            try:
                _template_mtimes[str(path)] = path.stat().st_mtime if path.exists() else 0.0
            except OSError:
                pass
    return _template_cache


def engine_reload_templates() -> dict[str, Any]:
    """手动重载模板配置（CLI 可调用）。"""
    global _template_cache
    old_count = len(_template_cache)
    _template_cache = _load_templates()
    new_count = len(_template_cache)
    # 更新 mtime 记录
    for path in [LOOP_TEMPLATES_PATH, USER_LOOP_TEMPLATES_PATH]:
        try:
            _template_mtimes[str(path)] = path.stat().st_mtime if path.exists() else 0.0
        except OSError:
            pass
    return {"oldCount": old_count, "newCount": new_count, "templates": list(_template_cache.keys())}


def _template_exists(name: str) -> bool:
    """检查模板名是否存在。"""
    return name in _get_templates_cached()


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
    templates = _get_templates_cached()
    for name, cfg in sorted(templates.items()):
        period = cfg.get("period", 300)
        desc = cfg.get("description", "")
        is_builtin = name in _BUILTIN_TEMPLATES
        builtin_tag = "" if is_builtin else " [自定义]"
        print(f"  📋 {name}{builtin_tag}")
        if desc:
            for line in desc.split("\n"):
                print(f"     {line}")
        print(f"     周期: {period}s\n")


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
    print(f"🔄 Loop '{name}' 已注册")
    print(f"   任务: {task}")
    print(f"   周期: {interval_s}s  |  最大循环: {max_cycles or '无限'}")
    if template:
        # 模板名验证
        if not _template_exists(template):
            print(f"   ⚠️ 模板 '{template}' 未在配置中定义，将使用通用执行路径")
        # 【L 修复 2026-06-30】只查模板的 docstring, 不用 f-string 空拼接
        # 原 template_desc = f" — {engine_templates.__doc__}" 是死代码, if False 进一步取消显示
        template_help = ""
        if engine_templates.__doc__:
            template_help = f" — {engine_templates.__doc__.split(chr(10))[0].strip()}"
        print(f"   模板: {template}{template_help}")
        print(f"   执行: python3 scripts/mark42.py engine --run {name}")
        print(f"   监控: python3 scripts/mark42.py engine --watch-task {name}")


def engine_kill(name: str) -> None:
    """终止一个 Loop。"""
    loops = _load_loops()
    if name not in loops:
        logger.error("Loop 不存在: %s", name); print(f"❌ Loop '{name}' 不存在")
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
        logger.error("任务状态文件不存在: %s", status_file); print(f"❌ 任务状态文件不存在: {status_file}")
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
        logger.error("Loop 不存在: %s", name); print(f"❌ Loop '{name}' 不存在")
        return
    loop = loops[name]
    loop["status"] = "running"
    loop["lastRun"] = _now_iso()
    _save_loops(loops)
    template_name = loop.get("template", "")
    task = loop["task"]
    print(f"▶️ 执行 Loop '{name}': {task}")
    if template_name == "context-guard":
        check = get_compress().check()
        usage = check.get("usagePercent", 0)
        print(f"   🔍 Observe: 上下文 {usage}%")
        # 平台优先 + Mark42 兜底 (2026-07-29):
        # armor_compress 内含平台探测期（60s 等平台自己 compact）+ compact 锁
        # - WARN 阶段: 只监控+预警
        # - ALERT 阶段: 触发 armor_compress 自主救场
        if usage >= THRESHOLD_ALERT:
            print(f"   🟠 Decide: 超 ALERT 阈值 ({THRESHOLD_ALERT}%)，启动自主救场")
            try:
                from .consciousness import Consciousness
                cs = Consciousness()
                issue = {"source": "armor", "category": "context_alert",
                         "severity": "critical", "value": usage,
                         "msg": f"上下文使用率 {usage}% 达到告警线"}
                handle_result = cs.handle_issue(issue, dry_run=False)
                path = handle_result.get("path", "")
                print(f"   🔗 v3-5 路由: {path}")
                loop["lastResult"] = {"action": "compress", "usage": usage, "v3_5_path": path}
            except Exception as e:
                print(f"   ⚠️ v3-5 链路异常: {e}，回退直接压缩")
                result = get_compress().compress()
                verify = get_compress().check()
                new_usage = verify.get("usagePercent", 0)
                print(f"   ✅ Verify: {usage}% -> {new_usage}%")
                loop["lastResult"] = {"action": "compress", "before": usage, "after": new_usage}
        elif usage >= THRESHOLD_WARN:
            print(f"   🟡 Decide: 超 WARN 阈值 ({THRESHOLD_WARN}%)，预警，等平台处理")
            loop["lastResult"] = {"action": "monitor", "usage": usage}
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
            # v3-5: 写错误档案（L5）+ 走 Consciousness 链路
            try:
                from .consciousness import Consciousness
                cs = Consciousness()
                issue = {"source": "engine", "category": "gateway_down",
                         "severity": "critical",
                         "msg": "Gateway 不可达"}
                handle_result = cs.handle_issue(issue, dry_run=True)
                print(f"   🔗 v3-5 路由: {handle_result.get('path', 'unknown')}")
                loop["lastResult"]["v3_5_path"] = handle_result.get("path", "")
            except Exception as e:
                print(f"   ⚠️ v3-5 链路异常: {e}")
    elif template_name == "memory-index":
        # 扫描最近 7 天 memory/daily/ 文件，更新 INDEX.md 主题锚点
        memory_dir = WORKSPACE / "memory" / "daily"
        index_path = WORKSPACE / "memory" / "INDEX.md"
        scanned = 0
        new_anchors = []
        if memory_dir.exists():
            from datetime import datetime as _dt, timedelta as _td
            # 用日期比较而非时间戳比较，避免 00:00:00 < 当前时刻导致跳过当天
            today = _dt.now().date()
            cutoff_date = today - _td(days=7)
            for df in sorted(memory_dir.glob("*.md"), reverse=True):
                try:
                    date_str = df.stem
                    dt = _dt.strptime(date_str, "%Y-%m-%d").date()
                    if dt < cutoff_date:
                        continue
                    scanned += 1
                    content = df.read_text()[:2000]
                    # 提取 ## 标题作为主题锚点
                    import re
                    topics = re.findall(r'^##\s+(.+)', content, re.MULTILINE)
                    for topic in topics:
                        anchor = f"- [{date_str}] {topic.strip()}"
                        if anchor not in new_anchors:
                            new_anchors.append(anchor)
                except Exception:
                    pass
            # 更新 INDEX.md
            if new_anchors:
                existing = index_path.read_text() if index_path.exists() else "# 记忆索引\n"
                # 只追加不重复的锚点
                added = 0
                for anchor in new_anchors[:20]:
                    if anchor not in existing:
                        existing += f"\n{anchor}"
                        added += 1
                if added > 0:
                    index_path.write_text(existing)
        print(f"   📋 记忆索引: 扫描 {scanned} 天, 新增 {len(new_anchors)} 个锚点")
        loop["lastResult"] = {"scannedDays": scanned, "newAnchors": len(new_anchors)}
    else:
        # 通用/自定义 Loop 回退
        if template_name:
            # 用户自定义模板（不含执行逻辑）- 使用 generic 路径
            print(f"   ℹ️ 自定义模板 '{template_name}' 使用通用执行路径")
            # 仅记录 broker 事件，不执行特定逻辑
            loop["lastResult"] = {
                "action": "executed",
                "template": template_name,
                "note": "自定义模板通用路径",
            }
        else:
            # 无模板的通用 Loop
            task_lower = task.lower()
            if "context" in task_lower or "armor" in task_lower or "上下文" in task_lower:
                result = get_compress().compress()
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
                    with open(event_file, "r", encoding="utf-8", errors="replace") as f:
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
                        print(trim_summary(f"[{ts}] 🧠 检测到铠甲压缩完成 (策略: {strategy}, 使用率: {usage}%)", 120))
                        _append_broker("engine", "mark42.engine.bridge.armor_compress_seen",
                                       f"Engine 已收到压缩完成信号", "ok",
                                       trim_detail(f"策略: {strategy} | 使用率: {usage}%", 160),
                                       {"bridgeEvent": "armor.compress.done", "usagePercent": usage})
                    # ── 压缩联动：上下文危险 → 建议 /compact ──
                    if "compaction.advised" in source_evt:
                        usage = metadata.get("usagePercent", 0)
                        print(trim_summary(f"[{ts}] 🚨 上下文 {usage}% — 强烈建议在聊天中执行 /compact", 120))
                        _append_broker("health", "engine.compaction.alerted",
                                       f"建议压缩: {usage}%", "warn",
                                       trim_detail("Armor 建议手动执行 /compact", 160),
                                       {"usagePercent": usage})
                    # ── 系统级上下文告警 → 异步触发压缩（不阻塞 daemon 主循环） ──
                    if "context_monitor.alert" in source_evt or "context_monitor.critical" in source_evt:
                        usage = metadata.get("usagePercent", 0)
                        if usage >= THRESHOLD_ALERT:
                            print(trim_summary(f"[{ts}] 🟠 收到上下文告警 ({usage}%)，启动压缩子进程", 120))
                            script = str(Path(__file__).resolve().parent.parent / "mark42.py")
                            try:
                                subprocess.Popen(
                                    [sys.executable, "-u", script, "armor", "--compress"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True,
                                )
                            except subprocess.SubprocessError as e:
                                print(trim_summary(f"[{ts}] ❌ 启动压缩子进程失败: {e}", 140))
                    # ── 模型故障检测（只感知，不切换 — OpenClaw 内置 failover 接管） ──
                    if "model.fallback" in source_evt or "engine.model.fallback" in source_evt:
                        summary = event.get("summary", "")
                        print(trim_summary(f"[{ts}] ⚠️ 检测到模型故障信号: {summary}", 140))
                        print(f"      OpenClaw 内置 failover 将自动切换备用模型")
                        _append_broker("health", "engine.model.fallback.detected",
                                       trim_summary(f"模型故障: {summary}", 120), "warn",
                                       trim_detail("已记录，failover 由 OpenClaw 接管", 160),
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
                            print(trim_summary(f"[{ts}] ℹ️ Heavy 开工信号但任务文件无效/过期 ({task_name})，跳过创建 watch", 140))
                            continue
                        print(trim_summary(f"[{ts}] ⚙️ 检测到 Heavy 任务开工: {task_name}", 120))
                        loops2 = _load_loops()
                        watch_name = f"watch-{task_name}"
                        if watch_name not in loops2:
                            engine_start(task=f"监控大工程: {task_name}", interval_s=30,
                                         template="task-watch")
                        _append_broker("engine", "mark42.engine.bridge.heavy_started",
                                       f"Engine 已为 Heavy 任务创建监控 Loop", "ok",
                                       trim_detail(f"任务: {task_name}", 160),
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
            # ── G 项：同时检查 Loop 模板文件是否变更 ──
            rotation_check_count += 1
            if rotation_check_count % 10 == 0:
                # G 项：模板热加载检测
                if _check_template_files_changed():
                    global _template_cache
                    _template_cache = _load_templates()
                    print(f"[{ts}] 🔄 Loop 模板已热重载 ({len(_template_cache)} 个模板)")
                    _append_broker("engine", "mark42.engine.templates.reloaded",
                                   "Loop 模板热重载", "ok",
                                   f"{len(_template_cache)} 个模板",
                                   {"templateCount": len(_template_cache)})
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
