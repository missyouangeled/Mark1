"""ContextState 持久化测试（方案 44 Phase 2）。

重点钉住：
    1. 写入必须原子 —— 崩溃不留截断文件；
    2. 损坏的历史状态必须导致「全量回退」而非静默用坏数据；
    3. 归档目录不参与 keep_versions 轮替（方案 §14）。
"""

from __future__ import annotations

import json

import pytest

from mark42.audit.state_store import (
    ARCHIVE_SUFFIX,
    CURRENT_FILENAME,
    StateStore,
)
from mark42.context_state import new_empty_state


@pytest.fixture
def store(tmp_path):
    return StateStore(tmp_path / "context_state", keep_versions=3)


def _state(intent="目标"):
    st = new_empty_state(session_intent=intent)
    st.constraints = [{"constraint_id": "c1", "text": "只用中文",
                       "strength": "hard", "priority": "P0",
                       "evidence": "SOUL.md:6"}]
    return st


# ── 基础读写 ──────────────────────────────────────────


class TestBasicIO:
    def test_load_from_empty_dir_is_fresh_start(self, store):
        res = store.load_current()
        assert res.found is False
        assert res.error == ""
        assert res.is_fresh_start() is True
        assert res.state.item_count() == 0

    def test_save_then_load(self, store):
        st = _state("按方案 44 干活")
        store.save(st)
        res = store.load_current()
        assert res.found is True
        assert res.state.session_intent == "按方案 44 干活"
        assert len(res.state.hard_constraints()) == 1

    def test_save_creates_both_current_and_version(self, store):
        store.save(_state())
        assert (store.dir / CURRENT_FILENAME).exists()
        assert len(store.versions()) == 1

    def test_fingerprint_survives_roundtrip(self, store):
        st = _state()
        store.save(st)
        assert store.load_current().state.fingerprint() == st.fingerprint()

    def test_current_is_valid_json(self, store):
        store.save(_state())
        json.loads((store.dir / CURRENT_FILENAME).read_text(encoding="utf-8"))

    def test_no_temp_files_left(self, store):
        for i in range(5):
            store.save(_state(f"目标{i}"))
        assert list(store.dir.glob("*.tmp")) == []


# ── 损坏容忍：必须全量回退，不得静默用坏数据 ──────────


class TestCorruptionHandling:
    def test_truncated_json_triggers_fallback(self, store):
        store.save(_state())
        store.current_path.write_text('{"schema_version": 1, "sess',
                                      encoding="utf-8")
        res = store.load_current()
        assert res.found is False
        assert "JSONDecodeError" in res.error
        assert res.is_fresh_start() is False  # 有 error，不是首次

    def test_non_dict_json_triggers_fallback(self, store):
        store.save(_state())
        store.current_path.write_text('["a", "list"]', encoding="utf-8")
        res = store.load_current()
        assert res.found is False
        assert "TypeError" in res.error

    def test_schema_violation_triggers_fallback(self, store):
        """能解析但违反契约的状态，也必须拒用。"""
        store.save(_state())
        store.current_path.write_text(
            json.dumps({"schema_version": 999, "session_intent": "x"}),
            encoding="utf-8")
        res = store.load_current()
        assert res.found is False
        assert "未通过校验" in res.error

    def test_fallback_state_is_usable_empty(self, store):
        store.current_path.parent.mkdir(parents=True, exist_ok=True)
        store.current_path.write_text("garbage", encoding="utf-8")
        res = store.load_current()
        assert res.state.item_count() == 0
        assert res.state.schema_version >= 1


# ── 版本轮替 ──────────────────────────────────────────


class TestRotation:
    def test_keeps_only_n_versions(self, store):
        for i in range(10):
            store.save(_state(f"目标{i}"), timestamp=f"2026080{i}-000000")
        assert len(store.versions()) == 3

    def test_keeps_the_newest(self, store):
        for i in range(5):
            store.save(_state(f"目标{i}"), timestamp=f"2026080{i}-000000")
        names = [p.name for p in store.versions()]
        assert "context-state-20260804-000000.json" in names
        assert "context-state-20260800-000000.json" not in names

    def test_current_always_latest(self, store):
        for i in range(5):
            store.save(_state(f"目标{i}"), timestamp=f"2026080{i}-000000")
        assert store.load_current().state.session_intent == "目标4"

    def test_keep_versions_minimum_one(self, tmp_path):
        s = StateStore(tmp_path / "x", keep_versions=0)
        assert s.keep_versions == 1


# ── 归档（方案 §14）──────────────────────────────────


class TestArchive:
    def test_archive_moves_directory(self, store):
        store.save(_state())
        target = store.archive(reason="Phase 2 回滚演练")
        assert target is not None
        assert target.endswith(ARCHIVE_SUFFIX)
        assert not store.dir.exists()

    def test_archive_writes_reason(self, store):
        from pathlib import Path
        store.save(_state())
        target = Path(store.archive(reason="因 SLO 未达标回滚"))
        assert (target / "ARCHIVE_REASON.txt").read_text(
            encoding="utf-8") == "因 SLO 未达标回滚"

    def test_archived_not_counted_in_rotation(self, store):
        """归档目录不参与 keep_versions 轮替。"""
        store.save(_state())
        store.archive(reason="r1")
        for i in range(5):
            store.save(_state(f"新{i}"), timestamp=f"2026081{i}-000000")
        assert len(store.versions()) == 3       # 新目录正常轮替
        assert len(store.archived_dirs()) == 1  # 归档仍在

    def test_archive_nonexistent_dir_returns_none(self, tmp_path):
        assert StateStore(tmp_path / "nope").archive() is None

    def test_multiple_archives_coexist(self, store):
        import time
        store.save(_state())
        store.archive(reason="r1")
        store.save(_state())
        time.sleep(1.05)  # 归档目录名按秒，避免同名
        store.archive(reason="r2")
        assert len(store.archived_dirs()) == 2

    def test_can_start_fresh_after_archive(self, store):
        store.save(_state("旧"))
        store.archive()
        assert store.load_current().is_fresh_start() is True
        store.save(_state("新"))
        assert store.load_current().state.session_intent == "新"


# ── 观测 ──────────────────────────────────────────────


class TestStats:
    def test_stats_on_empty(self, store):
        s = store.stats()
        assert s["hasCurrent"] is False
        assert s["versionCount"] == 0
        assert s["archivedCount"] == 0

    def test_stats_after_save(self, store):
        st = _state()
        store.save(st)
        s = store.stats()
        assert s["hasCurrent"] is True
        assert s["versionCount"] == 1
        assert s["itemCount"] == st.item_count()
        assert s["fingerprint"] == st.fingerprint()

    def test_stats_reports_load_error(self, store):
        store.current_path.parent.mkdir(parents=True, exist_ok=True)
        store.current_path.write_text("broken", encoding="utf-8")
        assert store.stats()["loadError"]

    def test_stats_json_serializable(self, store):
        store.save(_state())
        json.dumps(store.stats(), ensure_ascii=False)
