#!/usr/bin/env python3
"""Mark42 烟测脚本 — 跑在每个 commit 前。

用法：
    python3 scripts/mark42-tests.py          # 只跑无副作用测试
    python3 scripts/mark42-tests.py --full    # 包括守护启停（有副作用）
    python3 scripts/mark42-tests.py --status  # 只检查守护状态
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
WORKSPACE = SCRIPTS.parent
STATE = Path.home() / ".local" / "state" / "openclaw" / "mark42"
LOGS = Path("/mnt/data/openclaw/mark42/logs")

PASS = 0
FAIL = 0


def ok(label: str):
    global PASS
    PASS += 1
    print(f"  ✅ {label}")


def err(label: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  ❌ {label}")
    if detail:
        print(f"      {detail}")


def run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError:
        return -2, "", "NOT FOUND"


# ── 测试用例 ──

def test_imports():
    print("\n📦 模块导入检查")
    modules = [
        "config",
        "utils",
        "logs",
        "compaction_diag",
        "armor",
        "engine",
        "heavy",
        "cli",
        "compression_algorithms",
        "pii_redactor",
        "algo_scheduler",
        "session_fence_safe",
    ]
    for m in modules:
        code, out, stderr = run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0,'{SCRIPTS}'); "
             f"import mark42_modules.{m}"],
            timeout=10,
        )
        if code == 0:
            ok(f"mark42_modules.{m}")
        else:
            err(f"mark42_modules.{m}", stderr.strip() or out.strip())


def test_compression_algorithms():
    """阶段 1 Day 1: SmartCrusher 压缩算法专项测试"""
    print("\n🧪 压缩算法专项 (Day 1)")
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "compression_algorithms.py")],
        timeout=30,
    )
    if code == 0 and "通过" in out:
        ok("SmartCrusher 单元测试")
    else:
        err("SmartCrusher 单元测试", stderr.strip() or out.strip()[-300:])


def test_pii_redactor():
    """阶段 1 Day 2: PII 脱敏专项测试"""
    print("\n🔒 PII 脱敏专项 (Day 2)")
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "pii_redactor.py")],
        timeout=30,
    )
    if code == 0 and "通过" in out:
        ok("PIIRedactor 单元测试")
    else:
        err("PIIRedactor 单元测试", stderr.strip() or out.strip()[-300:])


def test_algo_scheduler():
    """阶段 1 Day 3: 算法调度器专项测试"""
    print("\n📊 算法调度器专项 (Day 3)")
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "algo_scheduler.py")],
        timeout=30,
    )
    if code == 0 and "通过" in out:
        ok("AlgorithmScheduler 单元测试")
    else:
        err("AlgorithmScheduler 单元测试", stderr.strip() or out.strip()[-300:])


def test_session_fence():
    """Session Fence 安全测试"""
    print("\n🚧 Session Fence 安全测试")
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "test_session_fence.py")],
        timeout=60,
    )
    if code == 0 and "通过" in out and "0 失败" in out:
        ok("session_fence 测试")
    else:
        err("session_fence 测试", stderr.strip() or out.strip()[-300:])


def test_syntax():
    print("\n🔍 语法检查")
    code, out, stderr = run(
        [sys.executable, "-m", "compileall", "-q",
         str(SCRIPTS / "mark42_modules")],
        timeout=10,
    )
    if code == 0:
        ok("compileall 零错误")
    else:
        err("compileall", stderr.strip() or out.strip())


def test_cli():
    print("\n🏃 CLI 入口")

    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42.py"), "--help"],
        timeout=5,
    )
    if code == 0 and "--help" in (out + stderr):
        ok("mark42.py --help")
    else:
        err("mark42.py --help", stderr.strip())

    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42.py"), "status", "--json"],
        timeout=10,
    )
    if code == 0:
        try:
            d = json.loads(out)
            ok(f"mark42.py status --json (版本={d.get('version','?')})")
        except json.JSONDecodeError:
            err("mark42.py status --json 输出不是合法 JSON")
    else:
        err("mark42.py status --json", stderr.strip())


def test_config_files():
    print("\n📁 关键文件检查")

    config = STATE / "config.json"
    if config.exists():
        try:
            with open(config) as f:
                cfg = json.load(f)
            v = cfg.get("version", "?")
            ok(f"config.json (版本={v})")
        except Exception:
            err("config.json 无法读取")
    else:
        ok("config.json 不存在（未初始化，正常）")

    loops = STATE / "engine" / "loops.json"
    if loops.exists():
        try:
            with open(loops) as f:
                data = json.load(f)
            count = len(data)
            ok(f"loops.json ({count} 个 Loop)")
        except Exception:
            err("loops.json 无法读取")
    else:
        err("loops.json 不存在")


def test_log_paths():
    print("\n📋 日志路径检查")
    for p in [STATE, STATE / "armor", STATE / "engine", STATE / "heavy"]:
        if p.exists():
            ok(f"状态目录存在: {p.relative_to(Path.home())}")
        else:
            err(f"状态目录不存在: {p.relative_to(Path.home())}")

    if LOGS.exists():
        log_files = list(LOGS.glob("*.log"))
        log_count = len(log_files)
        ok(f"日志目录存在 ({log_count} 个日志文件)")
    else:
        err("日志目录不存在 (/mnt/data/openclaw/mark42/logs)")


def test_status():
    """检查守护进程状态（不启动任何东西，只读）"""
    print("\n📊 守护状态检查")

    # 检查旧日志目录是否还在写入
    old_log_dir = STATE / "armor" / "daemon-logs"
    if old_log_dir.exists():
        old_files = list(old_log_dir.glob("*.log"))
        if old_files:
            old_size = sum(f.stat().st_size for f in old_files)
            if old_size > 1000:
                err(f"旧日志目录仍有数据: {old_log_dir} ({old_size} bytes)")
            else:
                ok(f"旧日志目录已停止写入 (size={old_size})")
        else:
            ok("旧日志目录为空")


def test_daemon_full():
    """完整守护启停测试（--full 模式才执行）"""
    print("\n🔄 守护进程完整测试")
    print("   (需要约 15 秒)")

    # 1. 确保没有旧进程
    subprocess.run(["pkill", "-f", "mark42.py assemble"], capture_output=True)
    subprocess.run(["pkill", "-f", "mark42.py armor --guard"], capture_output=True)
    subprocess.run(["pkill", "-f", "mark42.py engine --daemon"], capture_output=True)
    time.sleep(2)

    # 2. 启动 assemble
    print("   ▶️ assemble 启动...")
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPTS / "mark42.py"), "assemble"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(8)

    # 3. 检查进程
    result = subprocess.run(["pgrep", "-af", "mark42.py"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n") if "pgrep" not in l and l.strip()]
    armor_ok = any("armor --guard" in l for l in lines)
    engine_ok = any("engine --daemon" in l for l in lines)

    if armor_ok and engine_ok:
        ok("armor-guard + engine-daemon 双守护启动")
    else:
        err("守护进程未完全启动",
            f"armor={armor_ok}, engine={engine_ok}, lines={len(lines)}")

    # 4. 等一个心跳
    time.sleep(5)
    hb = STATE / "engine" / "daemon-heartbeat.json"
    if hb.exists():
        try:
            with open(hb) as f:
                data = json.load(f)
            tick = data.get("lastTick", "")
            cycle = data.get("cycle", -1)
            ok(f"心跳正常 (cycle={cycle})")
        except Exception:
            err("心跳文件无法读取")
    else:
        err("心跳文件不存在")

    # 5. 检查日志
    if LOGS.exists():
        eng_log = LOGS / "engine-daemon.log"
        if eng_log.exists():
            with open(eng_log) as f:
                lines_log = f.readlines()
            if len(lines_log) > 5:
                ok(f"engine-daemon.log 正常写入 ({len(lines_log)} 行)")
            else:
                err(f"engine-daemon.log 行数过少 ({len(lines_log)})")

        armor_log = LOGS / "armor-guard.log"
        if armor_log.exists():
            with open(armor_log) as f:
                alog_lines = f.readlines()
            if any("上下文" in l for l in alog_lines):
                ok(f"armor-guard.log 正常写入 ({len(alog_lines)} 行)")
            else:
                err(f"armor-guard.log 内容异常 ({len(alog_lines)} 行)")

    # 6. 检查 stderr
    if LOGS.exists():
        eng_err = LOGS / "engine-daemon-stderr.log"
        if eng_err.exists() and eng_err.stat().st_size > 0:
            with open(eng_err) as f:
                err_lines = f.readlines()
            err("engine-daemon stderr 有内容", "".join(err_lines[:3]))
        else:
            ok("engine-daemon stderr 干净")

    # 7. 优雅关闭
    subprocess.run(["pkill", "-f", "mark42.py assemble"], capture_output=True)
    subprocess.run(["pkill", "-f", "mark42.py armor --guard"], capture_output=True)
    subprocess.run(["pkill", "-f", "mark42.py engine --daemon"], capture_output=True)
    time.sleep(2)
    leftover = subprocess.run(["pgrep", "-af", "mark42.py"], capture_output=True, text=True)
    leftovers = [l for l in leftover.stdout.strip().split("\n") if "pgrep" not in l and l.strip() and "mark42-tests" not in l]
    if not leftovers:
        ok("守护进程优雅关闭（零残留）")
    else:
        err(f"守护进程有残留: {leftovers}")


# ── 入口 ──

def main():
    global PASS, FAIL

    parser = argparse.ArgumentParser(description="Mark42 烟测")
    parser.add_argument("--full", action="store_true", help="含守护进程启停测试")
    parser.add_argument("--status", action="store_true", help="只检查守护状态")
    args = parser.parse_args()

    print("=" * 60)
    print("Mark42 烟测")
    print("=" * 60)

    test_imports()
    test_syntax()
    test_cli()
    test_config_files()
    test_log_paths()

    # 阶段 1 专项 (2026-06-24 Day 1-3)
    test_compression_algorithms()
    test_pii_redactor()
    test_algo_scheduler()
    test_session_fence()

    if args.status:
        test_status()
    elif args.full:
        test_status()
        test_daemon_full()

    print("\n" + "=" * 60)
    print(f"结果: {PASS} 通过 / {FAIL} 失败")
    print("=" * 60)

    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
