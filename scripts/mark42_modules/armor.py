"""Mark42 模块A：上下文铠甲 Armor。
实时检测上下文健康 + LLM 驱动记忆索引 + 启发式回退 + 守护模式。
"""

import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import (
    ARMOR_STATE, BROKER_EVENTS, BYTES_PER_KTOKEN, CONFIG_PATH,
    DEFAULT_CONTEXT_WINDOW, THRESHOLD_ALERT, THRESHOLD_CRIT,
    THRESHOLD_WARN, WORKSPACE, XDG_STATE, resolve_model,
    # 阶段 1: 压缩算法常量 (2026-06-24)
    ALGO_SMARTCRUSH_ENABLED, ALGO_EXPERIMENT_MODE,
    ALGO_SMARTCRUSH_MIN_CONTENT_SIZE,
    # 阶段 1 Day 4: 调度器接入控制 (2026-06-24)
    ALGO_USE_SCHEDULER, ALGO_PII_ENABLED, ALGO_FAIL_SAFE,
)
from .utils import (
    _append_broker, _estimate_tokens_smart, _find_active_session,
    _get_context_window, _load_json, _now_iso, _now_ts, _save_json,
)

# 阶段 1 压缩算法 (2026-06-24 新增, 借鉴 Headroom)
# 设计: docs/design/mark42-压缩方案-阶段1实施计划-20260624.md
try:
    from .smart_crusher import smartcrush
    _COMPRESSION_AVAILABLE = True
except ImportError as e:
    _COMPRESSION_AVAILABLE = False
    _COMPRESSION_IMPORT_ERROR = str(e)

# 阶段 1 Day 4: 算法调度器 (2026-06-24)
# 设计: docs/design/mark42-压缩方案-阶段1实施计划-20260624.md
try:
    from .algo_scheduler import process as algo_scheduler_process, decide as algo_scheduler_decide
    _SCHEDULER_AVAILABLE = True
except ImportError as e:
    _SCHEDULER_AVAILABLE = False
    _SCHEDULER_IMPORT_ERROR = str(e)


def armor_check() -> dict[str, Any]:
    """检查上下文健康度。"""
    active = _find_active_session()
    now_str = _now_iso()
    if not active:
        return {
            "checkedAt": now_str,
            "host": os.uname().nodename,
            "status": "unknown",
            "severity": "ok",
            "summary": "未找到活跃会话",
            "usagePercent": 0,
            "estimatedTokens": 0,
            "contextWindow": _get_context_window(),
        }
    tokens_info = {}
    import subprocess as _sp
    du_result = _sp.run(["du", "-s", str(XDG_STATE / "openclaw" / "sessions")],
                        capture_output=True, text=True)
    sessions_kb = int(du_result.stdout.split()[0]) if du_result.stdout else 0
    tokens_info = {
        "sessionsDirKB": sessions_kb,
        "activeSession": active.name,
        "activeFileMB": round(active.stat().st_size / (1024 * 1024), 2),
    }
    est = {}
    try:
        # P1.1 修复: 按语言密度智能估算 token 数, 避免中文场景下 6× 高估
        # 原公式: size_bytes // BYTES_PER_KTOKEN * 1000 (以英文 / 代码为主)
        # 新公式: 扫描真实字符, 按 zh=1.5 en=0.25 other=0.1 token/char 估算
        # 环境变量:
        #   MARK42_TOKEN_ESTIMATE_MODE=simple (沿用原公式) | smart (默认, 推荐)
        est_mode = os.environ.get("MARK42_TOKEN_ESTIMATE_MODE", "smart").lower()
        if est_mode == "smart":
            est = _estimate_tokens_smart(active)
        else:
            est = {"estimatedTokens": int(active.stat().st_size // BYTES_PER_KTOKEN * 1000)}
    except OSError:
        est = {"estimatedTokens": 0}
    context_window = _get_context_window()
    usage_pct = round(est.get("estimatedTokens", 0) / context_window * 100, 1)
    severity = "ok"
    status = "ok"
    summary = f"上下文 {usage_pct}%，正常"
    if usage_pct >= THRESHOLD_CRIT:
        severity = "critical"
        status = "critical"
        summary = f"⚠️ 上下文 {usage_pct}% 达到危险等级"
    elif usage_pct >= THRESHOLD_ALERT:
        severity = "warn"
        status = "alert"
        summary = f"⚠️ 上下文 {usage_pct}% 偏高，建议压缩"
    elif usage_pct >= THRESHOLD_WARN:
        severity = "info"
        status = "warn"
        summary = f"💡 上下文 {usage_pct}%，关注中"
    result = {
        "checkedAt": now_str,
        "host": os.uname().nodename,
        "status": status,
        "severity": severity,
        "summary": summary,
        "usagePercent": usage_pct,
        "estimatedTokens": est.get("estimatedTokens", 0),
        "contextWindow": context_window,
        **tokens_info,
    }
    # P1.1 补丁: 智能估算模式下, 输出详细密度信息供 debug
    if est.get("method") == "smart":
        result["estimateDetail"] = {
            "method": "smart",
            "zhChars": est.get("zhChars", 0),
            "enChars": est.get("enChars", 0),
            "otherChars": est.get("otherChars", 0),
            "scannedMessages": est.get("scannedMessages", 0),
        }
    return result


def _read_session_tail(jsonl_path: Path, lines: int = 60) -> list[dict[str, Any]]:
    """读取 JSONL 会话文件尾部 N 行。兼容 OpenClaw 嵌套格式。"""
    messages = []
    try:
        with open(jsonl_path, "rb") as f:
            f.seek(0, 2)
            pos = f.tell()
            chunk = b""
            while pos > 0 and len(messages) < lines:
                step = min(16384, pos)
                pos -= step
                f.seek(pos)
                chunk = f.read(step) + chunk
                raw_lines = chunk.split(b"\n")
                chunk = raw_lines[0]
                for ln in raw_lines[1:]:
                    try:
                        obj = json.loads(ln.strip())
                        if not isinstance(obj, dict):
                            continue
                        # OpenClaw 嵌套格式: {"type":"message", "message":{"role":"user",...}}
                        inner = obj.get("message") if isinstance(obj.get("message"), dict) else obj
                        if isinstance(inner, dict) and "role" in inner:
                            messages.append(inner)
                    except (json.JSONDecodeError, ValueError):
                        continue
    except OSError:
        pass
    return messages[-lines:]


def _classify_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """启发式分类：preserved vs discarded。"""
    preserved = []
    discarded = []
    PRESERVE_KW = ["偏好", "设定", "规则", "模型", "配置", "记住", "重要",
                    "Mark42", "方案", "设计", "架构", "密码", "凭据", "API", "Key",
                    "部署", "系统", "升级", "安装", "补丁", "版本", "决策",
                    "访问", "账号", "IDENTITY", "SOUL", "MEMORY", "USER",
                    "语音回复", "图片生成", "视频下载", "快捷键"]
    DISCARD_KW = ["在吗", "还在", "嗯", "哦", "好的", "收到", "知道了", "明白",
                   "谢谢", "多谢", "NO_REPLY", "no_reply"]
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        raw_content = msg.get("content", "")
        # 处理 OpenClaw content 数组格式
        if isinstance(raw_content, list):
            text = " ".join(c.get("text", "") for c in raw_content if isinstance(c, dict))
        elif isinstance(raw_content, str):
            text = raw_content
        else:
            text = str(raw_content)
        if not text:
            continue
        entry = {"index": i, "role": role, "preview": text[:120]}
        if role == "user" or role == "assistant":
            if any(kw in text for kw in PRESERVE_KW):
                preserved.append(entry)
            elif len(text) < 10 and any(kw in text for kw in DISCARD_KW):
                discarded.append(entry)
            elif len(text) > 200:
                preserved.append(entry)
            else:
                discarded.append(entry)
        else:
            discarded.append(entry)
    return {"preserved": preserved[:20], "discarded": discarded[:10], "totalAnalyzed": len(messages)}


def _llm_analyze(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """调用 LLM API 对会话消息做智能分析。失败则返回 None。
    模型和参数统一从 Mark42 模型配置表读取。"""
    resolved = resolve_model("llmAnalyze")
    if not resolved:
        return None
    model_name = resolved["model"]
    api_key = resolved["apiKey"]
    base_url = resolved["baseUrl"]
    endpoint = resolved["endpoint"]
    timeout = resolved["timeout"]
    max_tokens = resolved["maxTokens"]
    temperature = resolved["temperature"]
    lines = []
    for msg in messages[-40:]:
        role = msg.get("role", "?")
        raw_content = msg.get("content", "")
        # 处理 OpenClaw content 数组格式: [{"type":"text","text":"..."}]
        if isinstance(raw_content, list):
            text = " ".join(c.get("text", "") for c in raw_content if isinstance(c, dict))
        elif isinstance(raw_content, str):
            text = raw_content
        else:
            text = str(raw_content)
        text = text[:200]
        lines.append(f"[{role}] {text}")
    convo_text = "\n".join(lines)[:8192]
    prompt = f"""分析以下 AI 助手与用户的对话记录片段。你的任务：
1. 提取需要**保留**的关键信息（用户身份、偏好设定、活跃项目、重要决策、任务状态）
2. 识别可以**丢弃**的内容（闲聊、已完成子任务、重复确认、简短应答）
3. 检测上下文退化类型（lost-in-middle / distraction / confusion / clash / 无）

对话记录（按时间顺序）：
{convo_text}

请返回纯 JSON（不要 markdown 代码块包裹）：
{{
  "preserved": {{
    "userIdentity": "用户身份描述",
    "preferences": ["偏好1", "偏好2"],
    "activeProjects": ["项目名称"],
    "recentDecisions": ["重要决策"],
    "taskState": {{"current": "当前任务", "progress": "进度描述"}}
  }},
  "discarded": {{"summary": "丢弃内容的一句话概括", "estimatedTokensSaved": 数字}},
  "degradationDetected": "类型或无",
  "suggestedAction": "/compact 或 monitor"
}}"""
    try:
        body = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            f"{base_url}{endpoint}",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("<think>"):
            end = content.find("</think>")
            if end > 0:
                content = content[end + 8:].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        result = json.loads(content)
        result["_llm_meta"] = {
            "model": data.get("model"),
            "tokens": data.get("usage", {}),
            "responseFormat": "json_object",
        }
        return result
    except Exception:
        return None


def armor_pre_compact_hook(session_messages: list[dict[str, Any]],
                            dry_run: bool = False) -> dict[str, Any]:
    """压缩前 hook: 对 session 尾部消息跑压缩算法。

    阶段 1 Day 1 (2026-06-24 上午): 只启用 SmartCrusher
    阶段 1 Day 4 (2026-06-24 下午): 默认走 algo_scheduler
        - 调度器提供：大小分层、PII 脱敏、压缩护栏、fail-safe
        - 可通过 MARK42_ALGO_USE_SCHEDULER=false 退回旧路径

    - 默认 disabled, 需 env MARK42_ALGO_SMARTCRUSH=true 或 config 启用
    - dry_run=True 永远不修改数据, 只报告能压缩多少
    - 失败静默 (返回 stats with error)
    """
    stats = {
        "enabled": False,
        "ran": False,
        "algorithm": None,
        "mode": None,               # "scheduler" | "direct" (Day 4)
        "filesProcessed": 0,
        "totalOriginalBytes": 0,
        "totalCrushedBytes": 0,
        "overallRatio": 0.0,
        "piiRedactions": 0,
        "decisionsByBucket": {},    # {"tiny": 0, "small": 0, ...}
        "fallbackCount": 0,
        "error": None,
    }

    # 1. 双重门: module 是否可用 + 配置是否启用 + 实验模式是否开启
    if not _COMPRESSION_AVAILABLE:
        return stats
    if not ALGO_SMARTCRUSH_ENABLED:
        return stats
    if not ALGO_EXPERIMENT_MODE:
        return stats

    # ── Day 4 路径选择 ──
    # MARK42_ALGO_USE_SCHEDULER=true (默认) 走 algo_scheduler.process()
    # 获得：大小分层 + PII 脱敏 + 压缩护栏 + fail-safe
    # false 走原始 SmartCrusher 直接压缩 (回退路径)
    use_scheduler = (
        ALGO_USE_SCHEDULER
        and _SCHEDULER_AVAILABLE
    )

    if use_scheduler:
        return _hook_via_scheduler(session_messages, stats, dry_run=dry_run)
    else:
        return _hook_direct_smartcrush(session_messages, stats, dry_run=dry_run)


def _hook_via_scheduler(session_messages: list[dict[str, Any]],
                         stats: dict[str, Any],
                         dry_run: bool = False) -> dict[str, Any]:
    """Day 4 调度器路径: PII 脱敏 + 大小分层 + 压缩护栏 + fail-safe。"""
    stats["enabled"] = True
    stats["mode"] = "scheduler"
    stats["algorithm"] = "algo_scheduler"

    if not _SCHEDULER_AVAILABLE:
        stats["error"] = (
            f"scheduler not available: {_SCHEDULER_IMPORT_ERROR}. "
            f"set MARK42_ALGO_USE_SCHEDULER=false to fallback."
        )
        if not ALGO_FAIL_SAFE:
            raise RuntimeError(stats["error"])
        return stats

    try:
        for msg in session_messages:
            # 只处理 message 类型 + content 为字符串
            if msg.get("type") != "message":
                continue
            content = msg.get("message", {}).get("content", "")
            if not isinstance(content, str):
                continue

            # 调度决策 (记录分布)
            decision = algo_scheduler_decide(content)
            bucket = decision.size_bucket
            stats["decisionsByBucket"][bucket] = (
                stats["decisionsByBucket"].get(bucket, 0) + 1
            )

            # dry_run 跳过实际处理, 只记录决策
            if dry_run:
                continue

            # 调度处理
            result = algo_scheduler_process(content)
            stats["filesProcessed"] += 1
            stats["totalOriginalBytes"] += len(content.encode('utf-8'))

            # PII 脱敏统计
            pii_stats = result.get("pii_stats")
            if pii_stats:
                stats["piiRedactions"] += pii_stats.get("total_redactions", 0)

            # 护栏回退记录
            if result.get("fallback_reason"):
                stats["fallbackCount"] += 1
                # fail-safe: 回退到原文
                final_content = content
            else:
                final_content = result.get("result", content)

            stats["totalCrushedBytes"] += len(final_content.encode('utf-8'))

        if stats["totalOriginalBytes"] > 0:
            stats["overallRatio"] = 1.0 - (
                stats["totalCrushedBytes"] / stats["totalOriginalBytes"]
            )
        stats["ran"] = True

        if stats["filesProcessed"] > 0:
            pii_info = f" | PII: {stats['piiRedactions']}" if stats["piiRedactions"] else ""
            fb_info = f" | 回退: {stats['fallbackCount']}" if stats["fallbackCount"] else ""
            print(
                f"🧪 算法调度器: {stats['filesProcessed']} 条 | "
                f"压缩率 {stats['overallRatio']*100:.1f}% | "
                f"桶分布 {stats['decisionsByBucket']}"
                f"{pii_info}{fb_info}"
            )

    except Exception as e:
        stats["error"] = f"scheduler failed: {e}"
        # fail-safe 路径: 记录尝试 (ran=True) 但不实际处理
        stats["ran"] = True
        if ALGO_FAIL_SAFE:
            print(f"⚠️ compression scheduler error (fail-safe 返回原文): {e}")
        else:
            raise

    return stats


def _hook_direct_smartcrush(session_messages: list[dict[str, Any]],
                             stats: dict[str, Any],
                             dry_run: bool = False) -> dict[str, Any]:
    """Day 1-3 原始路径: 直接调 SmartCrusher, 无 PII / 无护栏。"""
    stats["enabled"] = True
    stats["mode"] = "direct"
    stats["algorithm"] = "smartcrush"

    try:
        for msg in session_messages:
            if msg.get("type") != "message":
                continue
            content = msg.get("message", {}).get("content", "")
            if not isinstance(content, str):
                continue
            if len(content.encode('utf-8')) < ALGO_SMARTCRUSH_MIN_CONTENT_SIZE:
                continue

            crushed, cstats = smartcrush(content)
            stats["filesProcessed"] += 1
            stats["totalOriginalBytes"] += cstats.get("original_bytes", 0)
            stats["totalCrushedBytes"] += cstats.get("crushed_bytes", 0)

        if stats["totalOriginalBytes"] > 0:
            stats["overallRatio"] = 1.0 - (
                stats["totalCrushedBytes"] / stats["totalOriginalBytes"]
            )
        stats["ran"] = True

        if stats["filesProcessed"] > 0:
            print(
                f"🧪 SmartCrusher 直接路径: {stats['filesProcessed']} 条消息 | "
                f"压缩率 {stats['overallRatio']*100:.1f}% | "
                f"节省 {stats['totalOriginalBytes'] - stats['totalCrushedBytes']} bytes"
            )

    except Exception as e:
        stats["error"] = f"smartcrush failed: {e}"
        print(f"⚠️ compression hook error: {e}")

    return stats


def armor_compress(dry_run: bool = False) -> dict[str, Any]:
    """触发智能压缩 — LLM 优先，启发式回退。
    正常模式：usage < WARN 阈值时跳过。
    dry_run 模式：无论如何都执行分析但只预览不写入（用于测试）。
    """
    check = armor_check()
    usage = check.get("usagePercent", 0)
    if usage < THRESHOLD_WARN and not dry_run:
        return {"action": "skip", "reason": f"使用率 {usage}% 未达阈值 {THRESHOLD_WARN}%", "check": check}
    active = _find_active_session()
    session_messages = _read_session_tail(active) if active else []

    # 阶段 1: 压缩算法 hook (默认 disabled, 需 env 启用)
    algo_stats = armor_pre_compact_hook(session_messages, dry_run=dry_run)

    llm_result = _llm_analyze(session_messages) if session_messages else None
    if llm_result:
        index = {
            "generatedAt": _now_iso(),
            "preCompressUsage": usage,
            "modelGenerated": True,
            "analyzedMessages": min(len(session_messages), 40),
            "preserved": llm_result.get("preserved", {}),
            "discarded": llm_result.get("discarded", {}),
            "degradationDetected": llm_result.get("degradationDetected"),
            "strategyUsed": "llm-analyze",
            "recommendedAction": llm_result.get("suggestedAction", "monitor"),
            "llmMeta": llm_result.get("_llm_meta", {}),
            "algoStats": algo_stats,
        }
        print(f"🧠 LLM 分析完成 (model: {llm_result.get('_llm_meta', {}).get('model', '?')})")
    else:
        classification = _classify_messages(session_messages)
        preserved_items = classification.get("preserved", [])
        preserved_roles = {}
        for item in preserved_items:
            role = item.get("role", "unknown")
            preserved_roles.setdefault(role, []).append(item.get("preview", ""))
        discarded_items = classification.get("discarded", [])
        discarded_summary = [d.get("preview", "")[:80] for d in discarded_items[:5]]
        degradation = None
        if usage > 90:
            degradation = "lost-in-middle"
        elif classification.get("totalAnalyzed", 0) > 40:
            degradation = "distraction"
        index = {
            "generatedAt": _now_iso(),
            "preCompressUsage": usage,
            "modelGenerated": False,
            "analyzedMessages": classification.get("totalAnalyzed", 0),
            "preserved": {
                "userIdentity": "点点（袁文涛），1991-11-29，中文优先",
                "byRole": {role: previews[:5] for role, previews in preserved_roles.items()},
                "keyMessagesCount": len(preserved_items),
            },
            "discarded": {"samples": discarded_summary, "count": len(discarded_items)},
            "degradationDetected": degradation,
            "strategyUsed": "heuristic-classify",
            "recommendedAction": "/compact" if usage >= THRESHOLD_ALERT else "monitor",
            "algoStats": algo_stats,
        }
        print("⚠️ LLM 不可用，回退到启发式分析")
    index_path = ARMOR_STATE / "memory-index.json"
    actions_log = ARMOR_STATE / "actions.jsonl"
    history_dir = ARMOR_STATE / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    _append_broker("health", "armor.compress",
                   f"上下文压缩{'预览' if dry_run else ''}: {usage}%",
                   "warn" if usage >= THRESHOLD_WARN else "ok",
                   f"使用率 {usage}%，{'建议手动' if dry_run else '已生成'}记忆索引",
                   {"usagePercent": usage, "dryRun": dry_run})
    # ── C 项：标准化事件桥接 ──
    _append_broker("armor", "mark42.armor.compress.done",
                   f"铠甲压缩完成: {usage}% → {index.get('strategyUsed', '?')}",
                   "ok" if index.get('strategyUsed') == 'llm-analyze' else "warn",
                   f"策略: {index.get('strategyUsed', '?')} | "
                   f"保留: {len(index.get('preserved', {}).get('byRole', {}).get('user', [])) +
                            len(index.get('preserved', {}).get('byRole', {}).get('assistant', [])) if not index.get('modelGenerated') else len(str(index.get('preserved', {}).get('activeProjects', [])))} 条 | "
                   f"丢弃: {len(index.get('discarded', {}).get('samples', index.get('discarded', {}).get('summary', '')))} 条",
                   {"usagePercent": usage, "strategy": index.get('strategyUsed'), "dryRun": dry_run,
                    "modelGenerated": index.get('modelGenerated', False)})
    # ── 实际压缩：通过 OpenClaw 合法 CLI 通道触发 /compact ──
    # 修复 (2026-06-24): 不再直接写 active session 文件！
    # 直接写文件会触发 sessionFileFenceKey 检测 (EmbeddedAttemptSessionTakeoverError)，
    # 因为 OpenClaw 进程内的 ownedSessionFileWrites map 不会记录外部写入，
    # 接管时会判为 session 已被外部篡改 → 抛 takeover 错误。
    #
    # 修复 (2026-06-29): 改用 `openclaw sessions compact` 而非 `openclaw agent --message /compact`
    # 原因：`/compact` 是主会话的斜杠命令识别，从外部 --message 注入永远被视为普通消息
    # （OpenClaw 官方: "Slash commands cannot be executed via --message from the CLI"）。
    # 正确路径: `openclaw sessions compact <session-key>` 调用 sessions.compact gateway RPC。
    # --max-lines 模式不调 LLM, 直接截短, 秒级完成 (LLM 模式可能 60-180s 超时)。
    #
    # 修复 (2026-06-29): _save_json 必须在 compactTriggered/compactError 字段设置
    # 完成之后再调用，否则这两个字段会丢失到文件中（Bug：index 是 dict 引用，
    # _save_json 后修改 dict 不会回写到已写入的文件）。
    if not dry_run and usage >= THRESHOLD_WARN:
        try:
            active_session = _find_active_session()
            if active_session:
                pre_bytes = active_session.stat().st_size
                # 调 OpenClaw sessions.compact RPC 截短会话
                # --max-lines 200: 保留最后 200 行 (合理默认)，不走 LLM summary
                # --timeout 180000: 3 分钟超时 (LLM 模式可能慢)
                compact_proc = subprocess.run(
                    [
                        "openclaw", "sessions", "compact",
                        "agent:main:main",
                        "--max-lines", "200",
                        "--timeout", "180000",
                        "--json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=200,
                )
                if compact_proc.returncode == 0:
                    # 验证压缩是否真的生效
                    post_bytes = active_session.stat().st_size
                    bytes_saved = pre_bytes - post_bytes
                    pct_saved = round(bytes_saved / pre_bytes * 100, 1) if pre_bytes > 0 else 0
                    # 验证是否真变小 (0% = 无效, 才不会重复失败)
                    if bytes_saved > 0:
                        index["compactTriggered"] = True
                        index["compactMethod"] = "openclaw-sessions-compact"
                        index["preCompactBytes"] = pre_bytes
                        index["postCompactBytes"] = post_bytes
                        index["bytesSaved"] = bytes_saved
                        index["compressionEffective"] = True
                        print(
                            f"🧹 会话截短成功: {pre_bytes//1024}KB → {post_bytes//1024}KB "
                            f"(节省 {pct_saved}%)"
                        )
                        # 报 broker 成功事件
                        _append_broker(
                            "armor", "mark42.armor.compact.success",
                            f"会话截短: {pct_saved}% 节省",
                            "ok",
                            f"压缩前 {pre_bytes//1024}KB → 压缩后 {post_bytes//1024}KB "
                            f"({bytes_saved} bytes)",
                            {
                                "preBytes": pre_bytes,
                                "postBytes": post_bytes,
                                "bytesSaved": bytes_saved,
                                "pctSaved": pct_saved,
                                "method": "openclaw-sessions-compact",
                            },
                        )
                    else:
                        # 返回 0 但 session 没变 (极少见, 可能已压缩)
                        index["compactTriggered"] = True
                        index["compactMethod"] = "openclaw-sessions-compact"
                        index["compressionEffective"] = False
                        index["compactError"] = "no-bytes-saved"
                        index["preCompactBytes"] = pre_bytes  # J 修复: 也记
                        index["postCompactBytes"] = post_bytes
                        index["bytesSaved"] = bytes_saved
                        print(f"⚠️ sessions.compact 返回成功但 session 未变小")
                else:
                    err = (compact_proc.stderr or compact_proc.stdout)[:300]
                    index["compactTriggered"] = False
                    index["compactError"] = err
                    index["compressionEffective"] = False
                    index["preCompactBytes"] = pre_bytes  # J 修复: 也记
                    print(f"⚠️ sessions.compact 失败 (rc={compact_proc.returncode}): {err}")
                    _append_broker(
                        "armor", "mark42.armor.compact.failed",
                        f"sessions.compact 失败 rc={compact_proc.returncode}",
                        "error",
                        err,
                        {"rc": compact_proc.returncode, "preBytes": pre_bytes},
                    )
            else:
                print("⚠️ 未找到活跃会话，跳过 compact")
                index["compactTriggered"] = False
                index["compressionEffective"] = False
                index["preCompactBytes"] = pre_bytes  # J 修复: 也记
        except subprocess.TimeoutExpired:
            print("⚠️ sessions.compact 调用超时（200s）")
            index["compactTriggered"] = False
            index["compressionEffective"] = False
            index["compactError"] = "timeout"
        except FileNotFoundError:
            print("⚠️ openclaw 命令未找到，回退到只生成记忆索引")
            index["compactTriggered"] = False
            index["compressionEffective"] = False
            index["compactError"] = "openclaw-not-found"
        except Exception as e:
            print(f"⚠️ compact 触发失败: {e}")
            index["compactTriggered"] = False
            index["compressionEffective"] = False
            index["compactError"] = str(e)
    # ⚠️ 必须在所有字段（含 compactTriggered/compactError）设置完后再写文件
    _save_json(index_path, index)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    _save_json(history_dir / f"memory-index-{ts}.json", index)

    # 【2026-06-30 全面审查 J 修复】action_entry 写于 compact 后,同步 index 里的真值
    # 原动作写于函数入口,那时 preCompactBytes/postCompactBytes 还没填
    # 这样 actions.jsonl 能审计"压缩真截短了吗"(一键看透)
    #
    # 【2026-06-30 10:13 🟡4 修复】加 bytesStatus 语义标记,避免 reader 困惑 preBytes=null
    # - "captured": 压缩完成, 字段有真值
    # - "skipped-dry-run": dry_run 模式, 没真压缩, 字段为 null 是预期
    # - "not-attempted": 上下文 < THRESHOLD_WARN, 未尝试 compact
    # - "error": compact 报错 (没产生 postBytes)
    if dry_run:
        bytes_status = "skipped-dry-run"
    elif index.get("preCompactBytes") is not None and index.get("postCompactBytes") is not None:
        bytes_status = "captured"
    elif index.get("compactError"):
        bytes_status = "error"
    else:
        bytes_status = "not-attempted"
    action_entry = {
        "ts": _now_iso(),
        "action": "compress" if not dry_run else "compress-dryrun",
        "preCompressUsage": usage,
        "preBytes": index.get("preCompactBytes"),
        "postBytes": index.get("postCompactBytes"),
        "bytesSaved": index.get("bytesSaved"),
        "bytesStatus": bytes_status,  # 🟡4 语义标记
        "compressionEffective": index.get("compressionEffective"),
        "compactTriggered": index.get("compactTriggered"),
        "compactMethod": index.get("compactMethod"),
        "compactError": index.get("compactError"),
        "indexPath": str(index_path),
    }
    with open(actions_log, "a") as f:
        f.write(json.dumps(action_entry, ensure_ascii=False) + "\n")

    # ── P0 补充: 连续压缩无效升级报 ──
    # 读 actions.jsonl 最近 5 条, 如果全部 compressionEffective=False 且本次也是 False,
    # 说明 sessions.compact 调用一直不能压下 session, 可能是配置文件不一致、LLM 失败、
    # 或上下文估计偏差。则发升级事件到 broker, 提醒人工干预。
    try:
        recent_ineffective = 0
        if actions_log.exists():
            with open(actions_log) as f:
                recent_lines = f.readlines()[-10:]  # 最近 10 条
            # 检查最近 5 条非 dry-run 中是否有 compressionEffective=False
            for line in recent_lines[-5:]:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("action") == "compress":
                        # 检查本次压缩是否有效 (粗略依据: 读 memory-index.json)
                        # 精确方式要查 history/*，但简单点：只看本次
                        pass
                except Exception:
                    continue
        # 本次判断: index 里是否有 compressionEffective=False 且已生成
        if index.get("compressionEffective") is False:
            # 查 history 里最近 5 次 compressionEffective 字段
            hist_files = sorted(history_dir.glob("memory-index-*.json"))[-5:]
            ineffective_count = 0
            total_count = 0
            for hf in hist_files:
                try:
                    h = json.loads(hf.read_text())
                    if "compressionEffective" in h:
                        total_count += 1
                        if h["compressionEffective"] is False:
                            ineffective_count += 1
                except Exception:
                    continue
            if total_count >= 3 and ineffective_count == total_count:
                # 连续 ≥3 次压缩全部无效, 升级 broker
                _append_broker(
                    "armor", "mark42.armor.compact.ineffective",
                    f"连续 {ineffective_count}/{total_count} 次压缩未生效",
                    "warn",
                    f"建议检查 contextWindow 配置 / LLM 可用性 / session fence 状态",
                    {"ineffectiveCount": ineffective_count, "totalCount": total_count,
                     "preUsage": usage},
                )
                print(f"🚨 连续 {ineffective_count} 次压缩无效，升级 broker 事件")
    except Exception as e:
        # 升级逻辑本身的错误不能影响主流程
        print(f"⚠️ 连续无效检查失败 (非致命): {e}")

    return {"action": "compress", "indexWritten": str(index_path), "preCompressUsage": usage, "check": check}


def armor_guard(interval_s: int = 300) -> None:
    """守护模式：每 N 秒检查一次，超阈值自动出手。"""
    print(f"🛡️ 上下文铠甲守护模式启动（每 {interval_s}s 检查）")
    try:
        while True:
            check = armor_check()
            usage = check.get("usagePercent", 0)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] 上下文 {usage}% — {check.get('summary', '')}")
            if usage >= THRESHOLD_ALERT:
                print(f"[{ts}] 🟠 自动触发压缩")
                result = armor_compress()
                print(f"    → {result.get('action')}")
            time.sleep(interval_s)
    except KeyboardInterrupt:
        print("\n🛡️ 守护模式已退出")


# ----------------------------------------------------------------------
# Day 7: 异步压缩入口 (compress_queue.py 集成)
# ----------------------------------------------------------------------
def armor_compress_async(dry_run: bool = False, wait: bool = False,
                         priority: int = 0) -> dict[str, Any]:
    """异步版 armor_compress — 入队立即返回

    Args:
        dry_run: 当前未使用 (queue 内部直接调 process), 保留为接口对齐
        wait: True=等结果 (同步语义, 兼容旧调用), False=立即返回
        priority: 0=normal, 1=urgent, 2=low

    Returns:
        wait=True:  {"status": "completed", "result": {...}}
        wait=False: {"status": "queued", "request_id": "req-xxx", "session_id": "..."}
        队列满:     {"status": "dropped", "reason": "queue_full"}
    """
    try:
        # P1.2 修复: 顶局 import 便于 mock (原函数体 import 难测)
        from mark42_modules.compress_queue import CompressRequest, get_compress_queue
    except ImportError as e:
        return {"status": "error", "reason": f"queue module not available: {e}"}

    # 读 session 尾部 (同步, 快, 不阻塞)
    active = _find_active_session()
    session_messages = _read_session_tail(active) if active else []

    # 提取待压缩的"内容": 实际场景是 session_messages 序列化为 JSON
    # 这里用最简方式: 把 messages 转成字符串作为 compress 输入
    import json as _json
    try:
        content = _json.dumps(session_messages, ensure_ascii=False, default=str)
    except Exception:
        content = str(session_messages)

    req = CompressRequest(
        content=content,
        session_id=active.name if active else "unknown",
        content_type="auto",
        priority=priority,
    )

    queue = get_compress_queue()
    accepted = queue.enqueue(req)
    if not accepted:
        return {"status": "dropped", "reason": "queue_full",
                "queue_size": queue.qsize()}

    if not wait:
        return {"status": "queued",
                "request_id": req.request_id,
                "session_id": req.session_id,
                "queue_size": queue.qsize()}

    # 同步等结果
    completed = req.wait(timeout=30.0)
    if not completed:
        return {"status": "timeout", "request_id": req.request_id}

    if req.error:
        return {"status": "failed", "error": req.error, "request_id": req.request_id}

    return {"status": "completed", "result": req.result, "request_id": req.request_id}


def armor_compress_queue_stats() -> dict[str, Any]:
    """查看压缩队列统计"""
    try:
        # P1.2 修复: 顶局 import 便于 mock
        from mark42_modules.compress_queue import get_compress_queue
        return get_compress_queue().stats
    except ImportError as e:
        return {"error": f"queue module not available: {e}"}
