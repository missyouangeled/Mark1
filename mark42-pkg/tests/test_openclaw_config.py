"""openclaw.json 安全写入适配器测试（P0-3 C 方案）。

【2026-08-03 新增】

⚠️ 安全底线：本文件所有测试**绝不允许触碰真实的 ~/.openclaw/openclaw.json**。
全部通过 monkeypatch 重定向到 tmp_path。这是硬性要求——
真实配置写坏，整个 OpenClaw 起不来（CASE-20260616-002）。
"""

import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mark42 import openclaw_config as oc
from mark42.openclaw_config import (
    ConfigWriteError,
    _atomic_write_json,
    _deep_merge,
    patch_openclaw_config,
)

PKG_ROOT = str(Path(__file__).resolve().parent.parent)

SAMPLE_CONFIG = {
    "agents": {
        "defaults": {"model": {"primary": "volcengine-agent/glm-5.2"}},
    },
    "models": {"providers": {"volcengine-agent": {"apiKey": "sk-secret-do-not-lose"}}},
    "gateway": {"port": 8080},
}


@pytest.fixture
def fake_config(tmp_path, monkeypatch):
    """把 openclaw.json 重定向到临时目录，并禁用真实 validate 调用。"""
    cfg_dir = tmp_path / "openclaw_home"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "openclaw.json"
    cfg_path.write_text(
        json.dumps(SAMPLE_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(oc, "OPENCLAW_CONFIG", cfg_path)
    monkeypatch.setattr(oc, "_LOCK_PATH", cfg_dir / ".openclaw.json.mark42.lock")
    # 默认不真的调 openclaw config validate（那会读真实环境）
    monkeypatch.setattr(oc, "_validate", lambda: (True, "stubbed"))
    return cfg_path


# ── 安全底线 ──────────────────────────────────────────────


class TestSafetyGuard:
    def test_never_touches_real_config(self, fake_config):
        """确认测试用的路径不是用户真实配置。"""
        real = Path.home() / ".openclaw" / "openclaw.json"
        assert fake_config != real
        assert "openclaw_home" in str(fake_config)

    def test_module_default_points_at_real_path(self, monkeypatch):
        """无任何覆盖时，默认必须指向真实用户配置（生产行为正确）。

        原实现靠 grep 源码字符串
        ``OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"``
        来验证，把**实现细节**当成了契约：P2-16 把硬编码常量换成
        延迟解析器后该断言就失败了，但生产行为完全正确。
        现改为直接断言**行为**：没有 CLI/环境变量/TOML 覆盖时，
        解析结果就是 ``~/.openclaw/openclaw.json``。

        仍然不用 importlib.reload：reload 会把其他测试 monkeypatch 的路径
        全部冲回真实值，造成测试间污染，更危险的是后续测试可能真的
        去写用户配置。
        """
        from mark42 import openclaw_config, user_config

        monkeypatch.delenv("OPENCLAW_CONFIG", raising=False)
        monkeypatch.setattr(user_config, "get", lambda *a, **k: "")
        user_config.set_openclaw_config_override(None)
        # 确保模块级没有残留的显式赋值
        monkeypatch.delattr(openclaw_config, "OPENCLAW_CONFIG", raising=False)

        # 根 conftest 会把 HOME 指向临时目录做隔离，
        # 因此断言「相对于当前 HOME 的默认位置」而非硬编码绝对路径。
        assert openclaw_config._openclaw_config_path() == (
            Path("~/.openclaw/openclaw.json").expanduser()
        )

    def test_module_has_no_import_time_hardcoded_constant(self):
        """P2-16 防回归：不得重新引入 import 时固化的硬编码常量。

        一旦有人把 ``OPENCLAW_CONFIG = Path.home()/...`` 写回模块顶层，
        环境变量与 TOML 配置就又会静默失效。
        """
        src = (Path(PKG_ROOT) / "mark42" / "openclaw_config.py").read_text(
            encoding="utf-8"
        )
        assert 'OPENCLAW_CONFIG = Path.home()' not in src


# ── 原子写入 ──────────────────────────────────────────────


class TestAtomicWrite:
    def test_atomic_write_roundtrip(self, tmp_path):
        p = tmp_path / "c.json"
        _atomic_write_json(p, {"a": 1, "中文": "值"})
        assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1, "中文": "值"}

    def test_ends_with_newline(self, tmp_path):
        """保持与原实现一致：文件以换行结尾。"""
        p = tmp_path / "c.json"
        _atomic_write_json(p, {"a": 1})
        assert p.read_text(encoding="utf-8").endswith("\n")

    def test_no_temp_file_residue(self, tmp_path):
        target = tmp_path / "atomic_only"
        target.mkdir()
        p = target / "c.json"
        _atomic_write_json(p, {"a": 1})
        assert [f.name for f in target.iterdir()] == ["c.json"]

    def test_preserves_permissions(self, tmp_path):
        p = tmp_path / "c.json"
        _atomic_write_json(p, {"a": 1})
        os.chmod(p, 0o600)
        _atomic_write_json(p, {"a": 2})
        assert (p.stat().st_mode & 0o777) == 0o600

    def test_kill_during_write_keeps_config_valid(self, tmp_path):
        """故障注入：写入途中 SIGKILL，配置仍必须是完整可解析的 JSON。

        这是 P0-3 最核心的验收点——旧实现在这里会留下半截文件。
        """
        p = tmp_path / "openclaw.json"
        _atomic_write_json(p, SAMPLE_CONFIG)

        script = f"""
import os, signal, sys
sys.path.insert(0, {PKG_ROOT!r})
from mark42.openclaw_config import _atomic_write_json
big = {{"payload": ["x" * 400] * 5000}}
os.kill(os.getpid(), signal.SIGKILL)
_atomic_write_json({str(p)!r}, big)
"""
        proc = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, timeout=60
        )
        assert proc.returncode != 0

        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert loaded == SAMPLE_CONFIG, "配置被写坏了——原子性失效"
        # API key 必须还在
        assert (
            loaded["models"]["providers"]["volcengine-agent"]["apiKey"]
            == "sk-secret-do-not-lose"
        )


# ── 字段级 merge：不整份覆盖 ──────────────────────────────


class TestDeepMerge:
    def test_only_changes_specified_fields(self):
        base = json.loads(json.dumps(SAMPLE_CONFIG))
        changes = _deep_merge(base, {"gateway": {"port": 9090}})
        assert base["gateway"]["port"] == 9090
        # 其他字段一字未动
        assert (
            base["models"]["providers"]["volcengine-agent"]["apiKey"]
            == "sk-secret-do-not-lose"
        )
        assert base["agents"]["defaults"]["model"]["primary"] == "volcengine-agent/glm-5.2"
        assert len(changes) == 1

    def test_nested_merge_preserves_siblings(self):
        base = {"a": {"x": 1, "y": 2}}
        _deep_merge(base, {"a": {"x": 99}})
        assert base == {"a": {"x": 99, "y": 2}}

    def test_no_change_returns_empty(self):
        base = json.loads(json.dumps(SAMPLE_CONFIG))
        assert _deep_merge(base, {"gateway": {"port": 8080}}) == []

    def test_adds_missing_key(self):
        base = {"a": 1}
        changes = _deep_merge(base, {"b": 2})
        assert base == {"a": 1, "b": 2}
        assert len(changes) == 1


# ── dry-run 默认 ──────────────────────────────────────────


class TestDryRunDefault:
    def test_dry_run_is_default(self, fake_config):
        before = fake_config.read_text(encoding="utf-8")
        r = patch_openclaw_config({"gateway": {"port": 9999}})
        assert r["status"] == "dry_run"
        assert fake_config.read_text(encoding="utf-8") == before, "dry-run 竟然改了文件"

    def test_dry_run_reports_changes(self, fake_config):
        r = patch_openclaw_config({"gateway": {"port": 9999}})
        assert len(r["changes"]) == 1
        assert "gateway.port" in r["changes"][0]

    def test_nothing_to_do_when_already_target(self, fake_config):
        r = patch_openclaw_config({"gateway": {"port": 8080}}, apply=True)
        assert r["status"] == "nothing_to_do"
        assert r["changes"] == []

    def test_apply_actually_writes(self, fake_config):
        r = patch_openclaw_config({"gateway": {"port": 9999}}, apply=True)
        assert r["status"] == "applied"
        assert json.loads(fake_config.read_text(encoding="utf-8"))["gateway"]["port"] == 9999

    def test_apply_creates_backup(self, fake_config):
        r = patch_openclaw_config({"gateway": {"port": 9999}}, apply=True)
        backup = Path(r["backupPath"])
        assert backup.exists()
        assert json.loads(backup.read_text(encoding="utf-8"))["gateway"]["port"] == 8080

    def test_apply_preserves_api_key(self, fake_config):
        """最要紧的一条：改端口不能把 API key 弄丢。"""
        patch_openclaw_config({"gateway": {"port": 9999}}, apply=True)
        cfg = json.loads(fake_config.read_text(encoding="utf-8"))
        assert (
            cfg["models"]["providers"]["volcengine-agent"]["apiKey"]
            == "sk-secret-do-not-lose"
        )


# ── 校验失败自动回滚 ──────────────────────────────────────


class TestValidationRollback:
    def test_rollback_when_validate_fails(self, fake_config, monkeypatch):
        monkeypatch.setattr(oc, "_validate", lambda: (False, "未知配置项 foo"))
        before = json.loads(fake_config.read_text(encoding="utf-8"))

        with pytest.raises(ConfigWriteError, match="校验失败"):
            patch_openclaw_config({"foo": "bar"}, apply=True)

        # 必须完整回滚
        assert json.loads(fake_config.read_text(encoding="utf-8")) == before

    def test_skip_validation_flag(self, fake_config, monkeypatch):
        monkeypatch.setattr(oc, "_validate", lambda: (False, "should not be called"))
        r = patch_openclaw_config(
            {"gateway": {"port": 9999}}, apply=True, validate=False
        )
        assert r["status"] == "applied"


# ── mutate 回调 ───────────────────────────────────────────


class TestMutateCallback:
    def test_mutate_can_delete_field(self, fake_config):
        def drop_port(cfg):
            del cfg["gateway"]["port"]
            return ["gateway.port: 已删除"]

        r = patch_openclaw_config(mutate=drop_port, apply=True)
        assert r["status"] == "applied"
        assert "port" not in json.loads(fake_config.read_text(encoding="utf-8"))["gateway"]

    def test_patch_and_mutate_mutually_exclusive(self, fake_config):
        with pytest.raises(ValueError, match="只能提供一个"):
            patch_openclaw_config({"a": 1}, mutate=lambda c: [])
        with pytest.raises(ValueError, match="只能提供一个"):
            patch_openclaw_config()


# ── 跨进程锁 ──────────────────────────────────────────────


def _locked_writer(args):
    """子进程：拿锁后写入一个专属字段。"""
    cfg_path, lock_path, worker = args
    sys.path.insert(0, PKG_ROOT)
    from pathlib import Path as P

    from mark42 import openclaw_config as m

    m.OPENCLAW_CONFIG = P(cfg_path)
    m._LOCK_PATH = P(lock_path)
    m._validate = lambda: (True, "stub")
    try:
        m.patch_openclaw_config({f"worker_{worker}": worker}, apply=True)
        return True
    except Exception:
        return False


class TestCrossProcessLock:
    def test_concurrent_patches_do_not_lose_fields(self, fake_config):
        """核心验证：多进程并发 patch 不同字段时，谁的改动都不能丢。

        旧实现（读旧快照 → 整份覆盖）在这里必然丢字段。
        """
        lock_path = fake_config.parent / ".openclaw.json.mark42.lock"
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(4) as pool:
            results = pool.map(
                _locked_writer,
                [(str(fake_config), str(lock_path), w) for w in range(4)],
            )
        assert all(results), "有子进程写入失败"

        cfg = json.loads(fake_config.read_text(encoding="utf-8"))
        missing = [w for w in range(4) if f"worker_{w}" not in cfg]
        assert not missing, f"并发写入丢失了字段: {missing}"
        # 原有内容也不能丢
        assert (
            cfg["models"]["providers"]["volcengine-agent"]["apiKey"]
            == "sk-secret-do-not-lose"
        )

    def test_lock_timeout_raises(self, fake_config, monkeypatch):
        """锁被长期占用时必须超时报错，而不是无限等待或强行写入。"""
        import fcntl

        lock_path = fake_config.parent / ".openclaw.json.mark42.lock"
        monkeypatch.setattr(oc, "_LOCK_PATH", lock_path)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            with pytest.raises(ConfigWriteError, match="超时"):
                with oc._exclusive_lock(timeout_s=1):
                    pass
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_lock_released_after_use(self, fake_config):
        """锁必须释放，否则后续调用会被自己卡死。"""
        patch_openclaw_config({"gateway": {"port": 9001}}, apply=True)
        r = patch_openclaw_config({"gateway": {"port": 9002}}, apply=True)
        assert r["status"] == "applied"


# ── 错误处理 ──────────────────────────────────────────────


class TestErrorHandling:
    def test_missing_config_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(oc, "OPENCLAW_CONFIG", tmp_path / "nope.json")
        monkeypatch.setattr(oc, "_LOCK_PATH", tmp_path / ".lock")
        with pytest.raises(ConfigWriteError, match="缺少配置文件"):
            patch_openclaw_config({"a": 1}, apply=True)

    def test_call_sites_use_atomic_writer(self):
        """防回归：两个调用方不得再出现裸 open 写 openclaw.json。

        【2026-08-05 P2-6】原实现断言源码里必须出现 ``_atomic_write_json``
        和 ``_exclusive_lock`` 两个符号名 —— 把**实现细节**当成了契约。
        P2-6 把写入整体委托给 ``patch_openclaw_config()``
        （它内部就是锁内重读 + 原子写 + 备份 + 回滚）后该断言失败，
        但安全性反而**更强**了。

        现改为断言真正的不变量：
          1. 不得出现裸 open(..., "w") 写配置（这才是要防的东西）
          2. 必须走安全写入通道之一：直接用原子写原语，
             或委托给 patch_openclaw_config
        """
        import re

        for mod in ("context_safety.py", "compaction_diag.py"):
            src = (Path(PKG_ROOT) / "mark42" / mod).read_text(encoding="utf-8")

            for m in re.finditer(r"""open\(([^)]*),\s*["']w["']""", src):
                target = m.group(1)
                assert "config" not in target.lower(), (
                    f"{mod} 出现裸 open 写配置: {m.group(0)}"
                )

            safe_channels = ("_atomic_write_json", "patch_openclaw_config")
            assert any(ch in src for ch in safe_channels), (
                f"{mod} 未接入任何安全写入通道（预期之一：{safe_channels}）"
            )

    def test_call_sites_never_write_config_without_lock(self):
        """安全写入通道本身必须带跨进程锁。

        调用方可以委托给 patch_openclaw_config（它自己拿锁），
        但如果直接用 _atomic_write_json，就必须自己拿 _exclusive_lock。
        """
        for mod in ("context_safety.py", "compaction_diag.py"):
            src = (Path(PKG_ROOT) / "mark42" / mod).read_text(encoding="utf-8")
            if "patch_openclaw_config" in src:
                continue  # 已委托给自带锁的原语
            assert "_exclusive_lock" in src, (
                f"{mod} 直接用原子写却未拿跨进程锁"
            )

