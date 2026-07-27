"""Consciousness 意识层单元测试。

测试范围:
  - SelfCheckResult / CertaintyAssessment 数据类
  - DETERMINISTIC_RULES 结构正确性
  - Consciousness 类初始化（默认规则）
  - assess_certainty() 对各种 issue 的路由
  - handle_issue() dry_run=True / False
  - auto_remediate() 修复器调用
  - mock get_compress / get_engine 等外部依赖
"""

import json
from unittest.mock import patch, MagicMock

import pytest


# ── 数据类测试 ───────────────────────────────────────────

class TestSelfCheckResult:
    """测试 SelfCheckResult 数据类。"""

    def test_can_create_empty(self):
        from mark42_modules.consciousness import SelfCheckResult

        result = SelfCheckResult(checked_at="2024-01-01", healthy=True)
        assert result.checked_at == "2024-01-01"
        assert result.healthy is True
        assert result.issues == []
        assert result.raw == {}

    def test_to_dict_works(self):
        from mark42_modules.consciousness import SelfCheckResult

        result = SelfCheckResult(
            checked_at="2024-01-01",
            healthy=False,
            issues=[{"source": "armor", "category": "context_alert"}],
            raw={"some": "data"},
        )
        d = result.to_dict()
        assert d["checked_at"] == "2024-01-01"
        assert d["healthy"] is False
        assert len(d["issues"]) == 1
        assert d["raw"] == {"some": "data"}


class TestCertaintyAssessment:
    """测试 CertaintyAssessment 数据类。"""

    def test_can_create(self):
        from mark42_modules.consciousness import CertaintyAssessment

        assess = CertaintyAssessment(
            certainty="100%",
            matched_rule="rule-001",
            archive_entry_id=None,
            archive_auto_approved=False,
            action="auto_remediate",
            reason="匹配规则",
            next_step="执行修复",
        )
        assert assess.certainty == "100%"
        assert assess.matched_rule == "rule-001"
        assert assess.action == "auto_remediate"

    def test_to_dict_works(self):
        from mark42_modules.consciousness import CertaintyAssessment

        assess = CertaintyAssessment(
            certainty="high",
            matched_rule=None,
            archive_entry_id="ERR-123",
            archive_auto_approved=True,
            action="auto_remediate",
            reason="命中档案",
            next_step="按档案执行",
        )
        d = assess.to_dict()
        assert d["certainty"] == "high"
        assert d["archive_entry_id"] == "ERR-123"
        assert d["archive_auto_approved"] is True


# ── DETERMINISTIC_RULES 测试 ─────────────────────────────

class TestDeterministicRules:
    """测试 DETERMINISTIC_RULES 常量结构。"""

    def test_rules_is_list(self):
        from mark42_modules.consciousness import DETERMINISTIC_RULES

        assert isinstance(DETERMINISTIC_RULES, list)
        assert len(DETERMINISTIC_RULES) > 0

    def test_each_rule_has_required_fields(self):
        from mark42_modules.consciousness import DETERMINISTIC_RULES

        for rule in DETERMINISTIC_RULES:
            assert "id" in rule
            assert "name" in rule
            assert "match" in rule
            assert "certainty" in rule
            assert "action" in rule
            assert "reason" in rule

    def test_match_has_source_and_category(self):
        from mark42_modules.consciousness import DETERMINISTIC_RULES

        for rule in DETERMINISTIC_RULES:
            match = rule["match"]
            assert "source" in match
            assert "category" in match

    def test_certainty_values_are_valid(self):
        from mark42_modules.consciousness import DETERMINISTIC_RULES

        valid_certainties = {"100%", "high", "low", "unknown"}
        for rule in DETERMINISTIC_RULES:
            assert rule["certainty"] in valid_certainties

    def test_action_values_are_valid(self):
        from mark42_modules.consciousness import DETERMINISTIC_RULES

        valid_actions = {"auto_remediate", "ask_user", "lookup_archive", "ask_advisor"}
        for rule in DETERMINISTIC_RULES:
            assert rule["action"] in valid_actions

    def test_rule_ids_are_unique(self):
        from mark42_modules.consciousness import DETERMINISTIC_RULES

        ids = [r["id"] for r in DETERMINISTIC_RULES]
        assert len(ids) == len(set(ids))


# ── Consciousness 初始化测试 ─────────────────────────────

class TestConsciousnessInit:
    """测试 Consciousness 类初始化。"""

    def test_init_with_defaults(self):
        from mark42_modules.consciousness import Consciousness, DETERMINISTIC_RULES

        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            with patch("mark42_modules.consciousness.ErrorArchive", return_value=MagicMock()):
                cs = Consciousness()
                assert cs.rules is DETERMINISTIC_RULES

    def test_init_with_custom_rules(self):
        from mark42_modules.consciousness import Consciousness

        custom_rules = [
            {"id": "test-001", "match": {"source": "test", "category": "test"},
             "certainty": "100%", "action": "ask_user", "reason": "test"}
        ]
        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            with patch("mark42_modules.consciousness.ErrorArchive", return_value=MagicMock()):
                cs = Consciousness(rules=custom_rules)
                assert cs.rules == custom_rules

    def test_init_with_custom_archive(self):
        from mark42_modules.consciousness import Consciousness

        mock_archive = MagicMock()
        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            cs = Consciousness(archive=mock_archive)
            assert cs.archive is mock_archive


# ── assess_certainty 测试 ─────────────────────────────────

class TestAssessCertainty:
    """测试 assess_certainty 路由逻辑。"""

    def _make_cs(self, mock_archive=None):
        from mark42_modules.consciousness import Consciousness, DETERMINISTIC_RULES

        if mock_archive is None:
            mock_archive = MagicMock()
            mock_archive.lookup.return_value = None

        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            return Consciousness(archive=mock_archive, rules=DETERMINISTIC_RULES)

    def test_match_rule_100_percent_context_alert(self):
        cs = self._make_cs()
        issue = {"source": "armor", "category": "context_alert"}
        assess = cs.assess_certainty(issue)
        assert assess.certainty == "100%"
        assert assess.matched_rule == "rule-004"
        assert assess.action == "auto_remediate"
        assert assess.archive_entry_id is None

    def test_match_rule_100_percent_process_down(self):
        cs = self._make_cs()
        issue = {"source": "sidecar", "category": "process_down"}
        assess = cs.assess_certainty(issue)
        assert assess.certainty == "100%"
        assert assess.matched_rule == "rule-003"
        assert assess.action == "auto_remediate"

    def test_match_rule_100_percent_loop_not_registered(self):
        cs = self._make_cs()
        issue = {"source": "engine", "category": "loop_not_registered"}
        assess = cs.assess_certainty(issue)
        assert assess.certainty == "100%"
        assert assess.matched_rule == "rule-005"
        assert assess.action == "auto_remediate"

    def test_match_rule_100_percent_embed_missing(self):
        cs = self._make_cs()
        issue = {"source": "sidecar", "category": "embed_index_missing"}
        assess = cs.assess_certainty(issue)
        assert assess.certainty == "100%"
        assert assess.matched_rule == "rule-002"
        assert assess.action == "auto_remediate"

    def test_match_rule_low_certainty(self):
        cs = self._make_cs()
        issue = {"source": "scratch", "category": "unknown_file"}
        assess = cs.assess_certainty(issue)
        assert assess.certainty == "low"
        assert assess.matched_rule == "rule-001"
        assert assess.action == "ask_user"

    def test_match_rule_unknown_certainty(self):
        cs = self._make_cs()
        issue = {"source": "systemd", "category": "service_modified"}
        assess = cs.assess_certainty(issue)
        assert assess.certainty == "unknown"
        assert assess.matched_rule == "rule-006"
        assert assess.action == "ask_user"

    def test_no_match_returns_unknown_and_ask_user(self):
        cs = self._make_cs()
        issue = {"source": "new_module", "category": "new_problem"}
        assess = cs.assess_certainty(issue)
        assert assess.certainty == "unknown"
        assert assess.matched_rule is None
        assert assess.action == "ask_user"

    def test_archive_hit_auto_approved(self):
        from mark42_modules.error_archive import ArchiveEntry
        mock_archive = MagicMock()
        mock_entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
            auto_approved=True,
        )
        mock_archive.lookup.return_value = mock_entry

        cs = self._make_cs(mock_archive)
        issue = {"source": "armor", "category": "context_alert"}
        assess = cs.assess_certainty(issue)

        assert assess.certainty == "high"
        assert assess.archive_entry_id == "ERR-123"
        assert assess.archive_auto_approved is True
        assert assess.action == "auto_remediate"

    def test_archive_hit_not_approved(self):
        from mark42_modules.error_archive import ArchiveEntry
        mock_archive = MagicMock()
        mock_entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
            auto_approved=False,
        )
        mock_archive.lookup.return_value = mock_entry

        cs = self._make_cs(mock_archive)
        issue = {"source": "armor", "category": "context_alert"}
        assess = cs.assess_certainty(issue)

        assert assess.certainty == "low"
        assert assess.archive_entry_id == "ERR-123"
        assert assess.archive_auto_approved is False
        assert assess.action == "ask_user"


# ── auto_remediate 测试 ───────────────────────────────────

class TestAutoRemediate:
    """测试 auto_remediate 修复执行逻辑。"""

    def _make_cs(self):
        from mark42_modules.consciousness import Consciousness, DETERMINISTIC_RULES

        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            with patch("mark42_modules.consciousness.ErrorArchive", return_value=MagicMock()):
                return Consciousness(rules=DETERMINISTIC_RULES)

    def test_dry_run_true_returns_ok_without_executing(self):
        cs = self._make_cs()
        issue = {"source": "armor", "category": "context_alert"}
        assessment = MagicMock()

        result = cs.auto_remediate(issue, assessment, dry_run=True)
        assert result["ok"] is True
        assert result["dry_run"] is True
        assert result["action"] == "would_execute"

    def test_no_executor_returns_error(self):
        cs = self._make_cs()
        issue = {"source": "unknown", "category": "unknown_category"}
        assessment = MagicMock()

        result = cs.auto_remediate(issue, assessment, dry_run=False)
        assert result["ok"] is False
        assert result["action"] == "no_executor"

    def test_blacklist_category_blocked(self):
        cs = self._make_cs()
        issue = {"source": "system", "category": "user_data_modification"}
        assessment = MagicMock()

        result = cs.auto_remediate(issue, assessment, dry_run=False)
        assert result["ok"] is False
        assert result["action"] == "blocked_by_blacklist"

# ── handle_issue 测试 ─────────────────────────────────────

class TestHandleIssue:
    """测试 handle_issue 主入口。"""

    def _make_cs(self, mock_archive=None):
        from mark42_modules.consciousness import Consciousness, DETERMINISTIC_RULES

        if mock_archive is None:
            mock_archive = MagicMock()
            mock_archive.lookup.return_value = None

        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            return Consciousness(archive=mock_archive, rules=DETERMINISTIC_RULES)

    def test_handle_issue_100_percent_dry_run(self):
        cs = self._make_cs()
        issue = {"source": "armor", "category": "context_alert"}

        result = cs.handle_issue(issue, dry_run=True)

        assert result["path"] == "C3_auto_remediate"
        assert result["remediation"]["dry_run"] is True

    def test_handle_issue_unknown_goes_to_dialog(self):
        cs = self._make_cs()
        issue = {"source": "new", "category": "unknown"}

        result = cs.handle_issue(issue, dry_run=True)

        assert result["path"] == "C4_dialog"
        assert "request" in result

    def test_handle_issue_low_certainty_goes_to_dialog(self):
        cs = self._make_cs()
        issue = {"source": "scratch", "category": "unknown_file"}

        result = cs.handle_issue(issue, dry_run=True)

        assert result["path"] == "C4_dialog"

    def test_handle_issue_archive_auto_approved(self):
        from mark42_modules.error_archive import ArchiveEntry
        mock_archive = MagicMock()
        mock_entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
            auto_approved=True,
        )
        mock_archive.lookup.return_value = mock_entry
        mock_archive.increment_auto_count.return_value = {
            "allowed": True, "count": 2
        }

        cs = self._make_cs(mock_archive)
        issue = {"source": "armor", "category": "context_alert"}

        result = cs.handle_issue(issue, dry_run=True)

        assert result["path"] == "C5_archive_auto_approved"
        assert result["result"]["archive_id"] == "ERR-123"
        assert result["result"]["auto_approved"] is True


# ── dialog 测试 ─────────────────────────────────────────

class TestDialog:
    """测试 dialog 主动对话请求生成。"""

    def _make_cs(self):
        from mark42_modules.consciousness import Consciousness, DETERMINISTIC_RULES

        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            with patch("mark42_modules.consciousness.ErrorArchive", return_value=MagicMock()):
                return Consciousness(rules=DETERMINISTIC_RULES)

    def test_dialog_generates_request(self):
        cs = self._make_cs()
        issue = {"source": "armor", "category": "context_alert",
                 "severity": "critical", "msg": "使用率过高"}
        assessment = MagicMock()
        assessment.certainty = "100%"

        req = cs.dialog(issue, assessment)

        assert req.trigger == "armor:context_alert"
        assert req.severity == "critical"
        # 默认是 user（如果没有真实 advisor）
        assert req.to in ("user", "advisor")

    def test_dialog_generates_options_for_100_percent(self):
        cs = self._make_cs()
        issue = {"source": "armor", "category": "context_alert",
                 "severity": "warning", "msg": "test"}
        assessment = MagicMock()
        assessment.certainty = "100%"

        req = cs.dialog(issue, assessment)

        option_ids = [o["id"] for o in req.options]
        assert "approve_remediation" in option_ids
        assert "ask_advisor" in option_ids
        assert "manual_decide" in option_ids

    def test_dialog_generates_options_for_ask_user(self):
        cs = self._make_cs()
        issue = {"source": "armor", "category": "context_alert",
                 "severity": "warning", "msg": "test"}
        assessment = MagicMock()
        assessment.certainty = "low"
        assessment.action = "ask_user"

        req = cs.dialog(issue, assessment)

        option_ids = [o["id"] for o in req.options]
        assert "approve_remediation" in option_ids
        assert "ask_advisor" in option_ids
        assert "manual_decide" in option_ids


# ── check_archive 测试 ──────────────────────────────────

class TestCheckArchive:
    """测试 check_archive C5 路径。"""

    def _make_cs(self, mock_archive=None):
        from mark42_modules.consciousness import Consciousness

        if mock_archive is None:
            mock_archive = MagicMock()
            mock_archive.lookup.return_value = None

        with patch("mark42_modules.consciousness.build_consciousness", return_value=MagicMock()):
            return Consciousness(archive=mock_archive)

    def test_no_archive_hit_returns_none(self):
        cs = self._make_cs()
        issue = {"source": "armor", "category": "context_alert"}

        result = cs.check_archive(issue)
        assert result is None

    def test_archive_not_approved_returns_none(self):
        from mark42_modules.error_archive import ArchiveEntry
        mock_archive = MagicMock()
        mock_entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
            auto_approved=False,
        )
        mock_archive.lookup.return_value = mock_entry

        cs = self._make_cs(mock_archive)
        issue = {"source": "armor", "category": "context_alert"}

        result = cs.check_archive(issue)
        assert result is None

    def test_archive_approved_returns_result(self):
        from mark42_modules.error_archive import ArchiveEntry
        mock_archive = MagicMock()
        mock_entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
            auto_approved=True,
        )
        mock_archive.lookup.return_value = mock_entry
        mock_archive.increment_auto_count.return_value = {
            "allowed": True, "count": 2
        }

        cs = self._make_cs(mock_archive)
        issue = {"source": "armor", "category": "context_alert"}

        result = cs.check_archive(issue)
        assert result is not None
        assert result["archive_id"] == "ERR-123"
        assert result["auto_approved"] is True
        assert result["count"] == 2

    def test_archive_cooldown_blocked(self):
        from mark42_modules.error_archive import ArchiveEntry
        mock_archive = MagicMock()
        mock_entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
            auto_approved=True,
        )
        mock_archive.lookup.return_value = mock_entry
        mock_archive.increment_auto_count.return_value = {
            "allowed": False, "count": 5, "require_reconfirm": True
        }

        cs = self._make_cs(mock_archive)
        issue = {"source": "armor", "category": "context_alert"}

        result = cs.check_archive(issue)
        assert result["auto_approved"] is False
        assert result["reason"] == "cooldown 触发，需要重新确认"
