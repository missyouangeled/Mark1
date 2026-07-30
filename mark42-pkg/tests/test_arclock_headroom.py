"""
Headroom ArcLock 适配器单元测试。

测试范围:
- P1: headroom_compress 实现正确的 check/compress/diagnose 格式
- P2: 通过注册器注册后，get_compress() 返回 Headroom 实现
- P3: isinstance(HeadroomCompress, CompressLock) 通过
- P4: 从 arclock.yaml 加载配置后生效
- P5: HeadroomMemory 同样符合 MemoryLock Protocol
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skip(reason="requires examples module")

# 确保 examples 目录在 PYTHONPATH 中
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES_DIR.parent))


# ── P1: HeadroomCompress 方法返回正确格式 ──

class TestHeadroomCompressFormat:
    """测试 HeadroomCompress 的三个方法返回正确的数据格式。"""

    def test_check_returns_correct_fields(self):
        """check() 必须返回 usagePercent 和 severity 字段。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        compress = HeadroomCompress()
        result = compress.check()

        assert isinstance(result, dict)
        assert "usagePercent" in result
        assert "severity" in result
        assert isinstance(result["usagePercent"], float)
        assert isinstance(result["severity"], str)

    def test_check_usage_percent_range(self):
        """usagePercent 应该在 0-100 之间。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        compress = HeadroomCompress()
        # 多运行几次确保随机值都在合理范围
        for _ in range(10):
            result = compress.check()
            assert 0 <= result["usagePercent"] <= 100, \
                f"usagePercent {result['usagePercent']} 超出范围"

    def test_compress_dry_run_returns_correct_fields(self):
        """compress(dry_run=True) 必须返回 action、before、after 字段。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        compress = HeadroomCompress()
        result = compress.compress(dry_run=True)

        assert isinstance(result, dict)
        assert "action" in result
        assert "before" in result
        assert "after" in result
        assert result["action"] == "dry_run"

    def test_compress_real_run_returns_saved_percent(self):
        """compress(dry_run=False) 应该返回 savedPercent。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        compress = HeadroomCompress()
        result = compress.compress(dry_run=False)

        assert "savedPercent" in result
        assert result["action"] == "compressed"
        assert isinstance(result["savedPercent"], float)
        assert result["savedPercent"] >= 0

    def test_diagnose_returns_provider_info(self):
        """diagnose() 必须返回 provider 和 model 信息。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        compress = HeadroomCompress(api_key="test", model="gpt-4o-mini")
        result = compress.diagnose()

        assert isinstance(result, dict)
        assert "provider" in result
        assert "model" in result
        assert result["provider"] == "headroom"
        assert result["model"] == "gpt-4o-mini"


# ── P2: ArcLock 注册器集成测试 ──

class TestHeadroomRegistration:
    """测试 Headroom 适配器可以通过 ArcLock 注册器正常注册和获取。"""

    def test_register_headroom_compress(self):
        """注册 HeadroomCompress 后，get_compress() 应该返回它。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        from mark42.interfaces import get_compress, register

        # 注册前先清理注册表（通过重新 import 重置，但注册会覆盖）
        headroom = HeadroomCompress(api_key="test-key")
        register("compress", headroom)

        result = get_compress()

        assert result is not None
        assert type(result).__name__ == "HeadroomCompress"
        assert result.api_key == "test-key"

    def test_headroom_compress_called_via_registry(self):
        """通过注册器调用 get_compress().check() 应该正常工作。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        from mark42.interfaces import get_compress, register

        register("compress", HeadroomCompress())
        compress = get_compress()

        result = compress.check()
        assert "usagePercent" in result
        assert result["usagePercent"] > 0

    def test_register_headroom_memory(self):
        """注册 HeadroomMemory 后，get_memory() 应该返回它。"""
        from examples.arclock_headroom.headroom_memory import HeadroomMemory

        from mark42.interfaces import get_memory, register

        headroom = HeadroomMemory(api_key="test-key", index_name="test-index")
        register("memory", headroom)

        result = get_memory()

        assert result is not None
        assert type(result).__name__ == "HeadroomMemory"
        assert result.index_name == "test-index"


# ── P3: Protocol 兼容性测试 ──

class TestHeadroomProtocolCompliance:
    """测试 Headroom 适配器符合 ArcLock Protocol 定义。"""

    def test_headroom_compress_is_compress_lock(self):
        """HeadroomCompress 实例应该是 CompressLock 的实例（鸭子类型）。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        from mark42.interfaces.compress import CompressLock

        headroom = HeadroomCompress()
        assert isinstance(headroom, CompressLock), \
            "HeadroomCompress 应该符合 CompressLock Protocol"

    def test_headroom_memory_is_memory_lock(self):
        """HeadroomMemory 实例应该是 MemoryLock 的实例（鸭子类型）。"""
        from examples.arclock_headroom.headroom_memory import HeadroomMemory

        from mark42.interfaces.memory import MemoryLock

        headroom = HeadroomMemory()
        assert isinstance(headroom, MemoryLock), \
            "HeadroomMemory 应该符合 MemoryLock Protocol"

    def test_third_party_needs_no_mark42_import(self):
        """第三方适配器不需要 import mark42 就能通过 isinstance 检查。

        这是 Protocol vs ABC 的核心优势——零侵入。
        """
        from mark42.interfaces.compress import CompressLock
        from mark42.interfaces.memory import MemoryLock

        # 模拟一个完全不知道 mark42 的第三方实现
        class TotallyIndependentCompress:
            def check(self): return {"usagePercent": 50.0}
            def compress(self, dry_run=True): return {"action": "ok"}
            def diagnose(self): return {}

        class TotallyIndependentMemory:
            def search(self, query, top_k=5): return []
            def index(self, documents): return {"indexed": 0}
            def health(self): return True

        # 不需要继承，不需要 import，只要方法签名对就行
        assert isinstance(TotallyIndependentCompress(), CompressLock)
        assert isinstance(TotallyIndependentMemory(), MemoryLock)


# ── P4: 配置文件加载测试 ──

class TestHeadroomConfigFileLoading:
    """测试从 arclock.yaml 配置文件加载 Headroom 适配器。"""

    def test_configure_from_file_loads_headroom(self):
        """从 YAML 配置文件加载 Headroom 实现应该成功。"""
        from mark42.interfaces import configure_from_file, get_compress, get_memory

        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_path = f.name
            f.write("""
arclock:
  compress:
    module: "examples.arclock_headroom.headroom_compress"
    class: "HeadroomCompress"
    config:
      api_key: "sk-from-config"
      model: "gpt-4o-config"

  memory:
    module: "examples.arclock_headroom.headroom_memory"
    class: "HeadroomMemory"
    config:
      api_key: "sk-memory-from-config"
      index_name: "config-index"
""")

        try:
            # 从配置文件加载
            configure_from_file(config_path)

            # 验证 compress 已替换
            compress = get_compress()
            assert type(compress).__name__ == "HeadroomCompress"
            assert compress.api_key == "sk-from-config"
            assert compress.model == "gpt-4o-config"

            # 验证 memory 已替换
            memory = get_memory()
            assert type(memory).__name__ == "HeadroomMemory"
            assert memory.api_key == "sk-memory-from-config"
            assert memory.index_name == "config-index"

        finally:
            os.unlink(config_path)

    def test_partial_config_uses_default_for_others(self):
        """只配置部分锁扣，其他应该用默认实现。"""
        from mark42.interfaces import configure_from_file, get_compress, get_consciousness

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_path = f.name
            f.write("""
arclock:
  compress:
    module: "examples.arclock_headroom.headroom_compress"
    class: "HeadroomCompress"
    config:
      api_key: "partial-test"
  # consciousness 没配置，应该用默认
""")

        try:
            configure_from_file(config_path)

            # compress 应该是 Headroom
            compress = get_compress()
            assert type(compress).__name__ == "HeadroomCompress"

            # consciousness 应该是默认实现 (BuiltinConsciousness)
            consciousness = get_consciousness()
            assert consciousness is not None
            assert type(consciousness).__name__ == "BuiltinConsciousness"

        finally:
            os.unlink(config_path)


# ── P5: HeadroomMemory 功能测试 ──

class TestHeadroomMemoryFunctionality:
    """测试 HeadroomMemory 的搜索、索引、健康检查功能。"""

    def test_search_returns_list_of_dicts(self):
        """search() 应该返回字典列表，每个字典有 content、score、source。"""
        from examples.arclock_headroom.headroom_memory import HeadroomMemory

        memory = HeadroomMemory()
        results = memory.search("ArcLock", top_k=3)

        assert isinstance(results, list)
        assert len(results) <= 3

        for r in results:
            assert isinstance(r, dict)
            assert "content" in r
            assert "score" in r
            assert "source" in r
            assert isinstance(r["content"], str)
            assert isinstance(r["score"], float)
            assert 0 <= r["score"] <= 1

    def test_search_respects_top_k(self):
        """search() 应该遵守 top_k 参数。"""
        from examples.arclock_headroom.headroom_memory import HeadroomMemory

        memory = HeadroomMemory()

        results_2 = memory.search("test", top_k=2)
        assert len(results_2) <= 2

        results_5 = memory.search("test", top_k=5)
        assert len(results_5) <= 5

    def test_index_returns_indexed_count(self):
        """index() 应该返回 indexed 和 status 字段。"""
        from examples.arclock_headroom.headroom_memory import HeadroomMemory

        memory = HeadroomMemory()
        initial_count = len(memory._mock_documents)

        new_docs = [
            {"content": "文档 1", "metadata": {"source": "test"}},
            {"content": "文档 2", "metadata": {"source": "test"}},
        ]

        result = memory.index(new_docs)

        assert isinstance(result, dict)
        assert "indexed" in result
        assert "status" in result
        assert result["indexed"] == 2
        assert result["status"] == "success"
        assert len(memory._mock_documents) == initial_count + 2

    def test_health_returns_bool(self):
        """health() 应该返回布尔值。"""
        from examples.arclock_headroom.headroom_memory import HeadroomMemory

        memory = HeadroomMemory()
        result = memory.health()

        assert isinstance(result, bool)


# ── P6: 热插拔测试 ──

class TestHeadroomHotSwap:
    """测试运行时热替换实现——这是战甲哲学的核心。"""

    def test_hot_swap_compress_at_runtime(self):
        """运行时可以随时替换 compress 实现，不需要重启。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        from mark42.interfaces import get_compress, register
        from mark42.plugins.builtin_compress import BuiltinCompress

        # 先用默认实现
        register("compress", BuiltinCompress())
        impl1 = get_compress()
        assert type(impl1).__name__ == "BuiltinCompress"

        # 运行时切换到 Headroom
        register("compress", HeadroomCompress())
        impl2 = get_compress()
        assert type(impl2).__name__ == "HeadroomCompress"

        # 再切回来
        register("compress", BuiltinCompress())
        impl3 = get_compress()
        assert type(impl3).__name__ == "BuiltinCompress"

    def test_hot_swap_does_not_break_existing_code(self):
        """热替换后，现有代码不需要任何修改就能继续工作。"""
        from examples.arclock_headroom.headroom_compress import HeadroomCompress

        from mark42.interfaces import get_compress, register
        from mark42.plugins.builtin_compress import BuiltinCompress

        # 这段代码是"业务代码"，它不知道具体实现是什么
        def business_logic():
            compress = get_compress()
            return compress.check()["usagePercent"]

        # 用内置实现运行业务代码
        register("compress", BuiltinCompress())
        result1 = business_logic()
        assert isinstance(result1, (int, float))

        # 运行时切换到 Headroom
        register("compress", HeadroomCompress())

        # 业务代码不需要任何修改，继续工作！
        # ✅ 这就是 ArcLock 的魔力——透明替换
        result2 = business_logic()
        assert isinstance(result2, (int, float))

        # ✅ 这就是 ArcLock 的魔力——透明替换
