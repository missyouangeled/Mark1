"""Mark42 模块A：上下文铠甲 Armor。
实时检测上下文健康 + LLM 驱动记忆索引 + 启发式回退 + 守护模式。
"""

import json
import logging
import os
import subprocess
import time
import urllib.request
import uuid

logger = logging.getLogger(__name__)
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import (
    ALGO_EXPERIMENT_MODE,
    ALGO_FAIL_SAFE,
    ALGO_SMARTCRUSH_ENABLED,
    ALGO_SMARTCRUSH_MIN_CONTENT_SIZE,
    # 阶段 1 Day 4: 调度器接入控制 (2026-06-24)
    ALGO_USE_SCHEDULER,
    ARMOR_STATE,
    BYTES_PER_KTOKEN,
    DEFAULT_CONTEXT_WINDOW,
    OPENCLAW_BIN,
    XDG_STATE,
    get_dynamic_thresholds,
    resolve_model,
)
from .output_guard import compact_preview, trim_detail
from .utils import (
    _append_broker,
    _estimate_tokens_smart,
    _find_active_session,
    _get_context_window,
    _now_iso,
    _save_json,
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
    from .algo_scheduler import decide as algo_scheduler_decide
    from .algo_scheduler import process as algo_scheduler_process
    _SCHEDULER_AVAILABLE = True
except ImportError as e:
    _SCHEDULER_AVAILABLE = False
    _SCHEDULER_IMPORT_ERROR = str(e)

# ── compact 编排常量 (2026-08-04 从 armor_compress 内部提取到模块级) ──
# 拆分原因: armor_compress 原为 665 行巨型函数, 常量散落函数内部导致
# 子逻辑无法独立测试。提到模块级后各阶段可单独 mock/覆盖。
COMPACT_COOLDOWN_SEC = 1800   # compact 冷却期 30 分钟, 避免反复压缩已压过的 session
PLATFORM_PROBE_SEC = 60       # 平台探测期总时长: 先等平台自己 auto-compaction
PLATFORM_PROBE_INTERVAL = 10  # 探测期内每次检查间隔
COMPACT_LOCK_TTL_SEC = 620    # compact 锁过期时间 (compact 超时 620s + 缓冲)
_COMPACT_LOCK_RECLAIM_RETRIES = 3  # 过期/损坏锁的回收重试上界（防无界递归）

# 测试钩子: conftest.py 会 setattr 为 True 以跳过平台探测期的真实 sleep
_PLATFORM_PROBE_SKIP_SLEEP = False


def _compact_cooldown_file() -> Path:
    """compact 冷却期标记文件路径。

    做成函数而非模块级常量: XDG_STATE 在测试中被 monkeypatch 重定向,
    模块级常量会在 import 时固化成旧路径。
    """
    return XDG_STATE / "mark42" / "armor" / "compact-cooldown.json"


def _compact_lock_file() -> Path:
    """compact 锁文件路径。同上, 延迟求值避免测试路径固化。"""
    return XDG_STATE / "mark42" / "armor" / "compact.lock"


def _new_compact_lock_token() -> str:
    """生成锁的唯一所有权 token（PID 会被复用，不能单靠 PID）。"""
    return f"{os.getpid()}-{uuid.uuid4().hex}"


def _lock_inode(lock_file: Path) -> int | None:
    """取锁文件当前 inode；不存在或不可读返回 None。"""
    try:
        return lock_file.stat().st_ino
    except OSError:
        return None


def _read_compact_lock_identity(lock_file: Path) -> tuple[dict, int | None] | None:
    """读锁内容 + 同时记下当时的 inode。

    返回 ``(lock_data, inode)``；锁不存在时返回 None。
    内容不是合法 JSON 时 ``lock_data`` 为空 dict（交给调用方当损坏锁处理）。
    inode 用于删除前比对：即使文件名相同，被重建过的锁 inode 也会变。
    """
    try:
        raw = lock_file.read_text()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    ino = _lock_inode(lock_file)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            data = {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    return data, ino


def _unlink_compact_lock_if_same(
    lock_file: Path, expected_token: str | None, expected_ino: int | None
) -> bool:
    """仅当锁仍是「自己刚刚观测到的那一份」时才删除。

    这是 P2-15 的核心修复：check 与 unlink 之间存在时间窗，
    另一进程可能已回收旧锁并建了**新鲜锁**。删除前重新比对
    token 与 inode，不一致就说明锁已换主，必须放手。

    返回是否实际执行了删除。
    """
    current = _read_compact_lock_identity(lock_file)
    if current is None:
        return False  # 已被别人删了，无需动作
    current_data, current_ino = current

    if expected_ino is not None and current_ino != expected_ino:
        logger.warning("compact 锁已被重建(inode 变化)，放弃删除以免踩掉他人锁")
        return False
    if expected_token is not None and current_data.get("token") != expected_token:
        logger.warning("compact 锁已换主(token 不符)，放弃删除以免踩掉他人锁")
        return False
    if expected_token is None and current_data.get("token"):
        # 观测时是损坏/无 token 锁，现在却有了合法 token —— 已被健康锁接管
        logger.warning("compact 锁已被健康锁接管，放弃删除")
        return False

    try:
        lock_file.unlink(missing_ok=True)
        return True
    except OSError as e:
        logger.warning("compact 锁删除失败: %s", e)
        return False


def _iso_age_seconds(iso_ts: str) -> float | None:
    """计算 ISO 时间戳距今多少秒。兼容 aware / naive 两种格式。

    【2026-08-04 Bug 修复】_now_iso() 产出的时间戳带时区偏移（如 +08:00），
    而原代码用 datetime.now()（naive）相减，会抛：
        TypeError: can't subtract offset-naive and offset-aware datetimes

    后果（拆分前就存在的真 bug，被子函数单测暴露）：
      1. compact 锁完全失效——异常被 except 吃掉后走「锁文件损坏」分支，
         删锁重建，于是两个 Mark42 实例可以同时 compact。
      2. 冷却期检查失效——同样被吃掉，30 分钟防重复压缩形同虚设。

    Returns: 秒数；无法解析时返回 None。
    """
    from datetime import datetime as _dt
    try:
        parsed = _dt.fromisoformat(iso_ts)
    except (ValueError, TypeError):
        return None
    now = _dt.now(tz=parsed.tzinfo) if parsed.tzinfo is not None else _dt.now()
    return (now - parsed).total_seconds()


def _try_acquire_compact_lock() -> bool:
    """尝试获取 compact 锁。返回 True 表示获取成功。

    使用 O_CREAT|O_EXCL 原子创建，避免竞态条件。

    锁内写入唯一 ``token``（含 PID），回收过期/损坏锁时只删除
    「自己刚刚读到的那一份」（比对 token 与 inode）。否则在 check 与
    unlink 之间，另一进程可能已回收旧锁并建了**新鲜锁**，
    无条件 unlink 会把别人的新锁踩掉（P2-15）。
    """
    return _acquire_compact_lock_once(_COMPACT_LOCK_RECLAIM_RETRIES)


def _acquire_compact_lock_once(retries_left: int) -> bool:
    """单轮锁获取。``retries_left`` 给回收重试封顶，避免无界递归。"""
    import errno as _errno
    lock_file = _compact_lock_file()
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    # 先尝试原子创建（O_CREAT|O_EXCL）
    try:
        fd = os.open(
            str(lock_file),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
        # 防御：若拿到 0/1/2（标准流被上层关闭时可能发生，如 pytest fd 捕获模式），
        # 用 F_DUPFD 重定位到 >=3 的 fd；并把低位 slot 重新指向 /dev/null，
        # 保证标准输入/输出/错误流始终有效，不会因后续 close 而损坏。
        if fd < 3:
            import fcntl as _fcntl
            _high = _fcntl.fcntl(fd, _fcntl.F_DUPFD, 3)
            _devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(_devnull, fd)
            os.close(_devnull)
            fd = _high
        try:
            os.write(fd, json.dumps({
                "acquiredAt": _now_iso(),
                "pid": os.getpid(),
                "token": _new_compact_lock_token(),
            }, ensure_ascii=False).encode())
        finally:
            os.close(fd)
        return True
    except OSError as e:
        if e.errno != _errno.EEXIST:
            # 非预期错误，保守起见不获取锁
            return False

    if retries_left <= 0:
        # 回收重试耗尽：锁一直被别的进程抢走，本轮放弃
        logger.warning("compact 锁回收重试耗尽，本轮放弃抢锁")
        return False

    # 锁文件已存在，检查是否过期
    try:
        observed = _read_compact_lock_identity(lock_file)
        if observed is None:
            # 读不到（刚被删掉）——直接重试抢锁
            return _acquire_compact_lock_once(retries_left - 1)
        lock_data, observed_ino = observed
        lock_ts = lock_data.get("acquiredAt")
        if lock_ts:
            lock_age = _iso_age_seconds(lock_ts)
            if lock_age is not None and lock_age < COMPACT_LOCK_TTL_SEC:
                return False  # 锁未过期
        # 锁已过期（或缺 acquiredAt）：只删除自己刚读到的那份
        _unlink_compact_lock_if_same(
            lock_file, lock_data.get("token"), observed_ino
        )
        return _acquire_compact_lock_once(retries_left - 1)
    except Exception:
        # 锁文件损坏：同样只删自己观测到的那份 inode
        _unlink_compact_lock_if_same(lock_file, None, _lock_inode(lock_file))
        return _acquire_compact_lock_once(retries_left - 1)


def _release_compact_lock() -> None:
    """释放 compact 锁——**仅当锁确实属于本进程时**。

    旧实现无条件 unlink：如果本进程的锁已因超时被别人回收、
    而对方正在持锁工作，这里会把**对方的锁**删掉，
    导致第三个进程也能抢入 —— 互斥彻底失效（P2-15）。
    """
    lock_file = _compact_lock_file()
    try:
        observed = _read_compact_lock_identity(lock_file)
        if observed is None:
            return  # 锁已不存在，幂等
        lock_data, observed_ino = observed
        if lock_data.get("pid") != os.getpid():
            logger.warning(
                "compact 锁已不属于本进程(持有者 pid=%s)，拒绞删除",
                lock_data.get("pid"),
            )
            return
        _unlink_compact_lock_if_same(
            lock_file, lock_data.get("token"), observed_ino
        )
    except Exception as e:
        logger.warning("ignored error: %s", e)


def _platform_compact_probe(usage_val: float, dry_run: bool = False) -> bool:
    """平台探测期：等待平台自己 compact。

    Mark42 是跨平台铠甲, armor_compress 是最后自主救场能力, 但不能与平台自带的
    auto-compaction 冲突。所以先等一个探测期看平台是否自己处理。

    返回 True 表示平台已处理（usage 下降了），False 表示平台无反应。
    """
    if dry_run:
        return False  # dry_run 不等
    # 测试环境可跳过 sleep（conftest.py setattr _PLATFORM_PROBE_SKIP_SLEEP=True）
    import sys as _sys
    _armor_mod = _sys.modules.get(__name__)
    if _armor_mod and getattr(_armor_mod, "_PLATFORM_PROBE_SKIP_SLEEP", False):
        print("   [test] 跳过平台探测期 sleep")
        return False
    print(f"👀 平台探测期 ({PLATFORM_PROBE_SEC}s)：等待平台 auto-compaction 反应...")
    for i in range(PLATFORM_PROBE_SEC // PLATFORM_PROBE_INTERVAL):
        time.sleep(PLATFORM_PROBE_INTERVAL)
        probe_check = armor_check()
        probe_usage = probe_check.get("usagePercent", 0)
        if probe_usage < usage_val - 5:
            # usage 下降了 5%+，说明平台自己 compact 了
            print(f"   ✅ 探测到 usage 下降: {usage_val}% -> {probe_usage}%，平台已处理")
            return True
        print(f"   ⏳ [{(i+1)*PLATFORM_PROBE_INTERVAL}s] usage={probe_usage}% (无变化)")
    print("   ⚠️ 平台探测期结束，usage 仍无下降，Mark42 自主出手")
    return False



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
    # 动态阈值：大窗口更早介入 (context rot 更严重)
    _warn_pct, _alert_pct, _crit_pct = get_dynamic_thresholds(context_window)
    severity = "ok"
    status = "ok"
    summary = f"上下文 {usage_pct}%，正常"
    if usage_pct >= _crit_pct:
        severity = "critical"
        status = "critical"
        summary = f"⚠️ 上下文 {usage_pct}% 达到危险等级 (阈值{_crit_pct}%)"
    elif usage_pct >= _alert_pct:
        severity = "warn"
        status = "alert"
        summary = f"⚠️ 上下文 {usage_pct}% 偏高，建议压缩 (阈值{_alert_pct}%)"
    elif usage_pct >= _warn_pct:
        severity = "info"
        status = "warn"
        summary = f"💡 上下文 {usage_pct}%，关注中 (阈值{_warn_pct}%)"
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
    messages: list[dict[str, Any]] = []
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
        entry = {"index": i, "role": role, "preview": compact_preview(text, 120)}
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
    for msg in messages[-20:]:
        role = msg.get("role", "?")
        raw_content = msg.get("content", "")
        # 处理 OpenClaw content 数组格式: [{"type":"text","text":"..."}]
        if isinstance(raw_content, list):
            text = " ".join(c.get("text", "") for c in raw_content if isinstance(c, dict))
        elif isinstance(raw_content, str):
            text = raw_content
        else:
            text = str(raw_content)
        text = text[:150]
        lines.append(f"[{role}] {text}")
    convo_text = "\n".join(lines)[:4096]
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
        req = urllib.request.Request(  # noqa: S310 (LLM API urllib，url 来自受信配置)
            f"{base_url}{endpoint}",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 (LLM API urllib，url 来自受信配置)
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
        # LLM 响应 JSON 顶层必须是对象，否则后续 result["_llm_meta"] 会崩（P3-4）
        if not isinstance(result, dict):
            print(
                f"    ⚠️ _llm_analyze 响应顶层不是对象（{type(result).__name__}），已丢弃"
            )
            return None
        result["_llm_meta"] = {
            "model": data.get("model"),
            "tokens": data.get("usage", {}),
            "responseFormat": "json_object",
        }
        return result
    except Exception as e:
        print(f"    ⚠️ _llm_analyze 失败: {type(e).__name__}: {e}")
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
    stats: dict[str, Any] = {
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
            logger.warning("compression scheduler error (fail-safe 返回原文): %s", e)
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
        logger.warning("compression hook error: %s", e)

    return stats


def _compress_build_index(
    session_messages: list[dict[str, Any]],
    usage: float,
    algo_stats: dict[str, Any],
    alert_pct: float,
) -> dict[str, Any]:
    """构建记忆索引 — LLM 优先，启发式回退。

    2026-08-04 从 armor_compress 拆出。只负责分析 + 组装 index dict，
    不做任何文件写入或事件上报，方便单独测试两条分支。

    Args:
        session_messages: session 尾部消息列表
        usage: 当前上下文使用率
        algo_stats: 阶段 1 压缩算法 hook 的统计结果
        alert_pct: ALERT 阈值，用于启发式分支判定 recommendedAction

    Returns:
        index dict，含 strategyUsed 字段区分两条路径（llm-analyze / heuristic-classify）
    """
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
        return index

    classification = _classify_messages(session_messages)
    preserved_items = classification.get("preserved", [])
    preserved_roles: dict[str, list[str]] = {}
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
        "recommendedAction": "/compact" if usage >= alert_pct else "monitor",
        "algoStats": algo_stats,
    }
    print("⚠️ LLM 不可用，回退到启发式分析")
    return index


def _compress_log_events(usage: float, dry_run: bool, index: dict[str, Any],
                         warn_pct: float) -> None:
    """上报压缩事件到 broker（health 频道 + 标准化 armor 频道）。

    2026-08-04 从 armor_compress 拆出。纯副作用函数，无返回值。
    """
    _append_broker("health", "armor.compress",
                   f"上下文压缩{'预览' if dry_run else ''}: {usage}%",
                   "warn" if usage >= warn_pct else "ok",
                   f"使用率 {usage}%，{'建议手动' if dry_run else '已生成'}记忆索引",
                   {"usagePercent": usage, "dryRun": dry_run})
    # ── C 项：标准化事件桥接 ──
    _append_broker("armor", "mark42.armor.compress.done",
                   f"铠甲压缩完成: {usage}% → {index.get('strategyUsed', '?')}",
                   "ok" if index.get('strategyUsed') == 'llm-analyze' else "warn",
                   trim_detail(
                       f"策略: {index.get('strategyUsed', '?')} | "
                       f"保留: {len(index.get('preserved', {}).get('byRole', {}).get('user', [])) + len(index.get('preserved', {}).get('byRole', {}).get('assistant', [])) if not index.get('modelGenerated') else len(str(index.get('preserved', {}).get('activeProjects', [])))} 条 | "
                       f"丢弃: {len(index.get('discarded', {}).get('samples', index.get('discarded', {}).get('summary', '')))} 条",
                       180,
                   ),
                   {"usagePercent": usage, "strategy": index.get('strategyUsed'), "dryRun": dry_run,
                    "modelGenerated": index.get('modelGenerated', False)})


def _compress_check_cooldown(index: dict[str, Any], index_path: Path,
                            check: dict[str, Any]) -> dict[str, Any] | None:
    """压缩冷却期检查。

    2026-08-04 从 armor_compress 拆出。背景（修复 2026-07-29）：
    连续 compact 已压缩过的 session 是无效操作——LLM 摘要 + 结构化元数据
    会让文件比原文还大。加 30 分钟冷却期避免反复蹂躏。

    副作用：命中冷却期时会回写 index 字段 + 落盘 index_path。

    Returns:
        命中冷却期时返回 skip 结果 dict；不命中返回 None 让主流程继续。
    """
    compact_cooldown_file = _compact_cooldown_file()
    if not compact_cooldown_file.exists():
        return None
    try:
        import json as _json
        cd = _json.loads(compact_cooldown_file.read_text())
        last_ts = cd.get("lastCompactTs")
        if last_ts:
            # 【2026-08-04 Bug 修复】原代码 datetime.now() - fromisoformat(aware)
            # 会抛 TypeError 并被下方 except 吃掉 -> 冷却期形同虚设。
            elapsed = _iso_age_seconds(last_ts)
            if elapsed is not None and elapsed < COMPACT_COOLDOWN_SEC:
                remaining = int((COMPACT_COOLDOWN_SEC - elapsed) / 60)
                print(f"⏸️ 压缩冷却中（还剩 {remaining} 分钟），跳过本次 compact")
                index["compactTriggered"] = False
                index["compactError"] = f"cooldown-{remaining}min"
                index["compressionEffective"] = False
                index["preCompactBytes"] = None
                _save_json(index_path, index)
                return {"action": "skip-cooldown", "reason": f"冷却中，还剩 {remaining} 分钟",
                        "check": check}
    except Exception as e:
        logger.warning("冷却期检查失败（非致命）: %s", e)
    return None


def _compress_check_already_compacted(active: Path, index: dict[str, Any],
                                     index_path: Path, usage: float,
                                     check: dict[str, Any]) -> dict[str, Any] | None:
    """预检 session 是否已被 compact 过。

    2026-08-04 从 armor_compress 拆出。背景（修复 2026-07-29）：
    如果 session 文件里已有 compaction 条目，说明最近被摘要过，
    再跑 LLM compact 只会让摘要+元数据膨胀（实测变大 10KB+）。

    副作用：命中时回写 index + 落盘 + 写冷却期标记 + 上报 broker 事件。

    Returns:
        命中时返回 skip 结果 dict；不命中返回 None。
    """
    try:
        with open(active) as _f:
            _head = _f.read(8192)  # 读前 8KB 够判断
        if '"type":"compaction"' not in _head and '"type": "compaction"' not in _head:
            return None
        print("⏸️ Session 已含 compaction 摘要，跳过 LLM compact（避免摘要膨胀）")
        index["compactTriggered"] = False
        index["compactError"] = "session-already-compacted"
        index["compressionEffective"] = False
        index["preCompactBytes"] = active.stat().st_size
        _save_json(index_path, index)
        # 写冷却期标记
        try:
            cooldown_file = _compact_cooldown_file()
            cooldown_file.parent.mkdir(parents=True, exist_ok=True)
            cooldown_file.write_text(
                json.dumps({"lastCompactTs": _now_iso(), "reason": "already-compacted"},
                           ensure_ascii=False)
            )
        except Exception as e:
            logger.warning("ignored error: %s", e)
        _append_broker(
            "armor", "mark42.armor.compact.skipped",
            "Session 已含摘要，跳过 compact",
            "info",
            "session 文件检测到 compaction 条目，跳过避免摘要膨胀",
            {"preBytes": index["preCompactBytes"], "usagePercent": usage},
        )
        return {"action": "skip-already-compacted", "reason": "session 已含 compaction 摘要",
                "check": check}
    except Exception as e:
        logger.warning("预检 compaction 失败（非致命）: %s", e)
    return None


def _compress_run_compact_cli(active_session: Path, index: dict[str, Any],
                              usage: float) -> None:
    """执行实际压缩：Session Fence 验证 + OpenClaw sessions.compact CLI 调用。

    2026-08-04 从 armor_compress 拆出（原为深度嵌套的 ~180 行内联块）。

    历史背景：
    - 修复 (2026-06-24): 不再直接写 active session 文件！直接写会触发
      sessionFileFenceKey 检测 (EmbeddedAttemptSessionTakeoverError)，因为 OpenClaw
      进程内的 ownedSessionFileWrites map 不会记录外部写入。
    - 修复 (2026-06-29): 用 `openclaw sessions compact` 而非 `--message /compact`，
      因为斜杠命令从外部 --message 注入永远被视为普通消息。
    - 修复 (2026-07-29): LLM compact 后先看文件大小变化再判成败：
      变大=摘要膨胀（不回退）/ 变小=成功 / 没变=真失败（才回退 maxlines）。

    副作用：直接回写 index 字段（compactTriggered / compactMethod / preCompactBytes /
    postCompactBytes / bytesSaved / compressionEffective / compactError），无返回值。
    异常不在本函数捕获，由调用方统一处理 TimeoutExpired / FileNotFoundError。
    """
    from .session_fence import fence_record_post, fence_record_pre, fence_verify

    # fence 验证：检查 session 是否安全可操作
    verify = fence_verify(active_session)
    if not verify["ok"]:
        logger.warning("Session Fence 拦截: %s", verify["reason"])
        index["compactTriggered"] = False
        index["compactError"] = f"fence-blocked: {verify['reason']}"
        index["compressionEffective"] = False
        index["preCompactBytes"] = None
        _append_broker(
            "armor", "mark42.armor.compact.fence_blocked",
            f"Session Fence 拦截: {verify['reason']}",
            "warn",
            f"原因: {verify['reason']}",
            {"fenceReason": verify["reason"], "usagePercent": usage},
        )
        return

    fence_pre = fence_record_pre(active_session)
    pre_bytes = active_session.stat().st_size
    # 调 OpenClaw sessions.compact RPC 做 LLM 摘要压缩
    # 不加 --max-lines: 走 LLM 摘要模式（doubao-seed-2.0-pro），保留语义
    # --timeout 600000: OpenClaw 内部超时 600s (LLM 模式可能慢 60-180s)
    compact_proc = subprocess.run(
        [
            OPENCLAW_BIN, "sessions", "compact",
            "agent:main:main",
            "--timeout", "600000",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=620,  # 比 OpenClaw 内部超时多 20s 缓冲
    )
    # ── 修复 (2026-07-29): LLM compact 后检查文件大小变化 ──
    # 不管 rc 是 0 还是非 0，先看文件有没有变化：
    # - 变大 = LLM 摘要膨胀（不要回退 maxlines）
    # - 变小 = compact 成功（即使 rc!=0 也算成功）
    # - 没变 = compact 真失败（才回退 maxlines）
    _post_llm_bytes = active_session.stat().st_size if active_session.exists() else pre_bytes
    _llm_made_it_bigger = _post_llm_bytes > pre_bytes
    _llm_made_it_smaller = _post_llm_bytes < pre_bytes

    if _llm_made_it_bigger:
        logger.warning("LLM 摘要比原文大 (pre=%d, post=%d)，跳过 maxlines 回退",
                       pre_bytes, _post_llm_bytes)
        index["compactTriggered"] = True
        index["compactMethod"] = "openclaw-sessions-compact"
        index["preCompactBytes"] = pre_bytes
        index["postCompactBytes"] = _post_llm_bytes
        index["bytesSaved"] = pre_bytes - _post_llm_bytes
        index["compressionEffective"] = False
        index["compactError"] = "llm-summary-larger-than-original"
        _append_broker(
            "armor", "mark42.armor.compact.summary_inflated",
            "LLM 摘要比原文大，压缩反效果",
            "warn",
            f"pre={pre_bytes}B post={_post_llm_bytes}B diff={pre_bytes - _post_llm_bytes}B",
            {"preBytes": pre_bytes, "postBytes": _post_llm_bytes, "usagePercent": usage},
        )
    elif _llm_made_it_smaller:
        post_bytes = _post_llm_bytes
        bytes_saved = pre_bytes - post_bytes
        pct_saved = round(bytes_saved / pre_bytes * 100, 1) if pre_bytes > 0 else 0
        index["compactTriggered"] = True
        index["compactMethod"] = "openclaw-sessions-compact"
        index["preCompactBytes"] = pre_bytes
        index["postCompactBytes"] = post_bytes
        index["bytesSaved"] = bytes_saved
        index["compressionEffective"] = True
        print(f"🧹 LLM 压缩成功: {pre_bytes//1024}KB -> {post_bytes//1024}KB (节约 {pct_saved}%)")
        _append_broker(
            "armor", "mark42.armor.compact.success",
            f"LLM 压缩: {pct_saved}% 节约",
            "ok",
            f"{pre_bytes//1024}KB -> {post_bytes//1024}KB ({bytes_saved} bytes)",
            {"preBytes": pre_bytes, "postBytes": post_bytes, "bytesSaved": bytes_saved,
             "pctSaved": pct_saved},
        )
        _inject_memory_index(index)
    else:
        # 文件没变化 -> compact 真失败或被拒绝 -> 才回退到 maxlines
        if compact_proc.returncode != 0:
            print("    ⚠️ LLM 压缩失败且文件未变，回退到截短模式")
            compact_proc = subprocess.run(
                [
                    OPENCLAW_BIN, "sessions", "compact",
                    "agent:main:main",
                    "--max-lines", "150",
                    "--timeout", "180000",
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=200,  # 截短模式快，200s 够用
            )
        if compact_proc.returncode == 0:
            post_bytes = active_session.stat().st_size
            bytes_saved = pre_bytes - post_bytes
            pct_saved = round(bytes_saved / pre_bytes * 100, 1) if pre_bytes > 0 else 0
            fence_post = fence_record_post(active_session, fence_pre)
            if not fence_post["ok"]:
                logger.warning("Session Fence 检测到外部篡改！pre=%d post=%d",
                               pre_bytes, post_bytes)
                _append_broker(
                    "armor", "mark42.armor.compact.fence_tampered",
                    "Session Fence 检测到外部篡改",
                    "warn",
                    f"pre={pre_bytes}B post={post_bytes}B delta={fence_post['delta']}B",
                    {"preSize": pre_bytes, "postSize": post_bytes, "tampered": True},
                )
            if bytes_saved > 0:
                index["compactTriggered"] = True
                index["compactMethod"] = "openclaw-sessions-compact"
                index["preCompactBytes"] = pre_bytes
                index["postCompactBytes"] = post_bytes
                index["bytesSaved"] = bytes_saved
                index["compressionEffective"] = True
                print(f"🧹 会话截短成功: {pre_bytes//1024}KB -> {post_bytes//1024}KB (节约 {pct_saved}%)")
                _append_broker(
                    "armor", "mark42.armor.compact.success",
                    f"会话截短: {pct_saved}% 节约",
                    "ok",
                    f"压缩前 {pre_bytes//1024}KB -> 压缩后 {post_bytes//1024}KB ({bytes_saved} bytes)",
                    {"preBytes": pre_bytes, "postBytes": post_bytes, "bytesSaved": bytes_saved,
                     "pctSaved": pct_saved, "method": "openclaw-sessions-compact"},
                )
                _inject_memory_index(index)
            else:
                index["compactTriggered"] = True
                # 区分：是否走了 maxlines 回退
                _used_fallback = ('--max-lines' in ' '.join(compact_proc.args)
                                  if hasattr(compact_proc, 'args') else False)
                index["compactMethod"] = ("openclaw-sessions-compact-maxlines-fallback"
                                          if _used_fallback else "openclaw-sessions-compact")
                index["compressionEffective"] = False
                index["compactError"] = ("no-bytes-saved-after-fallback"
                                         if _used_fallback else "no-bytes-saved")
                index["preCompactBytes"] = pre_bytes
                index["postCompactBytes"] = post_bytes
                index["bytesSaved"] = bytes_saved
                print("⚠️ sessions.compact 返回成功但 session 未缩小")
        else:
            err = (compact_proc.stderr or compact_proc.stdout)[:300]
            index["compactTriggered"] = False
            index["compactError"] = err
            index["compressionEffective"] = False
            index["preCompactBytes"] = pre_bytes
            logger.warning("sessions.compact 失败 (rc=%d): %s", compact_proc.returncode, err)
            _append_broker(
                "armor", "mark42.armor.compact.failed",
                f"sessions.compact 失败 rc={compact_proc.returncode}",
                "error",
                err,
                {"rc": compact_proc.returncode, "preBytes": pre_bytes},
            )

    # ── 压缩后写冷却期标记 ──
    try:
        _cooldown_f = _compact_cooldown_file()
        _cooldown_f.parent.mkdir(parents=True, exist_ok=True)
        _cooldown_f.write_text(
            json.dumps({"lastCompactTs": _now_iso(), "reason": "post-compact"},
                       ensure_ascii=False)
        )
    except Exception as e:
        logger.warning("ignored error: %s", e)


def _compress_write_action_log(index: dict[str, Any], index_path: Path,
                              actions_log: Path, usage: float,
                              dry_run: bool) -> None:
    """写 actions.jsonl 审计记录。

    2026-08-04 从 armor_compress 拆出。

    历史背景：
    - 【2026-06-30 审查 J 修复】action_entry 必须写于 compact 后，同步 index 里的真值。
      原动作写于函数入口，那时 preCompactBytes/postCompactBytes 还没填。
    - 【2026-06-30 🟡4 修复】加 bytesStatus 语义标记，避免 reader 困惑 preBytes=null：
      captured / skipped-dry-run / not-attempted / error
    """
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


def _compress_check_ineffective_escalation(index: dict[str, Any], history_dir: Path,
                                          usage: float) -> None:
    """连续压缩无效升级报（P0 补充）。

    2026-08-04 从 armor_compress 拆出。

    若 history 最近 ≥3 次压缩全部 compressionEffective=False 且本次也是 False，
    说明 sessions.compact 调用一直不能压下 session，可能是配置文件不一致、
    LLM 失败、或上下文估计偏差。则发升级事件到 broker，提醒人工干预。

    升级逻辑本身的错误不能影响主流程，所以全部包在 try 里。
    """
    try:
        # 本次判断: index 里是否有 compressionEffective=False 且已生成
        if index.get("compressionEffective") is not False:
            return
        # 查 history 里最近 5 次 compressionEffective 字段
        hist_files = sorted(history_dir.glob("memory-index-*.json"))[-5:]
        ineffective_count = 0
        total_count = 0
        unreadable = 0
        for hf in hist_files:
            try:
                h = json.loads(hf.read_text())
                if "compressionEffective" in h:
                    total_count += 1
                    if h["compressionEffective"] is False:
                        ineffective_count += 1
            except (OSError, json.JSONDecodeError):
                # 关键区分：这里的判定是"连续 N 次压缩全部无效就升级告警"。
                # 如果坏文件被静默跳过, total_count 会偏小, 可能让本该触发的
                # 升级条件(total_count >= 3)永远不满足 —— 静默削弱了告警能力。
                unreadable += 1
                continue
        if unreadable:
            logger.warning(
                "压缩历史有 %d/%d 份无法解析已跳过, 无效压缩升级判定可能偏保守",
                unreadable, len(hist_files),
            )
        if total_count >= 3 and ineffective_count == total_count:
            # 连续 ≥3 次压缩全部无效, 升级 broker
            _append_broker(
                "armor", "mark42.armor.compact.ineffective",
                f"连续 {ineffective_count}/{total_count} 次压缩未生效",
                "warn",
                trim_detail("建议检查 contextWindow 配置 / LLM 可用性 / compact 子命令", 160),
                {"ineffectiveCount": ineffective_count, "totalCount": total_count,
                 "preUsage": usage},
            )
            print(trim_detail(f"🚨 连续 {ineffective_count} 次压缩无效，升级 broker 事件", 120))
    except Exception as e:
        # 升级逻辑本身的错误不能影响主流程
        print(trim_detail(f"⚠️ 连续无效检查失败 (非致命): {e}", 140))


def _compress_audit_hook(index: dict[str, Any]) -> None:
    """Post-Compact Audit hook（异步，不阻塞）。

    2026-08-04 从 armor_compress 拆出。

    compact 完成（无论成功或失败）后自动核对关键信息是否丢失。
    即使 compact 失败也审计——因为部分执行可能已丢失信息。
    audit hook 失败不影响主流程。
    """
    try:
        from .interfaces import get_audit
        _audit = get_audit()
        if _audit is not None:
            _audit.audit_compact_async(
                pre_compact_snapshot={
                    "timestamp": _now_iso(),
                    "source": "pre-compact",
                    "compactTriggered": index.get("compactTriggered", False),
                    "compactError": index.get("compactError", ""),
                },
                post_compact_summary={
                    "timestamp": _now_iso(),
                    "source": "post-compact",
                },
            )
    except Exception as e:
        logger.warning("ignored error: %s", e)  # audit hook 失败不影响主流程


def armor_compress(dry_run: bool = False) -> dict[str, Any]:
    """触发智能压缩 — LLM 优先，启发式回退。
    正常模式：usage < WARN 阈值时跳过。
    dry_run 模式：无论如何都执行分析但只预览不写入（用于测试）。
    """
    check = armor_check()
    usage = check.get("usagePercent", 0)
    _ctx_window = check.get("contextWindow", DEFAULT_CONTEXT_WINDOW)
    _warn_pct, _alert_pct, _crit_pct = get_dynamic_thresholds(_ctx_window)
    if usage < _warn_pct and not dry_run:
        return {"action": "skip", "reason": f"使用率 {usage}% 未达阈值 {_warn_pct}%", "check": check}
    active = _find_active_session()
    session_messages = _read_session_tail(active) if active else []

    # 阶段 1: 压缩算法 hook (默认 disabled, 需 env 启用)
    algo_stats = armor_pre_compact_hook(session_messages, dry_run=dry_run)

    # 阶段 2: 构建记忆索引（LLM 优先 / 启发式回退）
    index = _compress_build_index(session_messages, usage, algo_stats, _alert_pct)

    index_path = ARMOR_STATE / "memory-index.json"
    actions_log = ARMOR_STATE / "actions.jsonl"
    history_dir = ARMOR_STATE / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    # 阶段 3: 事件上报
    _compress_log_events(usage, dry_run, index, _warn_pct)

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
    # ── 阶段 4: 压缩前置检查（冷却期 + 已压缩预检）──
    # 两个检查已拆到模块级 (2026-08-04)，命中则直接返回 skip 结果。
    # 背景（2026-07-29）：连续 compact 已压缩过的 session 是无效操作，
    # LLM 摘要 + 结构化元数据会让文件比原文还大。
    if not dry_run:
        cooldown_result = _compress_check_cooldown(index, index_path, check)
        if cooldown_result is not None:
            return cooldown_result

    if not dry_run and active:
        already_result = _compress_check_already_compacted(
            active, index, index_path, usage, check)
        if already_result is not None:
            return already_result


    # ── 修复 (2026-07-29): _get_context_window() 现在读 session 实际运行模型 ──
    # 之前读 primary config (doubao-seed-2.0-pro, 128K)，导致 GLM-5.2 (1M)
    # 的 usage 被算成 87.5%（实际只有 9%），触发不必要的 compact。
    # 现在 _get_context_window() 返回实际模型的 contextWindow，
    # armor_check() 算的 usage 已经是正确的百分比，不需要额外折扣。
    # 例如 GLM-5.2 (1M): 95K tokens -> usage = 9.5%，远低于 70% 阈值。

    # ── 平台探测期 + compact 锁 (2026-07-29) ──
    # Mark42 是跨平台铠甲，armor_compress 是最后自主救场能力。
    # 但不能与平台自带的 auto-compaction 冲突，所以加“平台优先探测”机制：
    # 1. 发现 usage >= 阈值时，先等一个探测期（默认 60 秒）
    # 2. 探测期内每 10 秒检查 usage 是否下降
    # 3. usage 下降了 -> 平台已 compact，Mark42 跳过
    # 4. 探测期结束 usage 仍无变化 -> 平台没反应，Mark42 自主出手
    # 5. 出手前再检查 compact 锁，避免与另一个 Mark42 实例撞车
    # 常量与三个子函数已提到模块级 (2026-08-04 拆分)

    if not dry_run and usage >= _warn_pct:
        # 1) 平台探测期
        platform_handled = _platform_compact_probe(usage, dry_run=dry_run)
        if platform_handled:
            index["compactTriggered"] = False
            index["compactError"] = "platform-auto-compaction-handled"
            index["compressionEffective"] = True
            index["preCompactBytes"] = None
            _save_json(index_path, index)
            return {"action": "skip-platform-handled", "reason": "平台 auto-compaction 已处理", "check": check}

        # 2) 获取 compact 锁
        if not _try_acquire_compact_lock():
            print("⏸️ compact 锁被占用，另一个 compact 正在进行，跳过")
            index["compactTriggered"] = False
            index["compactError"] = "compact-lock-busy"
            index["compressionEffective"] = False
            index["preCompactBytes"] = None
            _save_json(index_path, index)
            return {"action": "skip-locked", "reason": "另一个 compact 正在进行", "check": check}

        try:
            # ── 阶段 5: 实际压缩（Session Fence + CLI 调用）──
            # 已拆到模块级 _compress_run_compact_cli (2026-08-04)
            active_session = _find_active_session()
            if not active_session:
                print("⚠️ 未找到活跃会话，跳过 compact")
                index["compactTriggered"] = False
                index["compactError"] = "no-active-session"
                index["compressionEffective"] = False
                index["preCompactBytes"] = None
            else:
                _compress_run_compact_cli(active_session, index, usage)

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
            logger.warning("compact 触发失败: %s", e)
            index["compactTriggered"] = False
            index["compressionEffective"] = False
            index["compactError"] = str(e)
        finally:
            _release_compact_lock()
    # ⚠️ 必须在所有字段（含 compactTriggered/compactError）设置完后再写文件
    _save_json(index_path, index)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    _save_json(history_dir / f"memory-index-{ts}.json", index)

    # ── 阶段 6: 收尾（审计日志 + 无效升级 + audit hook）──
    # 三个子步骤已拆到模块级 (2026-08-04)
    _compress_write_action_log(index, index_path, actions_log, usage, dry_run)
    _compress_check_ineffective_escalation(index, history_dir, usage)
    if not dry_run:
        _compress_audit_hook(index)

    return {"action": "compress", "indexWritten": str(index_path), "preCompressUsage": usage, "check": check}


def _send_context_warn_event(usage: float) -> bool:
    """通过 openclaw CLI 向主会话注入上下文预警 systemEvent。

    Returns: True=发送成功, False=失败
    """
    import subprocess as _sp
    text = (
        f"⚠️ 上下文预警：当前会话上下文使用率已达 {usage}%。"
        f"建议尽快执行 /compact 主动压缩，避免上下文溢出导致 compaction 超时失败。"
    )
    try:
        result = _sp.run(
            [OPENCLAW_BIN, "system", "event",
             "--text", text,
             "--mode", "next-heartbeat",
             "--session-key", "agent:main:main"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            print(f"    📡 已向主会话发送上下文预警 ({usage}%)")
            return True
        else:
            print(f"    ⚠️ 预警发送失败: {result.stderr.strip()[:100]}")
            return False
    except Exception as e:
        print(f"    ⚠️ 预警发送异常: {e}")
        return False


def _inject_memory_index(index: dict[str, Any]) -> bool:
    """压缩后自动注入 memory-index 到主会话。

    将压缩时保留的关键信息通过 systemEvent 注入回会话，
    确保 AI 不会因为压缩丢失重要上下文。

    Returns: True=注入成功, False=失败
    """
    import subprocess as _sp
    preserved = index.get("preserved", {})

    # 构建注入文本
    lines = ["📝 [Mark42 memory-index] 压缩后自动注入关键信息："]

    # 用户身份
    user_id = preserved.get("userIdentity", "")
    if user_id:
        lines.append(f"- 用户身份: {user_id}")

    # 按角色保留的消息
    by_role = preserved.get("byRole", {})
    for role in ("user", "assistant"):
        msgs = by_role.get(role, [])
        if msgs:
            label = "用户" if role == "user" else "AI"
            lines.append(f"- {label}关键消息:")
            for msg in msgs[:3]:  # 最多 3 条
                preview = str(msg)[:200]
                lines.append(f"  - {preview}")

    # LLM 分析结果
    if index.get("modelGenerated"):
        active_projects = preserved.get("activeProjects", [])
        if active_projects:
            lines.append(f"- 活跃项目: {', '.join(str(p) for p in active_projects[:3])}")

    # 压缩信息
    strategy = index.get("strategyUsed", "unknown")
    pre_bytes = index.get("preCompactBytes", 0)
    post_bytes = index.get("postCompactBytes", 0)
    if pre_bytes and post_bytes:
        saved = pre_bytes - post_bytes
        lines.append(f"- 压缩: {strategy}, {pre_bytes//1024}KB -> {post_bytes//1024}KB (节省 {saved//1024}KB)")

    text = "\n".join(lines)

    try:
        result = _sp.run(
            [OPENCLAW_BIN, "system", "event",
             "--text", text,
             "--mode", "next-heartbeat",
             "--session-key", "agent:main:main"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            print(f"    📝 已注入 memory-index 到主会话 ({len(lines)} 行)")
            return True
        else:
            print(f"    ⚠️ memory-index 注入失败: {result.stderr.strip()[:100]}")
            return False
    except Exception as e:
        print(f"    ⚠️ memory-index 注入异常: {e}")
        return False


def armor_guard(interval_s: int = 300) -> None:
    """守护模式：每 N 秒检查一次，超阈值自主救场。

    设计哲学：平台优先，Mark42 兜底。
    - WARN 阈值(70%): 发送预警，进入观察
    - ALERT 阈值(85%): 调用 armor_compress 自主救场
    - armor_compress 内含平台探测期：先等 60 秒看平台是否自己 compact
    - 如果平台处理了 -> 跳过
    - 如果平台没反应 -> Mark42 出手
    - 出手前再检查 compact 锁，避免与另一个 compact 实例撞车
    """
    _warn_sent_at = None  # 上次发送预警的时间戳，避免重复刷屏
    _warn_cooldown = 600  # 预警冷却 10 分钟
    print(f"🛡️ 上下文铠甲守护模式启动（每 {interval_s}s 检查，平台优先 + 自主兜底）")
    try:
        while True:
            check = armor_check()
            usage = check.get("usagePercent", 0)
            _ctx_window = check.get("contextWindow", DEFAULT_CONTEXT_WINDOW)
            _warn_pct, _alert_pct, _crit_pct = get_dynamic_thresholds(_ctx_window)
            ts = datetime.now().strftime("%H:%M:%S")
            print(trim_detail(f"[{ts}] 上下文 {usage}% - {check.get('summary', '')}", 120))
            now_ts = time.time()
            should_warn = (
                usage >= _warn_pct
                and (_warn_sent_at is None or now_ts - _warn_sent_at >= _warn_cooldown)
            )
            if should_warn:
                print(f"[{ts}] 🟡 上下文达 WARN 阈值 ({usage}%)，发送预警")
                if _send_context_warn_event(usage):
                    _warn_sent_at = now_ts
            elif usage >= _alert_pct:
                # ALERT 阶段：触发 armor_compress 自主救场
                # armor_compress 内含平台探测期 + compact 锁
                print(f"[{ts}] 🟠 ALERT 阈值 ({usage}%)，启动自主救场")
                result = armor_compress()
                print(f"    -> {result.get('action')}")
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
        from mark42.compress_queue import CompressRequest, get_compress_queue
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
        from mark42.compress_queue import get_compress_queue
        return get_compress_queue().stats
    except ImportError as e:
        return {"error": f"queue module not available: {e}"}


# ── G10: LLM 压缩成功率统计 + fallback SLO 告警 ──

# SLO 阈值：fallback 率超过此值触发告警
FALLBACK_SLO_THRESHOLD = 0.20  # 20%


def armor_llm_stats(window: int = 50) -> dict[str, Any]:
    """统计最近 N 次压缩的 LLM 成功率 / fallback 率。

    从 actions.jsonl 读取历史记录，按 compactMethod 分类统计。
    - LLM 路径：compactMethod 含 'llm' 或 'smartcrush'
    - Fallback 路径：compactMethod 含 'fallback' 或 'maxlines' 或 'heuristic'
    - 其他（如 openclaw-sessions-compact）：单列
    """
    actions_log = ARMOR_STATE / "actions.jsonl"
    if not actions_log.exists():
        return {"total": 0, "llmSuccess": 0, "fallback": 0, "other": 0,
                "llmRate": 0.0, "fallbackRate": 0.0, "sloBreached": False}

    try:
        with open(actions_log) as f:
            lines = f.readlines()[-window:]
    except OSError as e:
        # 原实现只回 "读取失败" 而丢掉真实原因(权限/编码/磁盘),
        # 调用方与运维都无法判断该怎么处理
        logger.error("读取 actions.jsonl 失败: %s (%s)", actions_log, e)
        return {"error": f"读取 actions.jsonl 失败: {type(e).__name__}: {e}"}

    total = 0
    llm_success = 0
    fallback = 0
    other = 0
    errors = 0
    unparsed: list[str] = []

    for line in lines:
        try:
            d = json.loads(line.strip())
            if d.get("action") not in ("compress", "compress-dryrun"):
                continue
            total += 1
            method = d.get("compactMethod") or ""
            is_error = bool(d.get("compactError"))

            if "llm" in method.lower() or "smartcrush" in method.lower():
                llm_success += 1
            elif "fallback" in method.lower() or "maxlines" in method.lower() or "heuristic" in method.lower():
                fallback += 1
            elif is_error:
                errors += 1
            else:
                other += 1
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            # 统计口径必须可信: 坏样本静默丢弃会让 llm_rate 失真
            # (分母变小 -> 成功率虚高), 因此累计并在结束时告警
            unparsed.append(f"{type(e).__name__}")
            continue

    if unparsed:
        logger.warning(
            "压缩方法统计有 %d 份样本无法解析已跳过(%s), llm_rate 可能失真",
            len(unparsed), ", ".join(sorted(set(unparsed))),
        )

    effective_total = llm_success + fallback
    llm_rate = (llm_success / effective_total) if effective_total > 0 else 0.0
    fallback_rate = (fallback / effective_total) if effective_total > 0 else 0.0

    result = {
        "total": total,
        "llmSuccess": llm_success,
        "fallback": fallback,
        "other": other,
        "errors": errors,
        "llmRate": round(llm_rate * 100, 1),
        "fallbackRate": round(fallback_rate * 100, 1),
        "sloThreshold": FALLBACK_SLO_THRESHOLD * 100,
        "sloBreached": fallback_rate > FALLBACK_SLO_THRESHOLD,
        "window": min(window, len(lines)),
    }

    # SLO 告警：fallback 率超阈值时发 broker 事件
    if result["sloBreached"] and effective_total >= 5:
        try:
            from .utils import _append_broker
            _append_broker(
                "armor", "mark42.armor.llm.slo_breach",
                f"LLM fallback 率 {fallback_rate*100:.1f}% 超过 SLO 阈值 {FALLBACK_SLO_THRESHOLD*100:.0f}%",
                "warn",
                f"最近 {effective_total} 次压缩中 fallback {fallback} 次",
                {"fallbackRate": fallback_rate, "threshold": FALLBACK_SLO_THRESHOLD,
                 "window": effective_total},
            )
        except Exception as e:
            logger.warning("ignored error: %s", e)

    return result
