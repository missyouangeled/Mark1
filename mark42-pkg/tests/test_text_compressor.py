"""text_compressor.py 单元测试（pytest 形式）。

原为脚本式 run_tests()，转换为 pytest 可收集的 test_* 函数以纳入覆盖率统计。
"""

import re

from mark42.text_compressor import (
    TextCompressor,
    get_text_compressor,
    REDUNDANT_PHRASES,
    SYNONYMS,
)


def _tc():
    return get_text_compressor()


# ── 测试 1: 太小 passthrough ──

SHORT = "x" * 150


def test_1_1_mode_passthrough_small():
    _, stats = _tc().compress(SHORT)
    assert stats["mode"] == "passthrough_small"


def test_1_2_不变():
    out, _ = _tc().compress(SHORT)
    assert out == SHORT


def test_1_3_ratio_0():
    _, stats = _tc().compress(SHORT)
    assert stats["ratio"] == 0.0


# ── 测试 2: 冗余水话删除 ──

SAMPLE = (
    "总而言之，这个系统使用 Python 进行开发。由于采用了微服务架构，因此能够支持高并发。\n"
    "综上所述，我们使用 Redis 作为缓存。由于性能优异，因此可以处理百万级请求。\n"
    "简而言之，Mark42 是一款非常优秀的工具。由于设计巧妙，因此可以满足各种需求。\n"
)


def test_2_1_删除总而言之():
    out, _ = _tc().compress(SAMPLE)
    assert "总而言之" not in out


def test_2_2_删除综上所述():
    out, _ = _tc().compress(SAMPLE)
    assert "综上所述" not in out


def test_2_3_删除简而言之():
    out, _ = _tc().compress(SAMPLE)
    assert "简而言之" not in out


def test_2_4_removed_phrase_count_ge_3():
    _, stats = _tc().compress(SAMPLE)
    assert stats["removed_phrase_count"] >= 3


# ── 测试 3: 同义词替换 ──

SYN_SAMPLE = "我们需要使用这个工具进行测试。由于性能优异，因此可以满足需求。它能够处理大量数据。" * 3


def test_3_1_synonym_replacements_gt_0():
    _, stats = _tc().compress(SYN_SAMPLE)
    assert stats["synonym_replacements"] > 0


# ── 测试 4: 数字单位化 ──

NUM_SAMPLE = "数据库有 1500000 条记录, 缓存命中 8500 次, 总共 999 条 (未达阈值), 写入 1234567 行" * 3


def test_4_1_number_unit_conversions_ge_2():
    _, stats = _tc().compress(NUM_SAMPLE)
    assert stats["number_unit_conversions"] >= 2


def test_4_2_1500000_to_1_5M():
    out, _ = _tc().compress(NUM_SAMPLE)
    assert "1.5M" in out


def test_4_3_1234567_to_1_2M():
    out, _ = _tc().compress(NUM_SAMPLE)
    assert "1.2M" in out


def test_4_4_999_不变():
    out, _ = _tc().compress(NUM_SAMPLE)
    assert "999" in out


# ── 测试 5: 连续重复行去重 ──

REPEAT = "重要信息\n" * 50 + "另一段\n" + "重要信息\n" * 30 + "结尾"


def test_5_1_dedup_repeat_lines_gt_50():
    _, stats = _tc().compress(REPEAT)
    assert stats["dedup_repeat_lines"] > 50


def test_5_2_含重复N次标注():
    out, _ = _tc().compress(REPEAT)
    assert "(重复" in out


# ── 测试 6: 空白归一 ──

WS_SAMPLE = ("  hello  \n\n\n\n  world  \n\n\n\n\n") * 15


def test_6_1_行尾无空格():
    out, _ = _tc().compress(WS_SAMPLE)
    assert "\n  \n" not in out and not out.endswith(" ")


def test_6_2_无连续3空行():
    out, _ = _tc().compress(WS_SAMPLE)
    has_triple_blank = bool(re.search(r"\n\n\n", out))
    assert not has_triple_blank


# ── 测试 7: 整体压缩率 ──

LONG_SAMPLE = (
    "总而言之，这个系统使用 Python 进行开发。由于采用了微服务架构，因此能够支持高并发。\n"
    "数据库有 1500000 条记录, 缓存命中 8500 次。\n"
    + "重要信息\n" * 20
)


def test_7_1_mode_compressed():
    _, stats = _tc().compress(LONG_SAMPLE)
    assert stats["mode"] == "compressed"


def test_7_2_ratio_gt_10pct():
    _, stats = _tc().compress(LONG_SAMPLE)
    assert stats["ratio"] > 0.10


# ── 测试 8: llm 模式 ──


def test_8_1_mode_以llm开头():
    tc_llm = TextCompressor(method="llm")
    _, stats = tc_llm.compress("anything" * 200)
    assert stats["mode"].startswith("llm_")


def test_8_2_llm_info存在():
    tc_llm = TextCompressor(method="llm")
    _, stats = tc_llm.compress("anything" * 200)
    assert "llm_info" in stats


# ── 测试 9: 错误输入 fail-safe ──


def test_9_1_空输入不报错():
    _, stats = _tc().compress("")
    assert stats["mode"] == "none"


def test_9_2_纯空白不报错():
    _, stats = _tc().compress("   \n\n   ")
    assert True  # 走到这里就是通过


# ── 测试 10: 护栏 - 低压缩率回退 ──

NO_REDUNDANCY = "z" * 2000 + "y" * 2000


def test_10_1_无变化或回退():
    _, stats = _tc().compress(NO_REDUNDANCY)
    assert stats["mode"] in ("fallback_low_ratio", "passthrough_small")


# ── 测试 11: 混合策略协同 ──

MIXED = (
    "总而言之，Mark42 使用 Python 进行开发。" * 10
    + "数据库有 2000000 条记录, 缓存 5000 次。" * 10
    + "重要提示\n" * 50
)


def test_11_1_综合压缩率_gt_20pct():
    _, stats = _tc().compress(MIXED)
    assert stats["ratio"] > 0.20


def test_11_2_removed_phrase_count_gt_0():
    _, stats = _tc().compress(MIXED)
    assert stats["removed_phrase_count"] > 0


def test_11_3_number_unit_conversions_gt_0():
    _, stats = _tc().compress(MIXED)
    assert stats["number_unit_conversions"] > 0


def test_11_4_dedup_repeat_lines_gt_0():
    _, stats = _tc().compress(MIXED)
    assert stats["dedup_repeat_lines"] > 0


# ── 测试 12: 扩展词典覆盖（中文技术词） ──

TECH_CN = "系统需要创建任务并获取配置，然后发送消息并返回结果。"


def test_12_1_替换仍生效():
    out, replaced = _tc()._replace_synonyms(TECH_CN)
    assert replaced >= 1


def test_12_2_需要_要():
    out, _ = _tc()._replace_synonyms(TECH_CN)
    assert "系统要" in out


def test_12_3_发送消息保留():
    out, _ = _tc()._replace_synonyms(TECH_CN)
    assert "发送消息" in out


def test_12_4_返回结果保留():
    out, _ = _tc()._replace_synonyms(TECH_CN)
    assert "返回结果" in out


# ── 测试 13: 上下文单位归一 ──

UNITS = "响应耗时 50 ms，日志大小 2 KB，缓存峰值 1.5 MB，备份 1 G bytes。"


def test_13_0_单位归一命中4次():
    _, converted = _tc()._convert_numbers(UNITS)
    assert converted >= 4


def test_13_1_ms_毫秒():
    out, _ = _tc()._convert_numbers(UNITS)
    assert "50毫秒" in out


def test_13_2_KB_bytes():
    out, _ = _tc()._convert_numbers(UNITS)
    assert "2048 bytes" in out


def test_13_3_MB_bytes():
    out, _ = _tc()._convert_numbers(UNITS)
    assert "1572864 bytes" in out


def test_13_4_G_bytes_bytes():
    out, _ = _tc()._convert_numbers(UNITS)
    assert "1073741824 bytes" in out


# ── 测试 14: fallback_low_ratio 统计一致 ──


def test_14_1_回退统计一致():
    out, stats = _tc().compress("ABCDEFGHIJ" * 300)
    if stats["mode"] == "fallback_low_ratio":
        assert stats["crushed_bytes"] == stats["original_bytes"]
    else:
        assert stats["mode"] in ("compressed", "passthrough_small")


def test_14_2_回退ratio保留():
    out, stats = _tc().compress("ABCDEFGHIJ" * 300)
    if stats["mode"] == "fallback_low_ratio":
        assert stats["ratio"] < _tc().min_useful_ratio
    else:
        assert True


# ── 测试 15: 英文整词边界 ──

BOUNDARY = "errorless serviceable application_service prior to start"


def test_15_1_errorless不误替换():
    out, _ = _tc()._replace_synonyms(BOUNDARY)
    assert "errorless" in out


def test_15_2_serviceable不误替换():
    out, _ = _tc()._replace_synonyms(BOUNDARY)
    assert "serviceable" in out


def test_15_3_prior_to_正常替换():
    out, _ = _tc()._replace_synonyms(BOUNDARY)
    assert "before start" in out


# ── 测试 16: 避免过度压缩伤语义 ──

SEMANTIC_SAMPLE = "系统支持热更新，并支持在线扩容。请确认配置完成后记录日志。"


def test_16_1_支持保留():
    out, _ = _tc().compress(SEMANTIC_SAMPLE * 20)
    assert "支持热更新" in out


def test_16_2_确认保留():
    out, _ = _tc().compress(SEMANTIC_SAMPLE * 20)
    assert "确认配置完成后记录日志" in out


def test_16_3_note_that不应被裸删():
    literal_sample = "We should note that the API returns note that as literal text."
    out, _ = _tc().compress(literal_sample * 20)
    assert "note that" in out


COLLISION_SAMPLE = "接口通过率达到 99%。服务提供者需要认证。文档包含量较大。"


def test_16_4_通过率不误伤():
    out, _ = _tc().compress(COLLISION_SAMPLE * 20)
    assert "通过率" in out


def test_16_5_提供者不误伤():
    out, _ = _tc().compress(COLLISION_SAMPLE * 20)
    assert "提供者" in out


def test_16_6_包含量不误伤():
    out, _ = _tc().compress(COLLISION_SAMPLE * 20)
    assert "包含量" in out


# ── 测试 17: 词典规模达标 ──


def test_17_1_SYNONYMS_ge_100():
    assert len(SYNONYMS) >= 100


def test_17_2_REDUNDANT_PHRASES_ge_80():
    assert len(REDUNDANT_PHRASES) >= 80
