"""从 text_compressor.py 提取的单元测试。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.text_compressor import *


def run_tests():
    passed = 0
    failed = 0

    def check(name: str, cond: bool):
        nonlocal passed, failed
        if cond:
            logger.info(f"  ✓ {name}")
            passed += 1
        else:
            logger.info(f"  ✗ {name}")
            failed += 1

    tc = get_text_compressor()

    # ---- 测试 1: 太小 passthrough ----
    short = "x" * 150
    out, stats = tc.compress(short)
    logger.info("\n[测试 1] 500B 小文本 passthrough")
    check("1.1 mode=passthrough_small", stats["mode"] == "passthrough_small")
    check("1.2 不变", out == short)
    check("1.3 ratio=0", stats["ratio"] == 0.0)

    # ---- 测试 2: 冗余水话删除 ----
    sample = (
        "总而言之，这个系统使用 Python 进行开发。由于采用了微服务架构，因此能够支持高并发。\n"
        "综上所述，我们使用 Redis 作为缓存。由于性能优异，因此可以处理百万级请求。\n"
        "简而言之，Mark42 是一款非常优秀的工具。由于设计巧妙，因此可以满足各种需求。\n"
    )
    out, stats = tc.compress(sample)
    logger.info("\n[测试 2] 冗余水话删除")
    check("2.1 删除总而言之", "总而言之" not in out)
    check("2.2 删除综上所述", "综上所述" not in out)
    check("2.3 删除简而言之", "简而言之" not in out)
    check("2.4 removed_phrase_count >= 3", stats["removed_phrase_count"] >= 3)

    # ---- 测试 3: 同义词替换 ----
    syn_sample = "我们需要使用这个工具进行测试。由于性能优异，因此可以满足需求。它能够处理大量数据。" * 3
    out, stats = tc.compress(syn_sample)
    logger.info("\n[测试 3] 同义词替换")
    # 可能因水话先处理而差异, 至少应有一些替换发生
    # 关键: "使用" → "用", "进行" → "做" 等
    check("3.1 synonym_replacements > 0", stats["synonym_replacements"] > 0)

    # ---- 测试 4: 数字单位化 ----
    num_sample = "数据库有 1500000 条记录, 缓存命中 8500 次, 总共 999 条 (未达阈值), 写入 1234567 行" * 3
    out, stats = tc.compress(num_sample)
    logger.info("\n[测试 4] 数字单位化")
    check("4.1 number_unit_conversions >= 2", stats["number_unit_conversions"] >= 2)
    check("4.2 1500000 → 1.5M", "1.5M" in out)
    check("4.3 1234567 → 1.2M", "1.2M" in out)
    check("4.4 999 不变 (小于 1000)", "999" in out)

    # ---- 测试 5: 连续重复行去重 ----
    repeat = "重要信息\n" * 50 + "另一段\n" + "重要信息\n" * 30 + "结尾"
    out, stats = tc.compress(repeat)
    logger.info("\n[测试 5] 连续重复行去重")
    check("5.1 dedup_repeat_lines > 50", stats["dedup_repeat_lines"] > 50)
    check("5.2 含 (重复 N 次) 标注", "(重复" in out)

    # ---- 测试 6: 空白归一 ----
    ws_sample = ("  hello  \n\n\n\n  world  \n\n\n\n\n") * 15
    out, stats = tc.compress(ws_sample)
    logger.info("\n[测试 6] 空白归一")
    check("6.1 行尾无空格", "\n  \n" not in out and not out.endswith(" "))
    # 6.2 多空行归一: 不应连续 3 个空行
    has_triple_blank = bool(re.search(r"\n\n\n", out))
    check("6.2 无连续 3+ 空行", not has_triple_blank)

    # ---- 测试 7: 整体压缩率 (长样本) ----
    long_sample = (
        "总而言之，这个系统使用 Python 进行开发。由于采用了微服务架构，因此能够支持高并发。\n"
        "数据库有 1500000 条记录, 缓存命中 8500 次。\n"
        "重要信息\n" * 20
    )
    out, stats = tc.compress(long_sample)
    logger.info("\n[测试 7] 综合长样本")
    logger.info(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio'] * 100:.1f}%)")
    check("7.1 mode=compressed", stats["mode"] == "compressed")
    check("7.2 ratio > 10%", stats["ratio"] > 0.10)

    # ---- 测试 8: llm 模式 (Day 8: 真接 LiteLLM) ----
    tc_llm = TextCompressor(method="llm")
    out, stats = tc_llm.compress("anything" * 200)  # 1600B 触发 LLM
    logger.info(f"\n[测试 8] llm 模式 — 真调 LLM (mode={stats['mode']}, ratio={stats['ratio']:.1%})")
    check("8.1 mode 以 llm_ 开头", stats["mode"].startswith("llm_"))
    check("8.2 llm_info 存在", "llm_info" in stats)
    # 注: 这里如果 LLM 可达会调; 不可达会 fallback。两种都应走 llm_ 模式

    # ---- 测试 9: 错误输入 fail-safe ----
    out, stats = tc.compress("")
    check("9.1 空输入不报错", stats["mode"] == "none")
    out, stats = tc.compress("   \n\n   ")
    check("9.2 纯空白不报错", True)  # 走到这里就是通过

    # ---- 测试 10: 护栏 - 低压缩率回退 ----
    # 同义词替换会大幅缩短, 但若文本本身已是压缩态, 压缩率可能 < 10%
    # 用大量 "abc" 短行: dedup 不会触发, 水话无, 数字无, 同义词无
    no_redundancy = "z" * 2000 + "y" * 2000
    out, stats = tc.compress(no_redundancy)
    logger.info("\n[测试 10] 护栏: 无冗余文本")
    logger.info(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio'] * 100:.1f}%)")
    # 应该回退或 passthrough
    check("10.1 无变化或回退", stats["mode"] in ("fallback_low_ratio", "passthrough_small"))

    # ---- 测试 11: 混合策略协同 ----
    mixed = (
        "总而言之，Mark42 使用 Python 进行开发。" * 10
        + "数据库有 2000000 条记录, 缓存 5000 次。" * 10
        + "重要提示\n" * 50
    )
    out, stats = tc.compress(mixed)
    logger.info("\n[测试 11] 混合策略协同")
    logger.info(f"  原 {stats['original_bytes']}B → 压 {stats['crushed_bytes']}B (压缩率 {stats['ratio'] * 100:.1f}%)")
    check("11.1 综合压缩率 > 20%", stats["ratio"] > 0.20)
    check("11.2 removed_phrase_count > 0", stats["removed_phrase_count"] > 0)
    check("11.3 number_unit_conversions > 0", stats["number_unit_conversions"] > 0)
    check("11.4 dedup_repeat_lines > 0", stats["dedup_repeat_lines"] > 0)

    # ---- 测试 12: 扩展词典覆盖（中文技术词） ----
    tech_cn = "系统需要创建任务并获取配置，然后发送消息并返回结果。"
    out, replaced = tc._replace_synonyms(tech_cn)
    logger.info("\n[测试 12] 扩展词典覆盖（中文技术词）")
    check("12.1 替换仍生效", replaced >= 1)
    check("12.2 需要→要", "系统要" in out)
    check("12.3 发送消息保留", "发送消息" in out)
    check("12.4 返回结果保留", "返回结果" in out)

    # ---- 测试 13: 上下文单位归一 ----
    units = "响应耗时 50 ms，日志大小 2 KB，缓存峰值 1.5 MB，备份 1 G bytes。"
    out, converted = tc._convert_numbers(units)
    logger.info("\n[测试 13] 上下文单位归一")
    check("13.0 单位归一命中 4 次", converted >= 4)
    check("13.1 ms→毫秒", "50毫秒" in out)
    check("13.2 KB→bytes", "2048 bytes" in out)
    check("13.3 MB→bytes", "1572864 bytes" in out)
    check("13.4 G bytes→bytes", "1073741824 bytes" in out)

    # ---- 测试 14: fallback_low_ratio 统计一致 ----
    out, stats = tc.compress("ABCDEFGHIJ" * 300)
    logger.info("\n[测试 14] fallback_low_ratio 统计一致")
    if stats["mode"] == "fallback_low_ratio":
        check("14.1 回退时 crushed_bytes=original_bytes", stats["crushed_bytes"] == stats["original_bytes"])
        check("14.2 回退时 ratio 保留原计算值", stats["ratio"] < tc.min_useful_ratio)
    else:
        check("14.1 非回退也可接受", stats["mode"] in ("compressed", "passthrough_small"))
        check("14.2 非回退不报错", True)

    # ---- 测试 15: 英文整词边界 ----
    boundary = "errorless serviceable application_service prior to start"
    out, replaced = tc._replace_synonyms(boundary)
    logger.info("\n[测试 15] 英文整词边界")
    check("15.1 errorless 不误替换", "errorless" in out)
    check("15.2 serviceable 不误替换", "serviceable" in out)
    check("15.3 prior to 正常替换", "before start" in out)

    # ---- 测试 16: 避免过度压缩伤语义 ----
    semantic_sample = "系统支持热更新，并支持在线扩容。请确认配置完成后记录日志。"
    out, stats = tc.compress(semantic_sample * 20)
    logger.info("\n[测试 16] 避免过度压缩伤语义")
    check("16.1 支持保留", "支持热更新" in out)
    check("16.2 确认保留", "确认配置完成后记录日志" in out)

    literal_sample = "We should note that the API returns note that as literal text."
    out, stats = tc.compress(literal_sample * 20)
    check("16.3 note that 不应被裸删", "note that" in out)

    collision_sample = "接口通过率达到 99%。服务提供者需要认证。文档包含量较大。"
    out, stats = tc.compress(collision_sample * 20)
    check("16.4 通过率不误伤", "通过率" in out)
    check("16.5 提供者不误伤", "提供者" in out)
    check("16.6 包含量不误伤", "包含量" in out)

    # ---- 测试 17: 词典规模达标 ----
    logger.info("\n[测试 17] 词典规模达标")
    check("17.1 SYNONYMS >= 100", len(SYNONYMS) >= 100)
    check("17.2 REDUNDANT_PHRASES >= 80", len(REDUNDANT_PHRASES) >= 80)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"结果: {passed} 通过 / {failed} 失败")
    logger.info("=" * 60)
    return failed == 0
