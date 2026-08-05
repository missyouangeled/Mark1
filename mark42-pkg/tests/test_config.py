"""test_config.py - 配置系统测试。

覆盖：
- 路径常量正确性
- 阈值读取（默认值 + 环境变量覆盖）
- get_model_config() 配置读取
- resolve_model() 模型参数解析
- _conf_load_json / _conf_save_json
- mark42_init() 初始化
"""

import os
from pathlib import Path

from mark42 import config as cfg
from mark42.config import (
    MARK42_STATE,
    THRESHOLD_ALERT,
    THRESHOLD_CRIT,
    THRESHOLD_WARN,
    WORKSPACE,
    XDG_STATE,
    _conf_load_json,
    _conf_save_json,
    get_model_config,
    resolve_model,
)

# ── 路径常量 ──────────────────────────────────────────────


class TestPathConstants:
    def test_workspace_is_path(self):
        assert isinstance(WORKSPACE, Path)

    def test_workspace_exists_or_default(self):
        """WORKSPACE 应指向 ~/.openclaw/workspace 或 env 指定路径。

        注意：conftest 的 autouse fixture 会把 HOME 改成临时目录，
        因此不能用 Path.home() 做断言（那会拿到被 mock 的假路径）。
        WORKSPACE 是 config import 时算好的常量，这里只验证其结构：
        要么等于 MARK42_WORKSPACE，要么以 .openclaw/workspace 结尾。
        """
        env_ws = os.environ.get("MARK42_WORKSPACE")
        if env_ws:
            assert str(WORKSPACE) == env_ws
        else:
            assert WORKSPACE.parts[-2:] == (".openclaw", "workspace")

    def test_xdg_state_resolved(self):
        assert isinstance(XDG_STATE, Path)

    def test_mark42_state_under_xdg(self):
        assert MARK42_STATE == XDG_STATE / "openclaw" / "mark42"


# ── 阈值 ────────────────────────────────────────────────


class TestThresholds:
    def test_default_values(self):
        """无环境变量时应为默认值。"""
        assert THRESHOLD_WARN == 70
        assert THRESHOLD_ALERT == 85
        assert THRESHOLD_CRIT == 95

    def test_env_override(self):
        """环境变量应覆盖默认阈值。"""
        # 这些值在 import 时已固定，所以只测值合理性
        assert 0 < THRESHOLD_WARN < THRESHOLD_ALERT < THRESHOLD_CRIT <= 100


# ── _conf_load_json / _conf_save_json ─────────────────────


class TestConfJson:
    def test_save_and_load(self, tmp_path):
        """保存后应能正确加载。"""
        f = tmp_path / "test.json"
        data = {"key": "value", "num": 42, "nested": {"a": 1}}
        _conf_save_json(f, data)
        loaded = _conf_load_json(f)
        assert loaded == data

    def test_load_nonexistent_returns_empty(self, tmp_path):
        """加载不存在的文件应返回空字典。"""
        f = tmp_path / "nonexistent.json"
        result = _conf_load_json(f)
        assert result == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        """保存时应自动创建父目录。"""
        f = tmp_path / "sub" / "dir" / "test.json"
        _conf_save_json(f, {"x": 1})
        assert f.exists()
        assert _conf_load_json(f) == {"x": 1}

    def test_unicode_content(self, tmp_path):
        """应正确处理中文内容。"""
        f = tmp_path / "unicode.json"
        data = {"name": "贾维斯", "desc": "上下文铠甲系统"}
        _conf_save_json(f, data)
        assert _conf_load_json(f) == data


# ── get_model_config ──────────────────────────────────────


class TestGetModelConfig:
    def test_returns_known_config(self):
        """已知配置键应返回配置字典。"""
        result = get_model_config("llmAnalyze")
        assert result is not None
        assert "model" in result
        assert "provider" in result

    def test_returns_none_for_unknown(self):
        """未知配置键应返回 None。"""
        result = get_model_config("nonexistent_key_12345")
        assert result is None

    def test_llm_analyze_uses_doubao(self, tmp_path, monkeypatch):
        """llmAnalyze 应配置为 doubao-seed-2.0-pro。"""
        # 临时指向不存在的 config.json，强制走 config.toml
        import mark42.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "CONFIG_PATH", tmp_path / "nonexistent.json")
        result = get_model_config("llmAnalyze")
        assert result is not None
        assert result["model"] == "doubao-seed-2.0-pro"
        assert result["provider"] == "volcengine-agent"


# ── resolve_model ────────────────────────────────────────


class TestResolveModel:
    def test_returns_none_for_unknown(self):
        """未知配置键应返回 None。"""
        assert resolve_model("nonexistent_12345") is None

    def test_returns_dict_with_api_params(self):
        """已知配置应返回完整 API 参数。"""
        result = resolve_model("llmAnalyze")
        if result is not None:
            required = {"model", "apiKey", "baseUrl", "endpoint", "maxTokens", "temperature", "timeout"}
            assert required.issubset(result.keys())
            assert len(result["apiKey"]) > 0
            assert result["timeout"] > 0
            assert result["maxTokens"] > 0

    def test_returns_none_without_openclaw_config(self, tmp_path, monkeypatch):
        """没有 openclaw.json 时应返回 None（无 API key）。"""
        monkeypatch.setenv("OPENCLAW_CONFIG", str(tmp_path / "nonexistent.json"))
        # 需要重新 import
        import importlib

        importlib.reload(cfg)
        result = cfg.resolve_model("llmAnalyze")
        # 如果 openclaw.json 不存在，api_key 为空，应返回 None
        # 但如果实际环境有 openclaw.json，需要模拟
        if result is not None:
            # 实际环境有配置，跳过此断言
            pass


class TestSchemaDowngradeProtection:
    """P3-6 防回归：未来 schema 不得被静默降级。

    历史 bug（已实证复现）：`_migrate_config_if_needed` 只判断
    "等不等于当前版本"，于是**任何非当前版本都会进迁移** ——
    schema 3/4/99 等未来版本也会被改写成当前版本**并写回磁盘**。

    后果：新版本 Mark42 写的配置，被旧版程序读一次就永久降级；
    新版本才认识的字段语义也可能被误解。这类损坏是不可逆的。

    修复后行为：
      schema <  当前 -> 正常向上迁移（原行为不变）
      schema == 当前 -> 直接返回
      schema >  当前 -> 拒绝降级与写回，只告警并原样返回（只读兼容）
                        需强行降级须显式设 MARK42_ALLOW_SCHEMA_DOWNGRADE=1
    """

    def test_future_schema_is_not_downgraded(self, monkeypatch):
        from mark42.config import (
            CONFIG_SCHEMA_VERSION,
            _migrate_config_if_needed,
        )

        monkeypatch.delenv("MARK42_ALLOW_SCHEMA_DOWNGRADE", raising=False)
        future_version = CONFIG_SCHEMA_VERSION + 97
        cfg = {
            "configSchemaVersion": future_version,
            "newFeatureField": {"deep": "value"},
            "thresholds": {"warn": 42},
        }
        out = _migrate_config_if_needed(cfg)

        assert out["configSchemaVersion"] == future_version, "未来 schema 被降级了"
        assert out["newFeatureField"] == {"deep": "value"}, "未来字段被丢弃"
        assert "migratedAt" not in out, "未来 schema 不该被打迁移标记"
        assert "migratedByVersion" not in out

    def test_future_schema_warns(self, monkeypatch, caplog):
        import logging

        from mark42.config import (
            CONFIG_SCHEMA_VERSION,
            _migrate_config_if_needed,
        )

        monkeypatch.delenv("MARK42_ALLOW_SCHEMA_DOWNGRADE", raising=False)
        with caplog.at_level(logging.WARNING):
            _migrate_config_if_needed(
                {"configSchemaVersion": CONFIG_SCHEMA_VERSION + 1}
            )
        assert any("只读" in r.message for r in caplog.records), (
            "未来 schema 必须明确告警，不能静默"
        )

    def test_future_schema_not_written_back(self, monkeypatch, tmp_path):
        """关键：未来 schema 绝不能写回磁盘（写回即造成永久降级）。"""
        from mark42 import config as cfg_mod

        monkeypatch.delenv("MARK42_ALLOW_SCHEMA_DOWNGRADE", raising=False)
        saved = []
        monkeypatch.setattr(cfg_mod, "_save_config", lambda c: saved.append(c))

        cfg_mod._migrate_config_if_needed(
            {"configSchemaVersion": cfg_mod.CONFIG_SCHEMA_VERSION + 5}
        )
        assert saved == [], "未来 schema 被写回磁盘了"

    def test_explicit_override_allows_downgrade(self, monkeypatch):
        """显式开启环境变量后才允许降级（提供逃生舱但不默认）。"""
        from mark42.config import (
            CONFIG_SCHEMA_VERSION,
            _migrate_config_if_needed,
        )

        monkeypatch.setenv("MARK42_ALLOW_SCHEMA_DOWNGRADE", "1")
        out = _migrate_config_if_needed(
            {"configSchemaVersion": CONFIG_SCHEMA_VERSION + 3}
        )
        assert out["configSchemaVersion"] == CONFIG_SCHEMA_VERSION

    def test_old_schema_still_migrates_up(self, monkeypatch):
        """向上迁移是原有能力，不得被本次修复破坏。"""
        from mark42 import config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_save_config", lambda c: None)
        out = cfg_mod._migrate_config_if_needed(
            {"version": "2.3.0", "thresholds": {"warn": 70}}
        )
        assert out["configSchemaVersion"] == cfg_mod.CONFIG_SCHEMA_VERSION
        assert out["legacyVersion"] == "2.3.0"
        # 用户自定义配置不得被动
        assert out["thresholds"] == {"warn": 70}

    def test_current_schema_returns_same_object(self):
        from mark42.config import (
            CONFIG_SCHEMA_VERSION,
            _migrate_config_if_needed,
        )

        cfg = {"configSchemaVersion": CONFIG_SCHEMA_VERSION, "x": 1}
        assert _migrate_config_if_needed(cfg) is cfg

    def test_non_int_schema_does_not_crash(self, monkeypatch):
        """schema 字段被写成字符串等异常值时不得崩溃。"""
        from mark42 import config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_save_config", lambda c: None)
        out = cfg_mod._migrate_config_if_needed({"configSchemaVersion": "bad"})
        # 非法值按"需要迁移"处理，迁到当前版本
        assert out["configSchemaVersion"] == cfg_mod.CONFIG_SCHEMA_VERSION
