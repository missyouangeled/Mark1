"""Mark42 工具函数模块。"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# 活跃 session 的 .lock 文件最大年龄（秒），超过视为死 session
LOCK_MAX_AGE = 120

# 从 config 导入常量
# 【N 修复 2026-06-30】删死 import: BROKER_DIRTY, MAX_BROKER_EVENTS_MB
# - BROKER_DIRTY: 仅 config.py 定义, utils import 后无人调 (所有 broker 事件都走 BROKER_DIR/events.jsonl)
# - MAX_BROKER_EVENTS_MB: 仅 logs.py 调, utils import 后无人调
from .config import (
    ARMOR_STATE, BROKER_DIR, BROKER_SOURCE, BYTES_PER_KTOKEN,
    CONFIG_PATH, DEFAULT_CONTEXT_WINDOW, HEAVY_STATE, MARK42_STATE,
    MARK42_BROKER_EVENTS, MAX_ACTIONS_LINES, MAX_HISTORY_FILES,
    MAX_LOG_AGE_DAYS, SCRATCH, THRESHOLD_ALERT, THRESHOLD_CRIT,
    THRESHOLD_WARN, WORKSPACE, XDG_STATE,
)
from .output_guard import trim_detail, trim_summary


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()

def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _append_broker(source_view: str, event_type: str, label: str, level: str,
                   summary: str, metadata: dict[str, Any] | None = None) -> None:
    BROKER_DIR.mkdir(parents=True, exist_ok=True)
    safe_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    event = {
        "ts": _now_iso(),
        "source": BROKER_SOURCE,
        "sourceView": source_view,
        "sourceEventType": event_type,
        "label": label,
        "level": level,
        "summary": trim_summary(summary),
        "metadata": safe_metadata,
    }
    if isinstance(event["metadata"], dict):
        for key in ("summary", "detail", "preview", "message"):
            if key in event["metadata"]:
                event["metadata"][key] = trim_detail(event["metadata"][key])
    with open(str(MARK42_BROKER_EVENTS), "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return -1.0

def _find_active_session() -> Path | None:
    """找当前活跃 session：优先用 .lock 文件，按 mtime 取最新。
    
    选择策略：
    1. 找所有 .jsonl.lock 文件，按修改时间排序
    2. 过滤掉 LOCK_MAX_AGE 秒内未更新的死 session
    3. 取最新的活跃 session，回退到对应 JSONL 文件
    4. 无 .lock 文件时回退到按 mtime 取最新 .jsonl
    """
    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    now = time.time()
    # 策略 A：.lock 文件
    lock_files = sorted(
        sessions_dir.glob("*.jsonl.lock"),
        key=_safe_mtime,
        reverse=True,
    )
    for lock in lock_files:
        mtime = _safe_mtime(lock)
        if mtime < 0:
            continue
        age = now - mtime
        if age > LOCK_MAX_AGE:
            continue  # 死 session
        jsonl_path = Path(str(lock).replace(".lock", ""))
        if jsonl_path.exists():
            return jsonl_path
    # 策略 B：回退——按 mtime 取最新 JSONL
    # 优先看 .reset / .deleted / .bak 后缀，排除; 再按 mtime 倒序
    candidates = [
        c for c in sessions_dir.glob("*.jsonl")
        if all(bad not in str(c) for bad in [".reset.", ".deleted.", ".bak-", ".trajectory."])
    ]
    candidates.sort(key=_safe_mtime, reverse=True)
    return candidates[0] if candidates else None

def _estimate_tokens(session_path: Path) -> dict[str, Any]:
    try:
        size_bytes = session_path.stat().st_size
        tokens = size_bytes // BYTES_PER_KTOKEN * 1000
        file_mb = size_bytes / (1024 * 1024)
        return {"estimatedTokens": tokens, "fileSizeMB": round(file_mb, 2)}
    except OSError:
        return {"estimatedTokens": 0, "fileSizeMB": 0}


# ── P1.1 修复: 自适应 token 估算 ─────────────────────────────
# 原公式 size_bytes // BYTES_PER_KTOKEN * 1000 在中文 chat 场景高估 6.6×
# (实测: 真实字符/token 比 ≈ 0.25, 而 BYTES_PER_KTOKEN=2048 假设是 0.5)
#
# 修复: 扫描 session 文件头部/尾部 N 条消息, 统计中英文字符比例,
#       用真实密度估算:
#       - 中文: 1.5 token/char (Claude/Qwen 平均)
#       - 英文: 0.25 token/char (BPE 估算)
#       - 数字/标点: 0.1 token/char
#       - JSON 控制符: 计入但 token 密度低
#
# 环境变量:
#   MARK42_TOKEN_ESTIMATE_MODE=simple|smart (默认 smart)
#     - simple: 沿用 BYTES_PER_KTOKEN 公式 (原行为, 避免重蹈)
#     - smart: 扫描真实字符, 按密度估算
#   MARK42_TOKEN_SCAN_LINES=N (默认 200) 扫描的尾部消息条数

import re as _re

_ZH_RE = _re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
_EN_RE = _re.compile(r'[a-zA-Z]')

# 不同语言的 token 密度 (经验值, 适用于 Claude/Qwen/DeepSeek/GPT-4)
_DENSITY = {
    'zh': 1.5,    # 中文字符: 1.5 token/char
    'en': 0.25,   # 英文字符: 0.25 token/char (BPE 压缩)
    'other': 0.1, # 数字/标点/JSON: 0.1 token/char
}

def _estimate_tokens_smart(session_path: Path, scan_lines: int = 200) -> dict[str, Any]:
    """自适应 token 估算: 扫描真实字符密度, 避免中文场景下 6× 高估。

    Args:
        session_path: session jsonl 文件路径
        scan_lines: 扫描最后多少行 (默认 200 条消息), 太少不准, 太多太慢

    Returns:
        {
          "estimatedTokens": int,      # 估算 token 总数
          "fileSizeMB": float,          # 实际文件大小
          "method": "smart",            # 估算方法
          "zhChars": int,               # 扫描到的中文字符数
          "enChars": int,               # 扫描到的英文字符数
          "otherChars": int,            # 其他字符数
          "scannedMessages": int,       # 实际扫描到的消息数
        }
    """
    result = {
        "estimatedTokens": 0,
        "fileSizeMB": 0,
        "method": "smart",
        "zhChars": 0,
        "enChars": 0,
        "otherChars": 0,
        "scannedMessages": 0,
    }
    try:
        size_bytes = session_path.stat().st_size
        result["fileSizeMB"] = round(size_bytes / (1024 * 1024), 2)

        if size_bytes == 0:
            return result

        # 从尾部读 scan_lines 行, 避免扫描 100MB 大文件
        try:
            scan_lines_n = int(os.environ.get("MARK42_TOKEN_SCAN_LINES", "200"))
        except (ValueError, TypeError):
            scan_lines_n = 200
        scan_lines_n = max(50, min(scan_lines_n, 1000))

        zh_chars = en_chars = other_chars = 0
        scanned = 0

        # 逆序读末尾 N 行
        try:
            with open(session_path, "rb") as f:
                f.seek(0, 2)
                pos = f.tell()
                chunk = b""
                lines_collected = []
                while pos > 0 and len(lines_collected) < scan_lines_n:
                    step = min(16384, pos)
                    pos -= step
                    f.seek(pos)
                    chunk = f.read(step) + chunk
                    raw_lines = chunk.split(b"\n")
                    chunk = raw_lines[0]
                    lines_collected = raw_lines[1:] + lines_collected
                lines_collected = lines_collected[-scan_lines_n:]
        except OSError:
            return result

        for ln in lines_collected:
            try:
                obj = json.loads(ln.strip())
            except (json.JSONDecodeError, ValueError):
                continue
            inner = obj.get("message") if isinstance(obj.get("message"), dict) else obj
            if not isinstance(inner, dict):
                continue
            content = inner.get("content", "")
            # 提取 text
            if isinstance(content, list):
                text_chunks = [c.get("text", "") for c in content if isinstance(c, dict)]
                text = " ".join(str(t) for t in text_chunks)
            elif isinstance(content, str):
                text = content
            else:
                continue
            if not text:
                continue
            # 统计字符密度
            for ch in text:
                if _ZH_RE.match(ch):
                    zh_chars += 1
                elif _EN_RE.match(ch):
                    en_chars += 1
                else:
                    other_chars += 1
            scanned += 1

        result["zhChars"] = zh_chars
        result["enChars"] = en_chars
        result["otherChars"] = other_chars
        result["scannedMessages"] = scanned

        # 推算总文件 chars = (扫描 chars / 扫描行数) × 总文件行数
        # 总文件行数 ≈ size_bytes / 平均每行字节 (智能粗估)
        try:
            avg_line_bytes = sum(len(ln) for ln in lines_collected[-scanned:]) / max(scanned, 1)
            total_lines_estimate = max(1, int(size_bytes / max(avg_line_bytes, 1)))
            if scanned > 0 and total_lines_estimate > scanned:
                # 外推: total = scanned_chars × (total_lines / scanned_lines)
                ratio = total_lines_estimate / scanned
                zh_total = int(zh_chars * ratio)
                en_total = int(en_chars * ratio)
                other_total = int(other_chars * ratio)
            else:
                zh_total, en_total, other_total = zh_chars, en_chars, other_chars
        except (ZeroDivisionError, ValueError):
            zh_total, en_total, other_total = zh_chars, en_chars, other_chars

        # token 估算 = zh × 1.5 + en × 0.25 + other × 0.1
        est_tokens = int(
            zh_total * _DENSITY['zh']
            + en_total * _DENSITY['en']
            + other_total * _DENSITY['other']
        )
        result["estimatedTokens"] = est_tokens
        return result
    except OSError:
        return result

# ── 公共文件扫描（统一跳过规则，供 heavy.preflight/detect/start 复用） ──

_SKIP_PATTERNS = ["__pycache__", ".pyc", ".git/", "node_modules/", ".meta/"]

def _list_project_files(path: Path) -> list[Path]:
    """扫描目录下所有非隐藏文件，跳过 __pycache__/.pyc/.git/node_modules/.meta。
    保证 heavy_preflight、heavy_detect、heavy_start 三处使用统一过滤规则。
    """
    if path.is_file():
        return [path]
    files = []
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        if f.name.startswith("."):
            continue
        path_str = str(f)
        if any(skip in path_str for skip in _SKIP_PATTERNS):
            continue
        files.append(f)
    return files


def _get_context_window() -> int:
    """获取当前会话上下文窗口大小。
    策略：直接从 openclaw.json 的 providers 中读取主会话当前模型对应的 contextWindow。
    优先级：
      1. 当前主会话的 model+provider（从 sessions_list RPC 或会话 jsonl 获取）
      2. openclaw.json agents.defaults.models.primary
      3. openclaw.json 第一个有 contextWindow 的模型
      4. config.json contextWindow
      5. DEFAULT_CONTEXT_WINDOW
    """
    oc_path = Path.home() / ".openclaw" / "openclaw.json"
    oc = {}
    if oc_path.exists():
        try:
            oc = json.loads(oc_path.read_text())
        except Exception:
            pass

    # 策略 1: 从 session jsonl 找当前 session 的 model（不再依赖 resolved）
    # OpenClaw 会话 jsonl 顶层 type=session 没有 model 字段，只在 message 的 usage 里有
    # 实际可靠路径：读 openclaw.json 的 agents.defaults.models.primary
    primary_model = None
    primary_provider = None
    try:
        agents = oc.get('agents', {})
        defaults = agents.get('defaults', {})
        primary = defaults.get('model', {}).get('primary', '')
        # primary 格式: "minimax/MiniMax-M3" 或 "deepseek/deepseek-v4-pro"
        if '/' in primary:
            primary_provider, primary_model = primary.split('/', 1)
    except Exception:
        pass

    if primary_model and primary_provider:
        cw = _lookup_context_window(oc, primary_provider, primary_model)
        if cw:
            return cw

    # 策略 2: 遍历 openclaw.json 所有 provider/models，取第一个有 contextWindow 的
    try:
        for pkey, pcfg in oc.get('models', {}).get('providers', {}).items():
            for m in pcfg.get('models', []):
                cw = m.get('contextWindow')
                if isinstance(cw, int) and cw > 0:
                    return cw
    except Exception:
        pass

    # 策略 3: config.json
    try:
        cfg = _load_json(CONFIG_PATH)
        cw = cfg.get("contextWindow", DEFAULT_CONTEXT_WINDOW)
        if isinstance(cw, int) and cw > 0:
            return cw
    except Exception:
        pass
    return DEFAULT_CONTEXT_WINDOW


def _lookup_context_window(oc: dict, provider: str, model_id: str) -> int | None:
    """在 openclaw.json 中查找指定 provider.model 的 contextWindow。"""
    pcfg = oc.get('models', {}).get('providers', {}).get(provider, {})
    for m in pcfg.get('models', []):
        if m.get('id') == model_id or m.get('name') == model_id:
            cw = m.get('contextWindow')
            if isinstance(cw, int) and cw > 0:
                return cw
    return None
