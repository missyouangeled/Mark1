"""从 pii_redactor.py 提取的单元测试。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.pii_redactor import *


def run_tests():
    """PII 脱敏单元测试"""
    logger.info("=" * 60)
    logger.info("PIIRedactor 单元测试")
    logger.info("=" * 60)

    redactor = PIIRedactor()

    test_cases = [
        # (name, input, expected_to_contain, expected_not_to_contain)
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

