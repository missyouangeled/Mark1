"""Mark42 Context Safety: OpenClaw 上下文安全基线体检 / 应用 / 验收。"""

from __future__ import annotations

import json
import shutil
import subprocess
import shutil
import pathlib


def _find_openclaw() -> str:
    """动态查找 openclaw CLI 路径。"""
    path = shutil.which("openclaw")
    if path:
        return path
    for candidate in [
        pathlib.Path.home() / ".npm-global" / "bin" / "openclaw",
        pathlib.Path("/usr/local/bin/openclaw"),
        pathlib.Path("/usr/bin/openclaw"),
    ]:
        if candidate.exists():
            return str(candidate)
    return "openclaw"

from datetime import datetime
from pathlib import Path
from typing import Any

from .log_setup import get_logger
from .output_guard import trim_detail, trim_json_short
from .utils import _now_iso

logger = get_logger(__name__)


OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
SESSIONS_STORE = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
TOOL_CHECK_FILE = Path.home() / ".openclaw" / "workspace" / "tmp" / "tool-check.txt"

DEFAULT_MEMORY_FLUSH_PROMPT = (
    "在做 memory flush 时，只保留后续执行真正需要的工作记忆、用户偏好、未完成任务、约束和决策，"
    "不要把临时日志、长工具输出、重复中间推理原样搬进去。"
)
DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT = (
    "你在执行 OpenClaw 的 memory flush。输出必须简洁、结构化、可延续。"
    "优先保留：用户要求、当前任务状态、关键约束、未完成事项、已经验证过的结论。"
)

CONTEXT_PRUNING_BASELINE = {
    "mode": "cache-ttl",
    "ttl": "10m",
    "keepLastAssistants": 4,
    "softTrimRatio": 0.65,
    "hardClearRatio": 0.88,
    "minPrunableToolChars": 1200,
    "tools": {
        "allow": ["exec", "read", "process", "web_search", "web_fetch", "image"],
    },
}

COMPACTION_BASELINE = {
    "truncateAfterCompaction": True,
    "keepRecentTokens": 12000,
    "maxHistoryShare": 0.4,
    "model": "litellm/agnes-2.0-flash",
}

MEMORY_FLUSH_BASELINE = {
    "enabled": True,
    "softThresholdTokens": 15000,
    "model": "litellm/agnes-2.0-flash",
}

SESSION_MAINTENANCE_BASELINE = {
    "mode": "enforce",
    "pruneAfter": "14d",
    "maxEntries": 120,
}


def _load_openclaw_config() -> dict[str, Any]:
    if not OPENCLAW_CONFIG.exists():
        raise FileNotFoundError(f"缺少配置文件: {OPENCLAW_CONFIG}")
    with open(OPENCLAW_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_openclaw_config(data: dict[str, Any]) -> None:
    with open(OPENCLAW_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _backup_openclaw_config() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = OPENCLAW_CONFIG.with_name(f"openclaw.json.mark42-context-safety-{stamp}.bak")
    shutil.copy2(OPENCLAW_CONFIG, backup)
    return backup


def _run_openclaw_validate() -> tuple[bool, str]:
    proc = subprocess.run(
        [_find_openclaw(), "config", "validate"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output.strip()


def _ensure_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def _get_current_session_override() -> dict[str, Any]:
    if not SESSIONS_STORE.exists():
        return {}
    try:
        with open(SESSIONS_STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    current = data.get("agent:main:main", {})
    if not isinstance(current, dict):
        return {}
    return {
        "modelOverride": current.get("modelOverride"),
        "providerOverride": current.get("providerOverride"),
        "modelOverrideSource": current.get("modelOverrideSource"),
    }


def _compare_value(actual: Any, expected: Any) -> bool:
    return actual == expected


def _status_checks(config: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    agents = _ensure_dict(config, "agents")
    defaults = _ensure_dict(agents, "defaults")
    compaction = _ensure_dict(defaults, "compaction")
    memory_flush = _ensure_dict(compaction, "memoryFlush")
    context_pruning = _ensure_dict(defaults, "contextPruning")
    session = _ensure_dict(config, "session")
    maintenance = _ensure_dict(session, "maintenance")

    def add_check(name: str, actual: Any, expected: Any, severity: str = "warn") -> None:
        ok = _compare_value(actual, expected)
        checks.append(
            {
                "name": name,
                "actual": actual,
                "expected": expected,
                "ok": ok,
                "severity": "pass" if ok else severity,
            }
        )

    for key, expected in CONTEXT_PRUNING_BASELINE.items():
        add_check(f"contextPruning.{key}", context_pruning.get(key), expected)

    add_check("compaction.truncateAfterCompaction", compaction.get("truncateAfterCompaction"), COMPACTION_BASELINE["truncateAfterCompaction"])
    add_check("compaction.keepRecentTokens", compaction.get("keepRecentTokens"), COMPACTION_BASELINE["keepRecentTokens"])
    add_check("compaction.maxHistoryShare", compaction.get("maxHistoryShare"), COMPACTION_BASELINE["maxHistoryShare"])
    add_check("compaction.model", compaction.get("model"), COMPACTION_BASELINE["model"])

    add_check("memoryFlush.enabled", memory_flush.get("enabled"), MEMORY_FLUSH_BASELINE["enabled"])
    add_check("memoryFlush.softThresholdTokens", memory_flush.get("softThresholdTokens"), MEMORY_FLUSH_BASELINE["softThresholdTokens"])
    add_check("memoryFlush.model", memory_flush.get("model"), MEMORY_FLUSH_BASELINE["model"])

    add_check("session.maintenance.mode", maintenance.get("mode"), SESSION_MAINTENANCE_BASELINE["mode"])
    add_check("session.maintenance.pruneAfter", maintenance.get("pruneAfter"), SESSION_MAINTENANCE_BASELINE["pruneAfter"])
    add_check("session.maintenance.maxEntries", maintenance.get("maxEntries"), SESSION_MAINTENANCE_BASELINE["maxEntries"])

    override = _get_current_session_override()
    checks.append(
        {
            "name": "currentSession.modelOverride",
            "actual": override,
            "expected": "由模型选择列表决定；本模块只提示不修改",
            "ok": True,
            "severity": "info",
        }
    )

    return checks


def _print_checks(checks: list[dict[str, Any]], verbose: bool = False) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "info": 0}
    for item in checks:
        severity = item["severity"]
        counts[severity] = counts.get(severity, 0) + 1
        prefix = {
            "pass": "[PASS]",
            "warn": "[WARN]",
            "fail": "[FAIL]",
            "info": "[INFO]",
        }.get(severity, "[INFO]")
        if severity == "info":
            shown = item['actual'] if verbose else trim_json_short(item['actual'], 120)
            logger.info(f"{prefix} {item['name']}: {shown}")
        else:
            if verbose:
                actual = repr(item['actual'])
                expected = repr(item['expected'])
            else:
                actual = trim_detail(repr(trim_json_short(item['actual'], 120)), 160)
                expected = trim_detail(repr(trim_json_short(item['expected'], 120)), 160)
            logger.info(f"{prefix} {item['name']}: actual={actual} expected={expected}")
    return counts


def context_safety_status(verbose: bool = False) -> dict[str, Any]:
    config = _load_openclaw_config()
    checks = _status_checks(config)
    logger.info("== Mark42 Context Safety Status ==")
    logger.info(f"config: {OPENCLAW_CONFIG}")
    counts = _print_checks(checks, verbose=verbose)
    logger.info(f"summary: pass={counts['pass']} warn={counts['warn']} fail={counts['fail']} info={counts['info']}")
    return {"checks": checks, "summary": counts, "checkedAt": _now_iso()}


def _merge_context_safety_patch(config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    changed: list[str] = []
    agents = _ensure_dict(config, "agents")
    defaults = _ensure_dict(agents, "defaults")
    context_pruning = _ensure_dict(defaults, "contextPruning")
    compaction = _ensure_dict(defaults, "compaction")
    memory_flush = _ensure_dict(compaction, "memoryFlush")
    session = _ensure_dict(config, "session")
    maintenance = _ensure_dict(session, "maintenance")

    for key, expected in CONTEXT_PRUNING_BASELINE.items():
        if context_pruning.get(key) != expected:
            context_pruning[key] = expected
            changed.append(f"agents.defaults.contextPruning.{key}")

    if compaction.get("mode") != "safeguard":
        compaction["mode"] = "safeguard"
        changed.append("agents.defaults.compaction.mode")

    for key, expected in COMPACTION_BASELINE.items():
        if compaction.get(key) != expected:
            compaction[key] = expected
            changed.append(f"agents.defaults.compaction.{key}")

    for key, expected in MEMORY_FLUSH_BASELINE.items():
        if memory_flush.get(key) != expected:
            memory_flush[key] = expected
            changed.append(f"agents.defaults.compaction.memoryFlush.{key}")

    if not memory_flush.get("prompt"):
        memory_flush["prompt"] = DEFAULT_MEMORY_FLUSH_PROMPT
        changed.append("agents.defaults.compaction.memoryFlush.prompt")

    if not memory_flush.get("systemPrompt"):
        memory_flush["systemPrompt"] = DEFAULT_MEMORY_FLUSH_SYSTEM_PROMPT
        changed.append("agents.defaults.compaction.memoryFlush.systemPrompt")

    for key, expected in SESSION_MAINTENANCE_BASELINE.items():
        if maintenance.get(key) != expected:
            maintenance[key] = expected
            changed.append(f"session.maintenance.{key}")

    return config, changed


def context_safety_apply(verbose: bool = False) -> dict[str, Any]:
    config = _load_openclaw_config()
    new_config, changed = _merge_context_safety_patch(config)
    backup = None
    if changed:
        backup = _backup_openclaw_config()
        _save_openclaw_config(new_config)
    valid, output = _run_openclaw_validate()
    logger.info("== Mark42 Context Safety Apply ==")
    logger.info(f"backup: {backup if backup else 'none'}")
    if changed:
        logger.info("changed:")
        if verbose:
            for item in changed:
                logger.info(f"  - {item}")
        else:
            logger.info(f"  - {len(changed)} 项变更")
    else:
        logger.info("changed: none")
    logger.info(f"validate: {'PASS' if valid else 'FAIL'}")
    if output:
        logger.info(output)
    return {
        "backup": str(backup) if backup else None,
        "changed": changed,
        "validateOk": valid,
        "validateOutput": output,
        "appliedAt": _now_iso(),
    }


def context_safety_verify(verbose: bool = False) -> int:
    result = context_safety_status(verbose=verbose)
    valid, output = _run_openclaw_validate()
    logger.info("== Validate ==")
    logger.info(f"status: {'PASS' if valid else 'FAIL'}")
    if output and verbose:
        logger.info(output)
    smoke_ok, smoke_lines = _run_light_smoke_checks()
    logger.info("== Smoke ==")
    if verbose:
        for line in smoke_lines:
            logger.info(line)
    else:
        pass_count = sum(1 for line in smoke_lines if line.startswith("[PASS]"))
        fail_count = sum(1 for line in smoke_lines if line.startswith("[FAIL]"))
        logger.info(f"summary: pass={pass_count} fail={fail_count}")
    summary = result["summary"]
    if not valid:
        return 1
    if summary.get("fail", 0) > 0:
        return 1
    if not smoke_ok:
        return 1
    return 0


def _run_light_smoke_checks() -> tuple[bool, list[str]]:
    lines: list[str] = []
    ok = True

    if TOOL_CHECK_FILE.exists():
        try:
            content = TOOL_CHECK_FILE.read_text(encoding="utf-8").strip().replace("\n", " / ")
            lines.append(f"[PASS] read smoke: {TOOL_CHECK_FILE} -> {content}")
        except OSError as exc:
            ok = False
            lines.append(f"[FAIL] read smoke: {exc}")
    else:
        ok = False
        lines.append(f"[FAIL] read smoke: 缺少测试文件 {TOOL_CHECK_FILE}")

    if OPENCLAW_CONFIG.exists():
        lines.append("[PASS] internal status smoke: openclaw 配置文件存在")
    else:
        ok = False
        lines.append(f"[FAIL] internal status smoke: 缺少配置文件 {OPENCLAW_CONFIG}")

    try:
        proc = subprocess.run(
            ["curl", "-fsSL", "https://docs.openclaw.ai"],
            capture_output=True,
            text=False,
            check=False,
            timeout=20,
        )
        if proc.returncode == 0 and b"OpenClaw" in proc.stdout[:4096]:
            lines.append("[PASS] web_fetch smoke: docs.openclaw.ai 可达")
        else:
            ok = False
            lines.append("[FAIL] web_fetch smoke: docs.openclaw.ai 抽检失败")
    except (OSError, subprocess.TimeoutExpired) as exc:
        ok = False
        lines.append(f"[FAIL] web_fetch smoke: {exc}")

    return ok, lines
