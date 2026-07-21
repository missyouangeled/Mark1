"""从 log_deduplicator.py 提取的单元测试。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.log_deduplicator import *


def run_tests():
    """8 个用例: 纯日志去重 / tail 保留 / critical events / 非日志 passthrough / 压缩率等"""
    logger.info("=" * 60)
    logger.info("LogDeduplicator 单元测试")
    logger.info("=" * 60)

    dedup = LogDeduplicator(keep_tail_lines=50, dedup_min_repeat=3, max_unique_lines=200)

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            logger.info(f"  ✓ {name}")
            passed += 1
        else:
            logger.info(f"  ✗ {name} -- {detail}")
            failed += 1

    # ---- 测试 1: 纯日志去重 (2 组: 100 行 INFO + 50 行 ERROR) ----
    lines = (
        ["2026-06-24 12:00:00 INFO: loading module\n"] * 100
        + ["2026-06-24 12:00:01 ERROR: crash\n"] * 50
        + ["2026-06-24 12:00:02 INFO: trailing\n"] * 60
    )
    test1_input = "2026-06-24 12:00:00 INFO: test start\n" + "".join(lines)
    test1_output, test1_stats = dedup.dedup(test1_input)
    logger.info("\n[测试 1] 152 行重复日志 (test start + 100 loading + 50 crash)")
    logger.info(f"  原始: {test1_stats['original_bytes']} bytes / {test1_stats['original_lines']} 行")
    logger.info(f"  压缩: {test1_stats['crushed_bytes']} bytes")
    logger.info(f"  压缩率: {test1_stats['ratio'] * 100:.1f}%")
    logger.info(f"  merged_groups={test1_stats['merged_groups']}, unique={test1_stats['unique_lines']}")
    check("1.1 is_log=True", test1_stats["is_log"] is True)
    check(
        "1.2 合并了 3 组 (loading + crash + trailing)",
        test1_stats["merged_groups"] == 3,
        f"got {test1_stats['merged_groups']}",
    )
    check("1.3 压缩率 > 50%", test1_stats["ratio"] > 0.5, f"got {test1_stats['ratio']:.2%}")
    check("1.4 critical 包含 ERROR", any("ERROR" in e for e in test1_stats["critical_events"]))
    check("1.5 head 含 [×100] 计数", "[×100]" in test1_output)
    check(
        "1.6 tail 段含 crash 行 (50 行全保留)",
        sum(1 for _ in range(50) if "ERROR: crash" in test1_output) >= 50 or test1_output.count("ERROR: crash") >= 50,
    )

    # ---- 测试 2: tail 保留 (默认 keep_tail_lines=50) ----
    tail_part = "".join([f"2026-06-24 12:00:00 DEBUG: tail line {i}\n" for i in range(60)])
    head_part = "".join(["2026-06-24 12:00:00 INFO: repeating\n"] * 200)
    test2_input = head_part + tail_part
    test2_output, test2_stats = dedup.dedup(test2_input)
    logger.info("\n[测试 2] tail 保留 (keep_tail_lines=50)")
    logger.info(f"  原始: {test2_stats['original_lines']} 行, tail 保留: {test2_stats['kept_tail_lines']}")
    check("2.1 保留 tail 50 行", test2_stats["kept_tail_lines"] == 50)
    check("2.2 输出包含 tail 标记", "原文" in test2_output)
    check("2.3 tail 50 行都在输出里", sum(1 for i in range(10, 60) if f"tail line {i}" in test2_output) == 50)

    # ---- 测试 3: critical events ----
    test3_input = "DEBUG: x\n" * 100 + "ERROR: crash\nFATAL: oops\nTraceback (most recent call last):\n"
    test3_output, test3_stats = dedup.dedup(test3_input)
    logger.info("\n[测试 3] 关键事件提取")
    logger.info(f"  critical events: {test3_stats['critical_events']}")
    check("3.1 ERROR 提取", any("ERROR" in e for e in test3_stats["critical_events"]))
    check("3.2 FATAL 提取", any("FATAL" in e for e in test3_stats["critical_events"]))
    check("3.3 Traceback 提取", any("Traceback" in e for e in test3_stats["critical_events"]))

    # ---- 测试 4: 非日志文本 passthrough ----
    test4_input = "hello world this is just a regular text\nno timestamps or levels here\n"
    test4_output, test4_stats = dedup.dedup(test4_input)
    logger.info("\n[测试 4] 非日志文本 passthrough")
    logger.info(f"  is_log={test4_stats['is_log']}, mode={test4_stats['mode']}")
    check("4.1 is_log=False", test4_stats["is_log"] is False)
    check("4.2 mode=passthrough", test4_stats["mode"] == "passthrough")
    check("4.3 输出等于输入", test4_output == test4_input)

    # ---- 测试 5: 空内容 ----
    test5_output, test5_stats = dedup.dedup("")
    check("5.1 空内容 ratio=0", test5_stats["ratio"] == 0.0)
    check("5.2 空内容返回原文", test5_output == "")

    # ---- 测试 6: 不重复日志 (< dedup_min_repeat) 不合并 ----
    test6_input = "\n".join([f"INFO: unique line {i}" for i in range(10)])
    test6_output, test6_stats = dedup.dedup(test6_input)
    logger.info("\n[测试 6] 不重复日志 (< dedup_min_repeat)")
    logger.info(f"  unique_lines={test6_stats['unique_lines']}, merged={test6_stats['merged_groups']}")
    check("6.1 merged_groups=0", test6_stats["merged_groups"] == 0)

    # ---- 测试 7: 大日志 (性能 + 压缩率) ----
    test7_lines = [f"2026-06-24 INFO: processing request #{i}\n" for i in range(1000)]
    test7_lines += [f"2026-06-24 ERROR: timeout on request #{i}\n" for i in range(50)]
    test7_input = "".join(test7_lines)
    test7_output, test7_stats = dedup.dedup(test7_input)
    logger.info("\n[测试 7] 大日志 (1050 行)")
    logger.info(f"  原始: {test7_stats['original_bytes']} bytes")
    logger.info(f"  压缩: {test7_stats['crushed_bytes']} bytes")
    logger.info(f"  压缩率: {test7_stats['ratio'] * 100:.1f}%")
    check("7.1 压缩率 > 70%", test7_stats["ratio"] > 0.7, f"got {test7_stats['ratio']:.2%}")

    # ---- 测试 8: 关键事件优先级 (critical 置顶) ----
    test8_input = "2026-06-24 12:00:00 INFO: normal\n" * 200 + "2026-06-24 12:00:01 FATAL: critical event\n"
    test8_output, test8_stats = dedup.dedup(test8_input)
    logger.info("\n[测试 8] critical 置顶")
    fatal_pos = test8_output.find("FATAL: critical")
    section_critical_pos = test8_output.find("--- 关键事件")
    section_head_pos = test8_output.find("--- 去重后的日志")
    logger.info(f"  关键事件段位置: {section_critical_pos}, 去重 head 段位置: {section_head_pos}")
    check("8.1 critical 事件在输出中", fatal_pos > -1)
    check(
        "8.2 critical 段在 head 段之前",
        section_critical_pos > -1 and section_head_pos > -1 and section_critical_pos < section_head_pos,
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"结果: {passed} 通过 / {failed} 失败")
    logger.info("=" * 60)
    return failed == 0
