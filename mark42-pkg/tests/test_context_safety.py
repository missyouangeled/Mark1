"""test_context_safety.py - 上下文安全基线模块测试。

覆盖：
- context_safety_status: 状态检查、返回结构
- context_safety_apply: 变更应用、备份机制
- context_safety_verify: 验证逻辑
- 工具函数: _load_openclaw_config, _save_openclaw_config, _ensure_dict, _compare_value
"""

import json
import subprocess
from pathlib import Path

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
        """需要修改时应应用更改并创建备份。

        【2026-08-05 P1-5】apply 默认改为 dry-run，真实写入需显式
        execute_now=True。这里断言的是「需要改时确实能改」这一正确语义，
        因此补上 execute_now=True（而非迁就 dry-run 去弱化断言）。
        """
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
        monkeypatch.setattr(cs, "_validate_candidate_config", lambda c: (True, ""))

        result = cs.context_safety_apply(verbose=False, execute_now=True)

        # 应有变更
        assert len(result["changed"]) > 0
        # 备份文件应存在
        assert result["backup"] is not None
        # 配置文件已修改
        new_config = cs._load_openclaw_config()
        assert new_config["agents"]["defaults"]["contextPruning"]["mode"] == "cache-ttl"
        assert new_config["agents"]["defaults"]["compaction"]["keepRecentTokens"] == 12000

    def test_validate_failure_propagated(self, tmp_path, monkeypatch):
        """验证失败应正确反映到结果中。

        【2026-08-05 P1-5】写入后复验只在 execute_now=True 路径执行，
        故补上该参数；同时 stub 候选预校验为通过，以便专门测试
        「写入后复验失败」这条分支。
        """
        config_path = tmp_path / "openclaw.json"
        config_data = {"agents": {"defaults": {}}}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (False, "validation error"))
        monkeypatch.setattr(cs, "_validate_candidate_config", lambda c: (True, ""))

        result = cs.context_safety_apply(verbose=False, execute_now=True)

        assert result["validateOk"] is False
        assert "validation error" in result["validateOutput"]
        # P1-5：复验失败必须回滚，不能把无效配置留在正式文件里
        assert result["rolledBack"] is True

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


class TestApplyRollbackSafety:
    """P1-5 防回归：非法候选配置永远不能成为最终正式配置。

    历史 bug（实证复现过）：
      1. `_save_openclaw_config(new_config)` 先把新配置**写进正式文件**，
         之后才跑 `openclaw config validate`；
      2. validate 失败只把 `validateOk=False` 塞进返回值；
      3. 备份虽然建了，却从没人用它回滚 —— 无效配置原地留着。
    后果：merge 结果是合法 JSON 但不符 OpenClaw schema 时，Gateway 直接起不来。

    修复后的验收标准（对应方案 P1-5）：
      - 非法候选配置永远不能成为最终正式配置
      - 校验或写入失败后原配置保持可用
      - 回滚失败必须作为独立高严重错误报告
      - 默认 dry-run，真实 apply 必须显式确认
    """

    MARKER = "原始配置不可被破坏"

    def _setup(self, tmp_path, monkeypatch, *, candidate_ok=True, verify_ok=True):
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(
            json.dumps({"agents": {"defaults": {}}, "MARKER": self.MARKER}),
            encoding="utf-8",
        )
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(
            cs, "_validate_candidate_config", lambda c: (candidate_ok, "候选校验")
        )
        monkeypatch.setattr(
            cs, "_run_openclaw_validate", lambda: (verify_ok, "写后复验")
        )
        return config_path

    def _intact(self, config_path):
        """正式配置是否仍是未被改动的原始内容。"""
        data = json.loads(config_path.read_text(encoding="utf-8"))
        untouched = "compaction" not in data.get("agents", {}).get("defaults", {})
        return data.get("MARKER") == self.MARKER and untouched

    def test_apply_defaults_to_dry_run(self, tmp_path, monkeypatch):
        """默认必须是 dry-run —— 不显式确认就不许写盘。"""
        config_path = self._setup(tmp_path, monkeypatch)
        result = cs.context_safety_apply()
        assert result["dryRun"] is True
        assert result["written"] is False
        assert result["changed"], "本用例前提是确实有待变更项"
        assert self._intact(config_path)

    def test_candidate_validate_failure_never_touches_real_config(
        self, tmp_path, monkeypatch
    ):
        """候选预校验失败时，正式配置必须一个字节都没被碰过。"""
        config_path = self._setup(tmp_path, monkeypatch, candidate_ok=False)
        result = cs.context_safety_apply(execute_now=True)
        assert result["validateOk"] is False
        assert result["written"] is False
        assert result["backup"] is None, "既然没写，就不该产生备份"
        assert self._intact(config_path)

    def test_post_write_validate_failure_rolls_back(self, tmp_path, monkeypatch):
        """预校验通过但写后复验失败 -> 必须回滚，原配置保持可用。"""
        config_path = self._setup(tmp_path, monkeypatch, verify_ok=False)
        result = cs.context_safety_apply(execute_now=True)
        assert result["written"] is True
        assert result["validateOk"] is False
        assert result["rolledBack"] is True
        assert self._intact(config_path), "回滚后必须恢复成原始配置"

    def test_successful_apply_writes_config(self, tmp_path, monkeypatch):
        """两道校验都过时必须真正落盘（不能因为加了保护就写不进去）。"""
        config_path = self._setup(tmp_path, monkeypatch)
        result = cs.context_safety_apply(execute_now=True)
        assert result["written"] is True
        assert result["validateOk"] is True
        assert result["rolledBack"] is False
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert "compaction" in data["agents"]["defaults"]

    def test_rollback_failure_is_reported_as_severe(self, tmp_path, monkeypatch):
        """回滚本身失败时，必须作为独立高严重错误上报，不能静默。"""
        self._setup(tmp_path, monkeypatch, verify_ok=False)
        monkeypatch.setattr(
            cs, "_restore_openclaw_config", lambda b: (False, "磁盘只读")
        )
        result = cs.context_safety_apply(execute_now=True)
        assert result["rolledBack"] is False
        assert result["rollbackFailed"] is True
        assert "磁盘只读" in result["rollbackNote"]

    def test_backup_created_before_write(self, tmp_path, monkeypatch):
        """真实写入前必须留下可用备份。"""
        self._setup(tmp_path, monkeypatch)
        result = cs.context_safety_apply(execute_now=True)
        backup = Path(result["backup"])
        assert backup.exists()
        # 备份内容必须是**写入前**的原始配置
        assert json.loads(backup.read_text(encoding="utf-8"))["MARKER"] == self.MARKER

    def test_no_changes_skips_write_entirely(self, tmp_path, monkeypatch):
        """无变更时不应备份、不应写入。"""
        self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(cs, "_merge_context_safety_patch", lambda c: (c, []))
        result = cs.context_safety_apply(execute_now=True)
        assert result["changed"] == []
        assert result["written"] is False
        assert result["backup"] is None

    def test_restore_helper_recovers_content(self, tmp_path, monkeypatch):
        """_restore_openclaw_config 必须真的把内容写回去。"""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(json.dumps({"broken": True}), encoding="utf-8")
        backup = tmp_path / "backup.bak"
        backup.write_text(json.dumps({"MARKER": self.MARKER}), encoding="utf-8")
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)

        ok, note = cs._restore_openclaw_config(backup)
        assert ok is True
        assert json.loads(config_path.read_text(encoding="utf-8"))["MARKER"] == (
            self.MARKER
        )
        assert backup.name in note

    def test_restore_helper_reports_missing_backup(self, tmp_path, monkeypatch):
        """备份不存在时必须明确失败，不能假装回滚成功。"""
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", tmp_path / "openclaw.json")
        ok, note = cs._restore_openclaw_config(tmp_path / "no-such.bak")
        assert ok is False
        assert "不存在" in note

    def test_candidate_validate_ignores_unrelated_cli_failure(
        self, tmp_path, monkeypatch
    ):
        """CLI 没读到临时文件时，不得把环境问题误判成 schema 非法。

        否则测试环境或缺省配置的机器上，正常 apply 会被永久堵死。
        """
        monkeypatch.setattr(cs, "OPENCLAW_BIN", "/bin/false")
        ok, output = cs._validate_candidate_config({"agents": {}})
        assert ok is True, "预校验不可用时应降级放行，交由写入后复验兜底"
        assert output == ""


class TestConcurrentWriteSafety:
    """P2-6 防回归：不得基于锁外快照整份覆盖，静默吃掉并发写入。

    历史 bug（两处，均实证复现）：
      - `context_safety_apply` 与 `compaction_apply` 都在**锁外**读配置快照，
        锁只包住最后一步写入，中间隔着整个 diagnose/merge 过程；
      - 并发时会拿陈旧快照整份覆盖，静默吃掉别人
        （另一个 Mark42 模块 / Control UI / 用户）刚写的字段。
      - `compaction_diag` 的原注释已经指出这个风险，但代码并未解决。

    修复：写入统一走 `patch_openclaw_config(mutate=...)`，
    该原语在**锁内重读**最新配置后才执行 mutator。
    """

    MARKER_KEY = "USER_CONCURRENT_EDIT"

    def _make_config(self, tmp_path):
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(
            json.dumps({"agents": {"defaults": {}}}), encoding="utf-8"
        )
        return config_path

    def test_apply_preserves_field_written_after_snapshot(
        self, tmp_path, monkeypatch
    ):
        """A 读快照后 B 写入新字段 -> A 落盘不得吃掉该字段。"""
        config_path = self._make_config(tmp_path)
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_validate_candidate_config", lambda c: (True, ""))
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, "ok"))

        real_load = cs._load_openclaw_config

        def load_then_concurrent_write():
            snapshot = real_load()
            # 模拟另一个进程在 A 读完快照之后写入
            live = json.loads(config_path.read_text(encoding="utf-8"))
            live[self.MARKER_KEY] = "并发写入的重要设置"
            config_path.write_text(json.dumps(live), encoding="utf-8")
            return snapshot

        monkeypatch.setattr(cs, "_load_openclaw_config", load_then_concurrent_write)

        result = cs.context_safety_apply(execute_now=True)
        after = json.loads(config_path.read_text(encoding="utf-8"))

        assert result["written"] is True
        # A 自己的基线仍要生效
        assert "compaction" in after["agents"]["defaults"]
        # 且不能吃掉 B 的字段
        assert self.MARKER_KEY in after, "锁外快照整份覆盖，吃掉了并发写入"

    def test_apply_recomputes_changes_inside_lock(self, tmp_path, monkeypatch):
        """mutator 必须在锁内拿到的**最新**配置上重算，而非复用快照结果。"""
        config_path = self._make_config(tmp_path)
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_validate_candidate_config", lambda c: (True, ""))
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, "ok"))

        seen: list[dict] = []
        real_merge = cs._merge_context_safety_patch

        def spy_merge(config):
            seen.append(config)
            return real_merge(config)

        monkeypatch.setattr(cs, "_merge_context_safety_patch", spy_merge)
        cs.context_safety_apply(execute_now=True)

        # 至少两次：一次算快照（供 dry-run 预览/预校验），一次在锁内重算
        assert len(seen) >= 2, "写入路径必须在锁内重新 merge 一次"

    def test_nothing_to_do_when_peer_already_aligned(self, tmp_path, monkeypatch):
        """锁内重读发现别人已对齐好基线时，应报 nothing_to_do 而非重复写。"""
        config_path = self._make_config(tmp_path)
        monkeypatch.setattr(cs, "OPENCLAW_CONFIG", config_path)
        monkeypatch.setattr(cs, "_validate_candidate_config", lambda c: (True, ""))
        monkeypatch.setattr(cs, "_run_openclaw_validate", lambda: (True, "ok"))

        # 锁内 merge 时假装已无变更（等价于别的进程刚对齐完）
        calls = {"n": 0}
        real_merge = cs._merge_context_safety_patch

        def merge_then_empty(config):
            calls["n"] += 1
            if calls["n"] == 1:
                return real_merge(config)  # 快照阶段仍报有变更
            return config, []              # 锁内重算：已无需修改

        monkeypatch.setattr(cs, "_merge_context_safety_patch", merge_then_empty)
        result = cs.context_safety_apply(execute_now=True)

        assert result["changed"] == []
        assert result["written"] is False
