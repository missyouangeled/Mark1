"""
Mark42 v3 §3.6.3 R14 · 集群管理器单元测试

测试覆盖:
  1. 集群初始化（目录结构、文件创建）
  2. 健康检查（3 指标）
  3. 重启流程（计数、上限）
  4. 替换流程（重置、审计）
  5. 集群列表
  6. 失败计数
  7. 边界情况
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mark42.cluster_manager import (
    CLUSTER_DEFINITIONS,
    MAX_RESTARTS,
    ClusterConfig,
    ClusterManager,
    HealthCheckResult,
    _check_contract_passed,
    _check_port_accessible,
    _check_process_running,
    _record_action,
    _write_failure_md,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def temp_state_dir():
    """临时状态目录（隔离测试）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with patch("mark42.cluster_manager.STATE_DIR", tmp_path):
            with patch("mark42.cluster_manager.CLUSTERS_DIR", tmp_path / "clusters"):
                with patch("mark42.cluster_manager.ACTIONS_FILE", tmp_path / "armor" / "actions.jsonl"):
                    yield tmp_path


@pytest.fixture
def cm(temp_state_dir):
    """ClusterManager 实例（已初始化）。"""
    manager = ClusterManager()
    manager.init_clusters()
    return manager


# ── 辅助函数测试 ───────────────────────────────────────────────────────


def test_check_process_running_none():
    """测试：无进程名时返回 True。"""
    assert _check_process_running(None) is True


def test_check_process_running_unknown():
    """测试：未知进程名返回 False。"""
    assert _check_process_running("non-existent-process-xyz-123") is False


def test_check_port_accessible_none():
    """测试：无端口时返回 True。"""
    assert _check_port_accessible(None) is True


def test_check_port_accessible_impossible():
    """测试：不可能的端口返回 False。"""
    assert _check_port_accessible(65535) is False  # 几乎不可能有服务


def test_record_action(temp_state_dir):
    """测试：记录操作到 actions.jsonl。"""
    _record_action("test_action", {"foo": "bar"})
    actions_file = temp_state_dir / "armor" / "actions.jsonl"
    assert actions_file.exists()
    lines = actions_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["action"] == "test_action"
    assert data["foo"] == "bar"
    assert "timestamp" in data


# ── ClusterConfig 测试 ────────────────────────────────────────────────


def test_cluster_config_creation():
    """测试：ClusterConfig 数据类创建。"""
    config = ClusterConfig(
        name="cluster-test",
        core_id="core_test",
        criticality="critical",
        components=["comp1", "comp2"],
        port=12345,
        process_name="test-process",
    )
    assert config.name == "cluster-test"
    assert config.core_id == "core_test"
    assert config.criticality == "critical"
    assert len(config.components) == 2
    assert config.port == 12345


def test_cluster_config_to_dict():
    """测试：ClusterConfig 转字典。"""
    config = ClusterConfig(
        name="cluster-test",
        core_id="core_test",
        criticality="critical",
        components=["comp1"],
    )
    d = config.to_dict()
    assert d["name"] == "cluster-test"
    assert d["core_id"] == "core_test"
    assert isinstance(d["components"], list)


# ── HealthCheckResult 测试 ───────────────────────────────────────────


def test_health_check_result_healthy():
    """测试：HealthCheckResult healthy 属性。"""
    result = HealthCheckResult(
        cluster="test",
        process_running=True,
        port_accessible=True,
        contract_passed=True,
        status="healthy",
    )
    assert result.healthy is True


def test_health_check_result_not_healthy():
    """测试：HealthCheckResult 非 healthy 状态。"""
    result = HealthCheckResult(
        cluster="test",
        process_running=True,
        port_accessible=True,
        contract_passed=False,
        status="degraded",
    )
    assert result.healthy is False


# ── ClusterManager 初始化测试 ─────────────────────────────────────────


def test_init_clusters_creates_directories(cm, temp_state_dir):
    """测试：init_clusters 创建所有集群目录。"""
    clusters_dir = temp_state_dir / "clusters"
    for cd in CLUSTER_DEFINITIONS:
        assert (clusters_dir / cd["name"]).exists()


def test_init_clusters_creates_config_files(cm, temp_state_dir):
    """测试：init_clusters 创建 config.json 文件。"""
    clusters_dir = temp_state_dir / "clusters"
    for cd in CLUSTER_DEFINITIONS:
        config_file = clusters_dir / cd["name"] / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["name"] == cd["name"]
        assert data["core_id"] == cd["core_id"]


def test_init_clusters_creates_status_files(cm, temp_state_dir):
    """测试：init_clusters 创建 status.json 文件。"""
    clusters_dir = temp_state_dir / "clusters"
    for cd in CLUSTER_DEFINITIONS:
        status_file = clusters_dir / cd["name"] / "status.json"
        assert status_file.exists()
        data = json.loads(status_file.read_text(encoding="utf-8"))
        assert data["cluster"] == cd["name"]
        assert data["status"] == "healthy"


def test_init_clusters_creates_restart_count(cm, temp_state_dir):
    """测试：init_clusters 创建 restart_count 文件，初始值为 0。"""
    clusters_dir = temp_state_dir / "clusters"
    for cd in CLUSTER_DEFINITIONS:
        count_file = clusters_dir / cd["name"] / "restart_count"
        assert count_file.exists()
        assert count_file.read_text(encoding="utf-8").strip() == "0"


def test_init_clusters_returns_correct_data(cm):
    """测试：init_clusters 返回值正确。"""
    result = cm.init_clusters()
    assert result["ok"] is True
    assert result["count"] == 8
    assert len(result["initialized"]) == 8
    assert "cluster-consciousness" in result["initialized"]


# ── ClusterManager 列表测试 ───────────────────────────────────────────


def test_list_clusters_returns_all(cm):
    """测试：list_clusters 返回所有 8 个集群。"""
    clusters = cm.list_clusters()
    assert len(clusters) == 8


def test_list_clusters_contains_fields(cm):
    """测试：list_clusters 包含必要字段。"""
    clusters = cm.list_clusters()
    for c in clusters:
        assert "name" in c
        assert "core_id" in c
        assert "criticality" in c
        assert "status" in c
        assert "restart_count" in c
        assert "port" in c
        assert "components" in c


def test_list_clusters_initial_status(cm):
    """测试：初始化后集群状态为 healthy。"""
    clusters = cm.list_clusters()
    for c in clusters:
        assert c["status"] == "healthy"
        assert c["restart_count"] == 0


# ── ClusterManager 失败计数测试 ───────────────────────────────────────


def test_get_failure_count_initial(cm):
    """测试：初始失败计数为 0。"""
    count = cm.get_failure_count("cluster-consciousness")
    assert count == 0


def test_get_failure_count_unknown_cluster(cm):
    """测试：未知集群失败计数返回 0。"""
    count = cm.get_failure_count("non-existent-cluster")
    assert count == 0


def test_get_failure_count_after_write(cm, temp_state_dir):
    """测试：写入计数后能正确读取。"""
    cluster_dir = temp_state_dir / "clusters" / "cluster-consciousness"
    (cluster_dir / "restart_count").write_text("3", encoding="utf-8")
    count = cm.get_failure_count("cluster-consciousness")
    assert count == 3


# ── ClusterManager 健康检查测试 ───────────────────────────────────────


def test_health_check_unknown_cluster(cm):
    """测试：未知集群健康检查返回 down。"""
    result = cm.health_check("non-existent-cluster")
    assert result.status == "down"
    assert result.cluster == "non-existent-cluster"
    assert result.process_running is False
    assert result.healthy is False


def test_health_check_updates_status(cm, temp_state_dir):
    """测试：健康检查更新 status.json。"""
    cm.health_check("cluster-text-compress")
    status_file = temp_state_dir / "clusters" / "cluster-text-compress" / "status.json"
    assert status_file.exists()
    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert "last_check" in data
    assert "message" in data


def test_health_check_creates_failure_md_when_degraded(cm, temp_state_dir):
    """测试：降级时创建 FAILURE.md。"""
    with patch("mark42.cluster_manager._check_contract_passed", return_value=(False, "模拟失败")):
        cm.health_check("cluster-text-compress")
        failure_md = temp_state_dir / "clusters" / "cluster-text-compress" / "FAILURE.md"
        assert failure_md.exists()
        content = failure_md.read_text(encoding="utf-8")
        assert "FAILURE" in content
        assert "cluster-text-compress" in content


def test_health_check_removes_failure_md_when_healthy(cm, temp_state_dir):
    """测试：恢复健康时删除 FAILURE.md。"""
    cluster_dir = temp_state_dir / "clusters" / "cluster-text-compress"
    # 先创建 FAILURE.md
    (cluster_dir / "FAILURE.md").write_text("test failure", encoding="utf-8")
    # 健康检查（应该删除）
    with patch("mark42.cluster_manager._check_contract_passed", return_value=(True, "")):
        cm.health_check("cluster-text-compress")
        assert not (cluster_dir / "FAILURE.md").exists()


def test_health_check_records_action(cm, temp_state_dir):
    """测试：健康检查记录到 actions.jsonl。"""
    cm.health_check("cluster-consciousness")
    actions_file = temp_state_dir / "armor" / "actions.jsonl"
    assert actions_file.exists()
    lines = actions_file.read_text(encoding="utf-8").strip().split("\n")
    found = any('"action": "cluster_health_check"' in line for line in lines)
    assert found


def test_health_check_all(cm):
    """测试：health_check_all 检查所有集群。"""
    results = cm.health_check_all()
    assert len(results) == 8
    for r in results:
        assert isinstance(r, HealthCheckResult)


# ── ClusterManager 重启测试 ───────────────────────────────────────────


def test_restart_unknown_cluster(cm):
    """测试：重启未知集群失败。"""
    result = cm.restart("non-existent-cluster")
    assert result["ok"] is False


def test_restart_increments_count(cm):
    """测试：重启增加计数。"""
    initial = cm.get_failure_count("cluster-text-compress")
    result = cm.restart("cluster-text-compress")
    after = cm.get_failure_count("cluster-text-compress")
    assert after == initial + 1
    assert result["restart_count"] == initial + 1


def test_restart_python_module_cluster(cm):
    """测试：Python 模块集群重启成功（无实际进程）。"""
    result = cm.restart("cluster-text-compress")
    assert result["ok"] is True
    assert "纯 Python 模块" in result["message"]


def test_restart_max_limit_should_replace(cm, temp_state_dir):
    """测试：达到最大重启次数后 should_replace 为 True。"""
    cluster_dir = temp_state_dir / "clusters" / "cluster-text-compress"
    # 先设置计数到 MAX_RESTARTS - 1
    (cluster_dir / "restart_count").write_text(str(MAX_RESTARTS - 1), encoding="utf-8")
    # 再重启一次，达到上限
    result = cm.restart("cluster-text-compress")
    assert result["should_replace"] is True
    assert result["restart_count"] == MAX_RESTARTS


def test_restart_over_max_returns_should_replace(cm, temp_state_dir):
    """测试：超过最大重启次数时不重启，返回应该替换。"""
    cluster_dir = temp_state_dir / "clusters" / "cluster-text-compress"
    (cluster_dir / "restart_count").write_text(str(MAX_RESTARTS), encoding="utf-8")
    result = cm.restart("cluster-text-compress")
    assert result["ok"] is False
    assert result["should_replace"] is True
    assert "达到上限" in result["message"]


def test_restart_records_action(cm, temp_state_dir):
    """测试：重启记录到 actions.jsonl。"""
    cm.restart("cluster-text-compress")
    actions_file = temp_state_dir / "armor" / "actions.jsonl"
    lines = actions_file.read_text(encoding="utf-8").strip().split("\n")
    found = any('"action": "cluster_restart"' in line for line in lines)
    assert found


# ── ClusterManager 替换测试 ───────────────────────────────────────────


def test_replace_unknown_cluster(cm):
    """测试：替换未知集群失败。"""
    result = cm.replace("non-existent-cluster")
    assert result["ok"] is False


def test_replace_resets_restart_count(cm, temp_state_dir):
    """测试：替换后重启计数重置为 0。"""
    cluster_dir = temp_state_dir / "clusters" / "cluster-text-compress"
    # 先设置计数
    (cluster_dir / "restart_count").write_text("5", encoding="utf-8")
    # 替换
    result = cm.replace("cluster-text-compress")
    assert result["ok"] is True
    assert result["restart_count_reset"] is True
    # 验证计数已重置
    count = (cluster_dir / "restart_count").read_text(encoding="utf-8").strip()
    assert count == "0"


def test_replace_updates_status(cm, temp_state_dir):
    """测试：替换更新 status.json。"""
    result = cm.replace("cluster-text-compress")
    status_file = temp_state_dir / "clusters" / "cluster-text-compress" / "status.json"
    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert "last_replace" in data
    assert data["replaced_from"] == "backup"


def test_replace_with_git_source(cm, temp_state_dir):
    """测试：从 git 来源替换。"""
    result = cm.replace("cluster-text-compress", source="git")
    assert result["ok"] is True
    status_file = temp_state_dir / "clusters" / "cluster-text-compress" / "status.json"
    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert data["replaced_from"] == "git"


def test_replace_removes_failure_md(cm, temp_state_dir):
    """测试：替换后删除 FAILURE.md。"""
    cluster_dir = temp_state_dir / "clusters" / "cluster-text-compress"
    (cluster_dir / "FAILURE.md").write_text("test failure", encoding="utf-8")
    cm.replace("cluster-text-compress")
    assert not (cluster_dir / "FAILURE.md").exists()


def test_replace_records_action(cm, temp_state_dir):
    """测试：替换记录到 actions.jsonl。"""
    cm.replace("cluster-text-compress")
    actions_file = temp_state_dir / "armor" / "actions.jsonl"
    lines = actions_file.read_text(encoding="utf-8").strip().split("\n")
    found = any('"action": "cluster_replace"' in line for line in lines)
    assert found


# ── ClusterManager 重置计数测试 ───────────────────────────────────────


def test_reset_restart_count(cm, temp_state_dir):
    """测试：重置重启计数。"""
    cluster_dir = temp_state_dir / "clusters" / "cluster-text-compress"
    (cluster_dir / "restart_count").write_text("3", encoding="utf-8")
    result = cm.reset_restart_count("cluster-text-compress")
    assert result["ok"] is True
    count = (cluster_dir / "restart_count").read_text(encoding="utf-8").strip()
    assert count == "0"


def test_reset_restart_count_unknown_cluster(cm, temp_state_dir):
    """测试：重置未知集群失败。"""
    result = cm.reset_restart_count("non-existent-cluster")
    assert result["ok"] is False


# ── 集成测试：重启 -> 失败 -> 替换 完整流程 ────────────────────────────


def test_full_restart_replace_flow(cm, temp_state_dir):
    """测试：完整流程 - 多次重启失败后触发替换。"""
    cluster_name = "cluster-text-compress"
    cluster_dir = temp_state_dir / "clusters" / cluster_name

    # 初始状态
    assert cm.get_failure_count(cluster_name) == 0

    # 第一次重启
    r1 = cm.restart(cluster_name)
    assert r1["ok"] is True
    assert r1["restart_count"] == 1
    assert r1["should_replace"] is False

    # 第二次重启
    r2 = cm.restart(cluster_name)
    assert r2["restart_count"] == 2
    assert r2["should_replace"] is False

    # 第三次重启（达到上限）
    r3 = cm.restart(cluster_name)
    assert r3["restart_count"] == MAX_RESTARTS
    assert r3["should_replace"] is True

    # 第四次重启应该被拒绝
    r4 = cm.restart(cluster_name)
    assert r4["ok"] is False
    assert r4["should_replace"] is True

    # 执行替换
    replace_result = cm.replace(cluster_name)
    assert replace_result["ok"] is True
    assert replace_result["restart_count_reset"] is True

    # 验证计数已重置
    assert cm.get_failure_count(cluster_name) == 0

    # 又可以重启了
    r5 = cm.restart(cluster_name)
    assert r5["ok"] is True
    assert r5["restart_count"] == 1
    assert r5["should_replace"] is False


# ── 边界测试 ──────────────────────────────────────────────────────────


def test_cluster_definitions_have_8_clusters():
    """测试：CLUSTER_DEFINITIONS 有且仅有 8 个集群（R10）。"""
    assert len(CLUSTER_DEFINITIONS) == 8


def test_cluster_definitions_have_correct_naming():
    """测试：集群命名符合规范。"""
    for cd in CLUSTER_DEFINITIONS:
        assert cd["name"].startswith("cluster-")


def test_cluster_definitions_have_criticality():
    """测试：所有集群都有关键性标记。"""
    for cd in CLUSTER_DEFINITIONS:
        assert cd["criticality"] in ["critical", "degradable", "optional"]


def test_cluster_definitions_have_components():
    """测试：所有集群都有组件列表。"""
    for cd in CLUSTER_DEFINITIONS:
        assert isinstance(cd["components"], list)
        assert len(cd["components"]) > 0


def test_max_restarts_is_3():
    """测试：MAX_RESTARTS 是 3（R14 规范）。"""
    assert MAX_RESTARTS == 3
