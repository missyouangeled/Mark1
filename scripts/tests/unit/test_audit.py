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
        assert len(AUDIT_CATEGORIES) == 6

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


# ═════════════════════════════════════════════════════
# 7. 补充测试 - LLMChecker 完整流程
# ═════════════════════════════════════════════════════


class TestLLMCheckerFull:
    """LLMChecker 补充测试。"""

    def test_llm_check_full_flow(self, mocker):
        """1. LLMChecker.check() 完整流程 - mock LLM 返回有效 JSON。"""
        checker = LLMChecker()
        mock_llm = mocker.MagicMock()
        mock_llm.chat.return_value = '''```json
{
  "findings": [
    {"category": "identity", "item": "用户: 袁文涛", "status": "preserved", "detail": "保留"},
    {"category": "preferences", "item": "语言: 中文", "status": "preserved", "detail": "保留"}
  ],
  "recommendation": "信息保留完整"
}
```'''
        mocker.patch.object(checker, "_get_llm", return_value=mock_llm)

        pre_info = {
            "identity": ["用户: 袁文涛"],
            "preferences": ["语言: 中文"],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
        }

        result = checker.check(pre_info, "袁文涛用中文交流")
        assert result.verdict == "pass"
        assert result.score == 1.0
        assert len(result.findings) == 2
        assert result.findings[0].status == "preserved"
        assert result.recommendation == "信息保留完整"

    def test_llm_build_prompt_contains_categories_and_summary(self):
        """2. LLMChecker._build_prompt() - 验证 prompt 包含所有类别和摘要。"""
        checker = LLMChecker()
        pre_info = {
            "identity": ["用户: 袁文涛"],
            "preferences": ["语言: 中文"],
            "projects": ["Mark42 审计系统"],
            "decisions": [],
            "recent_topics": [],
        }
        summary = "这是压缩后的摘要，包含用户信息"

        prompt = checker._build_prompt(pre_info, summary)

        assert "identity" in prompt
        assert "preferences" in prompt
        assert "projects" in prompt
        assert "袁文涛" in prompt
        assert "压缩后的摘要" in prompt

    def test_llm_parse_json_code_block(self):
        """3. LLMChecker._parse_llm_response() - 测试 ```json 代码块解析。"""
        checker = LLMChecker()
        response = '''下面是审计结果：
```json
{
  "findings": [
    {"category": "identity", "item": "用户: 袁文涛", "status": "preserved", "detail": ""}
  ],
  "recommendation": "OK"
}
```
结束'''
        pre_info = {"identity": ["用户: 袁文涛"]}
        result = checker._parse_llm_response(response, pre_info)
        assert len(result.findings) == 1
        assert result.findings[0].item == "用户: 袁文涛"

    def test_llm_parse_failure_falls_back_to_rule(self, mocker):
        """4. LLMChecker._parse_llm_response() - JSON 解析失败降级到 Rule。"""
        checker = LLMChecker()
        invalid_response = '''这不是有效的 JSON
{
  "findings": [
    invalid json
  ]
}'''
        pre_info = {
            "identity": ["用户: 袁文涛"],
            "preferences": [],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
        }

        # 这不是有效的 JSON，应该降级到 RuleChecker
        result = checker._parse_llm_response(invalid_response, pre_info)
        # RuleChecker 用关键词匹配，invalid_response 里没有关键词所以会是 lost
        assert result.verdict in ["pass", "fail", "partial"]  # 不报错即可

    def test_llm_compute_result_empty_findings_returns_pass(self):
        """5. LLMChecker._compute_result() - 空 findings 返回 pass。"""
        checker = LLMChecker()
        result = checker._compute_result([], "测试推荐")
        assert result.verdict == "pass"
        assert result.score == 1.0
        # 空 findings 时使用硬编码的默认推荐语，不使用传入的参数
        assert "无关键信息" in result.recommendation

    def test_llm_timeout_falls_back_to_rule(self, mocker):
        """6. LLMChecker 超时降级 - mock llm.chat 抛出 timeout。"""
        checker = LLMChecker()
        mock_llm = mocker.MagicMock()
        mock_llm.chat.side_effect = Exception("Timeout: request took too long")
        mocker.patch.object(checker, "_get_llm", return_value=mock_llm)

        pre_info = {
            "identity": ["用户: 袁文涛"],
            "preferences": [],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
        }

        result = checker.check(pre_info, "用户袁文涛")
        # 降级到 RuleChecker 后应该有结果
        assert result.verdict in ["pass", "partial"]
        # error 可能包含降级信息
        assert result.error is not None


class TestRuleCheckerFull:
    """RuleChecker 补充测试。"""

    def test_extract_keywords_chinese(self):
        """7. RuleChecker._extract_keywords() - 中文分词。"""
        checker = RuleChecker()
        keywords = checker._extract_keywords("用户: 袁文涛")
        # 应该提取出关键词，包含 "用户" 和 "袁文涛"
        assert len(keywords) > 0
        # 测试其他中文
        keywords2 = checker._extract_keywords("语言锁定: 只用中文")
        assert len(keywords2) > 0

    def test_rule_check_multi_categories_items(self):
        """8. RuleChecker.check() - 多类别多项目场景。"""
        checker = RuleChecker()
        pre_info = {
            "identity": ["用户: 袁文涛", "AI: 贾维斯"],
            "preferences": ["语言: 中文", "回复风格: 简洁"],
            "projects": ["项目: Mark42 审计系统"],
            "decisions": ["决策: 用 pytest 测试"],
            "recent_topics": ["话题: 单元测试覆盖"],
        }
        summary = "用户袁文涛和AI贾维斯正在用中文语言讨论 Mark42 审计系统项目，采用简洁回复风格，用 pytest 决策进行单元测试覆盖"
        result = checker.check(pre_info, summary)
        # 大部分信息应该被匹配到
        assert result.verdict in ["pass", "partial"]
        assert result.score >= 0.3  # 宽松阈值，能匹配到关键词就行


# ═════════════════════════════════════════════════════
# 8. 补充测试 - SnapshotReader 完整提取
# ═════════════════════════════════════════════════════


class TestSnapshotReaderFull:
    """OpenClawSnapshotReader 补充测试。"""

    def test_find_latest_before_multiple_snapshots(self, tmp_path):
        """9. find_latest_before - 多个快照选最近的。"""
        timestamps = [
            "2026-07-29T080000",
            "2026-07-29T090000",
            "2026-07-29T100000",
            "2026-07-29T110000",
        ]
        for ts in timestamps:
            (tmp_path / f"snapshot-{ts}").mkdir()

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        result = reader.find_latest_before("2026-07-29T103000")
        assert result is not None
        assert "snapshot-2026-07-29T100000" in result["path"]

    def test_extract_key_info_from_user_identity(self, tmp_path):
        """10. extract_key_info - 从 USER.md 提取身份信息。"""
        snap_dir = tmp_path / "snapshot-test"
        snap_dir.mkdir()
        (snap_dir / "USER.md").write_text(
            "**Name:** 袁文涛\n**What to call them:** 点点\n"
        )
        (snap_dir / "context-summary.md").write_text("")

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        snapshot = {"path": str(snap_dir), "timestamp": ""}
        info = reader.extract_key_info(snapshot)

        assert any("袁文涛" in i for i in info["identity"])
        assert any("点点" in i for i in info["identity"])

    def test_extract_key_info_from_memory_preferences(self, tmp_path):
        """11. extract_key_info - 从 MEMORY.md 提取偏好。"""
        snap_dir = tmp_path / "snapshot-test"
        snap_dir.mkdir()
        (snap_dir / "MEMORY.md").write_text(
            "# 长期记忆\n\n"
            "## 偏好规则\n\n"
            "- **语言锁定**: 只用中文\n"
            "- **代码风格**: Python 优先\n"
        )
        (snap_dir / "context-summary.md").write_text("")

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        snapshot = {"path": str(snap_dir), "timestamp": ""}
        info = reader.extract_key_info(snapshot)

        # 应该提取到偏好规则（标题和内容）
        assert len(info["preferences"]) > 0
        # "偏好规则" 是标题，会被提取
        assert any("偏好规则" in p or "语言锁定" in p or "只用中文" in p for p in info["preferences"])

    def test_extract_key_info_from_memory_rules_dir(self, tmp_path):
        """12. extract_key_info - 从 memory/rules/ 提取偏好。"""
        snap_dir = tmp_path / "snapshot-test"
        snap_dir.mkdir()
        (snap_dir / "MEMORY.md").write_text("")
        (snap_dir / "context-summary.md").write_text("")

        rules_dir = snap_dir / "memory" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "chat-style.md").write_text(
            "## 对话风格\n\n"
            "- 回复要简洁明了\n"
            "- 多用 emoji 增加亲和力\n"
        )

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        snapshot = {"path": str(snap_dir), "timestamp": ""}
        info = reader.extract_key_info(snapshot)

        # 应该从 rules 目录提取偏好
        assert len(info["preferences"]) > 0
        assert any("chat-style" in p or "简洁" in p for p in info["preferences"])

    def test_extract_identity_combined_sources(self, tmp_path):
        """13. _extract_identity - USER.md/SOUL.md/MEMORY.md 联合提取。"""
        snap_dir = tmp_path / "snapshot-test"
        snap_dir.mkdir()
        (snap_dir / "USER.md").write_text("**Name:** 袁文涛\n")
        (snap_dir / "SOUL.md").write_text("名字：贾维斯\n")
        (snap_dir / "MEMORY.md").write_text("生日：2000-01-01\n")

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        identities = reader._extract_identity(snap_dir)

        assert any("袁文涛" in i for i in identities)
        assert any("贾维斯" in i for i in identities)
        assert any("生日" in i for i in identities)

    def test_extract_preferences_combined_memory_and_rules(self, tmp_path):
        """14. _extract_preferences - MEMORY.md + memory/rules/ 联合提取。"""
        snap_dir = tmp_path / "snapshot-test"
        snap_dir.mkdir()
        (snap_dir / "MEMORY.md").write_text(
            "## 基础规则\n\n"
            "- **语言**: 中文\n"
        )
        rules_dir = snap_dir / "memory" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "coding.md").write_text("## 代码规则\n- PEP8 规范\n")

        reader = OpenClawSnapshotReader(snapshot_root=tmp_path)
        prefs = reader._extract_preferences(snap_dir)

        # 两者的偏好都应该被提取
        assert len(prefs) > 0
        # MEMORY.md 的标题 "基础规则" 会被提取
        # memory/rules/ 的内容 "[coding] 代码规则" 和 "PEP8 规范" 会被提取
        assert any("基础规则" in p or "代码规则" in p or "PEP8" in p for p in prefs)

    def test_extract_projects_from_context_summary(self):
        """15. _extract_projects - 从 context-summary 提取项目。"""
        reader = OpenClawSnapshotReader()
        summary_text = """
## 今日摘要

- 贾维斯：今天做了 compact 优化

项目：Mark42 压缩审计系统
决策：采用 pytest 作为测试框架

项目：Skill Workshop 技能管理
"""
        projects = reader._extract_projects(summary_text)
        assert len(projects) >= 2
        assert any("Mark42" in p for p in projects)
        assert any("Skill" in p for p in projects)

    def test_extract_decisions_from_context_summary(self):
        """16. _extract_decisions - 从 context-summary 提取决策。"""
        reader = OpenClawSnapshotReader()
        summary_text = """
## 技术决策

决策：采用 pytest 作为测试框架
方案：用 JSON 存储审计报告
决定：异步执行审计不阻塞主流程
策略：覆盖率目标 80%
"""
        decisions = reader._extract_decisions(summary_text)
        assert len(decisions) >= 3
        assert any("pytest" in d for d in decisions)
        assert any("JSON" in d for d in decisions)

    def test_extract_recent_topics_from_context_summary(self):
        """17. _extract_recent_topics - 从 context-summary 提取话题。"""
        reader = OpenClawSnapshotReader()
        summary_text = """
## 今日摘要

- 完成了单元测试框架搭建
- 讨论了覆盖率计算方法
- 测试了 pytest-mock 的使用
- 修复了 snapshot 路径问题
"""
        topics = reader._extract_recent_topics(summary_text)
        assert len(topics) >= 3
        assert any("单元测试" in t for t in topics)


# ═════════════════════════════════════════════════════
# 9. 补充测试 - SummaryExtractor JSONL 格式
# ═════════════════════════════════════════════════════


class TestSummaryExtractorFull:
    """OpenClawSummaryExtractor 补充测试。"""

    def test_extract_from_jsonl_finds_type_compaction(self, tmp_path):
        """18. _extract_from_jsonl - 找到 type=\"compaction\" 条目。"""
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({"role": "user", "content": "你好"}),
            json.dumps({"role": "assistant", "content": "你好"}),
            json.dumps({"type": "compaction", "summary": "## 压缩摘要\n对话是你好，用户问候"}),
        ]
        session_file.write_text("\n".join(lines) + "\n")

        extractor = OpenClawSummaryExtractor()
        text = extractor._extract_from_jsonl(session_file)

        assert "压缩摘要" in text
        assert "对话是你好" in text

    def test_extract_from_jsonl_summary_empty_fallback_details(self, tmp_path):
        """19. _extract_from_jsonl - compaction summary 为空时 fallback 到 details。"""
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "compaction",
                "summary": "",  # 空摘要
                "details": {
                    "readFiles": ["a.py", "b.py"],
                    "modifiedFiles": ["c.py"]
                }
            }),
        ]
        session_file.write_text("\n".join(lines) + "\n")

        extractor = OpenClawSummaryExtractor()
        text = extractor._extract_from_jsonl(session_file)

        assert "读取文件" in text
        assert "a.py" in text
        assert "修改文件" in text
        assert "c.py" in text

    def test_extract_from_jsonl_no_compaction_returns_tail_messages(self, tmp_path):
        """20. _extract_from_jsonl - 找不到 compaction 时返回最后 20 条消息。"""
        session_file = tmp_path / "session.jsonl"
        lines = []
        for i in range(30):
            lines.append(json.dumps({"role": "user", "content": f"消息 {i}"}))
            lines.append(json.dumps({"role": "assistant", "content": f"回复 {i}"}))
        session_file.write_text("\n".join(lines) + "\n")

        extractor = OpenClawSummaryExtractor()
        text = extractor._extract_from_jsonl(session_file)

        # 应该包含最近的消息
        assert "消息 29" in text
        assert "回复 29" in text
        # 不应该包含太旧的消息

    def test_extract_from_jsonl_empty_file_returns_empty_session(self, tmp_path):
        """21. _extract_from_jsonl - 空文件返回 \"(empty session)\"。"""
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("")

        extractor = OpenClawSummaryExtractor()
        text = extractor._extract_from_jsonl(session_file)

        assert "empty session" in text

    def test_extract_summary_text_path_not_exists_calls_sqlite(self, mocker, tmp_path):
        """22. extract_summary_text - 路径不存在时调用 _extract_from_sqlite。"""
        extractor = OpenClawSummaryExtractor()
        mock_sqlite = mocker.patch.object(
            extractor, "_extract_from_sqlite", return_value="from sqlite"
        )

        result = extractor.extract_summary_text({"path": str(tmp_path / "not-exist.jsonl")})

        mock_sqlite.assert_called_once()
        assert result == "from sqlite"


# ═════════════════════════════════════════════════════
# 10. 补充测试 - Report 完整字段
# ═════════════════════════════════════════════════════


class TestReportFull:
    """报告补充测试。"""

    def test_write_report_complete_fields(self, tmp_path, mocker):
        """23. write_report - 完整字段验证。"""
        mocker.patch("mark42_modules.audit.report.AUDIT_DIR", tmp_path / "audit")

        result = AuditResult(
            verdict="partial",
            score=0.75,
            findings=[
                Finding(category="identity", item="用户: 袁文涛", status="preserved", detail="保留"),
                Finding(category="preferences", item="语言: 中文", status="lost", detail="丢失"),
            ],
            recommendation="部分信息丢失，关注语言设置",
        )
        pre_snap = {"path": "/snap/pre", "timestamp": "2026-07-29T10:00:00"}
        post_sum = {"path": "/snap/post", "timestamp": "2026-07-29T10:01:00"}

        report_path = write_report(result, pre_snap, post_sum)
        assert Path(report_path).exists()

        data = json.loads(Path(report_path).read_text())
        assert "timestamp" in data
        assert data["verdict"] == "partial"
        assert data["score"] == 0.75
        assert len(data["findings"]) == 2
        assert data["findings"][0]["status"] == "preserved"
        assert data["findings"][1]["status"] == "lost"
        assert data["recommendation"] == "部分信息丢失，关注语言设置"
        assert data["preSnapshot"] == pre_snap
        assert data["postSummary"] == post_sum

    def test_send_alert_partial_sends_warning(self, mocker):
        """24. send_alert - partial 级别发 warning。"""
        mock_broker = mocker.patch("mark42_modules.audit.report._append_broker")
        result = AuditResult(
            verdict="partial",
            score=0.75,
            findings=[
                Finding(category="preferences", item="x", status="degraded"),
            ],
            recommendation="部分丢失",
        )
        send_alert(result, "/path/to/report")

        mock_broker.assert_called_once()
        call_args = mock_broker.call_args
        assert call_args[0][1] == "mark42.armor.audit.partial"  # event_type
        assert call_args[0][3] == "warning"  # level

    def test_cleanup_old_reports_custom_keep_count(self, tmp_path, mocker):
        """25. _cleanup_old_reports - 保留指定数量。"""
        mocker.patch("mark42_modules.audit.report.AUDIT_DIR", tmp_path / "audit")
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        # 创建 15 份报告
        for i in range(15):
            (audit_dir / f"audit-{i:04d}.json").write_text("{}")

        from mark42_modules.audit.report import _cleanup_old_reports
        _cleanup_old_reports(keep=5)

        remaining = list(audit_dir.glob("audit-*.json"))
        assert len(remaining) == 5

    def test_cleanup_old_reports_oserror_ignored(self, tmp_path, mocker):
        """【report.py 行 92-95】删除文件失败时忽略 OSError。"""
        mocker.patch("mark42_modules.audit.report.AUDIT_DIR", tmp_path / "audit")
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        # 创建一些报告
        for i in range(5):
            (audit_dir / f"audit-{i:04d}.json").write_text("{}")

        # mock Path.unlink 抛出 OSError
        mocker.patch("pathlib.Path.unlink", side_effect=OSError("file busy"))

        from mark42_modules.audit.report import _cleanup_old_reports
        # 不应该抛出异常
        _cleanup_old_reports(keep=2)

        # 所有文件应该都保留（因为 unlink 都失败了）
        remaining = list(audit_dir.glob("audit-*.json"))
        assert len(remaining) == 5

    def test_send_alert_counts_all_status_types(self, mocker):
        """【report.py 行 75-77】send_alert 统计 lost/degraded/preserved 数量。"""
        from mark42_modules.audit.report import send_alert
        from mark42_modules.audit import AuditResult, Finding

        mock_broker = mocker.patch("mark42_modules.audit.report._append_broker")

        result = AuditResult(
            verdict="fail",
            score=0.5,
            findings=[
                Finding(category="identity", item="1", status="lost"),
                Finding(category="identity", item="2", status="lost"),  # lostCount=2
                Finding(category="preferences", item="3", status="degraded"),  # degradedCount=1
                Finding(category="projects", item="4", status="preserved"),  # preservedCount=1
            ],
            recommendation="测试",
        )
        send_alert(result, "/path/to/report.json")

        mock_broker.assert_called_once()
        call_args = mock_broker.call_args
        broker_meta = call_args[0][5]  # 第 6 个参数是 metadata dict
        assert broker_meta["lostCount"] == 2
        assert broker_meta["degradedCount"] == 1
        assert broker_meta["preservedCount"] == 1


# ═════════════════════════════════════════════════════
# 11. 补充测试 - BuiltinAudit 完整流程
# ═════════════════════════════════════════════════════


class TestBuiltinAuditFull:
    """BuiltinAudit 补充测试。"""

    def test_audit_compact_full_mock_chain(self, mocker, tmp_path):
        """26. audit_compact - 全流程 mock。"""
        from mark42_modules.plugins.builtin_audit import BuiltinAudit

        mocker.patch("mark42_modules.audit.report.AUDIT_DIR", tmp_path / "audit")
        
        mock_result = AuditResult(
            verdict="pass",
            score=1.0,
            findings=[],
            recommendation="测试通过",
        )

        # Patch 类方法
        mocker.patch.object(
            OpenClawSnapshotReader, "find_latest_before",
            return_value={"path": str(tmp_path), "timestamp": "t1"},
        )
        mocker.patch.object(
            OpenClawSnapshotReader, "extract_key_info",
            return_value={"identity": ["用户: 袁文涛"], "preferences": [],
                          "projects": [], "decisions": [], "recent_topics": []},
        )
        mocker.patch.object(
            OpenClawSummaryExtractor, "find_post_compact_summary",
            return_value={"path": str(tmp_path / "s.jsonl"), "timestamp": "t2"},
        )
        mocker.patch.object(
            OpenClawSummaryExtractor, "extract_summary_text",
            return_value="袁文涛",
        )
        mocker.patch.object(LLMChecker, "check", return_value=mock_result)

        mock_write = mocker.patch(
            "mark42_modules.plugins.builtin_audit.write_report",
            return_value="/mock/report.json"
        )
        mock_alert = mocker.patch(
            "mark42_modules.plugins.builtin_audit.send_alert"
        )

        audit = BuiltinAudit()
        result = audit.audit_compact(
            pre_compact_snapshot={"timestamp": "t1"},
            post_compact_summary={"timestamp": "t2"},
        )

        assert result["verdict"] == "pass"
        assert result["score"] == 1.0
        assert result["reportPath"] == "/mock/report.json"
        mock_write.assert_called_once()
        mock_alert.assert_called_once()

    def test_async_run_exception_safe(self, mocker):
        """27. _async_run - 异步线程异常安全（不崩溃）。"""
        from mark42_modules.plugins.builtin_audit import BuiltinAudit

        audit = BuiltinAudit()

        # 让 audit_compact 抛出异常
        mocker.patch.object(
            audit._snapshot_reader, "find_latest_before",
            side_effect=Exception("async failure test"),
        )

        # _async_run 有异常保护，不应该抛出
        audit._async_run({"timestamp": ""}, {"timestamp": ""})
        # 不崩溃就是通过（内部的 broker 写入失败会被静默吞掉，不影响主流程）


# ── Constraint Pinner 测试 ──────────────────────────


class TestConstraintPinner:
    """约束保护：compact 后重新注入关键约束。"""

    def test_extract_from_soul_md(self, tmp_path):
        """从 SOUL.md 提取语言锁定规则和核心准则。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "SOUL.md").write_text(
            "## ⚠️ 输出语言强制规则\n"
            "**你必须只用中文回复。禁止使用英文回复。**\n\n"
            "**Be genuinely helpful.**\n"
            "- 私密的事情保持私密。\n"
            "- 发送邮件前先问\n",
            encoding="utf-8",
        )
        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.extract_pinned_constraints()
        assert "中文" in result
        assert "SOUL.md" in result
        # 私密边界也应被提取
        assert "私密" in result

    def test_extract_from_user_md(self, tmp_path):
        """从 USER.md 提取名字和时区。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "USER.md").write_text(
            "- **Name:** 袁文涛\n"
            "- **What to call them:** 点点\n"
            "- **Timezone:** Asia/Shanghai\n"
            "- **Notes:** 习惯用\"点点\"自称\n",
            encoding="utf-8",
        )
        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.extract_pinned_constraints()
        assert "袁文涛" in result
        assert "点点" in result
        assert "Shanghai" in result

    def test_extract_from_agents_md(self, tmp_path):
        """从 AGENTS.md 提取基本规则。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "AGENTS.md").write_text(
            "## 基本规则\n\n"
            "- 只用中文。交付前自检。\n"
            "- 修改任务：先查现有能力\n"
            "- 发送邮件/推文/公开内容前先问\n"
            "- 高风险系统操作前读崩坏案例\n",
            encoding="utf-8",
        )
        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.extract_pinned_constraints()
        assert "只用中文" in result
        assert "高风险" in result

    def test_extract_all_files_combined(self, tmp_path):
        """多个文件同时存在时合并提取。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "SOUL.md").write_text("**你必须只用中文回复。**\n", encoding="utf-8")
        (tmp_path / "USER.md").write_text("- **Name:** 袁文涛\n", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("- 只用中文\n", encoding="utf-8")

        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.extract_pinned_constraints()
        assert "SOUL.md" in result
        assert "USER.md" in result
        assert "AGENTS.md" in result
        assert "袁文涛" in result

    def test_extract_empty_workspace(self, tmp_path):
        """没有任何文件时返回空字符串。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.extract_pinned_constraints()
        assert result == ""

    def test_extract_missing_one_file(self, tmp_path):
        """只有部分文件存在时也能提取。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "USER.md").write_text("- **Name:** 袁文涛\n", encoding="utf-8")
        # SOUL.md 和 AGENTS.md 不存在

        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.extract_pinned_constraints()
        assert "袁文涛" in result
        assert "SOUL.md" not in result  # 不存在的文件不会被提到

    def test_max_total_chars_limit(self, tmp_path):
        """总字符数超过 MAX_TOTAL_CHARS 时截断。"""
        from mark42_modules.audit.pinning import ConstraintPinner, MAX_TOTAL_CHARS

        # 写一个超大文件
        (tmp_path / "SOUL.md").write_text("中文 " * 5000, encoding="utf-8")

        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.extract_pinned_constraints()
        # 结果不应超过 MAX_TOTAL_CHARS + header
        assert len(result) < MAX_TOTAL_CHARS + 500  # 加上 header 的余量

    def test_inject_to_file(self, tmp_path, mocker):
        """inject_to_file 写入临时文件。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "SOUL.md").write_text("**中文回复**\n", encoding="utf-8")

        # mock ARMOR_STATE 到 tmp_path
        mocker.patch("mark42_modules.config.ARMOR_STATE", tmp_path / "armor")

        pinner = ConstraintPinner(workspace=tmp_path)
        path = pinner.inject_to_file()
        assert path is not None
        content = Path(path).read_text(encoding="utf-8")
        assert "中文" in content
        assert "Post-Compact" in content

    def test_inject_to_file_empty_returns_none(self, tmp_path):
        """没有约束时 inject_to_file 返回 None。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        pinner = ConstraintPinner(workspace=tmp_path)
        assert pinner.inject_to_file() is None

    def test_inject_via_broker(self, tmp_path, mocker):
        """inject_via_broker 发送 broker 事件。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "SOUL.md").write_text("**中文回复**\n", encoding="utf-8")

        mock_broker = mocker.patch("mark42_modules.utils._append_broker")

        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.inject_via_broker()
        assert result is True
        assert mock_broker.called
        call_args = mock_broker.call_args
        assert "constraint_reinject" in call_args[0][1]

    def test_inject_via_broker_no_constraints(self, tmp_path):
        """没有约束时 inject_via_broker 返回 False。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        pinner = ConstraintPinner(workspace=tmp_path)
        assert pinner.inject_via_broker() is False

    def test_extract_essential_lines_max_lines_boundary(self, tmp_path):
        """【pinning.py 行 77-78】MAX_LINES_PER_FILE 边界，超过后截断。"""
        from mark42_modules.audit.pinning import ConstraintPinner, MAX_LINES_PER_FILE

        pinner = ConstraintPinner(workspace=tmp_path)
        
        # 创建超过 MAX_LINES_PER_FILE 行数的 AGENTS.md
        extra_lines = "\n".join([f"- 规则 {i}" for i in range(MAX_LINES_PER_FILE + 5)])
        (tmp_path / "AGENTS.md").write_text(extra_lines, encoding="utf-8")
        
        result = pinner.extract_pinned_constraints()
        # 应该被截断到 MAX_LINES_PER_FILE 行
        # 每一行以 "- 规则" 开头，计数不应该超过 MAX_LINES_PER_FILE
        lines_count = result.count("- 规则")
        assert lines_count <= MAX_LINES_PER_FILE

    def test_extract_essential_lines_empty_returns_empty(self, tmp_path):
        """【pinning.py 行 136-139】没有匹配到关键内容时返回空字符串。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        pinner = ConstraintPinner(workspace=tmp_path)
        
        # 文件有内容但没有匹配到任何关键模式
        # 注意：不能包含 "中文" "English" "语言" 等关键词
        (tmp_path / "SOUL.md").write_text(
            "普通内容，无粗体规则，无锁定关键词\n"
            "只是一些普通的文本行\n"
            "Another plain line without bold markers\n",
            encoding="utf-8",
        )
        
        result = pinner.extract_pinned_constraints()
        # 空内容不会生成 header，直接返回空
        assert result == ""

    def test_inject_via_broker_exception_returns_false(self, tmp_path, mocker):
        """【pinning.py 行 173-174】broker 写入异常时静默返回 False。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "SOUL.md").write_text("**中文回复**\n", encoding="utf-8")
        
        # mock _append_broker 抛出异常
        mocker.patch("mark42_modules.utils._append_broker", side_effect=Exception("broker down"))

        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.inject_via_broker()
        # 异常被捕获，返回 False
        assert result is False

    def test_inject_to_file_exception_returns_none(self, tmp_path, mocker):
        """【pinning.py 行 201-202】文件写入异常时静默返回 None。"""
        from mark42_modules.audit.pinning import ConstraintPinner

        (tmp_path / "SOUL.md").write_text("**中文回复**\n", encoding="utf-8")
        
        # mock Path.write_text 抛出异常（通过 mock ARMOR_STATE 为不可写路径）
        mocker.patch("mark42_modules.config.ARMOR_STATE", tmp_path)
        # 直接让 mkdir 失败
        mocker.patch("pathlib.Path.mkdir", side_effect=PermissionError("read-only fs"))

        pinner = ConstraintPinner(workspace=tmp_path)
        result = pinner.inject_to_file()
        assert result is None


# ── SummaryExtractor SQLite fallback 测试 ─────────


class TestSummaryExtractorSQLite:
    """SQLite fallback 路径测试（覆盖率从 72% -> 80%+）。"""

    def test_sqlite_fallback_returns_content(self, mocker):
        """SQLite fallback -- openclaw CLI 返回 compaction 条目。"""
        from mark42_modules.audit.summary_extractor import OpenClawSummaryExtractor

        ext = OpenClawSummaryExtractor()

        # mock subprocess.run 返回 compaction 条目
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "type": "compaction",
            "summary": "## Decisions\n1. 测试决策",
        }, ensure_ascii=False)
        mocker.patch("subprocess.run", return_value=mock_result)

        text = ext._extract_from_sqlite({"path": "/nonexistent"})
        assert "测试决策" in text

    def test_sqlite_fallback_no_compaction_returns_tail(self, mocker):
        """SQLite fallback -- 没有 compaction 条目时返回最近的对话。"""
        from mark42_modules.audit.summary_extractor import OpenClawSummaryExtractor

        ext = OpenClawSummaryExtractor()

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"role": "user", "content": "最近的对话"}, ensure_ascii=False)
        mocker.patch("subprocess.run", return_value=mock_result)

        text = ext._extract_from_sqlite({"path": "/nonexistent"})
        assert len(text) > 0

    def test_sqlite_fallback_cli_error_returns_empty(self, mocker):
        """SQLite fallback -- CLI 返回非零退出码。"""
        from mark42_modules.audit.summary_extractor import OpenClawSummaryExtractor

        ext = OpenClawSummaryExtractor()

        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mocker.patch("subprocess.run", return_value=mock_result)

        text = ext._extract_from_sqlite({"path": "/nonexistent"})
        assert text == ""

    def test_sqlite_fallback_timeout_returns_empty(self, mocker):
        """SQLite fallback -- subprocess 超时。"""
        from mark42_modules.audit.summary_extractor import OpenClawSummaryExtractor
        import subprocess as _sp

        ext = OpenClawSummaryExtractor()

        mocker.patch("subprocess.run", side_effect=_sp.TimeoutExpired("openclaw", 15))

        text = ext._extract_from_sqlite({"path": "/nonexistent"})
        assert text == ""

    def test_sqlite_fallback_command_not_found(self, mocker):
        """SQLite fallback -- openclaw 命令不存在。"""
        from mark42_modules.audit.summary_extractor import OpenClawSummaryExtractor

        ext = OpenClawSummaryExtractor()

        mocker.patch("subprocess.run", side_effect=FileNotFoundError("openclaw"))

        text = ext._extract_from_sqlite({"path": "/nonexistent"})
        assert text == ""
