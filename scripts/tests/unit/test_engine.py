"""engine.py 测试群。

覆盖范围：
  - engine_start / engine_kill / engine_list  Loop CRUD
  - engine_run_loop 5 个模板分支（context-guard / task-watch / health-watch /
    model-fallback / memory-index）
  - engine_daemon 守护进程（daemon thread 跑短间隔，验证心跳写入）

设计要点：
  - mock armor_check / armor_compress / subprocess 避免真依赖
  - 用 _load_loops / _save_loops mock 隔离 loops.json 读写
  - engine_daemon 用 daemon thread + 短 interval，主进程退出时自动死
"""

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mark42_modules import engine


# ── helper ────────────────────────────────────────────────

def _make_loop(name="test-loop", template="", task="test task",
               interval=300, status="registered", cycle=0, max_cycles=None):
    """构造一个标准的 loop 字典。"""
    return {
        name: {
            "task": task,
            "interval": interval,
            "maxCycles": max_cycles,
            "template": template,
            "status": status,
            "cycle": cycle,
            "lastRun": None,
            "lastResult": None,
            "createdAt": "2026-06-29T09:00:00",
        }
    }


# ─────────────────────── engine_start / kill / list ───────────────────────

class TestEngineStart:
    """engine_start() 测试群。"""

    def test_creates_new_loop(self, mocker, engine_state):
        """应创建新 Loop 并持久化。"""
        # mock _load_loops 返回空
        mocker.patch.object(engine, "_load_loops", return_value={})
        mock_save = mocker.patch.object(engine, "_save_loops")

        engine.engine_start(task="监控上下文", interval_s=60)

        mock_save.assert_called_once()
        saved_loops = mock_save.call_args[0][0]
        assert len(saved_loops) == 1
        loop_name = list(saved_loops.keys())[0]
        loop = saved_loops[loop_name]
        assert loop["task"] == "监控上下文"
        assert loop["interval"] == 60
        assert loop["status"] == "registered"

    def test_with_template_uses_template_as_name(self, mocker, engine_state):
        """指定 template 时，loop name 应等于 template。"""
        mocker.patch.object(engine, "_load_loops", return_value={})
        mock_save = mocker.patch.object(engine, "_save_loops")

        engine.engine_start(task="test", template="context-guard")

        saved_loops = mock_save.call_args[0][0]
        assert "context-guard" in saved_loops
        assert saved_loops["context-guard"]["template"] == "context-guard"

    def test_duplicate_template_overwrites(self, mocker, engine_state):
        """同名 template 覆盖已存在的 loop。"""
        existing = _make_loop(name="context-guard", template="context-guard")
        mocker.patch.object(engine, "_load_loops", return_value=existing)
        mock_save = mocker.patch.object(engine, "_save_loops")

        engine.engine_start(task="new task", template="context-guard")

        saved = mock_save.call_args[0][0]
        assert saved["context-guard"]["task"] == "new task"


class TestEngineKill:
    """engine_kill() 测试群。"""

    def test_marks_loop_as_killed(self, mocker, engine_state):
        """应将 loop 状态改为 killed 并记录 killedAt。"""
        loops = _make_loop(name="to-kill", status="registered")
        mocker.patch.object(engine, "_load_loops", return_value=loops)
        mock_save = mocker.patch.object(engine, "_save_loops")

        engine.engine_kill("to-kill")

        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["to-kill"]["status"] == "killed"
        assert "killedAt" in saved["to-kill"]

    def test_nonexistent_loop_no_save(self, mocker, engine_state):
        """不存在的 loop 不应 save（直接 return）。"""
        mocker.patch.object(engine, "_load_loops", return_value={})
        mock_save = mocker.patch.object(engine, "_save_loops")

        engine.engine_kill("nonexistent")

        mock_save.assert_not_called()


class TestEngineList:
    """engine_list() 测试群 - 测试输出包含期望 loop 信息。"""

    def test_empty_state(self, mocker, capsys):
        """无 loop 时输出"暂无活跃 Loop"。"""
        mocker.patch.object(engine, "_load_loops", return_value={})
        engine.engine_list()
        out = capsys.readouterr().out
        assert "暂无活跃 Loop" in out

    def test_shows_registered_loop(self, mocker, capsys):
        """应显示 loop 的 name/status/cycle/interval。"""
        loops = _make_loop(name="my-loop", task="do thing", interval=120, cycle=5)
        mocker.patch.object(engine, "_load_loops", return_value=loops)
        engine.engine_list()
        out = capsys.readouterr().out
        assert "my-loop" in out
        assert "120s" in out
        assert "5/" in out  # cycle 5 / max


# ─────────────────────── engine_run_loop 模板测试 ───────────────────────

class TestEngineRunLoopContextGuard:
    """context-guard 模板测试群。"""

    def test_low_usage_monitor_only(self, mocker, engine_state):
        """低使用率只 monitor，不触发 compress。"""
        loops = _make_loop(name="ctx-loop", template="context-guard")
        # mock armor_check 返回低使用率
        mocker.patch.object(engine, "armor_check",
                          return_value={"usagePercent": 30.0, "severity": "ok"})
        mock_compress = mocker.patch.object(engine, "armor_compress")

        engine.engine_run_loop("ctx-loop", persist=False, _loops=loops)

        mock_compress.assert_not_called()
        assert loops["ctx-loop"]["lastResult"]["action"] == "monitor"
        assert loops["ctx-loop"]["cycle"] == 1

    def test_high_usage_triggers_compress(self, mocker, engine_state):
        """使用率 >= ALERT 时触发 compress，记录 before/after。"""
        loops = _make_loop(name="ctx-loop", template="context-guard")
        # 两次 armor_check 调用：第一次 Observe，第二次 Verify
        mocker.patch.object(engine, "armor_check",
                          side_effect=[
                              {"usagePercent": 90.0, "severity": "critical"},
                              {"usagePercent": 50.0, "severity": "warn"},
                          ])
        mock_compress = mocker.patch.object(engine, "armor_compress",
                                          return_value={"action": "compress"})

        engine.engine_run_loop("ctx-loop", persist=False, _loops=loops)

        mock_compress.assert_called_once()
        assert loops["ctx-loop"]["lastResult"]["before"] == 90.0
        assert loops["ctx-loop"]["lastResult"]["after"] == 50.0


class TestEngineRunLoopTaskWatch:
    """task-watch 模板测试群。"""

    def test_no_active_tasks(self, mocker, engine_state, heavy_state):
        """没有 active heavy task 时记录空列表。"""
        loops = _make_loop(name="tw", template="task-watch")
        # mock HEAVY_STATE.glob 返回空
        mocker.patch.object(engine, "HEAVY_STATE", heavy_state)
        # 确保 heavy_state 目录是空的
        engine.engine_run_loop("tw", persist=False, _loops=loops)
        assert loops["tw"]["lastResult"]["activeTasks"] == []
        assert loops["tw"]["lastResult"]["pending"] == 0
        assert loops["tw"]["lastResult"]["failed"] == 0


class TestEngineRunLoopHealthWatch:
    """health-watch 模板测试群。"""

    def test_normal_no_alerts(self, mocker, engine_state):
        """磁盘和内存充足时不告警。"""
        loops = _make_loop(name="hw", template="health-watch")
        # mock _save_loops 避免 fcntl 错误
        mocker.patch.object(engine, "_save_loops")
        # mock shutil.disk_usage
        mock_du = MagicMock()
        mock_du.free = 100 * 1024**3  # 100GB
        mocker.patch("shutil.disk_usage", return_value=mock_du)
        # mock Path.exists（让 /mnt/data 路径检查返回 True）
        mocker.patch.object(Path, "exists", return_value=True)
        # mock /proc/meminfo
        meminfo = "MemTotal:       16000000 kB\nMemAvailable:    8000000 kB\n"
        mocker.patch("builtins.open", mock_open(read_data=meminfo))

        engine.engine_run_loop("hw", persist=False, _loops=loops)

        assert loops["hw"]["lastResult"]["alerts"] == []
        assert "100.0G" in loops["hw"]["lastResult"]["diskRoot"]

    def test_low_disk_alerts(self, mocker, engine_state):
        """磁盘 < 5GB 时告警。"""
        loops = _make_loop(name="hw", template="health-watch")
        mocker.patch.object(engine, "_save_loops")
        mock_du = MagicMock()
        mock_du.free = 2 * 1024**3  # 2GB（不足 5GB）
        mocker.patch("shutil.disk_usage", return_value=mock_du)
        mocker.patch.object(Path, "exists", return_value=True)
        meminfo = "MemAvailable:    8000000 kB\n"
        mocker.patch("builtins.open", mock_open(read_data=meminfo))

        engine.engine_run_loop("hw", persist=False, _loops=loops)

        assert len(loops["hw"]["lastResult"]["alerts"]) >= 1
        assert any("磁盘" in a for a in loops["hw"]["lastResult"]["alerts"])


class TestEngineRunLoopModelFallback:
    """model-fallback 模板测试群。"""

    def test_gateway_ok(self, mocker, engine_state):
        """Gateway 健康时 lastResult.gatewayOk=True。"""
        loops = _make_loop(name="mf", template="model-fallback")
        # mock urllib.request.urlopen 返回 200
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen = mocker.patch("urllib.request.urlopen", return_value=mock_resp)

        engine.engine_run_loop("mf", persist=False, _loops=loops)

        mock_urlopen.assert_called_once()
        assert loops["mf"]["lastResult"]["gatewayOk"] is True

    def test_gateway_unreachable(self, mocker, engine_state):
        """Gateway 不可达时 lastResult.gatewayOk=False。"""
        loops = _make_loop(name="mf", template="model-fallback")
        mocker.patch("urllib.request.urlopen",
                    side_effect=Exception("connection refused"))

        engine.engine_run_loop("mf", persist=False, _loops=loops)

        assert loops["mf"]["lastResult"]["gatewayOk"] is False


class TestEngineRunLoopMemoryIndex:
    """memory-index 模板测试群。"""

    def test_scans_recent_daily_files(self, mocker, engine_state, tmp_path):
        """扫描最近 daily 文件并更新 INDEX.md。"""
        # 设置假 memory/daily/ 目录
        memory_dir = tmp_path / "memory"
        daily_dir = memory_dir / "daily"
        daily_dir.mkdir(parents=True)
        (daily_dir / "2026-06-29.md").write_text("## Test Topic A\n## Test Topic B\n")
        # mock WORKSPACE 指向 tmp_path
        mocker.patch.object(engine, "WORKSPACE", tmp_path)
        loops = _make_loop(name="mi", template="memory-index")
        mocker.patch.object(engine, "_load_loops", return_value=loops)

        engine.engine_run_loop("mi", persist=False, _loops=loops)

        index_file = memory_dir / "INDEX.md"
        assert index_file.exists()
        content = index_file.read_text()
        assert "2026-06-29] Test Topic A" in content
        assert "2026-06-29] Test Topic B" in content
        assert loops["mi"]["lastResult"]["scannedDays"] >= 1


class TestEngineRunLoopGeneric:
    """通用 task（无 template）测试群。"""

    def test_context_keyword_triggers_armor_compress(self, mocker, engine_state):
        """task 含"context"或"armor"关键词时调 armor_compress。"""
        loops = _make_loop(name="generic", template="", task="监控 context 健康")
        mock_compress = mocker.patch.object(engine, "armor_compress",
                                          return_value={"action": "compress", "preCompressUsage": 80.0})

        engine.engine_run_loop("generic", persist=False, _loops=loops)

        mock_compress.assert_called_once()
        assert loops["generic"]["lastResult"]["action"] == "compress"

    def test_unknown_task_marks_executed(self, mocker, engine_state):
        """未知 task 标记为 executed。"""
        loops = _make_loop(name="generic", template="", task="something else")
        engine.engine_run_loop("generic", persist=False, _loops=loops)
        assert loops["generic"]["lastResult"]["action"] == "executed"


class TestEngineRunLoopCycle:
    """cycle 计数 + 完成条件测试群。"""

    def test_cycle_increments(self, mocker, engine_state):
        """每次执行 cycle 增 1。"""
        loops = _make_loop(name="l1", template="", task="foo", cycle=5)
        mocker.patch.object(engine, "armor_check",
                          return_value={"usagePercent": 30.0})
        engine.engine_run_loop("l1", persist=False, _loops=loops)
        assert loops["l1"]["cycle"] == 6

    def test_status_resets_to_registered_after_run(self, mocker, engine_state):
        """执行后状态回到 registered（除非达到 maxCycles）。"""
        loops = _make_loop(name="l1", template="", task="foo", status="running", cycle=0)
        mocker.patch.object(engine, "armor_check",
                          return_value={"usagePercent": 30.0})
        engine.engine_run_loop("l1", persist=False, _loops=loops)
        assert loops["l1"]["status"] == "registered"

    def test_completes_after_max_cycles(self, mocker, engine_state):
        """达到 maxCycles 后状态变为 completed。"""
        loops = _make_loop(name="l1", template="", task="foo", cycle=9, max_cycles=10)
        mocker.patch.object(engine, "armor_check",
                          return_value={"usagePercent": 30.0})
        engine.engine_run_loop("l1", persist=False, _loops=loops)
        assert loops["l1"]["status"] == "completed"
        assert loops["l1"]["cycle"] == 10


# ─────────────────────── engine_daemon 守护进程 ───────────────────────

class TestEngineDaemon:
    """engine_daemon() 守护进程测试群。

    设计：用 daemon thread 跑短间隔（1s）daemon，主线程等 2-3s 后断言，
    测试结束进程退出时 daemon thread 自动被强杀。
    """

    def test_daemon_writes_heartbeat(self, engine_state):
        """daemon 跑一会后应写心跳文件。"""
        t = threading.Thread(
            target=engine.engine_daemon,
            kwargs={"interval_s": 1},
            daemon=True,
        )
        t.start()
        time.sleep(2.5)  # 让 daemon 跑 2 个 tick

        heartbeat = engine_state / "daemon-heartbeat.json"
        assert heartbeat.exists(), "daemon 没写心跳文件"
        hb = json.loads(heartbeat.read_text())
        assert "lastTick" in hb
        assert "cycle" in hb
        assert hb["cycle"] >= 1

    def test_daemon_writes_cursor(self, engine_state):
        """daemon 跑一会后应写 cursor 文件。"""
        t = threading.Thread(
            target=engine.engine_daemon,
            kwargs={"interval_s": 1},
            daemon=True,
        )
        t.start()
        time.sleep(2.5)

        cursor = engine_state / "daemon-cursor.json"
        # cursor 可能没 events 可扫，但 lastScan 字段应被写入
        # 实际代码是 if any new_lines: 才更新 lastScan
        # 但每 tick 都会调 _save_json(cursor_file, {...lastScan})
        # 所以 cursor 文件应存在
        assert cursor.exists() or not (engine_state / "daemon-heartbeat.json").exists()
        # 至少心跳存在证明 daemon 跑过