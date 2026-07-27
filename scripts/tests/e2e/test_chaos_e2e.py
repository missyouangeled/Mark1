#!/usr/bin/env python3
"""P1-2: ChaosEngine 实跑验证脚本。

安全地执行 ChaosEngine 实验（非 dry-run），验证 verify 阶段。

只跑以下安全实验：
  - kill_engine: systemd 自愈（kill 后自动重启）
  - kill_armor: systemd 自愈（同上）
  - circuit_breaker_trip: 熔断器触发（纯内存操作）
  - consciousness_degraded: stub 降级（纯内存操作）

跳过以下危险实验：
  - fill_disk: 会真的占磁盘空间
  - network_latency: 会注入网络延迟
  - high_context: 需要特殊上下文构造

用法:
  python3 tests/e2e/test_chaos_e2e.py              # 跑安全实验
  python3 tests/e2e/test_chaos_e2e.py --dry-run     # 全部 dry-run
  python3 tests/e2e/test_chaos_e2e.py --all        # 包括危险实验
"""

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SAFE_EXPERIMENTS = ["kill_engine", "kill_armor", "circuit_breaker_trip", "consciousness_degraded"]
DANGEROUS_EXPERIMENTS = ["fill_disk", "network_latency", "high_context"]


def _print(name: str, ok: bool, detail: str = "") -> None:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {name}" + (f" -- {detail}" if detail else ""))


def run_chaos_e2e(dry_run: bool = False, run_all: bool = False) -> int:
    from mark42_modules.chaos_engine import ChaosEngine

    print("=" * 60)
    print("  ChaosEngine 实跑验证")
    print("=" * 60)
    print()

    ce = ChaosEngine()

    experiments = SAFE_EXPERIMENTS[:]
    if run_all:
        experiments.extend(DANGEROUS_EXPERIMENTS)

    passed = 0
    total = 0

    for exp_name in experiments:
        total += 1
        print(f"── {exp_name} ({'dry-run' if dry_run else '实跑'}) ──")

        try:
            t0 = time.monotonic()
            result = ce.run_experiment(exp_name, dry_run=dry_run)
            elapsed = (time.monotonic() - t0) * 1000

            ok = result.status == "passed"
            detail = f"setup={result.setup_ok}, exec={result.execute_ok}, verify={result.verify_ok}, {elapsed:.0f}ms"

            if not dry_run and not result.verify_ok:
                detail += f", verify_failed: {result.details}"

            _print(exp_name, ok, detail)
            if ok:
                passed += 1
        except Exception as e:
            _print(exp_name, False, f"异常: {e}")
        print()

    # ── 总结 ──
    print("=" * 60)
    print(f"  结果: {passed}/{total} 通过")
    print("=" * 60)

    # ── 历史记录验证 ──
    print()
    print("── 历史记录验证 ──")
    history = ce.get_results(limit=10)
    if history:
        print(f"  📋 最近 {len(history)} 条实验记录:")
        for h in history[:5]:
            print(f"     {h.get('experiment','?')} | {h.get('status','?')} | {h.get('started_at','?')[:19]}")
    else:
        print("  ⚠️ 无历史记录")
    print()

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChaosEngine 实跑验证")
    parser.add_argument("--dry-run", action="store_true", help="全部 dry-run")
    parser.add_argument("--all", action="store_true", help="包括危险实验")
    args = parser.parse_args()

    passed = run_chaos_e2e(dry_run=args.dry_run, run_all=args.all)
    sys.exit(0 if passed > 0 else 1)
