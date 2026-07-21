"""Mark42 压缩诊断与自动调优模块。
检测 OpenClaw 内置压缩配置，诊断问题，生成舒适合理的优化建议并可选自动应用。

v2.0 (2026-06-16): 升级至病因层——令牌感知、双层阈值、摘要探针、分身隔离、降解检测。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONTEXT_WINDOW
from .log_setup import get_logger
from .utils import _now_iso

logger = get_logger(__name__)

# ── 常量 ──────────────────────────────────────────────

# 默认路径
_OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"

# 舒适范围定义（基于 128K+ 上下文窗口模型的实践数据）
_COMFORT_ZONES = {
    # 键: (最小值, 舒适值, 最大值, 单位, 说明)
    "maxActiveTranscriptBytes": {
        "min": 1_000_000,  # ~1MB
        "comfort": 3_000_000,  # ~3MB
        "max": 10_000_000,  # ~10MB
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

# ── v2.0 新增常量：令牌感知 / 双层阈值 / 探针 ──────────

# 默认 session 目录
_SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"

# 双层阈值 — memoryFlush.softThresholdTokens 应为主阈值的 50% 左右 (Hermes 风格)
_DUAL_THRESHOLD_IDEAL_RATIO = 0.50
_DUAL_THRESHOLD_WARN_GAP = 0.30  # 差距 < 30% → 可能同时触发

# 摘要质量探针问题模板 (Factory.ai 风格 4 类)
_PROBE_TEMPLATES = {
    "recall": "请回顾：在最近的压缩之前，最关键的一条技术决策是什么？请具体说明。",
    "artifact": "请列出最近操作中涉及的所有文件路径和各自的修改状态。",
    "continuation": "当前任务的下一步应该做什么？请给出具体行动计划。",
    "decision": "最近一次讨论中关于配置/方案的选择结论是什么？是否已执行？",
}

# 降解检测阈值
_DRIFT_WINDOW = 3  # 检查最近 N 次压缩
_DRIFT_DROP_RATIO = 0.30  # 得分下降超过此比例触发告警

# 分身隔离建议触发阈值
_ISOLATION_SESSION_THRESHOLD = 12  # 今日片段 > 此数 → 建议拆分
_ISOLATION_HIGH_TOKEN_KB = 80  # 单 session > 此 token 数 (K) → 建议拆分


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
                    for _mname, mcfg in mods.items():
                        if isinstance(mcfg, dict) and mcfg.get("contextWindow"):
                            return mcfg["contextWindow"]
    return DEFAULT_CONTEXT_WINDOW


def _format_bytes(b: int) -> str:
    """人性化字节显示。"""
    if b >= 1_000_000:
        return f"{b / 1_000_000:.1f}MB"
    if b >= 1_000:
        return f"{b / 1_000:.0f}KB"
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
            "range": f"{_format_bytes(cmin) if zone['unit'] == 'bytes' else cmin} ~ {_format_bytes(cmax) if zone['unit'] == 'bytes' else cmax}",
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
            "range": f"{_format_bytes(cmin) if zone['unit'] == 'bytes' else cmin} ~ {_format_bytes(cmax) if zone['unit'] == 'bytes' else cmax}",
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
        "range": f"{_format_bytes(cmin) if zone['unit'] == 'bytes' else cmin} ~ {_format_bytes(cmax) if zone['unit'] == 'bytes' else cmax}",
    }


def _check_stat(session_count: int, largest_mb: float, ctx_window: int) -> list[dict[str, Any]]:
    """检测会话碎片化程度。"""
    issues = []
    # 碎片化检测：短时间内大量 session 文件
    if session_count > 10:
        issues.append(
            {
                "key": "session_fragmentation",
                "label": "会话碎片化",
                "severity": SEVERITY_WARN,
                "status": "high",
                "current": session_count,
                "advice": f"今天已产生 {session_count} 个会话片段 → 压缩太频繁。提高 maxActiveTranscriptBytes 可减少碎片。",
            }
        )
    # 单文件过小就触发压缩
    if largest_mb > 0 and largest_mb < 1.0:
        issues.append(
            {
                "key": "too_small_transcript",
                "label": "转录文件偏小",
                "severity": SEVERITY_WARN,
                "status": "small",
                "current": f"{largest_mb:.1f}MB",
                "advice": f"最大转录文件仅 {largest_mb:.1f}MB 就触发压缩 → maxActiveTranscriptBytes 过低。建议 2-3MB。",
            }
        )
    return issues


# ── v2.0 新增检测函数 ───────────────────────────────────


def _token_aware_check(cc: dict) -> dict[str, Any]:
    """令牌感知检测：从 session jsonl 读取实际 token 消耗，
    对比文件大小阈值与真实 token 占用是否合理。

    返回 token 感知诊断结果，包含实际 token 消耗 vs 配置阈值的对比。
    """
    result = {
        "key": "token_awareness",
        "label": "令牌感知诊断",
        "status": "ok",
        "severity": SEVERITY_OK,
        "maxTokensSeen": 0,
        "avgTokensPerTurn": 0,
        "estimatedContextPercent": 0,
        "advice": None,
    }

    if not _SESSIONS_DIR.exists():
        result["status"] = "no_data"
        result["advice"] = "无法读取 session 数据，跳过 token 感知检测。"
        return result

    # 收集今天所有 session 的 token 数据
    today = datetime.now().strftime("%Y-%m-%d")
    all_tokens = []  # 每个 compaction 点的 tokensBefore
    turns_per_session = []  # 每 session 的回合数
    largest_token_sum = 0

    for f in sorted(_SESSIONS_DIR.glob(f"{today}*.jsonl")):
        try:
            turn_count = 0
            session_tokens = 0
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # 每个 assistant/compaction/summary 行都有 usage
                    msg = obj.get("message", {})
                    if isinstance(msg, dict):
                        usage = msg.get("usage", {})
                        if isinstance(usage, dict) and "totalTokens" in usage:
                            all_tokens.append(usage["totalTokens"])
                            session_tokens = max(session_tokens, usage["totalTokens"])
                    # compaction 事件的 tokensBefore
                    tb = obj.get("tokensBefore")
                    if isinstance(tb, (int, float)) and tb > 0:
                        all_tokens.append(int(tb))
                    turn_count += 1
            if turn_count > 0:
                turns_per_session.append(turn_count)
                largest_token_sum = max(largest_token_sum, session_tokens)
        except OSError:
            continue

    if not all_tokens:
        result["status"] = "no_data"
        result["advice"] = "今天暂无 session token 数据。"
        return result

    max_tokens = max(all_tokens)
    # 用 bytes 阈值估算等效 token：DeepSeek/Claude 约 3-4 chars/token，JSONL 约 4 chars/token
    matb = cc.get("maxActiveTranscriptBytes", 3_000_000)
    estimated_byte_equivalent_tokens = matb // 4  # 粗略估计

    result["maxTokensSeen"] = max_tokens
    result["avgTokensPerTurn"] = round(sum(turns_per_session) / max(len(turns_per_session), 1), 1)
    result["totalSessionsScanned"] = len(turns_per_session)
    result["estimatedByteEquivalentTokens"] = estimated_byte_equivalent_tokens

    ctx = DEFAULT_CONTEXT_WINDOW
    pct = (max_tokens / ctx * 100) if ctx else 0
    result["estimatedContextPercent"] = round(pct, 1)

    # 判断：文件大小阈值 vs 实际 token 占比是否匹配
    if estimated_byte_equivalent_tokens < max_tokens * 0.5:
        # 文件大小阈值低估了 token 消耗 → 延迟压缩
        result["status"] = "mismatch"
        result["severity"] = SEVERITY_WARN
        result["advice"] = (
            f"maxActiveTranscriptBytes={_format_bytes(matb)} 估计等效 ~{estimated_byte_equivalent_tokens} tokens，"
            f"但实际已达到 {max_tokens} tokens ({pct:.0f}% 窗口)。"
            f"文件大小阈值可能低估了 token 消耗，建议降低至 {_format_bytes(int(max_tokens * 3.5))} 左右以提前触发压缩。"
        )
    elif max_tokens > ctx * 0.85:
        result["status"] = "near_limit"
        result["severity"] = SEVERITY_WARN
        result["advice"] = (
            f"实际 token 已达 {max_tokens} ({pct:.0f}%)，接近 {ctx // 1000}K 窗口上限。"
            f"建议检查压缩是否及时触发，或降低 maxActiveTranscriptBytes。"
        )
    else:
        result["status"] = "ok"

    return result


def _dual_threshold_check(cc: dict, ctx_window: int) -> dict[str, Any] | None:
    """双层阈值检查：主阈值 (maxActiveTranscriptBytes) 与
    memoryFlush.softThresholdTokens 的偏移是否合理。

    Hermes 风格：主阈值 50% 窗口 + 安全网 85% 窗口，避免同时触发。
    """
    mf = cc.get("memoryFlush", {})
    if not mf or not mf.get("enabled"):
        return None  # memoryFlush 未启用，不需要检查

    matb = cc.get("maxActiveTranscriptBytes")
    stt = mf.get("softThresholdTokens")
    if matb is None or stt is None:
        return None

    # 把 maxActiveTranscriptBytes 转为等效 token
    matb_tokens = matb // 4
    gate_tokens = stt

    ratio = gate_tokens / max(matb_tokens, 1)
    gap = abs(matb_tokens - gate_tokens) / max(matb_tokens, 1)

    result = {
        "key": "dual_threshold",
        "label": "双层阈值偏移",
        "mainTokensEstimate": matb_tokens,
        "gateTokens": gate_tokens,
        "ratio": round(ratio, 2),
        "gapPercent": round(gap * 100),
    }

    # OpenClaw 的 maxActiveTranscriptBytes 是文件大小（bytes），softThresholdTokens 是 token 数
    # 异构单位不能简单比较比例。memoryFlush 应在压缩前优先触发写记忆，设计合理。
    result["status"] = "heterogeneous"
    result["severity"] = SEVERITY_OK
    result["advice"] = (
        f"主阈值是文件大小（{_format_bytes(matb)} ≈ ~{matb_tokens} tokens 等效），"
        f"memoryFlush 是 token 阈值（{gate_tokens} tokens）。"
        f"两者单位不同 — memoryFlush 应在压缩前优先触发写记忆，设计合理。"
    )

    return result


def _probe_quality_check(cc: dict) -> dict[str, Any] | None:
    """摘要质量探针：检测最近一次压缩后，
    用标准化问题评估关键信息留存率 (Factory.ai 风格)。

    注意：此函数只在能够访问 LLM 时才有意义（需要 `--probe` 模式），
    默认只返回「探针就绪」状态。
    """
    # 检查是否存在 compaction 事件可分析
    today = datetime.now().strftime("%Y-%m-%d")
    compaction_events = 0
    latest_compaction = None

    if _SESSIONS_DIR.exists():
        for f in sorted(_SESSIONS_DIR.glob(f"{today}*.jsonl"), reverse=True):
            try:
                with open(f) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if obj.get("type") in ("compaction", "compression") or "tokensBefore" in obj:
                            compaction_events += 1
                            if latest_compaction is None:
                                latest_compaction = {
                                    "sessionFile": f.name,
                                    "tokensBefore": obj.get("tokensBefore", 0),
                                    "details": obj.get("details", ""),
                                    "fromHook": obj.get("fromHook", False),
                                }
            except OSError:
                continue
            if latest_compaction:
                break

    result = {
        "key": "probe_quality",
        "label": "摘要质量探针",
        "status": "ready" if compaction_events > 0 else "no_compaction",
        "severity": SEVERITY_OK,
        "compactionEventsToday": compaction_events,
        "latestCompaction": latest_compaction,
        "probeQuestions": _PROBE_TEMPLATES,
        "advice": (
            f"今日 {compaction_events} 次压缩。运行 --probe 模式可自动评估每次压缩后的关键信息留存率。"
            if compaction_events > 0
            else "今日无压缩事件，无需探针评估。"
        ),
    }
    return result


def _isolation_check(session_count: int, token_data: dict) -> list[dict[str, Any]]:
    """分身隔离建议：当碎片化或 token 消耗超阈值时，
    建议将高负载子任务拆分到独立子 Agent (Anthropic 多 Agent 研究员策略)。
    """
    issues = []

    # 碎片化触发
    if session_count > _ISOLATION_SESSION_THRESHOLD:
        issues.append(
            {
                "key": "isolation_fragmentation",
                "label": "分身隔离建议（碎片化）",
                "severity": SEVERITY_WARN,
                "status": "high",
                "current": session_count,
                "threshold": _ISOLATION_SESSION_THRESHOLD,
                "advice": (
                    f"今日已产生 {session_count} 个会话片段（> {_ISOLATION_SESSION_THRESHOLD}）。"
                    f"与其单纯提高 maxActiveTranscriptBytes（可能增大单次压缩压力），"
                    f"不如将高 token 消耗子任务拆分到独立子 Agent。"
                    f"使用 sessions_spawn(mode='run', context='isolated') 即可。"
                ),
            }
        )

    # token 消耗触发
    max_tokens = token_data.get("maxTokensSeen", 0)
    if max_tokens > _ISOLATION_HIGH_TOKEN_KB * 1000:
        issues.append(
            {
                "key": "isolation_token_heavy",
                "label": "分身隔离建议（token 密集）",
                "severity": SEVERITY_WARN,
                "status": "heavy",
                "current": f"{max_tokens // 1000}K tokens",
                "threshold": f"{_ISOLATION_HIGH_TOKEN_KB}K tokens",
                "advice": (
                    f"单 session 消耗 {max_tokens // 1000}K tokens（> {_ISOLATION_HIGH_TOKEN_KB}K）。"
                    f"大量上下文消耗意味着任务复杂度高 → 将调研/编码/测试各自分到独立子 Agent，"
                    f"每个 Agent 保持窄上下文（Anthropic 研究：隔离上下文优于单 Agent 长上下文）。"
                ),
            }
        )

    return issues


def _drift_check(cc: dict) -> dict[str, Any] | None:
    """上下文降解检测：检测连续压缩后 tokensBefore 的变化趋势。
    如果连续 N 次压缩后 tokensBefore 没有明显下降（说明压缩无效），
    或者急剧下降（可能丢失了关键信息），触发告警。

    这是轻量级检测——不需要 LLM，只靠 token 计数趋势分析。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    token_befores = []  # 收集所有 compaction 的 tokensBefore

    if _SESSIONS_DIR.exists():
        for f in sorted(_SESSIONS_DIR.glob(f"{today}*.jsonl")):
            try:
                with open(f) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        tb = obj.get("tokensBefore")
                        if isinstance(tb, (int, float)) and tb > 0:  # 过滤无效 0 值
                            token_befores.append(int(tb))
            except OSError:
                continue

    if len(token_befores) < 2:
        return {
            "key": "drift_detection",
            "label": "上下文降解检测",
            "status": "insufficient_data",
            "severity": SEVERITY_OK,
            "compactionCount": len(token_befores),
            "advice": f"今日仅 {len(token_befores)} 次压缩，数据不足以分析降解趋势。",
        }

    # 分析最近 N 次压缩的趋势
    recent = token_befores[-min(_DRIFT_WINDOW, len(token_befores)) :]
    first_val = recent[0]
    last_val = recent[-1]

    drop_ratio = (first_val - last_val) / max(first_val, 1)

    result = {
        "key": "drift_detection",
        "label": "上下文降解检测",
        "compactionCount": len(token_befores),
        "recentTokensBefore": recent,
        "firstTokensBefore": first_val,
        "lastTokensBefore": last_val,
        "dropRatio": round(drop_ratio, 2),
    }

    if drop_ratio > _DRIFT_DROP_RATIO:
        result["status"] = "degradation_suspected"
        result["severity"] = SEVERITY_WARN
        result["advice"] = (
            f"最近 {len(recent)} 次压缩 tokensBefore 从 {first_val} 降至 {last_val} "
            f"（下降 {int(drop_ratio * 100)}%）。如果每次压缩的摘要都在丢失信息，"
            f"会导致上下文持续降解 → 建议运行 --probe 模式评估摘要质量。"
        )
    elif drop_ratio < 0.05 and len(recent) >= 3:
        # 几乎不变 → 压缩可能无效
        result["status"] = "compression_stalled"
        result["severity"] = SEVERITY_WARN
        result["advice"] = (
            f"最近 {len(recent)} 次压缩 tokensBefore 稳定在 ~{last_val}，"
            f"压缩后 token 数几乎没有下降。可能 compression 未生效或阈值设置过高。"
        )
    else:
        result["status"] = "healthy"
        result["severity"] = SEVERITY_OK
        result["advice"] = f"压缩趋势健康：tokensBefore 从 {first_val} 到 {last_val}，稳定下降。"

    return result


def compaction_diagnose(token_aware: bool = False, probe: bool = False) -> dict[str, Any]:
    """诊断 OpenClaw 压缩配置，返回完整诊断报告。

    Args:
        token_aware: 启用令牌感知检测（从 session jsonl 读取实际 token 消耗）
        probe: 启用摘要质量探针（检测压缩后关键信息留存率）
    """
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
        issues.append(
            {
                "key": "memoryFlush",
                "label": "Memory Flush（压缩前记忆写入）",
                "severity": alert["severity"],
                "status": "missing",
                "advice": alert["fix"],
            }
        )
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

    # ── v2.0 新增检测 ────────────────────────────────────

    # 6. 令牌感知检测
    token_data = {"maxTokensSeen": 0, "avgTokensPerTurn": 0}
    if token_aware:
        ta = _token_aware_check(cc)
        issues.append(ta)
        if ta["severity"] != SEVERITY_OK and ta.get("advice"):
            advice.append(ta["advice"])
            has_warn = True
        token_data = ta

    # 7. 双层阈值检查
    dt = _dual_threshold_check(cc, ctx_window)
    if dt:
        issues.append(dt)
        if dt["severity"] != SEVERITY_OK:
            advice.append(dt["advice"])
            has_warn = True

    # 8. 摘要质量探针
    if probe:
        pq = _probe_quality_check(cc)
        if pq:
            issues.append(pq)
            if pq.get("advice"):
                advice.append(pq["advice"])

    # 9. 分身隔离建议
    iso = _isolation_check(session_count, token_data)
    if iso:
        issues.extend(iso)
        for i in iso:
            advice.append(i["advice"])
            has_warn = True

    # 10. 上下文降解检测
    dr = _drift_check(cc)
    if dr:
        issues.append(dr)
        if dr["severity"] != SEVERITY_OK:
            advice.append(dr["advice"])
            has_warn = True

    # ── 汇总当前配置 ──────────────────────────────────────

    # 11. 汇总当前配置
    current_config = {}
    for k in (
        "mode",
        "truncateAfterCompaction",
        "notifyUser",
        "maxActiveTranscriptBytes",
        "keepRecentTokens",
        "reserveTokens",
    ):
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
            if has_warn
            else "所有压缩配置在舒适范围内 ✅"
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
                changes.append(
                    {
                        "key": key,
                        "from": issue["current"],
                        "to": compact["maxActiveTranscriptBytes"],
                        "reason": issue["advice"],
                    }
                )

        elif key == "keepRecentTokens":
            if status in ("too_low", "too_high"):
                compact["keepRecentTokens"] = _COMFORT_ZONES["keepRecentTokens"]["comfort"]
                changes.append(
                    {
                        "key": key,
                        "from": issue["current"],
                        "to": compact["keepRecentTokens"],
                        "reason": issue["advice"],
                    }
                )

        elif key == "reserveTokens":
            if status in ("too_low", "too_high"):
                compact["reserveTokens"] = _COMFORT_ZONES["reserveTokens"]["comfort"]
                changes.append(
                    {
                        "key": key,
                        "from": issue["current"],
                        "to": compact["reserveTokens"],
                        "reason": issue["advice"],
                    }
                )

        elif key == "memoryFlush" and status == "missing":
            compact["memoryFlush"] = _MISSING_ALERTS["memoryFlush"]["default_value"]
            changes.append(
                {
                    "key": key,
                    "from": None,
                    "to": "启用（softThresholdTokens=32000, 含自定义 prompt）",
                    "reason": _MISSING_ALERTS["memoryFlush"]["fix"],
                }
            )

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
    """人性化打印诊断报告 (v2.0 支持令牌感知/探针/隔离/降解)。"""
    logger.info("\n" + "=" * 64)
    logger.info("  📊 Mark42 压缩配置诊断 v2.0")
    logger.info("=" * 64)
    logger.info(f"  上下文窗口: {diag['contextWindow'] // 1000}K")
    logger.info(f"  今日会话片段: {diag.get('todaySessionCount', '?')} 个")
    logger.info(f"  最大转录文件: {diag.get('largestTranscriptMB', '?')}MB")
    logger.info(f"  配置文件: {diag['openclawJsonPath']}\n")

    if diag["status"] == "ok" and not any(
        i.get("key", "")
        in (
            "token_awareness",
            "dual_threshold",
            "probe_quality",
            "isolation_fragmentation",
            "isolation_token_heavy",
            "drift_detection",
        )
        and i.get("severity") != "ok"
        for i in diag.get("issues", [])
    ):
        logger.info("  ✅ 所有压缩配置在舒适范围内\n")
        return

    logger.warning(f"  ⚠️  {diag['summary']}\n")

    for issue in diag["issues"]:
        sev = issue.get("severity", "ok")
        icon = {"ok": "✅", "warn": "⚠️", "critical": "🔴", "info": "ℹ️"}.get(sev, "ℹ️")
        label = issue.get("label", issue.get("key", "?"))
        cur = issue.get("current_human", issue.get("current", "?"))
        comfort = issue.get("comfort_human", "")
        cs = issue.get("status", "")
        key = issue.get("key", "")

        # ── v2.0 新类型特殊处理 ──
        if key == "token_awareness":
            logger.info(f"  {icon} {label}")
            if cs in ("ok", "no_data"):
                logger.info(f"     状态: {cs}")
            else:
                logger.warning(
                    f"     实际最大 token: {issue.get('maxTokensSeen', '?')} ({issue.get('estimatedContextPercent', '?')}% 窗口)"
                )
                logger.warning(f"     文件阈值等效: ~{issue.get('estimatedByteEquivalentTokens', '?')} tokens")
            if issue.get("advice"):
                logger.warning(f"     建议: {issue['advice']}")
            logger.info("")
            continue

        if key == "dual_threshold":
            logger.info(f"  {icon} {label}")
            logger.info(f"     主阈值等效: ~{issue.get('mainTokensEstimate', '?')} tokens")
            logger.info(f"     memoryFlush 安全网: {issue.get('gateTokens', '?')} tokens")
            logger.info(f"     偏移比例: {issue.get('ratio', '?')} ({issue.get('gapPercent', '?')}% 差距)")
            if issue.get("advice"):
                logger.info(f"     建议: {issue['advice']}")
            logger.info("")
            continue

        if key == "probe_quality":
            logger.info(f"  {icon} {label}")
            logger.info(f"     今日压缩事件: {issue.get('compactionEventsToday', 0)} 次")
            if issue.get("latestCompaction"):
                lc = issue["latestCompaction"]
                logger.info(
                    f"     最近压缩: tokensBefore={lc.get('tokensBefore', '?')}, file={lc.get('sessionFile', '?')}"
                )
            if issue.get("advice"):
                logger.info(f"     {issue['advice']}")
            logger.info(
                f"     探针问题数: {len(issue.get('probeQuestions', {}))} 类 (recall/artifact/continuation/decision)"
            )
            logger.info("")
            continue

        if key in ("isolation_fragmentation", "isolation_token_heavy"):
            logger.warning(f"  {icon} {label}")
            logger.warning(f"     当前: {cur}")
            if issue.get("threshold"):
                logger.warning(f"     阈值: {issue['threshold']}")
            logger.warning(f"     建议: {issue.get('advice', '')}")
            logger.info("")
            continue

        if key == "drift_detection":
            logger.info(f"  {icon} {label}")
            if cs == "insufficient_data":
                logger.info(f"     状态: 数据不足（仅 {issue.get('compactionCount', 0)} 次压缩）")
            else:
                logger.warning(f"     压缩次数: {issue.get('compactionCount', '?')}")
                recent = issue.get("recentTokensBefore", [])
                if recent:
                    logger.warning(f"     最近 trend: {recent} (下降 {issue.get('dropRatio', 0) * 100:.0f}%)")
            if issue.get("advice"):
                logger.warning(f"     建议: {issue['advice']}")
            logger.info("")
            continue

        # ── 原有逻辑 ──
        if cs == "missing":
            logger.warning(f"  {icon} {label}")
            logger.warning("     状态: 未启用")
            logger.warning(f"     建议: {issue.get('advice', '')}")
        elif cs == "ok":
            logger.info(f"  {icon} {label} = {cur} (舒适范围 {issue.get('range', '')})")
        else:
            logger.warning(f"  {icon} {label} = {cur}")
            if comfort:
                logger.warning(f"     舒适值: {comfort} (范围 {issue.get('range', '')})")
            logger.warning(f"     建议: {issue.get('advice', '')}")
        logger.info("")

    if diag.get("advice"):
        logger.info("  ── 优化建议汇总 ──")
        for i, a in enumerate(diag["advice"], 1):
            logger.info(f"  {i}. {a}")
        logger.info("")

    logger.info("=" * 64)


def print_apply_result(result: dict[str, Any]) -> None:
    """人性化打印 apply 结果。"""
    logger.info("\n" + "=" * 64)
    status = result["status"]
    if status == "nothing_to_do":
        logger.info("  ✅ 无需修改，配置已在舒适范围")
    elif status == "dry_run":
        logger.info("  🔍 预览模式 — 以下是将要修改的内容：\n")
        for ch in result.get("changes", []):
            logger.info(f"  📝 {ch['key']}")
            logger.info(f"     {ch.get('from', '?')} → {ch.get('to', '?')}")
            logger.info(f"     原因: {ch.get('reason', '')}\n")
        logger.info(f"  共 {len(result['changes'])} 项修改，未实际写入。")
        logger.info("  执行 --apply 以应用更改。")
    elif status == "applied":
        logger.info("  ✅ 已应用压缩配置优化\n")
        for ch in result.get("changes", []):
            logger.info(f"  ✅ {ch['key']}")
            logger.info(f"     {ch.get('from', '?')} → {ch.get('to', '?')}\n")
        logger.info(f"  备份: {result.get('backupPath', '?')}")
        logger.info("  重启 Gateway 后生效: openclaw gateway restart")
    elif status == "error":
        logger.error(f"  ❌ 错误: {result.get('summary', '')}")
    else:
        logger.info(f"  ℹ️  {result.get('summary', '')}")
    logger.info("=" * 64 + "\n")
