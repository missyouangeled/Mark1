"""CoreRegistry 核心位注册表单元测试。

测试范围:
  - CoreEntry 数据类
  - CoreRegistry 类 list_cores / get_core / probe_all / quarantine / restore
  - probe_core() 对各核心的探测
  - cli_cores_list / cli_cores_probe / cli_cores_quarantine / cli_cores_restore
  - mock HTTP 请求和 systemd
"""

from unittest.mock import MagicMock, patch

# ── CORE_DEFINITIONS 常量测试 ────────────────────────────

class TestCoreDefinitions:
    """测试 CORE_DEFINITIONS 常量。"""

    def test_definitions_is_list(self):
        from mark42.core_registry import CORE_DEFINITIONS

        assert isinstance(CORE_DEFINITIONS, list)
        assert len(CORE_DEFINITIONS) == 8  # 8 个核心位

    def test_each_core_has_required_fields(self):
        from mark42.core_registry import CORE_DEFINITIONS

        for core in CORE_DEFINITIONS:
            assert "core_id" in core
            assert "core_role" in core
            assert "model_name" in core
            assert "runtime" in core
            assert "criticality" in core
            assert "fallback_chain" in core

    def test_core_ids_are_unique(self):
        from mark42.core_registry import CORE_DEFINITIONS

        ids = [c["core_id"] for c in CORE_DEFINITIONS]
        assert len(ids) == len(set(ids))

    def test_criticality_values_are_valid(self):
        from mark42.core_registry import CORE_DEFINITIONS

        valid = {"critical", "degradable", "optional"}
        for core in CORE_DEFINITIONS:
            assert core["criticality"] in valid


# ── CoreEntry 数据类测试 ─────────────────────────────────

class TestCoreEntry:
    """测试 CoreEntry 数据类。"""

    def test_can_create(self):
        from mark42.core_registry import CoreEntry

        entry = CoreEntry(
            core_id="core_1_test",
            core_role="test_role",
            model_name="test-model",
            runtime="api",
            base_url="http://localhost",
            criticality="critical",
            fallback_chain=["fallback1"],
        )
        assert entry.core_id == "core_1_test"
        assert entry.status == "unknown"
        assert entry.total_invocations == 0
        assert entry.total_failures == 0

    def test_to_dict_works(self):
        from mark42.core_registry import CoreEntry

        entry = CoreEntry(
            core_id="core_1_test",
            core_role="test_role",
            model_name="test-model",
            runtime="api",
            base_url="http://localhost",
            criticality="critical",
            status="healthy",
            last_used_at="2024-01-01",
            total_invocations=100,
            total_failures=5,
        )
        d = entry.to_dict()
        assert d["core_id"] == "core_1_test"
        assert d["status"] == "healthy"
        assert d["total_invocations"] == 100


# ── 补丁辅助 ───────────────────────────────────────────

def _patch_module(module_path, tmp_path):
    """补丁 core_registry 模块中的文件路径。"""
    reg_dir = tmp_path / "core-registry"
    reg_dir.mkdir(parents=True, exist_ok=True)

    # 创建补丁
    p1 = patch.object(module_path, "REGISTRY_DIR", reg_dir)
    p2 = patch.object(module_path, "REGISTRY_FILE", reg_dir / "registry.json")
    return p1, p2


# ── CoreRegistry 初始化测试 ──────────────────────────────

class TestCoreRegistryInit:
    """测试 CoreRegistry 初始化。"""

    def test_init_creates_default_cores(self, tmp_path):
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import CoreRegistry
                reg = CoreRegistry()
                cores = reg.list_cores()
                assert len(cores) == 8
                core_ids = [c["core_id"] for c in cores]
                assert "core_1_main_consciousness" in core_ids
                assert "core_2_armor_consciousness" in core_ids
                assert "core_3_memory_vector_engine" in core_ids

    def test_get_core_returns_entry(self, tmp_path):
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import CoreRegistry
                reg = CoreRegistry()
                core = reg.get_core("core_1_main_consciousness")
                assert core is not None
                assert core.core_id == "core_1_main_consciousness"

    def test_get_core_nonexistent_returns_none(self, tmp_path):
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import CoreRegistry
                reg = CoreRegistry()
                core = reg.get_core("core_nonexistent")
                assert core is None


# ── probe_core 测试 ──────────────────────────────────────

class TestProbeCore:
    """测试 probe_core() 函数。"""

    def test_probe_nonexistent_core(self):
        from mark42.core_registry import probe_core

        result = probe_core("core_nonexistent")
        assert result["status"] == "unknown"
        assert "not found" in result["reason"]

    def test_probe_core_1_main_consciousness(self):
        from mark42.core_registry import probe_core

        with patch("mark42.core_registry._probe_http", return_value=True):
            result = probe_core("core_1_main_consciousness")
            assert result["status"] == "healthy"

    def test_probe_core_1_main_consciousness_down(self):
        from mark42.core_registry import probe_core

        with patch("mark42.core_registry._probe_http", return_value=False):
            result = probe_core("core_1_main_consciousness")
            assert result["status"] == "down"

    def test_probe_core_2_armor_consciousness(self):
        """核心 2 不直接探活，默认 healthy。"""
        from mark42.core_registry import probe_core

        result = probe_core("core_2_armor_consciousness")
        assert result["status"] == "healthy"

class TestCoreRegistryProbeAll:
    """测试 CoreRegistry.probe_all() 方法。"""

class TestCoreRegistryQuarantine:
    """测试 CoreRegistry.quarantine() 和 restore() 方法。"""

    def test_quarantine_nonexistent_returns_false(self, tmp_path):
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import CoreRegistry
                reg = CoreRegistry()
                ok = reg.quarantine("core_nonexistent")
                assert ok is False

    def test_restore_nonexistent_returns_false(self, tmp_path):
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import CoreRegistry
                reg = CoreRegistry()
                ok = reg.restore("core_nonexistent")
                assert ok is False


# ── CoreRegistry record_invocation 测试 ─────────────────

class TestCoreRegistryRecordInvocation:
    """测试 CoreRegistry.record_invocation() 方法。"""

    def test_record_invocation_nonexistent_no_crash(self, tmp_path):
        """不存在的核心调用 record_invocation 不崩溃。"""
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import CoreRegistry
                reg = CoreRegistry()
                reg.record_invocation("core_nonexistent", success=True)
                # 不抛异常就是通过


# ── CoreRegistry stats 测试 ─────────────────────────────

class TestCoreRegistrySummary:
    """测试 CoreRegistry.summary() 方法。"""

    def test_summary_returns_total(self, tmp_path):
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import CoreRegistry
                reg = CoreRegistry()
                summary = reg.summary()
                assert summary["total"] == 8

class TestCliCores:
    """测试 cli_cores_* CLI 接口。"""

    def test_cli_cores_list(self, tmp_path):
        reg_dir = tmp_path / "core-registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        with patch("mark42.core_registry.REGISTRY_DIR", reg_dir):
            with patch("mark42.core_registry.REGISTRY_FILE", reg_dir / "registry.json"):
                from mark42.core_registry import cli_cores_list
                result = cli_cores_list()
                assert "cores" in result
                assert "summary" in result
                assert len(result["cores"]) == 8

class TestHelperFunctions:
    """测试 _probe_http / _probe_systemd 等辅助函数。"""

    def test_probe_http_success(self):
        from mark42.core_registry import _probe_http

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response
            result = _probe_http("http://localhost")
            assert result is True

    def test_probe_http_failure(self):
        from mark42.core_registry import _probe_http

        with patch("urllib.request.urlopen", side_effect=Exception("连接失败")):
            result = _probe_http("http://localhost")
            assert result is False

    def test_probe_systemd_active(self):
        from mark42.core_registry import _probe_systemd

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout.strip.return_value = "active"
            mock_run.return_value = mock_result
            result = _probe_systemd("openclaw-test")
            assert result == "active"

    def test_probe_systemd_failed(self):
        from mark42.core_registry import _probe_systemd

        with patch("subprocess.run", side_effect=Exception("systemctl 失败")):
            result = _probe_systemd("openclaw-test")
            assert result == "unknown"


# ── 文件隔离测试 ─────────────────────────────────────────

class TestFileIsolation:
    """测试注册表文件操作隔离。"""
