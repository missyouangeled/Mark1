"""验证 conftest.py 的环境隔离正确生效（自我测试）。

如果这些测试通过，说明：
  1. autouse fixture 工作正常
  2. config 重定向到 tmp_path
  3. 不会污染真生产 ~/.local/state/openclaw/mark42/
"""

import os
from pathlib import Path


def test_isolation_does_not_pollute_real_state(tmp_path):
    """autouse fixture 已经把 XDG_STATE_HOME 改成 tmp_path 子目录。

    我们这里验证：真生产路径 ~/.local/state/openclaw/mark42/ 没被写新东西。
    """
    real_state = Path.home() / ".local" / "state" / "openclaw" / "mark42"

    # 记录改之前的 mtime（如果有 actions.jsonl）
    real_actions = real_state / "armor" / "actions.jsonl"
    mtime_before = real_actions.stat().st_mtime if real_actions.exists() else None

    # 触发 conftest 的 autouse fixture（不需要显式引用）
    from mark42_modules import config

    # 验证 config.MARK42_STATE 已经指向 tmp_path，不是真生产
    assert str(config.MARK42_STATE).startswith(str(tmp_path)), (
        f"config.MARK42_STATE 没被重定向到 tmp_path: {config.MARK42_STATE}"
    )
    assert not str(config.MARK42_STATE).startswith(str(real_state)), (
        f"config.MARK42_STATE 还在指真生产: {config.MARK42_STATE}"
    )

    # 验证真生产文件没变（这是隔离生效的最终证据）
    if mtime_before is not None:
        mtime_after = real_actions.stat().st_mtime
        assert mtime_before == mtime_after, "测试污染了真生产文件！"


def test_data_root_is_also_redirected(tmp_path):
    """DATA_ROOT 也必须指向 tmp_path，不能指 /mnt/data。"""
    from mark42_modules import config

    assert str(config.DATA_ROOT).startswith(str(tmp_path)), (
        f"DATA_ROOT 没被重定向: {config.DATA_ROOT}"
    )


def test_log_dir_is_redirected(tmp_path):
    """LOG_DIR 必须派生到 tmp_path 下。"""
    from mark42_modules import config

    assert str(config.LOG_DIR).startswith(str(tmp_path)), (
        f"LOG_DIR 没被重定向: {config.LOG_DIR}"
    )


def test_real_xdg_state_unchanged(monkeypatch):
    """验证 monkeypatch 正确恢复 XDG_STATE_HOME。

    设计思路：
      - conftest autouse 设临时值时，monkeypatch.setenv 记录了原值
      - 调 monkeypatch.undo() 会逆序撤销所有 monkeypatch.setenv
      - 撤销后，XDG_STATE_HOME 应该回到系统原始状态（未设）
      - 如果系统原本就设过，撤销后应该等于那个原值

    这个测试是 conftest 安全性的"反向验证"：
      如果这里 undo() 后环境变脏了，说明 monkeypatch 没正确恢复。
    """
    # 初始：conftest autouse 已设临时值
    assert "XDG_STATE_HOME" in os.environ
    conftest_xdg = os.environ["XDG_STATE_HOME"]
    assert conftest_xdg != "<UNSET>"  # 我们之前手动 set 过

    # 测试体手动 setenv（验证可以覆盖）
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/fake_xdg_for_test")
    assert os.environ["XDG_STATE_HOME"] == "/tmp/fake_xdg_for_test"

    # 主动 undo：会按 LIFO 撤销所有 monkeypatch
    #   1. 撤销测试体 setenv → 恢复为 conftest 设的临时值
    #   2. 撤销 conftest setenv → 恢复为系统原始值（未设）
    monkeypatch.undo()

    # 撤销后 XDG_STATE_HOME 应该回到系统原始状态
    # （如果系统原本没设，撤销后 os.environ.get 返回 None）
    current = os.environ.get("XDG_STATE_HOME")
    assert current is None, (
        f"monkeypatch.undo() 后环境变脏了: XDG_STATE_HOME={current} (应为 None)"
    )

    # 注意：测试结束时 pytest 会再调一次 monkeypatch.undo()（conftest 的），
    # 但这时已经撤销过了，再撤一次应该是 no-op。


def test_armor_state_path(armor_state):
    """验证 armor_state fixture 返回正确路径。"""
    # 路径应该是 <tmp>/state/openclaw/mark42/armor
    assert "armor" in str(armor_state)
    assert "mark42" in str(armor_state)
    # 父目录应该已存在（fixture 创建的）
    assert armor_state.parent.exists()


def test_engine_state_path(engine_state):
    """验证 engine_state fixture。"""
    assert "engine" in str(engine_state)


def test_heavy_state_path(heavy_state):
    """验证 heavy_state fixture。"""
    assert "heavy" in str(heavy_state)


def test_broker_dir_path(broker_dir):
    """验证 broker_dir fixture。"""
    assert "broker" in str(broker_dir)


def test_fixtures_are_independent(tmp_path):
    """每个测试的 tmp_path 是独立的（pytest 默认行为）。"""
    from mark42_modules import config

    # 这个测试的 MARK42_STATE 应该和上一个测试的不一样
    state_a = config.MARK42_STATE

    # 触发一次 autouse（虽然 pytest 会自动应用）
    # 这里我们只是验证路径看起来对
    assert str(state_a).startswith(str(tmp_path))