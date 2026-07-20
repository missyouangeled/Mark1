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
        elif isinstance(args, (list, tuple)) and args and args[0].endswith("openclaw"):
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

    # ── 2026-06-30 J 修复: actions.jsonl 加 preBytes/postBytes/bytesSaved/effective ──

    def test_actions_log_includes_bytes_fields_when_compact_succeeds(self, mocker, armor_state):
        """【J 修复】sessions.compact 成功后,actions.jsonl 应含 preBytes/postBytes/bytesSaved/compressionEffective。"""
        # 设高使用率
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        # 模拟会话: compact 前 X 字节, compact 后 Y 字节 (Y < X)
        session_mock, initial_bytes, compact_bytes = _high_usage_session_with_compactable(
            target_pct=80.0, compact_to_pct=30.0,
        )
        mocker.patch.object(armor, "_find_active_session", return_value=session_mock)
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        mocker.patch.object(armor, "_read_session_tail", return_value=msgs)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )
        # 模拟 sessions.compact 成功且 session 变小
        initial_size = session_mock.stat.return_value.st_size
        compact_size = int(initial_size * 0.5)  # 压缩到一半
        def shrink_session():
            session_mock.set_size(compact_size)
        # 用 mock run + side_effect 实现
        from unittest.mock import MagicMock as _MM
        def run_side(args, **kwargs):
            if isinstance(args, (list, tuple)) and args and args[0] == "du":
                fake = _MM()
                fake.stdout = f"{int(initial_size/1024)}\t/sessions"
                return fake
            elif isinstance(args, (list, tuple)) and args[0].endswith("openclaw") and args[1] == "sessions":
                # 模拟压缩后变小
                session_mock.set_size(compact_size)
                fake = _MM()
                fake.returncode = 0
                fake.stdout = '{"ok":true}'
                fake.stderr = ""
                return fake
            fake = _MM()
            fake.returncode = 0
            fake.stdout = ""
            fake.stderr = ""
            return fake
        mocker.patch("subprocess.run", side_effect=run_side)

        armor.armor_compress()

        actions_log = armor_state / "actions.jsonl"
        assert actions_log.exists()
        entry = json.loads(actions_log.read_text().strip().split("\n")[-1])
        # J 修复后以下字段都应存在
        assert "preBytes" in entry, "J 修复: actions.jsonl 应含 preBytes 字段"
        assert "postBytes" in entry, "J 修复: actions.jsonl 应含 postBytes 字段"
        assert "bytesSaved" in entry, "J 修复: actions.jsonl 应含 bytesSaved 字段"
        assert "compressionEffective" in entry, "J 修复: actions.jsonl 应含 compressionEffective 字段"
        # 真值: preBytes > postBytes, effective=True
        assert entry["preBytes"] == initial_size
        assert entry["postBytes"] == compact_size
        assert entry["bytesSaved"] == initial_size - compact_size
        assert entry["compressionEffective"] is True

    def test_actions_log_marks_effective_false_when_no_bytes_saved(self, mocker, armor_state):
        """【J 修复】sessions.compact 返回成功但 session 未变小时,actions.jsonl 应记 effective=False。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        session_mock = MagicMock()
        session_mock.name = "agent.jsonl"
        initial_size = 1024 * 1024  # 1MB, 不变
        session_mock.stat.return_value.st_size = initial_size
        mocker.patch.object(armor, "_find_active_session", return_value=session_mock)
        msgs = [{"role": "user", "content": "x"}]
        mocker.patch.object(armor, "_read_session_tail", return_value=msgs)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )
        from unittest.mock import MagicMock as _MM
        def run_side(args, **kwargs):
            if isinstance(args, (list, tuple)) and args[0] == "du":
                fake = _MM(); fake.stdout = f"{int(initial_size/1024)}\t/sessions"; return fake
            elif isinstance(args, (list, tuple)) and args[0].endswith("openclaw") and args[1] == "sessions":
                fake = _MM(); fake.returncode = 0; fake.stdout = '{"ok":true}'; fake.stderr = ""
                return fake
            fake = _MM(); fake.returncode = 0; fake.stdout = ""; fake.stderr = ""; return fake
        mocker.patch("subprocess.run", side_effect=run_side)

        armor.armor_compress()

        actions_log = armor_state / "actions.jsonl"
        entry = json.loads(actions_log.read_text().strip().split("\n")[-1])
        # J 修复: effective 字段仍然要写,值为 False
        assert "compressionEffective" in entry
        assert entry["compressionEffective"] is False
        # preBytes 记了, postBytes=None 或同 preBytes
        assert entry["preBytes"] == initial_size

    # ── 2026-06-30 10:13 🟡4 修复: bytesStatus 语义标记 ──

    def test_bytes_status_captured_on_successful_compact(self, mocker, armor_state):
        """【🟡4】真 compact 成功,bytesStatus='captured'。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        session_mock, initial_bytes, compact_bytes = _high_usage_session_with_compactable(
            target_pct=80.0, compact_to_pct=30.0,
        )
        mocker.patch.object(armor, "_find_active_session", return_value=session_mock)
        msgs = [{"role": "user", "content": "x"}]
        mocker.patch.object(armor, "_read_session_tail", return_value=msgs)
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )
        from unittest.mock import MagicMock as _MM
        initial_size = session_mock.stat.return_value.st_size
        compact_size = int(initial_size * 0.5)
        def run_side(args, **kwargs):
            if isinstance(args, (list, tuple)) and args[0] == "du":
                fake = _MM(); fake.stdout = f"{int(initial_size/1024)}\t/sessions"; return fake
            elif isinstance(args, (list, tuple)) and args[0].endswith("openclaw") and args[1] == "sessions":
                session_mock.set_size(compact_size)
                fake = _MM(); fake.returncode = 0; fake.stdout = '{"ok":true}'; fake.stderr = ""
                return fake
            fake = _MM(); fake.returncode = 0; fake.stdout = ""; fake.stderr = ""; return fake
        mocker.patch("subprocess.run", side_effect=run_side)

        armor.armor_compress()
        entry = json.loads((armor_state / "actions.jsonl").read_text().strip().split("\n")[-1])
        # 🟡4 验证: 压缩成功时 bytesStatus='captured'
        assert entry.get("bytesStatus") == "captured", (
            f"🟡4 修复: 压缩成功应记 bytesStatus='captured', 实际 {entry.get('bytesStatus')}"
        )

    def test_bytes_status_skipped_dry_run(self, mocker, armor_state):
        """【🟡4】dry_run 模式,bytesStatus='skipped-dry-run',reader 明确不是 bug。"""
        mocker.patch.object(
            armor, "armor_check",
            return_value={"usagePercent": 80.0, "severity": "warn", "summary": "x"},
        )
        mocker.patch.object(armor, "_find_active_session", return_value=None)
        mocker.patch.object(armor, "_read_session_tail", return_value=[])
        mocker.patch.object(
            armor, "_llm_analyze",
            return_value={"preserved": {}, "discarded": {}, "degradationDetected": None},
        )

        armor.armor_compress(dry_run=True)
        entry = json.loads((armor_state / "actions.jsonl").read_text().strip().split("\n")[-1])
        # 🟡4 验证: dry_run 时 bytesStatus 明确标记,preBytes=null 是预期
        assert entry.get("bytesStatus") == "skipped-dry-run", (
            f"🟡4 修复: dry_run 应记 'skipped-dry-run', 实际 {entry.get('bytesStatus')}"
        )
        # preBytes 是 null 是预期, 不报错
        assert entry.get("preBytes") is None
        assert entry.get("action") == "compress-dryrun"


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
            if args and args[0].endswith("openclaw") and len(args) > 1 and args[1] == "sessions":
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
            elif isinstance(args, (list, tuple)) and args and args[0].endswith("openclaw"):
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
            elif isinstance(args, (list, tuple)) and args and args[0].endswith("openclaw"):
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
            if isinstance(args, (list, tuple)) and args and args[0].endswith("openclaw"):
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


# ─────────────────────── armor_compress_async（P1.2） ───────────────────────

class TestArmorCompressAsync:
    """P1.2: armor_compress_async 异步链路单测覆盖。

    设计考虑:
      armor_compress_async 函数体内 'from compress_queue import CompressRequest' 创建
      模块局部 binding, patch 'compress_queue.CompressRequest' 不生效。
      解决: patch 整个 queue 路径 (get_compress_queue), 让 armor 走真实流程,
      然后验证 queue 交互行为 (enqueue 被调, 返 dropped, status 字段)

    覆盖场景:
      1. wait=False 返回 queued 状态 + session_id 正确
      2. 队列满时 (enqueue=False) 返回 dropped
      3. priority 参数不报错
      4. 无活跃 session 时 session_id=unknown
      5. queue_stats 报告队列统计
      6. 真入队后 queue.enqueue 被调 + queue_size 增加
    """

    def _mock_queue(self, mocker, enqueue_returns=True, qsize_value=1):
        """mock get_compress_queue 返 mock 队列。"""
        from mark42_modules import compress_queue

        # 用真实 CompressRequest 实例 (不要 patch 类), 只 mock queue
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = enqueue_returns
        mock_queue.qsize.return_value = qsize_value
        mock_queue.stats = {"enqueued": 0, "processed": 0, "failed": 0,
                            "dropped_queue_full": 0, "dropped_low_priority": 0}

        # patch get_compress_queue 返回 mock queue
        mocker.patch.object(compress_queue, "get_compress_queue", return_value=mock_queue)
        return mock_queue

    def test_enqueue_returns_queued_status(self, mocker):
        """默认 wait=False 应返回 queued status + request_id。"""
        fake_session = MagicMock()
        fake_session.name = "test.jsonl"
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        mocker.patch.object(armor, "_read_session_tail", return_value=[
            {"role": "user", "content": "测试"}
        ])
        self._mock_queue(mocker, enqueue_returns=True, qsize_value=2)

        result = armor.armor_compress_async(wait=False)

        assert result["status"] == "queued"
        assert "request_id" in result
        assert result["session_id"] == "test.jsonl"
        assert result["queue_size"] == 2

    def test_wait_true_returns_status(self, mocker):
        """wait=True 返回 status 字段 (不一定 completed, 取决于队列实现)。"""
        fake_session = MagicMock()
        fake_session.name = "test.jsonl"
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        mocker.patch.object(armor, "_read_session_tail", return_value=[
            {"role": "user", "content": "hi"}
        ])
        self._mock_queue(mocker, enqueue_returns=True)

        result = armor.armor_compress_async(wait=True)

        # wait=True 可能 completed/timeout/failed, 但应不是 queued
        assert "status" in result
        assert result["status"] != "queued", "wait=True 不应立即返回 queued"

    def test_priority_argument_accepted(self, mocker):
        """priority 参数不报错 (验证任何合法 priority 都能传过)。"""
        fake_session = MagicMock()
        fake_session.name = "urgent.jsonl"
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        mocker.patch.object(armor, "_read_session_tail", return_value=[])
        mock_queue = self._mock_queue(mocker)

        for prio in [0, 1, 2, 9]:
            result = armor.armor_compress_async(wait=False, priority=prio)
            assert result["status"] == "queued", f"priority={prio} 应能入队"

    def test_queue_full_returns_dropped(self, mocker):
        """enqueue 返回 False (队列满) → 返回 dropped + queue_size。"""
        fake_session = MagicMock()
        fake_session.name = "flood.jsonl"
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        mocker.patch.object(armor, "_read_session_tail", return_value=[])
        self._mock_queue(mocker, enqueue_returns=False, qsize_value=100)

        result = armor.armor_compress_async(wait=False)

        assert result["status"] == "dropped"
        assert result["reason"] == "queue_full"
        assert result["queue_size"] == 100

    def test_no_active_session_uses_unknown_session_id(self, mocker):
        """无活跃 session 时，session_id 字段应为 unknown。"""
        mocker.patch.object(armor, "_find_active_session", return_value=None)
        mocker.patch.object(armor, "_read_session_tail", return_value=[])
        self._mock_queue(mocker)

        result = armor.armor_compress_async(wait=False)

        assert result["status"] == "queued"
        assert result["session_id"] == "unknown"

    def test_real_enqueue_called_with_session_messages(self, mocker):
        """入队应真调用 queue.enqueue (拿真实 CompressRequest 实例)。"""
        fake_session = MagicMock()
        fake_session.name = "session.jsonl"
        mocker.patch.object(armor, "_find_active_session", return_value=fake_session)
        sample_msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        mocker.patch.object(armor, "_read_session_tail", return_value=sample_msgs)
        mock_queue = self._mock_queue(mocker)

        armor.armor_compress_async(wait=False, priority=2)

        # enqueue 应被调用一次, 传入一个 CompressRequest
        assert mock_queue.enqueue.call_count == 1
        req = mock_queue.enqueue.call_args[0][0]
        # CompressRequest 应包含我们的内容
        assert hasattr(req, "content")
        assert hasattr(req, "session_id")
        assert hasattr(req, "priority")
        assert req.session_id == "session.jsonl"
        assert req.priority == 2
        # content 应是 JSON 序列化的消息
        import json
        assert json.loads(req.content) == sample_msgs

    def test_queue_stats_callable(self):
        """armor_compress_queue_stats 应返回 dict (真队列 or error 状态)。"""
        result = armor.armor_compress_queue_stats()
        assert isinstance(result, dict)
        # 真队列会返回 stats, 不存在时会返回 {"error": ...}
        if "error" not in result:
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

    def test_scheduler_disabled_falls_back_to_direct_path(self, mocker, monkeypatch):
        """调度器不可用时走 direct 路径。"""
        # 启用所有门
        monkeypatch.setattr(armor, "ALGO_SMARTCRUSH_ENABLED", True)
        monkeypatch.setattr(armor, "ALGO_EXPERIMENT_MODE", True)
        monkeypatch.setattr(armor, "ALGO_USE_SCHEDULER", False)
        # fake smartcrush
        fake_result = {"crushed_bytes": 50, "original_bytes": 200}
        mocker.patch.object(armor, "smartcrush", return_value=("", fake_result))

        msgs = [
            {"type": "message", "message": {"content": "a" * 5000}},
            {"type": "message", "message": {"content": "b" * 5000}},
        ]
        result = armor.armor_pre_compact_hook(msgs, dry_run=False)

        assert result["enabled"] is True
        assert result["mode"] == "direct"
        assert result["algorithm"] == "smartcrush"
        assert result["filesProcessed"] == 2
        assert result["overallRatio"] > 0

    def test_scheduler_path_records_buckets_pii_and_fallback(self, mocker, monkeypatch):
        """调度器路径应记录桶分布、PII 脱敏数和回退。"""
        monkeypatch.setattr(armor, "ALGO_SMARTCRUSH_ENABLED", True)
        monkeypatch.setattr(armor, "ALGO_EXPERIMENT_MODE", True)
        monkeypatch.setattr(armor, "ALGO_USE_SCHEDULER", True)
        # fake algo_scheduler
        mock_decide = MagicMock()
        mock_decide.size_bucket = "small"
        mocker.patch.object(armor, "algo_scheduler_decide", return_value=mock_decide)
        mock_process = MagicMock(side_effect=[
            {"result": "compressed", "pii_stats": {"total_redactions": 3}, "fallback_reason": None},
            {"result": "compressed", "pii_stats": {"total_redactions": 0}, "fallback_reason": "too_small"},
            {"result": "compressed", "pii_stats": None, "fallback_reason": None},
        ])
        mocker.patch.object(armor, "algo_scheduler_process", side_effect=mock_process)

        msgs = [
            {"type": "message", "message": {"content": "foo"}},
            {"type": "message", "message": {"content": "bar"}},
            {"type": "other", "content": "ignored"},
            {"type": "message", "message": {"content": 12345}},
        ]
        result = armor.armor_pre_compact_hook(msgs, dry_run=False)

        assert result["enabled"] is True
        assert result["mode"] == "scheduler"
        assert result["algorithm"] == "algo_scheduler"
        assert result["filesProcessed"] == 2
        assert result["piiRedactions"] == 3
        assert result["fallbackCount"] == 1
        assert result["decisionsByBucket"].get("small", 0) == 2

    def test_scheduler_dry_run_skips_process_but_records_decisions(self, mocker, monkeypatch):
        """dry_run=True 时只记录决策，不真的跑调度处理。"""
        monkeypatch.setattr(armor, "ALGO_SMARTCRUSH_ENABLED", True)
        monkeypatch.setattr(armor, "ALGO_EXPERIMENT_MODE", True)
        monkeypatch.setattr(armor, "ALGO_USE_SCHEDULER", True)
        mock_decide = MagicMock(size_bucket="tiny")
        mocker.patch.object(armor, "algo_scheduler_decide", return_value=mock_decide)
        mock_process = mocker.patch.object(armor, "algo_scheduler_process")

        msgs = [{"type": "message", "message": {"content": "x"}}]
        result = armor.armor_pre_compact_hook(msgs, dry_run=True)

        assert result["decisionsByBucket"].get("tiny", 0) == 1
        mock_process.assert_not_called()
        assert result["filesProcessed"] == 0

    def test_scheduler_failure_with_fail_safe_swallows(self, mocker, monkeypatch):
        """调度器异常 + ALGO_FAIL_SAFE=True 时静默吞错。"""
        monkeypatch.setattr(armor, "ALGO_SMARTCRUSH_ENABLED", True)
        monkeypatch.setattr(armor, "ALGO_EXPERIMENT_MODE", True)
        monkeypatch.setattr(armor, "ALGO_USE_SCHEDULER", True)
        monkeypatch.setattr(armor, "ALGO_FAIL_SAFE", True)
        mocker.patch.object(armor, "algo_scheduler_decide", side_effect=RuntimeError("boom"))

        msgs = [{"type": "message", "message": {"content": "x"}}]
        result = armor.armor_pre_compact_hook(msgs, dry_run=False)

        assert result["ran"] is True
        assert "boom" in (result["error"] or "")
        assert result["filesProcessed"] == 0

    def test_scheduler_path_no_compression_available(self, mocker, monkeypatch):
        """算法不可用时应直接返回 disabled stats（不发燥）。"""
        monkeypatch.setattr(armor, "_COMPRESSION_AVAILABLE", False)

        result = armor.armor_pre_compact_hook([], dry_run=False)

        assert result["enabled"] is False
        assert result["ran"] is False
        assert result["error"] is None


class TestArmorCompressSkip:
    """armor_compress() 低于阈值 / dry_run 分支。"""

    def test_skip_below_warn_threshold(self, mocker):
        """使用率 < WARN 且非 dry_run 时返回 skip。"""
        fake_check = {"usagePercent": 30.0, "severity": "ok"}
        mocker.patch.object(armor, "armor_check", return_value=fake_check)

        result = armor.armor_compress()

        assert result["action"] == "skip"
        assert "30.0%" in result["reason"]


class TestArmorGuard:
    """armor_guard() 守护循环。"""

    def test_guard_exits_on_keyboard_interrupt(self, mocker):
        """守护循环应可被 KeyboardInterrupt 干净退出。"""
        fake_check = {"usagePercent": 30.0, "severity": "ok", "summary": "ok"}
        mocker.patch.object(armor, "armor_check", return_value=fake_check)
        mocker.patch.object(armor.time, "sleep", side_effect=KeyboardInterrupt)

        armor.armor_guard(interval_s=0)

    def test_guard_triggers_compress_above_alert(self, mocker):
        """使用率超 ALERT 时自动触发 compress。"""
        fake_check = {"usagePercent": 85.0, "severity": "warn", "summary": "near"}
        mocker.patch.object(armor, "armor_check", return_value=fake_check)
        mocker.patch.object(armor, "armor_compress", return_value={"action": "compress"})
        sleep_mock = mocker.patch.object(armor.time, "sleep", side_effect=KeyboardInterrupt)

        armor.armor_guard(interval_s=0)

        assert sleep_mock.called


class TestArmorCompressAsyncExtra:
    """armor_compress_async() 补充覆盖：queue dropped / timeout / failed。"""

    def test_async_queue_full_returns_dropped(self, mocker):
        """queue 已满时返回 dropped。"""
        fake_active = MagicMock()
        fake_active.name = "agent.jsonl"
        mocker.patch.object(armor, "_find_active_session", return_value=fake_active)
        mocker.patch.object(armor, "_read_session_tail", return_value=[{"role": "user"}])

        fake_req = MagicMock()
        mocker.patch("mark42_modules.compress_queue.CompressRequest", return_value=fake_req)
        fake_queue = MagicMock(enqueue=MagicMock(return_value=False), qsize=MagicMock(return_value=42))
        mocker.patch("mark42_modules.compress_queue.get_compress_queue", return_value=fake_queue)

        result = armor.armor_compress_async()

        assert result["status"] == "dropped"
        assert result["reason"] == "queue_full"
        assert result["queue_size"] == 42

    def test_async_wait_timeout_returns_timeout(self, mocker):
        """wait=True 但 req.wait 超时：返回 timeout。"""
        fake_active = MagicMock()
        fake_active.name = "agent.jsonl"
        mocker.patch.object(armor, "_find_active_session", return_value=fake_active)
        mocker.patch.object(armor, "_read_session_tail", return_value=[{"role": "user"}])

        fake_req = MagicMock()
        fake_req.wait.return_value = False
        mocker.patch("mark42_modules.compress_queue.CompressRequest", return_value=fake_req)
        fake_queue = MagicMock(enqueue=MagicMock(return_value=True), qsize=MagicMock(return_value=1))
        mocker.patch("mark42_modules.compress_queue.get_compress_queue", return_value=fake_queue)

        result = armor.armor_compress_async(wait=True)

        assert result["status"] == "timeout"
        assert result["request_id"] == fake_req.request_id

    def test_async_wait_failed_returns_error(self, mocker):
        """wait=True 且 req.error 不为空：返回 failed。"""
        fake_active = MagicMock(name="agent.jsonl")
        mocker.patch.object(armor, "_find_active_session", return_value=fake_active)
        mocker.patch.object(armor, "_read_session_tail", return_value=[])

        fake_req = MagicMock()
        fake_req.wait.return_value = True
        fake_req.error = "scheduler explode"
        mocker.patch("mark42_modules.compress_queue.CompressRequest", return_value=fake_req)
        fake_queue = MagicMock(enqueue=MagicMock(return_value=True), qsize=MagicMock(return_value=1))
        mocker.patch("mark42_modules.compress_queue.get_compress_queue", return_value=fake_queue)

        result = armor.armor_compress_async(wait=True)

        assert result["status"] == "failed"
        assert result["error"] == "scheduler explode"

    def test_async_completed_returns_result(self, mocker):
        """wait=True 且 req.error=None：返回 completed + result。"""
        fake_active = MagicMock(name="agent.jsonl")
        mocker.patch.object(armor, "_find_active_session", return_value=fake_active)
        mocker.patch.object(armor, "_read_session_tail", return_value=[{"role": "user"}])

        fake_req = MagicMock()
        fake_req.wait.return_value = True
        fake_req.error = None
        fake_req.result = {"action": "compress"}
        mocker.patch("mark42_modules.compress_queue.CompressRequest", return_value=fake_req)
        fake_queue = MagicMock(enqueue=MagicMock(return_value=True), qsize=MagicMock(return_value=1))
        mocker.patch("mark42_modules.compress_queue.get_compress_queue", return_value=fake_queue)

        result = armor.armor_compress_async(wait=True)

        assert result["status"] == "completed"
        assert result["result"] == {"action": "compress"}


class TestArmorCompressQueueStatsExtra:
    """armor_compress_queue_stats() 错误路径。"""

    def test_returns_error_when_module_unavailable(self, mocker):
        """队列模块 import 失败时返回 error dict。"""
        mocker.patch(
            "mark42_modules.compress_queue.get_compress_queue",
            side_effect=ImportError("queue broken"),
        )

        result = armor.armor_compress_queue_stats()

        assert "error" in result
        assert "queue broken" in result["error"]