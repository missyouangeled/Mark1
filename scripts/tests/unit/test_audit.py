"""Post-Compact Audit 单测。

覆盖：
    1. SnapshotReader: 快照查找 + 关键信息提取
    2. SummaryExtractor: 摘要查找 + 文本提取
    3. Checker: LLM 核对 + 规则 fallback
    4. Report: 报告写入 + 清理
    5. BuiltinAudit: 集成流程
    6. armor hook: compact 后触发
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 让 import 能找到 mark42_modules
TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from mark42_modules.audit import (
    AuditResult, Finding, AUDIT_CATEGORIES,
    VERDICT_PASS_THRESHOLD, VERDICT_FAIL_CATEGORIES,
)
from mark42_modules.audit.snapshot_reader import OpenClawSnapshotReader
from mark42_modules.audit.summary_extractor import OpenClawSummaryExtractor
from mark42_modules.audit.checker import LLMChecker, RuleChecker
from mark42_modules.audit.report import write_report, send_alert, AUDIT_DIR


# ═════════════════════════════════════════════════════
# 1. 数据模型测试
# ═════════════════════════════════════════════════════


class TestAuditDataModel:
    """数据模型基本测试。"""

    def test_finding_creation(self):
        f = Finding(category="identity", item="用户: 袁文涛", status="preserved")
        assert f.category == "identity"
        assert f.status == "preserved"
        assert f.detail == ""

    def test_audit_result_defaults(self):
        r = AuditResult(verdict="pass", score=0.9)
        assert r.findings == []
        assert r.recommendation == ""
        assert r.timestamp == ""
        assert r.error == ""

    def test_audit_categories(self):
        assert "identity" in AUDIT_CATEGORIES
        assert "preferences" in AUDIT_CATEGORIES
        assert len(AUDIT_CATEGORIES) == 5

    def test_verdict_thresholds(self):
        assert VERDICT_PASS_THRESHOLD == 0.8
        assert "identity" in VERDICT_FAIL_CATEGORIES
        assert "preferences" in VERDICT_FAIL_CATEGORIES


# ═════════════════════════════════════════════════════
# 2. SnapshotReader 测试
# ═════════════════════════════════════════════════════


class TestSnapshotReader:
    """OpenClawSnapshotReader 测试。"""

    def test_find_latest_before_empty_dir(self, tmp_path):
        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        result = reader.find_latest_before("2026-07-29T10:00:00")
        assert result is None

    def test_find_latest_before_finds_correct(self, tmp_path):
        # 创建两个快照
        for ts, dirname in [
            ("2026-07-29T080000", "snapshot-2026-07-29T080000"),
            ("2026-07-29T100000", "snapshot-2026-07-29T100000"),
        ]:
            (tmp_path / dirname).mkdir()

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        result = reader.find_latest_before("2026-07-29T105000")
        assert result is not None
        assert "snapshot-2026-07-29T100000" in result["path"]
        assert result["source"] == "data-disk"

    def test_find_latest_before_excludes_future(self, tmp_path):
        (tmp_path / "snapshot-2026-07-29T120000").mkdir()
        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        result = reader.find_latest_before("2026-07-29T100000")
        assert result is None

    def test_extract_key_info_empty(self, tmp_path):
        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        snapshot = {"path": str(tmp_path / "nonexistent"), "timestamp": ""}
        info = reader.extract_key_info(snapshot)
        assert all(v == [] for v in info.values())

    def test_extract_key_info_from_files(self, tmp_path):
        # 创建模拟快照
        snap_dir = tmp_path / "snapshot-2026-07-29T100000"
        snap_dir.mkdir()

        (snap_dir / "USER.md").write_text(
            "**Name:** 袁文涛\n**What to call them:** 点点\n"
        )
        (snap_dir / "SOUL.md").write_text(
            "名字：贾维斯\n"
        )
        (snap_dir / "MEMORY.md").write_text(
            "# 长期记忆\n## 偏好规则\n- **语言锁定**: 只用中文\n## 项目\n## API\n"
        )
        (snap_dir / "context-summary.md").write_text(
            "## 今日摘要\n- 贾维斯：今天做了 compact 优化\n"
            "项目：Mark42 压缩子系统\n决策：平台优先策略\n"
        )
        (snap_dir / "daily-2026-07-29-transcript.md").write_text(
            "贾维斯·09:00：早上好\n贾维斯·10:00：开始工作\n"
        )

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        snapshot = {"path": str(snap_dir), "timestamp": "2026-07-29T10:00:00"}
        info = reader.extract_key_info(snapshot)

        # 身份信息
        assert any("袁文涛" in i for i in info["identity"])
        assert any("贾维斯" in i for i in info["identity"])

        # 偏好
        assert len(info["preferences"]) > 0

        # 项目和决策
        assert any("compact" in p.lower() or "Mark42" in p for p in info["projects"])

        # 近期话题
        assert len(info["recent_topics"]) > 0


# ═════════════════════════════════════════════════════
# 3. SummaryExtractor 测试
# ═════════════════════════════════════════════════════


class TestSummaryExtractor:
    """OpenClawSummaryExtractor 测试。"""

    def test_find_post_compact_summary_no_session(self, mocker):
        mocker.patch(
            "mark42_modules.audit.summary_extractor._find_active_session",
            return_value=None,
        )
        extractor = OpenClawSummaryExtractor()
        result = extractor.find_post_compact_summary("2026-07-29T10:00:00")
        assert result is None

    def test_find_post_compact_summary_found(self, mocker, tmp_path):
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("")

        mocker.patch(
            "mark42_modules.audit.summary_extractor._find_active_session",
            return_value=session_file,
        )

        extractor = OpenClawSummaryExtractor()
        result = extractor.find_post_compact_summary("2026-07-29T10:00:00")
        assert result is not None
        assert result["source"] == "openclaw-session"

    def test_extract_summary_text_with_compaction_marker(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({"role": "user", "content": "你好"}),
            json.dumps({"role": "assistant", "content": "你好"}),
            json.dumps({"role": "system", "content": "<summary>这是压缩后的摘要</summary>"}),
        ]
        session_file.write_text("\n".join(lines) + "\n")

        extractor = OpenClawSummaryExtractor()
        summary = {"path": str(session_file), "timestamp": ""}
        text = extractor.extract_summary_text(summary)
        assert "<summary>" in text
        assert "压缩后的摘要" in text

    def test_extract_summary_text_fallback_to_tail(self, tmp_path):
        """没有 compaction 标记时返回最近消息。"""
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({"role": "user", "content": "旧消息"}),
            json.dumps({"role": "assistant", "content": "旧回复"}),
            json.dumps({"role": "user", "content": "最新消息"}),
        ]
        session_file.write_text("\n".join(lines) + "\n")

        extractor = OpenClawSummaryExtractor()
        summary = {"path": str(session_file), "timestamp": ""}
        text = extractor.extract_summary_text(summary)
        assert "最新消息" in text


# ═════════════════════════════════════════════════════
# 4. Checker 测试
# ═════════════════════════════════════════════════════


class TestRuleChecker:
    """RuleChecker 测试（不依赖 LLM）。"""

    def test_all_preserved(self):
        checker = RuleChecker()
        pre_info = {
            "identity": ["袁文涛"],
            "preferences": ["中文"],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
        }
        summary = "袁文涛 使用中文交流"
        result = checker.check(pre_info, summary)
        assert result.verdict == "pass"
        assert result.score == 1.0

    def test_all_lost(self):
        checker = RuleChecker()
        pre_info = {
            "identity": ["张三"],
            "preferences": ["禁止英文"],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
        }
        summary = "今天天气不错"
        result = checker.check(pre_info, summary)
        assert result.verdict == "fail"
        assert result.score < 0.5

    def test_partial(self):
        checker = RuleChecker()
        pre_info = {
            "identity": ["袁文涛", "贾维斯"],
            "preferences": ["中文", "简洁"],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
        }
        # 只有一半信息在摘要里
        summary = "袁文涛 要求简洁回复"
        result = checker.check(pre_info, summary)
        assert result.verdict in ("partial", "pass")


class TestLLMChecker:
    """LLMChecker 测试。"""

    def test_llm_unavailable_falls_back_to_rule(self, mocker):
        checker = LLMChecker()
        mocker.patch.object(checker, "_get_llm", return_value=None)

        pre_info = {
            "identity": ["袁文涛"],
            "preferences": [],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
        }
        result = checker.check(pre_info, "袁文涛")
        assert result.verdict == "pass"
        # 应该降级到 RuleChecker
        assert result.error == "" or "降级" in result.error or result.error == ""

    def test_llm_parse_response(self):
        checker = LLMChecker()
        mock_response = '''```json
{
  "findings": [
    {"category": "identity", "item": "用户: 袁文涛", "status": "preserved", "detail": "保留"},
    {"category": "preferences", "item": "语言: 中文", "status": "lost", "detail": "未提及"}
  ],
  "recommendation": "部分丢失"
}
```'''
        pre_info = {"identity": ["用户: 袁文涛"], "preferences": ["语言: 中文"]}
        result = checker._parse_llm_response(mock_response, pre_info)
        assert len(result.findings) == 2
        assert result.findings[0].status == "preserved"
        assert result.findings[1].status == "lost"

    def test_compute_result_pass(self):
        checker = LLMChecker()
        findings = [
            Finding(category="identity", item="a", status="preserved"),
            Finding(category="identity", item="b", status="preserved"),
        ]
        result = checker._compute_result(findings)
        assert result.verdict == "pass"
        assert result.score == 1.0

    def test_compute_result_fail_on_identity_lost(self):
        checker = LLMChecker()
        findings = [
            Finding(category="identity", item="a", status="lost"),
            Finding(category="identity", item="b", status="lost"),
        ]
        result = checker._compute_result(findings)
        assert result.verdict == "fail"

    def test_compute_result_partial(self):
        checker = LLMChecker()
        findings = [
            Finding(category="identity", item="a", status="preserved"),
            Finding(category="identity", item="b", status="preserved"),
            Finding(category="preferences", item="c", status="degraded"),
            Finding(category="preferences", item="d", status="lost"),
        ]
        result = checker._compute_result(findings)
        assert result.verdict == "partial"


# ═════════════════════════════════════════════════════
# 5. Report 测试
# ═════════════════════════════════════════════════════


class TestReport:
    """报告写入测试。"""

    def test_write_report(self, tmp_path, mocker):
        mocker.patch("mark42_modules.audit.report.AUDIT_DIR", tmp_path / "audit")

        result = AuditResult(
            verdict="pass",
            score=0.95,
            findings=[Finding(category="identity", item="test", status="preserved")],
            recommendation="OK",
        )

        path = write_report(result, {"path": "/snap"}, {"path": "/sum"})
        assert Path(path).exists()

        data = json.loads(Path(path).read_text())
        assert data["verdict"] == "pass"
        assert data["score"] == 0.95
        assert len(data["findings"]) == 1

    def test_send_alert_pass_noop(self, mocker):
        """pass verdict 不发告警。"""
        mock_broker = mocker.patch("mark42_modules.audit.report._append_broker")
        result = AuditResult(verdict="pass", score=1.0)
        send_alert(result, "/path/to/report")
        mock_broker.assert_not_called()

    def test_send_alert_fail(self, mocker):
        mock_broker = mocker.patch("mark42_modules.audit.report._append_broker")
        result = AuditResult(
            verdict="fail",
            score=0.2,
            findings=[Finding(category="identity", item="x", status="lost")],
            recommendation="恢复",
        )
        send_alert(result, "/path/to/report")
        mock_broker.assert_called_once()
        call_args = mock_broker.call_args
        # (source, event_type, label, level, ...)
        assert call_args[0][0] == "armor"  # source
        assert call_args[0][1] == "mark42.armor.audit.fail"  # event_type
        assert call_args[0][3] == "error"  # level

    def test_cleanup_old_reports(self, tmp_path, mocker):
        mocker.patch("mark42_modules.audit.report.AUDIT_DIR", tmp_path / "audit")
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        # 创建 25 份报告
        for i in range(25):
            (audit_dir / f"audit-20260729-{i:04d}.json").write_text("{}")

        from mark42_modules.audit.report import _cleanup_old_reports
        _cleanup_old_reports(keep=20)

        remaining = list(audit_dir.glob("audit-*.json"))
        assert len(remaining) == 20


# ═════════════════════════════════════════════════════
# 6. BuiltinAudit 集成测试
# ═════════════════════════════════════════════════════


class TestBuiltinAudit:
    """BuiltinAudit 集成测试。"""

    def test_audit_compact_no_snapshot(self, mocker):
        """快照不存在时返回 skip。"""
        from mark42_modules.plugins.builtin_audit import BuiltinAudit

        audit = BuiltinAudit()
        mocker.patch.object(
            audit._snapshot_reader, "find_latest_before", return_value=None
        )

        result = audit.audit_compact(
            pre_compact_snapshot={"timestamp": "2026-07-29T10:00:00"},
            post_compact_summary={"timestamp": "2026-07-29T10:01:00"},
        )
        assert result["verdict"] == "skip"

    def test_audit_compact_no_summary(self, mocker, tmp_path):
        """摘要不存在时返回 skip。"""
        from mark42_modules.plugins.builtin_audit import BuiltinAudit

        audit = BuiltinAudit()
        mocker.patch.object(
            audit._snapshot_reader, "find_latest_before",
            return_value={"path": str(tmp_path), "timestamp": ""},
        )
        mocker.patch.object(
            audit._snapshot_reader, "extract_key_info",
            return_value={"identity": [], "preferences": [], "projects": [],
                          "decisions": [], "recent_topics": []},
        )
        mocker.patch.object(
            audit._summary_extractor, "find_post_compact_summary",
            return_value=None,
        )

        result = audit.audit_compact(
            pre_compact_snapshot={"timestamp": ""},
            post_compact_summary={"timestamp": ""},
        )
        assert result["verdict"] == "skip"

    def test_audit_compact_success(self, mocker, tmp_path):
        """完整审计流程。"""
        from mark42_modules.plugins.builtin_audit import BuiltinAudit
        from mark42_modules.audit.snapshot_reader import OpenClawSnapshotReader
        from mark42_modules.audit.summary_extractor import OpenClawSummaryExtractor
        from mark42_modules.audit.checker import LLMChecker

        audit = BuiltinAudit()
        mocker.patch("mark42_modules.audit.report.AUDIT_DIR", tmp_path / "audit")

        # Patch 类方法（避免 conftest reload 导致实例 mock 失效）
        mocker.patch.object(
            OpenClawSnapshotReader, "find_latest_before",
            return_value={"path": str(tmp_path), "timestamp": "2026-07-29T10:00:00"},
        )
        mocker.patch.object(
            OpenClawSnapshotReader, "extract_key_info",
            return_value={
                "identity": ["袁文涛"],
                "preferences": ["中文"],
                "projects": [],
                "decisions": [],
                "recent_topics": [],
            },
        )
        mocker.patch.object(
            OpenClawSummaryExtractor, "find_post_compact_summary",
            return_value={"path": str(tmp_path / "session.jsonl"), "timestamp": ""},
        )
        mocker.patch.object(
            OpenClawSummaryExtractor, "extract_summary_text",
            return_value="袁文涛使用中文对话",
        )
        mocker.patch.object(LLMChecker, "_get_llm", return_value=None)

        result = audit.audit_compact(
            pre_compact_snapshot={"timestamp": ""},
            post_compact_summary={"timestamp": ""},
        )
        assert result["verdict"] == "pass"
        assert result["score"] == 1.0
        assert "reportPath" in result

    def test_audit_compact_async_returns_queued(self, mocker):
        from mark42_modules.plugins.builtin_audit import BuiltinAudit

        audit = BuiltinAudit()
        mocker.patch.object(audit, "audit_compact", return_value={"verdict": "pass"})

        result = audit.audit_compact_async(
            pre_compact_snapshot={"timestamp": ""},
            post_compact_summary={"timestamp": ""},
        )
        assert result["queued"] is True
        assert "taskId" in result

    def test_audit_compact_exception_safe(self, mocker):
        """审计异常不影响主流程。"""
        from mark42_modules.plugins.builtin_audit import BuiltinAudit

        audit = BuiltinAudit()
        mocker.patch.object(
            audit._snapshot_reader, "find_latest_before",
            side_effect=Exception("boom"),
        )

        result = audit.audit_compact(
            pre_compact_snapshot={"timestamp": ""},
            post_compact_summary={"timestamp": ""},
        )
        assert result["verdict"] == "error"
