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
    THRESHOLD_WARN, WORKSPACE, XDG_STATE,
)
from .utils import (
    _append_broker, _find_active_session, _get_context_window, _load_json,
    _now_iso, _now_ts, _save_json,
)


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
        # 用文件字节数直接估算 token 数
        # JSONL 每字节 ≈ 0.25 token（中文约2-3 chars/token + JSON 控制字符）
        # 14 KB/1000 tokens 是 DeepSeek 模型的经验值
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
    """调用 DeepSeek API 对会话消息做智能分析。失败则返回 None。"""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    mark42_config_path = CONFIG_PATH
    if not config_path.exists():
        return None
    try:
        # 从 openclaw.json 取 API key
        with open(config_path) as f:
            cfg = json.load(f)
        provider = cfg.get("models", {}).get("providers", {}).get("minimax", {})
        api_key = provider.get("apiKey", "")
        base_url = provider.get("baseUrl", "https://api.minimax.chat/v1")
        if not api_key:
            return None
        # 从 Mark42 配置取模型名
        model_name = "MiniMax-M3"
        if mark42_config_path.exists():
            try:
                with open(mark42_config_path) as f:
                    mcfg = json.load(f)
                model_name = mcfg.get("models", {}).get("llmAnalyze", "MiniMax-M3")
            except Exception:
                pass
    except Exception:
        return None
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
            "max_tokens": 2000,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=45)
        data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        content = content.strip()
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
        }
        print("⚠️ LLM 不可用，回退到启发式分析")
    index_path = ARMOR_STATE / "memory-index.json"
    _save_json(index_path, index)
    history_dir = ARMOR_STATE / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    _save_json(history_dir / f"memory-index-{ts}.json", index)
    actions_log = ARMOR_STATE / "actions.jsonl"
    action_entry = {
        "ts": _now_iso(),
        "action": "compress" if not dry_run else "compress-dryrun",
        "preCompressUsage": usage,
        "indexPath": str(index_path),
    }
    with open(actions_log, "a") as f:
        f.write(json.dumps(action_entry, ensure_ascii=False) + "\n")
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
