"""user_config.py 单元测试"""
import json
from pathlib import Path

import pytest

from mark42 import user_config
from mark42.user_config import (
    get,
    get_config_path,
    get_default_config_path,
    get_openclaw_config_path,
    get_section,
    load_config,
    reload,
    set_openclaw_config_override,
)


class TestLoadConfig:
    def test_load_returns_dict(self):
        result = load_config()
        assert isinstance(result, dict)

    def test_force_reload(self):
        load_config()
        result2 = load_config(force_reload=True)
        assert isinstance(result2, dict)


class TestGet:
    def test_get_with_section_and_key(self):
        result = get("model", "primary", default="fallback")
        # 可能返回 default 或实际值
        assert result is not None

    def test_get_missing_returns_default(self):
        result = get("nonexistent_section", "nonexistent_key", default="default")
        assert result == "default"


class TestGetSection:
    def test_get_section_returns_dict(self):
        result = get_section("nonexistent")
        assert isinstance(result, dict)

    def test_reload(self):
        result = reload()
        assert isinstance(result, dict)


class TestGetConfigPath:
    def test_returns_path(self):
        result = get_config_path()
        assert isinstance(result, Path)

    def test_default_path(self):
        result = get_default_config_path()
        assert isinstance(result, Path)


@pytest.fixture(autouse=True)
def _clear_openclaw_override():
    """每个测试前后清空 CLI 覆盖，避免跨测试污染。"""
    set_openclaw_config_override(None)
    yield
    set_openclaw_config_override(None)


class TestOpenclawConfigPathResolution:
    """P2-16 防回归：openclaw.json 路径必须走单一解析器。

    历史 bug：``openclaw_config.py`` / ``context_safety.py`` /
    ``compaction_diag.py`` / ``config.py`` 各自硬编码
    ``Path.home()/".openclaw"/"openclaw.json"``，且多为**模块级常量**
    （import 时固化）。后果：``OPENCLAW_CONFIG`` 环境变量与配置向导
    写入的 ``[paths] openclaw_config`` 完全无效，多实例/容器/测试隔离
    下会误操作真实用户配置。

    优先级：CLI > 环境变量 > TOML > 平台默认。
    """

    def test_defaults_to_platform_path(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_CONFIG", raising=False)
        monkeypatch.setattr(user_config, "get", lambda *a, **k: "")
        # 根 conftest 会把 HOME 指向临时目录做隔离，
        # 所以这里断言「相对于当前 HOME 的默认位置」而非硬编码绝对路径。
        assert get_openclaw_config_path() == (
            Path("~/.openclaw/openclaw.json").expanduser()
        )

    def test_env_var_wins_over_default(self, monkeypatch, tmp_path):
        target = tmp_path / "env.json"
        monkeypatch.setenv("OPENCLAW_CONFIG", str(target))
        assert get_openclaw_config_path() == target

    def test_env_var_expands_user(self, monkeypatch):
        monkeypatch.setenv("OPENCLAW_CONFIG", "~/somewhere/oc.json")
        assert get_openclaw_config_path() == (
            Path("~/somewhere/oc.json").expanduser()
        )

    def test_blank_env_var_falls_through(self, monkeypatch):
        """空串/纯空白环境变量不得把路径解成空。"""
        monkeypatch.setenv("OPENCLAW_CONFIG", "   ")
        monkeypatch.setattr(user_config, "get", lambda *a, **k: "")
        assert get_openclaw_config_path() == (
            Path("~/.openclaw/openclaw.json").expanduser()
        )

    def test_toml_path_used_when_no_env(self, monkeypatch, tmp_path):
        target = tmp_path / "from-toml.json"
        monkeypatch.delenv("OPENCLAW_CONFIG", raising=False)
        monkeypatch.setattr(
            user_config, "get",
            lambda section, key, default=None: (
                str(target)
                if (section, key) == ("paths", "openclaw_config") else default
            ),
        )
        assert get_openclaw_config_path() == target

    def test_env_wins_over_toml(self, monkeypatch, tmp_path):
        env_target = tmp_path / "env.json"
        monkeypatch.setenv("OPENCLAW_CONFIG", str(env_target))
        monkeypatch.setattr(
            user_config, "get",
            lambda *a, **k: str(tmp_path / "toml.json"),
        )
        assert get_openclaw_config_path() == env_target

    def test_cli_override_wins_over_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENCLAW_CONFIG", str(tmp_path / "env.json"))
        cli_target = tmp_path / "cli.json"
        set_openclaw_config_override(cli_target)
        assert get_openclaw_config_path() == cli_target

    def test_cli_override_can_be_cleared(self, monkeypatch, tmp_path):
        env_target = tmp_path / "env.json"
        monkeypatch.setenv("OPENCLAW_CONFIG", str(env_target))
        set_openclaw_config_override(tmp_path / "cli.json")
        set_openclaw_config_override(None)
        assert get_openclaw_config_path() == env_target

    def test_broken_toml_falls_back_to_default(self, monkeypatch):
        """TOML 读取抛异常时不得连带整个路径体系崩掉。"""
        monkeypatch.delenv("OPENCLAW_CONFIG", raising=False)

        def boom(*a, **k):
            raise RuntimeError("toml 坏了")

        monkeypatch.setattr(user_config, "get", boom)
        assert get_openclaw_config_path() == (
            Path("~/.openclaw/openclaw.json").expanduser()
        )

    def test_not_cached_across_calls(self, monkeypatch, tmp_path):
        """解析器不得缓存——否则就重现了模块级常量的固化问题。"""
        first = tmp_path / "a.json"
        second = tmp_path / "b.json"
        monkeypatch.setenv("OPENCLAW_CONFIG", str(first))
        assert get_openclaw_config_path() == first
        monkeypatch.setenv("OPENCLAW_CONFIG", str(second))
        assert get_openclaw_config_path() == second


def _drop_explicit(monkeypatch, module, attr: str) -> None:
    """移除模块级显式赋值，使路径解析回落到统一解析器。

    这些属性由模块 ``__getattr__`` 动态提供，``monkeypatch.delattr``
    会因“属性本不在 __dict__ 里”而抛 AttributeError，故直接改 __dict__。
    """
    if attr in module.__dict__:
        monkeypatch.delitem(module.__dict__, attr)


class TestConsumersRespectResolvedPath:
    """P2-16 防回归：四个调用方必须跟随解析器，而非 import 时固化。"""

    def test_openclaw_config_module_follows_env(self, monkeypatch, tmp_path):
        from mark42 import openclaw_config

        target = tmp_path / "oc.json"
        monkeypatch.setenv("OPENCLAW_CONFIG", str(target))
        # 清掉其他测试可能注入的模块级显式赋值，确保测的是解析器路径。
        # 注意：不能用 monkeypatch.delattr —— 该属性由 __getattr__ 动态提供，
        # delattr 会抛 AttributeError。直接操作 __dict__ 并在结束时还原。
        _drop_explicit(monkeypatch, openclaw_config, "OPENCLAW_CONFIG")
        assert openclaw_config._openclaw_config_path() == target
        # 向后兼容属性也必须跟随（不能固化）
        assert openclaw_config.OPENCLAW_CONFIG == target
        # 锁文件必须与目标同目录（保证同一文件系统）
        assert openclaw_config._lock_path().parent == target.parent

    def test_context_safety_follows_env(self, monkeypatch, tmp_path):
        from mark42 import context_safety

        target = tmp_path / "cs.json"
        monkeypatch.setenv("OPENCLAW_CONFIG", str(target))
        _drop_explicit(monkeypatch, context_safety, "OPENCLAW_CONFIG")
        assert context_safety._openclaw_config_path() == target
        assert context_safety.OPENCLAW_CONFIG == target

    def test_compaction_diag_follows_env(self, monkeypatch, tmp_path):
        from mark42 import compaction_diag

        target = tmp_path / "cd.json"
        monkeypatch.setenv("OPENCLAW_CONFIG", str(target))
        _drop_explicit(monkeypatch, compaction_diag, "_OPENCLAW_JSON")
        assert compaction_diag._openclaw_json_path() == target
        assert compaction_diag._OPENCLAW_JSON == target

    def test_config_resolve_model_reads_custom_path(self, monkeypatch, tmp_path):
        """config.resolve_model 必须从自定义路径读 API key/baseUrl。"""
        from mark42 import config as mark42_config

        target = tmp_path / "custom.json"
        table = mark42_config.MARK42_MODEL_TABLE
        config_key = next(iter(table))
        provider = table[config_key].get("provider", "")
        target.write_text(json.dumps({"models": {"providers": {
            provider: {
                "apiKey": "KEY-FROM-CUSTOM",
                "baseUrl": "https://custom.example/v1",
            },
        }}}), encoding="utf-8")
        monkeypatch.setenv("OPENCLAW_CONFIG", str(target))

        resolved = mark42_config.resolve_model(config_key)
        assert resolved is not None
        assert resolved["apiKey"] == "KEY-FROM-CUSTOM"
        assert resolved["baseUrl"] == "https://custom.example/v1"

    def test_unknown_attribute_still_raises(self):
        """__getattr__ 兼容层不得把拼错的属性名吞成 None。"""
        from mark42 import compaction_diag, context_safety, openclaw_config

        for mod in (openclaw_config, context_safety, compaction_diag):
            with pytest.raises(AttributeError):
                getattr(mod, "NO_SUCH_ATTRIBUTE_XYZ")
