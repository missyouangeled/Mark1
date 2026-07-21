"""Mark42 用户配置加载器。

从 ~/.config/mark42/config.toml 读取用户配置，
回退到内置默认值（templates/config.toml）。

配置文件优先级：
1. 环境变量 MARK42_CONFIG 指定的路径
2. ~/.config/mark42/config.toml
3. 包内 templates/config.toml（默认值）
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
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()

            # 去引号
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
                # 处理 ~ 展开
                if val.startswith("~"):
                    val = str(Path.home() / val[2:])
            elif val.lower() in ("true", "false"):
                val = val.lower() == "true"
            else:
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
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


# ── 配置加载 ──────────────────────────────────────────────

_cache: dict[str, Any] | None = None


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
    """读取整个配置节。如 get_section("models")。"""
    cfg = load_config()
    return cfg.get(section, {})


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
    """强制重新加载配置。"""
    return load_config(force_reload=True)
