"""pii_redactor.py 测试群。

覆盖:
  - get_redactor() 工厂单例
  - _luhn_check() 信用卡校验
  - redact_pii(content) 包装函数
  - redact_pii_in_dict(obj) 递归脱敏
  - 关键边界: 本地 IP 排除 / invalid credit card 不误杀 / max_depth / custom replacement

设计:
  - 纯函数为主, 不需要 mock
  - 用真实字符串样本覆盖多种 PII 类型
  - 断言字段名按 pii_redactor.py 当前实现
"""

import runpy
import warnings

import pytest

from mark42_modules import pii_redactor


class TestPIIRedactorFactory:
    """get_redactor() 工厂测试群。"""

    def test_factory_singleton(self):
        r1 = pii_redactor.get_redactor()
        r2 = pii_redactor.get_redactor()
        assert r1 is r2

    def test_factory_returns_instance(self):
        redactor = pii_redactor.get_redactor()
        assert redactor is not None
        assert hasattr(redactor, "redact")
        assert hasattr(redactor, "redact_dict_values")


class TestLuhnCheck:
    """_luhn_check() 测试群。"""

    def test_valid_credit_card(self):
        assert pii_redactor._luhn_check("4532015112830366") is True

    def test_valid_credit_card_with_spaces_and_hyphens(self):
        assert pii_redactor._luhn_check("4532-0151 1283-0366") is True

    def test_invalid_credit_card(self):
        assert pii_redactor._luhn_check("1234567890123456") is False

    def test_invalid_credit_card_length(self):
        assert pii_redactor._luhn_check("123456789012") is False


class TestRedactText:
    """redact() / redact_pii() 文本脱敏测试群。"""

    def test_empty_content(self):
        result, meta = pii_redactor.redact_pii("")
        assert result == ""
        assert meta["original_bytes"] == 0
        assert meta["redacted_bytes"] == 0
        assert meta["total_redactions"] == 0

    def test_redacts_multiple_pii_types(self):
        text = (
            "联系邮箱 user@example.com，手机号 13812345678，"
            "OpenAI key=sk-proj-abcdefghijklmnopqrstuvwxyz1234567890，"
            "GitHub token=ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD，"
            "外网 IP 8.8.8.8，敏感路径 ~/.ssh/id_rsa，"
            "链接 https://api.example.com/v1?token=secretkey123456"
        )
        result, meta = pii_redactor.redact_pii(text)
        assert "user@example.com" not in result
        assert "13812345678" not in result
        assert "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890" not in result
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD" not in result
        assert "8.8.8.8" not in result
        assert "~/.ssh/id_rsa" not in result
        assert "secretkey123456" not in result
        assert "[REDACTED:email]" in result
        assert "[REDACTED:phone_cn]" in result
        assert result.count("[REDACTED:api_key]") >= 2
        assert "[REDACTED:ipv4]" in result
        assert "[REDACTED:path]" in result
        assert "[REDACTED:url_with_token]" in result
        assert meta["total_redactions"] >= 7
        assert meta["redactions_by_type"]["email"] == 1
        assert meta["redactions_by_type"]["phone_cn"] == 1

    def test_invalid_credit_card_not_redacted(self):
        text = "随机数字 1234567890123456 不是合法信用卡"
        result, meta = pii_redactor.redact_pii(text)
        assert result == text
        assert meta["total_redactions"] == 0
        assert meta["redactions_by_type"]["credit_card"] == 0

    def test_valid_credit_card_redacted(self):
        text = "测试卡号 4532015112830366"
        result, meta = pii_redactor.redact_pii(text)
        assert "4532015112830366" not in result
        assert "[REDACTED:credit_card]" in result
        assert meta["redactions_by_type"]["credit_card"] == 1

    def test_local_ips_are_excluded(self):
        text = "本地地址 127.0.0.1 和 0.0.0.0 不该被脱敏，公网 8.8.8.8 应该被脱敏。"
        result, meta = pii_redactor.redact_pii(text)
        assert "127.0.0.1" in result
        assert "0.0.0.0" in result
        assert "8.8.8.8" not in result
        assert result.count("[REDACTED:ipv4]") == 1
        assert meta["redactions_by_type"]["ipv4"] == 1

    def test_weak_chinese_name_rule_disabled_by_default(self):
        text = "张老师好，李总再见。"
        result, meta = pii_redactor.redact_pii(text)
        assert result == text
        assert meta["total_redactions"] == 0

    def test_can_enable_weak_chinese_name_rule(self):
        redactor = pii_redactor.PIIRedactor(enabled_types=["chinese_name_weak"])
        text = "张三老师好，李四总再见，王五经理到了。"
        result, meta = redactor.redact(text)
        assert "张三老师" not in result
        assert "王五经理" not in result
        assert "[REDACTED:name]" in result
        assert meta["redactions_by_type"]["chinese_name_weak"] >= 2

    def test_custom_replacement_is_used(self):
        redactor = pii_redactor.PIIRedactor(
            enabled_types=["email"],
            custom_replacements={"email": "<EMAIL>"},
        )
        result, meta = redactor.redact("请发到 user@example.com")
        assert result == "请发到 <EMAIL>"
        assert meta["redactions_by_type"]["email"] == 1

    def test_enabled_types_limits_scope(self):
        redactor = pii_redactor.PIIRedactor(enabled_types=["email"])
        text = "邮箱 user@example.com，手机 13812345678"
        result, meta = redactor.redact(text)
        assert "user@example.com" not in result
        assert "[REDACTED:email]" in result
        assert "13812345678" in result
        assert "phone_cn" not in meta["redactions_by_type"]
        assert meta["total_redactions"] == 1


class TestRedactDictValues:
    """redact_dict_values() / redact_pii_in_dict() 递归测试群。"""

    def test_redacts_nested_dict_and_list(self):
        payload = {
            "user": {
                "email": "a@b.com",
                "phone": "13812345678",
            },
            "items": [
                {"note": "call 15987654321"},
                "server 8.8.8.8",
                123,
            ],
        }
        result, meta = pii_redactor.redact_pii_in_dict(payload)
        assert result["user"]["email"] == "[REDACTED:email]"
        assert result["user"]["phone"] == "[REDACTED:phone_cn]"
        assert result["items"][0]["note"] == "call [REDACTED:phone_cn]"
        assert result["items"][1] == "server [REDACTED:ipv4]"
        assert result["items"][2] == 123
        assert meta["total_redactions"] == 4
        assert meta["redactions_by_type"]["email"] == 1
        assert meta["redactions_by_type"]["phone_cn"] == 2
        assert meta["redactions_by_type"]["ipv4"] == 1

    def test_max_depth_stops_recursion(self):
        redactor = pii_redactor.PIIRedactor(enabled_types=["email"])
        payload = {
            "level1": {
                "level2": {
                    "email": "deep@example.com",
                }
            }
        }
        result, meta = redactor.redact_dict_values(payload, max_depth=1)
        assert result["level1"]["level2"]["email"] == "deep@example.com"
        assert meta["total_redactions"] == 0

    def test_non_string_nodes_are_untouched(self):
        redactor = pii_redactor.PIIRedactor(enabled_types=["email"])
        payload = {
            "ok": True,
            "count": 42,
            "none": None,
            "values": [1, 2, 3],
        }
        result, meta = redactor.redact_dict_values(payload)
        assert result == payload
        assert meta["total_redactions"] == 0
        assert meta["original_bytes"] == 0
        assert meta["redacted_bytes"] == 0


class TestRunTestsHarness:
    """补 _run_tests() 与 __main__ 入口。"""

    def test_run_tests_success(self, capsys):
        ok = pii_redactor._run_tests()

        out = capsys.readouterr().out
        assert ok is True
        assert "PIIRedactor 单元测试" in out
        assert "结果: 13 通过 / 0 失败 / 共 13 个" in out

    def test_run_tests_failure_and_exception_paths(self, mocker, capsys):
        class FakeRedactor:
            def redact(self, content: str):
                if "Random:" in content:
                    raise RuntimeError("boom")
                return content, {
                    "original_bytes": len(content.encode("utf-8")),
                    "redacted_bytes": len(content.encode("utf-8")),
                    "total_redactions": 0,
                    "redactions_by_type": {},
                }

            def redact_dict_values(self, obj):
                return obj, {
                    "original_bytes": 0,
                    "redacted_bytes": 0,
                    "total_redactions": 0,
                    "redactions_by_type": {},
                }

        mocker.patch.object(pii_redactor, "PIIRedactor", return_value=FakeRedactor())

        ok = pii_redactor._run_tests()

        out = capsys.readouterr().out
        assert ok is False
        assert "缺少" in out or "泄漏" in out
        assert "异常: boom" in out

    def test_module_main_exits_zero_when_run_tests_pass(self, capsys):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with pytest.raises(SystemExit) as exc:
                runpy.run_module("mark42_modules.pii_redactor", run_name="__main__")

        out = capsys.readouterr().out
        assert exc.value.code == 0
        assert "PIIRedactor 单元测试" in out
