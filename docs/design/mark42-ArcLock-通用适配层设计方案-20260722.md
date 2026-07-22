# Mark42 v4-ArcLock：通用适配层（电磁吸锁扣）设计方案

> 设计日期：2026-07-22
> 代号：ArcLock（Arc = 战甲，Lock = 锁扣）
> 状态：**方案设计中（待点点审核）**
> 目标：让 Mark42 的每个功能模块都能独立拔插，第三方实现可以"咔嗒"吸上、随时换掉

---

## 一、设计动机

### 1.1 点点的比喻

> "就像钢铁侠的战甲，每一块已经做到能独立了，但还要确保能换能随时插上。
> 钢铁侠用的是强力电磁吸锁扣，咱这个就应该有个类似的东西，让各个模块能快速拼接使用上。
> 如果客户买了 Headroom，他完全可以不用咱的上下文压缩功能，
> Mark42 的通用适配层接口可以直接接上 Headroom。"

### 1.2 当前痛点

Mark42 v3 的 R1 原则只做了"模型层可插拔"（LLM Provider 可换 ollama/api/stub）。
但功能模块之间是**硬编码直接导入**：

```python
# consciousness.py 硬编码调 armor 的压缩
from .armor import armor_compress

# engine.py 硬编码调 armor 的检查
from .armor import armor_check

# heavy.py 硬编码调 armor
from .armor import armor_compress
```

如果用户已有 Headroom（或其他压缩方案），现在只能改源码。

### 1.3 设计目标

每个功能模块对外暴露**统一接口契约**（Protocol），内部实现可替换。
用户在配置文件里指定用哪个实现，不用改一行代码。

---

## 二、核心设计：ArcLock 接口层

### 2.1 命名

- **ArcLock** = 战甲锁扣系统
- 每个"锁扣"是一个 Python `Protocol`（PEP 544 结构化子类型）
- 第三方实现不需要继承任何类，只要方法签名匹配就能"吸上"

### 2.2 为什么用 Protocol 而不是 ABC

| | Protocol | ABC |
|---|---------|-----|
| 第三方要继承 | 不需要 | 需要 |
| 鸭子类型 | ✅ 天然支持 | ❌ |
| 运行时检查 | ✅ `isinstance` | ✅ |
| 性能 | 零开销 | 略有 |
| 适合场景 | 插件生态 | 强约束框架内部 |

Protocol 的"不需要继承"特性就是"电磁吸"的关键--第三方代码只需要实现正确的方法签名，
不用 `import mark42`，不用继承任何类，就能被 Mark42 识别和使用。

### 2.3 新增文件结构

```
mark42/
├── interfaces/          # ← 新增：ArcLock 接口层
│   ├── __init__.py       #    注册器 + 公开导出
│   ├── compress.py       #    压缩接口
│   ├── memory.py         #    记忆/向量搜索接口
│   ├── consciousness.py #    意识/自愈接口
│   ├── error_archive.py  #    错误档案接口
│   ├── circuit_breaker.py #  熔断器接口
│   ├── health.py         #    健康监控接口
│   ├── chaos.py          #    混沌工程接口
│   ├── engine.py         #    循环引擎接口
│   └── heavy.py          #    重型战甲接口
├── plugins/              # ← 新增：默认实现注册
│   ├── __init__.py
│   ├── builtin_compress.py    # armor 压缩的默认实现
│   ├── builtin_memory.py      # QMD 向量搜索的默认实现
│   └── ...                    # 每个接口一个默认实现
├── armor.py              # 现有代码，改为实现 interfaces.compress
├── consciousness.py      # 现有代码，改为实现 interfaces.consciousness
├── ...
```

---

## 三、九大锁扣接口定义

### 3.1 压缩锁扣 `CompressLock`

```python
# interfaces/compress.py
from typing import Protocol, runtime_checkable, Any, Dict

@runtime_checkable
class CompressLock(Protocol):
    """上下文压缩锁扣。
    
    实现方可以 是 Mark42 armor、Headroom、或任何第三方压缩方案。
    """

    def check(self) -> Dict[str, Any]:
        """检查当前上下文状态。
        返回: {"usagePercent": float, "severity": str, ...}
        """
        ...

    def compress(self, dry_run: bool = True, **kwargs) -> Dict[str, Any]:
        """执行上下文压缩。
        dry_run=True: 只分析不执行
        dry_run=False: 真实执行
        返回: {"action": str, "before": float, "after": float, ...}
        """
        ...

    def diagnose(self) -> Dict[str, Any]:
        """压缩诊断（可选，返回详细分析）。"""
        ...
```

**现有实现**: `armor.py` 的 `armor_check()`, `armor_compress()`, `compaction_diag.py`
**第三方示例**: Headroom、LangChain 的 ConversationSummaryMemory

### 3.2 记忆搜索锁扣 `MemoryLock`

```python
# interfaces/memory.py
@runtime_checkable
class MemoryLock(Protocol):
    """记忆/向量搜索锁扣。"""

    def search(self, query: str, top_k: int = 5) -> list[Dict[str, Any]]:
        """语义搜索，返回相关文档列表。
        返回: [{"content": str, "score": float, "source": str}, ...]
        """
        ...

    def index(self, documents: list[Dict[str, Any]]) -> Dict[str, Any]:
        """索引文档。返回: {"indexed": int, "status": str}"""
        ...

    def health(self) -> bool:
        """后端是否可用。"""
        ...
```

**现有实现**: QMD 向量引擎（core_3）
**第三方示例**: Mem0、Pinecone、Weaviate、ChromaDB

### 3.3 意识/自愈锁扣 `ConsciousnessLock`

```python
# interfaces/consciousness.py
@runtime_checkable
class ConsciousnessLock(Protocol):
    """自愈意识锁扣。C1-C5 完整流程。"""

    def self_check(self) -> Dict[str, Any]:
        """C1: 自检，返回发现的问题列表。"""
        ...

    def assess(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """C2: 评估确定性，返回动作建议。"""
        ...

    def handle_issue(self, issue: Dict[str, Any],
                     dry_run: bool = True) -> Dict[str, Any]:
        """主入口：C5->C2->C3/C4 完整路由。"""
        ...
```

**现有实现**: `consciousness.py` 的 `Consciousness` 类
**第三方示例**: 自定义运维系统、Sentry + 自动修复脚本

### 3.4 错误档案锁扣 `ArchiveLock`

```python
# interfaces/error_archive.py
@runtime_checkable
class ArchiveLock(Protocol):
    """错误档案锁扣。记录和查询历史故障。"""

    def lookup(self, signature: str, **kwargs) -> Any:
        """查找历史记录。"""
        ...

    def add(self, entry: Dict[str, Any]) -> str:
        """添加新记录，返回 ID。"""
        ...

    def approve(self, entry_id: str) -> bool:
        """批准某条记录为可自动执行。"""
        ...
```

**现有实现**: `error_archive.py` 的 `ErrorArchive` 类
**第三方示例**: PagerDuty、Incident.io

### 3.5 熔断器锁扣 `BreakerLock`

```python
# interfaces/circuit_breaker.py
@runtime_checkable
class BreakerLock(Protocol):
    """熔断器锁扣。"""

    def can_call(self, key: str) -> bool:
        """当前是否可以调用。"""
        ...

    def record_success(self, key: str) -> None:
        """记录成功。"""
        ...

    def record_failure(self, key: str, reason: str = "") -> None:
        """记录失败。"""
        ...

    def status(self) -> Dict[str, Any]:
        """所有熔断器状态。"""
        ...
```

**现有实现**: `circuit_breaker.py` 的 `CircuitBreaker` 类
**第三方示例**: Hystrix、Resilience4j、tenacity

### 3.6 健康监控锁扣 `HealthLock`

```python
# interfaces/health.py
@runtime_checkable
class HealthLock(Protocol):
    """系统健康监控锁扣。"""

    def check_health(self) -> Dict[str, Any]:
        """返回当前系统健康状态。
        {"disk": ..., "memory": ..., "cpu": ..., "alerts": [...]}
        """
        ...
```

**现有实现**: `engine.py` 的 health-watch Loop
**第三方示例**: Prometheus exporter、Netdata

### 3.7 循环引擎锁扣 `EngineLock`

```python
# interfaces/engine.py
@runtime_checkable
class EngineLock(Protocol):
    """循环引擎锁扣。管理 Observe->Decide->Act->Verify 循环。"""

    def register_loop(self, name: str, template: str,
                      interval: int, task: str) -> bool:
        """注册一个 Loop。"""
        ...

    def run_loop(self, name: str) -> Dict[str, Any]:
        """执行一次 Loop。"""
        ...

    def list_loops(self) -> Dict[str, Any]:
        """列出所有 Loop 状态。"""
        ...
```

**现有实现**: `engine.py`
**第三方示例**: Celery Beat、APScheduler

### 3.8 混沌工程锁扣 `ChaosLock`

```python
# interfaces/chaos.py
@runtime_checkable
class ChaosLock(Protocol):
    """混沌工程锁扣。"""

    def list_experiments(self) -> list[Dict[str, Any]]:
        """列出可用实验。"""
        ...

    def run_experiment(self, name: str,
                       dry_run: bool = True) -> Dict[str, Any]:
        """执行实验。"""
        ...
```

**现有实现**: `chaos_engine.py`
**第三方示例**: Chaos Mesh、LitmusChaos

### 3.9 重型战甲锁扣 `HeavyLock`

```python
# interfaces/heavy.py
@runtime_checkable
class HeavyLock(Protocol):
    """重型战甲锁扣。大任务拆分+执行+监控。"""

    def submit(self, task_name: str, subtasks: list[Dict[str, Any]],
               execute_now: bool = False) -> str:
        """提交大任务，返回任务 ID。"""
        ...

    def status(self, task_id: str) -> Dict[str, Any]:
        """查询任务状态。"""
        ...

    def cancel(self, task_id: str) -> bool:
        """取消任务。"""
        ...
```

**现有实现**: `heavy.py`
**第三方示例**: Temporal、Airflow、Prefect

---

## 四、ArcLock 注册器

### 4.1 核心注册器

```python
# interfaces/__init__.py
"""ArcLock 注册器。

每个模块通过 register() 注册自己的默认实现。
用户通过配置文件或代码可以替换为第三方实现。

用法:
    from mark42.interfaces import get_compress, get_memory

    compress = get_compress()  # 返回当前注册的压缩实现
    result = compress.check()
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Type
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


# 便捷函数
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
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    arclock_cfg = cfg.get("arclock", {})
    for name, spec in arclock_cfg.items():
        module_path = spec["module"]
        cls_name = spec["class"]
        init_config = spec.get("config", {})

        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            impl = cls(**init_config) if init_config else cls()
            register(name, impl)
            logger.info("ArcLock 从配置加载: %s -> %s.%s", name, module_path, cls_name)
        except Exception as e:
            logger.error("ArcLock 配置加载失败 %s: %s", name, e)
            logger.info("ArcLock %s 回退到默认实现", name)
```

### 4.2 注册流程图

```
启动时:
  1. mark42 初始化
  2. 读取 arclock.yaml（如果有）
  3. 对每个配置项：import 第三方模块 -> 实例化 -> register()
  4. 没配的项：首次调用时懒加载默认实现
  5. 所有 get_xxx() 调用都走注册表

运行时替换（热插拔）:
  register("compress", HeadroomCompress(api_key=...))
  -> 立即生效，下一次 get_compress() 调用就用新实现
```

---

## 五、需要修改的现有文件

### 5.1 新增文件（不改现有代码）

| 文件 | 说明 | 行数估算 |
|------|------|---------|
| `interfaces/__init__.py` | 注册器 + get 函数 | ~120 |
| `interfaces/compress.py` | CompressLock Protocol | ~40 |
| `interfaces/memory.py` | MemoryLock Protocol | ~35 |
| `interfaces/consciousness.py` | ConsciousnessLock Protocol | ~35 |
| `interfaces/error_archive.py` | ArchiveLock Protocol | ~35 |
| `interfaces/circuit_breaker.py` | BreakerLock Protocol | ~30 |
| `interfaces/health.py` | HealthLock Protocol | ~20 |
| `interfaces/engine.py` | EngineLock Protocol | ~30 |
| `interfaces/chaos.py` | ChaosLock Protocol | ~25 |
| `interfaces/heavy.py` | HeavyLock Protocol | ~30 |
| `plugins/__init__.py` | 空文件 | 1 |
| `plugins/builtin_compress.py` | 包装 armor.py 为 CompressLock | ~60 |
| `plugins/builtin_memory.py` | 包装 QMD 为 MemoryLock | ~50 |
| `plugins/builtin_consciousness.py` | 包装 Consciousness 类 | ~40 |
| `plugins/builtin_archive.py` | 包装 ErrorArchive | ~40 |
| `plugins/builtin_breaker.py` | 包装 CircuitBreaker | ~40 |
| `plugins/builtin_health.py` | 包装 health-watch | ~30 |
| `plugins/builtin_engine.py` | 包装 engine | ~40 |
| `plugins/builtin_chaos.py` | 包装 ChaosEngine | ~30 |
| `plugins/builtin_heavy.py` | 包装 heavy | ~40 |
| **小计** | | **~800 行新代码** |

### 5.2 需要修改的现有文件

| 文件 | 修改内容 | 影响行数 |
|------|---------|---------|
| `consciousness.py` | `_remediate_context_alert` 里的 `from .armor import armor_compress` 改为 `from .interfaces import get_compress; get_compress().compress(dry_run=False)` | ~5 行 |
| `engine.py` | `context-guard` Loop 里的 `armor_check()` / `armor_compress()` 改为走 `get_compress()` | ~10 行 |
| `engine.py` | `model-fallback` Loop 里的 Gateway 检查改为走 `get_health()` | ~5 行 |
| `heavy.py` | 调 armor 的地方改为走 `get_compress()` | ~3 行 |
| `core_registry.py` | core_3 探测改为走 `get_memory().health()` | ~5 行 |
| `config.py` | 新增 `ARCLOCK_CONFIG_PATH` 常量 | ~3 行 |
| `cli/parser.py` | 新增 `mark42 arclock list` 子命令 | ~30 行 |
| `cli/parser.py` | `mark42 status` 底部加 ArcLock 状态行 | ~5 行 |
| **小计** | | **~65 行修改** |

### 5.3 不需要修改的文件

以下文件**完全不动**：
- `armor.py`（被 builtin_compress 包装）
- `error_archive.py`（被 builtin_archive 包装）
- `circuit_breaker.py`（被 builtin_breaker 包装）
- `chaos_engine.py`（被 builtin_chaos 包装）
- `cluster_manager.py`、`advisor_client.py`、`llm_provider.py`、其余所有文件

---

## 六、第三方接入示例

### 6.1 接入 Headroom 替代压缩

第三方只需写一个类，不用继承任何 Mark42 的东西：

```python
# headroom_adapter.py （第三方代码，不在 mark42 包内）
class HeadroomCompress:
    """适配 Headroom 到 Mark42 CompressLock 接口。"""

    def __init__(self, api_key: str = "", model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    def check(self):
        """调用 Headroom 的上下文分析 API。"""
        import requests
        resp = requests.get("https://api.headroom.ai/context/status",
                            headers={"Authorization": f"Bearer {self.api_key}"})
        data = resp.json()
        return {"usagePercent": data["usage"], "severity": data["level"]}

    def compress(self, dry_run: bool = True, **kwargs):
        """调用 Headroom 的压缩 API。"""
        if dry_run:
            return {"action": "dry_run", "would_compress": True}
        import requests
        resp = requests.post("https://api.headroom.ai/context/compress",
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json={"model": self.model})
        return resp.json()

    def diagnose(self):
        return {"provider": "headroom", "model": self.model}
```

然后在 `arclock.yaml` 里配置：

```yaml
arclock:
  compress:
    module: "headroom_adapter"
    class: "HeadroomCompress"
    config:
      api_key: "sk-xxx"
      model: "gpt-4o"
```

Mark42 启动时自动加载，所有内部调用压缩的地方都会走 Headroom。

### 6.2 接入 Pinecone 替代记忆搜索

```python
# pinecone_adapter.py
class PineconeMemory:
    def __init__(self, api_key: str, environment: str):
        import pinecone
        pinecone.init(api_key=api_key, environment=environment)
        self.index = pinecone.Index("mark42-memory")

    def search(self, query: str, top_k: int = 5):
        # 用自己的 embedding 生成 query vector
        results = self.index.query(query, top_k=top_k)
        return [{"content": r["metadata"]["text"],
                 "score": r["score"],
                 "source": "pinecone"} for r in results]

    def index(self, documents):
        # 批量写入
        ...

    def health(self):
        try:
            self.index.describe_index_stats()
            return True
        except:
            return False
```

### 6.3 不配就用默认

`arclock.yaml` 不存在或某个接口没配 -> 自动用 Mark42 内置实现，零配置开箱即用。

---

## 七、与 v3 的兼容性

### 7.1 零破坏迁移

| 迁移阶段 | 说明 | 风险 |
|---------|------|------|
| **阶段 1**：新增 interfaces/ + plugins/ | 只加新文件，不改现有代码 | 零风险 |
| **阶段 2**：内置实现注册 | 在 `__init__.py` 里把 armor/error_archive 等注册为默认实现 | 零风险 |
| **阶段 3**：内部调用改走注册器 | consciousness/engine/heavy 里的硬编码导入改为 `get_xxx()` | 低风险（有单元测试覆盖） |
| **阶段 4**：CLI 加 arclock 命令 | `mark42 arclock list` 查看当前实现 | 零风险 |

每个阶段独立可测试，不需要一次性全改。

### 7.2 测试策略

```python
# tests/unit/test_arclock.py

def test_default_compress_loaded():
    """不配任何东西，默认压缩实现可用。"""
    from mark42.interfaces import get_compress
    c = get_compress()
    assert c is not None
    result = c.check()
    assert "usagePercent" in result

def test_custom_compress_registered():
    """注册自定义实现后，get_compress() 返回新实现。"""
    from mark42.interfaces import register, get_compress

    class MyCompress:
        def check(self): return {"usagePercent": 42.0}
        def compress(self, dry_run=True): return {"action": "ok"}
        def diagnose(self): return {}

    register("compress", MyCompress())
    c = get_compress()
    assert c.check()["usagePercent"] == 42.0

def test_protocol_compliance():
    """第三方实现只要签名匹配就能通过 isinstance 检查。"""
    from mark42.interfaces.compress import CompressLock

    class HeadroomLike:
        def check(self): ...
        def compress(self, dry_run=True): ...
        def diagnose(self): ...

    assert isinstance(HeadroomLike(), CompressLock)  # 零导入就能通过
```

---

## 八、CLI 新增命令

```bash
# 查看所有锁扣的当前实现
mark42 arclock list

# 输出示例:
# 🔌 ArcLock 锁扣状态
#
#   compress        -> BuiltinCompress (mark42.armor)
#   memory          -> BuiltinMemory (qmd)
#   consciousness   -> BuiltinConsciousness (mark42.consciousness)
#   archive         -> BuiltinArchive (mark42.error_archive)
#   breaker         -> BuiltinBreaker (mark42.circuit_breaker)
#   health          -> BuiltinHealth (mark42.engine)
#   engine          -> BuiltinEngine (mark42.engine)
#   chaos           -> BuiltinChaos (mark42.chaos_engine)
#   heavy           -> BuiltinHeavy (mark42.heavy)
#
#   配置文件: 未配置（全部使用默认实现）

# 重新加载配置
mark42 arclock reload --config /path/to/arclock.yaml

# 测试某个锁扣
mark42 arclock test compress
#   ✅ CompressLock 协议检查通过
#   ✅ check() 返回有效结果: {"usagePercent": 48.8, ...}
#   ✅ compress(dry_run=True) 返回有效结果
```

---

## 九、架构图

```
                    ┌─────────────────────────────────┐
                    │        Mark42 CLI / API          │
                    │     mark42 arclock list/test     │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │      ArcLock 注册器              │
                    │   interfaces/__init__.py        │
                    │                                 │
                    │  get_compress()  -> ?           │
                    │  get_memory()    -> ?           │
                    │  get_breaker()   -> ?           │
                    │  ... 9 个锁扣                    │
                    └──┬──────────┬──────────┬────────┘
                       │          │          │
            ┌──────────▼──┐  ┌───▼────┐  ┌─▼──────────┐
            │ arclock.yaml│  │ 内置   │  │ 第三方     │
            │             │  │ 实现   │  │ 实现       │
            │ compress:   │  │        │  │            │
            │   headroom  │  │ armor  │  │ Headroom   │
            │ memory:     │  │ QMD    │  │ Pinecone   │
            │   pinecone  │  │ CB     │  │ Hystrix    │
            │ breaker:    │  │ ...    │  │ Sentry     │
            │   hystrix   │  │        │  │ ...        │
            └─────────────┘  └────────┘  └────────────┘
                             (默认)       (用户配置)

    优先级: arclock.yaml > 代码内 register() > 默认实现
    没配的 = 用默认 = 现有行为不变
```

---

## 十、实施计划

| 阶段 | 内容 | 估时 | 依赖 |
|------|------|------|------|
| **P1** | 新建 `interfaces/` 目录 + 9 个 Protocol 文件 | 2h | 无 |
| **P2** | 新建 `plugins/` 目录 + 9 个内置包装器 | 3h | P1 |
| **P3** | 注册器 `interfaces/__init__.py` | 2h | P1 |
| **P4** | 修改 5 个现有文件（~65 行改动） | 1h | P2, P3 |
| **P5** | CLI 新增 `arclock` 子命令 | 1h | P3 |
| **P6** | 单元测试（~15 个测试用例） | 2h | P4 |
| **P7** | arclock.yaml 示例文件 + 文档 | 1h | P6 |
| **总计** | | **~12h** | |

---

## 十一、设计决策记录

| # | 决策 | 理由 | 替代方案 |
|---|------|------|---------|
| 1 | 用 Protocol 不用 ABC | 第三方不需要继承，鸭子类型"吸上"就行 | ABC（太重，需 import） |
| 2 | 配置文件用 YAML | 人类可读，Python 生态标准 | TOML（也行，但嵌套结构不如 YAML） |
| 3 | 懒加载默认实现 | 不用就不加载，省内存 | 启动全加载（慢） |
| 4 | register() 支持运行时热替换 | 符合"随时拔插"的战甲理念 | 只支持配置文件（不够灵活） |
| 5 | 9 个接口不合并成 1 个大接口 | 每个锁扣独立可换，符合"每一块独立战斗" | 单一接口（违反 SRP） |
| 6 | 内置实现作为 plugins/ 包装器 | armor.py 等核心代码完全不改 | 直接在 armor.py 里加 Protocol（侵入） |
| 7 | 不用 entry_points / setup.py 插件发现 | 太重了，importlib + YAML 足够 | setuptools entry_points（适合大型生态） |

---

## 十二、与 v3 R1-R14 原则的关系

| 原则 | v3 状态 | ArcLock 升级 |
|------|---------|-------------|
| R1 可插拔 | 只做了 LLM Provider | **扩展到全部 9 个模块** |
| R6 dry-run | 所有执行入口默认 dry-run | 不变（第三方实现也要遵守） |
| R9 强制读协议 | 自动行为前必须读规则 | 不变 |
| R12 L3 cooldown | 5 次自动批准后必须确认 | 不变（archive 接口保留 cooldown 逻辑） |
| R14 集群思维 | 重启 3 次替换 | 不变 |

ArcLock 是 R1 的自然延伸：从"模型层可插拔"到"所有功能模块可插拔"。

---

## 十三、风险与缓解

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| 第三方实现不遵守 dry_run 约定 | 中 | `mark42 arclock test` 命令做协议合规检查 |
| 第三方实现抛异常导致 Mark42 崩溃 | 中 | 注册器所有调用包 try/except，失败回退默认实现 |
| 配置文件错误导致启动失败 | 低 | 解析失败时全部回退默认实现 + 打印警告 |
| 性能开销（多一层间接调用） | 低 | Protocol 调用是 O(1)，懒加载避免未用模块 |
| 接口设计需要前瞻性 | 中 | 先用最小接口（3-4 个方法），不够再加 |

---

## 总结

这套设计的核心就一句话：**每个模块定义一个 Protocol，内置实现是默认值，用户可以配置替换。**

点点的比喻完全对：现在的 Mark42 是一块块独立的战甲零件，ArcLock 就是那个"电磁吸锁扣"--规定了接口形状（锁扣的凹槽），任何符合形状的实现都能"咔嗒"吸上去。

代码量不大（~800 行新 + ~65 行修改），风险可控（零破坏迁移），下个月额度充足了可以做。
