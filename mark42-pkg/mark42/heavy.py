"""Mark42 模块C：重型战甲 Heavy。
大工程预检 + 上下文感知自动分批 + 收工验证。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .armor import armor_check, armor_compress
from .config import HEAVY_STATE, SCRATCH, THRESHOLD_ALERT, THRESHOLD_WARN
from .log_setup import get_logger
from .utils import _append_broker, _list_project_files, _load_json, _now_iso, _save_json

logger = get_logger(__name__)


def heavy_preflight(path_str: str) -> None:
    """大工程预检。"""
    p = Path(path_str).expanduser().resolve()
    logger.info(f"⚙️ 重型战甲预检: {p}\n")
    if not p.exists():
        logger.error(f"❌ 路径不存在: {p}")
        return
    files = _list_project_files(p)
    total_size = sum(f.stat().st_size for f in files)
    logger.info(f"📂 文件数: {len(files)}")
    logger.info(f"💾 总大小: {total_size / (1024 * 1024):.1f} MB")
    check = armor_check()
    usage = check.get("usagePercent", 0)
    remaining = 100 - usage
    logger.info(f"🧠 上下文余量: {remaining:.0f}% (当前 {usage}%)")
    if remaining < 20:
        logger.info("   ⚠️ 不足 — 强烈建议后台执行")
    elif remaining < 50:
        logger.info("   💡 偏紧 — 建议后台执行")
    else:
        logger.info("   ✅ 充足 — 可前台启动")
    mem = subprocess.run(["free", "-h"], capture_output=True, text=True).stdout
    for line in mem.splitlines():
        if line.startswith("Mem"):
            parts = line.split()
            mem = parts[1] if len(parts) > 1 else "?"
            break
    logger.info(f"🖥️ 内存: {mem}")
    for mp in ["/"]:
        # 如有数据盘可在此添加
        df = subprocess.run(["df", "-h", mp], capture_output=True, text=True).stdout.splitlines()
        if len(df) >= 2:
            parts = df[-1].split()
            if len(parts) >= 3:
                out = f"{parts[2]}/{parts[1]}"
            else:
                out = ""
        else:
            out = ""
        logger.info(f"💽 {mp}: 剩余 {out}" if out else "")


def heavy_detect(path_str: str) -> dict[str, Any]:
    """自动检测工程是否达到大工程标准，返回检测结果 dict。

    大工程标准（满足任一即触发）：
    - 文件数 >= 50
    - 总大小 >= 50MB
    - 嵌套层级 >= 5
    - 上下文余量 < 30%
    """
    p = Path(path_str).expanduser().resolve()
    result: dict[str, Any] = {
        "path": str(p),
        "exists": False,
        "isHeavy": False,
        "reasons": [],
        "metrics": {},
        "advice": "",
    }
    if not p.exists():
        result["advice"] = "路径不存在"
        return result
    result["exists"] = True

    # 使用公共扫描规则
    all_files = _list_project_files(p) if p.is_dir() else [p]
    max_depth = 0
    if p.is_dir():
        for f in all_files:
            depth = len(f.relative_to(p).parts)
            if depth > max_depth:
                max_depth = depth

    total_files = len(all_files)
    total_size = sum(f.stat().st_size for f in all_files)
    total_size_mb = total_size / (1024 * 1024)

    result["metrics"] = {
        "files": total_files,
        "sizeMB": round(total_size_mb, 2),
        "maxDepth": max_depth,
    }

    # 检查上下文
    check = armor_check()
    usage = check.get("usagePercent", 0)
    result["metrics"]["contextUsage"] = usage

    # 判定
    if total_files >= 50:
        result["isHeavy"] = True
        result["reasons"].append(f"文件数 {total_files} >= 50")
    if total_size_mb >= 50:
        result["isHeavy"] = True
        result["reasons"].append(f"总大小 {total_size_mb:.1f}MB >= 50MB")
    if max_depth >= 5:
        result["isHeavy"] = True
        result["reasons"].append(f"目录深度 {max_depth} >= 5 层")
    if usage > 70:
        result["isHeavy"] = True
        result["reasons"].append(f"上下文已用 {usage}% (>70%)，直接操作风险高")

    if result["isHeavy"]:
        result["advice"] = (
            f"检测到 {total_files} 文件 / {total_size_mb:.1f}MB，已达到大工程标准。"
            f"建议使用 heavy --start 开工，自动分批处理。"
        )
    else:
        result["advice"] = f"{total_files} 文件 / {total_size_mb:.1f}MB，未達大工程标准，可前台直接处理。"

    return result


def _auto_task_name(path_str: str) -> str:
    """从路径自动生成任务名。"""
    import datetime

    p = Path(path_str).expanduser().resolve()
    name = p.name if p.name else "大工程"
    ts = datetime.datetime.now().strftime("%m%d-%H%M")
    return f"{name}-{ts}"


def heavy_detect_human(path_str: str, auto_mode: str = "ask") -> None:
    """以人类可读格式输出检测结果。

    auto_mode:
      - "ask": 每次都问（默认，安全优先）
      - "semi": 半自动——检测到大工程后倒计时 30s，不拒绝就自动开工
      - "full": 全自动——直接开工
    """
    r = heavy_detect(path_str)
    if not r["exists"]:
        logger.error(f"❌ 路径不存在: {r['path']}")
        return
    m = r["metrics"]
    logger.info(f"🔍 大工程检测: {r['path']}")
    logger.info(f"   📂 {m['files']} 文件  |  💾 {m['sizeMB']:.1f}MB  |  📁 最深 {m['maxDepth']} 层")
    logger.info(f"   🧠 上下文: {m['contextUsage']}%")
    if not r["isHeavy"]:
        logger.info(f"\n✅ {r['advice']}")
        return

    logger.info("\n⚠️ 已达到大工程标准：")
    for reason in r["reasons"]:
        logger.info(f"   • {reason}")
    logger.info(f"\n💡 {r['advice']}")

    if auto_mode == "full":
        # 全自动：直接开工
        task_name = _auto_task_name(path_str)
        logger.info(f"\n🚀 全自动模式：直接开工 → {task_name}")
        heavy_start(path_str, task_name)
        return

    if auto_mode == "semi":
        # 半自动：倒计时 30s
        import time

        task_name = _auto_task_name(path_str)
        logger.info(f"\n⏳ 半自动模式：30 秒后自动开工 → {task_name}")
        logger.info("   拒绝：输入 'n' 或 Ctrl+C")
        logger.info("   立即开工：输入 'y' 或按回车跳过等待")
        try:
            import select

            logger.info("   ", end="", flush=True)
            for i in range(30, 0, -1):
                logger.info(f"\r   ⏳ {i}s... ", end="", flush=True)
                # 用 select 非阻塞检查 stdin 是否有输入
                rlist, _, _ = select.select([sys.stdin], [], [], 1.0)
                if rlist:
                    line = sys.stdin.readline().strip().lower()
                    if line in ("n", "no", "不", "拒绝"):
                        logger.info("\n❌ 已取消。手动开工:")
                        logger.info(f"   python3 scripts/mark42.py heavy --start {path_str} --task-name {task_name}")
                        return
                    elif line in ("y", "yes", "是", "好", "开", ""):
                        logger.info("\n✅ 立即开工")
                        heavy_start(path_str, task_name)
                        return
                time.sleep(1)
            # 倒计时结束，自动开工
            logger.info("\n✅ 倒计时结束，自动开工")
            heavy_start(path_str, task_name)
        except (KeyboardInterrupt, EOFError):
            logger.info("\n❌ 已取消。手动开工:")
            logger.info(f"   python3 scripts/mark42.py heavy --start {path_str} --task-name {task_name}")
        return

    # "ask" 模式：只提示
    task_name = _auto_task_name(path_str)
    logger.info("\n💡 手动开工命令:")
    logger.info(f"   python3 scripts/mark42.py heavy --start {path_str} --task-name {task_name}")


def heavy_start(path_str: str, task_name: str, context_aware: bool = True) -> None:
    """大工程开工 — 上下文感知自动分批。"""
    target = Path(path_str).expanduser().resolve()
    if not target.exists():
        logger.error(f"❌ 路径不存在: {target}")
        return
    task_dir = SCRATCH / task_name
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / ".keep").write_text("keep\n", encoding="utf-8")
    check = armor_check()
    usage = check.get("usagePercent", 0)
    logger.info(f"⚙️ 重型战甲开工: {task_name}")
    logger.info(f"   目标: {target}")
    logger.info(f"   Scratch: {task_dir}")
    logger.info(f"   🧠 上下文: {usage}%")
    if context_aware:
        if usage >= THRESHOLD_ALERT:
            logger.info("   ⚠️ 上下文偏高，自动触发压缩...")
            armor_compress()
        elif usage >= THRESHOLD_WARN:
            logger.info("   💡 建议后台执行（上下文偏紧）")
    files = _list_project_files(target)
    total_files = len(files)
    total_size = sum(f.stat().st_size for f in files)
    total_size_mb = total_size / (1024 * 1024)
    remaining_pct = 100 - usage
    # batch_size 公式：文件越多/上下文越紧 → 每批越小（上限 30，下限 1）
    # 【P 修复 2026-06-30】下限从 3 改为 1：1 个文件的任务也合理 (例如检测到的 .py 单文件)
    # 原 max(3, ...) 遇到 1 文件 + 100% 余量 = 0, max(3,0)=3, 实际只 1 文件被切成 1 批
    # 改后 max(1, ...)=1, 1 文件/1 批 更准确表达
    # 分母 200 是经验校准值：100 个文件、20% 余量 → 10 文件/批
    batch_size = max(1, min(30, int(total_files * remaining_pct / 200)))
    num_batches = max(1, (total_files + batch_size - 1) // batch_size)
    logger.info(f"   📂 文件: {total_files} 个 ({total_size_mb:.1f} MB)")
    logger.info(f"   📦 批次: {num_batches} 批 (每批 ≤{batch_size} 个文件)")
    batches = []
    for i in range(0, total_files, batch_size):
        chunk = files[i : i + batch_size]
        batches.append(
            {
                "id": f"batch-{len(batches) + 1:03d}",
                "files": [str(f.relative_to(target)) for f in chunk],
                "count": len(chunk),
                "sizeMB": round(sum(f.stat().st_size for f in chunk) / (1024 * 1024), 2),
            }
        )
    subtasks = {}
    for b in batches:
        subtasks[b["id"]] = {
            "status": "pending",
            "files": b["files"],
            "count": b["count"],
            "sizeMB": b["sizeMB"],
            "createdAt": _now_iso(),
        }
    init_status = {
        "taskName": task_name,
        "progress": "started",
        "targetPath": str(target),
        "summary": f"{total_files} 文件, {num_batches} 批次, {total_size_mb:.1f}MB",
        "subtasks": subtasks,
        "batchSize": batch_size,
        "totalBatches": num_batches,
        "lastUpdate": _now_iso(),
    }
    _save_json(task_dir / "status.json", init_status)
    heavy_status = HEAVY_STATE / f"{task_name}.json"
    _save_json(
        heavy_status,
        {
            "taskName": task_name,
            "targetPath": str(target),
            "scratchPath": str(task_dir),
            "status": "started",
            "startedAt": _now_iso(),
            "contextAware": context_aware,
            "preflightUsage": usage,
            "totalFiles": total_files,
            "totalSizeMB": round(total_size_mb, 2),
            "batches": len(batches),
        },
    )
    _append_broker(
        "tasks",
        "heavy.task.started",
        f"大工程开工: {task_name}",
        "ok",
        f"{total_files} 文件 | {num_batches} 批次 | {total_size_mb:.1f}MB",
        {"taskName": task_name, "totalFiles": total_files, "batches": num_batches},
    )
    logger.info("\n   📋 批次清单:")
    for b in batches:
        logger.info(f"      {b['id']}: {b['count']} 文件 ({b['sizeMB']:.1f}MB)")
    logger.info("\n✅ 已开工。使用以下命令监控：")
    logger.info(f"   python3 scripts/mark42.py engine --watch-task {task_name}")
    logger.info(f"   完工后: python3 scripts/mark42.py heavy --finish --task-name {task_name}")


def heavy_finish(task_name: str) -> None:
    """大工程收工校验。"""
    task_dir = SCRATCH / task_name
    status_file = task_dir / "status.json"
    if not status_file.exists():
        logger.error(f"❌ 任务 '{task_name}' 不存在")
        return
    st = _load_json(status_file)
    subtasks = st.get("subtasks", {})
    total = len(subtasks)
    done = sum(1 for s in subtasks.values() if s.get("status") in ("done", "completed"))
    failed = sum(1 for s in subtasks.values() if s.get("status") in ("failed", "error"))
    pending = sum(1 for s in subtasks.values() if s.get("status") == "pending")
    logger.info(f"🏁 大工程收工: {task_name}")
    logger.info(f"   结果: ✅ {done}/{total} 成功  |  ❌ {failed} 失败  |  ⏳ {pending} 未完成")
    if failed > 0 or pending > 0:
        logger.info("   ⚠️ 不建议收工，请先处理失败/未完成子任务")
        return
    heavy_status = HEAVY_STATE / f"{task_name}.json"
    hs = _load_json(heavy_status)
    hs["status"] = "finished"
    hs["finishedAt"] = _now_iso()
    _save_json(heavy_status, hs)
    st["progress"] = "finished"
    st["lastUpdate"] = _now_iso()
    _save_json(status_file, st)
    _append_broker(
        "tasks",
        "heavy.task.done",
        f"大工程收工: {task_name}",
        "ok",
        f"全部 {total} 子任务完成",
        {"taskName": task_name, "total": total},
    )
    logger.info(f"✅ 任务 '{task_name}' 已归档")


def heavy_execute(
    task_name: str, batch_id: str | None = None, command: str | None = None, execute_now: bool = False
) -> dict[str, Any]:
    """准备并（可选）执行大工程子任务 — 将 batch 分配给后台分身。
    不传 batch_id 则按序处理第一个 pending batch。

    【安全原则】（2026-06-30 审查后加强）：
      - 默认 execute_now=False：只生成脚本 + 标记为 running + 入队，**不真跑**
      - execute_now=True 显式才能真启动 bash 后台进程
      - 不传 --command → 脚本仅 echo 列出文件（no-op，不做任何修改）
      - 防“AI 忘了状态而误触” (“怕什么意外或自动压缩 你又不记得了”)

    Returns:
        dict 包含 action/script/queued/dry_run/started_pid 字段
    """
    task_dir = SCRATCH / task_name
    status_file = task_dir / "status.json"
    if not status_file.exists():
        logger.error(f"❌ 任务 '{task_name}' 未开工，请先 heavy --start")
        return
    st = _load_json(status_file)
    subtasks = st.get("subtasks", {})
    if not subtasks:
        logger.error("❌ 任务无子任务")
        return
    # 确定目标 batch
    target_id = batch_id
    if target_id:
        if target_id not in subtasks:
            logger.error(f"❌ 批次 '{target_id}' 不存在")
            return
        if subtasks[target_id]["status"] not in ("pending",):
            logger.warning(f"⚠️ 批次 '{target_id}' 状态为 '{subtasks[target_id]['status']}'，跳过")
            return
    else:
        for bid, bt in sorted(subtasks.items()):
            if bt.get("status") == "pending":
                target_id = bid
                break
        if not target_id:
            logger.info("✅ 所有批次已完成，无 pending 子任务")
            return
    batch = subtasks[target_id]
    files = batch.get("files", [])
    target_path = Path(st.get("targetPath", str(task_dir.parent)))
    logger.info(f"⚙️ 执行 {target_id}: {batch['count']} 文件 ({batch['sizeMB']:.2f}MB)")
    logger.info("   文件列表:")
    for f in files[:5]:
        logger.info(f"      {f}")
    if len(files) > 5:
        logger.info(f"      ... 共 {len(files)} 个")
    # 标记为 running
    batch["status"] = "running"
    batch["startedAt"] = _now_iso()
    st["lastUpdate"] = _now_iso()
    _save_json(status_file, st)
    # 生成执行脚本
    script_path, queue_file, exec_cmd, result = _heavy_build_script(
        task_dir, target_id, batch, target_path, task_name, files, command, execute_now
    )

    if execute_now:
        # 【真执行】仅在显式传 execute_now=True 才启动后台进程
        import subprocess

        try:
            log_path = task_dir / f"{target_id}-exec.log"
            log_fh = open(log_path, "a")
            proc = subprocess.Popen(
                ["/bin/bash", str(script_path)],
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # detach: 守护退出不影响子进程
            )
            result["action"] = "started"
            result["startedPid"] = proc.pid
            result["logPath"] = str(log_path)
            batch["pid"] = proc.pid
            batch["logPath"] = str(log_path)
            batch["dryRun"] = False
            st["lastUpdate"] = _now_iso()
            _save_json(status_file, st)
            _append_broker(
                "tasks",
                "heavy.batch.started",
                f"批次启动: {target_id} (PID {proc.pid})",
                "ok",
                f"任务: {task_name} | 脚本: {script_path.name} | 日志: {log_path.name}",
                {"taskName": task_name, "batchId": target_id, "pid": proc.pid, "dryRun": False},
            )
            logger.info(f"   🚀 启动后台进程 PID={proc.pid}")
            logger.info(f"   📄 日志: {log_path}")
        except Exception as e:
            result["action"] = "start_failed"
            result["error"] = str(e)
            logger.info(f"   ❌ 启动失败: {e}")
    else:
        logger.info(f"   📤 已入队: {queue_file}")
        logger.info(f"   执行脚本: {script_path}")
        if not command:
            logger.info("   ⚠️ 未传 --command，脚本仅 echo 列出文件（默认 no-op）")
        logger.info("   💡 仅入队，未启动。需 --execute-now 才真跑")
    return result


def heavy_execute_all(task_name: str, command: str | None = None, execute_now: bool = False) -> list[dict[str, Any]]:
    """自动准备所有 pending 子任务。默认仅入队，不传 execute_now 不真跑。"""
    task_dir = SCRATCH / task_name
    status_file = task_dir / "status.json"
    if not status_file.exists():
        logger.error(f"❌ 任务 '{task_name}' 未开工")
        return []
    st = _load_json(status_file)
    subtasks = st.get("subtasks", {})
    pending = [bid for bid, bt in subtasks.items() if bt.get("status") == "pending"]
    if not pending:
        logger.info("✅ 无 pending 子任务")
        return []
    logger.info(f"⚙️ 处理全部 {len(pending)} 个 pending 批次: {', '.join(pending)}")
    logger.info(f"   模式: {'DRY-RUN (仅入队)' if not execute_now else '真执行 (后台进程)'}")
    results = []
    for bid in pending:
        r = heavy_execute(task_name, bid, command=command, execute_now=execute_now)
        results.append(r)
    return results


def heavy_cleanup(task_name: str) -> None:
    """清理指定大工程的 scratch 目录。"""
    task_dir = SCRATCH / task_name
    if not task_dir.exists():
        logger.error(f"❌ scratch 目录不存在: {task_dir}")
        return
    shutil.rmtree(task_dir)
    heavy_status = HEAVY_STATE / f"{task_name}.json"
    if heavy_status.exists():
        heavy_status.unlink()
    logger.info(f"🧹 已清理: {task_name}")


def _heavy_build_script(task_dir, target_id, batch, target_path, task_name, files, command, execute_now):
    """构建执行脚本和队列文件，返回 (script_path, queue_file, exec_cmd, result)。"""
    import shlex as _shlex

    script_path = task_dir / f"{target_id}-exec.sh"
    target_full = target_path if target_path.is_absolute() else SCRATCH.parent / target_path
    script_lines = [
        "#!/bin/bash",
        "set -e",
        f"echo '🚀 {target_id}: {len(files)} files'",
        f"cd {_shlex.quote(str(target_full))}",
    ]
    for f in files:
        safe_path = _shlex.quote(str(target_full / f))
        script_lines.append(f"echo '  processing: {f}'")
        if command:
            # 用户提供的命令，{f} 会被替换为实际文件路径
            script_lines.append(command.replace("{f}", safe_path))
        else:
            # 默认仅 echo 列出文件，不真做任何修改
            script_lines.append(f"echo '  [no-op] would process: {f}'")
    script_lines.append(f"echo '✅ {target_id} done'")
    with open(script_path, "w") as sf:
        sf.write("\n".join(script_lines) + "\n")
    os.chmod(script_path, 0o755)  # noqa: S103
    # 写入执行队列文件（供 daemon/subagent 消费）
    queue_file = task_dir / "execute-queue.jsonl"
    exec_cmd = {
        "batchId": target_id,
        "taskName": task_name,
        "script": str(script_path),
        "files": files,
        "targetPath": str(target_full),
        "command": command,
        "timestamp": _now_iso(),
        "dryRun": not execute_now,
    }
    with open(queue_file, "a") as qf:
        qf.write(json.dumps(exec_cmd, ensure_ascii=False) + "\n")
    _append_broker(
        "tasks",
        "heavy.batch.queued",
        f"批次入队: {target_id}",
        "ok",
        f"{task_name}: {target_id} 已加入执行队列 (dry_run={not execute_now})",
        {"taskName": task_name, "batchId": target_id, "fileCount": len(files), "dryRun": not execute_now},
    )
    result: dict[str, Any] = {
        "action": "queued",
        "batchId": target_id,
        "script": str(script_path),
        "queued": True,
        "dryRun": not execute_now,
        "startedPid": None,
    }
    return script_path, queue_file, exec_cmd, result
