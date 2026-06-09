#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path.home() / '.openclaw' / 'workspace'
SCRATCH = Path('/mnt/data/openclaw/scratch')


def run(cmd: str) -> int:
    """Run a shell command; print it; return exit code."""
    print(f"$ {cmd}")
    res = subprocess.run(cmd, shell=True, check=False)
    return res.returncode


def run_quiet(cmd: list[str]) -> int:
    """Run silently, return exit code."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return res.returncode
    except Exception:
        return 1


def clean_workspace_tmp() -> int:
    tmp_dir = WORKSPACE / 'tmp'
    if not tmp_dir.exists():
        return 0
    cleaned = 0
    for item in tmp_dir.iterdir():
        if item.name == 'voice-replies':
            continue
        try:
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink(missing_ok=True)
            cleaned += 1
        except Exception as exc:
            print(f"[warn] 清理失败: {item} -> {exc}")
    return cleaned


def clean_pyc() -> int:
    cleaned = 0
    for p in WORKSPACE.rglob('__pycache__'):
        try:
            shutil.rmtree(p)
            cleaned += 1
        except Exception as exc:
            print(f"[warn] 清理失败: {p} -> {exc}")
    for p in WORKSPACE.rglob('*.pyc'):
        try:
            p.unlink(missing_ok=True)
            cleaned += 1
        except Exception as exc:
            print(f"[warn] 清理失败: {p} -> {exc}")
    return cleaned


def clean_sessions() -> str:
    """Run session-size-watcher --force-clean to purge dead sessions."""
    watcher = WORKSPACE / 'scripts' / 'openclaw-session-size-watcher.py'
    if not watcher.exists():
        return "session-watcher 脚本不存在，跳过"
    rc = run_quiet(['python3', str(watcher), '--force-clean'])
    return "已执行" if rc == 0 else f"执行完成（退出码 {rc}）"


def clean_idle_subagents() -> tuple[int, list[str]]:
    """Try to detect idle subagent sessions. Returns (count, names).
    This is a best-effort detection via sessions_list; actual cleanup
    must be done by the agent in the main session (this script can't
    call OpenClaw internal tools)."""
    idle = []
    try:
        res = subprocess.run(
            ['openclaw', 'sessions', 'list', '--kind', 'subagent', '--active-minutes', '10'],
            capture_output=True, text=True, check=False, timeout=10
        )
        if res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line and 'subagent' in line.lower():
                    idle.append(line)
    except Exception:
        pass
    return len(idle), idle


def drop_caches() -> str:
    """Try to drop kernel caches. Gracefully handle no-sudo machines."""
    # Try sudo -n first
    rc = run_quiet(['sudo', '-n', 'true'])
    if rc == 0:
        rc2 = run_quiet(['sudo', 'tee', '/proc/sys/vm/drop_caches'])
        if rc2 == 0:
            return "已释放（sudo）"
        return f"释放失败（退出码 {rc2}）"
    # Try without sudo (won't work on most machines, but try)
    rc2 = run_quiet(['sh', '-c', 'echo 3 > /proc/sys/vm/drop_caches'])
    if rc2 == 0:
        return "已释放（直接写入）"
    return "跳过（需要 sudo 权限，当前不可用）"


def print_scratch_hint() -> None:
    """Remind about scratch backup."""
    if not SCRATCH.exists():
        return
    recent = []
    for item in sorted(SCRATCH.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if item.is_dir():
            recent.append(item.name)
            if len(recent) >= 5:
                break
    if recent:
        print(f"\n💡 scratch 最近项目: {', '.join(recent)}")
        print(f"   建议手动确认是否需要备份关键结果文档。")


def main() -> int:
    print('=== OpenClaw 大工程收尾 ===')
    print()

    # ── 1. 系统状态快照 ──
    print('── 1/7 系统状态 ──')
    run('free -h')
    run('df -h / /mnt/data')

    # ── 2. 清理临时文件 ──
    print('\n── 2/7 临时文件清理 ──')
    tmp_cleaned = clean_workspace_tmp()
    pyc_cleaned = clean_pyc()
    print(f"[ok] tmp 清理: {tmp_cleaned} 项")
    print(f"[ok] pyc/__pycache__ 清理: {pyc_cleaned} 项")

    # ── 3. 会话大小清理 ──
    print('\n── 3/7 会话大小清理 ──')
    result = clean_sessions()
    print(f"[ok] 会话清理: {result}")

    # ── 4. 清理无任务分身 ──
    print('\n── 4/7 子代理清理 ──')
    n, names = clean_idle_subagents()
    if n > 0:
        print(f"[info] 检测到 {n} 个疑似闲置子代理")
        for name in names[:3]:
            print(f"       {name}")
        print(f"[info] 清理需在 OpenClaw 主会话中执行；已记录为提醒。")
    else:
        print(f"[ok] 未检测到闲置子代理")

    # ── 5. scratch 过期清理 ──
    print('\n── 5/7 scratch 过期清理 ──')
    scratch_cleaner = WORKSPACE / 'scripts' / 'openclaw-scratch-cleanup.py'
    if scratch_cleaner.exists():
        run(f'python3 {scratch_cleaner} --dry-run --print-kept')

    # ── 6. journald + kernel cache ──
    print('\n── 6/7 journald + kernel cache ──')
    run('journalctl --user --vacuum-size=50M 2>/dev/null; journalctl --vacuum-size=100M 2>/dev/null')
    cache_result = drop_caches()
    print(f"[ok] kernel cache: {cache_result}")

    # ── 7. 健康检查 ──
    print('\n── 7/7 系统健康检查 ──')
    run('python3 scripts/openclaw-system-summary.py --print-human')
    run('free -h')

    # ── 额外提醒 ──
    print_scratch_hint()
    print("\n📋 手工收尾提醒（finish 脚本不做自动化）:")
    print("   • 确认结果文档已生成并保存到 scratch")
    print("   • 更新 memory/daily/YYYY-MM-DD.md（今日工作总结）")
    print("   • 如涉及规则变化，更新 MEMORY.md 或相关规则文件")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
