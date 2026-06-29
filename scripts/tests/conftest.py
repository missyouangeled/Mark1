"""Mark42 共享测试 fixtures - 隔离文件系统、配置环境。

设计要点：
  1. autouse=True：每个测试自动应用环境隔离，零样板
  2. monkeypatch + tmp_path：所有状态写入临时目录，永不污染真生产
  3. 强制 reload mark42_modules.config：因为 XDG_STATE 在 import 时被读取
  4. 强制覆盖 DATA_ROOT：config.py 检测 /mnt/data 存在后会把 DATA_ROOT 指到那里，
     测试也要把它重定向到 tmp_path

使用：
  pytest scripts/tests/                # 跑所有
  pytest scripts/tests/unit/           # 只跑单测
  pytest scripts/tests/integration/    # 只跑集成
  pytest scripts/tests/smoke/ --runslow  # 烟测（默认跳过）
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

# 让 import 能找到 mark42_modules
TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
WORKSPACE_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))


# ── 1. 环境隔离（autouse）：所有测试都用 tmp_path 模拟状态目录 ──

@pytest.fixture(autouse=True)
def _isolate_mark42_state(monkeypatch, tmp_path):
    """自动应用：每个测试都用临时 XDG_STATE_HOME + DATA_ROOT，零污染。

    关键 trick：
      - 改 XDG_STATE_HOME → MARK42_STATE 等路径派生全部跟着变
      - monkeypatch.setattr(DATA_ROOT) → 覆盖 config.py 里的 /mnt/data 检测结果
      - reload config → 重新计算所有派生常量
      - ⚠️ reload 顺序很重要：必须先 reload 底层（utils），再 reload 上层（armor/engine/heavy）
        否则上层拿到的还是旧引用（Python 不会自动修复跨模块引用）

    顺序设计：
      1. config        (底层路径)
      2. utils         (底层 helper)
      3. compression 子模块（依赖 utils）
      4. armor         (依赖 utils + compression)
      5. engine / heavy / logs  (依赖 armor / utils)
    """
    import warnings

    # 1. 准备假目录
    fake_state = tmp_path / "state"
    fake_data = tmp_path / "data"
    fake_state.mkdir()
    fake_data.mkdir()
    (fake_state / "openclaw" / "mark42").mkdir(parents=True)
    (fake_data / "openclaw" / "mark42" / "logs").mkdir(parents=True)

    # 2. 改环境变量
    monkeypatch.setenv("XDG_STATE_HOME", str(fake_state))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    # 3. 强制 reload config（XDG_STATE 是 module-level 常量，必须 reload 才生效）
    import mark42_modules.config as _cfg
    importlib.reload(_cfg)

    # 4. 覆盖 DATA_ROOT（/mnt/data 检测逻辑只在 import 时跑一次）
    monkeypatch.setattr(_cfg, "DATA_ROOT", fake_data / "openclaw" / "mark42")
    monkeypatch.setattr(_cfg, "LOG_DIR", fake_data / "openclaw" / "mark42" / "logs")

    # 5. ⚠️ 关键 reload 顺序：按依赖图从底层到顶层
    reload_order = [
        # 底层：只依赖 stdlib + config
        "mark42_modules.utils",
        "mark42_modules.session_fence_safe",
        # 压缩子模块（依赖 utils）
        "mark42_modules.smart_crusher",
        "mark42_modules.compression_algorithms",
        "mark42_modules.code_compressor",
        "mark42_modules.diff_compressor",
        "mark42_modules.text_compressor",
        "mark42_modules.llm_text_compressor",
        "mark42_modules.pii_redactor",
        "mark42_modules.log_deduplicator",
        "mark42_modules.algo_scheduler",
        # 中层：依赖 utils + 压缩子模块
        "mark42_modules.armor",
        # 顶层：依赖 armor + utils
        "mark42_modules.engine",
        "mark42_modules.heavy",
        "mark42_modules.logs",
        "mark42_modules.cli",
    ]
    for mod_name in reload_order:
        if mod_name in sys.modules:
            try:
                importlib.reload(sys.modules[mod_name])
            except Exception as e:
                # ⚠️ reload 失败要可见，不能静默吞掉
                warnings.warn(
                    f"[mark42-test] reload {mod_name} 失败: {type(e).__name__}: {e}",
                    stacklevel=2,
                )

    yield fake_state
    # pytest 自动清理 tmp_path


# ── 2. 路径 fixtures（让测试代码少写几行）──

@pytest.fixture
def state_dir(_isolate_mark42_state):
    """返回状态目录根：<tmp>/state/openclaw/mark42"""
    from mark42_modules import config
    return config.MARK42_STATE


@pytest.fixture
def armor_state(state_dir):
    return state_dir / "armor"


@pytest.fixture
def engine_state(state_dir):
    return state_dir / "engine"


@pytest.fixture
def heavy_state(state_dir):
    return state_dir / "heavy"


@pytest.fixture
def broker_dir(state_dir):
    """broker 事件目录：<tmp>/state/openclaw/broker"""
    from mark42_modules import config
    return config.BROKER_DIR


@pytest.fixture
def session_messages():
    """为 armor_compress 提供标准的 10 条 session 消息。

    armor_compress 会在 _read_session_tail 返回空列表时跳过 LLM 调用。
    多数压缩路径的测试需要让 _read_session_tail 返回非空。
    """
    return [{"role": "user", "content": f"msg {i}"} for i in range(10)]


@pytest.fixture
def log_dir(_isolate_mark42_state):
    """数据盘日志目录：<tmp>/data/openclaw/mark42/logs"""
    from mark42_modules import config
    return config.LOG_DIR


# ── 3. CLI runner（集成测试用）──

@pytest.fixture
def cli_runner():
    """封装 mark42.py CLI 调用，返回 subprocess.run 的 CompletedProcess-like 对象。

    用法：
        def test_xxx(cli_runner):
            r = cli_runner("status")
            assert r.returncode == 0
            assert "Mark42" in r.stdout
    """
    mark42 = SCRIPTS_DIR / "mark42.py"

    def run(*args, timeout=30, check=False, env_extra=None):
        full_env = os.environ.copy()
        if env_extra:
            full_env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(mark42), *args],
            capture_output=True,
            text=True,
            env=full_env,
            timeout=timeout,
            check=check,
        )

    return run


# ── 4. 标准测试数据 ──

@pytest.fixture
def sample_messages():
    """标准测试输入：模拟一段对话（80 条）"""
    msgs = []
    for i in range(20):
        msgs.append({"role": "user", "content": f"问题 {i}"})
        msgs.append({"role": "assistant", "content": f"回答 {i}" * 5})
        msgs.append({"role": "user", "content": "追问"})
        msgs.append({"role": "assistant", "content": "补充说明。" * 3})
    return msgs


@pytest.fixture
def fake_session_file(tmp_path):
    """模拟一个 OpenClaw session jsonl 文件"""
    session = tmp_path / "sessions" / "agent-main-main.jsonl"
    session.parent.mkdir(parents=True, exist_ok=True)
    with open(session, "w") as f:
        for i in range(50):
            f.write(
                f'{{"role":"user","content":"msg {i}","ts":"2026-06-29T08:0{i//10}:0{i%10}:00"}}\n'
            )
    return session


# ── 5. Marker 注册 ──

def pytest_addoption(parser):
    """添加 --runslow 选项"""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="跑标记为 slow 的烟测（默认跳过）",
    )


def pytest_configure(config):
    """注册自定义 marker（不注册会触发 strict-markers 警告）"""
    config.addinivalue_line(
        "markers", "slow: 烟测，需要 --runslow 才跑（默认跳过）"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试，跨模块 + subprocess"
    )


def pytest_collection_modifyitems(config, items):
    """默认跳过 @pytest.mark.slow 测试，除非传 --runslow"""
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="需要 --runslow 才跑（默认跳过）")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)