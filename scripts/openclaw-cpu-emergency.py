#!/usr/bin/env python3
"""
openclaw-cpu-emergency.py — CPU 负载过高一键诊断/修复

用法：
  python3 openclaw-cpu-emergency.py --diagnose       # 只看不修
  python3 openclaw-cpu-emergency.py --repair          # 全自动修复
  python3 openclaw-cpu-emergency.py --light-clean      # 只清缓存，不杀进程
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parent.parent
SCRATCH = Path("/mnt/data/openclaw/scratch")
CORE_COUNT = os.cpu_count() or 8
LOAD_THRESHOLD = CORE_COUNT  # 1min 负载 > 核心数 = 过载

# --- helpers ---

def run_shell(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)

def now_short() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")

def print_header(title: str) -> None:
    print(f"\n{'='*50}")
    print(f"  {title}  [{now_short()}]")
    print(f"{'='*50}")

def get_load() -> tuple[float, float, float]:
    try:
        a,b,c = os.getloadavg()
        return round(a,2), round(b,2), round(c,2)
    except:
        return 0,0,0

def get_mem() -> dict:
    try:
        r = run_shell("free -h | head -3")
        return {"raw": r.stdout.strip()}
    except:
        return {"raw": "?"}

def get_disk() -> str:
    try:
        r = run_shell("df -h / /mnt/data 2>/dev/null")
        return r.stdout.strip()
    except:
        return "?"

def get_top_cpu(n: int = 8) -> str:
    try:
        r = run_shell(f"ps aux --sort=-%cpu | head -{n+1}")
        return r.stdout.strip()
    except:
        return "?"

def get_swap_hogs(n: int = 5) -> list[tuple[int, int, str]]:
    """返回 [(pid, swap_kb, cmd), ...] swap 大户"""
    hogs = []
    try:
        r = run_shell(f"ps aux --sort=-%mem | awk 'NR>1{{print $2}}' | head -{n}")
        for pid_str in r.stdout.strip().split():
            pid = int(pid_str)
            try:
                sw = run_shell(f"awk '/Swap:/{{sum+=$2}}END{{print sum}}' /proc/{pid}/smaps 2>/dev/null")
                swap_kb = int(sw.stdout.strip() or 0)
                if swap_kb > 0:
                    cmd = run_shell(f"ps -p {pid} -o cmd --no-headers 2>/dev/null")
                    hogs.append((pid, swap_kb, cmd.stdout.strip()[:80]))
            except:
                pass
    except:
        pass
    return sorted(hogs, key=lambda x: -x[1])


# --- Step 1: 诊断 ---

def step_diagnose() -> dict:
    load = get_load()
    mem = get_mem()
    disk = get_disk()
    top = get_top_cpu()
    hogs = get_swap_hogs()

    print_header("Step 1: 快速判伤")
    print(f"CPU 负载 (1/5/15min): {load[0]} / {load[1]} / {load[2]}  (核数: {CORE_COUNT})")
    status = "🟢 正常"
    if load[0] > LOAD_THRESHOLD:
        status = "🔴 过载"
    elif load[0] > LOAD_THRESHOLD * 0.7:
        status = "🟡 接近过载"
    print(f"状态: {status}")
    print(f"\n{mem['raw']}")
    print(f"\n{disk}")
    print(f"\nTop CPU:\n{top}")
    if hogs:
        print(f"\nSwap 大户:")
        for pid, kb, cmd in hogs:
            print(f"  PID {pid}: {kb//1024}MB swap  | {cmd}")

    return {"load": load, "hogs": hogs, "status": status}


# --- Step 2: 关进程 ---

SAFE_TO_KILL = [
    ("nautilus", "killall nautilus 2>/dev/null", "文件管理器", "低"),
]

SAFE_APPS = {
    "gnome-text-editor": ("killall gnome-text-editor 2>/dev/null", "GNOME 文本编辑器", "低（内容已保存则无损失）"),
    "gedit": ("killall gedit 2>/dev/null", "GEdit 编辑器", "低"),
    "evince": ("killall evince 2>/dev/null", "PDF 查看器", "低"),
    "eog": ("killall eog 2>/dev/null", "图片查看器", "低"),
}

def step_kill(dry_run: bool = True) -> list[str]:
    killed = []
    header = "Step 2: 关进程 (DRY-RUN)" if dry_run else "Step 2: 关进程"
    print_header(header)

    # nautilus 几乎总是罪魁祸首
    for name, cmd, desc, risk in SAFE_TO_KILL:
        r = run_shell(f"pgrep {name} 2>/dev/null")
        if r.stdout.strip():
            print(f"  {'[DRY] 检测到' if dry_run else '🔴 终止'} {desc} ({name})")
            if not dry_run:
                run_shell(cmd)
                killed.append(name)
        else:
            print(f"  ✅ {desc} 未运行")

    for name, (cmd, desc, risk) in SAFE_APPS.items():
        r = run_shell(f"pgrep {name} 2>/dev/null")
        if r.stdout.strip():
            swapped_kb = 0
            for pid in r.stdout.strip().split():
                try:
                    sw = run_shell(f"awk '/Swap:/{{sum+=$2}}END{{print sum}}' /proc/{pid}/smaps 2>/dev/null")
                    swapped_kb += int(sw.stdout.strip() or 0)
                except:
                    pass
            print(f"  {'[DRY] 检测到' if dry_run else '🟡 终止'} {desc} ({name}) | swap: {swapped_kb//1024}MB")
            if not dry_run:
                run_shell(cmd)
                killed.append(name)

    if not killed and not dry_run:
        print("  无安全可关进程，跳过。")
    return killed


# --- Step 3: 清临时文件 ---

def step_clean(dry_run: bool = True) -> dict:
    header = "Step 3: 清临时/垃圾文件 (DRY-RUN)" if dry_run else "Step 3: 清临时/垃圾文件"
    print_header(header)
    stats = {}

    # pycache
    pycache_dirs = list(WORKSPACE.rglob("__pycache__"))
    pyc_files = list(WORKSPACE.rglob("*.pyc"))
    stats["pycache_dirs"] = len(pycache_dirs)
    stats["pyc_files"] = len(pyc_files)
    if pycache_dirs or pyc_files:
        print(f"  Python 缓存: {len(pycache_dirs)} __pycache__目录 + {len(pyc_files)} .pyc 文件")
        if not dry_run:
            for d in pycache_dirs:
                shutil.rmtree(d, ignore_errors=True)
            for f in pyc_files:
                f.unlink(missing_ok=True)

    # journal — 用 --disk-usage 直接读实际占用（输出如 "47.3M"）
    before_j = run_shell("journalctl --user --disk-usage 2>/dev/null")
    import re
    before_match = re.search(r'[\d.]+[KMGT]?B?', before_j.stdout)
    before_str = before_match.group(0) if before_match else "?"
    if not dry_run:
        run_shell("journalctl --user --vacuum-time=2d 2>/dev/null")
        after_j = run_shell("journalctl --user --disk-usage 2>/dev/null")
        after_match = re.search(r'[\d.]+[KMGT]?B?', after_j.stdout)
        after_str = after_match.group(0) if after_match else "?"
        print(f"  journal: {before_str} → {after_str} (保留2天)")
    else:
        print(f"  journal: 当前占用 {before_str}")

    # workspace tmp (保留 voice-replies)
    tmp_dir = WORKSPACE / "tmp"
    tmp_cleaned = 0
    if tmp_dir.exists():
        for item in list(tmp_dir.iterdir()):
            if item.name == "voice-replies":
                continue
            if item.is_file() and (item.suffix in ('.mp3', '.wav', '.json', '.txt')) and item.stat().st_size < 10*1024*1024:
                continue
            mtime_days = (time.time() - item.stat().st_mtime) / 86400
            if mtime_days > 1 and not (item.is_dir() and (item / ".keep").exists()):
                tmp_cleaned += 1
                if not dry_run:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
    if tmp_cleaned > 0:
        print(f"  workspace/tmp: {tmp_cleaned} 过期临时文件 {'[DRY]' if dry_run else '已清理'}")
    stats["tmp_cleaned"] = tmp_cleaned

    # /tmp 大文件
    big_tmp = list(Path("/tmp").glob("*"))
    big_old = [f for f in big_tmp if f.is_file() and f.stat().st_size > 100*1024*1024
               and (time.time() - f.stat().st_mtime) > 3600]
    if big_old:
        print(f"  /tmp: {len(big_old)} 个大文件(>100MB, >1h)")
        if not dry_run:
            for f in big_old:
                f.unlink(missing_ok=True)
    stats["big_tmp"] = len(big_old)

    if not stats.get("pycache_dirs") and not stats.get("pyc_files") and tmp_cleaned == 0 and not big_old:
        print("  无需清理。")

    return stats


# --- Step 4: 内存 ---

def step_memory(dry_run: bool = True) -> None:
    print_header("Step 4: 释放内存压力")

    # kernel cache
    before = run_shell("free -h | grep Mem")
    if not dry_run:
        run_shell("sync && echo 3 | sudo tee /proc/sys/vm/drop_caches 2>/dev/null")
    after = run_shell("free -h | grep Mem")
    print(f"  [BEFORE] {before.stdout.strip()}")
    if not dry_run:
        print(f"  [AFTER]  {after.stdout.strip()}")
    else:
        print("  [DRY] skip sync+drop_caches")

    # swap 大户
    hogs = get_swap_hogs(5)
    if hogs:
        total_swap = sum(kb for _, kb, _ in hogs)
        if total_swap > 2 * 1024 * 1024:  # >2GB
            print(f"\n  ⚠️  总 swap {total_swap//1024}MB > 2GB，大户:")
            for pid, kb, cmd in hogs:
                print(f"    PID {pid}: {kb//1024}MB swap  | {cmd}")
            if not dry_run:
                print("  💡 swap 过大通常因浏览器/Java，建议手动关标签页或重启浏览器")
        else:
            print(f"\n  swap 总量 {total_swap//1024}MB，在可控范围")
    else:
        print("  无 swap 占用进程")


# --- Step 5: 验证 ---

def step_verify(before_load: tuple) -> None:
    print_header("Step 5: 恢复验证")
    load = get_load()
    mem = run_shell("free -h | head -2")
    disk_root = run_shell("df -h / | tail -1")
    print(f"CPU 负载 (1/5/15min): {load[0]} / {load[1]} / {load[2]}")
    print(f"  修复前: {before_load[0]} → 修复后: {load[0]}")
    print(f"\n{mem.stdout.strip()}")
    print(f"\n{disk_root.stdout.strip()}")
    if load[0] < LOAD_THRESHOLD * 0.7:
        print(f"\n  ✅ 负载已恢复（< {LOAD_THRESHOLD * 0.7:.0f}）")
    elif load[0] < LOAD_THRESHOLD:
        print(f"\n  🟡 负载可接受（< {LOAD_THRESHOLD}）")
    else:
        print(f"\n  ❌ 负载仍然偏高，建议重复 Step 2-4 或关闭浏览器")


# --- 主入口 ---

def main() -> None:
    parser = argparse.ArgumentParser(description="CPU 负载过高一键诊断/修复")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--diagnose", action="store_true", help="只看不修")
    group.add_argument("--repair", action="store_true", help="全自动修复 (kill + clean + memory)")
    group.add_argument("--light-clean", action="store_true", help="只清缓存，不杀进程")
    args = parser.parse_args()

    print(f"🔧 openclaw-cpu-emergency  [{now_short()}]")

    if args.diagnose:
        step_diagnose()
        print("\n💡 运行 '--repair' 以自动修复，或 '--light-clean' 以轻度清理。")
        return

    if args.light_clean:
        step_clean(dry_run=False)
        step_memory(dry_run=False)
        step_verify((0,0,0))
        return

    if args.repair:
        # Step 1: 判伤
        info = step_diagnose()
        before_load = info["load"]

        # 如果不严重，询问
        if before_load[0] < LOAD_THRESHOLD * 0.7:
            print(f"\n  负载 {before_load[0]} 无需修复。如果是预防性清理，请用 --light-clean。")
            return

        # Step 2: 关进程
        step_kill(dry_run=False)

        # Step 3: 清临时
        step_clean(dry_run=False)

        # Step 4: 释放内存
        step_memory(dry_run=False)

        # Step 5: 验证
        step_verify(before_load)

        print_header("完成")
        print("💡 后续操作请串行化（一个一个来），不要再同时跑多个重任务。")
        print(f"   参考: docs/通用-CPU负载过高临时处理方案.md")


if __name__ == "__main__":
    main()
