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
