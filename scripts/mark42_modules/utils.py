"""Mark42 工具函数模块。"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 活跃 session 的 .lock 文件最大年龄（秒），超过视为死 session
LOCK_MAX_AGE = 120

# 从 config 导入常量
from .config import (
    ARMOR_STATE, BROKER_DIR, BROKER_DIRTY, BROKER_SOURCE, BYTES_PER_KTOKEN,
    CONFIG_PATH, DEFAULT_CONTEXT_WINDOW, HEAVY_STATE, MARK42_STATE,
    MARK42_BROKER_EVENTS, MAX_ACTIONS_LINES, MAX_BROKER_EVENTS_MB, MAX_HISTORY_FILES,
    MAX_LOG_AGE_DAYS, SCRATCH, THRESHOLD_ALERT, THRESHOLD_CRIT,
    THRESHOLD_WARN, WORKSPACE, XDG_STATE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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
    event = {
        "ts": _now_iso(),
        "source": BROKER_SOURCE,
        "sourceView": source_view,
        "sourceEventType": event_type,
        "label": label,
        "level": level,
        "summary": summary,
        "metadata": metadata or {},
    }
    with open(str(MARK42_BROKER_EVENTS), "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def _run_script(name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(WORKSPACE / "scripts" / name), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)

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
    lock_files = sorted(sessions_dir.glob("*.jsonl.lock"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    for lock in lock_files:
        age = now - lock.stat().st_mtime
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
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None

def _estimate_tokens(session_path: Path) -> dict[str, Any]:
    try:
        size_bytes = session_path.stat().st_size
        tokens = size_bytes // BYTES_PER_KTOKEN * 1000
        file_mb = size_bytes / (1024 * 1024)
        return {"estimatedTokens": tokens, "fileSizeMB": round(file_mb, 2)}
    except OSError:
        return {"estimatedTokens": 0, "fileSizeMB": 0}

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
