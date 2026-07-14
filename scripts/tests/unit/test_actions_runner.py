"""actions_runner 测试群。

覆盖目标：
  - 列出 pending actions（含 executable 标记）
  - dry-run 默认行为（不执行）
  - --yes 才能真执行，且调用现有 assemble_restart
  - 未在白名单的动作在加 --yes 时仍被安全策略拒绝
  - broker 留痕

设计要点：
  - 直接用 mark42_modules.actions_runner，与 cli.py 的 actions 子命令分开测
  - assemble_restart 会真的重启 assemble，必须 mock
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mark42_modules import actions_runner


@pytest.fixture
def pending_actions_file(tmp_path, monkeypatch):
    """桥接 _write_pending_actions / _read_pending_actions 到 tmp_path。"""
    pending_path = tmp_path / "actions-pending.json"
    monkeypatch.setattr(actions_runner, "actions_queue_path", lambda: pending_path)
    return pending_path


class TestListActions:
    def test_returns_empty_when_no_pending(self, pending_actions_file):
        assert actions_runner.list_actions() == []

    def test_marks_executable_and_dry_run_only(self, pending_actions_file):
        pending_actions_file.write_text(
            json.dumps([
                {
                    "id": "refresh-actions",
                    "title": "刷新队列",
                    "reason": "刷新 suggestedActions",
                    "commandPreview": "mark42.py status --all-agents --json",
                    "priority": "low",
                },
                {
                    "id": "restart-assemble",
                    "title": "重启 Mark42 assemble 守护",
                    "reason": "assemble 全部停止",
                    "commandPreview": "mark42.py assemble",
                    "priority": "high",
                },
                {
                    "id": "rebalance-default-agent",
                    "title": "分流默认 agent 负载",
                    "reason": "main 最忙但 coder 空闲",
                    "commandPreview": "建议把新任务分配到 coder",
                    "priority": "medium",
                    "sourceAgent": "main",
                },
            ], ensure_ascii=False),
            encoding="utf-8",
        )

        actions = actions_runner.list_actions()

        assert len(actions) == 3
        first, second, third = sorted(actions, key=lambda a: a["actionId"])
        assert first["actionId"] == "rebalance-default-agent"
        assert first["executableNow"] is False
        assert first["dryRunOnly"] is True
        assert first["agent"] == "main"
        assert second["actionId"] == "refresh-actions"
        assert second["executableNow"] is True
        assert second["dryRunOnly"] is False
        assert third["actionId"] == "restart-assemble"
        assert third["executableNow"] is True
        assert third["dryRunOnly"] is False


class TestExecuteAction:
    def test_unknown_action_raises(self, pending_actions_file):
        with pytest.raises(actions_runner._ActionNotFoundError):
            actions_runner.execute_action("no-such-action", agent="main", dry_run=True)

    def test_dry_run_does_not_call_assemble_restart(self, pending_actions_file, mocker):
        restart_mock = mocker.patch(
            "mark42_modules.cli.assemble_restart",
            return_value={"pid": 9999, "log": "x", "agent": "main"},
        )

        result = actions_runner.execute_action(
            "restart-assemble", agent="main", dry_run=True,
        )

        assert result.executed is False
        assert result.actionId == "restart-assemble"
        assert result.agent == "main"
        assert result.commandPreview == "mark42.py assemble (agent=main)"
        restart_mock.assert_not_called()

    def test_execute_calls_assemble_restart_when_yes(self, pending_actions_file, mocker):
        restart_mock = mocker.patch(
            "mark42_modules.cli.assemble_restart",
            return_value={"pid": 9999, "log": "x", "agent": "main"},
        )

        result = actions_runner.execute_action(
            "restart-assemble", agent="main", dry_run=False,
        )

        assert result.executed is True
        assert result.metadata.get("pid") == 9999
        restart_mock.assert_called_once_with(agent="main")

    def test_dry_run_only_action_refused_even_with_yes(self, pending_actions_file, mocker):
        restart_mock = mocker.patch("mark42_modules.cli.assemble_restart")

        result = actions_runner.execute_action(
            "rebalance-default-agent", agent="main", dry_run=False,
        )

        assert result.executed is False
        assert result.level == "warning"
        assert result.metadata.get("refusedBySafetyPolicy") is True
        restart_mock.assert_not_called()

    def test_execute_action_writes_broker_event(self, pending_actions_file, mocker):
        broker_mock = mocker.patch("mark42_modules.utils._append_broker")
        mocker.patch(
            "mark42_modules.cli.assemble_restart",
            return_value={"pid": 1234, "log": "x", "agent": "main"},
        )

        actions_runner.execute_action(
            "restart-assemble", agent="main", dry_run=False,
        )

        assert broker_mock.called
        call_args = broker_mock.call_args.args
        call_kwargs = broker_mock.call_args.kwargs
        metadata = call_kwargs.get("metadata")
        if metadata is None and len(call_args) >= 6:
            metadata = call_args[5]
        assert metadata is not None
        assert metadata["actionId"] == "restart-assemble"
        assert metadata["executed"] is True

    def test_refresh_actions_dry_run(self, pending_actions_file):
        result = actions_runner.execute_action(
            "refresh-actions", agent=None, dry_run=True,
        )

        assert result.executed is False
        assert result.actionId == "refresh-actions"
        assert "刷新 suggestedActions" in result.summary

    def test_refresh_actions_execute_calls_status_dashboard(self, pending_actions_file, mocker):
        mock_status = mocker.patch(
            "mark42_modules.cli.status_dashboard",
            return_value={"suggestedActions": [{"id": "restart-assemble"}, {"id": "refresh-actions"}]},
        )

        result = actions_runner.execute_action(
            "refresh-actions", agent=None, dry_run=False,
        )

        assert result.executed is True
        assert result.metadata["actionCount"] == 2
        mock_status.assert_called_once_with(json_mode=True, all_agents=True)


class TestCliBridge:
    def test_main_list_emits_actions_json(self, capsys, pending_actions_file):
        pending_actions_file.write_text(
            json.dumps([{"id": "restart-assemble"}], ensure_ascii=False),
            encoding="utf-8",
        )

        rc = actions_runner.main(["--list"])
        out = capsys.readouterr().out
        parsed = json.loads(out)

        assert rc == 0
        assert len(parsed["actions"]) == 1
        assert parsed["actions"][0]["actionId"] == "restart-assemble"

    def test_main_run_without_args_returns_usage(self, capsys):
        rc = actions_runner.main([])
        out = capsys.readouterr().out
        assert rc == 1
        assert "actions" in out

    def test_main_run_unknown_id_returns_error(self, capsys, pending_actions_file):
        rc = actions_runner.main(["--run", "no-such-action"])
        captured = capsys.readouterr()
        assert rc == 2
        assert "未知动作" in captured.out
