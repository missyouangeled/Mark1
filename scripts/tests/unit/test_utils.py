"""utils.py 测试群。

覆盖目标：
  - 轻量 helper: 时间 / JSON / mtime
  - session 选择: lock 优先 + fallback
  - token 估算: simple / smart 容错与分支
  - 文件扫描: 跳过规则
  - context window: 多级回退策略

边界：
  - 不碰重型业务链路
  - 不依赖真实用户 home / 真实 openclaw 配置
"""

import builtins
import json
from pathlib import Path

from mark42_modules import utils


class _StatBoomPath:
    def stat(self):
        raise OSError("boom")


class TestBasicHelpers:
    def test_now_iso_returns_asia_shanghai_iso_string(self):
        ts = utils._now_iso()
        assert isinstance(ts, str)
        assert "T" in ts
        assert ts.endswith("+08:00")

    def test_now_ts_returns_float_timestamp(self):
        ts = utils._now_ts()
        assert isinstance(ts, float)
        assert ts > 0

    def test_load_json_missing_invalid_and_oserror_return_empty(self, monkeypatch, tmp_path):
        missing = tmp_path / "missing.json"
        assert utils._load_json(missing) == {}

        invalid = tmp_path / "invalid.json"
        invalid.write_text("{bad json", encoding="utf-8")
        assert utils._load_json(invalid) == {}

        ok = tmp_path / "ok.json"
        ok.write_text('{"a": 1}', encoding="utf-8")

        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if Path(path) == ok:
                raise OSError("cannot open")
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", fake_open)
        assert utils._load_json(ok) == {}

    def test_save_json_creates_parent_and_roundtrip(self, tmp_path):
        path = tmp_path / "deep" / "dir" / "data.json"
        utils._save_json(path, {"x": 1, "y": "中"})
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == {"x": 1, "y": "中"}

    def test_append_broker_writes_jsonl_event(self):
        utils._append_broker("unit", "test.event", "label", "info", "summary", {"k": 1})

        content = utils.MARK42_BROKER_EVENTS.read_text(encoding="utf-8")
        assert "test.event" in content
        assert "\"sourceView\": \"unit\"" in content
        assert "\"metadata\": {\"k\": 1}" in content

    def test_safe_mtime_missing_returns_negative_one(self, tmp_path):
        assert utils._safe_mtime(tmp_path / "gone.txt") == -1.0


class TestFindActiveSession:
    def test_prefers_recent_live_lock(self, monkeypatch, tmp_path):
        home = Path.home()
        sessions = home / ".openclaw" / "agents" / "main" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)

        live_jsonl = sessions / "live.jsonl"
        live_jsonl.write_text("{}\n", encoding="utf-8")
        live_lock = sessions / "live.jsonl.lock"
        live_lock.write_text("", encoding="utf-8")

        stale_jsonl = sessions / "stale.jsonl"
        stale_jsonl.write_text("{}\n", encoding="utf-8")
        stale_lock = sessions / "stale.jsonl.lock"
        stale_lock.write_text("", encoding="utf-8")

        now = 10_000.0
        monkeypatch.setattr(utils.time, "time", lambda: now)
        live_mtime = now - 5
        stale_mtime = now - utils.LOCK_MAX_AGE - 5
        live_lock.touch()
        stale_lock.touch()
        import os
        os.utime(live_lock, (live_mtime, live_mtime))
        os.utime(stale_lock, (stale_mtime, stale_mtime))

        assert utils._find_active_session() == live_jsonl

    def test_skips_missing_and_stale_lock_before_fallback(self, monkeypatch):
        home = Path.home()
        sessions = home / ".openclaw" / "agents" / "main" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)

        fresh_missing_lock = sessions / "ghost.jsonl.lock"
        fresh_missing_lock.write_text("", encoding="utf-8")
        stale_lock = sessions / "stale.jsonl.lock"
        stale_lock.write_text("", encoding="utf-8")
        fallback = sessions / "fallback.jsonl"
        fallback.write_text("{}\n", encoding="utf-8")

        now = 20_000.0
        monkeypatch.setattr(utils.time, "time", lambda: now)
        import os
        os.utime(fresh_missing_lock, (now - 5, now - 5))
        os.utime(stale_lock, (now - utils.LOCK_MAX_AGE - 5, now - utils.LOCK_MAX_AGE - 5))

        assert utils._find_active_session() == fallback

    def test_skips_lock_when_mtime_probe_returns_negative(self, monkeypatch):
        home = Path.home()
        sessions = home / ".openclaw" / "agents" / "main" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)

        bad_lock = sessions / "bad.jsonl.lock"
        bad_lock.write_text("", encoding="utf-8")
        fallback = sessions / "fallback2.jsonl"
        fallback.write_text("{}\n", encoding="utf-8")

        real_safe_mtime = utils._safe_mtime

        def fake_safe_mtime(path):
            if path == bad_lock:
                return -1.0
            return real_safe_mtime(path)

        monkeypatch.setattr(utils, "_safe_mtime", fake_safe_mtime)
        assert utils._find_active_session() == fallback

    def test_falls_back_to_latest_jsonl_and_skips_special_suffixes(self, tmp_path):
        home = Path.home()
        sessions = home / ".openclaw" / "agents" / "main" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)

        old = sessions / "old.jsonl"
        old.write_text("{}\n", encoding="utf-8")
        latest = sessions / "latest.jsonl"
        latest.write_text("{}\n", encoding="utf-8")
        skipped = sessions / "skip.reset.jsonl"
        skipped.write_text("{}\n", encoding="utf-8")
        skipped2 = sessions / "skip.deleted.jsonl"
        skipped2.write_text("{}\n", encoding="utf-8")
        skipped3 = sessions / "skip.trajectory.jsonl"
        skipped3.write_text("{}\n", encoding="utf-8")

        import os
        os.utime(old, (100, 100))
        os.utime(latest, (200, 200))
        os.utime(skipped, (300, 300))
        os.utime(skipped2, (400, 400))
        os.utime(skipped3, (500, 500))

        assert utils._find_active_session() == latest


class TestTokenEstimate:
    def test_estimate_tokens_success_and_oserror_fallback(self, tmp_path):
        path = tmp_path / "session.jsonl"
        path.write_bytes(b"x" * (2 * 1024 * 1024))

        result = utils._estimate_tokens(path)
        assert result["estimatedTokens"] == (2 * 1024 * 1024) // utils.BYTES_PER_KTOKEN * 1000
        assert result["fileSizeMB"] > 0

        class _PathLike:
            def stat(self):
                raise OSError("boom")

        failed = utils._estimate_tokens(_PathLike())
        assert failed == {"estimatedTokens": 0, "fileSizeMB": 0}

    def test_estimate_tokens_smart_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")

        result = utils._estimate_tokens_smart(path)
        assert result["estimatedTokens"] == 0
        assert result["method"] == "smart"
        assert result["scannedMessages"] == 0

    def test_estimate_tokens_smart_invalid_env_and_open_error(self, monkeypatch, tmp_path):
        path = tmp_path / "session.jsonl"
        path.write_text('{"content": "abc"}\n' * 200000, encoding="utf-8")
        monkeypatch.setenv("MARK42_TOKEN_SCAN_LINES", "not-an-int")
        monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("nope")))

        result = utils._estimate_tokens_smart(path)
        assert result["estimatedTokens"] == 0
        assert result["fileSizeMB"] > 0
        assert result["scannedMessages"] == 0

    def test_estimate_tokens_smart_handles_mixed_message_shapes(self, tmp_path):
        path = tmp_path / "session.jsonl"
        lines = [
            "not-json",
            json.dumps({"message": "not-a-dict"}, ensure_ascii=False),
            json.dumps({"content": [{"text": "中文A"}, {"text": "B"}]}, ensure_ascii=False),
            json.dumps({"content": 123}, ensure_ascii=False),
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = utils._estimate_tokens_smart(path)
        assert result["scannedMessages"] == 1
        assert result["zhChars"] >= 2
        assert result["enChars"] >= 2
        assert result["estimatedTokens"] > 0

    def test_estimate_tokens_smart_falls_back_when_projection_calc_errors(self, monkeypatch, tmp_path):
        path = tmp_path / "session.jsonl"
        path.write_text((json.dumps({"content": "中文abc"}, ensure_ascii=False) + "\n") * 5, encoding="utf-8")

        real_sum = builtins.sum
        called = {"n": 0}

        def fake_sum(iterable, start=0):
            called["n"] += 1
            if called["n"] == 1:
                raise ValueError("sum failed")
            return real_sum(iterable, start)

        monkeypatch.setattr(builtins, "sum", fake_sum)
        result = utils._estimate_tokens_smart(path)

        assert result["estimatedTokens"] > 0
        assert result["zhChars"] >= 2
        assert result["enChars"] >= 3

    def test_estimate_tokens_smart_outer_oserror_returns_zero(self):
        result = utils._estimate_tokens_smart(_StatBoomPath())
        assert result["estimatedTokens"] == 0
        assert result["fileSizeMB"] == 0

    def test_estimate_tokens_smart_uses_non_projection_branch(self, tmp_path):
        path = tmp_path / "single.jsonl"
        path.write_text(json.dumps({"content": "中a"}, ensure_ascii=False) + "\n", encoding="utf-8")

        result = utils._estimate_tokens_smart(path)

        assert result["fileSizeMB"] >= 0
        assert result["estimatedTokens"] >= 0
        assert result["method"] == "smart"

    def test_estimate_tokens_smart_handles_non_dict_inner(self, monkeypatch, tmp_path):
        path = tmp_path / "session.jsonl"
        path.write_text('{"content": "ignored"}\n', encoding="utf-8")

        class _FakeObj:
            def get(self, _key, _default=None):
                return None

        monkeypatch.setattr(utils.json, "loads", lambda _raw: _FakeObj())
        result = utils._estimate_tokens_smart(path)
        assert result["scannedMessages"] == 0


class TestListProjectFiles:
    def test_returns_single_file_directly(self, tmp_path):
        file = tmp_path / "one.txt"
        file.write_text("x", encoding="utf-8")
        assert utils._list_project_files(file) == [file]

    def test_skips_hidden_and_known_patterns(self, tmp_path):
        keep = tmp_path / "src" / "keep.py"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text("print(1)", encoding="utf-8")

        hidden = tmp_path / ".hidden.txt"
        hidden.write_text("x", encoding="utf-8")

        pycache = tmp_path / "src" / "__pycache__" / "x.pyc"
        pycache.parent.mkdir(parents=True, exist_ok=True)
        pycache.write_bytes(b"x")

        node = tmp_path / "node_modules" / "pkg" / "index.js"
        node.parent.mkdir(parents=True, exist_ok=True)
        node.write_text("x", encoding="utf-8")

        meta = tmp_path / "data" / ".meta" / "meta.json"
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text("{}", encoding="utf-8")

        files = utils._list_project_files(tmp_path)
        assert keep in files
        assert hidden not in files
        assert pycache not in files
        assert node not in files
        assert meta not in files


class TestContextWindowLookup:
    def test_lookup_context_window_match_and_none(self):
        oc = {
            "models": {
                "providers": {
                    "minimax": {
                        "models": [
                            {"id": "MiniMax-M3", "contextWindow": 111111},
                            {"name": "fallback-name", "contextWindow": 222222},
                        ]
                    }
                }
            }
        }
        assert utils._lookup_context_window(oc, "minimax", "MiniMax-M3") == 111111
        assert utils._lookup_context_window(oc, "minimax", "fallback-name") == 222222
        assert utils._lookup_context_window(oc, "minimax", "missing") is None

    def test_get_context_window_prefers_primary_model(self, tmp_path):
        home = Path.home()
        home.mkdir(parents=True, exist_ok=True)
        oc_path = home / ".openclaw" / "openclaw.json"
        oc_path.parent.mkdir(parents=True, exist_ok=True)
        oc_path.write_text(json.dumps({
            "agents": {"defaults": {"model": {"primary": "minimax/MiniMax-M3"}}},
            "models": {"providers": {"minimax": {"models": [{"id": "MiniMax-M3", "contextWindow": 54321}]}}},
        }), encoding="utf-8")

        assert utils._get_context_window() == 54321

    def test_get_context_window_falls_back_to_first_provider_model(self):
        home = Path.home()
        home.mkdir(parents=True, exist_ok=True)
        oc_path = home / ".openclaw" / "openclaw.json"
        oc_path.parent.mkdir(parents=True, exist_ok=True)
        oc_path.write_text(json.dumps({
            "agents": {"defaults": {"model": {"primary": "badformat"}}},
            "models": {"providers": {
                "foo": {"models": [{"id": "x", "contextWindow": 32123}]},
                "bar": {"models": [{"id": "y", "contextWindow": 99999}]},
            }},
        }), encoding="utf-8")

        assert utils._get_context_window() == 32123

    def test_get_context_window_falls_back_to_config_then_default(self, monkeypatch, tmp_path):
        home = Path.home()
        home.mkdir(parents=True, exist_ok=True)
        oc_path = home / ".openclaw" / "openclaw.json"
        oc_path.parent.mkdir(parents=True, exist_ok=True)
        oc_path.write_text("{bad json", encoding="utf-8")

        config_path = tmp_path / "config.json"
        monkeypatch.setattr(utils, "CONFIG_PATH", config_path)
        utils._save_json(config_path, {"contextWindow": 76543})
        assert utils._get_context_window() == 76543

        utils._save_json(config_path, {"contextWindow": 0})
        assert utils._get_context_window() == utils.DEFAULT_CONTEXT_WINDOW

    def test_get_context_window_handles_primary_parse_exception(self, monkeypatch):
        home = Path.home()
        home.mkdir(parents=True, exist_ok=True)
        oc_path = home / ".openclaw" / "openclaw.json"
        oc_path.parent.mkdir(parents=True, exist_ok=True)
        oc_path.write_text(json.dumps({"agents": object()}, default=str), encoding="utf-8")

        monkeypatch.setattr(utils, "_load_json", lambda _path: {"contextWindow": 45678})
        assert utils._get_context_window() == 45678

    def test_get_context_window_handles_provider_iteration_exception(self, monkeypatch):
        home = Path.home()
        home.mkdir(parents=True, exist_ok=True)
        oc_path = home / ".openclaw" / "openclaw.json"
        oc_path.parent.mkdir(parents=True, exist_ok=True)
        oc_path.write_text(json.dumps({
            "agents": {"defaults": {"model": {"primary": "badformat"}}},
            "models": {"providers": []},
        }), encoding="utf-8")

        monkeypatch.setattr(utils, "_load_json", lambda _path: {"contextWindow": 34567})
        assert utils._get_context_window() == 34567

    def test_get_context_window_handles_config_exception(self, monkeypatch):
        home = Path.home()
        home.mkdir(parents=True, exist_ok=True)
        oc_path = home / ".openclaw" / "openclaw.json"
        oc_path.parent.mkdir(parents=True, exist_ok=True)
        oc_path.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(utils, "_load_json", lambda _path: (_ for _ in ()).throw(RuntimeError("bad cfg")))
        assert utils._get_context_window() == utils.DEFAULT_CONTEXT_WINDOW


# ═══════════════════════════════════════════════════════════════════════════
# 【2026-07-13 新增】safe_call 装饰器 + 错误日志留痕 测试
# ═══════════════════════════════════════════════════════════════════════════


class TestSafeCall:
    """safe_call 装饰器是本次错误处理收口的核心。"""

    def test_safe_call_passes_through_success(self):
        @utils.safe_call(default=-1)
        def ok():
            return 42
        assert ok() == 42

    def test_safe_call_returns_default_on_exception(self, monkeypatch, tmp_path):
        err_log = tmp_path / "errors.jsonl"
        monkeypatch.setattr(utils, "ERRORS_FILE", err_log)

        @utils.safe_call(default="fallback", label="boom_test")
        def boom():
            raise RuntimeError("kaboom")
        assert boom() == "fallback"
        assert err_log.exists()
        lines = err_log.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["label"] == "boom_test"
        assert entry["excType"] == "RuntimeError"
        assert "kaboom" in entry["excMsg"]

    def test_safe_call_uses_func_name_as_label_by_default(self, monkeypatch, tmp_path):
        err_log = tmp_path / "errors.jsonl"
        monkeypatch.setattr(utils, "ERRORS_FILE", err_log)

        @utils.safe_call(default=None)
        def my_named_func():
            raise ValueError("x")
        my_named_func()
        entry = json.loads(err_log.read_text(encoding="utf-8").strip())
        assert entry["label"] == "my_named_func"

    def test_safe_call_does_not_swallow_keyboard_interrupt(self):
        @utils.safe_call(default=None)
        def interrupted():
            raise KeyboardInterrupt("user pressed ctrl+c")
        try:
            interrupted()
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError("safe_call 不应吞 KeyboardInterrupt")

    def test_safe_call_does_not_swallow_systemexit(self):
        @utils.safe_call(default=None)
        def exiting():
            raise SystemExit(1)
        try:
            exiting()
        except SystemExit:
            pass
        else:
            raise AssertionError("safe_call 不应吞 SystemExit")

    def test_safe_call_reraise_propagates_exception(self):
        @utils.safe_call(default=None, reraise=True)
        def boom():
            raise RuntimeError("must propagate")
        try:
            boom()
        except RuntimeError:
            pass
        else:
            raise AssertionError("reraise=True 应该向上抛")

    def test_safe_call_rotate_truncates_when_over_max(self, monkeypatch, tmp_path):
        err_log = tmp_path / "errors.jsonl"
        monkeypatch.setattr(utils, "ERRORS_FILE", err_log)
        monkeypatch.setattr(utils, "MAX_ERRORS_LINES", 10)

        @utils.safe_call(default=0)
        def n():
            raise RuntimeError("n")
        for _ in range(20):
            n()
        lines = err_log.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) <= 2 * (utils.MAX_ERRORS_LINES // 2)
        assert len(lines) > 0

    def test_safe_call_handles_errors_jsonl_write_failure_silently(self, monkeypatch, tmp_path):
        bad_path = tmp_path / "nonexistent_dir" / "errors.jsonl"
        monkeypatch.setattr(utils, "ERRORS_FILE", bad_path)

        @utils.safe_call(default="x")
        def boom():
            raise RuntimeError("y")
        assert boom() == "x"

    def test_safe_call_preserves_function_metadata(self):
        @utils.safe_call(default=None, label="meta")
        def documented_func():
            """my docstring"""
            return 1
        assert documented_func.__name__ == "documented_func"
        assert "my docstring" in (documented_func.__doc__ or "")
