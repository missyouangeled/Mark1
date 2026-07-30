"""
context_safety.py 单元测试

测试覆盖:
- 上下文安全检查逻辑
- 敏感信息检测（如果有）
- 安全策略执行
- 所有公开函数
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# 导入待测试模块
from mark42.context_safety import (
    context_safety_status,
    context_safety_apply,
    context_safety_verify,
    _compare_value,
    _ensure_dict,
    _get_current_session_override,
    _run_light_smoke_checks,
    _run_openclaw_validate,
    DEFAULT_MEMORY_FLUSH_PROMPT,
    DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT,
    CONTEXT_PRUNING_BASELINE,
)


class TestHelperFunctions:
    """测试辅助函数"""

    def test_compare_value_equal(self):
        """测试比较相等的值"""
        assert _compare_value(1, 1) is True
        assert _compare_value("test", "test") is True
        assert _compare_value([1, 2], [1, 2]) is True

    def test_compare_value_not_equal(self):
        """测试比较不相等的值"""
        assert _compare_value(1, 2) is False
        assert _compare_value("test", "Test") is False

    def test_ensure_dict_existing_dict(self):
        """测试已有 dict 时直接返回"""
        parent = {"key": {"subkey": "value"}}
        result = _ensure_dict(parent, "key")
        assert result == {"subkey": "value"}

    def test_ensure_dict_not_dict(self):
        """测试值不是 dict 时创建新 dict"""
        parent = {"key": "not a dict"}
        result = _ensure_dict(parent, "key")
        assert result == {}
        assert parent["key"] == {}

    def test_ensure_dict_missing_key(self):
        """测试 key 不存在时创建新 dict"""
        parent = {}
        result = _ensure_dict(parent, "newkey")
        assert result == {}
        assert parent["newkey"] == {}

    def test_get_current_session_override_nonexistent_file(self):
        """测试 sessions.json 不存在时返回空 dict"""
        with patch.object(Path, "exists", return_value=False):
            result = _get_current_session_override()
        assert result == {}

    def test_get_current_session_override_invalid_json(self):
        """测试 sessions.json JSON 无效时返回空 dict"""
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid json")):
                result = _get_current_session_override()
        assert result == {}

    def test_get_current_session_override_no_current_session(self):
        """测试没有当前会话时返回带 None 值的 dict（因为默认值是 {}）"""
        # sessions.json 存在但没有 agent:main:main 这个 key
        # .get(key, {}) 会返回默认 {}，dict.get() 对不存在的键返回 None
        with patch.object(Path, "exists", return_value=True):
            mo = mock_open(read_data='{"some_other_key": {"model": "test"}}')
            with patch("builtins.open", mo):
                result = _get_current_session_override()
        # 因为默认是 {}，dict.get() 对不存在的键返回 None
        assert result == {
            "modelOverride": None,
            "providerOverride": None,
            "modelOverrideSource": None,
        }

    def test_get_current_session_override_with_data(self):
        """测试有会话数据时返回正确的 override"""
        with patch.object(Path, "exists", return_value=True):
            mo = mock_open(read_data='{"agent:main:main": {"modelOverride": "gpt-4", "providerOverride": "openai", "modelOverrideSource": "user"}}')
            with patch("builtins.open", mo):
                result = _get_current_session_override()
        assert result == {
            "modelOverride": "gpt-4",
            "providerOverride": "openai",
            "modelOverrideSource": "user",
        }


class TestContextSafetyStatus:
    """测试 context_safety_status 函数"""

    def test_status_loads_config(self, mocker):
        """测试状态检查加载配置"""
        # mock 配置文件存在
        with patch.object(Path, "exists", return_value=True):
            # 符合基线的配置
            baseline_config = {
                "agents": {
                    "defaults": {
                        "contextPruning": CONTEXT_PRUNING_BASELINE.copy(),
                        "compaction": {
                            "truncateAfterCompaction": True,
                            "keepRecentTokens": 12000,
                            "maxHistoryShare": 0.4,
                            "model": "litellm/agnes-2.0-flash",
                            "memoryFlush": {
                                "enabled": True,
                                "softThresholdTokens": 15000,
                                "model": "litellm/agnes-2.0-flash",
                            }
                        }
                    }
                },
                "session": {
                    "maintenance": {
                        "mode": "enforce",
                        "pruneAfter": "14d",
                        "maxEntries": 120,
                    }
                }
            }
            
            with patch("mark42.context_safety.open", mock_open()):
                with patch("json.load", return_value=baseline_config):
                    # mock _get_current_session_override
                    mocker.patch("mark42.context_safety._get_current_session_override", return_value={})
                    # mock print to avoid clutter
                    mocker.patch("builtins.print")
                    
                    result = context_safety_status(verbose=False)
        
        assert "checks" in result
        assert "summary" in result
        assert "checkedAt" in result

    def test_status_config_not_found(self, mocker):
        """测试配置文件不存在时抛出异常"""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                context_safety_status()

    def test_status_with_failing_checks(self, mocker):
        """测试部分检查失败时的情况"""
        with patch.object(Path, "exists", return_value=True):
            # 不符合基线的配置
            bad_config = {
                "agents": {
                    "defaults": {
                        "contextPruning": {
                            "mode": "disabled",  # 不符合
                        },
                        "compaction": {
                            "truncateAfterCompaction": False,  # 不符合
                        }
                    }
                }
            }
            
            with patch("mark42.context_safety.open", mock_open()):
                with patch("json.load", return_value=bad_config):
                    mocker.patch("mark42.context_safety._get_current_session_override", return_value={})
                    mocker.patch("builtins.print")
                    
                    result = context_safety_status()
        
        # 应该有失败的检查
        checks = result["checks"]
        any_failed = any(not c["ok"] for c in checks)
        assert any_failed is True


class TestContextSafetyApply:
    """测试 context_safety_apply 函数"""

    def test_apply_no_changes_needed(self, mocker):
        """测试配置已经符合基线时不修改"""
        with patch.object(Path, "exists", return_value=True):
            # 已经完全符合基线的配置
            fully_compliant_config = {
                "agents": {
                    "defaults": {
                        "contextPruning": CONTEXT_PRUNING_BASELINE.copy(),
                        "compaction": {
                            "mode": "safeguard",
                            "truncateAfterCompaction": True,
                            "keepRecentTokens": 12000,
                            "maxHistoryShare": 0.4,
                            "model": "litellm/agnes-2.0-flash",
                            "memoryFlush": {
                                "enabled": True,
                                "softThresholdTokens": 15000,
                                "model": "litellm/agnes-2.0-flash",
                                "prompt": DEFAULT_MEMORY_FLUSH_PROMPT,
                                "systemPrompt": DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT,
                            }
                        }
                    }
                },
                "session": {
                    "maintenance": {
                        "mode": "enforce",
                        "pruneAfter": "14d",
                        "maxEntries": 120,
                    }
                }
            }
            
            with patch("mark42.context_safety.open", mock_open()):
                with patch("json.load", return_value=fully_compliant_config):
                    with patch("json.dump"):
                        # mock validate
                        mocker.patch("mark42.context_safety._run_openclaw_validate", return_value=(True, ""))
                        mocker.patch("builtins.print")
                        # mock backup not called
                        mock_backup = mocker.patch("mark42.context_safety._backup_openclaw_config")
                        
                        result = context_safety_apply()
        
        # 没有变更，不应该备份
        mock_backup.assert_not_called()
        assert result["changed"] == []

    def test_apply_makes_changes(self, mocker):
        """测试配置不符合基线时进行修改"""
        with patch.object(Path, "exists", return_value=True):
            # 空配置，所有项都需要修改
            empty_config = {}
            
            with patch("mark42.context_safety.open", mock_open()):
                with patch("json.load", return_value=empty_config):
                    with patch("json.dump"):
                        mocker.patch("mark42.context_safety._run_openclaw_validate", return_value=(True, ""))
                        mocker.patch("builtins.print")
                        mock_backup = mocker.patch("mark42.context_safety._backup_openclaw_config")
                        
                        result = context_safety_apply()
        
        # 应该有变更和备份
        mock_backup.assert_called_once()
        assert len(result["changed"]) > 0

    def test_apply_validates_after_change(self, mocker):
        """测试修改后执行验证"""
        with patch.object(Path, "exists", return_value=True):
            empty_config = {}
            
            with patch("mark42.context_safety.open", mock_open()):
                with patch("json.load", return_value=empty_config):
                    with patch("json.dump"):
                        mock_validate = mocker.patch(
                            "mark42.context_safety._run_openclaw_validate",
                            return_value=(True, "validated")
                        )
                        mocker.patch("builtins.print")
                        mocker.patch("mark42.context_safety._backup_openclaw_config")
                        
                        result = context_safety_apply()
        
        mock_validate.assert_called_once()
        assert result["validateOk"] is True
        assert result["validateOutput"] == "validated"

    def test_apply_failed_validation(self, mocker):
        """测试验证失败时的返回"""
        with patch.object(Path, "exists", return_value=True):
            empty_config = {}
            
            with patch("mark42.context_safety.open", mock_open()):
                with patch("json.load", return_value=empty_config):
                    with patch("json.dump"):
                        mocker.patch(
                            "mark42.context_safety._run_openclaw_validate",
                            return_value=(False, "validation failed")
                        )
                        mocker.patch("builtins.print")
                        mocker.patch("mark42.context_safety._backup_openclaw_config")
                        
                        result = context_safety_apply()
        
        assert result["validateOk"] is False


class TestContextSafetyVerify:
    """测试 context_safety_verify 函数"""

    def test_verify_all_passes(self, mocker):
        """测试所有检查通过时返回 0"""
        # mock status 检查全部通过
        mock_status = mocker.patch("mark42.context_safety.context_safety_status")
        mock_status.return_value = {"summary": {"pass": 20, "warn": 0, "fail": 0}}
        
        # mock validate 通过
        mocker.patch(
            "mark42.context_safety._run_openclaw_validate",
            return_value=(True, "")
        )
        
        # mock smoke checks 通过
        mocker.patch(
            "mark42.context_safety._run_light_smoke_checks",
            return_value=(True, [])
        )
        
        mocker.patch("builtins.print")
        
        result = context_safety_verify()
        
        assert result == 0

    def test_verify_validation_fails(self, mocker):
        """测试验证失败时返回非 0"""
        mock_status = mocker.patch("mark42.context_safety.context_safety_status")
        mock_status.return_value = {"summary": {"pass": 20, "warn": 0, "fail": 0}}
        
        # validate 失败
        mocker.patch(
            "mark42.context_safety._run_openclaw_validate",
            return_value=(False, "failed")
        )
        
        mocker.patch(
            "mark42.context_safety._run_light_smoke_checks",
            return_value=(True, [])
        )
        
        mocker.patch("builtins.print")
        
        result = context_safety_verify()
        
        assert result == 1

    def test_verify_status_has_fails(self, mocker):
        """测试状态检查有失败时返回非 0"""
        mock_status = mocker.patch("mark42.context_safety.context_safety_status")
        mock_status.return_value = {"summary": {"pass": 15, "warn": 3, "fail": 2}}
        
        mocker.patch(
            "mark42.context_safety._run_openclaw_validate",
            return_value=(True, "")
        )
        
        mocker.patch(
            "mark42.context_safety._run_light_smoke_checks",
            return_value=(True, [])
        )
        
        mocker.patch("builtins.print")
        
        result = context_safety_verify()
        
        assert result == 1

    def test_verify_smoke_fails(self, mocker):
        """测试冒烟检查失败时返回非 0"""
        mock_status = mocker.patch("mark42.context_safety.context_safety_status")
        mock_status.return_value = {"summary": {"pass": 20, "warn": 0, "fail": 0}}
        
        mocker.patch(
            "mark42.context_safety._run_openclaw_validate",
            return_value=(True, "")
        )
        
        # smoke 失败
        mocker.patch(
            "mark42.context_safety._run_light_smoke_checks",
            return_value=(False, ["FAIL: something went wrong"])
        )
        
        mocker.patch("builtins.print")
        
        result = context_safety_verify()
        
        assert result == 1


class TestSmokeChecks:
    """测试 _run_light_smoke_checks 冒烟检查"""

    def test_smoke_all_pass(self, mocker):
        """测试所有冒烟检查通过"""
        # mock read_text for tool-check file
        def mock_read_text(self, encoding=None):
            return "tool check ok"
        
        # 使用 side_effect 来模拟 exists
        def mock_exists(self):
            return True
            
        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                mock_curl = MagicMock()
                mock_curl.returncode = 0
                mock_curl.stdout = b"<html>OpenClaw Documentation</html>"
                mocker.patch("subprocess.run", return_value=mock_curl)
                
                ok, lines = _run_light_smoke_checks()
        
        assert ok is True

    def test_smoke_tool_file_missing(self, mocker):
        """测试工具检查文件缺失"""
        # 区分不同路径的存在性
        def mock_exists(self):
            if "tool-check" in str(self):
                return False  # tool file missing
            return True  # config exists
        
        with patch.object(Path, "exists", mock_exists):
            mock_curl = MagicMock()
            mock_curl.returncode = 0
            mock_curl.stdout = b"OpenClaw"
            mocker.patch("subprocess.run", return_value=mock_curl)
            
            ok, lines = _run_light_smoke_checks()
        
        assert ok is False

    def test_smoke_config_missing(self, mocker):
        """测试配置文件缺失"""
        def mock_exists(self):
            if "tool-check" in str(self):
                return True
            if "openclaw.json" in str(self):
                return False  # config missing
            return True
        
        def mock_read_text(self, encoding=None):
            return "ok"
        
        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                mock_curl = MagicMock()
                mock_curl.returncode = 0
                mock_curl.stdout = b"OpenClaw"
                mocker.patch("subprocess.run", return_value=mock_curl)
                
                ok, lines = _run_light_smoke_checks()
        
        assert ok is False

    def test_smoke_curl_fails(self, mocker):
        """测试 curl 失败"""
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value="ok"):
                mock_curl = MagicMock()
                mock_curl.returncode = 1  # failed
                mock_curl.stdout = b""
                mocker.patch("subprocess.run", return_value=mock_curl)
                
                ok, lines = _run_light_smoke_checks()
        
        assert ok is False

    def test_smoke_curl_wrong_content(self, mocker):
        """测试 curl 返回内容不含 OpenClaw"""
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value="ok"):
                mock_curl = MagicMock()
                mock_curl.returncode = 0
                mock_curl.stdout = b"Other content without the keyword"
                mocker.patch("subprocess.run", return_value=mock_curl)
                
                ok, lines = _run_light_smoke_checks()
        
        assert ok is False


class TestOpenclawValidate:
    """测试 _run_openclaw_validate 配置验证"""

    def test_validate_success(self, mocker):
        """测试验证成功"""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Config is valid"
        mock_proc.stderr = ""
        mocker.patch("subprocess.run", return_value=mock_proc)
        
        ok, output = _run_openclaw_validate()
        
        assert ok is True
        assert "Config is valid" in output

    def test_validate_failure(self, mocker):
        """测试验证失败"""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Validation error"
        mocker.patch("subprocess.run", return_value=mock_proc)
        
        ok, output = _run_openclaw_validate()
        
        assert ok is False
        assert "Validation error" in output
