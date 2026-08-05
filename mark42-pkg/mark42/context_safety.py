"""Mark42 Context Safety: OpenClaw 上下文安全基线体检 / 应用 / 验收。"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import OPENCLAW_BIN
from .output_guard import trim_detail, trim_json_short
from .utils import _now_iso

logger = logging.getLogger(__name__)


def _openclaw_config_path() -> Path:
    """openclaw.json 实际路径。延迟求值，尊重 CLI/环境变量/TOML (P2-16)。

    若调用方（包括测试）**显式**给本模块赋了 ``OPENCLAW_CONFIG``，
    则以该赋值为准（保留原有注入契约）。未赋值时才走统一解析器。
    关键区别：旧实现在 import 时就把默认值写成模块常量，使得环境变量
    永远无法生效；现在默认不预先赋值。
    """
    explicit = globals().get("OPENCLAW_CONFIG")
    if explicit is not None:
        return Path(explicit)

    from .user_config import get_openclaw_config_path

    return get_openclaw_config_path()


def __getattr__(name: str):
    """向后兼容：旧代码/测试仍可读模块级 ``OPENCLAW_CONFIG``（每次重新解析）。"""
    if name == "OPENCLAW_CONFIG":
        return _openclaw_config_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    # 【2026-07-31 P2 调优】从 15000 提到 32000（compaction 调优建议，舒适范围 16000-64000）
    # 原因：15000 偏低会导致 memory flush 过早触发
    "softThresholdTokens": 32000,
    "model": "litellm/agnes-2.0-flash",
}

SESSION_MAINTENANCE_BASELINE = {
    "mode": "enforce",
    "pruneAfter": "14d",
    "maxEntries": 120,
}


def _load_openclaw_config() -> dict[str, Any]:
    config_path = _openclaw_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"缺少配置文件: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def _save_openclaw_config(data: dict[str, Any]) -> None:
    """安全写入 openclaw.json。

    【2026-08-03 修复 P0-3】原实现直接 open(path, "w") 截断后再 dump，
    写到一半崩溃会把 openclaw.json 变成半截 JSON → Gateway 直接起不来
    （参考 CASE-20260616-002，High）。现改为原子写入 + 跳进程锁：
    临时文件 → fsync → os.replace()，要么完整旧内容要么完整新内容。
    """
    from .openclaw_config import _atomic_write_json, _exclusive_lock

    config_path = _openclaw_config_path()
    bak = Path(str(config_path) + ".bak." + datetime.now().strftime("%Y%m%d%H%M%S"))
    if config_path.exists():
        shutil.copy2(config_path, bak)
    try:
        with _exclusive_lock():
            _atomic_write_json(config_path, data)
    except Exception as e:
        logger.error("写入 openclaw.json 失败，正在回滚: %s", e)
        if bak.exists():
            shutil.copy2(bak, config_path)
        raise


def _backup_openclaw_config() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    config_path = _openclaw_config_path()
    backup = config_path.with_name(f"openclaw.json.mark42-context-safety-{stamp}.bak")
    shutil.copy2(config_path, backup)
    return backup


def _run_openclaw_validate() -> tuple[bool, str]:
    proc = subprocess.run(
        [OPENCLAW_BIN, "config", "validate"],
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
        with open(SESSIONS_STORE, encoding="utf-8") as f:
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
            print(f"{prefix} {item['name']}: {shown}")
        else:
            if verbose:
                actual = repr(item['actual'])
                expected = repr(item['expected'])
            else:
                actual = trim_detail(repr(trim_json_short(item['actual'], 120)), 160)
                expected = trim_detail(repr(trim_json_short(item['expected'], 120)), 160)
            print(f"{prefix} {item['name']}: actual={actual} expected={expected}")
    return counts


def context_safety_status(verbose: bool = False) -> dict[str, Any]:
    config = _load_openclaw_config()
    checks = _status_checks(config)
    print("== Mark42 Context Safety Status ==")
    print(f"config: {_openclaw_config_path()}")
    counts = _print_checks(checks, verbose=verbose)
    print(f"summary: pass={counts['pass']} warn={counts['warn']} fail={counts['fail']} info={counts['info']}")
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


def _validate_candidate_config(candidate: dict[str, Any]) -> tuple[bool, str]:
    """在**不触碰正式文件**的前提下校验候选配置 (P1-5)。

    做法：把候选配置写到临时文件，让 ``openclaw config validate``
    通过 ``OPENCLAW_CONFIG`` 指向该临时文件。这样非法候选永远不会
    成为正式配置。

    返回 ``(是否通过, 输出)``。若无法在预校验阶段得出结论（例如
    该版本 CLI 不支持环境变量覆盖），返回 ``(True, "")`` 表示
    “预校验不可用”，由调用方回退到“写入后复验 + 失败回滚”。
    """
    import os
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="mark42-cfg-validate-")
    tmp_cfg = Path(tmp_dir) / "openclaw.json"
    try:
        tmp_cfg.write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["OPENCLAW_CONFIG"] = str(tmp_cfg)
        proc = subprocess.run(
            [OPENCLAW_BIN, "config", "validate"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if proc.returncode == 0:
            return True, output

        # 关键：只有当 CLI 真的看到了我们的临时文件并拒绞它时，
        # 才能判定“候选配置非法”。如果该版本 CLI 不支持用
        # OPENCLAW_CONFIG 覆盖路径（或它去读了另一个不存在的默认路径），
        # 那这个失败只能说明“预校验不可用”，而不能说明候选配置有错。
        # 把环境问题误当成 schema 非法会直接堵死正常 apply。
        if str(tmp_cfg) not in output:
            logger.warning(
                "候选配置预校验不可用（CLI 未读取临时文件），将回退到写入后复验: %s",
                output[:200],
            )
            return True, ""
        return False, output
    except Exception as e:
        # 预校验本身出错不能造成“误报非法”，交由调用方走写后复验路径
        logger.warning("候选配置预校验不可用，将回退到写入后复验: %s", e)
        return True, ""
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _restore_openclaw_config(backup: Path) -> tuple[bool, str]:
    """从备份恢复正式配置。返回 ``(是否成功, 说明)``。

    回滚失败必须作为**独立高严重错误**上报（P1-5 验收标准），
    因为此时正式配置可能已不可用，Gateway 有起不来的风险。
    """
    config_path = _openclaw_config_path()
    try:
        if not backup.exists():
            return False, f"备份文件不存在: {backup}"
        from .openclaw_config import _atomic_write_json

        # 走原子写，避免回滚本身写到一半又把配置搞成半截 JSON
        _atomic_write_json(config_path, json.loads(backup.read_text(encoding="utf-8")))
        return True, f"已从备份恢复: {backup.name}"
    except Exception as e:
        logger.critical(
            "回滚 openclaw.json 失败！正式配置可能已不可用，请立即人工从 %s 恢复: %s",
            backup, e,
        )
        return False, f"回滚失败: {e}"


def context_safety_apply(
    verbose: bool = False, execute_now: bool = False
) -> dict[str, Any]:
    """对齐 OpenClaw context 安全基线。

    【P1-5 修复】2026-08-05。旧流程是：先把新配置写进正式文件，
    再跑 ``openclaw config validate``；validate 失败只把
    ``validateOk=False`` 塞进返回值，**已写入的无效配置原地留着**。
    备份虽然建了却从没人用它回滚 —— 一旦 merge 结果是合法 JSON 但
    不符 OpenClaw schema，Gateway 直接起不来。

    现流程：
      1. 锁内重读最新配置（不用陈旧快照，兼顾 P2-6）
      2. 生成候选配置
      3. 在**临时文件**上校验候选配置
      4. 预校验失败 -> 直接拒绞写入（正式配置未被碰过）
      5. 预校验通过 -> 备份 + 原子替换
      6. 写入后**再次校验**，失败立即从备份回滚
      7. 回滚失败作为独立高严重错误上报

    【注意】``_exclusive_lock()`` 不可重入（已实测：同进程嵌套获取会
    ConfigWriteError 超时），因此这里**不能**把整个流程包在锁里——
    ``_save_openclaw_config`` / ``_atomic_write_json`` 内部自己拿锁。
    持锁范围只限定在写入区间。

    Args:
        verbose: 输出逐项变更
        execute_now: 默认 ``False`` 为 dry-run，只报告将要做什么不真写。
            真实写入必须显式传 ``True``（对齐仓内
            ``heavy_execute`` 的 dry-run 默认安全惯例）。
    """
    config = _load_openclaw_config()
    new_config, changed = _merge_context_safety_patch(config)

    result: dict[str, Any] = {
        "backup": None,
        "changed": changed,
        "validateOk": True,
        "validateOutput": "",
        "dryRun": not execute_now,
        "written": False,
        "rolledBack": False,
        "appliedAt": _now_iso(),
    }

    print("== Mark42 Context Safety Apply ==")

    if not changed:
        valid, output = _run_openclaw_validate()
        result["validateOk"] = valid
        result["validateOutput"] = output
        print("backup: none")
        print("changed: none")
        print(f"validate: {'PASS' if valid else 'FAIL'}")
        if output:
            print(output)
        return result

    # 先在临时文件上校验候选配置 —— 非法候选永不落盘
    pre_valid, pre_output = _validate_candidate_config(new_config)
    result["candidateValidateOk"] = pre_valid
    if not pre_valid:
        result["validateOk"] = False
        result["validateOutput"] = pre_output
        print("backup: none")
        print(f"changed: {len(changed)} 项待变更（已拒绞）")
        if verbose:
            for item in changed:
                print(f"  - {item}")
        print("validate: FAIL（候选配置预校验未通过，正式配置未被修改）")
        if pre_output:
            print(pre_output)
        return result

    if not execute_now:
        print("backup: none（dry-run）")
        print(f"changed: {len(changed)} 项待变更")
        if verbose:
            for item in changed:
                print(f"  - {item}")
        print("validate: PASS（候选配置预校验通过）")
        print("dry-run：未写入。确认无误后加 --execute-now 真实应用。")
        return result

    # 真实写入：备份 -> 原子替换 -> 复验 -> 失败回滚
    backup = _backup_openclaw_config()
    result["backup"] = str(backup)
    _save_openclaw_config(new_config)
    result["written"] = True

    valid, output = _run_openclaw_validate()
    result["validateOk"] = valid
    result["validateOutput"] = output

    print(f"backup: {backup}")
    print("changed:")
    if verbose:
        for item in changed:
            print(f"  - {item}")
    else:
        print(f"  - {len(changed)} 项变更")
    print(f"validate: {'PASS' if valid else 'FAIL'}")
    if output:
        print(output)

    if not valid:
        restored, note = _restore_openclaw_config(backup)
        result["rolledBack"] = restored
        result["rollbackNote"] = note
        if restored:
            print(f"rollback: OK（{note}）")
        else:
            # 回滚失败是独立的高严重错误，必须显著提示
            result["rollbackFailed"] = True
            print(f"rollback: FAILED！{note}")
            print(f"⚠ 正式配置可能已不可用，请立即人工从 {backup} 恢复")

    return result


def context_safety_verify(verbose: bool = False) -> int:
    result = context_safety_status(verbose=verbose)
    valid, output = _run_openclaw_validate()
    print("== Validate ==")
    print(f"status: {'PASS' if valid else 'FAIL'}")
    if output and verbose:
        print(output)
    smoke_ok, smoke_lines = _run_light_smoke_checks()
    print("== Smoke ==")
    if verbose:
        for line in smoke_lines:
            print(line)
    else:
        pass_count = sum(1 for line in smoke_lines if line.startswith("[PASS]"))
        fail_count = sum(1 for line in smoke_lines if line.startswith("[FAIL]"))
        print(f"summary: pass={pass_count} fail={fail_count}")
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

    config_path = _openclaw_config_path()
    if config_path.exists():
        lines.append("[PASS] internal status smoke: openclaw 配置文件存在")
    else:
        ok = False
        lines.append(f"[FAIL] internal status smoke: 缺少配置文件 {config_path}")

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
