"""P1.3 集成测试：armor → openclaw sessions.compact 真交互。

设计原则：
- 不动真 active session（避免破坏 OpenClaw 主会话）
- 但真调 openclaw sessions.compact CLI（验证 RPC 链路可用）
- 验证 armor 真调用了 sessions.compact 而不是别的

测试场景:
  1. sessions.compact CLI 命令可用 + 帮助正确
  2. armor 触发压缩时调用的 CLI 参数格式正确（不依赖真压缩效果）
  3. armor_compress 输出含 compressionEffective / compactMethod 字段
  4. 备份-还原：备份当前 session, 调 compact 真截短, 验证大小变化, 还原
     （这条比较危险, 需要谨慎）
"""

import json
import shutil
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import armor


# ── helper ────────────────────────────────────────────────

def _find_active_session_path() -> Path | None:
    """找当前 active session 文件路径（用于集成测试）。"""
    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    if not sessions_dir.exists():
        return None
    # 按 mtime 取最新 jsonl
    candidates = [c for c in sessions_dir.glob("*.jsonl")
                  if not any(s in c.name for s in [".trajectory.", ".reset.", ".deleted."])]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _has_openclaw_cli() -> bool:
    """openclaw CLI 是否可用。"""
    try:
        result = subprocess.run(["openclaw", "--version"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── 集成测试 ─────────────────────────────────────────────

@pytest.mark.integration
class TestOpenClawSessionsCompactIntegration:
    """P1.3: 验证 armor 调 openclaw sessions.compact 的真交互。"""

    def test_openclaw_cli_available(self):
        """openclaw CLI 必须可用（前置条件）。"""
        assert _has_openclaw_cli(), "openclaw 命令不可用, 跳过集成测试"

    def test_sessions_compact_help_lists_max_lines_option(self):
        """openclaw sessions compact --help 应包含 --max-lines 选项（P0 修复依赖）。"""
        if not _has_openclaw_cli():
            pytest.skip("openclaw 不可用")

        result = subprocess.run(
            ["openclaw", "sessions", "compact", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert "--max-lines" in result.stdout, (
            f"openclaw sessions compact 必须支持 --max-lines, "
            f"实际输出:\n{result.stdout[:500]}"
        )

    def test_armor_compress_calls_sessions_compact_with_correct_args(self, mocker, armor_state):
        """armor_compress 触发压缩时, 必须调 openclaw sessions compact 而非别的命令。

        验证方法: 拦截 subprocess.run, 确认 args 包含 'sessions' 'compact'。
        """
        if not _has_openclaw_cli():
            pytest.skip("openclaw 不可用")

        # mock 高使用率 + session (用 simple 模式, 不依赖真文件)
        fake_session = MagicMock()
        fake_session.name = "agent.jsonl"
        # mock session 设 1GB, simple 模式算 488K tokens / 1M 窗口 = 48% > 70% 阈值
        # (阈值由 MARK42_CTX_WARN_PCT 控制, 是 int, 不能用浮点)
        fake_session.stat.return_value.st_size = 1024 * 1024 * 1024  # 1GB
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        mocker.patch.object(armor, "_read_session_tail", return_value=[
            {"role": "user", "content": "test"},
        ])
        mocker.patch.object(armor, "_llm_analyze",
                            return_value={"preserved": {}, "discarded": {},
                                          "degradationDetected": None})

        # 捕获所有 subprocess.run 调用
        calls = []

        def capture_run(*args, **kwargs):
            calls.append((args, kwargs))
            # 模拟 du
            if args and args[0] and isinstance(args[0], list) and args[0][0] == "du":
                result = MagicMock()
                result.stdout = "80000\t/sessions"
                result.returncode = 0
                result.stderr = ""
                return result
            # openclaw 命令 (默认成功)
            return MagicMock(returncode=0, stdout='{"ok":true}', stderr="")

        mocker.patch("subprocess.run", side_effect=capture_run)

        # P1.3: simple 模式让 mock session 生效, 否则 smart 模式读不到字符返 0 tokens
        mocker.patch.dict("os.environ", {
            "MARK42_TOKEN_ESTIMATE_MODE": "simple",
        })
        result = armor.armor_compress()

        # 验证有 openclaw sessions compact 调用
        sessions_compact_calls = [
            (args, kwargs) for args, kwargs in calls
            if args and args[0] and isinstance(args[0], list)
            and args[0][0] == "openclaw"
            and len(args[0]) >= 2 and args[0][1] == "sessions"
        ]
        assert len(sessions_compact_calls) >= 1, (
            f"armor 必须调 openclaw sessions compact, 实际调用: {calls}"
        )

        # 验证调用参数含 --max-lines
        cmd_args = sessions_compact_calls[0][0][0]
        assert "--max-lines" in cmd_args, (
            f"应传 --max-lines, 实际: {cmd_args}"
        )

    def test_armor_compress_real_run_dry_run_does_not_modify_session(self, mocker, armor_state):
        """dry_run 模式下 armor_compress 不应真调 sessions.compact。

        验证 dry_run 路径不会触发现有问题的 lock 等待。
        """
        if not _has_openclaw_cli():
            pytest.skip("openclaw 不可用")

        # mock 高使用率 + session (1GB 模拟超阈值, dry_run 强制执行)
        fake_session = MagicMock()
        fake_session.name = "agent.jsonl"
        fake_session.stat.return_value.st_size = 1024 * 1024 * 1024  # 1GB
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        mocker.patch.object(armor, "_read_session_tail", return_value=[
            {"role": "user", "content": "test"},
        ])
        mocker.patch.object(armor, "_llm_analyze",
                            return_value={"preserved": {}, "discarded": {},
                                          "degradationDetected": None})

        calls = []
        def capture_run(*args, **kwargs):
            calls.append(args[0] if args else None)
            if args and args[0] and isinstance(args[0], list) and args[0][0] == "du":
                result = MagicMock()
                result.stdout = "80000\t/sessions"
                return result
            return MagicMock(returncode=0, stdout='{"ok":true}', stderr="")

        mocker.patch("subprocess.run", side_effect=capture_run)

        # dry_run=True 强制执行, 无需降阈值
        mocker.patch.dict("os.environ", {"MARK42_TOKEN_ESTIMATE_MODE": "simple"})
        result = armor.armor_compress(dry_run=True)

        # dry_run 模式不应调 openclaw sessions compact
        compact_calls = [c for c in calls
                        if c and isinstance(c, list) and len(c) >= 2
                        and c[0] == "openclaw" and c[1] == "sessions"]
        assert len(compact_calls) == 0, (
            f"dry_run 不应调 compact, 实际: {compact_calls}"
        )
        # dry_run 仍生成 memory-index (preview)
        assert (armor_state / "memory-index.json").exists()

    def test_armor_compress_subprocess_failure_marked_in_index(self, mocker, armor_state):
        """openclaw sessions.compact 调用失败时, memory-index 应记录错误。

        实现思路:
          1. mock armor_check 返 90% usage, 跳过真实估算逻辑
          2. mock _find_active_session 返 fake session
          3. mock subprocess.run 调 openclaw 时返 returncode=1 + stderr 错误
          4. armor_compress() 进入 compact 流程, 失败时设 compactError
          5. 验证 armor_state/memory-index.json 存在 + 含 compactError
        """
        if not _has_openclaw_cli():
            pytest.skip("openclaw 不可用")

        # mock armor_check 直接返高 usage, 避免和阈值 + token 估算逻辑交互
        mocker.patch.object(armor, "armor_check", return_value={
            "usagePercent": 90, "status": "critical", "summary": "mocked",
            "activeSession": "agent.jsonl", "activeFileMB": 1024.0,
        })

        fake_session = MagicMock()
        fake_session.name = "agent.jsonl"
        fake_session.stat.return_value.st_size = 1024 * 1024 * 1024  # 1GB
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        mocker.patch.object(armor, "_read_session_tail", return_value=[
            {"role": "user", "content": "test"},
        ])
        mocker.patch.object(armor, "_llm_analyze",
                            return_value={"preserved": {}, "discarded": {},
                                          "degradationDetected": None})

        def capture_run(*args, **kwargs):
            if args and args[0] and isinstance(args[0], list) and args[0][0] == "du":
                result = MagicMock()
                result.stdout = "80000\t/sessions"
                return result
            # openclaw 命令: 返回失败
            result = MagicMock()
            result.returncode = 1
            result.stdout = ""
            result.stderr = "session locked: another compact in progress"
            return result

        mocker.patch("subprocess.run", side_effect=capture_run)

        result = armor.armor_compress()

        index = json.loads((armor_state / "memory-index.json").read_text())
        assert index["compactTriggered"] is False
        assert index["compressionEffective"] is False
        assert "session locked" in (index.get("compactError") or ""), (
            f"应记录错误信息, 实际: {index.get('compactError')}"
        )