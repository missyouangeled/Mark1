"""Mark42 常量、配置系统模块。"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ── 本地基础工具（不依赖 utils，避免循环导入） ──

def _conf_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _conf_load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def _conf_save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── 常量 ──────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parent.parent.parent
SCRIPTS = WORKSPACE / "scripts"
SCRATCH = Path("/mnt/data/openclaw/scratch")

XDG_STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
MARK42_STATE = XDG_STATE / "openclaw" / "mark42"
ARMOR_STATE = MARK42_STATE / "armor"
ENGINE_STATE = MARK42_STATE / "engine"
HEAVY_STATE = MARK42_STATE / "heavy"

BROKER_DIR = XDG_STATE / "openclaw" / "broker"
BROKER_EVENTS = BROKER_DIR / "events.jsonl"
BROKER_DIRTY = BROKER_DIR / ".dirty"
MARK42_BROKER_EVENTS = BROKER_DIR / "mark42-events.jsonl"

THRESHOLD_WARN = int(os.environ.get("MARK42_CTX_WARN_PCT", "70"))
THRESHOLD_ALERT = int(os.environ.get("MARK42_CTX_ALERT_PCT", "85"))
THRESHOLD_CRIT = int(os.environ.get("MARK42_CTX_CRIT_PCT", "95"))

BYTES_PER_KTOKEN = int(os.environ.get("MARK42_CTX_BYTES_PER_KTOKEN", str(14 * 1024)))
DEFAULT_CONTEXT_WINDOW = 131072

BROKER_SOURCE = "mark42"

CONFIG_PATH = MARK42_STATE / "config.json"

MAX_LOG_AGE_DAYS = 30
MAX_BROKER_EVENTS_MB = 10
MAX_HISTORY_FILES = 50
MAX_ACTIONS_LINES = 500

# ── 配置系统 ────────────────────────────────────────────

def _load_config() -> dict[str, any]:  # noqa
    if CONFIG_PATH.exists():
        return _conf_load_json(CONFIG_PATH)
    return {}

def _save_config(cfg: dict[str, any]) -> None:  # noqa
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conf_save_json(CONFIG_PATH, cfg)

def mark42_init() -> None:
    if CONFIG_PATH.exists():
        cfg = _load_config()
        print(f"⚙️ Mark42 已初始化（版本: {cfg.get('version', '?')})，使用 --config 修改")
        return
    cfg = {
        "version": "2.2",
        "initializedAt": _conf_now_iso(),
        "thresholds": {"warn": THRESHOLD_WARN, "alert": THRESHOLD_ALERT, "crit": THRESHOLD_CRIT},
        "contextWindow": DEFAULT_CONTEXT_WINDOW,
        "bytesPerKtoken": BYTES_PER_KTOKEN,
        "models": {"llmAnalyze": "deepseek-v4-pro", "llmProvider": "deepseek"},
        "daemon": {"scanInterval": 30, "autoArmorCompress": True, "autoTaskWatch": True},
    }
    _save_config(cfg)
    for d in [ARMOR_STATE, ENGINE_STATE, HEAVY_STATE]:
        d.mkdir(parents=True, exist_ok=True)
    (ARMOR_STATE / "history").mkdir(parents=True, exist_ok=True)
    print("✅ Mark42 已初始化")
    print(f"   配置: {CONFIG_PATH}")
    print(f"   状态: {MARK42_STATE}")
    print(f"   阈值: WARN={THRESHOLD_WARN}% ALERT={THRESHOLD_ALERT}% CRIT={THRESHOLD_CRIT}%")
    print(f"   使用 'python3 scripts/mark42.py --config' 查看/修改")

def mark42_config() -> None:
    if not CONFIG_PATH.exists():
        print("❌ 尚未初始化，请先运行: mark42.py --init")
        return
    cfg = _load_config()
    print("⚙️ Mark42 配置:\n")
    print(f"   版本: {cfg.get('version', '?')}")
    print(f"   初始化于: {cfg.get('initializedAt', '?')}")
    print(f"   上下文窗口: {cfg.get('contextWindow', 0)/1000:.0f}K")
    print(f"   字节/KToken: {cfg.get('bytesPerKtoken', '?')}")
    print(f"\n   阈值:")
    t = cfg.get("thresholds", {})
    print(f"     WARN: {t.get('warn', '?')}%  |  ALERT: {t.get('alert', '?')}%  |  CRIT: {t.get('crit', '?')}%")
    print(f"\n   模型:")
    m = cfg.get("models", {})
    print(f"     LLM 分析: {m.get('llmAnalyze', '?')}  ({m.get('llmProvider', '?')})")
    print(f"\n   守护模式:")
    d = cfg.get("daemon", {})
    print(f"     扫描间隔: {d.get('scanInterval', '?')}s")
    print(f"     自动压缩: {d.get('autoArmorCompress', '?')}")
    print(f"     自动监控: {d.get('autoTaskWatch', '?')}")
