"""
Mark42 v3 §4.8 · 核心位注册表 (Core Registry)

按 v3 §4.8 钉死的核心位注册表实现：
- 8 个核心位的状态管理（healthy/degraded/down/quarantined）
- 启动时探活 + 状态变化时更新
- CLI: mark42 cores list / verify / quarantine / restore

数据存储：~/.local/state/openclaw/mark42/core-registry/registry.json
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────

REGISTRY_DIR = Path.home() / ".local" / "state" / "openclaw" / "mark42" / "core-registry"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"

# 8 个核心位定义（§3.6 + §3.6.2 R13-D）
CORE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "core_id": "core_1_main_consciousness",
        "core_role": "main_consciousness",
        "model_name": "minimax/MiniMax-M3",
        "runtime": "api",
        "base_url": "https://api.minimax.chat/v1",
        "criticality": "critical",
        "fallback_chain": ["litellm/agnes-2.0-flash", "nvidia/z-ai/glm-5.2"],
    },
    {
        "core_id": "core_2_armor_consciousness",
        "core_role": "armor_consciousness",
        "model_name": "agnes-2.0-flash",
        "runtime": "api",
        "base_url": "https://apihub.agnes-ai.com/v1",
        "criticality": "degradable",
        "fallback_chain": ["degraded_to_v2"],
    },
    {
        "core_id": "core_3_memory_vector_engine",
        "core_role": "memory_vector",
        "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
        "runtime": "local_http",
        "base_url": "http://127.0.0.1:18792",
        "criticality": "degradable",
        "fallback_chain": ["L1_keyword_only"],
    },
    {
        "core_id": "core_4_text_compressor",
        "core_role": "text_compression",
        "model_name": "text_compressor + llm_text_compressor",
        "runtime": "local_python",
        "base_url": "",
        "criticality": "optional",
        "fallback_chain": ["truncate_only"],
    },
    {
        "core_id": "core_5_code_understand",
        "core_role": "code_understanding",
        "model_name": "code_analyzer (GLM-5.2 via API)",
        "runtime": "api",
        "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
        "criticality": "optional",
        "fallback_chain": ["skip"],
    },
    {
        "core_id": "core_6_log_classify",
        "core_role": "log_classification",
        "model_name": "log_classifier (keyword rules)",
        "runtime": "local_python",
        "base_url": "",
        "criticality": "optional",
        "fallback_chain": ["by_source"],
    },
    {
        "core_id": "core_7_pii_redact",
        "core_role": "pii_redaction",
        "model_name": "pii_redactor (regex + luhn)",
        "runtime": "local_python",
        "base_url": "",
        "criticality": "optional",
        "fallback_chain": ["regex_only"],
    },
    {
        "core_id": "core_8_anomaly_detect",
        "core_role": "anomaly_detection",
        "model_name": "anomaly_detector (threshold + zscore)",
        "runtime": "local_python",
        "base_url": "",
        "criticality": "optional",
        "fallback_chain": ["threshold_only"],
    },
]


# ── 数据类 ───────────────────────────────────────────

@dataclass
class CoreEntry:
    """单个核心位的注册信息。"""
    core_id: str
    core_role: str
    model_name: str
    runtime: str
    base_url: str
    criticality: str  # critical | degradable | optional
    fallback_chain: List[str] = field(default_factory=list)
    status: str = "unknown"  # unknown | healthy | degraded | down | quarantined
    last_used_at: Optional[str] = None
    total_invocations: int = 0
    total_failures: int = 0
    last_failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 探活函数 ─────────────────────────────────────────

def _probe_http(url: str, timeout: int = 3) -> bool:
    """HTTP 探活。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _probe_systemd(service: str) -> str:
    """systemd service 探活。返回 active/inactive/unknown。"""
    import subprocess
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", service],
            capture_output=True, text=True, timeout=3)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def probe_core(core_id: str) -> Dict[str, Any]:
    """探活单个核心。返回 {status, reason}。"""
    core = next((c for c in CORE_DEFINITIONS if c["core_id"] == core_id), None)
    if not core:
        return {"status": "unknown", "reason": "core not found"}

    rt = core["runtime"]
    url = core["base_url"]
    crit = core["criticality"]

    # 未加载的核心
    if rt == "none" or core["model_name"] == "not_loaded":
        return {"status": "down", "reason": "not_loaded"}

    # HTTP 探活
    if rt in ("api", "local_http") and url:
        if core_id == "core_1_main_consciousness":
            # 主意识走 OpenClaw gateway
            ok = _probe_http("http://127.0.0.1:18788/healthz")
            return {"status": "healthy" if ok else "down",
                    "reason": "" if ok else "gateway 不可达"}
        elif core_id == "core_3_memory_vector_engine":
            ok = _probe_http("http://127.0.0.1:18792/healthz")
            return {"status": "healthy" if ok else "down",
                    "reason": "" if ok else "embed-sidecar /healthz 不可达"}
        elif core_id == "core_2_armor_consciousness":
            # 意识层走 API，不直接探活（太慢），默认 healthy
            return {"status": "healthy", "reason": "api provider (skip probe)"}
        elif core_id == "core_5_code_understand":
            # 核心 5 走 API，不直接探活（太慢），默认 healthy
            return {"status": "healthy", "reason": "code_analyzer (api provider, skip probe)"}
        else:
            ok = _probe_http(url)
            return {"status": "healthy" if ok else "down",
                    "reason": "" if ok else f"{url} 不可达"}

    # Python 模块探活（核心 4 和 7）
    if rt == "local_python":
        try:
            if core_id == "core_4_text_compressor":
                from mark42_modules.text_compressor import TextCompressor
                TextCompressor()
                return {"status": "healthy", "reason": "text_compressor loaded"}
            elif core_id == "core_7_pii_redact":
                from mark42_modules.pii_redactor import PIIRedactor
                PIIRedactor()
                return {"status": "healthy", "reason": "pii_redactor loaded"}
            elif core_id == "core_6_log_classify":
                from mark42_modules.log_classifier import LogClassifier
                clf = LogClassifier()
                ok = clf.health_check()
                return {"status": "healthy" if ok else "down",
                        "reason": "log_classifier loaded" if ok else "health_check failed"}
            elif core_id == "core_8_anomaly_detect":
                from mark42_modules.anomaly_detector import AnomalyDetector
                ad = AnomalyDetector()
                ok = ad.health_check()
                return {"status": "healthy" if ok else "down",
                        "reason": "anomaly_detector loaded" if ok else "health_check failed"}
        except Exception as e:
            return {"status": "down", "reason": f"import failed: {e}"}

    return {"status": "unknown", "reason": f"unknown runtime: {rt}"}


# ── CoreRegistry 主类 ───────────────────────────────

class CoreRegistry:
    """核心位注册表。"""

    def __init__(self):
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if REGISTRY_FILE.exists():
            try:
                data = json.loads(REGISTRY_FILE.read_text())
                self.cores = {k: CoreEntry(**v) for k, v in data.get("cores", {}).items()}
            except Exception:
                self.cores = self._init_defaults()
        else:
            self.cores = self._init_defaults()

    def _init_defaults(self) -> Dict[str, CoreEntry]:
        return {c["core_id"]: CoreEntry(**c) for c in CORE_DEFINITIONS}

    def _save(self):
        data = {
            "cores": {k: v.to_dict() for k, v in self.cores.items()},
            "updated_at": datetime.now().isoformat(),
        }
        REGISTRY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def list_cores(self) -> List[Dict[str, Any]]:
        """列出所有核心。"""
        return [c.to_dict() for c in self.cores.values()]

    def get_core(self, core_id: str) -> Optional[CoreEntry]:
        return self.cores.get(core_id)

    def probe_all(self) -> Dict[str, Any]:
        """探活所有核心，更新状态。"""
        results = {}
        for core_id in self.cores:
            r = probe_core(core_id)
            self.cores[core_id].status = r["status"]
            if r["status"] == "healthy":
                # 更新 model_name（探活时可能从 not_loaded 变为已加载）
                core_def = next((c for c in CORE_DEFINITIONS if c["core_id"] == core_id), None)
                if core_def:
                    self.cores[core_id].model_name = core_def["model_name"]
            if r["status"] != "healthy" and r.get("reason"):
                self.cores[core_id].last_failure_reason = r["reason"]
            results[core_id] = r
        self._save()
        return results

    def quarantine(self, core_id: str, reason: str = "") -> bool:
        """隔离核心。"""
        if core_id not in self.cores:
            return False
        self.cores[core_id].status = "quarantined"
        self.cores[core_id].last_failure_reason = reason
        self._save()
        return True

    def restore(self, core_id: str) -> bool:
        """恢复隔离的核心。"""
        if core_id not in self.cores:
            return False
        r = probe_core(core_id)
        self.cores[core_id].status = r["status"]
        self.cores[core_id].last_failure_reason = None
        self._save()
        return True

    def record_invocation(self, core_id: str, success: bool, reason: str = ""):
        """记录一次调用。"""
        if core_id not in self.cores:
            return
        c = self.cores[core_id]
        c.total_invocations += 1
        c.last_used_at = datetime.now().isoformat()
        if not success:
            c.total_failures += 1
            c.last_failure_reason = reason
        self._save()

    def summary(self) -> Dict[str, Any]:
        """摘要统计。"""
        statuses = {}
        for c in self.cores.values():
            statuses[c.status] = statuses.get(c.status, 0) + 1
        return {
            "total": len(self.cores),
            "statuses": statuses,
            "critical_down": [c.core_id for c in self.cores.values()
                              if c.criticality == "critical" and c.status == "down"],
        }


# ── CLI 接口 ────────────────────────────────────────

def cli_cores_list() -> Dict[str, Any]:
    reg = CoreRegistry()
    return {"cores": reg.list_cores(), "summary": reg.summary()}

def cli_cores_probe() -> Dict[str, Any]:
    reg = CoreRegistry()
    return reg.probe_all()

def cli_cores_quarantine(core_id: str, reason: str = "") -> Dict[str, Any]:
    reg = CoreRegistry()
    ok = reg.quarantine(core_id, reason)
    return {"ok": ok, "core_id": core_id}

def cli_cores_restore(core_id: str) -> Dict[str, Any]:
    reg = CoreRegistry()
    ok = reg.restore(core_id)
    return {"ok": ok, "core_id": core_id}
