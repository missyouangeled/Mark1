"""consciousness.py 测试 - 测试 C1-C5 自检/评估/修复流程。"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.consciousness import (
    DETERMINISTIC_RULES,
    CertaintyAssessment,
    Consciousness,
    SelfCheckResult,
    _remediate_context_alert,
    _remediate_embed_index_missing,
    _remediate_loop_not_registered,
    _remediate_process_down,
)

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print(f"  ✗ {name} -- {detail}")


def make_mock_consciousness():
    """创建 mock 依赖的 Consciousness 实例。"""
    llm = MagicMock()
    archive = MagicMock()
    archive.lookup.return_value = None  # 默认无档案命中
    config = {"consciousness": {"enabled": True}}
    c = Consciousness(llm=llm, archive=archive, rules=DETERMINISTIC_RULES, config=config)
    return c


# ── 测试 1: SelfCheckResult 数据类 ──
def test_self_check_result():
    r = SelfCheckResult(checked_at="2026-01-01T00:00:00", healthy=True, issues=[{"source": "test"}], raw={"test": 1})
    check("1.1 issues", len(r.issues) == 1)
    check("1.2 raw", r.raw["test"] == 1)
    check("1.3 healthy True", r.healthy == True)
    r_empty = SelfCheckResult(checked_at="now", healthy=True, issues=[], raw={})
    check("1.4 healthy True", r_empty.healthy == True)


# ── 测试 2: CertaintyAssessment 数据类 ──
def test_certainty_assessment():
    a = CertaintyAssessment(
        certainty="high",
        matched_rule="R1",
        archive_entry_id=None,
        archive_auto_approved=False,
        action="auto_remediate",
        reason="test",
        next_step="do something",
    )
    check("2.1 certainty", a.certainty == "high")
    check("2.2 action", a.action == "auto_remediate")
    check("2.3 to_dict works", isinstance(a.to_dict(), dict))
    a_low = CertaintyAssessment(
        certainty="low",
        matched_rule=None,
        archive_entry_id=None,
        archive_auto_approved=False,
        action="ask_user",
        reason="",
        next_step="",
    )
    check("2.4 low certainty", a_low.certainty == "low")


# ── 测试 3: C1 self_check ──
def test_self_check():
    c = make_mock_consciousness()
    result = c.self_check()
    check("3.1 返回 SelfCheckResult", isinstance(result, SelfCheckResult))
    check("3.2 有 raw", isinstance(result.raw, dict))
    check("3.3 checked_at 非空", result.checked_at is not None and len(result.checked_at) > 0)
    check("3.4 issues 是 list", isinstance(result.issues, list))


# ── 测试 4: C2 assess_certainty - 规则表匹配 ──
def test_assess_certainty_rule_match():
    c = make_mock_consciousness()
    # 用 DETERMINISTIC_RULES 中的第一个规则的 source/category
    if DETERMINISTIC_RULES:
        rule = DETERMINISTIC_RULES[0]
        m = rule["match"]
        issue = {"source": m["source"], "category": m["category"], "severity": "critical"}
        assessment = c.assess_certainty(issue)
        check("4.1 匹配规则表", assessment.matched_rule is not None)
        check("4.2 action 来自规则", assessment.action == rule["action"])
    else:
        check("4.1 DETERMINISTIC_RULES 非空", False, "规则表为空")


# ── 测试 5: C2 assess_certainty - 错误档案命中且已批准 ──
def test_assess_certainty_archive_approved():
    llm = MagicMock()
    archive = MagicMock()
    mock_entry = MagicMock()
    mock_entry.id = "ERR-001"
    mock_entry.auto_approved = True
    archive.lookup.return_value = mock_entry
    config = {"consciousness": {"enabled": True}}
    c = Consciousness(llm=llm, archive=archive, rules=DETERMINISTIC_RULES, config=config)

    issue = {"source": "armor", "category": "context_alert"}
    a = c.assess_certainty(issue)
    check("5.1 archive_entry_id", a.archive_entry_id == "ERR-001")
    check("5.2 auto_approved True", a.archive_auto_approved == True)
    check("5.3 action auto_remediate", a.action == "auto_remediate")
    check("5.4 certainty high", a.certainty == "high")


# ── 测试 6: C2 assess_certainty - 错误档案命中但未批准 ──
def test_assess_certainty_archive_not_approved():
    llm = MagicMock()
    archive = MagicMock()
    mock_entry = MagicMock()
    mock_entry.id = "ERR-002"
    mock_entry.auto_approved = False
    archive.lookup.return_value = mock_entry
    config = {"consciousness": {"enabled": True}}
    c = Consciousness(llm=llm, archive=archive, rules=DETERMINISTIC_RULES, config=config)

    issue = {"source": "armor", "category": "context_alert"}
    a = c.assess_certainty(issue)
    check("6.1 archive_entry_id", a.archive_entry_id == "ERR-002")
    check("6.2 auto_approved False", a.archive_auto_approved == False)
    check("6.3 action ask_user", a.action == "ask_user")
    check("6.4 certainty low", a.certainty == "low")


# ── 测试 7: C2 assess_certainty - 完全未匹配 ──
def test_assess_certainty_no_match():
    c = make_mock_consciousness()
    issue = {"source": "unknown_source", "category": "unknown_category"}
    a = c.assess_certainty(issue)
    check("7.1 certainty unknown", a.certainty == "unknown")
    check("7.2 action ask_user", a.action == "ask_user")
    check("7.3 matched_rule None", a.matched_rule is None)


# ── 测试 8: C3 auto_remediate dry_run ──
def test_auto_remediate_dry_run():
    c = make_mock_consciousness()
    issue = {"source": "test", "category": "test", "severity": "warning"}
    assessment = CertaintyAssessment(
        certainty="high",
        matched_rule="test",
        archive_entry_id=None,
        archive_auto_approved=False,
        action="auto_remediate",
        reason="test",
        next_step="test",
    )
    result = c.auto_remediate(issue, assessment, dry_run=True)
    check("8.1 返回 dict", isinstance(result, dict))
    check(
        "8.2 dry_run", result.get("dry_run") == True or result.get("executed") == False or result.get("ok") is not None
    )


# ── 测试 9: 修复函数 _remediate_context_alert ──
def test_remediate_context_alert():
    issue = {"source": "armor", "value": 90, "msg": "上下文 90%"}
    result = _remediate_context_alert(issue)
    check("10.1 返回 dict", isinstance(result, dict))
    check("10.2 有 ok/action", "ok" in result or "action" in result)


# ── 测试 11: 修复函数 _remediate_process_down ──
def test_remediate_process_down():
    issue = {"source": "engine", "msg": "daemon 挂了"}
    result = _remediate_process_down(issue)
    check("11.1 返回 dict", isinstance(result, dict))
    check("11.2 有 ok/action", "ok" in result or "action" in result)


# ── 测试 12: 修复函数 _remediate_embed_index_missing ──
def test_remediate_embed_index_missing():
    issue = {"source": "memory", "msg": "索引缺失"}
    result = _remediate_embed_index_missing(issue)
    check("12.1 返回 dict", isinstance(result, dict))
    check("12.2 有 ok/action", "ok" in result or "action" in result)


# ── 测试 13: 修复函数 _remediate_loop_not_registered ──
def test_remediate_loop_not_registered():
    issue = {"source": "engine", "msg": "loop 未注册"}
    result = _remediate_loop_not_registered(issue)
    check("13.1 返回 dict", isinstance(result, dict))
    check("13.2 有 ok/action", "ok" in result or "action" in result)


# ── 测试 14: DETERMINISTIC_RULES 结构验证 ──
def test_rules_structure():
    check("14.1 规则非空", len(DETERMINISTIC_RULES) > 0)
    for i, rule in enumerate(DETERMINISTIC_RULES):
        check(f"14.{i + 2}.1 规则{i} 有id", "id" in rule, f"rule={rule}")
        check(f"14.{i + 2}.2 规则{i} 有match", "match" in rule)
        check(f"14.{i + 2}.3 规则{i} 有certainty", "certainty" in rule)
        check(f"14.{i + 2}.4 规则{i} 有action", "action" in rule)


def run_tests():
    print("=" * 60)
    print("Consciousness 测试")
    print("=" * 60)

    test_self_check_result()
    test_certainty_assessment()
    test_self_check()
    test_assess_certainty_rule_match()
    test_assess_certainty_archive_approved()
    test_assess_certainty_archive_not_approved()
    test_assess_certainty_no_match()
    test_auto_remediate_dry_run()
    test_remediate_context_alert()
    test_remediate_process_down()
    test_remediate_embed_index_missing()
    test_remediate_loop_not_registered()
    test_rules_structure()

    print()
    print("=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    sys.exit(0 if run_tests() else 1)


class TestConsciousnessQmdState:
    """测试 self_check 中 QMD 三态报告（cross-encoder 接入方案）。"""

    def _patch_qmd_state(self, mocker, **overrides):
        """统一 mock builtin_memory 模块的状态。"""
        from mark42.plugins import builtin_memory
        defaults = {
            "QMD_BIN": "/usr/bin/qmd",
            "QMD_INDEX": "/home/x/.cache/qmd/index.sqlite",
            "QMD_VECTOR_MODE": "auto",
            "_model_complete": lambda f: True,
            "_vector_available": lambda: True,
            "_rerank_available": lambda: True,
        }
        defaults.update(overrides)
        for k, v in defaults.items():
            mocker.patch.object(builtin_memory, k, v)
        mocker.patch("os.path.isfile", return_value=True)

    def test_qmd_state_included_in_raw(self, mocker):
        """self_check 的 raw 应包含 qmd_state 字段。"""
        self._patch_qmd_state(mocker)
        from mark42.consciousness import Consciousness
        c = Consciousness()
        result = c.self_check()
        assert "qmd_state" in result.raw
        st = result.raw["qmd_state"]
        assert "qmd_bin" in st
        assert "embedding_model" in st
        assert "rerank_model" in st
        assert "vector_available" in st
        assert "rerank_available" in st
        assert "search_mode" in st
        assert "degraded_reason" in st

    def test_qmd_state_all_ok(self, mocker):
        """qmd + embedding + rerank 全部就绪时，degraded_reason 应为 None。"""
        self._patch_qmd_state(mocker)
        from mark42.consciousness import Consciousness
        c = Consciousness()
        result = c.self_check()
        st = result.raw["qmd_state"]
        assert st["qmd_bin"] == "ok"
        assert st["qmd_index"] == "ok"
        assert st["embedding_model"] == "ok"
        assert st["rerank_model"] == "ok"
        assert st["vector_available"] is True
        assert st["rerank_available"] is True
        assert st["degraded_reason"] is None

    def test_qmd_state_rerank_missing(self, mocker):
        """rerank 模型缺失时，degraded_reason 应标注。"""
        self._patch_qmd_state(
            mocker,
            _rerank_available=lambda: False,
        )
        # mock embedding 模型完整，rerank 缺失
        from mark42.plugins import builtin_memory
        def model_complete(name):
            return "embeddinggemma" in name
        mocker.patch.object(builtin_memory, "_model_complete", side_effect=model_complete)

        from mark42.consciousness import Consciousness
        c = Consciousness()
        result = c.self_check()
        st = result.raw["qmd_state"]
        assert st["rerank_model"] == "missing_or_downloading"
        assert st["rerank_available"] is False
        # vector 仍可用，但 rerank 不可用
        assert st["vector_available"] is True
        # auto 模式下只是 info 级
        info_issues = [i for i in result.issues if "vector" in i.get("msg", "").lower() or "rerank" in i.get("msg", "").lower()]
        # 至少有一条 rerank 相关 issue
        assert any("rerank" in i.get("msg", "").lower() or "vector" in i.get("msg", "").lower() for i in result.issues)

    def test_qmd_state_on_mode_but_models_incomplete(self, mocker):
        """on 模式但模型未就绪时，应是 warning 级 issue。"""
        self._patch_qmd_state(
            mocker,
            QMD_VECTOR_MODE="on",
            _vector_available=lambda: False,
            _model_complete=lambda f: False,
        )
        from mark42.consciousness import Consciousness
        c = Consciousness()
        result = c.self_check()
        # 应有降级警告
        warning_issues = [i for i in result.issues if i.get("severity") == "warning"]
        assert any("on" in i.get("msg", "") for i in warning_issues)
        st = result.raw["qmd_state"]
        assert st["degraded_reason"] == "on_mode_but_models_incomplete"

    def test_qmd_state_qmd_binary_missing(self, mocker):
        """qmd 二进制缺失时，degraded_reason 应标注。"""
        self._patch_qmd_state(
            mocker,
            QMD_BIN="",
        )
        mocker.patch("os.path.isfile", return_value=False)
        from mark42.consciousness import Consciousness
        c = Consciousness()
        result = c.self_check()
        st = result.raw["qmd_state"]
        assert st["qmd_bin"] == "missing"
        assert st["degraded_reason"] == "qmd_binary_or_index_missing"
        # 应有 process_down 类 issue
        cats = [i.get("category") for i in result.issues]
        assert "process_down" in cats
