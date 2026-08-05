"""Mark42 常量、配置系统模块。"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 有效配置解析：单一入口 + 来源追踪 (P2-7) ─────────────
#
# 背景：配置向导（mark42 init）会把 ``[paths]`` / ``[thresholds]`` /
# ``[models]`` 写进 ``~/.config/mark42/config.toml``，文档也告诉用户可以改。
# 但核心模块一直只读环境变量与硬编码常量 —— 形成双轨制：
# 用户把 TOML 里 warn 改成 11，``load_config()`` 读到的是 11，
# 而运行时 ``THRESHOLD_WARN`` 仍为 70。向导让用户填的东西全是废的。
#
# 职责划分（本次明确）：
#   TOML  = 用户**期望**配置（可手改，人看的）
#   环境变量 = 部署/临时覆盖（优先于 TOML，方便 systemd 与测试）
#   state JSON = 内部**运行状态**（程序写，不当用户配置）
#
# 优先级：环境变量 > TOML > 代码默认值。

_CONFIG_SOURCES: dict[str, str] = {}


def _read_toml_value(section: str, key: str) -> Any:
    """读 TOML 单项配置。任何异常都不得影响常量初始化。

    本函数在**模块 import 期**被调用。TOML 写坏、权限不对、
    甚至 user_config 自己出错，都只能降级到默认值，
    绝不能让整个包导入失败。
    """
    try:
        # 关键：用 get_user_only 而非 get —— load_config() 会先 merge 包内
        # 默认模板，"读到值"不等于"用户真的配了这项"，否则会把代码默认值
        # 误标成 toml: 来源。
        from .user_config import get_user_only as _toml_get

        return _toml_get(section, key, None)
    except Exception:
        logger.debug("读 TOML [%s] %s 失败，降级为默认值", section, key, exc_info=True)
        return None


def _resolve_int(
    *, env: str, section: str, key: str, default: int, name: str
) -> int:
    """解析整型配置：环境变量 > TOML > 默认值，并记录生效来源。"""
    raw_env = os.environ.get(env)
    if raw_env is not None and str(raw_env).strip():
        try:
            value = int(str(raw_env).strip())
            _CONFIG_SOURCES[name] = f"env:{env}"
            return value
        except (TypeError, ValueError):
            logger.warning(
                "环境变量 %s=%r 不是合法整数，忽略并继续回退", env, raw_env
            )

    toml_value = _read_toml_value(section, key)
    if toml_value is not None:
        try:
            value = int(toml_value)
            _CONFIG_SOURCES[name] = f"toml:[{section}].{key}"
            return value
        except (TypeError, ValueError):
            logger.warning(
                "TOML [%s] %s=%r 不是合法整数，忽略并回退默认值",
                section, key, toml_value,
            )

    _CONFIG_SOURCES[name] = "default"
    return default


def _resolve_path(
    *, env: str, section: str, key: str, default: str, name: str
) -> Path:
    """解析路径配置：环境变量 > TOML > 默认值，并记录生效来源。"""
    raw_env = os.environ.get(env)
    if raw_env is not None and str(raw_env).strip():
        _CONFIG_SOURCES[name] = f"env:{env}"
        return Path(str(raw_env)).expanduser()

    toml_value = _read_toml_value(section, key)
    if isinstance(toml_value, str) and toml_value.strip():
        _CONFIG_SOURCES[name] = f"toml:[{section}].{key}"
        return Path(toml_value).expanduser()

    _CONFIG_SOURCES[name] = "default"
    return Path(default).expanduser()


def get_config_source(name: str) -> str:
    """返回某项有效配置的**生效来源**，例如 ``env:MARK42_CTX_WARN_PCT``、
    ``toml:[thresholds].warn``、``default``。未知项返回 ``unknown``。"""
    return _CONFIG_SOURCES.get(name, "unknown")


def get_effective_config() -> dict[str, Any]:
    """返回最终生效的配置快照 + 逐项来源（P2-7 唯一权威入口）。

    用于回答“我改了 TOML 到底生没生效”这类问题：
    ``values`` 是运行时真正在用的值，``sources`` 说明每项从哪里来。
    """
    values = {
        "paths.workspace": str(WORKSPACE),
        "paths.scratch": str(SCRATCH),
        "paths.xdg_state": str(XDG_STATE),
        "paths.openclaw_config": str(_effective_openclaw_config_path()),
        "thresholds.warn": THRESHOLD_WARN,
        "thresholds.alert": THRESHOLD_ALERT,
        "thresholds.crit": THRESHOLD_CRIT,
        "thresholds.bytes_per_ktoken": BYTES_PER_KTOKEN,
    }
    return {
        "values": values,
        "sources": {
            **{key: get_config_source(key) for key in values},
            # 路径类中唯一不由本模块解析的项，来源单独推导
            "paths.openclaw_config": _openclaw_config_source(),
        },
    }


def _effective_openclaw_config_path() -> Path:
    """openclaw.json 路径——转发给 P2-16 建的统一解析器，不重复实现。"""
    try:
        from .user_config import get_openclaw_config_path

        return get_openclaw_config_path()
    except Exception:  # pragma: no cover - 防御分支
        return Path("~/.openclaw/openclaw.json").expanduser()


def _openclaw_config_source() -> str:
    """openclaw.json 路径的生效来源（与 P2-16 解析器的优先级保持一致）。"""
    if os.environ.get("OPENCLAW_CONFIG", "").strip():
        return "env:OPENCLAW_CONFIG"
    toml_value = _read_toml_value("paths", "openclaw_config")
    if isinstance(toml_value, str) and toml_value.strip():
        return "toml:[paths].openclaw_config"
    return "default"

# ── 版本单一来源 ────────────────────────────────────────
# 【2026-08-03 修复】此前 __init__.py / pyproject.toml / CLI --version / mark42_init()
# 四处各自硬编码版本号，导致 mark42_init() 写入 2.3.0 而实际安装版本是 2.8.1，
# status 面板长期显示错误版本。现统一由 get_version() 提供，禁止再新增硬编码常量。


def get_version() -> str:
    """返回 Mark42 当前版本号（唯一权威来源）。

    优先读已安装包的元数据（importlib.metadata），保证与 pyproject.toml 一致；
    源码开发态（未安装）回退到 mark42.__version__。
    """
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version

        try:
            return _pkg_version("mark42")
        except PackageNotFoundError:
            logger.debug("mark42 包元数据未找到，回退到 __version__")
    except Exception as e:  # pragma: no cover - importlib.metadata 缺失属极端环境
        logger.debug("读取包元数据失败，回退到 __version__: %s", e)
    try:
        from . import __version__

        return str(__version__)
    except Exception as e:  # pragma: no cover
        logger.debug("读取 __version__ 失败: %s", e)
        return "unknown"


# 运行时配置 schema 版本。与程序版本无关，仅用于判断是否需要迁移旧配置。
CONFIG_SCHEMA_VERSION = 2

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
    """原子写入 JSON。

    【2026-08-03 修复】原实现直接 open(path, "w") 截断后再 json.dump()，
    进程在写入过程中被 kill/OOM/断电会留下半截文件，下次读取直接 JSONDecodeError，
    状态静默丢失。现改为同目录临时文件 + fsync + os.replace() 原子替换：
    要么是完整旧内容，要么是完整新内容，不存在中间态。
    """
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        # 保留原文件权限，避免原子替换后权限被 mkstemp 的 0600 覆盖
        if path.exists():
            try:
                os.chmod(tmp_name, path.stat().st_mode & 0o7777)
            except OSError:
                pass
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass

# ── 常量 ──────────────────────────────────────────────

# 【2026-08-03 修复】MARK42_WORKSPACE / MARK42_STATE_DIR / MARK42_LOG_DIR 三个环境变量
# 文档和 systemd unit 都声明了，installer.py / watchdog.py 也在用，
# 但 config.py 之前完全不读，导致 unit 里的 Environment= 完全无效，
# 用户以为做了路径隔离实际上没有。现统一优先级：环境变量 > 平台默认。
WORKSPACE = _resolve_path(
    env="MARK42_WORKSPACE", section="paths", key="workspace",
    default=str(Path(__file__).resolve().parent.parent.parent),
    name="paths.workspace",
)
SCRIPTS = WORKSPACE / "scripts"

# OpenClaw 可执行文件路径（动态查找，不硬编码）
import shutil as _shutil

OPENCLAW_BIN = _shutil.which("openclaw") or str(Path.home() / ".npm-global" / "bin" / "openclaw")

XDG_STATE = _resolve_path(
    env="XDG_STATE_HOME", section="paths", key="xdg_state",
    default=str(Path.home() / ".local" / "state"), name="paths.xdg_state",
)
# MARK42_STATE_DIR 可直接指定状态目录，优先于 XDG 推导
MARK42_STATE = Path(
    os.environ.get("MARK42_STATE_DIR") or str(XDG_STATE / "openclaw" / "mark42")
).expanduser()

# SCRATCH 路径（7/01 修： env 路由 + 数据盘 fallback）
# 优先级：MARK42_SCRATCH env > TOML [paths].scratch
#         > $MARK42_DATA_MOUNT/openclaw/scratch > XDG_STATE fallback
# 避免非点点机器数据盘不存在时 hard-fail
# 数据盘挂载点：可用 MARK42_DATA_MOUNT env 覆盖（默认 /mnt/data）
DATA_MOUNT = Path(os.environ.get("MARK42_DATA_MOUNT", "/mnt/data"))
# 【P2-7】纳入 TOML [paths].scratch。注意仍要保留数据盘 fallback：
# 显式指定（env/TOML）的路径按用户意图直接采用，不做存在性回退；
# 只有走「数据盘默认值」时才在数据盘缺失时回退到 XDG_STATE。
SCRATCH = _resolve_path(
    env="MARK42_SCRATCH", section="paths", key="scratch",
    default=str(DATA_MOUNT / "openclaw" / "scratch"), name="paths.scratch",
)
if get_config_source("paths.scratch") == "default" and not SCRATCH.parent.parent.exists():
    SCRATCH = XDG_STATE / "openclaw" / "scratch"
    _CONFIG_SOURCES["paths.scratch"] = "default:xdg-fallback"

# 数据盘路径（优先 DATA_MOUNT，回退 ~/.local/state）
DATA_ROOT = DATA_MOUNT / "openclaw" / "mark42"
if not DATA_ROOT.parent.parent.exists():
    DATA_ROOT = XDG_STATE / "openclaw" / "mark42"

# 会话快照根目录（数据盘，回退 XDG_STATE）
SESSION_BACKUP_ROOT = DATA_MOUNT / "openclaw" / "session-backup"
if not SESSION_BACKUP_ROOT.parent.parent.exists():
    SESSION_BACKUP_ROOT = XDG_STATE / "openclaw" / "session-backup"

ARMOR_STATE = MARK42_STATE / "armor"
ENGINE_STATE = MARK42_STATE / "engine"
HEAVY_STATE = MARK42_STATE / "heavy"

# ArcLock 配置文件路径
ARCLOCK_CONFIG_PATH = MARK42_STATE / "arclock.yaml"

# 日志统一放到数据盘（MARK42_LOG_DIR 可覆盖）
LOG_DIR = Path(
    os.environ.get("MARK42_LOG_DIR") or str(DATA_ROOT / "logs")
).expanduser()

BROKER_DIR = XDG_STATE / "openclaw" / "broker"
BROKER_EVENTS = BROKER_DIR / "events.jsonl"
BROKER_DIRTY = BROKER_DIR / ".dirty"
MARK42_BROKER_EVENTS = BROKER_DIR / "mark42-events.jsonl"

# 上下文阈值 -- 基准值，实际使用时按模型上下文窗口动态调整
# 小窗口 (128K): 用基准值 70/85/95
# 大窗口 (1M):   更早介入 60/75/90 (context rot 更严重)
# 通过 get_dynamic_thresholds(context_window) 动态计算
# 【P2-7】改走 _resolve_int：环境变量 > TOML [thresholds] > 代码默认值。
# 原实现只读环境变量，用户改 TOML 完全无效。
THRESHOLD_WARN = _resolve_int(
    env="MARK42_CTX_WARN_PCT", section="thresholds", key="warn",
    default=70, name="thresholds.warn",
)
THRESHOLD_ALERT = _resolve_int(
    env="MARK42_CTX_ALERT_PCT", section="thresholds", key="alert",
    default=85, name="thresholds.alert",
)
THRESHOLD_CRIT = _resolve_int(
    env="MARK42_CTX_CRIT_PCT", section="thresholds", key="crit",
    default=95, name="thresholds.crit",
)

# 动态阈值计算参数
# Anthropic 研究表明 context rot 在大窗口下更严重，应更早介入
# 参考工厂实践：Claude Code 95%，社区建议 60-80%
_DYNAMIC_WARN_BASE = 70      # 基准 WARN 阈值 (128K 窗口)
_DYNAMIC_WARN_LARGE = 60     # 大窗口 (>=500K) 的 WARN 阈值
_DYNAMIC_ALERT_BASE = 85
_DYNAMIC_ALERT_LARGE = 75
_DYNAMIC_CRIT_BASE = 95
_DYNAMIC_CRIT_LARGE = 90
_LARGE_WINDOW_THRESHOLD = 500000  # 超过 500K tokens 视为大窗口


def get_dynamic_thresholds(context_window: int) -> tuple[int, int, int]:
    """根据模型上下文窗口动态计算阈值。

    小窗口 (128K): WARN=70 ALERT=85 CRIT=95 (基准值)
    大窗口 (1M):   WARN=60 ALERT=75 CRIT=90 (更早介入，context rot 更严重)

    中间值线性插值。

    Args:
        context_window: 模型的上下文窗口大小 (tokens)

    Returns:
        (warn_pct, alert_pct, crit_pct)
    """
    if context_window <= 0:
        return THRESHOLD_WARN, THRESHOLD_ALERT, THRESHOLD_CRIT

    if context_window >= _LARGE_WINDOW_THRESHOLD:
        # 大窗口：更早介入
        # 超过 1M 时进一步降低
        if context_window >= 1_000_000:
            return _DYNAMIC_WARN_LARGE, _DYNAMIC_ALERT_LARGE, _DYNAMIC_CRIT_LARGE
        # 500K-1M 之间线性插值
        ratio = (context_window - _LARGE_WINDOW_THRESHOLD) / (1_000_000 - _LARGE_WINDOW_THRESHOLD)
        warn = int(_DYNAMIC_WARN_BASE - (_DYNAMIC_WARN_BASE - _DYNAMIC_WARN_LARGE) * ratio)
        alert = int(_DYNAMIC_ALERT_BASE - (_DYNAMIC_ALERT_BASE - _DYNAMIC_ALERT_LARGE) * ratio)
        crit = int(_DYNAMIC_CRIT_BASE - (_DYNAMIC_CRIT_BASE - _DYNAMIC_CRIT_LARGE) * ratio)
        return warn, alert, crit
    else:
        # 小窗口：用基准值
        return THRESHOLD_WARN, THRESHOLD_ALERT, THRESHOLD_CRIT

BYTES_PER_KTOKEN = _resolve_int(
    env="MARK42_CTX_BYTES_PER_KTOKEN", section="thresholds",
    key="bytes_per_ktoken", default=2 * 1024, name="thresholds.bytes_per_ktoken",
)
DEFAULT_CONTEXT_WINDOW = 131072

BROKER_SOURCE = "mark42"

CONFIG_PATH = MARK42_STATE / "config.json"

# Loop 模板配置文件路径
LOOP_TEMPLATES_PATH = Path(__file__).resolve().parent / "loop_templates.yaml"
USER_LOOP_TEMPLATES_PATH = WORKSPACE / "loop_templates.yaml"

# 【2026-07-13 新增】safe_call 错误日志路径（统一留痕，所有 @safe_call 包裹的函数失败都写这里）
ERRORS_FILE = MARK42_STATE / "errors.jsonl"
MAX_ERRORS_LINES = 1000  # 错误日志最多保留 1000 行，避免无限增长

MAX_LOG_AGE_DAYS = 30
MAX_BROKER_EVENTS_MB = 10
MAX_HISTORY_FILES = 50
MAX_ACTIONS_LINES = 500
MAX_DAEMON_LOG_MB = 50  # 单个 daemon 日志最大 50MB，超额截尾
# 【2026-08-03 修复】文档声明了 MARK42_MAX_DAEMON_LOG_LINES 但代码硬编码，现支持覆盖
MAX_DAEMON_LOG_LINES = int(os.environ.get("MARK42_MAX_DAEMON_LOG_LINES", "10000"))

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
    """从 Mark42 统一模型配置表读取指定用途的配置。
    优先读运行时 config.json，不存在时回退到代码中的 MARK42_MODEL_TABLE 默认值。
    """
    # 先尝试从运行时配置读取
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            models = cfg.get("models", {})
            entry = models.get(config_key)
            if entry:
                # 兼容旧格式：如果是纯字符串则包装
                if isinstance(entry, str):
                    return dict(MARK42_MODEL_TABLE.get(config_key, {}), model=entry)
                return dict(MARK42_MODEL_TABLE.get(config_key, {}), **entry)
        except Exception as e:
            logger.warning("ignored error: %s", e)
    # 回退到代码默认值
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
    # 路径走统一解析器（P2-16）。此处兼容两种加载方式：
    # 作为包模块（mark42.config）时走相对导入；
    # 被当顶层模块加载（llm_text_compressor 的 `from config import ...`
    # 兵底路径）时相对导入会抛 ImportError，退回绝对导入。
    try:
        from .user_config import get_openclaw_config_path
    except ImportError:  # pragma: no cover - 无包上下文的兵底分支
        try:
            from mark42.user_config import get_openclaw_config_path
        except ImportError:
            from user_config import get_openclaw_config_path

    openclaw_path = get_openclaw_config_path()
    if openclaw_path.exists():
        try:
            oc = json.loads(openclaw_path.read_text())
            provider = oc.get("models", {}).get("providers", {}).get(provider_key, {})
            api_key = provider.get("apiKey", "")
            if provider.get("baseUrl"):
                base_url = provider["baseUrl"]
        except Exception as e:
            logger.warning("ignored error: %s", e)

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

def _load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return _conf_load_json(CONFIG_PATH)
    return {}

def _save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conf_save_json(CONFIG_PATH, cfg)


def _migrate_config_if_needed(cfg: dict[str, Any]) -> dict[str, Any]:
    """把旧版运行时配置迁移到新 schema。

    【2026-08-03 新增】旧配置里的 "version" 字段被误当成程序版本使用，
    导致 status 面板长期显示初始化时写死的 2.3.0。迁移策略是保守的：
    - 只改 schema 相关字段，不动用户自定义的阈值/模型/daemon 配置；
    - 迁移前生成一次 .bak 备份，便于回滚；
    - 旧 "version" 值挪到 legacyVersion 留痕，不直接丢弃。

    【2026-08-05 修复 P3-6】原实现只判断“等不等于当前版本”，于是
    **任何非当前版本都会进迁移** —— 包括 schema 3/4/99 等**未来**版本，
    也会被改写成当前版本并写回磁盘。后果：新版本写的配置被旧版
    程序读一次就静默降级，新版本才认识的字段语义也可能被误解。

    现行为：
    - schema < 当前：正常向上迁移（原行为不变）
    - schema == 当前：直接返回
    - schema > 当前：**拒绞降级与写回**，只告警并原样返回（只读兼容）。
      需要强行降级时可设 MARK42_ALLOW_SCHEMA_DOWNGRADE=1 显式开启。
    """
    if not isinstance(cfg, dict) or not cfg:
        return cfg

    current = cfg.get("configSchemaVersion")
    if current == CONFIG_SCHEMA_VERSION:
        return cfg

    # 未来 schema：默认只读，不降级、不写回
    if isinstance(current, int) and current > CONFIG_SCHEMA_VERSION:
        if os.environ.get("MARK42_ALLOW_SCHEMA_DOWNGRADE", "").strip() not in (
            "1", "true", "True", "yes",
        ):
            logger.warning(
                "配置 schema v%s 高于本程序支持的 v%s，已按**只读**处理："
                "不降级、不写回。请升级 Mark42；确需强行降级请设置 "
                "MARK42_ALLOW_SCHEMA_DOWNGRADE=1。",
                current, CONFIG_SCHEMA_VERSION,
            )
            return cfg
        logger.warning(
            "MARK42_ALLOW_SCHEMA_DOWNGRADE 已开启，将把 schema v%s 强行降为 v%s，"
            "新版本特有字段可能被误解",
            current, CONFIG_SCHEMA_VERSION,
        )

    migrated = dict(cfg)
    legacy_version = migrated.pop("version", None)
    migrated["configSchemaVersion"] = CONFIG_SCHEMA_VERSION
    if legacy_version is not None:
        migrated.setdefault("legacyVersion", legacy_version)
    migrated["migratedAt"] = _conf_now_iso()
    migrated["migratedByVersion"] = get_version()

    try:
        if CONFIG_PATH.exists():
            backup = CONFIG_PATH.with_name(
                f"{CONFIG_PATH.name}.pre-schema{CONFIG_SCHEMA_VERSION}.bak"
            )
            if not backup.exists():
                backup.write_text(
                    json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
                )
        _save_config(migrated)
        logger.info(
            "配置已迁移到 schema v%s（旧 version=%s）",
            CONFIG_SCHEMA_VERSION,
            legacy_version,
        )
    except OSError as e:
        logger.warning("配置迁移写入失败，继续使用内存中的迁移结果: %s", e)
    return migrated

def mark42_init() -> None:
    if CONFIG_PATH.exists():
        cfg = _migrate_config_if_needed(_load_config())
        print(f"⚙️ Mark42 已初始化（版本: {get_version()}），使用 --config 修改")
        return
    cfg = {
        "configSchemaVersion": CONFIG_SCHEMA_VERSION,
        "initializedAt": _conf_now_iso(),
        "initializedWithVersion": get_version(),
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
    print("✅ Mark42 已初始化")
    print(f"   版本: {get_version()}")
    print(f"   配置: {CONFIG_PATH}")
    print(f"   状态: {MARK42_STATE}")
    print(f"   阈值: WARN={THRESHOLD_WARN}% ALERT={THRESHOLD_ALERT}% CRIT={THRESHOLD_CRIT}%")
    print("   使用 'mark42 --config' 查看/修改")

def print_effective_config() -> None:
    """打印**运行时真正生效**的配置及其来源（P2-7）。

    这一段回答的是"我改了 TOML 到底生没生效"。
    下方 state JSON 段落展示的是内部运行状态，两者职责不同，不要混看。
    """
    eff = get_effective_config()
    print("\n   生效配置（含来源追踪）:")
    print("     " + "-" * 62)
    for key, value in eff["values"].items():
        source = eff["sources"].get(key, "unknown")
        print(f"     {key:<32} {str(value):<22} <- {source}")
    print("     " + "-" * 62)
    print("     来源优先级: env 环境变量 > toml 用户配置 > default 代码默认值")
    try:
        from .user_config import get_config_path as _toml_path

        print(f"     用户 TOML 路径: {_toml_path()}")
    except Exception:  # pragma: no cover - 防御分支
        logger.debug("无法解析用户 TOML 路径，跳过该行显示", exc_info=True)


def mark42_config() -> None:
    if not CONFIG_PATH.exists():
        print("❌ 尚未初始化，请先运行: mark42.py --init")
        print("（下面仍显示当前生效配置，便于排查 TOML 是否被读取）")
        print_effective_config()
        return
    cfg = _load_config()
    print("⚙️ Mark42 配置:\n")
    print(f"   版本: {get_version()}")
    print(f"   配置 schema: v{cfg.get('configSchemaVersion', 1)}")
    print(f"   初始化于: {cfg.get('initializedAt', '?')}")
    print(f"   上下文窗口: {cfg.get('contextWindow', 0)/1000:.0f}K")
    print(f"   字节/KToken: {cfg.get('bytesPerKtoken', '?')}")
    print("\n   阈值:")
    t = cfg.get("thresholds", {})
    print(f"     WARN: {t.get('warn', '?')}%  |  ALERT: {t.get('alert', '?')}%  |  CRIT: {t.get('crit', '?')}%")
    print("\n   模型配置表:")
    m = cfg.get("models", {})
    for key, entry in m.items():
        if isinstance(entry, dict):
            print(f"     {key}: {entry.get('model', '?')}  (provider: {entry.get('provider', '?')})")
        elif isinstance(entry, str):
            print(f"     {key}: {entry}  (旧格式)")
    print("\n   守护模式:")
    d = cfg.get("daemon", {})
    print(f"     扫描间隔: {d.get('scanInterval', '?')}s")
    print(f"     自动压缩: {d.get('autoArmorCompress', '?')}")
    print(f"     自动监控: {d.get('autoTaskWatch', '?')}")
    h = cfg.get("heavy", {})
    print("\n   重型战甲:")
    print(f"     大工程检测: {'启用' if h.get('autoDetectEnabled') else '关闭'}")
    print(f"     检测模式: {h.get('autoDetect', 'ask')} (ask=询问/semi=半自动30s/full=全自动)")

    # 【P2-7】上面是内部运行状态(state JSON)，下面是真正生效的用户配置。
    # 明确区分二者，避免用户以为改了 TOML 就等于改了运行时。
    print_effective_config()
