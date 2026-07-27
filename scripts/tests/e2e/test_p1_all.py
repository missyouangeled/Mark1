#!/usr/bin/env python3
"""P1 综合验证：AdvisorClient + ChaosEngine + MetricsServer。

一次跑完所有 P1 验证项。
"""

import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def run_test(name: str, cmd: list[str]) -> tuple[bool, str]:
    """运行子测试，返回 (通过, 输出)。"""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}\n")

    t0 = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    elapsed = time.monotonic() - t0

    output = result.stdout + result.stderr
    print(output)

    # 检查结果行
    passed = "通过" in output or "PASS" in output or result.returncode == 0
    icon = "✅" if passed else "❌"
    print(f"\n{icon} {name} ({elapsed:.1f}s)")
    return passed, output


def test_metrics_server() -> bool:
    """直接测试 metrics server。"""
    print(f"\n{'='*60}")
    print(f"  P1-3: MetricsServer HTTP 端点")
    print(f"{'='*60}\n")

    from mark42_modules.metrics_server import MetricsServer

    import socket
    # 找一个可用端口
    test_port = 19100
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", test_port)) != 0:
                break
        test_port += 1

    server = MetricsServer(port=test_port)
    server.start_background()
    time.sleep(0.5)

    import urllib.request

    passed = 0
    total = 3

    # 1. /health
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{test_port}/health", timeout=5)
        if r.status == 200 and r.read().strip() == b"OK":
            print("  ✅ /health 返回 200 OK")
            passed += 1
        else:
            print("  ❌ /health 响应异常")
    except Exception as e:
        print(f"  ❌ /health 失败: {e}")

    # 2. /metrics
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{test_port}/metrics", timeout=5)
        body = r.read().decode()
        if r.status == 200 and "mark42_" in body:
            lines = [l for l in body.splitlines() if l and not l.startswith("#")]
            print(f"  ✅ /metrics 返回 {len(lines)} 条指标")
            passed += 1
        else:
            print(f"  ❌ /metrics 响应异常: status={r.status}")
    except Exception as e:
        print(f"  ❌ /metrics 失败: {e}")

    # 3. /unknown -> 404
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{test_port}/unknown", timeout=5)
        print(f"  ❌ /unknown 应返回 404，实际 {r.status}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("  ✅ /unknown 返回 404")
            passed += 1
        else:
            print(f"  ❌ /unknown 应返回 404，实际 {e.code}")
    except Exception as e:
        print(f"  ❌ /unknown 失败: {e}")

    server.stop()
    print(f"\n{'✅' if passed == total else '❌'} MetricsServer ({passed}/{total})")
    return passed == total


def main():
    all_passed = True

    # P1-1: AdvisorClient
    ok1, _ = run_test(
        "P1-1: AdvisorClient LLM 端到端链路验证",
        ["python3", str(SCRIPT_DIR / "tests" / "e2e" / "test_advisor_e2e.py")],
    )
    all_passed = all_passed and ok1

    # P1-2: ChaosEngine
    ok2, _ = run_test(
        "P1-2: ChaosEngine 实跑验证",
        ["python3", str(SCRIPT_DIR / "tests" / "e2e" / "test_chaos_e2e.py")],
    )
    all_passed = all_passed and ok2

    # P1-3: MetricsServer
    ok3 = test_metrics_server()
    all_passed = all_passed and ok3

    # 总结
    print(f"\n{'='*60}")
    print(f"  P1 综合验证结果: {'全部通过 ✅' if all_passed else '有失败项 ❌'}")
    print(f"{'='*60}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
