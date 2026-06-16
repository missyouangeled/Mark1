"""Mark42 压缩诊断与自动调优模块。
检测 OpenClaw 内置压缩配置，诊断问题，生成舒适合理的优化建议并可选自动应用。
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONTEXT_WINDOW
from .utils import _now_iso

# ── 常量 ──────────────────────────────────────────────

# 默认路径
_OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"

# 舒适范围定义（基于 128K+ 上下文窗口模型的实践数据）
_COMFORT_ZONES = {
    # 键: (最小值, 舒适值, 最大值, 单位, 说明)
    "maxActiveTranscriptBytes": {
        "min": 1_000_000,     # ~1MB
        "comfort": 3_000_000,  # ~3MB
        "max": 10_000_000,    # ~10MB
        "unit": "bytes",
        "label": "JSONL 压缩阈值",
        "desc": "JSONL 文件超过此大小时触发压缩。太低=频繁碎片化，太高=单文件过大加载慢。",
        "advice_low": "阈值过低 → 会话频繁碎片化，每次压缩都要等待。建议提高到 {comfort}（约{comfort_mb}MB）",
        "advice_high": "阈值偏高 → 单文件加载可能稍慢，但当前模型上下文窗口（{ctx}K）足以支撑，暂无问题",
    },
    "keepRecentTokens": {
        "min": 8_000,
        "comfort": 15_000,
        "max": 30_000,  # 不能太高，否则压缩没什么效果
        "unit": "tokens",
        "label": "保留最近 Token 数",
        "desc": "压缩时保留最近多少 token 不压缩。太低=丢近期上下文，太高=压不彻底很快又压。",
        "advice_low": "保留太少 → 压缩后可能丢失近期关键上下文。建议提高到 {comfort}",
        "advice_high": "保留太多 → 压缩不彻底，很快又触发下一次压缩。建议降低到 {comfort}",
    },
    "reserveTokens": {
        "min": 8_000,
        "comfort": 16_000,
        "max": 32_000,
        "unit": "tokens",
        "label": "预留空间",
        "desc": "触发压缩前为系统提示和下次模型输出预留的 token 数。",
        "advice_low": "预留空间过小 → 可能在多轮对话中过早触发压缩。建议 {comfort}",
        "advice_high": "预留空间偏大 → 会提前触发压缩。若无特殊需求，建议 {comfort}",
    },
    "softThresholdTokens": {
        "min": 16_000,
        "comfort": 32_000,
        "max": 64_000,
        "unit": "tokens",
        "label": "Memory Flush 软阈值",
        "desc": "上下文 token 超过此值时，在下次压缩前先触发静默记忆写入。",
        "advice_low": "阈值偏低 → memory flush 过早触发。",
        "advice_high": "阈值偏高 → 可能压缩已经发生但 flush 还没触发。",
    },
}

# 关键缺失→严重度映射
_MISSING_ALERTS = {
    "memoryFlush": {
        "severity": "warn",
        "fix": "启用 memoryFlush（压缩前自动写入记忆，防止上下文丢失）",
        "default_value": {
            "enabled": True,
            "softThresholdTokens": 32_000,
            "prompt": (
                "NO_REPLY\n"
                "将关键决策、任务状态、偏好变更、新增规则写入 memory/daily/YYYY-MM-DD.md。"
                "日常闲聊跳过。若无值得保留：什么都不写。"
            ),
            "systemPrompt": "只持久化对后续会话有延续价值的信息。简洁，不废话。",
        },
    },
}

# 建议的最低配置
_RECOMMENDED = {
    "mode": "safeguard",
    "truncateAfterCompaction": True,
    "notifyUser": True,
}

# 诊断结果严重度
SEVERITY_OK = "ok"
SEVERITY_WARN = "warn"
SEVERITY_CRIT = "critical"


def _load_openclaw_json() -> dict[str, Any] | None:
    """加载 openclaw.json。"""
    if not _OPENCLAW_JSON.exists():
        return None
    try:
        with open(_OPENCLAW_JSON) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _get_compaction_config() -> dict[str, Any] | None:
    """提取 compaction 配置段。"""
    cfg = _load_openclaw_json()
    if not cfg:
        return None
    agents = cfg.get("agents", {})
    defaults = agents.get("defaults", {})
    return defaults.get("compaction", {})


def _get_context_window() -> int:
    """从 openclaw.json 或当前模型获取上下文窗口大小。"""
    cfg = _load_openclaw_json()
    if cfg:
        # 尝试从 models 拿
        ms = cfg.get("models", {})
        if isinstance(ms, dict):
            provider_cfgs = ms.get("providers", {})
            for pname in ("deepseek-company", "deepseek"):
                p = provider_cfgs.get(pname, {})
                mods = p.get("models", [])
                if isinstance(mods, list):
                    for m in mods:
                        if isinstance(m, dict) and m.get("contextWindow"):
                            return m["contextWindow"]
                elif isinstance(mods, dict):
                    for mname, mcfg in mods.items():
                        if isinstance(mcfg, dict) and mcfg.get("contextWindow"):
                            return mcfg["contextWindow"]
    return DEFAULT_CONTEXT_WINDOW


def _format_bytes(b: int) -> str:
    """人性化字节显示。"""
    if b >= 1_000_000:
        return f"{b/1_000_000:.1f}MB"
    if b >= 1_000:
        return f"{b/1_000:.0f}KB"
    return f"{b}B"


def _check_value(key: str, value: int | None, ctx_window: int) -> dict[str, Any]:
    """检查单个配置值是否在舒适范围内。"""
    zone = _COMFORT_ZONES.get(key)
    if not zone or value is None:
        return {"key": key, "status": "missing", "severity": SEVERITY_OK}

    cmin, ccomfort, cmax = zone["min"], zone["comfort"], zone["max"]

    if value < cmin:
        return {
            "key": key,
            "label": zone["label"],
            "status": "too_low",
            "severity": SEVERITY_WARN,
            "current": value,
            "current_human": _format_bytes(value) if zone["unit"] == "bytes" else f"{value}",
            "comfort": ccomfort,
            "comfort_human": _format_bytes(ccomfort) if zone["unit"] == "bytes" else f"{ccomfort}",
            "range": f"{_format_bytes(cmin) if zone['unit']=='bytes' else cmin} ~ {_format_bytes(cmax) if zone['unit']=='bytes' else cmax}",
            "advice": zone["advice_low"].format(
                comfort=ccomfort,
                comfort_mb=_format_bytes(ccomfort) if zone["unit"] == "bytes" else ccomfort,
                ctx=ctx_window // 1000,
            ),
        }
    if value > cmax:
        level = SEVERITY_WARN if key == "keepRecentTokens" else SEVERITY_OK
        return {
            "key": key,
            "label": zone["label"],
            "status": "too_high",
            "severity": level,
            "current": value,
            "current_human": _format_bytes(value) if zone["unit"] == "bytes" else f"{value}",
            "comfort": ccomfort,
            "comfort_human": _format_bytes(ccomfort) if zone["unit"] == "bytes" else f"{ccomfort}",
            "range": f"{_format_bytes(cmin) if zone['unit']=='bytes' else cmin} ~ {_format_bytes(cmax) if zone['unit']=='bytes' else cmax}",
            "advice": zone.get("advice_high", "").format(
                comfort=ccomfort,
                comfort_mb=_format_bytes(ccomfort) if zone["unit"] == "bytes" else ccomfort,
                ctx=ctx_window // 1000,
            ),
        }
    return {
        "key": key,
        "label": zone["label"],
        "status": "ok",
        "severity": SEVERITY_OK,
        "current": value,
        "current_human": _format_bytes(value) if zone["unit"] == "bytes" else f"{value}",
        "comfort": ccomfort,
        "range": f"{_format_bytes(cmin) if zone['unit']=='bytes' else cmin} ~ {_format_bytes(cmax) if zone['unit']=='bytes' else cmax}",
    }


def _check_stat(session_count: int, largest_mb: float, ctx_window: int) -> list[dict[str, Any]]:
    """检测会话碎片化程度。"""
    issues = []
    # 碎片化检测：短时间内大量 session 文件
    if session_count > 10:
        issues.append({
            "key": "session_fragmentation",
            "label": "会话碎片化",
            "severity": SEVERITY_WARN,
            "status": "high",
            "current": session_count,
            "advice": f"今天已产生 {session_count} 个会话片段 → 压缩太频繁。提高 maxActiveTranscriptBytes 可减少碎片。",
        })
    # 单文件过小就触发压缩
    if largest_mb > 0 and largest_mb < 1.0:
        issues.append({
            "key": "too_small_transcript",
            "label": "转录文件偏小",
            "severity": SEVERITY_WARN,
            "status": "small",
            "current": f"{largest_mb:.1f}MB",
            "advice": f"最大转录文件仅 {largest_mb:.1f}MB 就触发压缩 → maxActiveTranscriptBytes 过低。建议 2-3MB。",
        })
    return issues


def compaction_diagnose() -> dict[str, Any]:
    """诊断 OpenClaw 压缩配置，返回完整诊断报告。"""
    cc = _get_compaction_config()
    ctx_window = _get_context_window()

    if not cc:
        return {
            "diagnosedAt": _now_iso(),
            "status": "no_config",
            "summary": "未找到 compaction 配置段（agents.defaults.compaction 可能为空）",
            "openclawJsonPath": str(_OPENCLAW_JSON),
            "contextWindow": ctx_window,
            "issues": [],
            "advice": [],
            "actionable": False,
        }

    issues = []
    advice = []
    has_warn = False

    # 1. 检查 maxActiveTranscriptBytes
    matb = cc.get("maxActiveTranscriptBytes")
    r = _check_value("maxActiveTranscriptBytes", matb, ctx_window)
    if r["status"] != "ok":
        issues.append(r)
        advice.append(r["advice"])
        has_warn = True
    else:
        issues.append(r)

    # 2. 检查 keepRecentTokens
    krt = cc.get("keepRecentTokens")
    r = _check_value("keepRecentTokens", krt, ctx_window)
    if r["status"] != "ok":
        issues.append(r)
        advice.append(r["advice"])
        has_warn = True
    else:
        issues.append(r)

    # 3. 检查 reserveTokens
    rt = cc.get("reserveTokens")
    if rt is not None:
        r = _check_value("reserveTokens", rt, ctx_window)
        if r["status"] != "ok":
            issues.append(r)
            advice.append(r["advice"])
            has_warn = True
        else:
            issues.append(r)

    # 4. 检查 memoryFlush
    mf = cc.get("memoryFlush", {})
    if not mf or not mf.get("enabled"):
        alert = _MISSING_ALERTS["memoryFlush"]
        issues.append({
            "key": "memoryFlush",
            "label": "Memory Flush（压缩前记忆写入）",
            "severity": alert["severity"],
            "status": "missing",
            "advice": alert["fix"],
        })
        advice.append(alert["fix"])
        has_warn = True
    else:
        # memoryFlush 已启用，检查 softThresholdTokens
        stt = mf.get("softThresholdTokens")
        r = _check_value("softThresholdTokens", stt, ctx_window)
        if r["status"] != "ok":
            issues.append(r)
            advice.append(r["advice"])
            has_warn = True
        else:
            issues.append({**r, "key": "memoryFlush.softThresholdTokens"})

    # 5. 会话文件统计
    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    session_count = 0
    largest_mb = 0.0
    if sessions_dir.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        for f in sessions_dir.glob(f"{today}*.jsonl"):
            session_count += 1
            mb = f.stat().st_size / (1024 * 1024)
            if mb > largest_mb:
                largest_mb = mb
    stat_issues = _check_stat(session_count, largest_mb, ctx_window)
    issues.extend(stat_issues)
    for si in stat_issues:
        advice.append(si["advice"])
        has_warn = True

    # 6. 汇总当前配置
    current_config = {}
    for k in ("mode", "truncateAfterCompaction", "notifyUser",
              "maxActiveTranscriptBytes", "keepRecentTokens", "reserveTokens"):
        if k in cc:
            current_config[k] = cc[k]
    if "memoryFlush" in cc:
        mf_copy = dict(cc["memoryFlush"])
        # 脱敏 prompt 内容
        if "prompt" in mf_copy and len(mf_copy["prompt"]) > 80:
            mf_copy["prompt"] = mf_copy["prompt"][:80] + "…"
        current_config["memoryFlush"] = mf_copy

    return {
        "diagnosedAt": _now_iso(),
        "status": "warn" if has_warn else "ok",
        "summary": (
            f"发现 {sum(1 for i in issues if i['severity'] != 'ok')} 个优化点"
            if has_warn else "所有压缩配置在舒适范围内 ✅"
        ),
        "openclawJsonPath": str(_OPENCLAW_JSON),
        "contextWindow": ctx_window,
        "todaySessionCount": session_count,
        "largestTranscriptMB": round(largest_mb, 1),
        "currentConfig": current_config,
        "issues": issues,
        "advice": advice,
        "actionable": has_warn,
    }


def compaction_apply(auto_confirm: bool = False) -> dict[str, Any]:
    """根据诊断结果自动调优 OpenClaw 压缩配置。
    auto_confirm=False → 只生成建议不写入
    auto_confirm=True → 自动应用更改
    """
    diag = compaction_diagnose()

    if not diag["actionable"]:
        return {
            "appliedAt": _now_iso(),
            "status": "nothing_to_do",
            "summary": "压缩配置已在舒适范围，无需修改",
            "changes": [],
            "diagnose": diag,
        }

    cfg = _load_openclaw_json()
    if not cfg:
        return {
            "appliedAt": _now_iso(),
            "status": "error",
            "summary": "无法读取 openclaw.json",
            "changes": [],
            "diagnose": diag,
        }

    # 确保路径存在
    compact = cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("compaction", {})

    changes = []

    # 遍历 issues，对超出范围的自动修正
    for issue in diag["issues"]:
        key = issue.get("key", "")
        status = issue.get("status", "")

        if key == "maxActiveTranscriptBytes":
            if status in ("too_low", "too_high"):
                compact["maxActiveTranscriptBytes"] = _COMFORT_ZONES["maxActiveTranscriptBytes"]["comfort"]
                changes.append({
                    "key": key,
                    "from": issue["current"],
                    "to": compact["maxActiveTranscriptBytes"],
                    "reason": issue["advice"],
                })

        elif key == "keepRecentTokens":
            if status in ("too_low", "too_high"):
                compact["keepRecentTokens"] = _COMFORT_ZONES["keepRecentTokens"]["comfort"]
                changes.append({
                    "key": key,
                    "from": issue["current"],
                    "to": compact["keepRecentTokens"],
                    "reason": issue["advice"],
                })

        elif key == "reserveTokens":
            if status in ("too_low", "too_high"):
                compact["reserveTokens"] = _COMFORT_ZONES["reserveTokens"]["comfort"]
                changes.append({
                    "key": key,
                    "from": issue["current"],
                    "to": compact["reserveTokens"],
                    "reason": issue["advice"],
                })

        elif key == "memoryFlush" and status == "missing":
            compact["memoryFlush"] = _MISSING_ALERTS["memoryFlush"]["default_value"]
            changes.append({
                "key": key,
                "from": None,
                "to": "启用（softThresholdTokens=32000, 含自定义 prompt）",
                "reason": _MISSING_ALERTS["memoryFlush"]["fix"],
            })

    if not changes:
        return {
            "appliedAt": _now_iso(),
            "status": "nothing_to_do",
            "summary": "无需要修改的配置项",
            "changes": [],
            "diagnose": diag,
        }

    if auto_confirm:
        # 备份
        bak = Path(str(_OPENCLAW_JSON) + ".bak." + datetime.now().strftime("%Y%m%d"))
        shutil.copy2(_OPENCLAW_JSON, bak)

        # 写入
        with open(_OPENCLAW_JSON, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

        return {
            "appliedAt": _now_iso(),
            "status": "applied",
            "summary": f"已应用 {len(changes)} 项压缩配置优化（备份 {bak.name}）",
            "backupPath": str(bak),
            "changes": changes,
            "diagnose": diag,
        }
    else:
        return {
            "appliedAt": _now_iso(),
            "status": "dry_run",
            "summary": f"预览模式 — 将修改 {len(changes)} 项配置，未实际写入",
            "changes": changes,
            "diagnose": diag,
        }


def print_diagnose(diag: dict[str, Any]) -> None:
    """人性化打印诊断报告。"""
    print("\n" + "=" * 64)
    print("  📊 Mark42 压缩配置诊断")
    print("=" * 64)
    print(f"  上下文窗口: {diag['contextWindow']//1000}K")
    print(f"  今日会话片段: {diag['todaySessionCount']} 个")
    print(f"  最大转录文件: {diag['largestTranscriptMB']}MB")
    print(f"  配置文件: {diag['openclawJsonPath']}\n")

    if diag["status"] == "ok":
        print("  ✅ 所有压缩配置在舒适范围内\n")
        return

    print(f"  ⚠️  {diag['summary']}\n")

    for issue in diag["issues"]:
        sev = issue["severity"]
        icon = {"ok": "✅", "warn": "⚠️", "critical": "🔴"}.get(sev, "ℹ️")
        label = issue.get("label", issue.get("key", "?"))
        cur = issue.get("current_human", issue.get("current", "?"))
        comfort = issue.get("comfort_human", "")
        cs = issue.get("status", "")

        if cs == "missing":
            print(f"  {icon} {label}")
            print(f"     状态: 未启用")
            print(f"     建议: {issue.get('advice', '')}")
        elif cs == "ok":
            print(f"  {icon} {label} = {cur} (舒适范围 {issue.get('range', '')})")
        else:
            print(f"  {icon} {label} = {cur}")
            print(f"     舒适值: {comfort} (范围 {issue.get('range', '')})")
            print(f"     建议: {issue.get('advice', '')}")
        print()

    if diag["advice"]:
        print("  ── 优化建议汇总 ──")
        for i, a in enumerate(diag["advice"], 1):
            print(f"  {i}. {a}")
        print()

    print("=" * 64)


def print_apply_result(result: dict[str, Any]) -> None:
    """人性化打印 apply 结果。"""
    print("\n" + "=" * 64)
    status = result["status"]
    if status == "nothing_to_do":
        print("  ✅ 无需修改，配置已在舒适范围")
    elif status == "dry_run":
        print("  🔍 预览模式 — 以下是将要修改的内容：\n")
        for ch in result.get("changes", []):
            print(f"  📝 {ch['key']}")
            print(f"     {ch.get('from', '?')} → {ch.get('to', '?')}")
            print(f"     原因: {ch.get('reason', '')}\n")
        print(f"  共 {len(result['changes'])} 项修改，未实际写入。")
        print(f"  执行 --apply 以应用更改。")
    elif status == "applied":
        print("  ✅ 已应用压缩配置优化\n")
        for ch in result.get("changes", []):
            print(f"  ✅ {ch['key']}")
            print(f"     {ch.get('from', '?')} → {ch.get('to', '?')}\n")
        print(f"  备份: {result.get('backupPath', '?')}")
        print(f"  重启 Gateway 后生效: openclaw gateway restart")
    elif status == "error":
        print(f"  ❌ 错误: {result.get('summary', '')}")
    else:
        print(f"  ℹ️  {result.get('summary', '')}")
    print("=" * 64 + "\n")
