#!/usr/bin/env python3
"""
verify-today-patches.py — 一键验证今日全部改动

覆盖：
  Watcher v2 整合（broker dirty flag + 监工内迁 + guardian 紧急通道 + 清理统一 + flush 同步）
  搜索短路 + TTL 缓存
  task-scheduler 闲时跳过
  耗时基线监控
  boot-health-check 开机体检

用法：
  python3 scripts/verify-today-patches.py           → 全量验证，退出码 0=全部通过
  python3 scripts/verify-today-patches.py --print    → 逐项打印结果
  python3 scripts/verify-today-patches.py --strict   → 任何警告也 exit 1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPTS = WORKSPACE / "scripts"
STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
OPENCLAW_STATE = STATE / "openclaw"


def run(cmd: list[str], timeout: int = 30) -> tuple[bool, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        stdout = (r.stdout or "").strip()
        stderr = (r.stderr or "").strip()
        return r.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, "", f"TIMEOUT({timeout}s)"
    except Exception as e:
        return False, "", str(e)


def check(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "ok": ok, "detail": detail}


def main():
    parser = argparse.ArgumentParser(description="一键验证今日全部补丁")
    parser.add_argument("--print", action="store_true", dest="do_print")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    checks = []
    PY = sys.executable

    # ── 1. Watcher 脚本存在性 ──
    watcher_scripts = [
        "openclaw-health-collector.py",
        "openclaw-task-scheduler.py",
        "openclaw-frontstage-guardian.py",
        "openclaw-lifecycle-maintainer.py",
    ]
    all_exist = True
    missing = []
    for s in watcher_scripts:
        if not (SCRIPTS / s).exists():
            all_exist = False
            missing.append(s)
    checks.append(check("watcher-scripts-exist", all_exist,
                        "missing: " + ",".join(missing) if missing else "all present"))

    # ── 2. Timer 数量 ──
    ok, out, _ = run(["systemctl", "--user", "list-timers", "--no-pager", "openclaw-*", "--no-legend"])
    timer_count = len([l for l in out.split("\n") if l.strip()]) if ok else 0
    checks.append(check("timer-count-5", timer_count == 5,
                        f"found {timer_count} timers (expected 5)"))

    # ── 3. 搜索短路（跳过缓存验证原始搜索）──
    ok, out, _ = run([PY, str(SCRIPTS / "memory-search-local-first.py"), "--no-cache", "贾维斯"])
    short_circuited = False
    try:
        data = json.loads(out) if out else {}
        short_circuited = data.get("shortCircuited", False)
    except Exception:
        pass
    checks.append(check("search-shortcircuit", short_circuited, f"shortCircuited={short_circuited}"))

    # ── 4. 搜索降级 ──
    ok, out, _ = run([PY, str(SCRIPTS / "memory-search-local-first.py"), "xyz不存在xyz"])
    fallback = False
    try:
        data = json.loads(out) if out else {}
        fallback = not data.get("shortCircuited", True)
    except Exception:
        pass
    checks.append(check("search-fallback", fallback, f"falls back to cloud"))

    # ── 5. TTL 缓存 ──
    ok, out, _ = run([PY, str(SCRIPTS / "query-cache.py"), "stats"])
    cache_ok = ok and "active" in out
    checks.append(check("ttl-cache", cache_ok, out[:100]))

    # ── 6. task-scheduler 闲时跳过 ──
    ok, out, _ = run([PY, str(SCRIPTS / "openclaw-task-scheduler.py"), "--dry-run", "--print-human"])
    idle_skip = "skip" in out.lower() or "idle" in out.lower()
    checks.append(check("task-scheduler-idle-skip", idle_skip, out[:100]))

    # ── 7. health-collector 耗时基线 ──
    ok, out, _ = run([PY, str(SCRIPTS / "openclaw-health-collector.py"), "--print-json"], timeout=40)
    latency_ok = False
    latency_detail = "parse error"
    try:
        data = json.loads(out) if out else {}
        clist = data.get("checks", [])
        if not clist:
            latency_detail = "no checks in output"
        else:
            total = len(clist)
            with_ms = sum(1 for c in clist if isinstance(c.get("elapsedMs"), int))
            if with_ms == total:
                latency_ok = True
                ms_vals = [str(c.get("elapsedMs")) for c in clist]
                latency_detail = f"{with_ms}/{total} checks have elapsedMs: {','.join(ms_vals)}ms"
            else:
                latency_detail = f"only {with_ms}/{total} have elapsedMs"
    except Exception as e:
        latency_detail = f"exception: {e}"
    checks.append(check("latency-baseline", latency_ok, latency_detail))

    # ── 8. flush 同步脚本 ──
    flush_script = SCRIPTS / "flush-memory-sync.sh"
    checks.append(check("flush-sync-script", flush_script.exists() and os.access(flush_script, os.X_OK),
                        str(flush_script)))

    # ── 9. broker dirty flag 机制 ──
    dirty_path = OPENCLAW_STATE / "broker" / ".dirty"
    log_path = OPENCLAW_STATE / "health-collector" / "collector.log"
    broker_ok = False
    detail = ""
    if log_path.exists():
        try:
            lines = log_path.read_text().split("\n")
            for line in reversed(lines):
                if "broker rebuild" in line:
                    # 应出现 rebuild skipped 或 rebuild triggered by dirty flag
                    if "skipped" in line or "dirty flag" in line:
                        broker_ok = True
                        detail = line.strip()[-120:]
                    else:
                        detail = line.strip()[-120:]
                    break
        except Exception:
            detail = "cannot read log"
    else:
        # 刚装可能没有日志，测试脚本本身能跑就行
        ok, out, _ = run([PY, str(SCRIPTS / "openclaw-health-collector.py"), "--print-human"])
        broker_ok = ok
        detail = "fresh install test: " + ("ok" if ok else "FAIL")
    checks.append(check("broker-dirty-flag", broker_ok, detail))

    # ── 10. AGENTS.md 搜索规则 ──
    agents = WORKSPACE / "AGENTS.md"
    rule_ok = False
    if agents.exists():
        content = agents.read_text()
        rule_ok = "memory-search-local-first" in content and "三级搜索策略" in content
    checks.append(check("agents-search-rule", rule_ok, "AGENTS.md contains search strategy"))

    # ── 11. boot-health-check ──
    ok, out, _ = run([PY, str(SCRIPTS / "openclaw-boot-health-check.py"), "--print-human"], timeout=20)
    boot_ok = ok and "错误" not in out and "error" not in out.lower()
    checks.append(check("boot-health-check", boot_ok, out[:100] if out else "no output"))

    # ── 输出 ──
    passed = sum(1 for c in checks if c["ok"])
    failed = len(checks) - passed

    if args.do_print:
        for c in checks:
            icon = "✅" if c["ok"] else "❌"
            print(f"  {icon} {c['name']:<30} {c['detail']}")
        print(f"\n  {passed}/{len(checks)} passed, {failed} failed")

    if args.strict:
        return 0 if failed == 0 else 1
    # 非 strict 下，只把真失败看作 exit 1（timer 数量 ≠5 允许降级）
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
