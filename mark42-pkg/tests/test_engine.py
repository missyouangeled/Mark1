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
    _check_template_files_changed,
    _get_templates_cached,
    _load_loops,
    _load_templates,
    _save_loops,
    _template_exists,
    engine_kill,
    engine_reload_templates,
    engine_run_loop,
    engine_start,
    engine_templates,
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
        required = {
            "task",
            "interval",
            "maxCycles",
            "template",
            "status",
            "cycle",
            "lastRun",
            "lastResult",
            "createdAt",
        }
        assert required.issubset(loop.keys())

    def test_createdat_is_iso_format(self):
        """createdAt 应为 ISO 格式时间字符串。"""
        engine_start("echo test", interval_s=60, template="time-check")
        loops = _load_loops()
        created = loops["time-check"]["createdAt"]
        # ISO 格式应包含 'T'
        assert "T" in created


# ── 模板相关函数测试 ───────────────────────────────────────


class TestTemplateFunctions:
    def test_load_templates_returns_builtin_when_no_files(self, monkeypatch, tmp_path):
        """无模板文件时应只返回内置模板。"""
        from mark42 import engine as eng_mod

        # mock 路径到不存在的位置
        nonexistent = tmp_path / "nonexistent"
        monkeypatch.setattr(eng_mod, "LOOP_TEMPLATES_PATH", nonexistent / "loop_templates.yaml")
        monkeypatch.setattr(eng_mod, "USER_LOOP_TEMPLATES_PATH", nonexistent / "user_templates.yaml")

        templates = _load_templates()
        assert len(templates) > 0
        assert "context-guard" in templates
        assert "task-watch" in templates

    def test_template_exists_returns_true_for_builtin(self):
        """内置模板应存在。"""
        assert _template_exists("context-guard") is True

    def test_template_exists_returns_false_for_unknown(self):
        """未知模板名应返回 False。"""
        assert _template_exists("nonexistent-template-12345") is False

    def test_get_templates_cached_returns_same(self):
        """缓存模板应返回相同对象。"""
        t1 = _get_templates_cached()
        t2 = _get_templates_cached()
        # 应该是同一个缓存对象
        assert t1 is t2

    def test_engine_reload_templates_returns_correct_structure(self):
        """reload_templates 应返回正确结构。"""
        result = engine_reload_templates()
        assert "oldCount" in result
        assert "newCount" in result
        assert "templates" in result
        assert isinstance(result["templates"], list)
        assert len(result["templates"]) > 0

    def test_check_template_files_changed_first_call(self, monkeypatch):
        """首次调用 check_template_files_changed 不应视为变更。"""
        # 清除 mtime 缓存
        from mark42 import engine
        engine._template_mtimes.clear()

        changed = _check_template_files_changed()
        # 首次调用只记录 mtime，不返回 changed=True
        assert changed is False


# ── engine_templates 打印函数测试 ──────────────────────────


class TestEngineTemplatesPrint:
    def test_engine_templates_does_not_crash(self, capsys):
        """engine_templates 打印不应崩溃。"""
        engine_templates()
        captured = capsys.readouterr()
        # 应该有输出
        assert len(captured.out) > 0
        # 应该包含模板名
        assert "context-guard" in captured.out


# ── engine_run_loop 核心执行测试 ───────────────────────────


class TestEngineRunLoop:
    def test_run_nonexistent_loop_prints_error(self, capsys):
        """执行不存在的 Loop 应打印错误。"""
        engine_run_loop("nonexistent-loop-12345")
        captured = capsys.readouterr()
        assert "不存在" in captured.out

    def test_run_loop_updates_cycle(self):
        """执行后 cycle 应 +1。"""
        engine_start("echo test", interval_s=60, template="run-test")
        loops_before = _load_loops()
        assert loops_before["run-test"]["cycle"] == 0

        engine_run_loop("run-test")

        loops_after = _load_loops()
        assert loops_after["run-test"]["cycle"] == 1

    def test_run_loop_updates_status(self):
        """执行中状态应为 running，完成后应为 registered。"""
        engine_start("echo test", interval_s=60, template="status-test")

        engine_run_loop("status-test")

        loops = _load_loops()
        # 完成后应回到 registered 状态（等待下一次）
        assert loops["status-test"]["status"] == "registered"

    def test_run_loop_updates_last_run(self):
        """执行后 lastRun 应更新。"""
        engine_start("echo test", interval_s=60, template="lastrun-test")
        loops_before = _load_loops()
        assert loops_before["lastrun-test"]["lastRun"] is None

        engine_run_loop("lastrun-test")

        loops_after = _load_loops()
        assert loops_after["lastrun-test"]["lastRun"] is not None

    def test_run_loop_completes_when_max_cycles_reached(self):
        """达到最大循环次数后状态应为 completed。"""
        engine_start("echo test", interval_s=60, max_cycles=1, template="max-cycle-test")

        engine_run_loop("max-cycle-test")

        loops = _load_loops()
        assert loops["max-cycle-test"]["status"] == "completed"

    def test_run_loop_with_persist_false(self):
        """persist=False 不应写入磁盘。"""
        engine_start("echo test", interval_s=60, template="persist-test")
        loops_before = _load_loops()

        # 传一个新的 dict 作为 _loops，persist=False
        test_loops = dict(loops_before)
        engine_run_loop("persist-test", persist=False, _loops=test_loops)

        # 磁盘上的状态不应改变（cycle 仍为 0）
        loops_disk = _load_loops()
        assert loops_disk["persist-test"]["cycle"] == 0
        # 但传入的 dict 应已更新
        assert test_loops["persist-test"]["cycle"] == 1


# ── engine_watch_task 测试 ─────────────────────────────────


class TestEngineWatchTask:
    def test_watch_nonexistent_task_prints_error(self, capsys, monkeypatch, tmp_path):
        """监控不存在的任务应打印错误。"""
        from mark42.engine import engine_watch_task
        from mark42 import engine as eng_mod

        # mock SCRATCH 到 tmp_path（空目录）
        monkeypatch.setattr(eng_mod, "SCRATCH", tmp_path)

        engine_watch_task("nonexistent-task-12345")
        captured = capsys.readouterr()
        assert "不存在" in captured.out

    def test_watch_exits_on_completion(self, capsys, monkeypatch, tmp_path):
        """任务完成时应退出循环。"""
        from mark42.engine import engine_watch_task
        from mark42 import engine as eng_mod
        import json

        # mock SCRATCH
        monkeypatch.setattr(eng_mod, "SCRATCH", tmp_path)
        # mock _append_broker 避免写入真实文件
        monkeypatch.setattr(eng_mod, "_append_broker", lambda *args, **kwargs: None)

        # 创建任务状态文件（所有子任务已完成）
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        status_file = task_dir / "status.json"
        status_data = {
            "subtasks": {
                "sub1": {"status": "done"},
                "sub2": {"status": "done"},
            }
        }
        with open(status_file, "w") as f:
            json.dump(status_data, f)

        engine_watch_task("test-task", interval_s=0)
        captured = capsys.readouterr()

        assert "已完成" in captured.out


# ── engine_list 打印测试 ───────────────────────────────────


class TestEngineList:
    def test_engine_list_empty_does_not_crash(self, capsys):
        """无 Loop 时打印不应崩溃。"""
        from mark42.engine import engine_list

        engine_list()
        captured = capsys.readouterr()
        assert "暂无活跃 Loop" in captured.out

    def test_engine_list_with_loop_does_not_crash(self, capsys):
        """有 Loop 时打印不应崩溃。"""
        from mark42.engine import engine_list

        engine_start("echo test", interval_s=60, template="list-test")
        engine_list()
        captured = capsys.readouterr()

        assert "list-test" in captured.out
        assert "周期:" in captured.out
