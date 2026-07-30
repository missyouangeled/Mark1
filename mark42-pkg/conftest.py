"""pytest 配置：确保 mark42 包可导入 + 共享 fixtures。"""
import sys
import os
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 把包目录的父目录加入 sys.path
pkg_parent = Path(__file__).resolve().parent.parent
if str(pkg_parent) not in sys.path:
    sys.path.insert(0, str(pkg_parent))


# ── 环境隔离 fixture（autouse）──

@pytest.fixture(autouse=True)
def _isolate_mark42_state(tmp_path, monkeypatch):
    """每个测试自动隔离：所有状态写入 tmp_path，不污染真实环境。"""
    state_dir = tmp_path / "state" / "openclaw" / "mark42"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("MARK42_STATE_DIR", str(state_dir))
    monkeypatch.setenv("MARK42_SCRATCH", str(tmp_path / "scratch"))
    
    # 强制 reload config
    import mark42.config
    importlib.reload(mark42.config)
    
    yield


# ── 路径 fixtures ──

@pytest.fixture
def state_dir(tmp_path):
    state = tmp_path / "state" / "openclaw" / "mark42"
    state.mkdir(parents=True, exist_ok=True)
    return state

@pytest.fixture
def armor_state(state_dir):
    return state_dir / "armor"

@pytest.fixture
def engine_state(state_dir):
    return state_dir / "engine"

@pytest.fixture
def heavy_state(state_dir):
    path = state_dir / "heavy"
    path.mkdir(parents=True, exist_ok=True)
    return path

@pytest.fixture
def broker_dir(state_dir):
    return state_dir / "broker"

@pytest.fixture
def log_dir(state_dir):
    path = state_dir / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path

@pytest.fixture
def scratch_dir(tmp_path):
    path = tmp_path / "scratch"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── 样本数据 fixtures ──

@pytest.fixture
def sample_long_text():
    return "这是一段很长的文本。" * 200

@pytest.fixture
def sample_repetitive_text():
    return "重复的行。\n" * 100

@pytest.fixture
def sample_code_python():
    return "def hello():\n    print('hello')\n" * 50

@pytest.fixture
def sample_diff():
    return "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@\n-old line\n+new line\n context\n"

@pytest.fixture
def mock_llm_response():
    return {"choices": [{"message": {"content": "压缩后的文本"}}]}

@pytest.fixture
def fake_session_file(tmp_path):
    f = tmp_path / "agent.jsonl"
    f.write_text('{"role":"user","content":"test"}\n', encoding="utf-8")
    return f
