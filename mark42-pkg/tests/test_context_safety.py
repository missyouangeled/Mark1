"""test_context_safety.py - 上下文安全基线模块测试。

覆盖：
- context_safety_status: 状态检查、返回结构
- context_safety_apply: 变更应用、备份机制
- context_safety_verify: 验证逻辑
- 工具函数: _load_openclaw_config, _save_openclaw_config, _ensure_dict, _compare_value
"""

import json
import subprocess

import pytest

from mark42 import context_safety as cs

# ── 工具函数测试 ───────────────────────────────────────────


class TestUtilityFunctions:
    def test_ensure_dict_creates_when_missing(self):
        """字典路径不存在时应创建。"""
        parent = {}
        result = cs._ensure_dict(parent, "agents")
        assert result == {}
        assert parent["agents"] == {}

    def test_ensure_dict_returns_existing(self):
        """字典路径存在时应返回原值。"""
        parent = {"agents": {"defaults": {"compaction": {}}}}
        result = cs._ensure_dict(parent, "agents")
        assert result is parent["agents"]

    def test_ensure_dict_overwrites_non_dict(self):
        """如果已有非字典值，应覆盖为空字典。"""
        parent = {"agents": "not_a_dict"}
        result = cs._ensure_dict(parent, "agents")
        assert result == {}
        assert parent["agents"] == {}

    def test_compare_value_simple(self):
        """简单值比较。"""
        assert cs._compare_value(1, 1) is True
        assert cs._compare_value("a", "a") is True
        assert cs._compare_value(True, True) is True
        assert cs._compare_value(1, 2) is False
        assert cs._compare_value(None, None) is True

    def test_compare_value_nested(self):
        """嵌套字典比较（测试 baseline 逻辑）。"""
        assert cs._compare_value({"a": 1}, {"a": 1}) is True
        assert cs._compare_value({"a": 1}, {"a": 2}) is False


# ── _load_openclaw_config / _save_openclaw_config ──────────


class TestConfigLoadSave:
    def test_load_nonexistent_raises(self, tmp_path, monkeypatch):
        """配置文件不存在应抛出 FileNotFoundError。"""
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", tmp_path / "nonexistent.json")
        with pytest.raises(FileNotFoundError):
            cs._load_openclaw_config()

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        """保存后应能正确加载。"""
        config_path = tmp_path / "openclaw.json"
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)

        data = {"agents": {"defaults": {"compaction": {"model": "test-model"}}}}
        cs._save_openclaw_config(data)
        loaded = cs._load_openclaw_config()
        assert loaded == data

    def test_save_uses_indent_and_ascii_false(self, tmp_path, monkeypatch):
        """保存格式应正确：缩进 + 中文不转义。"""
        config_path = tmp_path / "openclaw.json"
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)

        data = {"name": "上下文铠甲"}
        cs._save_openclaw_config(data)
        content = config_path.read_text(encoding="utf-8")
        assert "  " in content  # 缩进
        assert "上下文铠甲" in content  # 中文原样
        assert content.endswith("\n")  # 末尾换行


# ── context_safety_status ──────────────────────────────────


class TestContextSafetyStatus:
    def test_returns_correct_structure(self, tmp_path, monkeypatch):
        """status 应返回正确结构：checks, summary, checkedAt。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "contextPruning": cs.CONTEXT_PRUNING_BASELINE.copy(),
                    "compaction": {
                        **cs.COMPACTION_BASELINE,
                        "memoryFlush": cs.MEMORY_FLUSH_BASELINE.copy(),
                    },
                }
            },
            "session": {
                "maintenance": cs.SESSION_MAINTENANCE_BASELINE.copy(),
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")

        result = cs.context_safety_status(verbose=False)

        assert "checks" in result
        assert "summary" in result
        assert "checkedAt" in result
        assert isinstance(result["checks"], list)
        assert isinstance(result["summary"], dict)

    def test_perfect_config_all_pass(self, tmp_path, monkeypatch):
        """完美配置所有检查应通过。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "contextPruning": cs.CONTEXT_PRUNING_BASELINE.copy(),
                    "compaction": {
                        **cs.COMPACTION_BASELINE,
                        "memoryFlush": cs.MEMORY_FLUSH_BASELINE.copy(),
                    },
                }
            },
            "session": {
                "maintenance": cs.SESSION_MAINTENANCE_BASELINE.copy(),
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")

        result = cs.context_safety_status(verbose=False)

        # 所有 baseline 检查应通过
        for check in result["checks"]:
            if check["severity"] != "info":  # info 是当前 session 信息，不算 pass
                assert check["ok"] is True, f"Check failed: {check['name']}"

    def test_missing_config_triggers_warn(self, tmp_path, monkeypatch):
        """缺失配置应触发 warn。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}  # 几乎空配置
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")

        result = cs.context_safety_status(verbose=False)

        # 应有 warn 项
        assert result["summary"]["warn"] > 0

    def test_verbose_mode_does_not_crash(self, tmp_path, monkeypatch):
        """verbose=True 不应崩溃。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")

        # 不应抛出异常
        result = cs.context_safety_status(verbose=True)
        assert result is not None

    def test_session_override_info_check(self, tmp_path, monkeypatch):
        """应包含当前 session override 的 info 检查。"""
        config_path = tmp_path / "openclaw.json"
        sessions_path = tmp_path / "sessions.json"

        config_data = {"agents": {"defaults": {}}}
        sessions_data = {
            "agent:main:main": {
                "modelOverride": "test-model",
                "providerOverride": "test-provider",
            }
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        with open(sessions_path, "w", encoding="utf-8") as f:
            json.dump(sessions_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", sessions_path)

        result = cs.context_safety_status(verbose=False)

        # 找到 info 类型的检查
        info_checks = [c for c in result["checks"] if c["name"] == "currentSession.modelOverride"]
        assert len(info_checks) == 1
        assert info_checks[0]["severity"] == "info"


# ── context_safety_apply ───────────────────────────────────


class TestContextSafetyApply:
    def test_returns_correct_structure(self, tmp_path, monkeypatch):
        """apply 应返回正确结构：backup, changed, validateOk, validateOutput, appliedAt。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "contextPruning": cs.CONTEXT_PRUNING_BASELINE.copy(),
                    "compaction": {
                        **cs.COMPACTION_BASELINE,
                        "memoryFlush": cs.MEMORY_FLUSH_BASELINE.copy(),
                    },
                }
            },
            "session": {
                "maintenance": cs.SESSION_MAINTENANCE_BASELINE.copy(),
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, ""))

        result = cs.context_safety_apply(verbose=False)

        assert "backup" in result
        assert "changed" in result
        assert "validateOk" in result
        assert "validateOutput" in result
        assert "appliedAt" in result

    def test_no_changes_when_already_perfect(self, tmp_path, monkeypatch):
        """已完美配置时 changed 应为空列表，backup 为 None。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "contextPruning": cs.CONTEXT_PRUNING_BASELINE.copy(),
                    "compaction": {
                        "mode": "safeguard",
                        **cs.COMPACTION_BASELINE,
                        "memoryFlush": {
                            **cs.MEMORY_FLUSH_BASELINE.copy(),
                            "prompt": cs.DEFAULT_MEMORY_FLUSH_PROMPT,
                            "systemPrompt": cs.DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT,
                        },
                    },
                }
            },
            "session": {
                "maintenance": cs.SESSION_MAINTENANCE_BASELINE.copy(),
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, ""))

        result = cs.context_safety_apply(verbose=False)

        assert result["changed"] == []
        assert result["backup"] is None

    def test_applies_changes_when_needed(self, tmp_path, monkeypatch):
        """需要修改时应应用更改并创建备份。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "contextPruning": {"mode": "old-mode"},  # 错误值
                    "compaction": {"keepRecentTokens": 100},  # 错误值
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, ""))

        result = cs.context_safety_apply(verbose=False)

        # 应有变更
        assert len(result["changed"]) > 0
        # 备份文件应存在
        assert result["backup"] is not None
        # 配置文件已修改
        new_config = cs._load_openclaw_config()
        assert new_config["agents"]["defaults"]["contextPruning"]["mode"] == "cache-ttl"
        assert new_config["agents"]["defaults"]["compaction"]["keepRecentTokens"] == 12000

    def test_validate_failure_propagated(self, tmp_path, monkeypatch):
        """验证失败应正确反映到结果中。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (False, "validation error"))

        result = cs.context_safety_apply(verbose=False)

        assert result["validateOk"] is False
        assert "validation error" in result["validateOutput"]

    def test_verbose_mode_does_not_crash(self, tmp_path, monkeypatch):
        """verbose=True 不应崩溃。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, ""))

        # 不应抛出异常
        result = cs.context_safety_apply(verbose=True)
        assert result is not None


# ── context_safety_verify ──────────────────────────────────


class TestContextSafetyVerify:
    def test_verify_returns_zero_on_perfect_config(self, tmp_path, monkeypatch):
        """完美配置 + validate 通过 + smoke 通过 应返回 0。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {
            "agents": {
                "defaults": {
                    "contextPruning": cs.CONTEXT_PRUNING_BASELINE.copy(),
                    "compaction": {
                        "mode": "safeguard",
                        **cs.COMPACTION_BASELINE,
                        "memoryFlush": {
                            **cs.MEMORY_FLUSH_BASELINE.copy(),
                            "prompt": cs.DEFAULT_MEMORY_FLUSH_PROMPT,
                            "systemPrompt": cs.DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT,
                        },
                    },
                }
            },
            "session": {
                "maintenance": cs.SESSION_MAINTENANCE_BASELINE.copy(),
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        # mock 所有外部依赖
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")
        monkeypatch.setattr(cs, "TOOL_CHECK_FILE", tmp_path / "tool-check.txt")
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, ""))

        # 创建工具检查文件
        (tmp_path / "tool-check.txt").write_text("ok")

        # mock curl 检查
        def mock_subprocess_run(cmd, *args, **kwargs):
            class MockResult:
                returncode = 0
                stdout = b"OpenClaw"

            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        result = cs.context_safety_verify(verbose=False)
        assert result == 0

    def test_verify_returns_one_on_validate_fail(self, tmp_path, monkeypatch):
        """验证失败应返回 1。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (False, "error"))

        result = cs.context_safety_verify(verbose=False)
        assert result == 1

    def test_verify_returns_zero_on_warn_only(self, tmp_path, monkeypatch):
        """只有 warn 没有 fail 时应返回 0（verify 只检查 fail 级别）。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}  # 空配置，会有很多 warn 但没有 fail
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, ""))

        # 让 smoke 检查也通过
        monkeypatch.setattr(cs, "_run_light_smoke_checks", lambda: (True, []))

        result = cs.context_safety_verify(verbose=False)
        assert result == 0  # warn 不触发失败，只有 fail 才会

    def test_verbose_mode_does_not_crash(self, tmp_path, monkeypatch):
        """verbose=True 不应崩溃。"""
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "SESSIONS_STORE", tmp_path / "sessions.json")
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, ""))
        monkeypatch.setattr(cs, "_run_light_smoke_checks", lambda: (True, []))

        # 不应抛出异常
        result = cs.context_safety_verify(verbose=True)
        assert result is not None


# ── _run_light_smoke_checks ────────────────────────────────


class TestSmokeChecks:
    def test_all_checks_pass(self, tmp_path, monkeypatch):
        """所有 smoke 检查通过的情况。"""
        monkeypatch.setattr(cs, "TOOL_CHECK_FILE", tmp_path / "tool-check.txt")
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", tmp_path / "openclaw.json")

        (tmp_path / "tool-check.txt").write_text("ok")
        (tmp_path / "openclaw.json").write_text("{}")

        def mock_subprocess_run(cmd, *args, **kwargs):
            class MockResult:
                returncode = 0
                stdout = b"OpenClaw"

            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        ok, lines = cs._run_light_smoke_checks()
        assert ok is True
        assert len(lines) >= 3  # 至少 3 项检查

    def test_missing_tool_check_file(self, tmp_path, monkeypatch):
        """缺少工具检查文件应失败。"""
        monkeypatch.setattr(cs, "TOOL_CHECK_FILE", tmp_path / "nonexistent.txt")
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", tmp_path / "openclaw.json")

        (tmp_path / "openclaw.json").write_text("{}")

        def mock_subprocess_run(cmd, *args, **kwargs):
            class MockResult:
                returncode = 0
                stdout = b"OpenClaw"

            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        ok, lines = cs._run_light_smoke_checks()
        assert ok is False

    def test_web_fetch_failure(self, tmp_path, monkeypatch):
        """web_fetch 失败应导致整体失败。"""
        monkeypatch.setattr(cs, "TOOL_CHECK_FILE", tmp_path / "tool-check.txt")
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", tmp_path / "openclaw.json")

        (tmp_path / "tool-check.txt").write_text("ok")
        (tmp_path / "openclaw.json").write_text("{}")

        def mock_subprocess_run(cmd, *args, **kwargs):
            class MockResult:
                returncode = 1
                stdout = b""

            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        ok, lines = cs._run_light_smoke_checks()
        assert ok is False
