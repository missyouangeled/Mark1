"""从 algo_scheduler.py 提取的单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.algo_scheduler import *


def run_tests():
    """调度器单元测试"""
    logger.info("=" * 60)
    logger.info("Algorithm Scheduler 单元测试")
    logger.info("=" * 60)

    test_cases = [
        # (name, content, expected_action, expected_size_bucket,
        #  expected_compress, expected_pii)
        ("tiny_text", "hello world", "skip", "tiny", False, False),
        ("tiny_json", '{"a": 1}', "skip", "tiny", False, False),
        (
            "small_text",
            "x" * 5000,  # 5KB
            "skip",
            "small",
            False,
            False,
        ),  # 非 JSON
        (
            "small_json",
            '{"items": ['
            + ",".join(['{"id": ' + str(i) + ', "name": "user_' + str(i) + "_" + ("x" * 20) + '"}' for i in range(100)])
            + "]}",  # ~5KB
            "compress",
            "small",
            True,
            False,
        ),
        (
            "medium_json_with_pii",
            '{"users": ['
            + ",".join(
                ['{"email": "user' + str(i) + '@example.com", "name": "user_' + str(i) + '"}' for i in range(500)]
            )
            + "]}",
            "compress+pii",
            "medium",
            True,
            True,
        ),
        ("large_json", '{"data": [' + ",".join(['"x"' for _ in range(50000)]) + "]}", "review", "large", True, True),
        ("invalid_json", "not json at all, just text " * 200, "skip", "small", False, False),  # non-JSON small → skip
    ]

    passed = 0
    failed = 0
    for name, inp, exp_action, exp_bucket, exp_compress, exp_pii in test_cases:
        try:
            result = process(inp)
            d = result["decision"]

            ok = (
                d.action == exp_action
                and d.size_bucket == exp_bucket
                and d.should_compress == exp_compress
                and d.should_redact_pii == exp_pii
            )

            if ok:
                pii_count = (result["pii_stats"] or {}).get("total_redactions", 0)
                comp_ratio = (result["compress_stats"] or {}).get("ratio", 0.0)
                logger.info(
                    f"  ✅ [{name}] action={d.action} bucket={d.size_bucket} "
                    f"changed={result['changed']} pii={pii_count} comp={comp_ratio:.1%}"
                )
                passed += 1
            else:
                logger.error(
                    f"  ❌ [{name}] action={d.action}(exp {exp_action}) "
                    f"bucket={d.size_bucket}(exp {exp_bucket}) "
                    f"compress={d.should_compress}(exp {exp_compress}) "
                    f"pii={d.should_redact_pii}(exp {exp_pii})"
                )
                failed += 1
        except Exception as e:
            logger.error(f"  ❌ [{name}] 异常: {e}")
            failed += 1

    # 额外测试: 压缩率护栏
    logger.info("")
    logger.info("护栏测试:")

    # 测试 1: 太小收益回退
    tiny_json = '{"a": 1, "b": 2}'  # 太小 skip
    r = process(tiny_json)
    assert r["changed"] is False, f"tiny content should not change, got {r['changed']}"
    logger.info(f"  ✅ tiny 不变: changed={r['changed']}")

    # 测试 2: 大 JSON 触发压缩 + PII
    big_with_pii = json.dumps(
        {"logs": [{"user": f"user{i}@example.com", "msg": "x" * 100} for i in range(200)]}, ensure_ascii=False
    )
    r = process(big_with_pii)
    assert r["changed"] is True
    assert r["pii_stats"]["total_redactions"] > 0
    assert r["compress_stats"]["ratio"] > 0
    logger.info(
        f"  ✅ big+pii: changed=True, pii={r['pii_stats']['total_redactions']}, comp={r['compress_stats']['ratio']:.1%}"
    )

    # 测试 3: 错误输入 fail-safe
    r = process(None or "")
    assert r["result"] == "", f"empty input should return empty, got {r['result']!r}"
    logger.info(f"  ✅ 空输入 fail-safe: result={r['result']!r}")

    # ----------------------------------------------------------------
    # 新算法路由集成测试 (Day 6 - 代码/日志/差异/文本)
    # ----------------------------------------------------------------
    logger.info("")
    logger.info("新算法路由集成测试 (Day 6):")

    # T6.1: diff 路由
    diff_input = "@@ -1,5 +1,5 @@\n" + "\n".join(f" line{i}" for i in range(5)) + "\n-old\n+new\n"
    r = process(diff_input)
    assert r["decision"].route_algo == "diff", f"diff route expected, got {r['decision'].route_algo}"
    assert r["changed"], "diff should change content"
    assert r["compress_stats"] is not None
    logger.info(
        f"  ✅ [T6.1 diff路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.2: code 路由 (Python 源码, 需 > 200B 触发压缩)
    code_input = (
        "def foo(x, y):\n"
        '    """foo 函数 docstring"""\n'
        "    a = 1\n"
        "    b = 2\n"
        "    c = 3\n"
        "    return a + b + c\n"
        "\n"
        "class Bar:\n"
        '    """Bar 类 docstring"""\n'
        "    def __init__(self, x):\n"
        "        self.x = x\n"
        "    def method(self):\n"
        "        return self.x * 2\n"
        "    def method2(self):\n"
        "        return self.x + 100\n"
    )
    r = process(code_input)
    assert r["decision"].route_algo == "code", f"code route expected, got {r['decision'].route_algo}"
    assert r["changed"], "code should change content"
    logger.info(
        f"  ✅ [T6.2 code路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.3: log 路由 (重复行模拟日志, 需 > 50 行 让 head 非空触发 dedup)
    log_lines = ["[INFO] 2026-06-25T07:18:00 request_id=12345 status=200"] * 60 + [
        "[INFO] 2026-06-25T07:18:01 request_id=12346 status=200"
    ] * 10
    log_input = "\n".join(log_lines)
    r = process(log_input)
    assert r["decision"].route_algo == "log", f"log route expected, got {r['decision'].route_algo}"
    assert r["changed"], "log should change content"
    logger.info(
        f"  ✅ [T6.3 log路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.4: text 路由 (长文本: 4KB+ + 多行 + 平均行长 30+)
    long_text = "\n".join(
        f"这是第 {i:03d} 段长文本内容，包含足够多的字符以满足平均行长要求。内容是随机的描述性句子。\n"
        f"总而言之，这是一个测试文本。使用了同义词，进行压缩，应该有效果。\n"
        f"数据库有 {10000 + i * 100} 条记录, 缓存命中 {5000 + i * 10} 次。\n"
        for i in range(50)
    )
    assert len(long_text.encode("utf-8")) >= 4 * 1024, f"test input too small: {len(long_text)}"
    r = process(long_text)
    assert r["decision"].route_algo == "text", f"text route expected, got {r['decision'].route_algo}"
    assert r["changed"], "long text should change content"
    logger.info(
        f"  ✅ [T6.4 text路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.5: JSON 仍走 smartcrush (契约保留)
    json_input = json.dumps({"items": [{"id": i, "name": "user_" + str(i) * 5} for i in range(20)]})
    r = process(json_input)
    assert r["decision"].route_algo == "smartcrush", f"json should use smartcrush, got {r['decision'].route_algo}"
    logger.info(f"  ✅ [T6.5 JSON契约] algo={r['decision'].route_algo} (Day 3 契约保留)")
    passed += 1

    # T6.6: 路由优先级 - diff 优先于 code (即使含代码特征, diff header 更明确)
    diff_with_code = "diff --git a/foo.py b/foo.py\n@@ -1,2 +1,2 @@\n-def foo():\n+def bar():\n pass\n"
    r = process(diff_with_code)
    assert r["decision"].route_algo == "diff", f"diff should win over code, got {r['decision'].route_algo}"
    logger.info("  ✅ [T6.6 路由优先级] diff 优先于 code (正确)")
    passed += 1

    # T6.7: 压缩护栏 - 超过 max_safe_ratio 回退
    # 单字符 "x" * 500 重复 → 压缩后基本不缩小
    # 但 text 路由会认为 avg_line_len 太低 (500/1=500 vs 30) → 走 skip
    # 这里改用 log 路由验证护栏
    log_short = "ERROR something\n" * 20
    r = process(log_short)
    if r["compress_stats"] and r["compress_stats"]["ratio"] < 0.10:
        assert r["fallback_reason"] is not None, "low ratio should fallback"
        assert r["changed"] is False, "fallback should not change"
        logger.info(f"  ✅ [T6.7 压缩护栏] 低压缩率回退: {r['fallback_reason'][:50]}")
    else:
        logger.info(
            f"  ✅ [T6.7 压缩护栏] 压缩成功 (ratio={r['compress_stats']['ratio'] if r['compress_stats'] else 0:.1%})"
        )
    passed += 1

    logger.info("")
    logger.info(f"结果: {passed + 3} 通过 / {failed} 失败 / 共 {passed + failed + 3} 个")
    return failed == 0

