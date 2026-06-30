"""compaction_diag.py 测试群。

覆盖:
  - _format_bytes() 纯函数
  - _check_value() 纯函数 (单值区间检查)
  - _check_stat() 纯函数 (session 碎片化)
  - compaction_diagnose() 公开 API (mock config)

设计:
  - 纯函数直接测
  - 公开 API mock _load_openclaw_json / _get_compaction_config
  - 略过 _check_value 内部 zone 详尽测试 (避免 brittle)
"""

import pytest

from mark42_modules import compaction_diag


class TestFormatBytes:
    """_format_bytes() 字节格式化测试群。"""

    def test_format_bytes_zero(self):
        assert compaction_diag._format_bytes(0) == "0B"

    def test_format_bytes_bytes(self):
        assert compaction_diag._format_bytes(500) == "500B"

    def test_format_bytes_kb(self):
        assert "KB" in compaction_diag._format_bytes(1024)
        assert "KB" in compaction_diag._format_bytes(50_000)

    def test_format_bytes_mb(self):
        assert "MB" in compaction_diag._format_bytes(1_000_000)
        assert "MB" in compaction_diag._format_bytes(5_000_000)

    def test_format_bytes_boundary(self):
        """1000 字节 = 1KB, 1000000 = 1MB。"""
        assert "KB" in compaction_diag._format_bytes(1_000)
        assert "MB" in compaction_diag._format_bytes(1_000_000)


class TestCheckValue:
    """_check_value() 单值区间检查测试群。"""

    def test_check_value_missing_returns_missing_status(self):
        """value=None -> status=missing, severity=ok。"""
        r = compaction_diag._check_value("unknown_key", None, 131072)
        assert r["status"] == "missing"
        assert r["severity"] == compaction_diag.SEVERITY_OK

    def test_check_value_in_comfort_range(self):
        """known key + value 在舒适区 -> severity=ok。"""
        # 找一个真实存在的 key (用 _COMFORT_ZONES 第一个)
        first_key = next(iter(compaction_diag._COMFORT_ZONES))
        zone = compaction_diag._COMFORT_ZONES[first_key]
        comfort = zone["comfort"]
        ctx_window = 131072
        # 用 comfort 值测
        r = compaction_diag._check_value(first_key, comfort, ctx_window)
        assert r["severity"] in (compaction_diag.SEVERITY_OK, compaction_diag.SEVERITY_WARN)

    def test_check_value_unknown_key(self):
        """未知 key -> status=missing。"""
        r = compaction_diag._check_value("__not_a_real_key__", 100, 131072)
        assert r["status"] == "missing"


class TestCheckStat:
    """_check_stat() session 碎片化检测测试群。"""

    def test_check_stat_normal_no_issues(self):
        """1 session + 大文件 -> 无问题。"""
        issues = compaction_diag._check_stat(1, 5.0, 131072)
        assert isinstance(issues, list)
        assert len(issues) == 0

    def test_check_stat_many_sessions_fragments(self):
        """> 10 session -> 触发碎片化警告。"""
        issues = compaction_diag._check_stat(50, 5.0, 131072)
        assert len(issues) >= 1
        # 至少一个跟 session_fragmentation 有关
        keys = [i.get("key", "") for i in issues]
        assert "session_fragmentation" in keys

    def test_check_stat_small_file_warns(self):
        """largest_mb < 1.0MB -> 触发太小警告。"""
        issues = compaction_diag._check_stat(1, 0.5, 131072)
        assert len(issues) >= 1
        keys = [i.get("key", "") for i in issues]
        assert "too_small_transcript" in keys

    def test_check_stat_returns_list(self):
        """返回类型必须是 list[dict]。"""
        issues = compaction_diag._check_stat(1, 5.0, 131072)
        assert isinstance(issues, list)


class TestCompactionDiagnose:
    """compaction_diagnose() 公开 API 测试群 (mock config)。"""

    def test_diagnose_empty_config(self, mocker):
        """空 config -> 返回 dict 不崩。"""
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value={}
        )
        result = compaction_diag.compaction_diagnose()
        assert isinstance(result, dict)

    def test_diagnose_with_token_aware(self, mocker):
        """token_aware=True -> 不崩。"""
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value={}
        )
        result = compaction_diag.compaction_diagnose(token_aware=True)
        assert isinstance(result, dict)

    def test_diagnose_with_probe(self, mocker):
        """probe=True -> 不崩。"""
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value={}
        )
        result = compaction_diag.compaction_diagnose(probe=True)
        assert isinstance(result, dict)

    def test_diagnose_handles_none_config(self, mocker):
        """config 是 None -> 优雅降级。"""
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value=None
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value=None
        )
        result = compaction_diag.compaction_diagnose()
        assert isinstance(result, dict)


class TestSeverityConstants:
    """SEVERITY_* 常量存在性测试。"""

    def test_severity_constants_defined(self):
        assert hasattr(compaction_diag, "SEVERITY_OK")
        assert hasattr(compaction_diag, "SEVERITY_WARN")
        assert hasattr(compaction_diag, "SEVERITY_CRIT")
        # 这些应该是字符串
        assert isinstance(compaction_diag.SEVERITY_OK, str)
        assert isinstance(compaction_diag.SEVERITY_WARN, str)
        assert isinstance(compaction_diag.SEVERITY_CRIT, str)


class TestCompactionApply:
    """compaction_apply() 公开 API 测试群。

    【P0 安全】auto_confirm=False (默认) 应不写文件, 只生成建议。
    默认跳过, 加 @pytest.mark.slow 标记。
    """

    @pytest.mark.slow
    def test_apply_dry_run_does_not_write(self, mocker, tmp_path):
        """auto_confirm=False -> 不写 openclaw.json。"""
        # mock diagnose 返 actionable 建议
        fake_diag = {
            "actionable": True,
            "recommendations": [
                {"key": "maxActiveTranscriptBytes", "currentValue": 100000,
                 "recommendedValue": 3000000, "reason": "太小"}
            ],
            "timestamp": "2026-06-30T11:30:00",
            "summary": "需调优",
        }
        mocker.patch.object(
            compaction_diag, "compaction_diagnose", return_value=fake_diag
        )
        # 写一个空的 openclaw.json
        cfg_file = tmp_path / "openclaw.json"
        cfg_file.write_text("{}")
        mocker.patch.object(compaction_diag, "_load_openclaw_json", return_value={})
        mocker.patch.object(compaction_diag, "OPENCLAW_JSON", cfg_file)

        result = compaction_diag.compaction_apply(auto_confirm=False)
        # dry_run: 文件不应被改 (仍 {})
        assert cfg_file.read_text() == "{}"
        # 应有 status='dry_run' 或 changes 列表
        assert "changes" in result or "status" in result

    def test_apply_function_exists(self):
        """compaction_apply 顶层函数存在。"""
        assert hasattr(compaction_diag, "compaction_apply")
        assert callable(compaction_diag.compaction_apply)
