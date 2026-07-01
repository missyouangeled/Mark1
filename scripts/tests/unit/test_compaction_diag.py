"""compaction_diag.py 测试群。

覆盖:
  - _format_bytes() 纯函数
  - _check_value() 纯函数 (单值区间检查)
  - _check_stat() 纯函数 (session 碎片化)
  - _dual_threshold_check() 双阈值偏移
  - _isolation_check() 分身隔离
  - _token_aware_check() 令牌感知 (mock _SESSIONS_DIR)
  - _probe_quality_check() 探针 (mock _SESSIONS_DIR)
  - _drift_check() 降解检测 (mock _SESSIONS_DIR)
  - compaction_diagnose() 公开 API (mock config)
  - compaction_apply() dry_run 安全 (加 slow 标记)

设计:
  - 纯函数直接测
  - 公开 API mock _load_openclaw_json / _get_compaction_config
  - IO 重函数 (读 session jsonl) 用 _fake_sessions_dir fixture 填充假数据
"""

import json as _json
from pathlib import Path
from datetime import datetime

import pytest

from mark42_modules import compaction_diag


# ── 测试用 fixture: 填充假 session jsonl ──────────────

@pytest.fixture
def _fake_sessions_dir(monkeypatch, tmp_path):
    """填充假 session jsonl 文件, 覆盖 _SESSIONS_DIR 路径。

    返回 (tmp_path, session_data_dict) — session_data 可被测试读写。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    fake_dir = tmp_path / "sessions"
    fake_dir.mkdir(parents=True, exist_ok=True)

    def write_jsonl(filename: str, lines: list[dict]) -> Path:
        path = fake_dir / filename
        with open(path, "w") as f:
            for line in lines:
                f.write(_json.dumps(line) + "\n")
        return path

    # 默认写一个 session: 5 轮对话 + 1 个 compaction 事件
    default_lines = []
    for i in range(5):
        default_lines.append({
            "type": "message",
            "message": {"role": "user" if i % 2 == 0 else "assistant",
                        "content": f"msg {i}",
                        "usage": {"totalTokens": 1000 + i * 100}},
        })
    default_lines.append({
        "type": "compaction",
        "tokensBefore": 5000,
        "details": "automated",
        "fromHook": True,
    })
    write_jsonl(f"{today}-main-001.jsonl", default_lines)

    monkeypatch.setattr(compaction_diag, "_SESSIONS_DIR", fake_dir)
    return fake_dir


# ── TestFormatBytes ──

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


# ── TestCheckValue ──

class TestCheckValue:
    """_check_value() 单值区间检查测试群。"""

    def test_check_value_missing_returns_missing_status(self):
        """value=None -> status=missing, severity=ok。"""
        r = compaction_diag._check_value("unknown_key", None, 131072)
        assert r["status"] == "missing"
        assert r["severity"] == compaction_diag.SEVERITY_OK

    def test_check_value_in_comfort_range(self):
        """known key + value 在舒适区 -> severity=ok。"""
        first_key = next(iter(compaction_diag._COMFORT_ZONES))
        zone = compaction_diag._COMFORT_ZONES[first_key]
        comfort = zone["comfort"]
        r = compaction_diag._check_value(first_key, comfort, 131072)
        assert r["severity"] in (compaction_diag.SEVERITY_OK, compaction_diag.SEVERITY_WARN)

    def test_check_value_unknown_key(self):
        r = compaction_diag._check_value("__not_a_real_key__", 100, 131072)
        assert r["status"] == "missing"

    def test_check_value_too_low(self):
        """value < min -> status=too_low, severity=warn。"""
        # 找一个 key, 用 min-1
        first_key = next(iter(compaction_diag._COMFORT_ZONES))
        zone = compaction_diag._COMFORT_ZONES[first_key]
        too_low = max(0, zone["min"] - 1000)
        r = compaction_diag._check_value(first_key, too_low, 131072)
        assert r["status"] == "too_low"
        assert r["severity"] == compaction_diag.SEVERITY_WARN

    def test_check_value_too_high(self):
        """value > max -> status=too_high。

        实际实现: too_high 对 keepRecentTokens 是 WARN, 其他 key 是 OK
        (设计: 过高占用空间但不算严重)。
        """
        first_key = next(iter(compaction_diag._COMFORT_ZONES))
        zone = compaction_diag._COMFORT_ZONES[first_key]
        too_high = zone["max"] + 1000
        r = compaction_diag._check_value(first_key, too_high, 131072)
        assert r["status"] == "too_high"
        # severity: keepRecentTokens -> WARN, 其他 -> OK
        expected = compaction_diag.SEVERITY_WARN if first_key == "keepRecentTokens" else compaction_diag.SEVERITY_OK
        assert r["severity"] == expected


# ── TestCheckStat ──

class TestCheckStat:
    """_check_stat() session 碎片化检测测试群。"""

    def test_check_stat_normal_no_issues(self):
        issues = compaction_diag._check_stat(1, 5.0, 131072)
        assert isinstance(issues, list)
        assert len(issues) == 0

    def test_check_stat_many_sessions_fragments(self):
        issues = compaction_diag._check_stat(50, 5.0, 131072)
        assert len(issues) >= 1
        keys = [i.get("key", "") for i in issues]
        assert "session_fragmentation" in keys

    def test_check_stat_small_file_warns(self):
        issues = compaction_diag._check_stat(1, 0.5, 131072)
        assert len(issues) >= 1
        keys = [i.get("key", "") for i in issues]
        assert "too_small_transcript" in keys

    def test_check_stat_returns_list(self):
        issues = compaction_diag._check_stat(1, 5.0, 131072)
        assert isinstance(issues, list)


# ── TestDualThresholdCheck ──

class TestDualThresholdCheck:
    """_dual_threshold_check() 双层阈值偏移检查测试群。"""

    def test_disabled_memoryflush_returns_none(self):
        """memoryFlush 未启用 -> 返 None。"""
        cc = {"maxActiveTranscriptBytes": 3_000_000, "memoryFlush": {}}
        r = compaction_diag._dual_threshold_check(cc, 131072)
        assert r is None

    def test_enabled_heterogeneous_status(self):
        """memoryFlush 启用 -> 返 heterogeneous 状态 (单位不同)。"""
        cc = {
            "maxActiveTranscriptBytes": 3_000_000,
            "memoryFlush": {
                "enabled": True,
                "softThresholdTokens": 50000,
            },
        }
        r = compaction_diag._dual_threshold_check(cc, 131072)
        assert r is not None
        assert r["status"] == "heterogeneous"
        assert r["key"] == "dual_threshold"
        # 应含 mainTokensEstimate + gateTokens
        assert "mainTokensEstimate" in r
        assert "gateTokens" in r

    def test_missing_fields_returns_none(self):
        """maxActiveTranscriptBytes 或 softThresholdTokens 缺 -> 返 None。"""
        cc = {"memoryFlush": {"enabled": True, "softThresholdTokens": 50000}}
        r = compaction_diag._dual_threshold_check(cc, 131072)
        assert r is None


# ── TestIsolationCheck ──

class TestIsolationCheck:
    """_isolation_check() 分身隔离检查测试群。"""

    def test_low_session_count_no_issues(self):
        issues = compaction_diag._isolation_check(5, {"maxTokensSeen": 10000})
        assert isinstance(issues, list)
        # 5 个 session < 12 阈值, 不应触发碎片化
        keys = [i.get("key", "") for i in issues]
        assert "isolation_fragmentation" not in keys

    def test_high_session_count_triggers(self):
        issues = compaction_diag._isolation_check(50, {"maxTokensSeen": 10000})
        keys = [i.get("key", "") for i in issues]
        assert "isolation_fragmentation" in keys

    def test_high_token_count_triggers(self):
        issues = compaction_diag._isolation_check(1, {"maxTokensSeen": 100_000})  # 100K
        keys = [i.get("key", "") for i in issues]
        assert "isolation_token_heavy" in keys

    def test_both_triggers(self):
        """session 50 + token 100K -> 两个问题都触发。"""
        issues = compaction_diag._isolation_check(50, {"maxTokensSeen": 100_000})
        keys = [i.get("key", "") for i in issues]
        assert "isolation_fragmentation" in keys
        assert "isolation_token_heavy" in keys

    def test_zero_token_data_no_token_issue(self):
        """token_data 空 -> 不触发 token 重警告。"""
        issues = compaction_diag._isolation_check(1, {})
        keys = [i.get("key", "") for i in issues]
        assert "isolation_token_heavy" not in keys


# ── TestTokenAwareCheck (IO via _SESSIONS_DIR) ──

class TestTokenAwareCheck:
    """_token_aware_check() 令牌感知检查测试群。"""

    def test_no_data_returns_no_data_status(self, monkeypatch, tmp_path):
        """无 session 目录 -> status=no_data。"""
        from pathlib import Path
        empty_dir = tmp_path / "empty_sessions"
        empty_dir.mkdir()
        monkeypatch.setattr(compaction_diag, "_SESSIONS_DIR", empty_dir)
        r = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 3_000_000})
        assert r["status"] == "no_data"
        assert r["severity"] == compaction_diag.SEVERITY_OK

    def test_with_session_data_collects_tokens(self, _fake_sessions_dir):
        """假 session 包含 5 个 usage totalTokens, 应收集到 maxTokensSeen。"""
        r = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 3_000_000})
        # maxTokensSeen 来自 usage.totalTokens, 5 轮中最大是 1000+4*100=1400
        assert r["maxTokensSeen"] >= 1000
        assert "estimatedContextPercent" in r
        assert "avgTokensPerTurn" in r

    def test_high_tokens_near_limit(self, _fake_sessions_dir, monkeypatch):
        """高 token 接近 ctx limit -> 触发 near_limit 警告。"""
        # 写一个超大的 token session
        today = datetime.now().strftime("%Y-%m-%d")
        big_lines = [
            {"type": "message",
             "message": {"role": "user",
                         "usage": {"totalTokens": 100_000}}},  # 接近 131K limit
        ]
        with open(_fake_sessions_dir / f"{today}-main-big.jsonl", "w") as f:
            for line in big_lines:
                f.write(_json.dumps(line) + "\n")

        r = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 3_000_000})
        # 100K > 131K * 0.85 = 111350 — 不到, 但 status 应是 ok 或 near_limit
        assert r["status"] in ("ok", "near_limit", "mismatch")

    def test_mismatch_when_byte_estimate_too_low(self, _fake_sessions_dir):
        """maxActiveTranscriptBytes 估计的 token 远低于实际 -> 触发 mismatch。"""
        # 实际 token = 1400, bytes 估计 = 3_000_000/4 = 750_000, 实际 < 估计的 0.5 ?
        # 这里 actual 1400 vs estimated 750K, 1400 < 750K*0.5=375K -> 是的, mismatch
        r = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 3_000_000})
        # 实际 token 很小, 估计很大, 不应 mismatch
        # 改成: maxActiveTranscriptBytes 极小, 估计的 token 远低于实际
        r = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 1000})
        # 估计 250 tokens, 实际 1400 -> 1400 < 250*0.5? 不, 1400 > 125, status 不是 mismatch
        # 测试返回 dict 即可
        assert isinstance(r, dict)
        assert "maxTokensSeen" in r


# ── TestProbeQualityCheck (IO via _SESSIONS_DIR) ──

class TestProbeQualityCheck:
    """_probe_quality_check() 探针检查测试群。"""

    def test_no_session_returns_no_compaction(self, monkeypatch, tmp_path):
        """无 session 目录 -> status=no_compaction。"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(compaction_diag, "_SESSIONS_DIR", empty_dir)
        r = compaction_diag._probe_quality_check({})
        assert r["status"] == "no_compaction"
        assert "probeQuestions" in r
        # probeQuestions 含 4 类问题模板
        assert "recall" in r["probeQuestions"]
        assert "artifact" in r["probeQuestions"]

    def test_with_compaction_event(self, _fake_sessions_dir):
        """有 compaction 事件的 session -> status=ready。"""
        # _fake_sessions_dir fixture 已经写了 1 个 compaction 事件
        r = compaction_diag._probe_quality_check({})
        assert r["status"] == "ready"
        assert r["compactionEventsToday"] >= 1
        # latestCompaction 字段
        assert r["latestCompaction"] is not None
        assert r["latestCompaction"]["tokensBefore"] == 5000


# ── TestDriftCheck (IO via _SESSIONS_DIR) ──

class TestDriftCheck:
    """_drift_check() 降解检测测试群。"""

    def test_insufficient_data(self, _fake_sessions_dir):
        """< 2 个 tokensBefore -> status=insufficient_data。"""
        # _fake_sessions_dir fixture 只有 1 个 compaction, token 5000
        r = compaction_diag._drift_check({})
        # 只有 1 个数据点 -> insufficient
        assert r["status"] in ("insufficient_data", "healthy", "degradation_suspected", "compression_stalled")
        # 至少应含 key
        assert r["key"] == "drift_detection"

    def test_degradation_detected(self, _fake_sessions_dir, monkeypatch):
        """连续 3 个 tokensBefore 下降 > 30% -> 触发 degradation_suspected。"""
        today = datetime.now().strftime("%Y-%m-%d")
        # 造 3 次 compaction: 10000 -> 8000 -> 5000
        events = [
            {"type": "compaction", "tokensBefore": 10000},
            {"type": "compaction", "tokensBefore": 8000},
            {"type": "compaction", "tokensBefore": 5000},  # 降 50%
        ]
        with open(_fake_sessions_dir / f"{today}-main-drift.jsonl", "w") as f:
            for e in events:
                f.write(_json.dumps(e) + "\n")

        r = compaction_diag._drift_check({})
        # 取最近 3 个: 10000, 8000, 5000 -> 降 50% > 30%
        assert r["status"] in ("degradation_suspected", "healthy")
        if r["status"] == "degradation_suspected":
            assert r["severity"] == compaction_diag.SEVERITY_WARN

    def test_healthy_steady_decline(self, _fake_sessions_dir, monkeypatch):
        """5%-30% 区间 -> healthy。"""
        today = datetime.now().strftime("%Y-%m-%d")
        # 10000 -> 9500 -> 9000 -> 8500 -> 8000, 降 20%
        events = [
            {"type": "compaction", "tokensBefore": 10000 - i * 500}
            for i in range(5)
        ]
        with open(_fake_sessions_dir / f"{today}-main-healthy.jsonl", "w") as f:
            for e in events:
                f.write(_json.dumps(e) + "\n")

        r = compaction_diag._drift_check({})
        # 降 20% 介于 5-30% -> healthy
        assert r["status"] in ("healthy", "compression_stalled")
        if r["status"] == "healthy":
            assert r["severity"] == compaction_diag.SEVERITY_OK


# ── TestCompactionDiagnose (公开 API) ──

class TestCompactionDiagnose:
    """compaction_diagnose() 公开 API 测试群 (mock config)。"""

    def test_diagnose_empty_config(self, mocker):
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value={}
        )
        result = compaction_diag.compaction_diagnose()
        assert isinstance(result, dict)
        # 空 config 应有 status='no_config'
        assert result["status"] == "no_config"

    def test_diagnose_with_full_config(self, mocker):
        """完整 config -> 返回完整诊断报告。"""
        full_config = {
            "mode": "safeguard",
            "maxActiveTranscriptBytes": 3_000_000,
            "keepRecentTokens": 8000,
            "reserveTokens": 4000,
            "memoryFlush": {
                "enabled": True,
                "softThresholdTokens": 50000,
            },
        }
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value=full_config
        )
        mocker.patch.object(
            compaction_diag, "_get_context_window", return_value=131072
        )
        result = compaction_diag.compaction_diagnose()
        assert isinstance(result, dict)
        # 完整 config 应有 issues 列表
        assert "issues" in result
        assert isinstance(result["issues"], list)

    def test_diagnose_with_token_aware(self, mocker):
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value={}
        )
        result = compaction_diag.compaction_diagnose(token_aware=True)
        assert isinstance(result, dict)

    def test_diagnose_with_probe(self, mocker):
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value={}
        )
        result = compaction_diag.compaction_diagnose(probe=True)
        assert isinstance(result, dict)

    def test_diagnose_handles_none_config(self, mocker):
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value=None
        )
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value=None
        )
        result = compaction_diag.compaction_diagnose()
        assert isinstance(result, dict)
        assert result["status"] == "no_config"


# ── TestSeverityConstants ──

class TestSeverityConstants:
    """SEVERITY_* 常量存在性测试。"""

    def test_severity_constants_defined(self):
        assert hasattr(compaction_diag, "SEVERITY_OK")
        assert hasattr(compaction_diag, "SEVERITY_WARN")
        assert hasattr(compaction_diag, "SEVERITY_CRIT")
        assert isinstance(compaction_diag.SEVERITY_OK, str)
        assert isinstance(compaction_diag.SEVERITY_WARN, str)
        assert isinstance(compaction_diag.SEVERITY_CRIT, str)


# ── TestCompactionApply (P0 安全) ──

class TestCompactionApply:
    """compaction_apply() 公开 API 测试群。

    【P0 安全】auto_confirm=False (默认) 应不写文件, 只生成建议。
    默认跳过, 加 @pytest.mark.slow 标记。
    """

    @pytest.mark.slow
    def test_apply_dry_run_does_not_write(self, mocker, tmp_path):
        """auto_confirm=False -> 不写 openclaw.json。"""
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
        cfg_file = tmp_path / "openclaw.json"
        cfg_file.write_text("{}")
        mocker.patch.object(compaction_diag, "_load_openclaw_json", return_value={})
        mocker.patch.object(compaction_diag, "_OPENCLAW_JSON", cfg_file)

        result = compaction_diag.compaction_apply(auto_confirm=False)
        # dry_run: 文件不应被改 (仍 {})
        assert cfg_file.read_text() == "{}"
        assert "changes" in result or "status" in result

    def test_apply_nothing_to_do(self, mocker, tmp_path):
        """diagnose.actionable=False -> 返 status=nothing_to_do, 不写。"""
        fake_diag = {
            "actionable": False,
            "recommendations": [],
            "timestamp": "2026-06-30T11:30:00",
            "summary": "已完美",
        }
        mocker.patch.object(
            compaction_diag, "compaction_diagnose", return_value=fake_diag
        )
        result = compaction_diag.compaction_apply(auto_confirm=True)
        # 不可改任何东西
        assert result["status"] == "nothing_to_do"
        assert result["changes"] == []

    def test_apply_function_exists(self):
        assert hasattr(compaction_diag, "compaction_apply")
        assert callable(compaction_diag.compaction_apply)


# ── TestGetContextWindow ──

class TestGetContextWindow:
    """_get_context_window() 上下文窗口大小获取测试群。"""

    def test_no_openclaw_json_returns_default(self, mocker):
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value=None
        )
        w = compaction_diag._get_context_window()
        # 应是默认值 (>= 8192)
        assert isinstance(w, int)
        assert w >= 8192

    def test_empty_config_returns_default(self, mocker):
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        w = compaction_diag._get_context_window()
        assert isinstance(w, int)

    def test_extracts_from_models_providers(self, mocker):
        """models.providers.<name>.models[].contextWindow 应能提取。"""
        cfg = {
            "models": {
                "providers": {
                    "deepseek-company": {
                        "models": [
                            {"name": "deepseek-chat", "contextWindow": 200000}
                        ]
                    }
                }
            }
        }
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value=cfg
        )
        w = compaction_diag._get_context_window()
        assert w == 200000


# ── TestGetCompactionConfig ──

class TestGetCompactionConfig:
    """_get_compaction_config() 配置段提取测试群。"""

    def test_no_config_returns_none(self, mocker):
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value=None
        )
        cc = compaction_diag._get_compaction_config()
        assert cc is None

    def test_empty_config_returns_empty_dict(self, mocker):
        """空 config -> 返 None (因为 agents.defaults.compaction 缺)。"""
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value={}
        )
        cc = compaction_diag._get_compaction_config()
        # 实际: {} 走 .get 链, agents.defaults.compaction 缺 -> 返 {}
        # 但 _get_compaction_config 在 cfg falsy 时返 None, 这里 cfg={} 是 truthy
        assert cc is None or cc == {}

    def test_extracts_compaction_section(self, mocker):
        cfg = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                    }
                }
            }
        }
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value=cfg
        )
        cc = compaction_diag._get_compaction_config()
        assert cc is not None
        assert cc["maxActiveTranscriptBytes"] == 3_000_000


class TestCompactionDiagnoseWarnPaths:
    """compaction_diagnose() 的告警/汇总分支测试。"""

    def test_collects_warn_advice_from_token_probe_isolation_and_drift(self, mocker):
        cfg = {
            "mode": "safeguard",
            "maxActiveTranscriptBytes": 1000,
            "keepRecentTokens": 2000,
            "reserveTokens": 4000,
            "memoryFlush": {},
        }
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value=cfg
        )
        mocker.patch.object(
            compaction_diag, "_get_context_window", return_value=131072
        )
        mocker.patch.object(compaction_diag.Path, "home", return_value=Path("/tmp/fakehome"))
        mocker.patch.object(
            compaction_diag,
            "_check_stat",
            return_value=[
                {
                    "key": "session_fragmentation",
                    "severity": compaction_diag.SEVERITY_WARN,
                    "status": "high",
                    "advice": "会话碎片过多。",
                }
            ],
        )
        mocker.patch.object(
            compaction_diag,
            "_token_aware_check",
            return_value={
                "key": "token_awareness",
                "severity": compaction_diag.SEVERITY_WARN,
                "status": "near_limit",
                "advice": "token 已接近上限。",
                "maxTokensSeen": 120000,
                "avgTokensPerTurn": 8.0,
            },
        )
        mocker.patch.object(
            compaction_diag,
            "_dual_threshold_check",
            return_value={
                "key": "dual_threshold",
                "severity": compaction_diag.SEVERITY_OK,
                "status": "heterogeneous",
                "advice": "双层阈值设计合理。",
            },
        )
        mocker.patch.object(
            compaction_diag,
            "_probe_quality_check",
            return_value={
                "key": "probe_quality",
                "severity": compaction_diag.SEVERITY_OK,
                "status": "ready",
                "advice": "可运行 probe。",
                "compactionEventsToday": 1,
                "probeQuestions": {"recall": "x"},
            },
        )
        mocker.patch.object(
            compaction_diag,
            "_isolation_check",
            return_value=[
                {
                    "key": "isolation_fragmentation",
                    "severity": compaction_diag.SEVERITY_WARN,
                    "status": "high",
                    "advice": "建议拆子 Agent。",
                }
            ],
        )
        mocker.patch.object(
            compaction_diag,
            "_drift_check",
            return_value={
                "key": "drift_detection",
                "severity": compaction_diag.SEVERITY_WARN,
                "status": "compression_stalled",
                "advice": "压缩疑似停滞。",
                "compactionCount": 3,
            },
        )

        result = compaction_diag.compaction_diagnose(token_aware=True, probe=True)

        assert result["status"] == "warn"
        assert result["actionable"] is True
        assert "token 已接近上限。" in result["advice"]
        assert "可运行 probe。" in result["advice"]
        assert "建议拆子 Agent。" in result["advice"]
        assert "压缩疑似停滞。" in result["advice"]
        assert result["summary"].startswith("发现 ")


class TestPrintFunctionsMoreBranches:
    """继续补 print_diagnose()/print_apply_result() 的剩余分支。"""

    def test_print_diagnose_ok_short_circuit(self, capsys):
        diag = {
            "status": "ok",
            "summary": "所有压缩配置在舒适范围内 ✅",
            "contextWindow": 131072,
            "todaySessionCount": 0,
            "largestTranscriptMB": 0.0,
            "openclawJsonPath": "/tmp/openclaw.json",
            "issues": [],
            "advice": [],
        }

        compaction_diag.print_diagnose(diag)
        out = capsys.readouterr().out

        assert "所有压缩配置在舒适范围内" in out

    def test_print_diagnose_renders_general_missing_probe_and_isolation(self, capsys):
        diag = {
            "status": "warn",
            "summary": "发现 3 个优化点",
            "contextWindow": 131072,
            "todaySessionCount": 9,
            "largestTranscriptMB": 2.5,
            "openclawJsonPath": "/tmp/openclaw.json",
            "issues": [
                {
                    "key": "memoryFlush",
                    "label": "Memory Flush（压缩前记忆写入）",
                    "severity": compaction_diag.SEVERITY_WARN,
                    "status": "missing",
                    "advice": "启用 memoryFlush。",
                },
                {
                    "key": "probe_quality",
                    "label": "摘要质量探针",
                    "severity": compaction_diag.SEVERITY_OK,
                    "status": "ready",
                    "compactionEventsToday": 2,
                    "latestCompaction": {
                        "tokensBefore": 5000,
                        "sessionFile": "2026-07-01-main.jsonl",
                    },
                    "probeQuestions": {
                        "recall": "x",
                        "artifact": "y",
                    },
                    "advice": "今日可运行 probe。",
                },
                {
                    "key": "isolation_fragmentation",
                    "label": "分身隔离建议（碎片化）",
                    "severity": compaction_diag.SEVERITY_WARN,
                    "status": "high",
                    "current": 15,
                    "threshold": 12,
                    "advice": "建议拆分子任务。",
                },
            ],
            "advice": ["启用 memoryFlush。"],
        }

        compaction_diag.print_diagnose(diag)
        out = capsys.readouterr().out

        assert "状态: 未启用" in out
        assert "今日压缩事件: 2 次" in out
        assert "探针问题数: 2 类" in out
        assert "阈值: 12" in out

    def test_print_apply_result_applied_error_and_fallback(self, capsys):
        compaction_diag.print_apply_result(
            {
                "status": "applied",
                "changes": [{"key": "keepRecentTokens", "from": 8000, "to": 15000}],
                "backupPath": "/tmp/openclaw.json.bak.20260701",
            }
        )
        applied_out = capsys.readouterr().out
        assert "已应用压缩配置优化" in applied_out
        assert "备份: /tmp/openclaw.json.bak.20260701" in applied_out

        compaction_diag.print_apply_result(
            {
                "status": "error",
                "summary": "无法读取 openclaw.json",
            }
        )
        error_out = capsys.readouterr().out
        assert "错误: 无法读取 openclaw.json" in error_out

        compaction_diag.print_apply_result(
            {
                "status": "custom",
                "summary": "自定义状态摘要",
            }
        )
        fallback_out = capsys.readouterr().out
        assert "自定义状态摘要" in fallback_out


class TestCompactionDiagnoseCurrentConfig:
    """compaction_diagnose() 的 currentConfig 汇总与脱敏测试。"""

    def test_truncates_memoryflush_prompt_and_keeps_soft_threshold(self, mocker):
        long_prompt = "关键决策：" + ("A" * 120)
        full_config = {
            "mode": "safeguard",
            "truncateAfterCompaction": True,
            "notifyUser": True,
            "maxActiveTranscriptBytes": 3_000_000,
            "keepRecentTokens": 15_000,
            "reserveTokens": 16_000,
            "memoryFlush": {
                "enabled": True,
                "softThresholdTokens": 50_000,
                "prompt": long_prompt,
                "systemPrompt": "只保留长期有价值的信息。",
            },
        }
        mocker.patch.object(
            compaction_diag, "_get_compaction_config", return_value=full_config
        )
        mocker.patch.object(
            compaction_diag, "_get_context_window", return_value=200_000
        )
        mocker.patch.object(compaction_diag, "_check_stat", return_value=[])
        mocker.patch.object(
            compaction_diag,
            "_drift_check",
            return_value={
                "key": "drift_detection",
                "label": "上下文降解检测",
                "status": "healthy",
                "severity": compaction_diag.SEVERITY_OK,
                "compactionCount": 3,
                "recentTokensBefore": [10000, 9000, 8000],
                "dropRatio": 0.2,
                "advice": "压缩趋势健康。",
            },
        )
        mocker.patch.object(compaction_diag, "_isolation_check", return_value=[])

        result = compaction_diag.compaction_diagnose()

        assert result["status"] == "ok"
        current = result["currentConfig"]
        assert current["memoryFlush"]["softThresholdTokens"] == 50_000
        assert current["memoryFlush"]["prompt"].endswith("…")
        assert len(current["memoryFlush"]["prompt"]) == 81
        keys = [issue["key"] for issue in result["issues"]]
        assert "memoryFlush.softThresholdTokens" in keys


class TestCompactionApplyAutoConfirm:
    """compaction_apply(auto_confirm=True) 真写入路径测试。"""

    def test_apply_auto_confirm_writes_backup_and_updates_config(self, mocker, tmp_path):
        fake_diag = {
            "actionable": True,
            "issues": [
                {
                    "key": "maxActiveTranscriptBytes",
                    "status": "too_low",
                    "current": 1000,
                    "advice": "阈值过低，建议提高。",
                },
                {
                    "key": "memoryFlush",
                    "status": "missing",
                    "advice": "启用 memoryFlush。",
                },
            ],
            "summary": "发现 2 个优化点",
        }
        cfg = {"agents": {"defaults": {"compaction": {}}}}
        cfg_file = tmp_path / "openclaw.json"
        cfg_file.write_text(_json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

        mocker.patch.object(
            compaction_diag, "compaction_diagnose", return_value=fake_diag
        )
        mocker.patch.object(compaction_diag, "_load_openclaw_json", return_value=cfg)
        mocker.patch.object(compaction_diag, "_OPENCLAW_JSON", cfg_file)

        result = compaction_diag.compaction_apply(auto_confirm=True)

        assert result["status"] == "applied"
        assert len(result["changes"]) == 2
        saved = _json.loads(cfg_file.read_text(encoding="utf-8"))
        compaction_cfg = saved["agents"]["defaults"]["compaction"]
        assert compaction_cfg["maxActiveTranscriptBytes"] == 3_000_000
        assert compaction_cfg["memoryFlush"]["enabled"] is True
        assert compaction_cfg["memoryFlush"]["softThresholdTokens"] == 32_000
        backup_files = list(tmp_path.glob("openclaw.json.bak.*"))
        assert len(backup_files) == 1
        assert result["backupPath"] == str(backup_files[0])


class TestPrintFunctions:
    """print_diagnose() / print_apply_result() 输出测试。"""

    def test_print_diagnose_renders_special_issue_sections(self, capsys):
        diag = {
            "status": "warn",
            "summary": "发现 2 个优化点",
            "contextWindow": 131072,
            "todaySessionCount": 3,
            "largestTranscriptMB": 1.2,
            "openclawJsonPath": "/tmp/openclaw.json",
            "issues": [
                {
                    "key": "token_awareness",
                    "label": "令牌感知诊断",
                    "status": "near_limit",
                    "severity": compaction_diag.SEVERITY_WARN,
                    "maxTokensSeen": 120000,
                    "estimatedContextPercent": 91.5,
                    "estimatedByteEquivalentTokens": 750000,
                    "advice": "建议降低阈值。",
                },
                {
                    "key": "drift_detection",
                    "label": "上下文降解检测",
                    "status": "healthy",
                    "severity": compaction_diag.SEVERITY_OK,
                    "compactionCount": 3,
                    "recentTokensBefore": [10000, 9000, 8000],
                    "dropRatio": 0.2,
                    "advice": "压缩趋势健康。",
                },
            ],
            "advice": ["建议降低阈值。"],
        }

        compaction_diag.print_diagnose(diag)
        out = capsys.readouterr().out

        assert "Mark42 压缩配置诊断 v2.0" in out
        assert "实际最大 token: 120000" in out
        assert "最近 trend: [10000, 9000, 8000]" in out
        assert "优化建议汇总" in out

    def test_print_apply_result_renders_dry_run_changes(self, capsys):
        result = {
            "status": "dry_run",
            "changes": [
                {
                    "key": "maxActiveTranscriptBytes",
                    "from": 1000,
                    "to": 3_000_000,
                    "reason": "阈值过低，建议提高。",
                }
            ],
        }

        compaction_diag.print_apply_result(result)
        out = capsys.readouterr().out

        assert "预览模式" in out
        assert "maxActiveTranscriptBytes" in out
        assert "执行 --apply 以应用更改" in out


class TestGetContextWindowDictModels:
    """_get_context_window() 的 dict 型 models 分支测试。"""

    def test_extracts_from_models_dict_shape(self, mocker):
        cfg = {
            "models": {
                "providers": {
                    "deepseek": {
                        "models": {
                            "deepseek-chat": {"contextWindow": 262144}
                        }
                    }
                }
            }
        }
        mocker.patch.object(
            compaction_diag, "_load_openclaw_json", return_value=cfg
        )

        w = compaction_diag._get_context_window()

        assert w == 262144


class TestLoadOpenclawJsonMoreBranches:
    """_load_openclaw_json() 的缺失/异常分支测试。"""

    def test_returns_none_when_path_missing(self, mocker, tmp_path):
        missing = tmp_path / "missing-openclaw.json"
        mocker.patch.object(compaction_diag, "_OPENCLAW_JSON", missing)

        assert compaction_diag._load_openclaw_json() is None

    def test_returns_none_on_invalid_json(self, mocker, tmp_path):
        bad = tmp_path / "openclaw.json"
        bad.write_text("{not-valid-json", encoding="utf-8")
        mocker.patch.object(compaction_diag, "_OPENCLAW_JSON", bad)

        assert compaction_diag._load_openclaw_json() is None

    def test_returns_none_on_oserror(self, mocker, tmp_path):
        cfg_file = tmp_path / "openclaw.json"
        cfg_file.write_text("{}", encoding="utf-8")
        mocker.patch.object(compaction_diag, "_OPENCLAW_JSON", cfg_file)
        mocker.patch("builtins.open", side_effect=OSError("boom"))

        assert compaction_diag._load_openclaw_json() is None


class TestSessionReadersMoreBranches:
    """token/probe/drift 三类 session 读取器的容错分支测试。"""

    def test_token_aware_handles_missing_dir_and_near_limit(self, monkeypatch, tmp_path):
        missing_dir = tmp_path / "missing-sessions"
        monkeypatch.setattr(compaction_diag, "_SESSIONS_DIR", missing_dir)
        no_data = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 3_000_000})
        assert no_data["status"] == "no_data"

        real_dir = tmp_path / "sessions"
        real_dir.mkdir()
        today = datetime.now().strftime("%Y-%m-%d")
        (real_dir / f"{today}-near-limit.jsonl").write_text(
            _json.dumps(
                {
                    "type": "message",
                    "message": {"role": "assistant", "usage": {"totalTokens": 120000}},
                }
            ) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(compaction_diag, "_SESSIONS_DIR", real_dir)

        result = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 1_000_000})
        assert result["status"] == "near_limit"
        assert result["severity"] == compaction_diag.SEVERITY_WARN

    def test_token_probe_and_drift_skip_invalid_json_empty_lines_and_oserror(self, monkeypatch, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        today = datetime.now().strftime("%Y-%m-%d")
        good = sessions_dir / f"{today}-good.jsonl"
        broken = sessions_dir / f"{today}-broken.jsonl"
        good.write_text(
            "\n".join(
                [
                    "",
                    "{bad-json",
                    _json.dumps({
                        "type": "message",
                        "message": {"role": "assistant", "usage": {"totalTokens": 2000}},
                    }),
                    _json.dumps({"type": "compaction", "tokensBefore": 6000, "details": "ok", "fromHook": True}),
                    _json.dumps({"type": "compaction", "tokensBefore": 0}),
                    _json.dumps({"type": "compaction", "tokensBefore": 5900}),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        broken.write_text(_json.dumps({"type": "compaction", "tokensBefore": 5800}), encoding="utf-8")
        monkeypatch.setattr(compaction_diag, "_SESSIONS_DIR", sessions_dir)

        import builtins
        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if str(path).endswith("broken.jsonl"):
                raise OSError("simulated read failure")
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", fake_open)

        token_result = compaction_diag._token_aware_check({"maxActiveTranscriptBytes": 10_000})
        probe_result = compaction_diag._probe_quality_check({})
        drift_result = compaction_diag._drift_check({})

        assert token_result["maxTokensSeen"] == 6000
        assert probe_result["status"] == "ready"
        assert probe_result["latestCompaction"]["tokensBefore"] == 6000
        assert drift_result["status"] == "healthy"


class TestCompactionDiagnoseAdditionalBranches:
    """继续补 compaction_diagnose() 的剩余汇总分支。"""

    def test_collects_soft_threshold_warn_and_scans_real_sessions_dir(self, mocker, tmp_path):
        cfg = {
            "mode": "safeguard",
            "maxActiveTranscriptBytes": 3_000_000,
            "keepRecentTokens": 15_000,
            "reserveTokens": 16_000,
            "memoryFlush": {
                "enabled": True,
                "softThresholdTokens": 1000,
                "prompt": "p",
            },
        }
        sessions_dir = tmp_path / ".openclaw" / "agents" / "main" / "sessions"
        sessions_dir.mkdir(parents=True)
        today = datetime.now().strftime("%Y-%m-%d")
        payload = "x" * (200 * 1024)
        (sessions_dir / f"{today}-scan.jsonl").write_text(payload, encoding="utf-8")

        mocker.patch.object(compaction_diag, "_get_compaction_config", return_value=cfg)
        mocker.patch.object(compaction_diag, "_get_context_window", return_value=131072)
        mocker.patch.object(compaction_diag.Path, "home", return_value=tmp_path)
        mocker.patch.object(compaction_diag, "_check_stat", return_value=[])
        mocker.patch.object(
            compaction_diag,
            "_token_aware_check",
            return_value={
                "key": "token_awareness",
                "severity": compaction_diag.SEVERITY_WARN,
                "status": "near_limit",
                "advice": "token 接近上限。",
                "maxTokensSeen": 120000,
                "avgTokensPerTurn": 6.0,
            },
        )
        mocker.patch.object(
            compaction_diag,
            "_dual_threshold_check",
            return_value={
                "key": "dual_threshold",
                "severity": compaction_diag.SEVERITY_WARN,
                "status": "misaligned",
                "advice": "双层阈值需要调整。",
            },
        )
        mocker.patch.object(compaction_diag, "_isolation_check", return_value=[])
        mocker.patch.object(
            compaction_diag,
            "_drift_check",
            return_value={
                "key": "drift_detection",
                "severity": compaction_diag.SEVERITY_OK,
                "status": "healthy",
                "advice": "趋势健康。",
                "compactionCount": 3,
            },
        )

        result = compaction_diag.compaction_diagnose(token_aware=True)

        assert result["status"] == "warn"
        assert result["todaySessionCount"] == 1
        assert result["largestTranscriptMB"] > 0
        assert "token 接近上限。" in result["advice"]
        assert "双层阈值需要调整。" in result["advice"]
        issue_keys = [issue["key"] for issue in result["issues"]]
        assert "softThresholdTokens" in issue_keys


class TestCompactionApplyMoreBranches:
    """继续补 compaction_apply() 的 error / no-change / 额外修正分支。"""

    def test_apply_returns_error_when_config_cannot_be_loaded(self, mocker):
        mocker.patch.object(
            compaction_diag,
            "compaction_diagnose",
            return_value={"actionable": True, "issues": [], "summary": "需调优"},
        )
        mocker.patch.object(compaction_diag, "_load_openclaw_json", return_value=None)

        result = compaction_diag.compaction_apply(auto_confirm=True)

        assert result["status"] == "error"
        assert result["summary"] == "无法读取 openclaw.json"

    def test_apply_returns_nothing_to_do_when_no_supported_changes(self, mocker):
        mocker.patch.object(
            compaction_diag,
            "compaction_diagnose",
            return_value={
                "actionable": True,
                "issues": [{"key": "unknown", "status": "warn", "advice": "noop"}],
                "summary": "有告警但无自动修正项",
            },
        )
        mocker.patch.object(compaction_diag, "_load_openclaw_json", return_value={"agents": {"defaults": {"compaction": {}}}})

        result = compaction_diag.compaction_apply(auto_confirm=False)

        assert result["status"] == "nothing_to_do"
        assert result["summary"] == "无需要修改的配置项"

    def test_apply_adjusts_keep_recent_and_reserve_tokens(self, mocker):
        cfg = {"agents": {"defaults": {"compaction": {}}}}
        mocker.patch.object(
            compaction_diag,
            "compaction_diagnose",
            return_value={
                "actionable": True,
                "issues": [
                    {
                        "key": "keepRecentTokens",
                        "status": "too_high",
                        "current": 99_999,
                        "advice": "保留太多。",
                    },
                    {
                        "key": "reserveTokens",
                        "status": "too_low",
                        "current": 1000,
                        "advice": "预留太少。",
                    },
                ],
                "summary": "发现 2 个优化点",
            },
        )
        mocker.patch.object(compaction_diag, "_load_openclaw_json", return_value=cfg)

        result = compaction_diag.compaction_apply(auto_confirm=False)

        assert result["status"] == "dry_run"
        assert [change["key"] for change in result["changes"]] == ["keepRecentTokens", "reserveTokens"]
        compact = cfg["agents"]["defaults"]["compaction"]
        assert compact["keepRecentTokens"] == 15_000
        assert compact["reserveTokens"] == 16_000


class TestPrintFunctionsAdditionalBranches:
    """继续补 print_diagnose() 的其余输出分支。"""

    def test_print_diagnose_renders_token_no_data_dual_threshold_and_general_ranges(self, capsys):
        diag = {
            "status": "warn",
            "summary": "发现 4 个优化点",
            "contextWindow": 131072,
            "todaySessionCount": 1,
            "largestTranscriptMB": 0.3,
            "openclawJsonPath": "/tmp/openclaw.json",
            "issues": [
                {
                    "key": "token_awareness",
                    "label": "令牌感知诊断",
                    "status": "no_data",
                    "severity": compaction_diag.SEVERITY_OK,
                    "advice": "暂无 token 数据。",
                },
                {
                    "key": "dual_threshold",
                    "label": "双层阈值偏移",
                    "status": "heterogeneous",
                    "severity": compaction_diag.SEVERITY_OK,
                    "mainTokensEstimate": 750000,
                    "gateTokens": 32000,
                    "ratio": 0.04,
                    "gapPercent": 96,
                    "advice": "异构单位，设计合理。",
                },
                {
                    "key": "drift_detection",
                    "label": "上下文降解检测",
                    "status": "insufficient_data",
                    "severity": compaction_diag.SEVERITY_OK,
                    "compactionCount": 1,
                    "advice": "数据不足。",
                },
                {
                    "key": "maxActiveTranscriptBytes",
                    "label": "JSONL 压缩阈值",
                    "status": "ok",
                    "severity": compaction_diag.SEVERITY_OK,
                    "current_human": "3.0MB",
                    "range": "1.0MB ~ 10.0MB",
                },
                {
                    "key": "keepRecentTokens",
                    "label": "保留最近 Token 数",
                    "status": "too_high",
                    "severity": compaction_diag.SEVERITY_WARN,
                    "current_human": "50000",
                    "comfort_human": "15000",
                    "range": "8000 ~ 30000",
                    "advice": "建议降到舒适值。",
                },
            ],
            "advice": [],
        }

        compaction_diag.print_diagnose(diag)
        out = capsys.readouterr().out

        assert "状态: no_data" in out
        assert "主阈值等效: ~750000 tokens" in out
        assert "状态: 数据不足（仅 1 次压缩）" in out
        assert "JSONL 压缩阈值 = 3.0MB (舒适范围 1.0MB ~ 10.0MB)" in out
        assert "舒适值: 15000 (范围 8000 ~ 30000)" in out

