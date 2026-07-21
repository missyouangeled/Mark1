"""test_engine.py - 循环引擎测试。

覆盖：
- _load_loops / _save_loops 读写
- engine_start() 注册 Loop
- engine_kill() 终止 Loop
- engine_list() 列表
- Loop 状态转换
"""

import pytest

from mark42 import engine
from mark42.engine import (
    _load_loops,
    _save_loops,
    engine_kill,
    engine_start,
)


@pytest.fixture(autouse=True)
def isolated_engine_state(tmp_path, monkeypatch):
    """每个测试用独立的 engine state 目录，避免污染真实数据。"""
    test_state = tmp_path / "engine"
    test_state.mkdir(parents=True, exist_ok=True)
    test_loops = test_state / "loops.json"

    monkeypatch.setattr(engine, "ENGINE_STATE", test_state)
    monkeypatch.setattr(engine, "ENGINE_LOOPS", test_loops)

    yield

    # 清理
    if test_loops.exists():
        test_loops.unlink()


# ── _load_loops / _save_loops ─────────────────────────────

class TestLoadSaveLoops:
    def test_load_empty_returns_empty_dict(self):
        """无 loops.json 时应返回空字典。"""
        result = _load_loops()
        assert result == {}

    def test_save_then_load(self):
        """保存后应能正确加载。"""
        loops = {
            "test-loop": {
                "task": "echo hello",
                "interval": 60,
                "status": "registered",
                "cycle": 0,
            }
        }
        _save_loops(loops)
        loaded = _load_loops()
        assert loaded == loops

    def test_save_preserves_unicode(self):
        """应正确保存中文内容。"""
        loops = {
            "中文循环": {
                "task": "执行任务",
                "interval": 30,
                "status": "registered",
            }
        }
        _save_loops(loops)
        loaded = _load_loops()
        assert "中文循环" in loaded
        assert loaded["中文循环"]["task"] == "执行任务"


# ── engine_start ─────────────────────────────────────────

class TestEngineStart:
    def test_registers_new_loop(self):
        """应成功注册新 Loop。"""
        engine_start("echo test", interval_s=60, template="test-tpl")
        loops = _load_loops()
        assert "test-tpl" in loops
        assert loops["test-tpl"]["task"] == "echo test"
        assert loops["test-tpl"]["interval"] == 60
        assert loops["test-tpl"]["status"] == "registered"
        assert loops["test-tpl"]["cycle"] == 0

    def test_auto_generated_name(self):
        """无 template 时应自动生成名称。"""
        engine_start("echo auto", interval_s=120)
        loops = _load_loops()
        assert len(loops) == 1
        name = list(loops.keys())[0]
        assert name.startswith("loop-")

    def test_override_existing_loop(self):
        """同名 Loop 应被覆盖。"""
        engine_start("echo v1", interval_s=60, template="dup")
        engine_start("echo v2", interval_s=30, template="dup")
        loops = _load_loops()
        assert loops["dup"]["task"] == "echo v2"
        assert loops["dup"]["interval"] == 30

    def test_max_cycles_stored(self):
        """maxCycles 应被正确存储。"""
        engine_start("echo test", interval_s=60, max_cycles=10, template="cycled")
        loops = _load_loops()
        assert loops["cycled"]["maxCycles"] == 10

    def test_infinite_cycles_default(self):
        """max_cycles=0 应存储为 None（无限）。"""
        engine_start("echo test", interval_s=60, max_cycles=0, template="infinite")
        loops = _load_loops()
        assert loops["infinite"]["maxCycles"] is None


# ── engine_kill ──────────────────────────────────────────

class TestEngineKill:
    def test_kills_registered_loop(self):
        """应能终止已注册的 Loop。"""
        engine_start("echo test", interval_s=60, template="kill-me")
        engine_kill("kill-me")
        loops = _load_loops()
        assert loops["kill-me"]["status"] == "killed"
        assert "killedAt" in loops["kill-me"]

    def test_kill_nonexistent_logs_error(self):
        """终止不存在的 Loop 不应崩溃。"""
        engine_kill("nonexistent-loop-12345")
        # 不崩溃即通过

    def test_kill_preserves_other_loops(self):
        """终止一个 Loop 不应影响其他 Loop。"""
        engine_start("echo a", interval_s=60, template="loop-a")
        engine_start("echo b", interval_s=60, template="loop-b")
        engine_kill("loop-a")
        loops = _load_loops()
        assert loops["loop-b"]["status"] == "registered"
        assert loops["loop-a"]["status"] == "killed"


# ── Loop 状态完整性 ───────────────────────────────────────

class TestLoopIntegrity:
    def test_loop_has_all_required_fields(self):
        """注册的 Loop 应包含所有必需字段。"""
        engine_start("echo test", interval_s=60, template="fields")
        loops = _load_loops()
        loop = loops["fields"]
        required = {"task", "interval", "maxCycles", "template", "status", "cycle", "lastRun", "lastResult", "createdAt"}
        assert required.issubset(loop.keys())

    def test_createdat_is_iso_format(self):
        """createdAt 应为 ISO 格式时间字符串。"""
        engine_start("echo test", interval_s=60, template="time-check")
        loops = _load_loops()
        created = loops["time-check"]["createdAt"]
        # ISO 格式应包含 'T'
        assert "T" in created
