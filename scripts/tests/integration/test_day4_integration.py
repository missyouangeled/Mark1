"""Mark42 阶段 1 Day 4 集成测试（按 2026-07-01 当前实现重写）。

验证 armor_pre_compact_hook 正确接入 algo_scheduler：
1. 调度器路径：显式开 gate 后，scheduler 路径真实运行
2. dry_run 路径：记录决策但不处理内容
3. 大小分层：tiny / small / medium / large 桶都可观察到
4. direct 路径：关闭 scheduler 后退回 SmartCrusher
5. fail-safe：scheduler.process 出错时不抛异常，返回 stats.error
6. 双重门：ALGO_SMARTCRUSH_ENABLED=false 时 hook 完全不工作
7. armor_compress：会真实调用 pre_compact_hook，并把 algoStats 写入 index
"""

import json
import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_SCRIPTS = _THIS_DIR.parent.parent
sys.path.insert(0, str(_SCRIPTS))

from mark42_modules import armor


@pytest.fixture
def algo_enabled(monkeypatch):
    """显式打开 Day4 压缩链需要的所有门控。"""
    monkeypatch.setattr(armor, "ALGO_SMARTCRUSH_ENABLED", True)
    monkeypatch.setattr(armor, "ALGO_EXPERIMENT_MODE", True)
    monkeypatch.setattr(armor, "ALGO_USE_SCHEDULER", True)
    monkeypatch.setattr(armor, "ALGO_FAIL_SAFE", True)
    return monkeypatch


def test_scheduler_path_with_pii(algo_enabled):
    """显式开 gate 后，含 PII 的大 JSON 应走 scheduler。"""
    assert armor._SCHEDULER_AVAILABLE, "调度器模块应该可用"

    pii_json = json.dumps(
        {
            "users": [
                {"email": f"user{i}@example.com", "phone": "13812345678"}
                for i in range(120)
            ],
            "description": "x" * 6000,
        },
        ensure_ascii=False,
    )

    messages = [{
        "type": "message",
        "message": {"role": "user", "content": pii_json},
    }]

    stats = armor.armor_pre_compact_hook(messages, dry_run=False)

    assert stats["enabled"] is True
    assert stats["mode"] == "scheduler"
    assert stats["algorithm"] == "algo_scheduler"
    assert stats["ran"] is True
    assert stats["filesProcessed"] == 1
    assert stats["piiRedactions"] > 0
    assert stats["totalOriginalBytes"] > 0
    assert "medium" in stats["decisionsByBucket"] or "large" in stats["decisionsByBucket"]


def test_dry_run_records_decisions_without_processing(algo_enabled):
    """dry_run 只记录决策分布，不做真实处理。"""
    messages = [
        {
            "type": "message",
            "message": {"role": "user", "content": json.dumps({"x": i, "v": "x" * 200}) * 20},
        }
        for i in range(3)
    ]

    stats = armor.armor_pre_compact_hook(messages, dry_run=True)

    assert stats["enabled"] is True
    assert stats["mode"] == "scheduler"
    assert stats["ran"] is True
    assert stats["filesProcessed"] == 0
    assert stats["totalOriginalBytes"] == 0
    assert stats["totalCrushedBytes"] == 0
    assert sum(stats["decisionsByBucket"].values()) == len(messages)


def test_size_bucketing(algo_enabled):
    """不同大小内容应被归入不同 size bucket。"""
    messages = [
        {"type": "message", "message": {"role": "user", "content": "x" * 100}},
        {"type": "message", "message": {"role": "user", "content": json.dumps({"s": "x" * 4900})}},
        {"type": "message", "message": {"role": "user", "content": "\n".join(["这是一行足够长的中等文本内容。" * 5 for _ in range(120)])}},
        {"type": "message", "message": {"role": "user", "content": "\n".join(["这是超大的长文本内容。" * 8 for _ in range(2000)])}},
    ]

    stats = armor.armor_pre_compact_hook(messages, dry_run=True)
    buckets = stats["decisionsByBucket"]

    assert buckets.get("tiny", 0) >= 1, buckets
    assert buckets.get("small", 0) >= 1, buckets
    assert buckets.get("medium", 0) >= 1, buckets
    assert buckets.get("large", 0) >= 1, buckets


def test_fallback_when_scheduler_disabled(monkeypatch, algo_enabled):
    """关闭 scheduler 后应退回 direct/smartcrush 路径。"""
    monkeypatch.setattr(armor, "ALGO_USE_SCHEDULER", False)

    messages = [
        {
            "type": "message",
            "message": {"role": "user", "content": json.dumps({"i": i, "v": "x" * 100}) * 30},
        }
        for i in range(2)
    ]

    stats = armor.armor_pre_compact_hook(messages, dry_run=False)

    assert stats["enabled"] is True
    assert stats["mode"] == "direct"
    assert stats["algorithm"] == "smartcrush"
    assert stats["filesProcessed"] > 0
    assert stats["piiRedactions"] == 0


def test_fail_safe_on_scheduler_error(monkeypatch, algo_enabled):
    """scheduler.process 抛异常时应记录 error，并保持 fail-safe。"""
    def boom(*args, **kwargs):
        raise RuntimeError("simulated scheduler failure")

    monkeypatch.setattr(armor, "algo_scheduler_process", boom)

    messages = [{
        "type": "message",
        "message": {"role": "user", "content": json.dumps({"x": "y" * 5000})},
    }]

    stats = armor.armor_pre_compact_hook(messages, dry_run=False)

    assert "scheduler failed" in (stats.get("error") or "")
    assert stats["ran"] is True
    assert stats["filesProcessed"] == 0
    assert stats["mode"] == "scheduler"


def test_double_gate_when_algo_disabled(monkeypatch):
    """ALGO_SMARTCRUSH_ENABLED=false 时 hook 应直接返回空 stats。"""
    monkeypatch.setattr(armor, "ALGO_SMARTCRUSH_ENABLED", False)
    monkeypatch.setattr(armor, "ALGO_EXPERIMENT_MODE", True)

    messages = [{
        "type": "message",
        "message": {"role": "user", "content": "x" * 5000},
    }]

    stats = armor.armor_pre_compact_hook(messages, dry_run=False)

    assert stats["enabled"] is False
    assert stats["ran"] is False
    assert stats["mode"] is None
    assert stats["filesProcessed"] == 0


def test_end_to_end_in_armor_compress(monkeypatch, tmp_path, algo_enabled):
    """armor_compress(dry_run=True) 会调用 hook，并把 algoStats 写入 index。"""
    captured = {}

    monkeypatch.setattr(armor, "armor_check", lambda: {"usagePercent": 95})
    monkeypatch.setattr(armor, "_find_active_session", lambda: None)
    monkeypatch.setattr(armor, "_read_session_tail", lambda _path: [])
    monkeypatch.setattr(armor, "_append_broker", lambda *args, **kwargs: None)
    monkeypatch.setattr(armor, "_llm_analyze", lambda messages: None)
    monkeypatch.setattr(
        armor,
        "_classify_messages",
        lambda messages: {"preserved": [], "discarded": [], "totalAnalyzed": 0},
    )

    real_hook = armor.armor_pre_compact_hook

    def wrapped_hook(session_messages, dry_run=False):
        result = real_hook(session_messages, dry_run=dry_run)
        captured["algo_stats"] = result
        return result

    monkeypatch.setattr(armor, "armor_pre_compact_hook", wrapped_hook)

    def fake_save_json(path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if path.name == "memory-index.json":
            captured["index_path"] = path
            captured["index_data"] = data

    monkeypatch.setattr(armor, "ARMOR_STATE", tmp_path)
    monkeypatch.setattr(armor, "_save_json", fake_save_json)

    result = armor.armor_compress(dry_run=True)

    assert result["action"] == "compress"
    assert "algo_stats" in captured
    assert captured["index_path"].exists()
    assert captured["index_data"]["algoStats"] == captured["algo_stats"]


def main():
    return pytest.main([__file__, "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
