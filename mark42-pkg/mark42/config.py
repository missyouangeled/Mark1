"""Mark42 常量、配置系统模块。"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .log_setup import get_logger
from .user_config import load_config, get as cfg_get

logger = get_logger(__name__)

# ── 本地基础工具（不依赖 utils，避免循环导入） ──

def _conf_now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

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

# ── 用户配置 ──
_USER_CONFIG = load_config()

# ── 用户配置（从 ~/.config/mark42/config.toml 加载）──
_USER_CONFIG = load_config()

# ── 常量 ──────────────────────────────────────────────

# 工作区路径：env > config.toml > 默认值
WORKSPACE = Path(os.environ.get(
    "MARK42_WORKSPACE",
    cfg_get("paths", "workspace", str(Path.home() / ".openclaw" / "workspace"))
)).expanduser()
SCRIPTS = WORKSPACE / "scripts"

XDG_STATE = Path(os.environ.get("XDG_STATE_HOME", cfg_get("paths", "xdg_state", str(Path.home() / ".local" / "state"))))
MARK42_STATE = XDG_STATE / "openclaw" / "mark42"

# SCRATCH 路径（7/01 修： env 路由 + 数据盘 fallback）
# 优先级：MARK42_SCRATCH env > /mnt/data/openclaw/scratch > XDG_STATE fallback
# 避免非点点机器 /mnt/data 不存在时 hard-fail
SCRATCH = Path(os.environ.get(
    "MARK42_SCRATCH",
    cfg_get("paths", "scratch", str(XDG_STATE / "openclaw" / "scratch"))
))
if not SCRATCH.parent.exists():
    SCRATCH = XDG_STATE / "openclaw" / "scratch"

# 数据盘路径（优先 /mnt/data，回退 ~/.local/state）
# 数据目录优先用 SCRATCH 同级，不再硬编码 /mnt/data
DATA_ROOT = SCRATCH.parent / "mark42" if SCRATCH.parent.exists() else XDG_STATE / "openclaw" / "mark42"

ARMOR_STATE = MARK42_STATE / "armor"
ENGINE_STATE = MARK42_STATE / "engine"
HEAVY_STATE = MARK42_STATE / "heavy"

# 日志统一放到数据盘
LOG_DIR = DATA_ROOT / "logs"

BROKER_DIR = XDG_STATE / "openclaw" / "broker"
BROKER_EVENTS = BROKER_DIR / "events.jsonl"
BROKER_DIRTY = BROKER_DIR / ".dirty"
MARK42_BROKER_EVENTS = BROKER_DIR / "mark42-events.jsonl"

THRESHOLD_WARN = int(os.environ.get("MARK42_CTX_WARN_PCT", str(cfg_get("thresholds", "warn", 70))))
THRESHOLD_ALERT = int(os.environ.get("MARK42_CTX_ALERT_PCT", str(cfg_get("thresholds", "alert", 85))))
THRESHOLD_CRIT = int(os.environ.get("MARK42_CTX_CRIT_PCT", str(cfg_get("thresholds", "crit", 95))))

BYTES_PER_KTOKEN = int(os.environ.get("MARK42_CTX_BYTES_PER_KTOKEN", str(cfg_get("thresholds", "bytes_per_ktoken", 2048))))
DEFAULT_CONTEXT_WINDOW = 131072

BROKER_SOURCE = "mark42"

CONFIG_PATH = MARK42_STATE / "config.json"

# 【2026-07-13 新增】safe_call 错误日志路径（统一留痕，所有 @safe_call 包裹的函数失败都写这里）
ERRORS_FILE = MARK42_STATE / "errors.jsonl"
MAX_ERRORS_LINES = 1000  # 错误日志最多保留 1000 行，避免无限增长

MAX_LOG_AGE_DAYS = 30
MAX_BROKER_EVENTS_MB = 10
MAX_HISTORY_FILES = 50
MAX_ACTIONS_LINES = 500
MAX_DAEMON_LOG_MB = 50  # 单个 daemon 日志最大 50MB，超额截尾
MAX_DAEMON_LOG_LINES = 10000  # 单文件最大 10000 行

# ── 压缩算法配置 (阶段 1, 借鉴 Headroom) ──────────
# 2026-06-24 新增: 详见 docs/design/mark42-压缩方案-阶段1实施计划-20260624.md
# 默认全部 enabled=false (实验模式), 需手动开

ALGO_SMARTCRUSH_ENABLED = os.environ.get("MARK42_ALGO_SMARTCRUSH", "false").lower() == "true"
ALGO_SMARTCRUSH_MAX_ARRAY_LEN = 5
ALGO_SMARTCRUSH_MAX_STRING_LEN = 200
ALGO_SMARTCRUSH_MAX_DEPTH = 3
ALGO_SMARTCRUSH_MAX_NUMERIC_ARRAY_LEN = 50
ALGO_SMARTCRUSH_MIN_CONTENT_SIZE = 1024  # 只处理 > 1KB 的内容

# 实验模式总开关: --experiment=true 才走压缩算法
ALGO_EXPERIMENT_MODE = os.environ.get("MARK42_ALGO_EXPERIMENT", "false").lower() == "true"

# 压缩算法历史记录 (与 armor/actions.jsonl 同目录)
ALGO_HISTORY_DIR = ARMOR_STATE / "algo_history"

# ── 阶段 1 Day 4: 算法调度器接入控制 (2026-06-24) ──
# ALGO_USE_SCHEDULER: 是否让 armor_pre_compact_hook 走 algo_scheduler.process()
#                     而不是直接调 SmartCrusher。
#                     True = 走调度器（获得 PII 脱敏 + 大小分层 + 压缩护栏）。
#                     False = 直接调 SmartCrusher（Day 1-3 原始路径，仅供回退）。
ALGO_USE_SCHEDULER = os.environ.get("MARK42_ALGO_USE_SCHEDULER", "true").lower() == "true"

# ALGO_PII_ENABLED: 调度器内 PII 脱敏总开关。
#                   True = 压缩前自动脱敏邮箱/手机/身份证/信用卡/API key 等。
#                   False = 跳过脱敏（仅当确认数据安全时使用）。
ALGO_PII_ENABLED = os.environ.get("MARK42_ALGO_PII", "true").lower() == "true"

# ALGO_FAIL_SAFE: 调度器出错时是否回退到原文。
#                True = 错误静默返回原文（生产推荐）。
#                False = 错误抛出（调试用）。
ALGO_FAIL_SAFE = os.environ.get("MARK42_ALGO_FAIL_SAFE", "true").lower() == "true"

# ── 统一模型配置表 ─────────────────────────────────────
# Mark42 所有 AI 模型调用必须从此表读取，禁止在各模块硬编码模型名/参数。

MARK42_MODEL_TABLE: dict[str, dict[str, Any]] = {
    # 用途：上下文压缩时的 LLM 智能分析（armor._llm_analyze）
    "llmAnalyze": {
        "model": "doubao-seed-2.0-pro",
        "provider": "volcengine-agent",         # openclaw.json 中对应的 provider key
        "maxTokens": 2000,
        "temperature": 0.1,
        "timeout": 120,
        "baseUrlFallback": "https://ark.cn-beijing.volces.com/api/plan/v3",
        "endpoint": "/chat/completions",
    },
    # 用途：文本压缩时的 LLM 语义压缩（text_compressor method="llm" / llm_text_compressor）
    # Day 8 新增: 语义压缩 — 不同于"全对话分析"，这里是"压缩一段文本"
    # maxTokens 留大, 因为输出可能接近输入长度
    # temperature 0.0 保稳定
    "llmCompress": {
        "model": "doubao-seed-2.0-pro",
        "provider": "volcengine-agent",
        "maxTokens": 4000,
        "temperature": 0.0,
        "timeout": 90,
        "baseUrlFallback": "https://ark.cn-beijing.volces.com/api/plan/v3",
        "endpoint": "/chat/completions",
    },
    # 预留：未来新增 AI 用途时在此添加条目
    # "memoryIndex": { "model": "MiniMax-M3", ... },
    # "taskClassify": { "model": "MiniMax-M3", ... },
}

def get_model_config(config_key: str) -> dict[str, Any] | None:
    """读取模型配置。
    优先级：运行时 config.json > config.toml > MARK42_MODEL_TABLE 默认值。
    """
    # 1. 先从运行时 config.json 读
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            models = cfg.get("models", {})
            entry = models.get(config_key)
            if entry:
                if isinstance(entry, str):
                    return dict(MARK42_MODEL_TABLE.get(config_key, {}), model=entry)
                return dict(MARK42_MODEL_TABLE.get(config_key, {}), **entry)
        except Exception as e:
            logger.exception("Unhandled exception")
            pass

    # 2. 从 config.toml 读
    from .user_config import load_config as load_toml
    toml_cfg = load_toml()
    toml_models = toml_cfg.get("models", {})
    toml_entry = toml_models.get(config_key)
    if toml_entry and isinstance(toml_entry, dict):
        # 转换 snake_case -> camelCase（兼容旧格式）
        result = {}
        for k, v in toml_entry.items():
            result[k] = v
        # 确保有默认值
        defaults = MARK42_MODEL_TABLE.get(config_key, {})
        for dk, dv in defaults.items():
            if dk not in result:
                result[dk] = dv
        return result

    # 3. 回退到代码默认值
    return MARK42_MODEL_TABLE.get(config_key)

def resolve_model(config_key: str) -> dict[str, Any] | None:
    """解析最终模型调用参数。
    从统一配置表取模型名/参数，从 openclaw.json 取 API key/baseUrl。
    返回可直接用于 API 调用的参数字典。
    """
    model_entry = get_model_config(config_key)
    if not model_entry:
        return None
    
    provider_key = model_entry.get("provider", "")
    api_key = ""
    base_url = model_entry.get("baseUrlFallback", "")
    
    # 从 openclaw.json 取 API key 和 baseUrl
    openclaw_path = Path(os.environ.get("OPENCLAW_CONFIG", cfg_get("paths", "openclaw_config", str(Path.home() / ".openclaw" / "openclaw.json"))))
    if openclaw_path.exists():
        try:
            oc = json.loads(openclaw_path.read_text())
            provider = oc.get("models", {}).get("providers", {}).get(provider_key, {})
            api_key = provider.get("apiKey", "")
            if provider.get("baseUrl"):
                base_url = provider["baseUrl"]
        except Exception as e:
            logger.exception("Unhandled exception")
            pass
    
    if not api_key:
        return None
    
    return {
        "model": model_entry.get("model", ""),
        "apiKey": api_key,
        "baseUrl": base_url,
        "endpoint": model_entry.get("endpoint", "/v1/chat/completions"),
        "maxTokens": model_entry.get("maxTokens", 2000),
        "temperature": model_entry.get("temperature", 0.1),
        "timeout": model_entry.get("timeout", 45),
    }

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
        logger.info(f"⚙️ Mark42 已初始化（版本: {cfg.get('version', '?')})，使用 --config 修改")
        return
    cfg = {
        "version": "2.3.0",
        "initializedAt": _conf_now_iso(),
        "thresholds": {"warn": THRESHOLD_WARN, "alert": THRESHOLD_ALERT, "crit": THRESHOLD_CRIT},
        "contextWindow": DEFAULT_CONTEXT_WINDOW,
        "bytesPerKtoken": BYTES_PER_KTOKEN,
        "models": {
            "llmAnalyze": {
                "model": "MiniMax-M3",
                "provider": "minimax",
                "maxTokens": 2000,
                "temperature": 0.1,
                "timeout": 45,
            }
        },
        "daemon": {"scanInterval": 30, "autoArmorCompress": True, "autoTaskWatch": True},
        "heavy": {"autoDetect": "semi", "autoDetectEnabled": True},
    }
    _save_config(cfg)
    for d in [ARMOR_STATE, ENGINE_STATE, HEAVY_STATE]:
        d.mkdir(parents=True, exist_ok=True)
    (ARMOR_STATE / "history").mkdir(parents=True, exist_ok=True)
    logger.info("✅ Mark42 已初始化")
    logger.info(f"   配置: {CONFIG_PATH}")
    logger.info(f"   状态: {MARK42_STATE}")
    logger.info(f"   阈值: WARN={THRESHOLD_WARN}% ALERT={THRESHOLD_ALERT}% CRIT={THRESHOLD_CRIT}%")
    logger.info(f"   使用 'python3 scripts/mark42.py --config' 查看/修改")

def mark42_config() -> None:
    if not CONFIG_PATH.exists():
        logger.info("⚠️ 运行时配置未创建，使用用户配置文件 (~/.config/mark42/config.toml)")
    else:
        cfg = _load_config()
        logger.info(f"⚙️ 运行时配置:")
        logger.info(f"   版本: {cfg.get('version', '?')}")
        logger.info(f"   上下文窗口: {cfg.get('contextWindow', 0)/1000:.0f}K")
    # 显示用户配置文件内容摘要
    from .user_config import get_config_path, load_config as load_toml
    toml_cfg = load_toml()
    logger.info(f"\n📋 用户配置 (config.toml):")
    t = toml_cfg.get("thresholds", {})
    logger.info(f"   阈值: WARN={t.get('warn', 70)}% ALERT={t.get('alert', 85)}% CRIT={t.get('crit', 95)}%")
    p = toml_cfg.get("paths", {})
    logger.info(f"   工作区: {p.get('workspace', '~/.openclaw/workspace')}")
    logger.info(f"   OpenClaw: {p.get('openclaw_config', '~/.openclaw/openclaw.json')}")
    m = toml_cfg.get("models", {})
    for key, entry in m.items():
        if isinstance(entry, dict):
            logger.info(f"   模型 {key}: {entry.get('model', '?')} (provider: {entry.get('provider', '?')})")
    d = toml_cfg.get("daemon", {})
    logger.info(f"\n   守护进程:")
    logger.info(f"     扫描间隔: {d.get('scan_interval', 30)}s")
    logger.info(f"     自动压缩: {d.get('auto_armor_compress', True)}")
