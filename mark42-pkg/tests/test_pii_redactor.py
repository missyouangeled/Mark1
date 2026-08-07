"""从 pii_redactor.py 提取的单元测试。"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.pii_redactor import *

# ── PII 脱敏用例表（模块级常量）──
# 格式：(name, input, expected_to_contain, expected_not_to_contain)
#
# 提升为模块级是为了让下方 pytest 参数化测试与原有 run_tests() 共用同一份数据，
# 不产生两份会分叉的拷贝。
TEST_CASES = [
    (
        "email",
        "Contact me at user@example.com or admin@test.org",
        ["[REDACTED:email]"],
        ["user@example.com", "admin@test.org"],
    ),
    (
        "phone_cn",
        "我的手机是 13812345678，另一个 15987654321",
        ["[REDACTED:phone_cn]"],
        ["13812345678", "15987654321"],
    ),
    ("id_card_cn", "身份证: 110101199003078811", ["[REDACTED:id_card_cn]"], ["110101199003078811"]),
    (
        "api_key_openai",
        "API key: sk-proj-abcdefghijklmnopqrstuvwxyz1234567890ABCDEF",
        ["[REDACTED:api_key]"],
        ["sk-proj-abcdefghijklmnopqrstuvwxyz1234567890ABCDEF"],
    ),
    (
        "api_key_github",
        "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD",
        ["[REDACTED:api_key]"],
        ["ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD"],
    ),
    ("ipv4", "Server: 192.168.1.100, Backup: 8.8.8.8", ["[REDACTED:ipv4]"], ["192.168.1.100", "8.8.8.8"]),
    (
        "sensitive_path",
        "Config in ~/.ssh/id_rsa and /etc/passwd",
        ["[REDACTED:path]"],
        ["/.ssh/id_rsa", "/etc/passwd"],
    ),
    (
        "url_with_token",
        "API URL: https://api.example.com/v1?token=secretkey123456",
        ["[REDACTED:url_with_token]"],
        ["secretkey123456"],
    ),
    (
        "luhn_valid_credit_card",
        "Card: 4532015112830366 (test Visa)",
        ["[REDACTED:credit_card]"],
        ["4532015112830366"],
    ),
    (
        "luhn_invalid_number",
        "Random: 1234567890123456 (not a valid card)",
        [],  # 不应被脱敏
        ["[REDACTED:credit_card]"],
    ),
    (
        "local_ip_not_redacted",
        "Local: 127.0.0.1, broadcast: 0.0.0.0",
        ["127.0.0.1", "0.0.0.0"],  # 应保留
        ["[REDACTED:ipv4]"],
    ),
    (
        "chinese_name_weak_disabled",
        "张老师好，李总再见",
        ["张老师", "李总"],  # 弱匹配默认禁用, 应保留
        ["[REDACTED:name]"],
    ),
    (
        "dict_recursive",
        json.dumps(
            {"user": {"email": "a@b.com", "phone": "13812345678"}, "items": [{"note": "call 15987654321"}]},
            ensure_ascii=False,
        ),
        ["[REDACTED:email]", "[REDACTED:phone_cn]"],
        ["a@b.com", "13812345678", "15987654321"],
    ),
]


def _redact_case(redactor, name, inp):
    """执行单个用例的脱敏，返回 (输出文本, stats)。"""
    if name == "dict_recursive":
        obj = json.loads(inp)
        result, stats = redactor.redact_dict_values(obj)
        return json.dumps(result, ensure_ascii=False), stats
    return redactor.redact(inp)


# ── pytest 可见入口 ──
#
# 下方 run_tests() 是手写 runner，函数名不匹配 pytest.ini 的 python_functions = test_*，
# 导致本文件 13 个用例长期从未被 pytest 收集（静默跳过、零回归保护）。
# PII 脱敏是防泄漏机制，必须纳入测试。


@pytest.mark.parametrize(
    ("case_name", "inp", "must_contain", "must_not_contain"),
    TEST_CASES,
    ids=[c[0] for c in TEST_CASES],
)
def test_pii_redaction(case_name, inp, must_contain, must_not_contain):
    """逐例验证：应出现的占位符在，不应泄露的原文不在。"""
    redactor = PIIRedactor()
    out, stats = _redact_case(redactor, case_name, inp)

    for s in must_contain:
        assert s in out, f"[{case_name}] 缺少 {s!r}，实际输出: {out!r}"
    for s in must_not_contain:
        assert s not in out, f"[{case_name}] 泄露 {s!r}，实际输出: {out!r}"
    assert isinstance(stats, dict)


def test_case_table_not_shrunk():
    """守卫：用例表被抽空时，参数化会静默变成 0 个测试，这里显式拦住。"""
    assert len(TEST_CASES) >= 13, f"用例表异常缩小到 {len(TEST_CASES)} 条"


def run_tests():
    """PII 脱敏单元测试（保留的手写 runner，供直接 python 执行）"""
    logger.info("=" * 60)
    logger.info("PIIRedactor 单元测试")
    logger.info("=" * 60)

    redactor = PIIRedactor()

    test_cases = TEST_CASES

    passed = 0
    failed = 0
    for name, inp, must_contain, must_not_contain in test_cases:
        try:
            if name == "dict_recursive":
                obj = json.loads(inp)
                result, stats = redactor.redact_dict_values(obj)
                out = json.dumps(result, ensure_ascii=False)
            else:
                out, stats = redactor.redact(inp)

            ok = True
            for s in must_contain:
                if s not in out:
                    logger.error(f"  ❌ [{name}] 缺少: {s!r} → 输出: {out!r}")
                    ok = False
            for s in must_not_contain:
                if s in out:
                    logger.error(f"  ❌ [{name}] 泄漏: {s!r} → 输出: {out!r}")
                    ok = False

            if ok:
                logger.info(
                    f"  ✅ [{name}] redactions={stats['total_redactions']} "
                    f"({stats.get('original_bytes', 0)}→{stats.get('redacted_bytes', out.encode().__len__())} bytes)"
                )
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"  ❌ [{name}] 异常: {e}")
            failed += 1

    logger.info("")
    logger.info(f"结果: {passed} 通过 / {failed} 失败 / 共 {len(test_cases)} 个")
    return failed == 0
