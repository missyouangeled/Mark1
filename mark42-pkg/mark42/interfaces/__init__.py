"""ArcLock 注册器。

每个模块通过 register() 注册自己的默认实现。
用户通过配置文件或代码可以替换为第三方实现。

用法:
    from mark42.interfaces import get_compress, get_memory

    compress = get_compress()  # 返回当前注册的压缩实现
    result = compress.check()
"""

from __future__ import annotations
from typing import Any, Dict, Optional
import importlib
import logging

logger = logging.getLogger(__name__)

# 注册表：接口名 -> 实例
_REGISTRY: Dict[str, Any] = {}

# 接口名到默认实现的映射
_DEFAULTS: Dict[str, str] = {
    "compress": "mark42.plugins.builtin_compress:BuiltinCompress",
    "memory": "mark42.plugins.builtin_memory:BuiltinMemory",
    "consciousness": "mark42.plugins.builtin_consciousness:BuiltinConsciousness",
    "archive": "mark42.plugins.builtin_archive:BuiltinArchive",
    "breaker": "mark42.plugins.builtin_breaker:BuiltinBreaker",
    "health": "mark42.plugins.builtin_health:BuiltinHealth",
    "engine": "mark42.plugins.builtin_engine:BuiltinEngine",
    "chaos": "mark42.plugins.builtin_chaos:BuiltinChaos",
    "heavy": "mark42.plugins.builtin_heavy:BuiltinHeavy",
    "audit": "mark42.plugins.builtin_audit:BuiltinAudit",
}


def register(name: str, impl: Any) -> None:
    """注册一个实现。后注册的覆盖先注册的。"""
    _REGISTRY[name] = impl
    logger.info("ArcLock 注册: %s -> %s", name, type(impl).__name__)


def get(name: str) -> Optional[Any]:
    """获取一个实现。优先从注册表取，没有则加载默认。"""
    if name in _REGISTRY:
        return _REGISTRY[name]

    # 加载默认实现
    if name in _DEFAULTS:
        path = _DEFAULTS[name]
        module_path, cls_name = path.rsplit(":", 1)
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            impl = cls()
            register(name, impl)
            return impl
        except Exception as e:
            logger.warning("ArcLock 默认实现加载失败 %s: %s", name, e)
            return None

    logger.warning("ArcLock 未知接口: %s", name)
    return None


# ── 便捷函数 ──

def get_compress() -> Any:
    return get("compress")

def get_memory() -> Any:
    return get("memory")

def get_consciousness() -> Any:
    return get("consciousness")

def get_archive() -> Any:
    return get("archive")

def get_breaker() -> Any:
    return get("breaker")

def get_health() -> Any:
    return get("health")

def get_engine() -> Any:
    return get("engine")

def get_chaos() -> Any:
    return get("chaos")

def get_heavy() -> Any:
    return get("heavy")


def get_audit() -> Any:
    return get("audit")


def list_all() -> Dict[str, Any]:
    """列出所有锁扣的当前实现状态。"""
    result = {}
    for name in _DEFAULTS:
        impl = get(name)
        if impl is not None:
            result[name] = {
                "class": type(impl).__name__,
                "module": type(impl).__module__,
            }
        else:
            result[name] = {"error": "加载失败"}
    return result


def configure_from_file(config_path: str) -> None:
    """从配置文件加载实现覆盖。

    配置文件格式（YAML）:

    ```yaml
    arclock:
      compress:
        module: "headroom.compress"
        class: "HeadroomCompress"
        config:
          api_key: "xxx"
          model: "gpt-4o"

      memory:
        module: "pinecone_client"
        class: "PineconeMemory"
        config:
          api_key: "xxx"
          environment: "us-west-2"

      # 不配 = 用 Mark42 默认实现
      # conscious: 用默认

      breaker:
        module: "resilience4j_py"
        class: "Resilience4jBreaker"
        config:
          failure_rate_threshold: 0.5
    ```
    """
    try:
        import yaml
    except ImportError:
        logger.error("ArcLock 配置加载需要 PyYAML，请 pip install pyyaml")
        return

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        logger.error("ArcLock 配置文件读取失败 %s: %s", config_path, e)
        logger.info("ArcLock 全部回退到默认实现")
        return

    arclock_cfg = cfg.get("arclock", {})
    if not arclock_cfg:
        logger.info("ArcLock 配置为空，全部使用默认实现")
        return

    for name, spec in arclock_cfg.items():
        if name not in _DEFAULTS:
            logger.warning("ArcLock 未知接口名: %s，跳过", name)
            continue

        module_path = spec.get("module", "")
        cls_name = spec.get("class", "")
        init_config = spec.get("config", {})

        if not module_path or not cls_name:
            logger.warning("ArcLock %s 配置缺少 module/class，跳过", name)
            continue

        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            impl = cls(**init_config) if init_config else cls()
            register(name, impl)
            logger.info("ArcLock 从配置加载: %s -> %s.%s", name, module_path, cls_name)
        except Exception as e:
            logger.error("ArcLock 配置加载失败 %s: %s", name, e)
            logger.info("ArcLock %s 回退到默认实现", name)
