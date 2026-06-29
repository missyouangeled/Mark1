"""armor.py 压缩相关函数的单测。

覆盖范围：
  - armor_compress()        核心入口（skip / LLM / heuristic / dry_run / 写文件）
  - armor_pre_compact_hook() 压缩算法 hook
  - armor_compress_queue_stats() 队列统计

设计要点：
  - mock _find_active_session / _llm_analyze / armor_check 让测试不依赖真环境
  - 用 tmp_path 验证写文件逻辑（memory-index.json + actions.jsonl + history/）
  - **关键**：mock subprocess.run 时要区分两种调用：
      1. du（armor_check 内部）→ 返回 stdout=数字
      2. openclaw agent（armor_compress 内部）→ 返回 returncode/stdout/stderr
    用 side_effect 函数根据 args 区分
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import armor


# ── helper ────────────────────────────────────────────────

def _high_usage_session(target_pct: float):
    """构造一个会产生高使用率的 session mock。"""
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    return fake_session


def _dual_subprocess_mock(du_size_kb: int, cli_result: MagicMock = None,
                          compact_bytes_after: int = None):
    """构造同时 mock du 和 openclaw 两种调用的 side_effect 函数。

    用法：
        mocker.patch("subprocess.run", side_effect=_dual_subprocess_mock(...))

    参数:
      du_size_kb: armor_check 内部 du 命令返回的 KB 数
      cli_result: 自定义 openclaw 返回（覆盖默认成功）
      compact_bytes_after: 模拟 sessions.compact 后 session 文件新大小（字节）
                          默认 = 不模拟变小 (返回原大小), 会触发 compressionEffective=False
                          设置为具体值（小于原大小）= 模拟真压缩生效
    """
    def side_effect(args, **kwargs):
        if isinstance(args, (list, tuple)) and args and args[0] == "du":
            fake = MagicMock()
            fake.stdout = f"{du_size_kb}\t/sessions"
            return fake
        elif isinstance(args, (list, tuple)) and args and args[0] == "openclaw":
            # 区分 openclaw agent / openclaw sessions compact
            if len(args) >= 2 and args[1] == "agent":
                # 老路径（理论上不再调, 但保留兼容）
                if cli_result is not None:
                    return cli_result
                fake = MagicMock()
                fake.returncode = 0
                fake.stdout = '{"ok":true}'
                fake.stderr = ""
                return fake
            elif len(args) >= 2 and args[1] == "sessions":
                # 新路径: sessions compact
                # 修改 active_session 的 stat().st_size 返回值 (实现 "session 变小")
                # 查找上次传给 stat() 的 size 路径: 通过 _high_usage_session.set_size
                if compact_bytes_after is not None and hasattr(side_effect, 'active_session_mock'):
                    side_effect.active_session_mock.stat.return_value.st_size = compact_bytes_after
                if cli_result is not None:
                    return cli_result
                fake = MagicMock()
                fake.returncode = 0
                fake.stdout = '{"ok":true}'
                fake.stderr = ""
                return fake
            else:
                if cli_result is not None:
                    return cli_result
                fake = MagicMock()
                fake.returncode = 0
                fake.stdout = '{"ok":true}'
                fake.stderr = ""
                return fake
        else:
            fake = MagicMock()
            fake.returncode = 0
            fake.stdout = ""
            fake.stderr = ""
            return fake

    return side_effect


def _high_usage_session_with_compactable(target_pct: float, compact_to_pct: float = 30.0):
    """构造一个高使用率 session mock，且 sessions.compact 后可以模拟“变小”。

    返回 (session_mock, bytes_needed_before, bytes_after_compact):
      - bytes_needed_before: 初始字节数 (用于 _high_usage_session)
      - bytes_after_compact: 压缩后字节数（小于初始 → 会触发 compressionEffective=True）
    """
    # 初始 session 字节
    initial_bytes = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    compact_bytes = int(compact_to_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)

    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"

    # 使用可变容器包裹 size 以便 mock 能在 sessions.compact 后修改
    state = {"size": initial_bytes}
    fake_session.stat.return_value.st_size = initial_bytes

    # 提供 set_size 让 mock side_effect 可以调
    def set_size(new_size):
        state["size"] = new_size
        fake_session.stat.return_value.st_size = new_size
    fake_session.set_size = set_size
    return fake_session, initial_bytes, compact_bytes


def _setup_high_usage(mocker, target_pct: float = 80.0, with_messages: bool = True):
    """标准 setup: mock armor_check 高使用率 + session + subprocess。

    参数:
      with_messages: True 时 mock _read_session_tail 返回非空消息列表
                     (这样会走 LLM 分支而不是 heuristic fallback)
                     False 时 session_messages=[]，走 heuristic fallback
    """
    mocker.patch.object(
        armor, "armor_check",
        return_value={"usagePercent": target_pct, "severity": "warn", "summary": "x"},
    )
    fake_session = _high_usage_session(target_pct)
    mocker.patch.object(armor, "_find_active_session", return_value=fake_session)

    if with_messages:
        # 提供消息列表让 armor_compress 走 LLM 分支
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        mocker.patch.object(armor, "_read_session_tail", return_value=msgs)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )
    else:
        # 空消息列表，走 heuristic fallback
        mocker.patch.object(armor, "_read_session_tail", return_value=[])

    mocker.patch("subprocess.run", side_effect=_dual_subprocess_mock(
        du_size_kb=int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN) // 1024,
    ))


def _mock_read_tail(mocker, msgs=None):
    """便捷 helper: mock _read_session_tail。

    默认提供 10 条消息。传 msgs=[] 走 heuristic fallback。
    """
    if msgs is None:
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    mocker.patch.object(armor, "_read_session_tail", return_value=msgs)


# ─────────────────────── armor_compress ───────────────────────

class TestArmorCompress:
    """armor_compress() 测试群。"""

    def test_skip_when_usage_below_warn(self, mocker):
        """使用率 < WARN 阈值时，返回 action=skip。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 30.0, "severity": "ok", "summary": "x"},
        )
        # 即使有 session，也应该 skip
        mocker.patch.object(armor, "_find_active_session", return_value=None)

        result = armor.armor_compress()

        assert result["action"] == "skip"
        assert "未达阈值" in result["reason"]
        assert result["check"]["usagePercent"] == 30.0

    def test_skip_does_not_write_files(self, mocker, armor_state):
        """skip 模式不应写 memory-index.json 或 actions.jsonl。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 30.0, "severity": "ok", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session", return_value=None)

        armor.armor_compress()

        assert not (armor_state / "memory-index.json").exists()
        assert not (armor_state / "actions.jsonl").exists()

    def test_dry_run_bypasses_threshold(self, mocker):
        """dry_run=True 即使使用率低也执行分析。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 10.0, "severity": "ok", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session", return_value=None)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )

        result = armor.armor_compress(dry_run=True)

        assert result["action"] == "compress"
        assert result["preCompressUsage"] == 10.0

    def test_writes_memory_index_json(self, mocker, armor_state):
        """正常压缩应写 memory-index.json。"""
        _setup_high_usage(mocker, target_pct=80.0)

        result = armor.armor_compress()

        index_path = armor_state / "memory-index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text())
        assert index["preCompressUsage"] == 80.0
        assert index["modelGenerated"] is True
        assert index["strategyUsed"] == "llm-analyze"

        assert result["action"] == "compress"
        assert result["indexWritten"] == str(index_path)

    def test_actions_log_records_event(self, mocker, armor_state):
        """每次压缩应在 actions.jsonl 追加一条记录。"""
        _setup_high_usage(mocker, target_pct=80.0)

        armor.armor_compress()

        actions_log = armor_state / "actions.jsonl"
        assert actions_log.exists()
        lines = actions_log.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["action"] == "compress"
        assert entry["preCompressUsage"] == 80.0

    def test_dry_run_logs_compress_dryrun(self, mocker, armor_state):
        """dry_run 模式写 actions.jsonl 时 action 字段为 compress-dryrun。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session", return_value=None)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )

        armor.armor_compress(dry_run=True)

        actions_log = armor_state / "actions.jsonl"
        assert actions_log.exists()
        entry = json.loads(actions_log.read_text().strip().split("\n")[-1])
        assert entry["action"] == "compress-dryrun"

    def test_writes_history_snapshot(self, mocker, armor_state):
        """每次压缩应在 history/ 留快照。"""
        _setup_high_usage(mocker, target_pct=80.0)

        armor.armor_compress()

        history_dir = armor_state / "history"
        assert history_dir.exists()
        snapshots = list(history_dir.glob("memory-index-*.json"))
        assert len(snapshots) >= 1

    def test_falls_back_to_heuristic_when_llm_unavailable(self, mocker, armor_state):
        """LLM 不可用时应回退到启发式分类。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session",
                          return_value=_high_usage_session(80))
        _mock_read_tail(mocker)  # 让 armor_compress 走 LLM 分支
        mocker.patch.object(armor, "_llm_analyze", return_value=None)
        mocker.patch.object(
            armor, "_classify_messages",
            return_value={
                "preserved": [{"role": "user", "preview": "test"}],
                "discarded": [{"preview": "x"}] * 5,
                "totalAnalyzed": 30,
            },
        )
        mocker.patch("subprocess.run",
                    side_effect=_dual_subprocess_mock(du_size_kb=80_000))

        armor.armor_compress()

        index = json.loads((armor_state / "memory-index.json").read_text())
        assert index["strategyUsed"] == "heuristic-classify"
        assert index["modelGenerated"] is False

    def test_cli_trigger_success_sets_compact_triggered_true(self, mocker, armor_state):
        """openclaw sessions compact 成功且 session 真变小 → compactTriggered=True + compressionEffective=True。"""
        # mock session: 初始 80MB 等效字节数，压缩后变成 30MB 等效
        fake_session, before_b, after_b = _high_usage_session_with_compactable(80.0, 30.0)
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        _mock_read_tail(mocker)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )
        # mock subprocess.run: sessions.compact 后改 size
        def mock_run(args, **kwargs):
            # du 调用
            if args and args[0] == "du":
                f = MagicMock()
                f.stdout = "80000\t/sessions"
                return f
            # openclaw sessions compact - 模拟后会让 session 变小
            if args and args[0] == "openclaw" and len(args) > 1 and args[1] == "sessions":
                fake_session.set_size(after_b)
                f = MagicMock()
                f.returncode = 0
                f.stdout = '{"ok":true}'
                f.stderr = ""
                return f
            # 其他 openclaw 调用（老路径 agent）
            f = MagicMock()
            f.returncode = 0
            f.stdout = '{"ok":true}'
            f.stderr = ""
            return f
        mocker.patch("subprocess.run", side_effect=mock_run)

        armor.armor_compress()

        index = json.loads((armor_state / "memory-index.json").read_text())
        assert index.get("compactTriggered") is True
        assert index.get("compactMethod") == "openclaw-sessions-compact"
        # 验证压缩有效的字段
        assert index.get("compressionEffective") is True
        assert index.get("preCompactBytes") == before_b
        assert index.get("postCompactBytes") == after_b
        assert index.get("bytesSaved") == before_b - after_b

    def test_cli_trigger_but_session_did_not_shrink_marks_ineffective(self, mocker, armor_state):
        """openclaw sessions compact 返回成功但 session 未变小 → compressionEffective=False。"""
        _setup_high_usage(mocker, target_pct=80.0)
        # 不传 compact_bytes_after，session size 不会变

        armor.armor_compress()

        index = json.loads((armor_state / "memory-index.json").read_text())
        assert index.get("compactTriggered") is True  # subprocess 成功
        assert index.get("compressionEffective") is False  # 但 session 没变小
        assert index.get("compactError") == "no-bytes-saved"

    def test_ineffective_history_triggers_escalation_event(self, mocker, armor_state):
        """连续 ≥3 次压缩无效 → broker 发出 mark42.armor.compact.ineffective 事件。"""
        # 先跑一次让 history/ 创建
        _setup_high_usage(mocker, target_pct=80.0)
        armor.armor_compress()

        # 现在 history/ 已创建，改写为“连续无效”场景
        history_dir = armor_state / "history"
        for hf in history_dir.glob("memory-index-*.json"):
            entry = json.loads(hf.read_text())
            entry["compressionEffective"] = False
            hf.write_text(json.dumps(entry))

        # 还需要 ≥3 个历史文件, 如果只有 1 个, 复制补充
        existing = sorted(history_dir.glob("memory-index-*.json"))
        while len(existing) < 3:
            src = existing[0]
            new_path = history_dir / f"{src.stem}-extra.json"
            new_path.write_text(src.read_text())
            existing = sorted(history_dir.glob("memory-index-*.json"))

        # 再跑一次
        _setup_high_usage(mocker, target_pct=80.0)
        armor.armor_compress()

        # 检查 broker 事件
        from mark42_modules.config import MARK42_BROKER_EVENTS
        events = []
        if MARK42_BROKER_EVENTS.exists():
            with open(MARK42_BROKER_EVENTS) as f:
                events = [json.loads(line) for line in f]
        escalation_events = [e for e in events if "ineffective" in e.get("sourceEventType", "")]
        assert len(escalation_events) >= 1, f"应至少 1 条升级事件, 实际: {events}"
        assert "连续" in escalation_events[-1]["label"]

    def test_cli_trigger_failure_marks_compact_failed(self, mocker, armor_state):
        """CLI 失败 → compactTriggered=False + compactError 有内容。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session",
                          return_value=_high_usage_session(80))
        _mock_read_tail(mocker)  # 让 armor_compress 走 LLM 分支
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )

        # 构造 CLI 失败
        cli_fail = MagicMock()
        cli_fail.returncode = 1
        cli_fail.stderr = "openclaw agent error message"
        mocker.patch("subprocess.run",
                    side_effect=_dual_subprocess_mock(du_size_kb=80_000, cli_result=cli_fail))

        # 不应抛异常
        result = armor.armor_compress()

        # index 仍然写入了
        assert (armor_state / "memory-index.json").exists()
        index = json.loads((armor_state / "memory-index.json").read_text())
        assert index.get("compactTriggered") is False
        assert "openclaw agent error" in (index.get("compactError") or "")
        # 主 action 仍然是 compress
        assert result["action"] == "compress"

    def test_cli_not_found_handled_gracefully(self, mocker, armor_state):
        """openclaw 命令找不到（FileNotFoundError）应优雅处理。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session",
                          return_value=_high_usage_session(80))
        _mock_read_tail(mocker)  # 让 armor_compress 走 LLM 分支
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )

        def side_effect(args, **kwargs):
            if isinstance(args, (list, tuple)) and args and args[0] == "du":
                fake = MagicMock()
                fake.stdout = "80000\t/sessions"
                return fake
            elif isinstance(args, (list, tuple)) and args and args[0] == "openclaw":
                raise FileNotFoundError("openclaw not found")
            return MagicMock()

        mocker.patch("subprocess.run", side_effect=side_effect)

        armor.armor_compress()

        index = json.loads((armor_state / "memory-index.json").read_text())
        assert index.get("compactError") == "openclaw-not-found"
        assert index.get("compactTriggered") is False

    def test_cli_timeout_handled(self, mocker, armor_state):
        """CLI 超时（TimeoutExpired）应被捕获。"""
        import subprocess as sp
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session",
                          return_value=_high_usage_session(80))
        _mock_read_tail(mocker)  # 让 armor_compress 走 LLM 分支
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )

        def side_effect(args, **kwargs):
            if isinstance(args, (list, tuple)) and args and args[0] == "du":
                fake = MagicMock()
                fake.stdout = "80000\t/sessions"
                return fake
            elif isinstance(args, (list, tuple)) and args and args[0] == "openclaw":
                raise sp.TimeoutExpired(cmd="openclaw", timeout=180)
            return MagicMock()

        mocker.patch("subprocess.run", side_effect=side_effect)

        # 不应抛异常
        armor.armor_compress()

        index = json.loads((armor_state / "memory-index.json").read_text())
        assert index.get("compactError") == "timeout"

    def test_no_active_session_skips_compact(self, mocker, armor_state):
        """没有活跃会话时不触发 /compact。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        # _find_active_session 第一次返回 mock session（用于 _read_session_tail），
        # 第二次返回 None（用于触发 compact 时检测）
        call_count = [0]

        def session_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return _high_usage_session(80)
            return None  # 触发 compact 时找不到

        mocker.patch.object(armor, "_find_active_session", side_effect=session_side_effect)
        mocker.patch.object(armor, "_read_session_tail",
                          return_value=[{"role": "user", "content": "x"}] * 5)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )
        # 只 mock du，不应有 openclaw 调用
        mocker.patch("subprocess.run",
                    side_effect=_dual_subprocess_mock(du_size_kb=80_000))

        armor.armor_compress()

        index = json.loads((armor_state / "memory-index.json").read_text())
        # index 仍然写入了
        assert index["preCompressUsage"] == 80.0
        # compactTriggered 应该是 False 或不存在（因为 session 不存在）
        # 代码逻辑：如果 active_session 为 None，直接 index["compactTriggered"] = False
        assert index.get("compactTriggered") is False

    def test_dry_run_does_not_trigger_compact(self, mocker, armor_state):
        """dry_run 模式不应触发 openclaw agent CLI 调用。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session",
                          return_value=_high_usage_session(80))
        _mock_read_tail(mocker)  # 让 armor_compress 走 LLM 分支
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )
        # mock openclaw agent 调用，如果它被调用就会失败
        cli_called = [False]

        def side_effect(args, **kwargs):
            if isinstance(args, (list, tuple)) and args and args[0] == "openclaw":
                cli_called[0] = True
                raise RuntimeError("不应该调用 CLI")
            fake = MagicMock()
            fake.stdout = "80000\t/sessions"
            return fake

        mocker.patch("subprocess.run", side_effect=side_effect)

        armor.armor_compress(dry_run=True)

        assert cli_called[0] is False, "dry_run 不应触发 openclaw agent CLI"


# ─────────────────────── armor_compress_queue_stats ───────────────────────

class TestArmorCompressQueueStats:
    """armor_compress_queue_stats 测试群。"""

    def test_returns_dict_with_known_keys(self):
        """应返回 dict，包含 enqueued/processed/failed 等字段。"""
        result = armor.armor_compress_queue_stats()
        assert isinstance(result, dict)
        # 真队列存在时应包含这些字段；不存在时返回 error
        if "error" not in result:
            # 真队列模式
            for key in ["enqueued", "processed", "failed", "dropped_queue_full"]:
                assert key in result, f"queue stats 缺少字段: {key}"


# ─────────────────────── armor_pre_compact_hook ───────────────────────

class TestArmorPreCompactHook:
    """armor_pre_compact_hook 测试群。"""

    def test_returns_dict_with_required_fields(self):
        """应返回 dict，包含完整 stats 字段集。"""
        result = armor.armor_pre_compact_hook([], dry_run=False)
        assert isinstance(result, dict)
        for key in [
            "enabled", "ran", "algorithm", "mode",
            "filesProcessed", "totalOriginalBytes", "totalCrushedBytes",
            "overallRatio", "piiRedactions", "decisionsByBucket",
            "fallbackCount", "error",
        ]:
            assert key in result, f"pre_compact_hook 缺少字段: {key}"

    def test_empty_messages_returns_zero_stats(self):
        """空消息列表应返回零计数 stats。"""
        result = armor.armor_pre_compact_hook([], dry_run=False)
        assert result["filesProcessed"] == 0
        assert result["totalOriginalBytes"] == 0
        assert result["totalCrushedBytes"] == 0
        assert result["overallRatio"] == 0.0

    def test_dry_run_flag_passed_through(self):
        """dry_run 参数应被接受。"""
        # 不应抛异常
        result_dry = armor.armor_pre_compact_hook([], dry_run=True)
        result_real = armor.armor_pre_compact_hook([], dry_run=False)
        assert isinstance(result_dry, dict)
        assert isinstance(result_real, dict)

    def test_default_algorithm_disabled(self):
        """默认情况下算法 disabled（ALGO_SMARTCRUSH_ENABLED=False）。"""
        result = armor.armor_pre_compact_hook([{"role": "user", "content": "x"}], dry_run=False)
        # 默认应该是 ran=False 或 enabled=False
        assert result["ran"] is False or result["enabled"] is False

    def test_no_crash_on_large_messages(self):
        """大消息列表不应让 pre_compact_hook 崩溃。"""
        big = [{"role": "user", "content": f"msg {i}"} for i in range(1000)]
        result = armor.armor_pre_compact_hook(big, dry_run=False)
        assert isinstance(result, dict)