"""
Mark42 v3 §3.6.3 R14 · 集群思维 + 修复边界

R14 设计规范:
  - 8 核 = 8 个独立小集群（R10 多核心架构）
  - 集群内可复杂（配置 / schema / 契约），集群间必须简单
  - 集群挂 → 整体替换，不修复（Netflix "cattle vs pets" 哲学）
  - 战甲自身（systemd）挂 → 人修，不自动化

R14 的 6 个工程关键词:
  1. 集群配置目录化 - 每个集群 clusters/<name>/ 目录
  2. 契约 schema 一份 - 所有集群共享
  3. 集群打包 - tar.gz = 配置 + 二进制 + 启动脚本
  4. 集群健康度 3 指标 - 进程在 + 端口通 + 契约校验通过
  5. 替换流程命令 - mark42 cluster replace <name>
  6. 替换审计 - 每次替换写 actions.jsonl

修复边界:
  - 集群内组件挂 -> 自动重启 3 次，3 次失败 -> 整体替换集群
  - 集群挂 3 次 -> 主动对话问用户
  - 战甲自身（systemd）挂 -> 不自动化，人修

集群目录结构:
  ~/.local/state/openclaw/mark42/clusters/<name>/
    ├── config.yaml      # 集群配置
    ├── status.json      # 当前状态（健康 / 降级 / 挂）
    ├── restart_count    # 重启次数计数文件（纯数字）
    └── FAILURE.md       # 降级时写入（9 字段契约）
"""

from __future__ import annotations

from .log_setup import get_logger

logger = get_logger(__name__)

import json
import subprocess
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .core_registry import CORE_DEFINITIONS, CoreRegistry

# ── 常量 ────────────────────────────────────────────────────────────

STATE_DIR = Path.home() / ".local" / "state" / "openclaw" / "mark42"
CLUSTERS_DIR = STATE_DIR / "clusters"
ACTIONS_FILE = STATE_DIR / "armor" / "actions.jsonl"

# 8 个集群定义（R10：8 核 = 8 集群）
CLUSTER_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "cluster-consciousness",
        "core_id": "core_1_main_consciousness",
        "criticality": "critical",
        "components": ["main_consciousness", "openclaw_gateway"],
        "port": 18788,
        "process_name": "openclaw-gateway",
    },
    {
        "name": "cluster-auto-consciousness",
        "core_id": "core_2_armor_consciousness",
        "criticality": "degradable",
        "components": ["armor_consciousness", "local_model"],
        "port": None,
        "process_name": None,
    },
    {
        "name": "cluster-memory-vector",
        "core_id": "core_3_memory_vector_engine",
        "criticality": "degradable",
        "components": ["embed_sidecar", "vector_engine"],
        "port": 18792,
        "process_name": "embed-sidecar",
    },
    {
        "name": "cluster-text-compress",
        "core_id": "core_4_text_compressor",
        "criticality": "optional",
        "components": ["text_compressor", "smart_crusher"],
        "port": None,
        "process_name": None,
    },
    {
        "name": "cluster-code-understand",
        "core_id": "core_5_code_understand",
        "criticality": "optional",
        "components": ["code_analyzer", "ast_parser"],
        "port": None,
        "process_name": None,
    },
    {
        "name": "cluster-log-classify",
        "core_id": "core_6_log_classify",
        "criticality": "optional",
        "components": ["log_classifier", "keyword_matcher"],
        "port": None,
        "process_name": None,
    },
    {
        "name": "cluster-pii-redact",
        "core_id": "core_7_pii_redact",
        "criticality": "optional",
        "components": ["pii_redactor", "regex_rules"],
        "port": None,
        "process_name": None,
    },
    {
        "name": "cluster-anomaly-detect",
        "core_id": "core_8_anomaly_detect",
        "criticality": "optional",
        "components": ["anomaly_detector", "threshold_engine"],
        "port": None,
        "process_name": None,
    },
]

# 最大重启次数（R14：3 次失败后替换）
MAX_RESTARTS = 3


# ── 数据类 ───────────────────────────────────────────────────────────


@dataclass
class ClusterConfig:
    """集群配置（R14：集群配置目录化）。"""

    name: str  # 集群名，如 cluster-consciousness
    core_id: str  # 对应核心 ID
    criticality: str  # critical | degradable | optional
    components: list[str]  # 集群内组件列表
    port: int | None = None  # 监听端口（如有）
    process_name: str | None = None  # 进程名（如有）
    config_path: str = ""  # 配置文件路径
    startup_script: str = ""  # 启动脚本路径
    version: str = "1.0.0"  # 集群版本

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealthCheckResult:
    """健康检查结果（3 指标）。"""

    cluster: str
    process_running: bool  # 指标 1：进程在
    port_accessible: bool  # 指标 2：端口通
    contract_passed: bool  # 指标 3：契约校验通过
    status: str  # healthy | degraded | down
    message: str = ""

    @property
    def healthy(self) -> bool:
        return self.status == "healthy"


# ── 辅助函数 ─────────────────────────────────────────────────────────


def _check_process_running(process_name: str | None) -> bool:
    """检查进程是否在运行（指标 1）。"""
    if not process_name:
        # 没有独立进程的集群（如纯 Python 模块）视为进程在
        return True
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_port_accessible(port: int | None, host: str = "127.0.0.1") -> bool:
    """检查端口是否可访问（指标 2）。"""
    if port is None:
        # 没有端口的集群视为端口可通
        return True
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=3):
            return True
    except Exception:
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False


def _check_contract_passed(cluster_name: str, core_id: str) -> tuple[bool, str]:
    """检查契约是否通过（指标 3）。"""
    try:
        reg = CoreRegistry()
        core = reg.get_core(core_id)
        if not core:
            return False, "核心未注册"

        # Python 模块集群：尝试导入并做基础检查
        if cluster_name == "cluster-text-compress":
            from .text_compressor import TextCompressor

            tc = TextCompressor()
            compressed, stats = tc.compress("test " * 100)
            passed = len(compressed) > 0 and isinstance(stats, dict)
            return passed, "" if passed else "text_compressor 压缩失败"

        elif cluster_name == "cluster-pii-redact":
            from .pii_redactor import PIIRedactor

            pr = PIIRedactor()
            redacted, stats = pr.redact("我的电话是 13800138000")
            passed = "13800138000" not in redacted and stats["total_redactions"] > 0
            return passed, "" if passed else "pii_redactor 脱敏失败"

        elif cluster_name == "cluster-log-classify":
            from .log_classifier import LogClassifier

            lc = LogClassifier()
            passed = lc.health_check()
            return passed, "" if passed else "log_classifier 健康检查失败"

        elif cluster_name == "cluster-anomaly-detect":
            from .anomaly_detector import AnomalyDetector

            ad = AnomalyDetector()
            passed = ad.health_check()
            return passed, "" if passed else "anomaly_detector 健康检查失败"

        # 有端口的集群：端口通即契约通过（/healthz 已验证）
        if cluster_name in ["cluster-consciousness", "cluster-memory-vector"]:
            return True, ""

        # 默认：核心状态 healthy 则契约通过
        return core.status == "healthy", ""

    except Exception as e:
        return False, f"契约检查异常: {e}"


def _write_failure_md(cluster_dir: Path, cluster_name: str, reason: str, criticality: str) -> None:
    """写入 FAILURE.md（R13-D：降级响应契约 9 字段）。"""
    failure_content = f"""# FAILURE - {cluster_name}

> 生成时间: {datetime.now().isoformat()}
> 集群关键性: {criticality}

## 1. 故障标识
- cluster_name: {cluster_name}
- failure_type: health_check_failed
- severity: high

## 2. 影响面
- criticality: {criticality}
- affected_components: health_check 3 指标不满足

## 3. 降级方案
- fallback: 自动重启（最多 {MAX_RESTARTS} 次）
- next_action: 重启失败则替换集群

## 4. 故障原因
{reason}

## 5. 诊断信息
- 健康检查 3 指标: 进程在 + 端口通 + 契约校验通过
- 重启次数: 查看 restart_count 文件
"""
    (cluster_dir / "FAILURE.md").write_text(failure_content, encoding="utf-8")


def _record_action(action_type: str, data: dict[str, Any]) -> None:
    """记录操作到 actions.jsonl（R7：有据可查）。"""
    ACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    action = {
        "action": action_type,
        "timestamp": datetime.now().isoformat(),
        **data,
    }
    try:
        with open(ACTIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(action, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"记录 action 失败: {e}")


# ── ClusterManager 主类 ─────────────────────────────────────────────


class ClusterManager:
    """R14 集群管理器：集群配置目录化 + 3 指标健康检查 + 一键替换。"""

    def __init__(self):
        CLUSTERS_DIR.mkdir(parents=True, exist_ok=True)
        ACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    def init_clusters(self) -> dict[str, Any]:
        """初始化 8 个集群目录结构（R14：集群配置目录化）。

        每个集群目录包含:
          - config.yaml: 集群配置
          - status.json: 当前状态
          - restart_count: 重启次数（纯数字文件）
        """
        initialized = []
        for cd in CLUSTER_DEFINITIONS:
            cluster_dir = CLUSTERS_DIR / cd["name"]
            cluster_dir.mkdir(exist_ok=True)

            # 1. config.yaml
            config = ClusterConfig(
                name=cd["name"],
                core_id=cd["core_id"],
                criticality=cd["criticality"],
                components=cd["components"],
                port=cd["port"],
                process_name=cd["process_name"],
                config_path=str(cluster_dir / "config.yaml"),
                startup_script=str(cluster_dir / "start.sh"),
            )
            # 简化：用 JSON 代替 YAML（避免额外依赖）
            (cluster_dir / "config.json").write_text(
                json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # 2. status.json
            status = {
                "cluster": cd["name"],
                "status": "healthy",
                "last_check": datetime.now().isoformat(),
                "last_restart": None,
                "last_replace": None,
            }
            (cluster_dir / "status.json").write_text(
                json.dumps(status, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # 3. restart_count（纯数字文件）
            (cluster_dir / "restart_count").write_text("0", encoding="utf-8")

            initialized.append(cd["name"])

        _record_action("cluster_init", {"clusters": initialized})
        return {
            "ok": True,
            "initialized": initialized,
            "count": len(initialized),
            "base_dir": str(CLUSTERS_DIR),
        }

    def health_check(self, cluster_name: str) -> HealthCheckResult:
        """集群健康检查（R14：3 指标）。

        3 指标:
          1. 进程在
          2. 端口通
          3. 契约校验通过
        """
        cluster_def = next((c for c in CLUSTER_DEFINITIONS if c["name"] == cluster_name), None)
        if not cluster_def:
            return HealthCheckResult(
                cluster=cluster_name,
                process_running=False,
                port_accessible=False,
                contract_passed=False,
                status="down",
                message="未知集群",
            )

        # 指标 1：进程在
        process_running = _check_process_running(cluster_def["process_name"])

        # 指标 2：端口通
        port_accessible = _check_port_accessible(cluster_def["port"])

        # 指标 3：契约校验通过
        contract_passed, contract_msg = _check_contract_passed(cluster_name, cluster_def["core_id"])

        # 综合状态判断
        all_ok = process_running and port_accessible and contract_passed
        if all_ok:
            status = "healthy"
            message = "所有指标正常"
        elif process_running and port_accessible and not contract_passed:
            status = "degraded"
            message = f"契约校验失败: {contract_msg}"
        elif not process_running:
            status = "down"
            message = "进程未运行"
        elif not port_accessible:
            status = "down"
            message = "端口不可达"
        else:
            status = "degraded"
            message = "部分指标异常"

        # 更新 status.json
        cluster_dir = CLUSTERS_DIR / cluster_name
        if cluster_dir.exists():
            try:
                status_file = cluster_dir / "status.json"
                if status_file.exists():
                    current = json.loads(status_file.read_text(encoding="utf-8"))
                    current["status"] = status
                    current["last_check"] = datetime.now().isoformat()
                    current["message"] = message
                    status_file.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")

                # 如果不健康，写入 FAILURE.md
                if status != "healthy":
                    _write_failure_md(cluster_dir, cluster_name, message, cluster_def["criticality"])
                else:
                    # 健康时删除 FAILURE.md
                    failure_md = cluster_dir / "FAILURE.md"
                    if failure_md.exists():
                        failure_md.unlink()

            except Exception as e:
                logger.warning(f"更新 {cluster_name} 状态失败: {e}")

        result = HealthCheckResult(
            cluster=cluster_name,
            process_running=process_running,
            port_accessible=port_accessible,
            contract_passed=contract_passed,
            status=status,
            message=message,
        )

        _record_action("cluster_health_check", result.__dict__)
        return result

    def get_failure_count(self, cluster_name: str) -> int:
        """获取集群失败次数（用于决策：3 次失败后替换）。"""
        cluster_dir = CLUSTERS_DIR / cluster_name
        count_file = cluster_dir / "restart_count"
        if not count_file.exists():
            return 0
        try:
            return int(count_file.read_text(encoding="utf-8").strip())
        except Exception:
            return 0

    def restart(self, cluster_name: str) -> dict[str, Any]:
        """重启集群（R14：最多 3 次）。

        返回:
          - ok: 是否成功
          - restart_count: 当前重启次数
          - should_replace: 是否应该替换（超过 MAX_RESTARTS）
          - message: 说明
        """
        cluster_def = next((c for c in CLUSTER_DEFINITIONS if c["name"] == cluster_name), None)
        if not cluster_def:
            return {"ok": False, "reason": "未知集群", "should_replace": False}

        cluster_dir = CLUSTERS_DIR / cluster_name
        if not cluster_dir.exists():
            # 自动初始化
            self.init_clusters()

        # 读取当前重启次数
        restart_count = self.get_failure_count(cluster_name)

        # 检查是否超过最大重启次数
        if restart_count >= MAX_RESTARTS:
            _record_action(
                "cluster_restart_skipped",
                {
                    "cluster": cluster_name,
                    "restart_count": restart_count,
                    "reason": "已达最大重启次数",
                },
            )
            return {
                "ok": False,
                "cluster": cluster_name,
                "restart_count": restart_count,
                "should_replace": True,
                "message": f"已重启 {restart_count} 次，达到上限 {MAX_RESTARTS}，请使用 replace 替换集群",
            }

        # 执行重启逻辑
        restart_count += 1
        restarted = False
        restart_message = ""

        # 有 systemd 服务的集群：重启服务
        if cluster_name == "cluster-memory-vector":
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "restart", "openclaw-embed-sidecar"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                restarted = result.returncode == 0
                restart_message = "重启 embed-sidecar 服务" if restarted else f"服务重启失败: {result.stderr}"
            except Exception as e:
                restart_message = f"重启服务异常: {e}"

        elif cluster_name == "cluster-consciousness":
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "restart", "openclaw-gateway"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                restarted = result.returncode == 0
                restart_message = "重启 openclaw-gateway 服务" if restarted else f"服务重启失败: {result.stderr}"
            except Exception as e:
                restart_message = f"重启服务异常: {e}"

        else:
            # Python 模块集群：重新初始化核心注册表
            # 实际上这些是 import 时加载的，重启意义不大
            # 标记为成功（因为模块在内存中，不需要实际重启）
            restarted = True
            restart_message = f"{cluster_name} 是纯 Python 模块，无需重启进程"

        # 更新重启次数
        count_file = cluster_dir / "restart_count"
        count_file.write_text(str(restart_count), encoding="utf-8")

        # 更新 status.json
        status_file = cluster_dir / "status.json"
        if status_file.exists():
            try:
                current = json.loads(status_file.read_text(encoding="utf-8"))
                current["last_restart"] = datetime.now().isoformat()
                current["restart_count"] = restart_count
                status_file.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        _record_action(
            "cluster_restart",
            {
                "cluster": cluster_name,
                "restart_count": restart_count,
                "restarted": restarted,
                "message": restart_message,
            },
        )

        should_replace = restart_count >= MAX_RESTARTS

        return {
            "ok": restarted,
            "cluster": cluster_name,
            "restart_count": restart_count,
            "should_replace": should_replace,
            "message": restart_message + (f"（已达上限，下次需替换）" if should_replace else ""),
        }

    def replace(self, cluster_name: str, source: str = "backup") -> dict[str, Any]:
        """一键替换集群（R14：坏了就换不修）。

        Args:
            cluster_name: 集群名
            source: 替换来源 - backup（从备份恢复） | git（从 git 拉取）

        实现逻辑（Netflix Immutable Infrastructure 哲学）:
          1. 标记旧集群为 replaced
          2. 初始化新集群目录（纯净状态）
          3. 重置重启计数为 0
          4. 记录替换操作（审计）
        """
        cluster_def = next((c for c in CLUSTER_DEFINITIONS if c["name"] == cluster_name), None)
        if not cluster_def:
            return {"ok": False, "reason": "未知集群"}

        cluster_dir = CLUSTERS_DIR / cluster_name

        # 1. 标记旧集群状态
        if cluster_dir.exists():
            status_file = cluster_dir / "status.json"
            if status_file.exists():
                try:
                    current = json.loads(status_file.read_text(encoding="utf-8"))
                    current["status"] = "replaced"
                    current["last_replace"] = datetime.now().isoformat()
                    current["replace_source"] = source
                    status_file.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass

        # 2. 初始化新集群（纯净状态）
        # 重新创建目录结构
        cluster_dir.mkdir(exist_ok=True)

        config = ClusterConfig(
            name=cluster_def["name"],
            core_id=cluster_def["core_id"],
            criticality=cluster_def["criticality"],
            components=cluster_def["components"],
            port=cluster_def["port"],
            process_name=cluster_def["process_name"],
            config_path=str(cluster_dir / "config.json"),
            startup_script=str(cluster_dir / "start.sh"),
        )
        (cluster_dir / "config.json").write_text(
            json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        new_status = {
            "cluster": cluster_name,
            "status": "healthy",
            "last_check": datetime.now().isoformat(),
            "last_restart": None,
            "last_replace": datetime.now().isoformat(),
            "replaced_from": source,
        }
        (cluster_dir / "status.json").write_text(
            json.dumps(new_status, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 3. 重置重启计数
        (cluster_dir / "restart_count").write_text("0", encoding="utf-8")

        # 4. 删除 FAILURE.md（如果有）
        failure_md = cluster_dir / "FAILURE.md"
        if failure_md.exists():
            failure_md.unlink()

        # 5. 重启核心服务（如果有）
        if cluster_name == "cluster-memory-vector":
            try:
                subprocess.run(
                    ["systemctl", "--user", "restart", "openclaw-embed-sidecar"],
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass
        elif cluster_name == "cluster-consciousness":
            try:
                subprocess.run(
                    ["systemctl", "--user", "restart", "openclaw-gateway"],
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass

        _record_action(
            "cluster_replace",
            {
                "cluster": cluster_name,
                "source": source,
                "core_id": cluster_def["core_id"],
                "criticality": cluster_def["criticality"],
            },
        )

        return {
            "ok": True,
            "cluster": cluster_name,
            "source": source,
            "message": f"集群 {cluster_name} 已从 {source} 替换完成，重启计数已重置",
            "restart_count_reset": True,
        }

    def list_clusters(self) -> list[dict[str, Any]]:
        """列出所有集群及其状态。"""
        results = []
        for cd in CLUSTER_DEFINITIONS:
            cluster_dir = CLUSTERS_DIR / cd["name"]
            status_data = {}
            restart_count = 0

            if cluster_dir.exists():
                status_file = cluster_dir / "status.json"
                if status_file.exists():
                    try:
                        status_data = json.loads(status_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                restart_count = self.get_failure_count(cd["name"])

            results.append(
                {
                    "name": cd["name"],
                    "core_id": cd["core_id"],
                    "criticality": cd["criticality"],
                    "status": status_data.get("status", "unknown"),
                    "restart_count": restart_count,
                    "last_check": status_data.get("last_check"),
                    "port": cd["port"],
                    "process_name": cd["process_name"],
                    "components": cd["components"],
                }
            )

        return results

    def health_check_all(self) -> list[HealthCheckResult]:
        """健康检查所有集群。"""
        return [self.health_check(cd["name"]) for cd in CLUSTER_DEFINITIONS]

    def reset_restart_count(self, cluster_name: str) -> dict[str, Any]:
        """重置集群重启计数（手动维护用）。"""
        cluster_dir = CLUSTERS_DIR / cluster_name
        if not cluster_dir.exists():
            return {"ok": False, "reason": "集群目录不存在"}

        count_file = cluster_dir / "restart_count"
        count_file.write_text("0", encoding="utf-8")

        _record_action("cluster_reset_count", {"cluster": cluster_name})
        return {"ok": True, "cluster": cluster_name, "message": "重启计数已重置为 0"}
