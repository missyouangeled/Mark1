# Headroom ArcLock 适配器示例

这是一个完整的第三方 ArcLock 适配器实现示例，演示如何将 Headroom 服务
接入到 Mark42 的 ArcLock 通用适配层接口。

## ✨ 核心特性

- **零侵入**: 不需要 `import mark42` 任何内部模块
- **鸭子类型**: 只要方法签名匹配 Protocol，就能"咔嗒"吸上
- **热插拔**: 运行时可以随时替换实现
- **完全独立**: 适配器代码可以独立运行和测试

## 📁 文件结构

```
examples/arclock_headroom/
├── headroom_compress.py   # CompressLock 适配器（上下文压缩）
├── headroom_memory.py     # MemoryLock 适配器（向量搜索）
├── arclock.yaml           # 配置文件示例
└── README.md              # 本文档
```

## 🚀 快速开始

### 1. 独立测试适配器（不依赖 Mark42）

```bash
cd scripts/

# 测试压缩适配器
python3 examples/arclock_headroom/headroom_compress.py

# 测试记忆适配器
python3 examples/arclock_headroom/headroom_memory.py
```

这证明第三方代码可以完全独立运行，不需要任何 Mark42 依赖！

### 2. 接入到 Mark42

```bash
cd scripts/

# 复制配置文件到工作目录
cp examples/arclock_headroom/arclock.yaml ./arclock.yaml

# 查看当前实现状态
mark42 arclock list

# 测试压缩锁扣
mark42 arclock test compress

# 测试记忆锁扣
mark42 arclock test memory
```

### 3. 在代码中使用

```python
# 你的业务代码（完全不知道 Headroom 的存在）
from mark42_modules.interfaces import get_compress, get_memory

# 获取当前注册的实现（可能是内置的，也可能是 Headroom）
compress = get_compress()
memory = get_memory()

# 使用接口，完全透明
status = compress.check()
if status["severity"] == "high":
    compress.compress(dry_run=False)

results = memory.search("我的问题", top_k=5)
```

## 🧪 单元测试

```bash
cd scripts/

# 运行 Headroom 适配器专用测试
python3 -m pytest tests/unit/test_arclock_headroom.py -v

# 运行全量测试确保无回归
python3 -m pytest tests/unit/ --tb=short -q
```

## 🔧 配置说明

### arclock.yaml 格式

```yaml
arclock:
  compress:
    module: "examples.arclock_headroom.headroom_compress"   # Python 模块路径
    class: "HeadroomCompress"                                # 类名
    config:                                                  # 构造函数参数
      api_key: "sk-xxx"
      model: "gpt-4o"
      base_url: "https://api.headroom.ai"

  memory:
    module: "examples.arclock_headroom.headroom_memory"
    class: "HeadroomMemory"
    config:
      api_key: "sk-xxx"
      index_name: "mark42-memory"
```

### 切换回默认实现

三种方法:

1. **删除配置文件**: `rm arclock.yaml`
2. **注释掉配置项**: 在 YAML 中注释某锁扣配置
3. **CLI 命令**: `mark42 arclock reload --reset`

## 📋 接口协议规范

### CompressLock (压缩锁扣)

```python
class CompressLock(Protocol):
    def check(self) -> Dict[str, Any]:
        """返回: {"usagePercent": float, "severity": str, ...}"""

    def compress(self, dry_run: bool = True, **kwargs) -> Dict[str, Any]:
        """返回: {"action": str, "before": float, "after": float, ...}"""

    def diagnose(self) -> Dict[str, Any]:
        """返回详细诊断信息"""
```

### MemoryLock (记忆锁扣)

```python
class MemoryLock(Protocol):
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """返回: [{"content": str, "score": float, "source": str}, ...]"""

    def index(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """返回: {"indexed": int, "status": str}"""

    def health(self) -> bool:
        """后端是否可用"""
```

## 🔌 从 mock 到真实实现

当前示例用 stub/mock 数据。要接入真实 Headroom API:

1. 修改 `headroom_compress.py` 中的 `_mock_api_call()`:
   ```python
   import requests

   def _mock_api_call(self, endpoint: str, method: str = "GET", **kwargs):
       headers = {"Authorization": f"Bearer {self.api_key}"}
       url = f"{self.base_url}{endpoint}"
       if method == "GET":
           resp = requests.get(url, headers=headers, timeout=10)
       else:
           resp = requests.post(url, headers=headers, json=kwargs, timeout=10)
       return resp.json()
   ```

2. 修改 `headroom_memory.py` 同理，调用真实向量数据库 API。

## 🏆 设计理念

### 为什么用 Protocol 而不是继承?

| 特性 | Protocol | ABC 继承 |
|------|----------|----------|
| 第三方需 import mark42 | ❌ 不需要 | ✅ 需要 |
| 鸭子类型支持 | ✅ 天然 | ❌ 没有 |
| 运行时 isinstance | ✅ 支持 | ✅ 支持 |
| 性能开销 | 零 | 略有 |

### 战甲哲学

> "就像钢铁侠的战甲，每一块已经做到能独立了，
> 还要确保能换能随时插上。ArcLock 就是那个'电磁吸锁扣'。"

每一个锁扣都是独立的，第三方实现只需要匹配接口形状，
不需要知道 Mark42 的内部结构，就能"咔嗒"一声吸上去。

## 📚 更多示例

- [Pinecone 适配器](TODO) - 真实的向量数据库实现
- [Sentry 适配器](TODO) - 错误档案接入
- [Resilience4j 适配器](TODO) - 熔断器实现
- [Celery 适配器](TODO) - 任务队列替换

## 🤝 贡献你的适配器

欢迎提交 PR 添加更多第三方适配器示例！

要求:
1. 不依赖 mark42 内部模块
2. 实现完整的 Protocol 方法
3. 包含单元测试
4. 有 stub/mock 版本（可以独立运行）
