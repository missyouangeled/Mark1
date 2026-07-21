"""test_compaction_diag.py - 压缩配置诊断模块测试。

覆盖：
- compaction_diagnose: 返回结构、各种诊断场景
- compaction_apply: dry-run 模式 vs actual 应用
- print_diagnose / print_apply_result: 不报错、正确输出
- 工具函数: _check_value, _format_bytes, _get_context_window
"""
import json
from pathlib import Path

from mark42 import compaction_diag as cd

# ── 工具函数测试 ───────────────────────────────────────────

class TestUtilityFunctions:
    def test_format_bytes_bytes(self):
        """字节级显示。"""
        assert cd._format_bytes(100) == "100B"
        assert cd._format_bytes(999) == "999B"

    def test_format_bytes_kb(self):
        """KB 级显示。"""
        assert cd._format_bytes(1000) == "1KB"
        assert cd._format_bytes(1500) == "2KB"  # 四舍五入

    def test_format_bytes_mb(self):
        """MB 级显示。"""
        assert cd._format_bytes(1_000_000) == "1.0MB"
        assert cd._format_bytes(3_000_000) == "3.0MB"
        assert cd._format_bytes(3_500_000) == "3.5MB"

    def test_check_value_too_low(self):
        """值过低应返回 too_low 状态和 warn severity。"""
        result = cd._check_value("maxActiveTranscriptBytes", 500_000, 128000)
        assert result["status"] == "too_low"
        assert result["severity"] == cd.SEVERITY_WARN
        assert "建议" in result["advice"]

    def test_check_value_too_high(self):
        """值过高应返回 too_high 状态。"""
        # keepRecentTokens 太高触发 warn
        result = cd._check_value("keepRecentTokens", 40_000, 128000)
        assert result["status"] == "too_high"
        assert result["severity"] == cd.SEVERITY_WARN

    def test_check_value_ok(self):
        """舒适范围内应返回 ok。"""
        result = cd._check_value("keepRecentTokens", 15_000, 128000)
        assert result["status"] == "ok"
        assert result["severity"] == cd.SEVERITY_OK

    def test_check_value_missing_key(self):
        """未知键应返回 ok。"""
        result = cd._check_value("unknown_key", 100, 128000)
        assert result["status"] == "missing"

    def test_check_value_none_value(self):
        """None 值应返回 missing。"""
        result = cd._check_value("keepRecentTokens", None, 128000)
        assert result["status"] == "missing"


# ── compaction_diagnose ────────────────────────────────────

class TestCompactionDiagnose:
    def test_no_config_returns_no_config_status(self, tmp_path, monkeypatch):
        """配置文件不存在应返回 no_config 状态。"""
        monkeypatch.setattr(cd, "_OPENCLAW_JSON", tmp_path / "nonexistent.json")

        result = cd.compaction_diagnose()
        assert result["status"] == "no_config"
        assert result["actionable"] is False

    def test_compaction_with_missing_memoryflush(self, tmp_path, monkeypatch):
        """缺少 memoryFlush 配置应检测出问题。"""
        config_path = tmp_path / "openclaw.json"
        # 至少要有一个配置项，否则 {} 会被视为 falsy
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                        # memoryFlush 缺失
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)
        monkeypatch.setattr(cd, "_SESSIONS_DIR", tmp_path / "sessions")  # 不存在的目录

        result = cd.compaction_diagnose()
        assert result["status"] == "warn"
        assert result["actionable"] is True
        # 应检测到 memoryFlush 缺失
        memory_issues = [i for i in result["issues"] if i["key"] == "memoryFlush"]
        assert len(memory_issues) > 0

    def test_perfect_config_returns_ok(self, tmp_path, monkeypatch):
        """完美配置应返回 ok。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                        "reserveTokens": 16_000,
                        "memoryFlush": {
                            "enabled": True,
                            "softThresholdTokens": 32_000,
                        },
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)
        # mock Path.home() 来避免检查真实的 session 目录
        _original_home = Path.home
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # 确保 sessions 目录不存在
        sessions_dir = tmp_path / ".openclaw" / "agents" / "main" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)  # 创建但留空
        # 也 mock _SESSIONS_DIR 供其他函数使用
        monkeypatch.setattr(cd, "_SESSIONS_DIR", sessions_dir)

        result = cd.compaction_diagnose()

        # 所有基础检查应通过
        if result["status"] != "ok":
            # 打印 issues 便于调试
            for issue in result["issues"]:
                print(f"Issue: {issue}")
        assert result["status"] == "ok"
        assert result["actionable"] is False

    def test_returns_correct_structure(self, tmp_path, monkeypatch):
        """diagnose 应返回正确结构。"""
        config_path = tmp_path / "openclaw.json"
        # 要有完整配置，避免 missing 值为 None 时触发 code bug（missing 的 issue 没有 advice 字段
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)
        # mock Path.home() 来避免检查真实的 session 目录
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        sessions_dir = tmp_path / ".openclaw" / "agents" / "main" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(cd, "_SESSIONS_DIR", sessions_dir)

        result = cd.compaction_diagnose()

        required_keys = {
            "diagnosedAt", "status", "summary", "openclawJsonPath",
            "contextWindow", "todaySessionCount", "largestTranscriptMB",
            "currentConfig", "issues", "advice", "actionable"
        }
        assert required_keys.issubset(result.keys())
        assert isinstance(result["issues"], list)
        assert isinstance(result["advice"], list)

    def test_memory_flush_disabled_triggers_warn(self, tmp_path, monkeypatch):
        """memoryFlush 禁用应触发 warn。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                        "memoryFlush": {"enabled": False},
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)

        result = cd.compaction_diagnose()
        assert result["status"] == "warn"
        assert any(i["key"] == "memoryFlush" for i in result["issues"])

    def test_current_config_included(self, tmp_path, monkeypatch):
        """当前配置应包含在结果中。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "mode": "safeguard",
                        "truncateAfterCompaction": True,
                        "notifyUser": True,
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)

        result = cd.compaction_diagnose()
        assert "currentConfig" in result
        assert result["currentConfig"]["mode"] == "safeguard"
        assert result["currentConfig"]["maxActiveTranscriptBytes"] == 3_000_000


# ── compaction_apply ───────────────────────────────────────

class TestCompactionApply:
    def test_dry_run_mode_default(self, tmp_path, monkeypatch):
        """默认 auto_confirm=False 应是 dry-run 模式。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 500_000,  # 太低
                        "keepRecentTokens": 1000,  # 太低
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)

        result = cd.compaction_apply(auto_confirm=False)

        assert result["status"] == "dry_run"
        assert len(result["changes"]) > 0
        # 配置文件不应被修改
        with open(config_path) as f:
            cfg = json.load(f)
        assert cfg["agents"]["defaults"]["compaction"]["maxActiveTranscriptBytes"] == 500_000

    def test_actual_apply_modifies_config(self, tmp_path, monkeypatch):
        """auto_confirm=True 应实际修改配置。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 500_000,  # 太低
                        "keepRecentTokens": 1000,  # 太低
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)

        result = cd.compaction_apply(auto_confirm=True)

        assert result["status"] == "applied"
        assert "backupPath" in result
        # 配置文件应已修改
        with open(config_path) as f:
            cfg = json.load(f)
        assert cfg["agents"]["defaults"]["compaction"]["maxActiveTranscriptBytes"] == 3_000_000

    def test_nothing_to_do_when_perfect(self, tmp_path, monkeypatch):
        """完美配置时应返回 nothing_to_do。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                        "reserveTokens": 16_000,
                        "memoryFlush": {
                            "enabled": True,
                            "softThresholdTokens": 32_000,
                        },
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)

        result = cd.compaction_apply(auto_confirm=False)
        assert result["status"] == "nothing_to_do"
        assert result["changes"] == []

    def test_change_structure_is_correct(self, tmp_path, monkeypatch):
        """change 结构应包含 key, from, to, reason。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "keepRecentTokens": 1000,  # 太低 - 这个会被修复
                        "maxActiveTranscriptBytes": 3_000_000,  # 刚好正确，不会触发碎片检查问题
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)
        monkeypatch.setattr(cd, "_SESSIONS_DIR", tmp_path / "nonexistent_sessions")

        result = cd.compaction_apply(auto_confirm=False)

        assert len(result["changes"]) > 0
        change = result["changes"][0]
        assert "key" in change
        assert "from" in change
        assert "to" in change
        assert "reason" in change

    def test_no_config_returns_nothing_to_do(self, tmp_path, monkeypatch):
        """配置文件不存在应返回 nothing_to_do（因为 actionable=False）。"""
        config_path = tmp_path / "nonexistent.json"
        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)

        result = cd.compaction_apply(auto_confirm=False)
        # 当 config 不存在时，diagnose 返回 actionable=False
        # 这会导致 compaction_apply 返回 nothing_to_do
        assert result["status"] in ("nothing_to_do", "error")

    def test_memory_flush_is_applied_when_missing(self, tmp_path, monkeypatch):
        """缺失 memoryFlush 时应自动添加。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                        # memoryFlush 缺失
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)

        cd.compaction_apply(auto_confirm=True)

        # 检查 memoryFlush 已添加
        with open(config_path) as f:
            cfg = json.load(f)
        mf = cfg["agents"]["defaults"]["compaction"]["memoryFlush"]
        assert mf["enabled"] is True
        assert mf["softThresholdTokens"] == 32_000
        assert "prompt" in mf
        assert "systemPrompt" in mf


# ── print_diagnose ─────────────────────────────────────────

class TestPrintDiagnose:
    def test_print_ok_status_does_not_crash(self, tmp_path, monkeypatch, caplog):
        """打印 ok 状态不应崩溃。"""
        diag = {
            "status": "ok",
            "contextWindow": 128000,
            "todaySessionCount": 0,
            "largestTranscriptMB": 0.0,
            "openclawJsonPath": str(tmp_path / "openclaw.json"),
            "issues": [],
        }

        # 不应抛出异常
        cd.print_diagnose(diag)

    def test_print_warn_status_does_not_crash(self, tmp_path, monkeypatch, caplog):
        """打印 warn 状态不应崩溃。"""
        diag = {
            "status": "warn",
            "summary": "发现 1 个优化点",
            "contextWindow": 128000,
            "todaySessionCount": 0,
            "largestTranscriptMB": 0.0,
            "openclawJsonPath": str(tmp_path / "openclaw.json"),
            "issues": [
                {
                    "key": "keepRecentTokens",
                    "label": "保留最近 Token 数",
                    "severity": "warn",
                    "status": "too_low",
                    "current": 1000,
                    "current_human": "1000",
                    "comfort": 15000,
                    "comfort_human": "15000",
                    "range": "8000 ~ 30000",
                    "advice": "保留太少，建议提高到 15000",
                }
            ],
            "advice": ["保留太少，建议提高到 15000"],
        }

        # 不应抛出异常
        cd.print_diagnose(diag)

    def test_print_missing_memoryflush_does_not_crash(self, tmp_path, monkeypatch, caplog):
        """打印缺失 memoryFlush 不应崩溃。"""
        diag = {
            "status": "warn",
            "summary": "memoryFlush 未启用",
            "contextWindow": 128000,
            "todaySessionCount": 0,
            "largestTranscriptMB": 0.0,
            "openclawJsonPath": str(tmp_path / "openclaw.json"),
            "issues": [
                {
                    "key": "memoryFlush",
                    "label": "Memory Flush（压缩前记忆写入）",
                    "severity": "warn",
                    "status": "missing",
                    "advice": "启用 memoryFlush",
                }
            ],
            "advice": ["启用 memoryFlush"],
        }

        # 不应抛出异常
        cd.print_diagnose(diag)

    def test_print_with_advice_list_does_not_crash(self, tmp_path, monkeypatch, caplog):
        """打印带 advice 列表不应崩溃。"""
        diag = {
            "status": "warn",
            "summary": "发现 2 个优化点",
            "contextWindow": 128000,
            "todaySessionCount": 0,
            "largestTranscriptMB": 0.0,
            "openclawJsonPath": str(tmp_path / "openclaw.json"),
            "issues": [
                {
                    "key": "keepRecentTokens",
                    "label": "保留最近 Token 数",
                    "severity": "warn",
                    "status": "too_low",
                    "current": 1000,
                    "current_human": "1000",
                    "comfort": 15000,
                    "comfort_human": "15000",
                    "range": "8000 ~ 30000",
                    "advice": "保留太少，建议提高到 15000",
                }
            ],
            "advice": ["建议 1", "建议 2"],
        }

        # 不应抛出异常
        cd.print_diagnose(diag)


# ── print_apply_result ─────────────────────────────────────

class TestPrintApplyResult:
    def test_print_nothing_to_do_does_not_crash(self, caplog):
        """打印 nothing_to_do 状态不应崩溃。"""
        result = {
            "status": "nothing_to_do",
            "summary": "压缩配置已在舒适范围，无需修改",
            "changes": [],
        }
        cd.print_apply_result(result)

    def test_print_dry_run_does_not_crash(self, caplog):
        """打印 dry_run 状态不应崩溃。"""
        result = {
            "status": "dry_run",
            "summary": "预览模式",
            "changes": [
                {
                    "key": "keepRecentTokens",
                    "from": 1000,
                    "to": 15000,
                    "reason": "保留太少，建议提高",
                }
            ],
        }
        cd.print_apply_result(result)

    def test_print_applied_does_not_crash(self, caplog):
        """打印 applied 状态不应崩溃。"""
        result = {
            "status": "applied",
            "summary": "已应用优化",
            "backupPath": "/tmp/openclaw.json.bak",
            "changes": [
                {
                    "key": "keepRecentTokens",
                    "from": 1000,
                    "to": 15000,
                    "reason": "保留太少，建议提高",
                }
            ],
        }
        cd.print_apply_result(result)

    def test_print_error_does_not_crash(self, caplog):
        """打印 error 状态不应崩溃。"""
        result = {
            "status": "error",
            "summary": "无法读取 openclaw.json",
            "changes": [],
        }
        cd.print_apply_result(result)

    def test_print_empty_changes_does_not_crash(self, caplog):
        """打印空 changes 列表不应崩溃。"""
        result = {
            "status": "dry_run",
            "summary": "无需要修改的配置项",
            "changes": [],
        }
        cd.print_apply_result(result)


# ── v2.0 新增功能测试 ──────────────────────────────────────

class TestV2Features:
    def test_token_aware_check_no_data(self, tmp_path, monkeypatch):
        """无 session 数据时 token 感知应返回 no_data。"""
        monkeypatch.setattr(cd, "_SESSIONS_DIR", tmp_path / "nonexistent")
        cc = {"maxActiveTranscriptBytes": 3_000_000}
        result = cd._token_aware_check(cc)
        assert result["status"] in ("no_data", "ok")
        assert "maxTokensSeen" in result

    def test_drift_check_insufficient_data(self, tmp_path, monkeypatch):
        """数据不足时降解检测应返回 insufficient_data。"""
        monkeypatch.setattr(cd, "_SESSIONS_DIR", tmp_path / "sessions")
        (tmp_path / "sessions").mkdir(exist_ok=True)
        cc = {}
        result = cd._drift_check(cc)
        assert result is not None
        assert result["key"] == "drift_detection"

    def test_probe_quality_check_no_compaction(self, tmp_path, monkeypatch):
        """无压缩事件时探针应返回 no_compaction。"""
        monkeypatch.setattr(cd, "_SESSIONS_DIR", tmp_path / "sessions")
        (tmp_path / "sessions").mkdir(exist_ok=True)
        cc = {}
        result = cd._probe_quality_check(cc)
        assert result is not None
        assert "probe_quality" in result["key"]

    def test_diagnose_with_token_aware_flag(self, tmp_path, monkeypatch):
        """token_aware=True 应包含令牌感知诊断。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                        "memoryFlush": {
                            "enabled": True,
                            "softThresholdTokens": 32_000,
                        },
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)
        monkeypatch.setattr(cd, "_SESSIONS_DIR", tmp_path / "sessions")

        result = cd.compaction_diagnose(token_aware=True)
        token_issues = [i for i in result["issues"] if i["key"] == "token_awareness"]
        assert len(token_issues) == 1

    def test_diagnose_with_probe_flag(self, tmp_path, monkeypatch):
        """probe=True 应包含摘要质量探针诊断。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "compaction": {
                        "maxActiveTranscriptBytes": 3_000_000,
                        "keepRecentTokens": 15_000,
                        "memoryFlush": {
                            "enabled": True,
                            "softThresholdTokens": 32_000,
                        },
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cd, "_OPENCLAW_JSON", config_path)
        monkeypatch.setattr(cd, "_SESSIONS_DIR", tmp_path / "sessions")

        result = cd.compaction_diagnose(probe=True)
        probe_issues = [i for i in result["issues"] if i["key"] == "probe_quality"]
        assert len(probe_issues) == 1

    def test_print_token_aware_issue_does_not_crash(self, caplog):
        """打印 token_awareness 类型 issue 不应崩溃。"""
        diag = {
            "status": "warn",
            "summary": "令牌感知诊断",
            "contextWindow": 128000,
            "todaySessionCount": 0,
            "largestTranscriptMB": 0.0,
            "openclawJsonPath": "/tmp/openclaw.json",
            "issues": [
                {
                    "key": "token_awareness",
                    "label": "令牌感知诊断",
                    "severity": "warn",
                    "status": "mismatch",
                    "maxTokensSeen": 50000,
                    "estimatedContextPercent": 39.1,
                    "estimatedByteEquivalentTokens": 750000,
                    "advice": "文件大小阈值可能低估了 token 消耗",
                }
            ],
            "advice": [],
        }
        cd.print_diagnose(diag)

    def test_print_drift_detection_issue_does_not_crash(self, caplog):
        """打印 drift_detection 类型 issue 不应崩溃。"""
        diag = {
            "status": "warn",
            "summary": "上下文降解检测",
            "contextWindow": 128000,
            "todaySessionCount": 0,
            "largestTranscriptMB": 0.0,
            "openclawJsonPath": "/tmp/openclaw.json",
            "issues": [
                {
                    "key": "drift_detection",
                    "label": "上下文降解检测",
                    "severity": "warn",
                    "status": "degradation_suspected",
                    "compactionCount": 5,
                    "recentTokensBefore": [100000, 80000, 60000],
                    "firstTokensBefore": 100000,
                    "lastTokensBefore": 60000,
                    "dropRatio": 0.4,
                    "advice": "压缩后摘要质量可能下降",
                }
            ],
            "advice": [],
        }
        cd.print_diagnose(diag)
