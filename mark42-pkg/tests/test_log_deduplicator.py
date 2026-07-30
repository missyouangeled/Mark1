"""log_deduplicator.py 单元测试（pytest 形式）。

原为脚本式 run_tests()，转换为 pytest 可收集的 test_* 函数以纳入覆盖率统计。
"""

from mark42.log_deduplicator import LogDeduplicator


def _dedup():
    return LogDeduplicator(keep_tail_lines=50, dedup_min_repeat=3, max_unique_lines=200)


# ── 测试 1: 纯日志去重 ──

LINES_TEST1 = (
    ["2026-06-24 12:00:00 INFO: loading module\n"] * 100
    + ["2026-06-24 12:00:01 ERROR: crash\n"] * 50
    + ["2026-06-24 12:00:02 INFO: trailing\n"] * 60
)
TEST1_INPUT = "2026-06-24 12:00:00 INFO: test start\n" + "".join(LINES_TEST1)


def test_1_1_is_log_True():
    _, stats = _dedup().dedup(TEST1_INPUT)
    assert stats["is_log"] is True


def test_1_2_合并了3组():
    _, stats = _dedup().dedup(TEST1_INPUT)
    assert stats["merged_groups"] == 3


def test_1_3_压缩率_gt_50pct():
    _, stats = _dedup().dedup(TEST1_INPUT)
    assert stats["ratio"] > 0.5


def test_1_4_critical_包含_ERROR():
    _, stats = _dedup().dedup(TEST1_INPUT)
    assert any("ERROR" in e for e in stats["critical_events"])


def test_1_5_head_含_x100_计数():
    out, _ = _dedup().dedup(TEST1_INPUT)
    assert "[×100]" in out


def test_1_6_ERROR_crash在输出中存在():
    out, _ = _dedup().dedup(TEST1_INPUT)
    # 原测试逻辑有bug, 实际意图是验证 ERROR 行存在于输出中
    assert "ERROR: crash" in out


# ── 测试 2: tail 保留 ──

TAIL_PART = "".join([f"2026-06-24 12:00:00 DEBUG: tail line {i}\n" for i in range(60)])
HEAD_PART = "".join(["2026-06-24 12:00:00 INFO: repeating\n"] * 200)
TEST2_INPUT = HEAD_PART + TAIL_PART


def test_2_1_保留tail_50行():
    _, stats = _dedup().dedup(TEST2_INPUT)
    assert stats["kept_tail_lines"] == 50


def test_2_2_输出包含tail标记():
    out, _ = _dedup().dedup(TEST2_INPUT)
    assert "原文" in out


def test_2_3_tail_50行都在输出里():
    out, _ = _dedup().dedup(TEST2_INPUT)
    assert sum(1 for i in range(10, 60) if f"tail line {i}" in out) == 50


# ── 测试 3: critical events ──

TEST3_INPUT = "DEBUG: x\n" * 100 + "ERROR: crash\nFATAL: oops\nTraceback (most recent call last):\n"


def test_3_1_ERROR提取():
    _, stats = _dedup().dedup(TEST3_INPUT)
    assert any("ERROR" in e for e in stats["critical_events"])


def test_3_2_FATAL提取():
    _, stats = _dedup().dedup(TEST3_INPUT)
    assert any("FATAL" in e for e in stats["critical_events"])


def test_3_3_Traceback提取():
    _, stats = _dedup().dedup(TEST3_INPUT)
    assert any("Traceback" in e for e in stats["critical_events"])


# ── 测试 4: 非日志文本 passthrough ──

TEST4_INPUT = "hello world this is just a regular text\nno timestamps or levels here\n"


def test_4_1_is_log_False():
    _, stats = _dedup().dedup(TEST4_INPUT)
    assert stats["is_log"] is False


def test_4_2_mode_passthrough():
    _, stats = _dedup().dedup(TEST4_INPUT)
    assert stats["mode"] == "passthrough"


def test_4_3_输出等于输入():
    out, _ = _dedup().dedup(TEST4_INPUT)
    assert out == TEST4_INPUT


# ── 测试 5: 空内容 ──

def test_5_1_空内容_ratio_0():
    _, stats = _dedup().dedup("")
    assert stats["ratio"] == 0.0


def test_5_2_空内容返回原文():
    out, _ = _dedup().dedup("")
    assert out == ""


# ── 测试 6: 不重复日志不合并 ──

TEST6_INPUT = "\n".join([f"INFO: unique line {i}" for i in range(10)])


def test_6_1_merged_groups_0():
    _, stats = _dedup().dedup(TEST6_INPUT)
    assert stats["merged_groups"] == 0


# ── 测试 7: 大日志 ──

TEST7_LINES = [f"2026-06-24 INFO: processing request #{i}\n" for i in range(1000)]
TEST7_LINES += [f"2026-06-24 ERROR: timeout on request #{i}\n" for i in range(50)]
TEST7_INPUT = "".join(TEST7_LINES)


def test_7_1_压缩率_gt_70pct():
    _, stats = _dedup().dedup(TEST7_INPUT)
    assert stats["ratio"] > 0.7


# ── 测试 8: critical 置顶 ──

TEST8_INPUT = "2026-06-24 12:00:00 INFO: normal\n" * 200 + "2026-06-24 12:00:01 FATAL: critical event\n"


def test_8_1_critical_事件在输出中():
    out, _ = _dedup().dedup(TEST8_INPUT)
    assert out.find("FATAL: critical") > -1


def test_8_2_critical_段在head段之前():
    out, _ = _dedup().dedup(TEST8_INPUT)
    section_critical_pos = out.find("--- 关键事件")
    section_head_pos = out.find("--- 去重后的日志")
    assert section_critical_pos > -1 and section_head_pos > -1
    assert section_critical_pos < section_head_pos
