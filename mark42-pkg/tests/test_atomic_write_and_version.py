"""原子写入 + 版本单一来源 + 配置迁移 的回归测试。

【2026-08-03 新增】对应本次修复的三项：
- P0-1 JSON 非原子写入（进程被 kill 会留下半截文件）
- P0-2 版本号多处硬编码（status 长期显示 2.3.0）
- P1-2 MARK42_* 环境变量文档声明了但代码不读
"""

import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mark42.config import (
    CONFIG_SCHEMA_VERSION,
    _conf_load_json,
    _conf_save_json,
    _migrate_config_if_needed,
    get_version,
)
from mark42.utils import _load_json, _save_json


@pytest.fixture
def workdir(tmp_path):
    """专用干净子目录。

    不能直接用 tmp_path 判断"有无残留临时文件"——conftest 的 autouse 隔离
    fixture 会在 tmp_path 下建 state/data/home 等目录，会把断言污染掉。
    """
    d = tmp_path / "atomic_workdir"
    d.mkdir()
    return d


# ── 原子写入 ──────────────────────────────────────────────


class TestAtomicWrite:
    def test_save_json_roundtrip(self, workdir):
        p = workdir / "state.json"
        data = {"a": 1, "中文": "值"}
        _save_json(p, data)
        assert _load_json(p) == data

    def test_save_json_creates_parent_dirs(self, workdir):
        p = workdir / "deep" / "nested" / "state.json"
        _save_json(p, {"ok": True})
        assert p.exists()
        assert _load_json(p) == {"ok": True}

    def test_no_tmp_file_left_behind(self, workdir):
        p = workdir / "state.json"
        _save_json(p, {"x": 1})
        leftovers = [f.name for f in workdir.iterdir() if f.name != "state.json"]
        assert leftovers == [], f"残留临时文件: {leftovers}"

    def test_overwrite_keeps_file_parseable(self, workdir):
        p = workdir / "state.json"
        _save_json(p, {"round": 1})
        for i in range(2, 20):
            _save_json(p, {"round": i})
            # 每一轮之后文件都必须是完整可解析的
            assert _load_json(p)["round"] == i

    def test_serialization_failure_keeps_original_intact(self, workdir):
        """序列化失败时旧文件必须保持原样（这是原子性的核心价值）。

        注意：_save_json 带 @safe_call，异常会被吸掉并写入 errors.jsonl（既有设计），
        所以这里不断言抛异常，而是断言"旧数据没被截断"——旧实现会在这里把
        文件截成 0 字节或半截 JSON。
        """
        p = workdir / "state.json"
        _save_json(p, {"good": "original"})

        class Unserializable:
            pass

        _save_json(p, {"bad": Unserializable()})

        # 旧内容没被截断
        assert _load_json(p) == {"good": "original"}
        assert p.stat().st_size > 0
        # 也没留下临时文件
        leftovers = [f.name for f in workdir.iterdir() if f.name != "state.json"]
        assert leftovers == []

    def test_conf_save_json_is_atomic_too(self, workdir):
        p = workdir / "config.json"
        _conf_save_json(p, {"v": 1})
        assert _conf_load_json(p) == {"v": 1}
        _conf_save_json(p, {"v": 2})
        assert _conf_load_json(p) == {"v": 2}
        leftovers = [f.name for f in workdir.iterdir() if f.name != "config.json"]
        assert leftovers == []

    def test_conf_save_json_raises_on_bad_data(self, workdir):
        """_conf_save_json 不带 safe_call，序列化失败应该抛出，但不能留下垃圾。"""
        p = workdir / "config.json"
        _conf_save_json(p, {"good": 1})

        class Unserializable:
            pass

        with pytest.raises(TypeError):
            _conf_save_json(p, {"bad": Unserializable()})

        assert _conf_load_json(p) == {"good": 1}
        leftovers = [f.name for f in workdir.iterdir() if f.name != "config.json"]
        assert leftovers == []

    def test_preserves_file_permissions(self, workdir):
        """mkstemp 默认 0600，原子替换后不能悄悄改掉原文件的可见性。"""
        p = workdir / "state.json"
        _save_json(p, {"a": 1})
        os.chmod(p, 0o644)
        _save_json(p, {"a": 2})
        assert (p.stat().st_mode & 0o777) == 0o644

    @pytest.mark.parametrize(
        "kill_stage",
        ["after_open", "after_write", "after_flush", "after_fsync", "before_replace"],
    )
    def test_kill_at_each_write_stage_leaves_valid_file(self, workdir, kill_stage):
        """真实故障注入：在写入流程**各阶段**被 SIGKILL，原文件仍必须完整可解析。

        【2026-08-05 修复 P3-3】原实现在 `_save_json` **调用之前**就
        `os.kill(os.getpid(), SIGKILL)`，子进程压根没进写函数 ——
        只证明了"完全没写时旧文件没变"，是同义反复，毫无验证价值。

        现改为在临时文件写入、flush、fsync、os.replace 前后分别设置故障注入点，
        真正验证原子写的核心承诺：读者要么看到完整旧内容，要么看到完整新内容。
        """
        p = workdir / "state.json"
        _save_json(p, {"generation": "original"})

        pkg_root = str(Path(__file__).resolve().parent.parent)
        script = f'''
import os, signal, sys
from pathlib import Path
sys.path.insert(0, {pkg_root!r})
import mark42.utils as U

STAGE = {kill_stage!r}
_die = lambda: os.kill(os.getpid(), signal.SIGKILL)

# 在原子写的各个真实阶段挂钩，确保进程确实已经进入写流程
real_fdopen = os.fdopen
class Wrapped:
    def __init__(self, f): self._f = f
    def write(self, data):
        n = self._f.write(data)
        if STAGE == "after_write": _die()
        return n
    def flush(self):
        self._f.flush()
        if STAGE == "after_flush": _die()
    def fileno(self): return self._f.fileno()
    def __enter__(self): return self
    def __exit__(self, *a): return self._f.__exit__(*a)

def fake_fdopen(fd, *a, **k):
    f = real_fdopen(fd, *a, **k)
    if STAGE == "after_open": _die()
    return Wrapped(f)

real_fsync = os.fsync
def fake_fsync(fd):
    real_fsync(fd)
    if STAGE == "after_fsync": _die()

real_replace = os.replace
def fake_replace(src, dst):
    if STAGE == "before_replace": _die()
    return real_replace(src, dst)

os.fdopen = fake_fdopen
os.fsync = fake_fsync
os.replace = fake_replace

big = {{"generation": "new", "payload": ["x" * 500] * 4000}}
U._save_json(Path({str(p)!r}), big)
'''
        proc = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, timeout=60
        )
        # 确认真的被 SIGKILL（-9），而不是普通异常退出
        assert proc.returncode == -9, (
            f"阶段 {kill_stage} 未被 SIGKILL 终止，returncode={proc.returncode}，"
            f"stderr={proc.stderr.decode('utf-8', 'replace')[:400]}"
        )

        # 核心断言：原文件必须完整可解析，且仍是旧内容
        loaded = _load_json(p)
        assert loaded == {"generation": "original"}, (
            f"阶段 {kill_stage} 后原文件被破坏或被部分写入：{str(loaded)[:200]}"
        )

    def test_kill_after_replace_sees_new_content(self, workdir):
        """os.replace 完成后被杀，必须看到**完整新内容**（原子性的另一半）。"""
        p = workdir / "state.json"
        _save_json(p, {"generation": "original"})

        pkg_root = str(Path(__file__).resolve().parent.parent)
        script = f'''
import os, signal, sys
from pathlib import Path
sys.path.insert(0, {pkg_root!r})
import mark42.utils as U

real_replace = os.replace
def fake_replace(src, dst):
    real_replace(src, dst)
    os.kill(os.getpid(), signal.SIGKILL)   # 替换已完成后立刻死
os.replace = fake_replace

U._save_json(Path({str(p)!r}), {{"generation": "new"}})
'''
        proc = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, timeout=60
        )
        assert proc.returncode == -9

        loaded = _load_json(p)
        assert loaded == {"generation": "new"}, (
            "replace 已完成却没看到新内容，原子替换未生效"
        )

    def test_no_temp_files_left_after_crash(self, workdir):
        """崩溃后不得残留大量临时文件（会撑爆状态目录）。"""
        p = workdir / "state.json"
        _save_json(p, {"generation": "original"})

        pkg_root = str(Path(__file__).resolve().parent.parent)
        script = f'''
import os, signal, sys
from pathlib import Path
sys.path.insert(0, {pkg_root!r})
import mark42.utils as U
real_replace = os.replace
def fake_replace(src, dst):
    os.kill(os.getpid(), signal.SIGKILL)
os.replace = fake_replace
U._save_json(Path({str(p)!r}), {{"generation": "new"}})
'''
        subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=60)

        # SIGKILL 无法执行 finally，残留 1 个临时文件属预期；
        # 但原文件必须完好，且不得出现被截断的目标文件
        assert _load_json(p) == {"generation": "original"}
        leftovers = list(workdir.glob(".state.json.*.tmp"))
        assert len(leftovers) <= 1, f"残留过多临时文件: {leftovers}"


def _concurrent_writer(args):
    path, worker_id = args
    from mark42.utils import _save_json

    for i in range(15):
        _save_json(Path(path), {"worker": worker_id, "i": i, "pad": "y" * 2000})
    return worker_id


class TestConcurrentWrite:
    def test_multiprocess_writes_never_produce_half_file(self, workdir):
        """多进程并发写同一文件：可能互相覆盖（那是锁的职责），但绝不能出现坏 JSON。"""
        p = workdir / "shared.json"
        _save_json(p, {"init": True})

        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(4) as pool:
            pool.map(_concurrent_writer, [(str(p), w) for w in range(4)])

        raw = p.read_text(encoding="utf-8")
        parsed = json.loads(raw)  # 不抛异常即证明没有半截文件
        assert "worker" in parsed or "init" in parsed

        leftovers = [f.name for f in workdir.iterdir() if f.name != "shared.json"]
        assert leftovers == [], f"残留临时文件: {leftovers}"


# ── 版本单一来源 ──────────────────────────────────────────


class TestVersionSingleSource:
    def test_get_version_matches_dunder_version(self):
        import mark42

        assert get_version() == mark42.__version__

    def test_get_version_is_not_stale_2_3_0(self):
        """回归：status 面板曾长期显示初始化时写死的 2.3.0。"""
        assert get_version() != "2.3.0"

    def test_get_version_returns_nonempty_string(self):
        v = get_version()
        assert isinstance(v, str)
        assert v
        assert v != "unknown"

    def test_cli_version_flag_matches_get_version(self):
        pkg_root = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; from mark42.cli import main; sys.argv=['mark42','--version']; main()"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=pkg_root,
        )
        combined = proc.stdout + proc.stderr
        assert get_version() in combined, combined

    def test_no_hardcoded_version_in_cli_and_config(self):
        """防回归：禁止再把版本号写死在 CLI --version 或 mark42_init() 里。"""
        import mark42.cli as cli_mod
        import mark42.config as config_mod

        for mod in (cli_mod, config_mod):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            assert 'version="Mark42 v2' not in src
            assert '"version": "2.3.0"' not in src


# ── 配置迁移 ──────────────────────────────────────────────


class TestConfigMigration:
    def test_legacy_version_field_is_migrated(self, tmp_path, monkeypatch):
        cfg_path = tmp_path / "config.json"
        legacy = {
            "version": "2.3.0",
            "initializedAt": "2026-01-01T00:00:00+08:00",
            "thresholds": {"warn": 70, "alert": 85, "crit": 95},
        }
        cfg_path.write_text(json.dumps(legacy), encoding="utf-8")
        monkeypatch.setattr("mark42.config.CONFIG_PATH", cfg_path)

        migrated = _migrate_config_if_needed(_conf_load_json(cfg_path))

        assert migrated["configSchemaVersion"] == CONFIG_SCHEMA_VERSION
        assert "version" not in migrated
        assert migrated["legacyVersion"] == "2.3.0"

    def test_migration_preserves_user_settings(self, tmp_path, monkeypatch):
        """迁移只动 schema 字段，不许碰用户自定义的阈值和模型配置。"""
        cfg_path = tmp_path / "config.json"
        legacy = {
            "version": "2.3.0",
            "thresholds": {"warn": 55, "alert": 66, "crit": 77},
            "models": {"llmAnalyze": {"model": "my-custom-model"}},
            "daemon": {"scanInterval": 999},
        }
        cfg_path.write_text(json.dumps(legacy), encoding="utf-8")
        monkeypatch.setattr("mark42.config.CONFIG_PATH", cfg_path)

        migrated = _migrate_config_if_needed(_conf_load_json(cfg_path))

        assert migrated["thresholds"] == {"warn": 55, "alert": 66, "crit": 77}
        assert migrated["models"]["llmAnalyze"]["model"] == "my-custom-model"
        assert migrated["daemon"]["scanInterval"] == 999

    def test_migration_writes_backup(self, tmp_path, monkeypatch):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"version": "2.3.0"}), encoding="utf-8")
        monkeypatch.setattr("mark42.config.CONFIG_PATH", cfg_path)

        _migrate_config_if_needed(_conf_load_json(cfg_path))

        backups = list(tmp_path.glob("config.json.pre-schema*.bak"))
        assert len(backups) == 1
        assert json.loads(backups[0].read_text(encoding="utf-8"))["version"] == "2.3.0"

    def test_already_migrated_config_untouched(self, tmp_path, monkeypatch):
        cfg_path = tmp_path / "config.json"
        current = {"configSchemaVersion": CONFIG_SCHEMA_VERSION, "thresholds": {"warn": 70}}
        cfg_path.write_text(json.dumps(current), encoding="utf-8")
        monkeypatch.setattr("mark42.config.CONFIG_PATH", cfg_path)

        result = _migrate_config_if_needed(_conf_load_json(cfg_path))

        assert result == current
        assert list(tmp_path.glob("*.bak")) == []

    def test_empty_config_is_noop(self):
        assert _migrate_config_if_needed({}) == {}


# ── 环境变量覆盖 ──────────────────────────────────────────


class TestEnvOverrides:
    """P1-2：文档和 systemd unit 都声明了这些变量，之前 config.py 完全不读。"""

    def _reimport_config_with_env(self, env: dict):
        code = (
            "import importlib, mark42.config as c; importlib.reload(c); "
            "print(c.WORKSPACE); print(c.MARK42_STATE); "
            "print(c.LOG_DIR); print(c.MAX_DAEMON_LOG_LINES)"
        )
        merged = {**os.environ, **env}
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=merged,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout.strip().splitlines()

    def test_mark42_workspace_env_is_honored(self, tmp_path):
        out = self._reimport_config_with_env({"MARK42_WORKSPACE": str(tmp_path)})
        assert out[0] == str(tmp_path)

    def test_mark42_state_dir_env_is_honored(self, tmp_path):
        target = tmp_path / "state"
        out = self._reimport_config_with_env({"MARK42_STATE_DIR": str(target)})
        assert out[1] == str(target)

    def test_mark42_log_dir_env_is_honored(self, tmp_path):
        target = tmp_path / "logs"
        out = self._reimport_config_with_env({"MARK42_LOG_DIR": str(target)})
        assert out[2] == str(target)

    def test_max_daemon_log_lines_env_is_honored(self):
        out = self._reimport_config_with_env({"MARK42_MAX_DAEMON_LOG_LINES": "777"})
        assert out[3] == "777"

    def test_defaults_still_apply_without_env(self):
        out = self._reimport_config_with_env({})
        assert out[3] == "10000"
