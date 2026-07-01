"""cli.py 测试群。

覆盖范围：
  - status_dashboard(json_mode=True)  聚合状态返回 dict
  - status_dashboard(json_mode=False) 人类可读输出（capsys 验证）
  - main() argparse 分发到各模块
  - assemble() 启动入口（mock subprocess.Popen）

设计要点：
  - status_dashboard 内部 `from .config import XXX` + `from .armor import YYY`，
    所以 mock target 用完整模块路径如 "mark42_modules.armor.armor_check"
  - main() 内部 argparse 读 sys.argv，用 monkeypatch.setattr(sys, "argv", [...])
  - assemble() fork 子进程，必须 mock subprocess.Popen（target 是全局 "subprocess.Popen"）
"""

import sys
from unittest.mock import MagicMock, mock_open

import pytest

from mark42_modules import cli


# ─────────────────────── 公共 mock helper ───────────────────────

def _mock_status_dashboard_deps(mocker, usage=30.0, loops=None,
                                broker_lines=10, scratch_exists=True,
                                heavy_tasks=None, version="2.3.3",
                                armor_index_data=None):
    """为 status_dashboard 测试统一 mock 所有依赖。

    用 _mock_kind 标识路径类型，让 _load_json side_effect 能正确分流。
    """
    # armor
    mocker.patch("mark42_modules.armor.armor_check", return_value={
        "usagePercent": usage, "status": "ok", "severity": "ok",
        "summary": f"上下文 {usage}%，正常", "contextWindow": 131072,
        "estimatedTokens": int(usage / 100 * 131072),
    })

    # config 路径对象，用 _mock_kind 标识
    fake_scratch = MagicMock()
    fake_scratch.exists.return_value = scratch_exists
    fake_scratch._mock_kind = "scratch"
    fake_scratch.__iter__ = lambda self: iter([])
    mocker.patch("mark42_modules.config.SCRATCH", fake_scratch)

    fake_broker_events = MagicMock()
    fake_broker_events.exists.return_value = True
    fake_broker_events.stat.return_value.st_size = broker_lines * 100
    mocker.patch("mark42_modules.config.MARK42_BROKER_EVENTS", fake_broker_events)

    fake_armor_state = MagicMock()
    fake_armor_state._mock_kind = "armor-state"
    # ARMOR_STATE / "memory-index.json" 返回 memory_index_mock
    memory_index_mock = MagicMock()
    memory_index_mock._mock_kind = "memory-index"
    memory_index_mock.exists.return_value = armor_index_data is not None
    fake_armor_state.__truediv__ = lambda self, x: (
        memory_index_mock if "memory-index" in str(x) else MagicMock()
    )
    mocker.patch("mark42_modules.config.ARMOR_STATE", fake_armor_state)

    fake_cfg_path = MagicMock()
    fake_cfg_path.exists.return_value = True
    fake_cfg_path._mock_kind = "config"
    mocker.patch("mark42_modules.config.CONFIG_PATH", fake_cfg_path)

    mocker.patch("mark42_modules.config.THRESHOLD_WARN", 70.0)
    mocker.patch("mark42_modules.config.THRESHOLD_ALERT", 85.0)

    fake_engine_state = MagicMock()
    fake_engine_state._mock_kind = "engine-state"
    # ENGINE_STATE / "loops.json" 返回 loops_path
    loops_path = MagicMock()
    loops_path._mock_kind = "loops"
    fake_engine_state.__truediv__ = lambda self, x: (
        loops_path if "loops" in str(x) else MagicMock()
    )
    mocker.patch("mark42_modules.config.ENGINE_STATE", fake_engine_state)

    fake_heavy_state = MagicMock()
    fake_heavy_state._mock_kind = "heavy-state"
    fake_heavy_state.glob.return_value = list(heavy_tasks or [])
    # 给每个 heavy task 文件标记 kind
    for t in (heavy_tasks or []):
        t._mock_kind = "heavy-task"
        if not hasattr(t, "name") or not isinstance(t.name, str):
            t.name = "task1.json"
    mocker.patch("mark42_modules.config.HEAVY_STATE", fake_heavy_state)

    # utils._load_json: 按 _mock_kind 返回不同值
    def load_side_effect(path, *args, **kwargs):
        kind = getattr(path, "_mock_kind", None)
        if kind == "config":
            return {"version": version}
        if kind == "memory-index":
            return armor_index_data
        if kind == "loops":
            return loops or {}
        if kind == "heavy-task":
            return {"taskName": "t", "status": "started", "summary": "x"}
        return {}

    mocker.patch("mark42_modules.utils._load_json", side_effect=load_side_effect)

    # logs
    mocker.patch("mark42_modules.logs._load_state", return_value={
        "lastRotation": "2026-06-29T09:00:00", "rotationCount": 100,
    })

    mocker.patch("builtins.open", mock_open(read_data="\n" * broker_lines))

    return mocker


# ─────────────────────── status_dashboard JSON 模式 ───────────────────────

class TestStatusDashboardJson:
    """status_dashboard(json_mode=True) 返回 dict 测试群。"""

    def test_returns_dict_with_all_sections(self, mocker):
        """返回的 dict 应包含 armor/engine/heavy/logs/broker/scratch/actions。"""
        _mock_status_dashboard_deps(mocker)
        result = cli.status_dashboard(json_mode=True)
        assert isinstance(result, dict)
        for key in ["checkedAt", "version", "armor", "engine", "heavy",
                   "logs", "broker", "scratch", "actions"]:
            assert key in result, f"缺少 {key}"

    def test_high_usage_suggests_compact(self, mocker):
        """使用率 >= WARN 时建议 /compact。"""
        _mock_status_dashboard_deps(mocker, usage=85.0)
        result = cli.status_dashboard(json_mode=True)
        assert any("/compact" in a for a in result["actions"])

    def test_no_active_loops_suggests_start(self, mocker):
        """引擎空闲时建议注册 Loop。"""
        _mock_status_dashboard_deps(mocker, loops={})
        result = cli.status_dashboard(json_mode=True)
        assert any("引擎空闲" in a or "Loop" in a for a in result["actions"])

    def test_version_from_config(self, mocker):
        """version 应从 CONFIG_PATH 读取。"""
        _mock_status_dashboard_deps(mocker, version="2.5.0")
        result = cli.status_dashboard(json_mode=True)
        assert result["version"] == "2.5.0"

    def test_armor_section_includes_memory_index(self, mocker):
        """有 memory-index 时 armor.memoryIndex 应有内容。"""
        _mock_status_dashboard_deps(mocker,
            armor_index_data={
                "strategyUsed": "llm-analyze",
                "generatedAt": "2026-06-29T08:00:00",
                "modelGenerated": True,
            })
        result = cli.status_dashboard(json_mode=True)
        assert result["armor"]["memoryIndex"] is not None
        assert result["armor"]["memoryIndex"]["strategy"] == "llm-analyze"

    def test_engine_section_lists_loops(self, mocker):
        """engine.loops 应列出所有 loop 的状态。"""
        loops = {
            "loop1": {"status": "registered", "template": "context-guard",
                     "cycle": 3, "maxCycles": None, "task": "x",
                     "lastRun": "2026-06-29T08:00:00"},
            "loop2": {"status": "killed", "template": "",
                     "cycle": 0, "maxCycles": 10, "task": "y",
                     "lastRun": None},
        }
        _mock_status_dashboard_deps(mocker, loops=loops)
        result = cli.status_dashboard(json_mode=True)
        assert "loop1" in result["engine"]["loops"]
        assert "loop2" in result["engine"]["loops"]
        assert result["engine"]["activeLoops"] == 1

    def test_heavy_section_lists_tasks(self, mocker):
        """heavy.activeTasks 应列出所有 heavy 任务。"""
        task_files = [MagicMock(), MagicMock()]
        _mock_status_dashboard_deps(mocker, heavy_tasks=task_files)
        result = cli.status_dashboard(json_mode=True)
        assert len(result["heavy"]["activeTasks"]) == 2

    def test_broker_stats_included(self, mocker):
        """broker.mark42Events 应有行数。"""
        _mock_status_dashboard_deps(mocker, broker_lines=42)
        result = cli.status_dashboard(json_mode=True)
        assert "mark42Events" in result["broker"]


# ─────────────────────── status_dashboard 人类可读模式 ───────────────────────

class TestStatusDashboardHuman:
    """status_dashboard(json_mode=False) 输出格式测试群。"""

    def test_prints_dashboard(self, mocker, capsys):
        """应打印 dashboard 标题 + 各 section。"""
        _mock_status_dashboard_deps(mocker)
        cli.status_dashboard(json_mode=False)
        out = capsys.readouterr().out
        assert "🦾 Mark42 系统状态" in out
        assert "🛡️ 上下文铠甲" in out
        assert "🔄 循环引擎" in out
        assert "⚙️ 重型战甲" in out

    def test_returns_none_in_human_mode(self, mocker):
        """json_mode=False 时返回 None。"""
        _mock_status_dashboard_deps(mocker)
        result = cli.status_dashboard(json_mode=False)
        assert result is None


# ─────────────────────── main() argparse 分发 ───────────────────────

class TestMainDispatch:
    """main() argparse 分发测试群。"""

    def test_no_args_prints_help(self, mocker, capsys):
        """无参数时打印 help。"""
        mocker.patch.object(sys, "argv", ["mark42.py"])
        mocker.patch("mark42_modules.config.mark42_init")
        mocker.patch("mark42_modules.config.mark42_config")
        mocker.patch("mark42_modules.compaction_diag.compaction_apply")
        cli.main()
        out = capsys.readouterr().out
        assert "Mark42" in out

    def test_init_runs_mark42_init(self, mocker):
        """--init 应调 mark42_init。"""
        mocker.patch.object(sys, "argv", ["mark42.py", "--init"])
        mock_init = mocker.patch("mark42_modules.config.mark42_init")
        cli.main()
        mock_init.assert_called_once()

    def test_config_runs_mark42_config(self, mocker):
        """--config 应调 mark42_config。"""
        mocker.patch.object(sys, "argv", ["mark42.py", "--config"])
        mock_cfg = mocker.patch("mark42_modules.config.mark42_config")
        cli.main()
        mock_cfg.assert_called_once()

    def test_armor_check_dispatches(self, mocker):
        """armor --check 应调 armor_check。"""
        mocker.patch.object(sys, "argv", ["mark42.py", "armor", "--check"])
        mock_check = mocker.patch("mark42_modules.armor.armor_check",
                                 return_value={
                                     "usagePercent": 30.0, "status": "ok",
                                     "severity": "ok", "summary": "x",
                                     "contextWindow": 131072,
                                     "estimatedTokens": 1000,
                                 })
        cli.main()
        mock_check.assert_called_once()

    def test_armor_compress_with_dry_run(self, mocker):
        """armor --compress --dry-run 应调 armor_compress(dry_run=True)。"""
        mocker.patch.object(sys, "argv",
                          ["mark42.py", "armor", "--compress", "--dry-run"])
        mock_compress = mocker.patch("mark42_modules.armor.armor_compress",
                                    return_value={"action": "compress"})
        cli.main()
        mock_compress.assert_called_once()
        call_args = mock_compress.call_args
        dry_run = call_args.kwargs.get("dry_run") or (
            len(call_args.args) >= 1 and call_args.args[0] is True
        )
        assert dry_run is True


# ─────────────────────── assemble() 启动入口 ───────────────────────

class TestAssemble:
    """assemble() 启动入口测试群。"""

    def test_assemble_exits_cleanly_when_no_state(self, mocker):
        """无 ARMOR_STATE 时应自动 mark42_init 然后报错退出。"""
        fake_armor = MagicMock()
        fake_armor.exists.return_value = False
        mocker.patch("mark42_modules.config.ARMOR_STATE", fake_armor)
        mock_init = mocker.patch("mark42_modules.config.mark42_init")
        mocker.patch("mark42_modules.armor.armor_check",
                          return_value={"usagePercent": 30.0, "summary": "x"})
        mock_popen = mocker.patch("subprocess.Popen")
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_popen.return_value = mock_proc
        mocker.patch("os.kill", return_value=0)
        mocker.patch("signal.signal")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch.object(cli, "_trim_daemon_logs")

        try:
            cli.assemble()
        except (KeyboardInterrupt, SystemExit):
            pass

        mock_init.assert_called_once()
        assert mock_popen.call_count >= 2


class TestTrimDaemonLogs:
    """_trim_daemon_logs() 日志截尾逻辑。"""

    def test_trims_large_log_file(self, mocker, capsys):
        fake_log = MagicMock()
        fake_log.name = "engine-daemon.log"
        fake_log.stat.return_value.st_size = 5 * 1024 * 1024

        fake_dir = MagicMock()
        fake_dir.glob.return_value = [fake_log]

        mocker.patch("mark42_modules.config.MAX_DAEMON_LOG_MB", 1)
        mocker.patch("mark42_modules.config.MAX_DAEMON_LOG_LINES", 10)
        mocker.patch(
            "builtins.open",
            mock_open(read_data="".join(f"line{i}\n" for i in range(12))),
        )

        cli._trim_daemon_logs(fake_dir)

        out = capsys.readouterr().out
        assert "🧹 截尾 engine-daemon.log" in out
        assert "5 行" in out

    def test_skips_small_log_file(self, mocker):
        fake_log = MagicMock()
        fake_log.name = "small.log"
        fake_log.stat.return_value.st_size = 100

        fake_dir = MagicMock()
        fake_dir.glob.return_value = [fake_log]

        mocker.patch("mark42_modules.config.MAX_DAEMON_LOG_MB", 1)
        mocker.patch("mark42_modules.config.MAX_DAEMON_LOG_LINES", 10)
        open_mock = mocker.patch("builtins.open", mock_open(read_data="x\n"))

        cli._trim_daemon_logs(fake_dir)

        open_mock.assert_not_called()

    def test_ignores_oserror(self, mocker):
        fake_log = MagicMock()
        fake_log.stat.side_effect = OSError("boom")

        fake_dir = MagicMock()
        fake_dir.glob.return_value = [fake_log]

        cli._trim_daemon_logs(fake_dir)


class TestMainDispatchExtra:
    """补 main() 里现有未覆盖的高价值分发。"""

    def test_logs_rotate_dispatches(self, mocker):
        mocker.patch.object(sys, "argv", ["mark42.py", "logs", "--rotate"])
        mock_rotate = mocker.patch("mark42_modules.logs.log_rotate")
        mock_status = mocker.patch("mark42_modules.logs.log_rotate_status")

        cli.main()

        mock_rotate.assert_called_once_with("all")
        mock_status.assert_not_called()

    def test_logs_status_dispatches(self, mocker):
        mocker.patch.object(sys, "argv", ["mark42.py", "logs", "--status"])
        mock_rotate = mocker.patch("mark42_modules.logs.log_rotate")
        mock_status = mocker.patch("mark42_modules.logs.log_rotate_status")

        cli.main()

        mock_rotate.assert_not_called()
        mock_status.assert_called_once()

    def test_engine_start_dispatches(self, mocker):
        mocker.patch.object(
            sys,
            "argv",
            [
                "mark42.py", "engine", "--start",
                "--task", "监控上下文",
                "--interval", "60",
                "--max-cycles", "3",
                "--template", "context-guard",
            ],
        )
        mock_start = mocker.patch("mark42_modules.engine.engine_start")

        cli.main()

        mock_start.assert_called_once_with(
            task="监控上下文",
            interval_s=60,
            max_cycles=3,
            template="context-guard",
        )

    def test_engine_daemon_dispatches(self, mocker):
        mocker.patch.object(sys, "argv", ["mark42.py", "engine", "--daemon", "--interval", "45"])
        mock_daemon = mocker.patch("mark42_modules.engine.engine_daemon")

        cli.main()

        mock_daemon.assert_called_once_with(45)

    def test_engine_watch_task_dispatches(self, mocker):
        mocker.patch.object(sys, "argv", ["mark42.py", "engine", "--watch-task", "big-proj", "--interval", "120"])
        mock_watch = mocker.patch("mark42_modules.engine.engine_watch_task")

        cli.main()

        mock_watch.assert_called_once_with("big-proj", interval_s=120)

    def test_heavy_start_dispatches_context_toggle(self, mocker):
        mocker.patch.object(
            sys,
            "argv",
            [
                "mark42.py", "heavy", "--start", "/tmp/proj",
                "--task-name", "big-task", "--no-context-aware",
            ],
        )
        mock_start = mocker.patch("mark42_modules.heavy.heavy_start")

        cli.main()

        mock_start.assert_called_once_with("/tmp/proj", "big-task", context_aware=False)

    def test_heavy_execute_dispatches(self, mocker):
        mocker.patch.object(
            sys,
            "argv",
            [
                "mark42.py", "heavy", "--execute", "--task-name", "big-task",
                "--batch", "b1", "--command", "python {f}", "--execute-now",
            ],
        )
        mock_execute = mocker.patch("mark42_modules.heavy.heavy_execute")

        cli.main()

        mock_execute.assert_called_once_with(
            "big-task", "b1", command="python {f}", execute_now=True
        )

    def test_heavy_execute_all_dispatches(self, mocker):
        mocker.patch.object(
            sys,
            "argv",
            [
                "mark42.py", "heavy", "--execute-all", "--task-name", "big-task",
                "--command", "python {f}", "--execute-now",
            ],
        )
        mock_execute_all = mocker.patch("mark42_modules.heavy.heavy_execute_all")

        cli.main()

        mock_execute_all.assert_called_once_with(
            "big-task", command="python {f}", execute_now=True
        )

    def test_heavy_missing_task_name_prints_error(self, mocker, capsys):
        mocker.patch.object(sys, "argv", ["mark42.py", "heavy", "--start", "/tmp/proj"])
        mocker.patch("mark42_modules.heavy.heavy_start")

        cli.main()

        out = capsys.readouterr().out
        assert "--task-name 不能为空" in out

    def test_status_json_prints_serialized_dashboard(self, mocker, capsys):
        mocker.patch.object(sys, "argv", ["mark42.py", "status", "--json"])
        mocker.patch.object(cli, "status_dashboard", return_value={"ok": True, "value": 1})

        cli.main()

        out = capsys.readouterr().out
        assert '"ok": true' in out
        assert '"value": 1' in out

    def test_assemble_dispatches(self, mocker):
        mocker.patch.object(sys, "argv", ["mark42.py", "assemble"])
        mock_assemble = mocker.patch.object(cli, "assemble")

        cli.main()

        mock_assemble.assert_called_once()