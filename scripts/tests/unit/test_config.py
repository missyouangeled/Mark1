"""config.py 测试群 — 路径常量 + env 路由。

7/01 新增: SCRATCH env 路由 (MARK42_SCRATCH) 验证。
此前 config.py 完全无单测, 路径硬编码 /mnt/data 在别人机器直接报错无人发现。

测试覆盖:
  - SCRATCH 默认值 (点点机器)
  - SCRATCH env 覆盖
  - SCRATCH env 指向不存在路径 → fallback XDG_STATE
  - DATA_ROOT 已有 fallback 行为保持
  - THRESHOLD_* env 覆盖
  - XDG_STATE 默认走 ~/.local/state

⚠️ 设计原则： 不 reload sys.modules, 不污染其他测试。
  config 模块在 pytest 启动时已 import, 改 env 后只能验证"逻辑分支",
  实际重新解析需要在子进程跑。这是 7/01 教训 (test_logs 之前因为 reload 污染).
"""

import json
import os
import sys
from pathlib import Path

import pytest

import mark42_modules.config as cfg


# ── SCRATCH 路径测试 (用 subprocess 测 env 路由, 不污染 sys.modules) ──


class TestSCRATCHPath:
    """SCRATCH 路径: env 路由 + fallback (7/01 加)

    验证方式: 启动 subprocess 跑 python -c 'import ...; print(cfg.SCRATCH)',
    让 env 在子进程内生效, 避免污染父进程 sys.modules.
    """

    def test_default_uses_mnt_data(self):
        """无 env: 默认 /mnt/data/openclaw/scratch (点点机器)"""
        env = os.environ.copy()
        env.pop("MARK42_SCRATCH", None)
        result = _run_in_subprocess(_CHECK_SCRATCH_CODE, env=env)
        assert "/mnt/data/openclaw/scratch" in result

    def test_env_override_takes_precedence(self, tmp_path):
        """MARK42_SCRATCH env 覆盖"""
        custom = tmp_path / "my-scratch"
        custom.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["MARK42_SCRATCH"] = str(custom)
        result = _run_in_subprocess(_CHECK_SCRATCH_CODE, env=env)
        assert str(custom) in result

    def test_env_nonexistent_falls_back_to_xdg(self):
        """MARK42_SCRATCH 指向不存在路径 → 自动回退到 XDG_STATE/openclaw/scratch"""
        env = os.environ.copy()
        env["MARK42_SCRATCH"] = "/this/does/not/exist/scratch"
        result = _run_in_subprocess(_CHECK_SCRATCH_CODE, env=env)
        # fallback 触发: 路径里不含 /mnt/data 也不含 fake
        assert "/mnt/data" not in result
        assert "/this/does/not/exist" not in result
        # 应该是 XDG_STATE 派生
        assert "openclaw/scratch" in result

    def test_xdg_state_default_is_local_state(self):
        """XDG_STATE_HOME 未设: 默认 ~/.local/state"""
        env = os.environ.copy()
        env.pop("XDG_STATE_HOME", None)
        result = _run_in_subprocess(
            "from mark42_modules.config import XDG_STATE; print(XDG_STATE)",
            env=env,
        )
        assert ".local/state" in result


# ── DATA_ROOT fallback 行为保持 (用当前已 import 的 cfg) ──


class TestDataRootFallback:
    """DATA_ROOT 已有 fallback, 验证不被新 SCRATCH 改坏

    注意: conftest 已用 tmp_path 重定向 XDG_STATE, 所以 cfg.DATA_ROOT
    在测试里 = tmp_path 派生. 这是 conftest fixture 的设计, 不是 bug.
    """

    def test_data_root_uses_xdg_state_in_test_env(self):
        """测试环境下 (conftest 已隔离), DATA_ROOT 走 XDG_STATE fallback"""
        # conftest autouse fixture 把 XDG_STATE_HOME 改成 tmp_path
        # 所以 DATA_ROOT 应该是 tmp_path 派生, 不是 /mnt/data
        assert "/mnt/data" not in str(cfg.DATA_ROOT)
        # 应该是 XDG_STATE 派生
        assert str(cfg.XDG_STATE) in str(cfg.DATA_ROOT.parent.parent) or "pytest-of" in str(cfg.DATA_ROOT)

    def test_data_root_log_dir_under_data_root(self):
        """LOG_DIR 必须在 DATA_ROOT 下 (不破现有设计)"""
        assert cfg.LOG_DIR.parent == cfg.DATA_ROOT


# ── Threshold env 覆盖 (用 subprocess 验证, 因为 int() 解析在 import 时) ──


class TestThresholds:
    """THRESHOLD_* env 覆盖 (现有功能, 顺便覆盖)"""

    def test_threshold_warn_default_70(self):
        """MARK42_CTX_WARN_PCT 未设 → 70"""
        env = os.environ.copy()
        env.pop("MARK42_CTX_WARN_PCT", None)
        result = _run_in_subprocess(
            "from mark42_modules.config import THRESHOLD_WARN; print(THRESHOLD_WARN)",
            env=env,
        )
        assert result.strip() == "70"

    def test_threshold_warn_env_override(self):
        """MARK42_CTX_WARN_PCT=85 生效"""
        env = os.environ.copy()
        env["MARK42_CTX_WARN_PCT"] = "85"
        result = _run_in_subprocess(
            "from mark42_modules.config import THRESHOLD_WARN; print(THRESHOLD_WARN)",
            env=env,
        )
        assert result.strip() == "85"

    def test_threshold_alert_env_override(self):
        """MARK42_CTX_ALERT_PCT=95 生效"""
        env = os.environ.copy()
        env["MARK42_CTX_ALERT_PCT"] = "95"
        result = _run_in_subprocess(
            "from mark42_modules.config import THRESHOLD_ALERT; print(THRESHOLD_ALERT)",
            env=env,
        )
        assert result.strip() == "95"


# ── helper: 在子进程跑 python -c 验证 env 行为 ──


_CHECK_SCRATCH_CODE = (
    "from mark42_modules.config import SCRATCH; print(SCRATCH)"
)


def _run_in_subprocess(code: str, env: dict) -> str:
    """在子进程跑 python -c, 让 env 真正生效。

    返回 stdout. 不污染父进程 sys.modules.
    """
    import subprocess
    # 强制把 /home/missyouangeled/.openclaw/workspace/scripts 加到 PYTHONPATH
    env = env.copy()
    scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
    env["PYTHONPATH"] = scripts_dir + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    if result.returncode != 0:
        pytest.fail(
            f"subprocess 失败 (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout


class TestJsonHelpers:
    def test_conf_load_json_missing_returns_empty(self, tmp_path):
        path = tmp_path / "missing.json"
        assert cfg._conf_load_json(path) == {}

    def test_conf_load_json_invalid_returns_empty(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not-json}", encoding="utf-8")
        assert cfg._conf_load_json(path) == {}

    def test_conf_save_json_and_load_back(self, tmp_path):
        path = tmp_path / "nested" / "config.json"
        data = {"name": "Mark42", "ok": True}
        cfg._conf_save_json(path, data)
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == data
        assert cfg._conf_load_json(path) == data


class TestModelConfig:
    def test_get_model_config_falls_back_to_default_table(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
        result = cfg.get_model_config("llmAnalyze")
        assert result is not None
        assert result["model"] == "MiniMax-M3"
        assert result["provider"] == "minimax"

    def test_get_model_config_merges_runtime_dict_override(self, monkeypatch, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "models": {
                "llmAnalyze": {
                    "model": "Custom-M3",
                    "timeout": 99,
                }
            }
        }), encoding="utf-8")
        monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
        result = cfg.get_model_config("llmAnalyze")
        assert result is not None
        assert result["model"] == "Custom-M3"
        assert result["timeout"] == 99
        assert result["provider"] == "minimax"

    def test_get_model_config_supports_legacy_string_entry(self, monkeypatch, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "models": {
                "llmAnalyze": "Legacy-Model"
            }
        }), encoding="utf-8")
        monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
        result = cfg.get_model_config("llmAnalyze")
        assert result is not None
        assert result["model"] == "Legacy-Model"
        assert result["provider"] == "minimax"

    def test_get_model_config_invalid_json_falls_back(self, monkeypatch, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("{bad-json}", encoding="utf-8")
        monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
        result = cfg.get_model_config("llmCompress")
        assert result is not None
        assert result["model"] == "MiniMax-M3"

    def test_resolve_model_returns_none_for_unknown_key(self):
        assert cfg.resolve_model("not-exist") is None

    def test_resolve_model_returns_none_when_api_key_missing(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        (fake_home / ".openclaw").mkdir(parents=True)
        (fake_home / ".openclaw" / "openclaw.json").write_text(json.dumps({
            "models": {"providers": {"minimax": {}}}
        }), encoding="utf-8")
        monkeypatch.setattr(cfg.Path, "home", lambda: fake_home)
        result = cfg.resolve_model("llmAnalyze")
        assert result is None

    def test_resolve_model_uses_provider_api_key_and_base_url(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        openclaw_dir = fake_home / ".openclaw"
        openclaw_dir.mkdir(parents=True)
        (openclaw_dir / "openclaw.json").write_text(json.dumps({
            "models": {
                "providers": {
                    "minimax": {
                        "apiKey": "sk-test",
                        "baseUrl": "https://example.invalid/v1"
                    }
                }
            }
        }), encoding="utf-8")
        monkeypatch.setattr(cfg.Path, "home", lambda: fake_home)
        result = cfg.resolve_model("llmAnalyze")
        assert result is not None
        assert result["apiKey"] == "sk-test"
        assert result["baseUrl"] == "https://example.invalid/v1"
        assert result["model"] == "MiniMax-M3"
        assert result["endpoint"] == "/chat/completions"

    def test_resolve_model_falls_back_to_default_base_url(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        openclaw_dir = fake_home / ".openclaw"
        openclaw_dir.mkdir(parents=True)
        (openclaw_dir / "openclaw.json").write_text(json.dumps({
            "models": {
                "providers": {
                    "minimax": {
                        "apiKey": "sk-test"
                    }
                }
            }
        }), encoding="utf-8")
        monkeypatch.setattr(cfg.Path, "home", lambda: fake_home)
        result = cfg.resolve_model("llmCompress")
        assert result is not None
        assert result["baseUrl"] == "https://api.minimax.chat/v1"
        assert result["maxTokens"] == 4000
        assert result["temperature"] == 0.0


class TestConfigLifecycle:
    def test_load_config_returns_empty_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
        assert cfg._load_config() == {}

    def test_save_config_writes_file(self, monkeypatch, tmp_path):
        config_path = tmp_path / "mark42" / "config.json"
        monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
        data = {"version": "9.9.9"}
        cfg._save_config(data)
        assert json.loads(config_path.read_text(encoding="utf-8")) == data

    def test_mark42_init_creates_config_and_dirs(self, monkeypatch, tmp_path, capsys):
        state_root = tmp_path / "state"
        config_path = state_root / "config.json"
        armor = state_root / "armor"
        engine = state_root / "engine"
        heavy = state_root / "heavy"
        monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg, "MARK42_STATE", state_root)
        monkeypatch.setattr(cfg, "ARMOR_STATE", armor)
        monkeypatch.setattr(cfg, "ENGINE_STATE", engine)
        monkeypatch.setattr(cfg, "HEAVY_STATE", heavy)
        cfg.mark42_init()
        out = capsys.readouterr().out
        assert "✅ Mark42 已初始化" in out
        assert config_path.exists()
        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved["version"] == "2.3.0"
        assert armor.exists()
        assert engine.exists()
        assert heavy.exists()
        assert (armor / "history").exists()

    def test_mark42_init_when_already_initialized_prints_hint(self, monkeypatch, tmp_path, capsys):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"version": "2.3.0"}), encoding="utf-8")
        monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg, "_load_config", lambda: {"version": "2.3.0"})
        cfg.mark42_init()
        out = capsys.readouterr().out
        assert "已初始化" in out
        assert "使用 --config 修改" in out

    def test_mark42_config_without_init_prints_error(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "missing.json")
        cfg.mark42_config()
        out = capsys.readouterr().out
        assert "尚未初始化" in out

    def test_mark42_config_prints_summary_and_legacy_model(self, monkeypatch, tmp_path, capsys):
        config_path = tmp_path / "config.json"
        config_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg, "_load_config", lambda: {
            "version": "2.3.0",
            "initializedAt": "2026-07-01T10:00:00+08:00",
            "contextWindow": 1000000,
            "bytesPerKtoken": 2048,
            "thresholds": {"warn": 70, "alert": 85, "crit": 95},
            "models": {
                "llmAnalyze": {"model": "MiniMax-M3", "provider": "minimax"},
                "legacyModel": "old-format-model",
            },
            "daemon": {"scanInterval": 30, "autoArmorCompress": True, "autoTaskWatch": False},
            "heavy": {"autoDetectEnabled": True, "autoDetect": "semi"},
        })
        cfg.mark42_config()
        out = capsys.readouterr().out
        assert "⚙️ Mark42 配置" in out
        assert "版本: 2.3.0" in out
        assert "llmAnalyze: MiniMax-M3" in out
        assert "legacyModel: old-format-model  (旧格式)" in out
        assert "扫描间隔: 30s" in out
        assert "大工程检测: 启用" in out
