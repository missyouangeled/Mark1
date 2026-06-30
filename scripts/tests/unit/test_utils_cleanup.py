"""utils.py 死 import / 死函数清理 - 验证删了的真不在了。

测试策略:
  - import 检查
  - __all__ 检查（如果有）
  - subprocess / sys 等模块不应该在 utils 出现
"""

import pytest

from mark42_modules import utils


class TestUtilsDeadCodeRemoved:
    """utils.py 死代码清理 - 验证 N 修复。"""

    def test_broker_dirty_not_imported(self):
        """【N】BROKER_DIRTY 死 import 应被删, utils 模块不再导出。"""
        assert not hasattr(utils, "BROKER_DIRTY"), (
            "N 修复: BROKER_DIRTY 死 import 应被删, 但 utils 还能访问"
        )

    def test_max_broker_events_mb_not_imported(self):
        """【N】MAX_BROKER_EVENTS_MB 死 import 应被删 (只在 logs.py 用)。"""
        assert not hasattr(utils, "MAX_BROKER_EVENTS_MB"), (
            "N 修复: MAX_BROKER_EVENTS_MB 死 import 应被删, 但 utils 还能访问"
        )

    def test_run_script_removed(self):
        """【N】_run_script 死函数应被删 (没人调用)。"""
        assert not hasattr(utils, "_run_script"), (
            "N 修复: _run_script 死函数应被删, 但还存在"
        )

    def test_sys_subprocess_not_in_utils_namespace(self):
        """【N】utils 不应 import sys / subprocess (只 _run_script 用过)。"""
        # 检查 utils 模块 globals 里没有 sys / subprocess 命名空间污染
        # (注: pytest 自身可能注入 sys, 所以只检查 utils 主动 import 的)
        src = open(utils.__file__).read()
        # 检查 import 行不含 sys / subprocess
        import_lines = [l for l in src.split("\n")
                       if l.strip().startswith("import ") or l.strip().startswith("from ")]
        for line in import_lines[:15]:  # 只看文件头部的 import
            if "import sys" in line or "import subprocess" in line:
                pytest.fail(f"N 修复: utils.py 仍含 {line.strip()}")

    def test_active_utility_functions_still_work(self):
        """【N】删除死代码后, 活的工具函数仍正常 (回归保护)。"""
        # _now_iso 应仍工作
        ts = utils._now_iso()
        assert isinstance(ts, str)
        assert "T" in ts  # ISO 格式
        # _load_json / _save_json 应仍工作
        import tempfile
        from pathlib import Path
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write('{"a": 1, "b": "x"}')
            f.flush()
            data = utils._load_json(Path(f.name))
            assert data == {"a": 1, "b": "x"}
            Path(f.name).unlink()
        # _append_broker 应仍工作 (核心功能不能因清理而坏)
        from mark42_modules import config
        utils._append_broker("test", "test.event", "label", "ok", "summary", {"k": 1})
        # 验证 broker events.jsonl 增长 (conftest 已隔离 tmp)
        if config.MARK42_BROKER_EVENTS.exists():
            content = config.MARK42_BROKER_EVENTS.read_text()
            assert "test.event" in content
