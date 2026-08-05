"""Mark42 用户配置加载器。

从 ~/.config/mark42/config.toml 读取用户配置，
回退到内置默认值（templates/config.toml）。

配置文件优先级：
1. 环境变量 MARK42_CONFIG 指定的路径
2. ~/.config/mark42/config.toml
3. 包内 templates/config.toml（默认值）

本模块另提供 ``get_openclaw_config_path()``，作为全仓解析
``openclaw.json`` 路径的**唯一入口**（P2-16）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# ── TOML 解析 ─────────────────────────────────────────────


def _parse_toml(text: str) -> dict[str, Any]:
    """解析 TOML 文本。优先用标准库 tomllib，否则用内置轻量解析器。"""
    # Python 3.11+ 有 tomllib
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(text)

    # Python 3.10 fallback: 轻量 TOML 解析器（支持基本语法）
    return _lite_toml_parse(text)


def _lite_toml_parse(text: str) -> dict[str, Any]:
    """轻量 TOML 解析器，支持 [section] / key = value / 注释。
    不支持：多行字符串、数组表、日期。
    """
    result: dict[str, Any] = {}
    current = result

    for line in text.split("\n"):
        line = line.split("#")[0].strip()  # 去注释+首尾空格
        if not line:
            continue

        # [section.subsection]
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            parts = section.split(".")
            current = result
            for part in parts:
                part = part.strip()
                if part not in current:
                    current[part] = {}
                current = current[part]
            continue

        # key = value
        if "=" in line:
            key, _, raw_val = line.partition("=")
            key = key.strip()
            # 【P3-4】val 会依次尝试收敛为 bool/int/float，是刻意设计，
            # 故显式标注联合类型而非让 mypy 锁定为 str
            val: str | bool | int | float = raw_val.strip()

            # 去引号
            text_val = val if isinstance(val, str) else str(val)
            if (
                (text_val.startswith('"') and text_val.endswith('"'))
                or (text_val.startswith("'") and text_val.endswith("'"))
            ):
                val = text_val[1:-1]
                # 处理 ~ 展开
                if isinstance(val, str) and val.startswith("~"):
                    val = str(Path.home() / val[2:])
            elif text_val.lower() in ("true", "false"):
                val = text_val.lower() == "true"
            else:
                try:
                    val = int(text_val)
                except ValueError:
                    try:
                        val = float(text_val)
                    except ValueError:
                        pass  # 保持字符串

            current[key] = val

    return result


# ── 配置路径 ──────────────────────────────────────────────


def get_config_path() -> Path:
    """获取用户配置文件路径。"""
    # 1. 环境变量
    env_path = os.environ.get("MARK42_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    # 2. ~/.config/mark42/config.toml
    return Path.home() / ".config" / "mark42" / "config.toml"


def get_default_config_path() -> Path:
    """获取包内默认配置模板路径。"""
    import mark42

    pkg_dir = Path(mark42.__file__).parent
    return pkg_dir / "templates" / "config.toml"


# ── OpenClaw 配置路径：全局单一解析器 (P2-16) ─────────────

_DEFAULT_OPENCLAW_CONFIG = "~/.openclaw/openclaw.json"

# CLI 显式指定的路径（最高优先级）。由 CLI 入口调 set_openclaw_config_override() 注入。
_openclaw_config_override: Path | None = None


def set_openclaw_config_override(path: str | Path | None) -> None:
    """设置/清除 CLI 级的 openclaw.json 路径覆盖。"""
    global _openclaw_config_override
    _openclaw_config_override = Path(path).expanduser() if path else None


def get_openclaw_config_path() -> Path:
    """解析 openclaw.json 的实际路径 —— **全仓唯一入口** (P2-16)。

    优先级：CLI 显式指定 > 环境变量 ``OPENCLAW_CONFIG``
              > TOML ``[paths] openclaw_config`` > 平台默认。

    历史问题：``openclaw_config.py`` / ``context_safety.py`` /
    ``compaction_diag.py`` / ``config.py`` 各自硬编码
    ``Path.home() / ".openclaw" / "openclaw.json"``，且多为**模块级常量**
    （import 时就固化）。后果：环境变量与配置向导写入的
    ``[paths] openclaw_config`` 完全无效，多实例/容器/测试隔离下
    会误操作真实用户配置。

    注意：本函数每次调用都重新解析，不缓存。调用方必须在**使用时**
    调用，不得赋给模块级常量，否则会重现同一个 bug。
    """
    # 1. CLI 显式指定
    if _openclaw_config_override is not None:
        return _openclaw_config_override

    # 2. 环境变量
    env_path = os.environ.get("OPENCLAW_CONFIG")
    if env_path and env_path.strip():
        return Path(env_path).expanduser()

    # 3. TOML [paths] openclaw_config
    #    此处不能让 TOML 解析异常影响路径解析，否则配置写坏会连带
    #    整个路径体系崩掉，因此广泛捕获后退回默认。
    try:
        toml_path = get("paths", "openclaw_config", "")
        if isinstance(toml_path, str) and toml_path.strip():
            return Path(toml_path).expanduser()
    except Exception:  # pragma: no cover - 防御分支
        import logging

        logging.debug("读取 TOML [paths] openclaw_config 失败，退回默认", exc_info=True)

    # 4. 平台默认
    return Path(_DEFAULT_OPENCLAW_CONFIG).expanduser()


# ── 配置加载 ──────────────────────────────────────────────

_cache: dict[str, Any] | None = None
_user_only_cache: dict[str, Any] | None = None


def load_config(force_reload: bool = False) -> dict[str, Any]:
    """加载用户配置。优先用户配置，回退包内默认。

    Returns:
        完整配置字典，结构对应 config.toml
    """
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    # 尝试加载用户配置
    user_path = get_config_path()
    default_path = get_default_config_path()

    config: dict[str, Any] = {}

    # 先加载默认值
    if default_path.exists():
        try:
            config = _parse_toml(default_path.read_text(encoding="utf-8"))
        except Exception:
            config = {}

    # 再覆盖用户配置
    if user_path.exists():
        try:
            user_config = _parse_toml(user_path.read_text(encoding="utf-8"))
            _deep_merge(config, user_config)
        except Exception:
            import logging

            logging.debug("用户配置解析失败，使用默认值", exc_info=True)

    _cache = config
    return config


def load_user_only_config(force_reload: bool = False) -> dict[str, Any]:
    """只加载**用户自己写的** TOML，不合并包内默认模板。

    ``load_config()`` 会先 merge 包内 ``templates/config.toml``，因此
    “能读到值”并不等于“用户真的配了这一项”。做来源追踪（P2-7）
    时必须区分二者，否则会把代码默认值误标为 ``toml:``。
    """
    global _user_only_cache
    if _user_only_cache is not None and not force_reload:
        return _user_only_cache

    user_path = get_config_path()
    config: dict[str, Any] = {}
    if user_path.exists():
        try:
            config = _parse_toml(user_path.read_text(encoding="utf-8"))
        except Exception:
            import logging

            logging.debug("用户配置解析失败，视为未配置", exc_info=True)
            config = {}

    _user_only_cache = config
    return config


def get_user_only(section: str, key: str, default: Any = None) -> Any:
    """只从用户 TOML 取值（不回退包内模板）。用于来源追踪。"""
    return load_user_only_config().get(section, {}).get(key, default)


def _deep_merge(base: dict, override: dict) -> None:
    """深度合并 override 到 base（in-place）。"""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


# ── 便捷读取 ─────────────────────────────────────────────


def get(section: str, key: str, default: Any = None) -> Any:
    """读取配置值。如 get("thresholds", "warn", 70)。"""
    cfg = load_config()
    return cfg.get(section, {}).get(key, default)


def get_section(section: str) -> dict[str, Any]:
    """读取整个配置节。如 get_section("models")。

    节内容不是 dict（用户把 [models] 写成标量/数组）时返回 {}，
    避免调用方拿到非 dict 后崩在 .get()（P3-4）。
    """
    cfg = load_config()
    value = cfg.get(section, {})
    return value if isinstance(value, dict) else {}


# ── 配置初始化 ────────────────────────────────────────────


def init_user_config(force: bool = False) -> Path:
    """生成用户配置文件。默认复制包内模板到 ~/.config/mark42/config.toml。"""
    target = get_config_path()
    if target.exists() and not force:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)

    # 复制默认模板
    default_path = get_default_config_path()
    if default_path.exists():
        content = default_path.read_text(encoding="utf-8")
        # 展开 ~ 路径
        target.write_text(content, encoding="utf-8")
    else:
        # 如果模板不存在，写空配置
        target.write_text("# Mark42 配置文件\n", encoding="utf-8")

    return target


def reload() -> dict[str, Any]:
    """强制重新加载配置（含 user-only 缓存）。"""
    load_user_only_config(force_reload=True)
    return load_config(force_reload=True)


# ── 交互式配置向导 ────────────────────────────────────────


def _prompt(msg: str, default: str | int | bool | None = None) -> str:
    """带默认值的输入提示。"""
    if default is not None:
        return input(f"  {msg} [{default}]: ").strip() or str(default)
    return input(f"  {msg}: ").strip()


def _prompt_bool(msg: str, default: bool = True) -> bool:
    """是/否提示。"""
    d = "Y/n" if default else "y/N"
    raw = input(f"  {msg} [{d}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "true", "1")


def _prompt_int(msg: str, default: int) -> int:
    """整数提示。"""
    raw = _prompt(msg, default)
    try:
        return int(raw)
    except ValueError:
        print(f"  ⚠️ 无效数字，使用默认值 {default}")
        return default


def interactive_init() -> Path:
    """交互式配置向导：引导用户一步步配置 Mark42。

    步骤：
    1. 路径配置（workspace / scratch）
    2. 上下文阈值（warn / alert / crit）
    3. LLM 模型选择
    4. 守护进程参数
    5. 日志级别
    6. 生成配置文件
    """
    print()
    print("╔════════════════════════════════════════╗")
    print("║   Mark42 配置向导                       ║")
    print("║   按回车使用默认值，Ctrl+C 取消        ║")
    print("╚════════════════════════════════════════╝")
    print()

    # ── 1. 路径 ──
    print("── 1/5 路径配置 ──")
    workspace = _prompt("OpenClaw 工作区路径", "~/.openclaw/workspace")
    openclaw_config = _prompt("OpenClaw 配置文件路径", "~/.openclaw/openclaw.json")
    scratch = _prompt("临时文件目录（有数据盘可指定）", "~/.local/state/openclaw/scratch")
    print()

    # ── 2. 上下文阈值 ──
    print("── 2/5 上下文阈值 ──")
    print("  上下文使用率百分比，达到时触发对应行为")
    warn = _prompt_int("🟡 预警阈值 (%)", 70)
    alert = _prompt_int("🟠 告警阈值 (%)", 85)
    crit = _prompt_int("🔴 紧急阈值 (%)", 95)
    print()

    # ── 3. LLM 模型 ──
    print("── 3/5 LLM 模型 ──")
    print("  模型配置从 openclaw.json 读取 API key，这里只选模型名")
    llm_model = _prompt("分析模型", "doubao-seed-2.0-pro")
    compress_model = _prompt("压缩模型", "doubao-seed-2.0-pro")
    print()

    # ── 4. 守护进程 ──
    print("── 4/5 守护进程 ──")
    scan_interval = _prompt_int("引擎扫描间隔（秒）", 30)
    armor_interval = _prompt_int("铠甲检查间隔（秒）", 300)
    auto_compress = _prompt_bool("自动触发压缩？", True)
    auto_watch = _prompt_bool("自动监控 Heavy 任务？", True)
    print()

    # ── 5. 日志 ──
    print("── 5/5 日志级别 ──")
    print("  DEBUG / INFO / WARNING / ERROR")
    log_level = _prompt("日志级别", "INFO")
    print()

    # ── 生成配置 ──
    target = get_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# ────────────────────────────────────────────────────────────
# Mark42 配置文件（由配置向导生成）
# 路径: {target}
#
# 修改后重启生效:
#   systemctl --user restart mark42-armor-guard
#   systemctl --user restart mark42-engine-daemon
# ────────────────────────────────────────────────────────────

[paths]
workspace = "{workspace}"
openclaw_config = "{openclaw_config}"
scratch = "{scratch}"
xdg_state = "~/.local/state"

[thresholds]
warn  = {warn}
alert = {alert}
crit  = {crit}
bytes_per_ktoken = 2048

[models.llmAnalyze]
model = "{llm_model}"
provider = "volcengine-agent"
max_tokens = 2000
temperature = 0.1
timeout = 120

[models.llmCompress]
model = "{compress_model}"
provider = "volcengine-agent"
max_tokens = 4000
temperature = 0.0
timeout = 120

[daemon]
scan_interval = {scan_interval}
armor_check_interval = {armor_interval}
auto_armor_compress = {str(auto_compress).lower()}
auto_task_watch = {str(auto_watch).lower()}

[logs]
max_history_files = 50
max_age_days = 30
max_broker_events_mb = 10
max_actions_lines = 500
max_daemon_log_lines = 10000

[compress]
smart_crusher_enabled = false
use_scheduler = true
pii_enabled = true
fail_safe = true
experiment_mode = false

[logging]
level = "{log_level}"
"""

    target.write_text(content, encoding="utf-8")

    print(f"✅ 配置文件已生成: {target}")
    print()
    print("下一步：")
    print("  1. 运行 `mark42 --config` 查看配置")
    print("  2. 运行 `mark42 armor --check` 检查上下文状态")
    print("  3. 运行 `mark42 status` 查看系统状态")
    print()

    # 清除缓存
    global _cache
    _cache = None

    return target
