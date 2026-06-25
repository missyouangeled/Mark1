#!/usr/bin/env python3
"""Mark42 烟测脚本 — 跑在每个 commit 前。

用法：
    python3 scripts/mark42-tests.py          # 只跑无副作用测试
    python3 scripts/mark42-tests.py --full    # 包括守护启停（有副作用）
    python3 scripts/mark42-tests.py --status  # 只检查守护状态
"""

import argparse
import json
import os
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


def run(cmd: list[str], timeout: int = 15, env: dict | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
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


def test_day6_algorithms():
    """阶段 1 Day 6: 三个新算法专项 (Code/Log/Diff Compressor)"""
    print("\n🧬 Day 6 新算法专项 (Code/Log/Diff)")

    for name, module in [
        ("CodeCompressor", "code_compressor"),
        ("LogDeduplicator", "log_deduplicator"),
        ("DiffCompressor", "diff_compressor"),
    ]:
        code, out, stderr = run(
            [sys.executable, str(SCRIPTS / "mark42_modules" / f"{module}.py")],
            timeout=30,
        )
        if code == 0 and "通过" in out:
            # 提取 "X 通过 / Y 失败" 数字
            import re as _re
            m = _re.search(r"(\d+)\s*通过\s*/\s*(\d+)\s*失败", out)
            if m:
                ok(f"{name} 单元测试 ({m.group(1)}/{int(m.group(1))+int(m.group(2))})")
            else:
                ok(f"{name} 单元测试")
        else:
            err(f"{name} 单元测试", stderr.strip() or out.strip()[-300:])


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


def test_phase2_async_llm():
    """阶段 2: LLM 压缩走异步队列 (daemon 永不阻塞)"""
    print("\n⚡ Phase 2-1: LLM 异步压缩专项")
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "llm_text_compressor.py")],
        timeout=120,
    )
    if code == 0 and "通过" in out:
        import re as _re
        m = _re.search(r"(\d+)\s*通过\s*/\s*(\d+)\s*失败", out)
        if m:
            ok(f"LLMTextCompressor (含异步) 单元测试 ({m.group(1)}/{int(m.group(1))+int(m.group(2))})")
        else:
            ok("LLMTextCompressor 单元测试")
    else:
        err("LLMTextCompressor 单元测试", stderr.strip() or out.strip()[-300:])

    # 集成: LLM 异步入口 (daemon 永不阻塞关键验证)
    print("\n⚡ Phase 2-1 集成: llm_text_compress_async 永不阻塞")
    workspace = SCRIPTS.parent
    code, out, stderr = run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{workspace}/scripts'); "
         f"from mark42_modules.llm_text_compressor import llm_text_compress_async; "
         f"import time; "
         f"t0 = time.time(); "
         f"r = llm_text_compress_async('长文本测试，' * 100, mode='summarize', wait=False); "
         f"elapsed = (time.time() - t0) * 1000; "
         f"assert r['status'] == 'queued', 'expected queued, got ' + str(r); "
         f"assert elapsed < 100, 'wait=False should be < 100ms, got ' + str(elapsed) + 'ms'; "
         f"print('PASS: enqueue=' + format(elapsed, '.1f') + 'ms, request_id=' + r['request_id'])"
        ],
        timeout=30,
    )
    if code == 0 and "PASS" in out:
        ok("llm_text_compress_async 集成 (daemon 永不阻塞)")
    else:
        err("llm_text_compress_async 集成", stderr.strip() or out.strip()[-300:])


def test_phase2_use_llm_env():
    """阶段 2-2: MARK42_TEXT_USE_LLM 环境变量"""
    print("\n🌍 Phase 2-2: MARK42_TEXT_USE_LLM 环境变量")
    workspace = SCRIPTS.parent

    # 1. 默认 (MARK42_TEXT_USE_LLM 不设) -> rule_based
    code, out, stderr = run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{workspace}/scripts'); "
         f"from mark42_modules.algo_scheduler import process; "
         f"text = '总而言之，第 001 段长文本。\\n' * 150; "  # 4.5KB 触发 text 但默认不调 LLM
         f"r = process(text); "
         f"assert r.get('llm_used') is False or r.get('llm_used') is None, 'default should not use LLM, got ' + str(r.get('llm_used')); "
         f"ratio = r['compress_stats']['ratio'] if r.get('compress_stats') else 'N/A'; "
         f"print('PASS: default=rule_based, ratio=' + str(ratio))"
        ],
        timeout=60,
    )
    if code == 0 and "PASS" in out:
        ok("env 默认 (false) → rule_based")
    else:
        err("env 默认 (false)", stderr.strip() or out.strip()[-300:])

    # 2. MARK42_TEXT_USE_LLM=true -> LLM
    code, out, stderr = run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{workspace}/scripts'); "
         f"from mark42_modules.algo_scheduler import process; "
         f"text = '总而言之，第 001 段长文本。\\n' * 300; "  # 12KB 触发 text 路由
         f"r = process(text); "
         f"assert r.get('llm_used') is True, 'true env should use LLM, got ' + str(r.get('llm_used')); "
         f"print('PASS: true=LLM, ratio=' + str(r['compress_stats']['ratio']))"
        ],
        timeout=120,
        env={**os.environ, "MARK42_TEXT_USE_LLM": "true"},
    )
    if code == 0 and "PASS" in out:
        ok("env=true → LLM")
    else:
        err("env=true", stderr.strip() or out.strip()[-300:])

    # 3. MARK42_TEXT_USE_LLM=auto + 大输入 -> LLM
    code, out, stderr = run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{workspace}/scripts'); "
         f"from mark42_modules.algo_scheduler import process; "
         f"text = '总而言之，第 001 段长文本。\\n' * 300; "  # ~12KB 触发 text 路由
         f"r = process(text); "
         f"assert r.get('llm_used') is True, 'auto+big should use LLM, got ' + str(r.get('llm_used')); "
         f"print('PASS: auto+big=LLM, ratio=' + str(r['compress_stats']['ratio']))"
        ],
        timeout=120,
        env={**os.environ, "MARK42_TEXT_USE_LLM": "auto"},
    )
    if code == 0 and "PASS" in out:
        ok("env=auto + 大输入 (>5KB) → LLM")
    else:
        err("env=auto+big", stderr.strip() or out.strip()[-300:])

    # 4. MARK42_TEXT_USE_LLM=auto + 小输入 -> rule_based
    # 需 ≥ 4KB 触发 text 路由, 但 auto 阈值 5KB 决定是否走 LLM
    # 用 100 行 约 3KB, > 4KB *不会被* 触发 (另选 150 行约 4.5KB)
    code, out, stderr = run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{workspace}/scripts'); "
         f"from mark42_modules.algo_scheduler import process; "
         f"text = '总而言之，第 001 段。\\n' * 150; "  # ~4.5KB: 触发 text 但 auto 不走 LLM
         f"assert len(text.encode()) >= 4*1024, 'text too small'; "
         f"assert len(text.encode()) < 5*1024, 'text too big'; "
         f"r = process(text); "
         f"assert r.get('llm_used') is False or r.get('llm_used') is None, 'auto+small should not use LLM, got ' + str(r.get('llm_used')); "
         f"ratio = r['compress_stats']['ratio'] if r.get('compress_stats') else 'N/A'; "
         f"print('PASS: auto+small=rule_based, ratio=' + str(ratio))"
        ],
        timeout=30,
        env={**os.environ, "MARK42_TEXT_USE_LLM": "auto"},
    )
    if code == 0 and "PASS" in out:
        ok("env=auto + 小输入 (<5KB) → rule_based")
    else:
        err("env=auto+small", stderr.strip() or out.strip()[-300:])


def test_day7_async_queue():
    """阶段 1 Day 7: 压缩子系统异步化"""
    print("\n⚡ Day 7 异步化专项 (CompressQueue)")
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "compress_queue.py")],
        timeout=60,
    )
    if code == 0 and "通过" in out:
        import re as _re
        m = _re.search(r"(\d+)\s*通过\s*/\s*(\d+)\s*失败", out)
        if m:
            ok(f"CompressQueue 单元测试 ({m.group(1)}/{int(m.group(1))+int(m.group(2))})")
        else:
            ok("CompressQueue 单元测试")
    else:
        err("CompressQueue 单元测试", stderr.strip() or out.strip()[-300:])

    # 集成: armor_compress_async 入口
    print("\n⚡ Day 7 集成: armor_compress_async")
    workspace = SCRIPTS.parent
    code, out, stderr = run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{workspace}/scripts'); "
         f"from mark42_modules.armor import armor_compress_async, armor_compress_queue_stats; "
         f"r1 = armor_compress_async(wait=False); "
         f"assert r1.get('status') == 'queued', f'expected queued, got {{r1}}'; "
         f"r2 = armor_compress_async(wait=True, priority=1); "
         f"assert r2.get('status') == 'completed', f'expected completed, got {{r2}}'; "
         f"assert r2['result']['route_algo'] in ('smartcrush', 'code', 'diff', 'log', 'text'); "
         f"stats = armor_compress_queue_stats(); "
         f"assert 'processed' in stats; "
         f"print('PASS: async entry works')"
        ],
        timeout=30,
    )
    if code == 0 and "PASS" in out:
        ok("armor_compress_async 集成 (queue + wait + priority)")
    else:
        err("armor_compress_async 集成", stderr.strip() or out.strip()[-300:])


def test_day8_llm_compress():
    """阶段 1 Day 8: LLM 语义压缩"""
    print("\n🧠 Day 8 LLM 语义压缩专项")
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "llm_text_compressor.py")],
        timeout=120,
    )
    if code == 0 and "通过" in out:
        import re as _re
        m = _re.search(r"(\d+)\s*通过\s*/\s*(\d+)\s*失败", out)
        if m:
            ok(f"LLMTextCompressor 单元测试 ({m.group(1)}/{int(m.group(1))+int(m.group(2))})")
        else:
            ok("LLMTextCompressor 单元测试")
    else:
        err("LLMTextCompressor 单元测试", stderr.strip() or out.strip()[-300:])

    # 集成: text_compressor method="llm" 走 LLM
    print("\n🧠 Day 8 集成: text_compressor(method='llm')")
    workspace = SCRIPTS.parent
    code, out, stderr = run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '{workspace}/scripts'); "
         f"from mark42_modules.text_compressor import TextCompressor; "
         f"tc = TextCompressor(method='llm'); "
         f"sample = ('这是一段长文本。' * 100); "
         f"out, stats = tc.compress(sample); "
         f"assert stats['mode'].startswith('llm_'), f\"mode should start with llm_, got {{stats['mode']}}\"; "
         f"assert 'llm_info' in stats; "
         f"print('PASS: LLM mode works, mode=' + stats['mode'])"
        ],
        timeout=60,
    )
    if code == 0 and "PASS" in out:
        ok("text_compressor(method='llm') 集成")
    else:
        err("text_compressor(method='llm') 集成", stderr.strip() or out.strip()[-300:])


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


def test_day4_integration():
    """阶段 1 Day 4: 算法调度器接入 armor 集成测试"""
    print("\n🔗 Day 4 集成 (algo_scheduler 接入 armor)")
    env = os.environ.copy()
    env["MARK42_ALGO_SMARTCRUSH"] = "true"
    env["MARK42_ALGO_EXPERIMENT"] = "true"
    code, out, stderr = run(
        [sys.executable, str(SCRIPTS / "mark42_modules" / "test_day4_integration.py")],
        timeout=60,
        env=env,
    )
    if code == 0 and "0 失败" in out:
        ok("Day 4 集成测试")
    else:
        err("Day 4 集成测试", stderr.strip() or out.strip()[-500:])


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
    test_day6_algorithms()
    test_day7_async_queue()
    test_day8_llm_compress()
    test_phase2_async_llm()
    test_phase2_use_llm_env()
    test_session_fence()
    # 阶段 1 Day 4 集成
    test_day4_integration()

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
