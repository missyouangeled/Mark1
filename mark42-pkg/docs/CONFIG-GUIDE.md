# Mark42 配置向导

完整的 Mark42 配置指南，包含所有配置文件、环境变量和自定义选项。

---

## 📋 目录

1. [openclaw.json 配置](#1-openclawjson-配置)
2. [config.toml 配置](#2-configtoml-配置)
3. [arclock.yaml 配置](#3-arclockyaml-配置)
4. [systemd 服务配置](#4-systemd-服务配置)
5. [Compaction-Notifier Hook 配置](#5-compaction-notifier-hook-配置-v280)
6. [环境变量](#6-环境变量)

---

## 1. openclaw.json 配置

位置：`~/.openclaw/openclaw.json`

这是 OpenClaw 的主配置文件，Mark42 从这里读取模型供应商配置和 API key。

### 1.1 完整配置示例

```json
{
  "version": "1.0",
  "workspace": "~/.openclaw/workspace",
  "models": {
    "default_provider": "volcengine-agent",
    "providers": {
      "volcengine-agent": {
        "api_key": "your-volcengine-api-key",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-2.0-pro",
        "max_tokens": 131072,
        "temperature": 0.1
      },
      "litellm": {
        "api_key": "your-litellm-api-key",
        "base_url": "https://api.litellm.ai",
        "model": "gpt-4o",
        "max_tokens": 128000,
        "temperature": 0.0
      },
      "ollama": {
        "api_key": "ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3:70b",
        "max_tokens": 8192,
        "temperature": 0.7
      },
      "nvidia": {
        "api_key": "your-nvidia-api-key",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
        "max_tokens": 131072,
        "temperature": 0.2
      }
    },
    "routing": {
      "compress": "volcengine-agent",
      "analyze": "volcengine-agent",
      "heavy": "litellm",
      "consciousness": "ollama"
    }
  },
  "broker": {
    "enabled": true,
    "events_file": "~/.local/state/openclaw/broker/events.jsonl"
  },

  "postCompactionSections": ["启动流程", "基本规则（摘要）", "安装/启用新东西前三步"]
}
```

### 1.2 各供应商详细说明

#### Volcengine Agent（火山方舟 - 推荐）

- **用途**：主模型，用于上下文压缩和分析
- **优势**：稳定、速度快、Token 计费合理
- **获取 API Key**：
  1. 访问 [火山引擎控制台](https://console.volcengine.com/)
  2. 进入 方舟大模型平台
  3. 创建 API Key 并复制

```json
"volcengine-agent": {
  "api_key": "vk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "base_url": "https://ark.cn-beijing.volces.com/api/v3",
  "model": "doubao-seed-2.0-pro",
  "max_tokens": 131072,
  "temperature": 0.1
}
```

#### LiteLLM（Agnes AI）

- **用途**：复杂任务、重型工程
- **优势**：支持多模型路由、统一 API
- **获取 API Key**：访问 [LiteLLM 官网](https://litellm.ai/)

```json
"litellm": {
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "base_url": "https://api.litellm.ai",
  "model": "gpt-4o",
  "max_tokens": 128000,
  "temperature": 0.0
}
```

#### Ollama（本地模型）

- **用途**：本地测试、隐私敏感场景
- **优势**：完全本地运行、无 API 费用
- **安装**：
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ollama pull llama3:70b
  ```

```json
"ollama": {
  "api_key": "ollama",
  "base_url": "http://localhost:11434/v1",
  "model": "llama3:70b",
  "max_tokens": 8192,
  "temperature": 0.7
}
```

#### NVIDIA API

- **用途**：高质量推理、Nemotron 模型
- **优势**：企业级模型、性能优秀
- **获取 API Key**：访问 [NVIDIA API 目录](https://build.nvidia.com/)

```json
"nvidia": {
  "api_key": "nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "base_url": "https://integrate.api.nvidia.com/v1",
  "model": "nvidia/llama-3.1-nemotron-70b-instruct",
  "max_tokens": 131072,
  "temperature": 0.2
}
```

### 1.3 postCompactionSections 配置 (v2.8.0)

`postCompactionSections` 是 OpenClaw 的压缩后自动注入配置，配合 Mark42 的 ConstraintPinner 确保核心配置在多次压缩后不会丢失。

```json
"postCompactionSections": [
  "启动流程",
  "基本规则（摘要）",
  "安装/启用新东西前三步"
]
```

**工作机制**：
1. 每次 compact 后，OpenClaw 自动从 AGENTS.md 提取配置的章节
2. 将这些章节内容重新注入到压缩后的会话开头
3. 配合 ConstraintPinner 的双通道注入，形成三重保护

**推荐配置的章节**：
- `启动流程` - Agent 启动时的关键初始化步骤
- `基本规则（摘要）` - 核心行为规范
- `安全规则` - 不可违反的安全约束
- `输出格式` - 统一的响应格式要求

### 1.4 模型路由配置

`models.routing` 字段用于指定不同任务使用哪个模型供应商：

```json
"routing": {
  "compress": "volcengine-agent",    // 上下文压缩使用
  "analyze": "volcengine-agent",     // 上下文分析使用
  "heavy": "litellm",                // 重型任务使用
  "consciousness": "ollama"          // 意识自愈使用
}
```

---

## 2. config.toml 配置

位置：`~/.config/mark42/config.toml`

Mark42 的核心配置文件，包含阈值、路径、模型路由和 daemon 配置。

### 2.1 完整配置示例

```toml
# Mark42 配置文件
# 修改后重启服务生效: systemctl --user restart mark42-armor-guard

# ── 路径设置 ──────────────────────────────────────────────
[paths]
# OpenClaw 工作区路径
workspace = "~/.openclaw/workspace"
# OpenClaw 配置文件路径
openclaw_config = "~/.openclaw/openclaw.json"
# 临时文件/任务目录
scratch = "~/.local/state/openclaw/scratch"
# XDG 状态目录
xdg_state = "~/.local/state"

# ── 上下文监控阈值 ──────────────────────────────────────
[thresholds]
# 上下文使用率百分比，达到时触发对应行为
warn  = 70    # 🟡 发送预警 + 自动 LLM 压缩
alert = 85    # 🟠 强制再次压缩
crit  = 95    # 🔴 紧急处理

# Token 估算参数：每千 token 对应字节数
bytes_per_ktoken = 2048

# ── LLM 模型配置 ────────────────────────────────────────
# provider 对应 openclaw.json 中 providers 下的 key
[models.llmAnalyze]
model = "doubao-seed-2.0-pro"
provider = "volcengine-agent"
max_tokens = 2000
temperature = 0.1
timeout = 120
base_url_fallback = "https://ark.cn-beijing.volces.com/api/plan/v3"
endpoint = "/chat/completions"

[models.llmCompress]
model = "doubao-seed-2.0-pro"
provider = "volcengine-agent"
max_tokens = 4000
temperature = 0.0
timeout = 120
base_url_fallback = "https://ark.cn-beijing.volces.com/api/plan/v3"
endpoint = "/chat/completions"

# ── 守护进程 ─────────────────────────────────────────────
[daemon]
# Engine 扫描间隔（秒）
scan_interval = 30
# 上下文铠甲检查间隔（秒）
armor_check_interval = 300
# 是否自动触发压缩
auto_armor_compress = true
# 是否自动监控 Heavy 任务
auto_task_watch = true

# ── 日志轮替 ─────────────────────────────────────────────
[logs]
# 历史文件最大保留数
max_history_files = 50
# 日志最大保留天数
max_age_days = 30
# broker 事件最大体积（MB）
max_broker_events_mb = 10
# actions 日志最大行数
max_actions_lines = 500
# daemon 日志最大行数
max_daemon_log_lines = 10000

# ── 压缩算法 ─────────────────────────────────────────────
[compress]
# 是否启用 SmartCrusher 压缩算法
smart_crusher_enabled = false
# 是否使用调度器
use_scheduler = true
# 是否启用 PII 脱敏
pii_enabled = true
# 是否启用安全护栏
fail_safe = true
# 实验模式
experiment_mode = false

# ── 日志级别 ─────────────────────────────────────────────
[logging]
# DEBUG / INFO / WARNING / ERROR
level = "INFO"
```

### 2.2 阈值配置详解

#### 动态阈值系统 (v2.8.0)

从 v2.8.0 开始，Mark42 使用**动态阈值系统**，阈值根据上下文窗口大小自动调整，以对抗"上下文腐烂"（context rot）现象。

**原理**：大上下文窗口中信息更容易扩散，关键内容丢失更快。因此阈值随窗口增大而下调，更早触发压缩。

**动态阈值计算公式**：

```python
def get_dynamic_thresholds(context_window: int) -> dict:
    """根据上下文窗口大小返回动态阈值
    
    基准 (128K):  WARN=70, ALERT=85, CRIT=95
    目标 (1M):    WARN=60, ALERT=75, CRIT=90
    中间值线性插值
    """
```

| 窗口大小 | WARN | ALERT | CRIT | 说明 |
|----------|------|-------|------|------|
| 128K (基准) | 70% | 85% | 95% | 标准阈值 |
| 256K | 67% | 82% | 94% | 更早介入 |
| 512K | 63% | 79% | 92% | 衰减加速 |
| 1M | 60% | 75% | 90% | context rot 更严重 |

#### 三级阈值机制

| 级别 | 默认值 (128K) | 触发行为 | 说明 |
|---|---|---|---|
| **WARN** | 70% | 发送预警 + 自动 LLM 压缩 | 温和压缩，保留大部分语义 |
| **ALERT** | 85% | 强制再次压缩 + 更激进策略 | 深度压缩，优先保留关键信息 |
| **CRIT** | 95% | 紧急处理 + SmartCrusher | 极端压缩，必要时删除非关键数据 |

#### 静态覆盖（可选）

如果需要禁用动态阈值，使用固定值，可以通过配置文件或环境变量覆盖：

```toml
# config.toml - 静态阈值覆盖
[thresholds]
warn  = 70
alert = 85
crit  = 95
```

#### 调优建议

```toml
# 小模型（8K 上下文）- 更激进
[thresholds]
warn  = 60
alert = 75
crit  = 85

# 大模型（128K 上下文）- 动态阈值自动生效
# 无需额外配置，armor.py 自动读取窗口大小计算阈值
```

### 2.3 模型路由详解

Mark42 支持为不同任务指定不同的模型：

```toml
# 用于上下文分析、健康检查、诊断任务
[models.llmAnalyze]
model = "doubao-seed-2.0-pro"
provider = "volcengine-agent"
max_tokens = 2000      # 分析不需要太长输出
temperature = 0.1      # 低温度保证一致性
timeout = 120

# 用于上下文压缩任务
[models.llmCompress]
model = "doubao-seed-2.0-pro"
provider = "volcengine-agent"
max_tokens = 4000      # 压缩可能需要长输出
temperature = 0.0      # 零温度保证精确压缩
timeout = 120
```

---

## 3. arclock.yaml 配置

位置：`~/.local/state/openclaw/mark42/arclock.yaml`

ArcLock 是 Mark42 的通用适配层，允许你用第三方实现替换 9 大核心锁扣。

### 3.1 设计理念

- **不配即用**：不配置任何锁扣时，全部使用 Mark42 默认实现
- **按需替换**：只配置你想替换的锁扣，其余保持默认
- **动态加载**：配置修改后调用 `mark42 arclock --reload` 生效
- **协议优先**：所有自定义实现必须符合对应 Protocol 接口

### 3.2 完整配置示例

```yaml
# ArcLock 电磁锁扣配置文件
#
# 不配 = 用 Mark42 默认实现（零配置开箱即用）
# 只配你想替换的锁扣，其余自动走默认
#
# 配置优先级: arclock.yaml > 代码内 register() > 默认实现
#
# 自定义实现需要满足对应 Protocol 接口（PEP 544）。

arclock:
  # ── 压缩锁扣 (CompressLock) ──
  # 替换 Mark42 armor 为 Headroom 或其他第三方压缩方案
  compress:
    module: "headroom_adapter"
    class: "HeadroomCompress"
    config:
      api_key: "your-api-key"
      model: "gpt-4o"

  # ── 记忆搜索锁扣 (MemoryLock) ──
  # 替换 QMD 向量引擎为 Pinecone / Weaviate / ChromaDB
  memory:
    module: "pinecone_client"
    class: "PineconeMemory"
    config:
      api_key: "your-api-key"
      environment: "us-west-2"
      index_name: "mark42-memory"

  # ── 意识/自愈锁扣 (ConsciousnessLock) ──
  # 替换 Consciousness 为自定义运维系统
  consciousness:
    module: "my_ops_system"
    class: "OpsConsciousness"
    config:
      webhook_url: "https://hooks.slack.com/services/..."
      escalation_policy: "oncall"

  # ── 错误档案锁扣 (ArchiveLock) ──
  # 替换 ErrorArchive 为 PagerDuty / Incident.io
  archive:
    module: "pagerduty_adapter"
    class: "PagerDutyArchive"
    config:
      api_key: "your-pagerduty-key"
      service_id: "P123456"
      escalation_policy: "EP789012"

  # ── 熔断器锁扣 (BreakerLock) ──
  # 替换 CircuitBreaker 为 Hystrix / Resilience4j
  breaker:
    module: "resilience4j_py"
    class: "Resilience4jBreaker"
    config:
      failure_rate_threshold: 0.5
      wait_duration_in_open_state: 60
      ring_buffer_size_in_half_open_state: 10

  # ── 健康监控锁扣 (HealthLock) ──
  # 替换内置 health-watch 为 Prometheus exporter
  health:
    module: "prometheus_exporter"
    class: "PrometheusHealth"
    config:
      endpoint: "http://prometheus:9090"
      query: 'up{job="mark42"}'
      scrape_interval: 15

  # ── 循环引擎锁扣 (EngineLock) ──
  # 替换 engine 为 Celery Beat / APScheduler
  engine:
    module: "celery_adapter"
    class: "CeleryEngine"
    config:
      broker_url: "redis://localhost:6379/0"
      result_backend: "redis://localhost:6379/1"
      timezone: "Asia/Shanghai"

  # ── 混沌工程锁扣 (ChaosLock) ──
  # 替换 ChaosEngine 为 Chaos Mesh / LitmusChaos
  chaos:
    module: "chaos_mesh_adapter"
    class: "ChaosMeshLock"
    config:
      namespace: "mark42"
      kubeconfig: "/path/to/kubeconfig"
      chaos_daemon_url: "http://localhost:2381"

  # ── 重型战甲锁扣 (HeavyLock) ──
  # 替换 heavy 为 Temporal / Airflow / Prefect
  heavy:
    module: "temporal_adapter"
    class: "TemporalHeavy"
    config:
      host: "localhost:7233"
      namespace: "mark42"
      task_queue: "heavy-tasks"
```

### 3.3 Protocol 接口详解

每个锁扣必须实现对应的 Protocol 接口（PEP 544）：

#### CompressLock - 压缩锁扣

```python
from typing import Protocol, Optional

class CompressLock(Protocol):
    """上下文压缩锁扣协议"""
    
    def compress(self, context: str, target_ratio: float = 0.5) -> str:
        """
        压缩上下文
        
        Args:
            context: 原始上下文文本
            target_ratio: 目标压缩比例（0.5 = 压缩到 50%）
            
        Returns:
            压缩后的上下文
        """
        ...
    
    def estimate_tokens(self, text: str) -> int:
        """估算文本的 Token 数量（可选）"""
        ...
```

#### MemoryLock - 记忆搜索锁扣

```python
from typing import Protocol, TypedDict, list

class Document(TypedDict):
    id: str
    content: str
    metadata: dict
    score: float

class MemoryLock(Protocol):
    """记忆搜索锁扣协议"""
    
    def search(self, query: str, top_k: int = 5) -> list[Document]:
        """
        搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            相关文档列表
        """
        ...
    
    def add(self, documents: list[Document]) -> None:
        """添加记忆到索引"""
        ...
    
    def delete(self, doc_ids: list[str]) -> None:
        """删除记忆"""
        ...
```

#### ConsciousnessLock - 意识自愈锁扣

```python
from typing import Protocol, TypedDict, Optional

class Diagnosis(TypedDict):
    healthy: bool
    issues: list[dict]
    recommendations: list[str]
    severity: str  # "low" | "medium" | "high" | "critical"

class ConsciousnessLock(Protocol):
    """意识自愈锁扣协议"""
    
    def diagnose(self) -> Diagnosis:
        """
        诊断系统健康状态
        
        Returns:
            诊断结果
        """
        ...
    
    def heal(self, issue_id: str) -> bool:
        """
        尝试自动修复指定问题
        
        Args:
            issue_id: 问题 ID
            
        Returns:
            是否修复成功
        """
        ...
    
    def alert(self, diagnosis: Diagnosis) -> None:
        """发送告警（可选）"""
        ...
```

#### ArchiveLock - 错误档案锁扣

```python
from typing import Protocol, TypedDict, Optional, list

class ErrorEntry(TypedDict):
    id: str
    timestamp: str
    error_type: str
    message: str
    stacktrace: Optional[str]
    context: dict
    status: str  # "NEW" | "RESOLVED" | "AUTO_APPROVED" | "REJECTED"

class ArchiveLock(Protocol):
    """错误档案锁扣协议"""
    
    def archive(self, error: ErrorEntry) -> str:
        """
        归档错误
        
        Args:
            error: 错误条目
            
        Returns:
            归档后的条目 ID
        """
        ...
    
    def list(self, status: Optional[str] = None, limit: int = 20) -> list[ErrorEntry]:
        """列出错误档案"""
        ...
    
    def approve(self, entry_id: str) -> bool:
        """批准处理方案"""
        ...
    
    def reject(self, entry_id: str, reason: str) -> bool:
        """驳回处理方案"""
        ...
```

#### BreakerLock - 熔断器锁扣

```python
from typing import Protocol, Any, Callable

class BreakerLock(Protocol):
    """熔断器锁扣协议"""
    
    def call(self, fn: Callable, *args, **kwargs) -> Any:
        """
        受保护的函数调用
        
        Args:
            fn: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
            
        Raises:
            CircuitBreakerError: 熔断器打开时抛出
        """
        ...
    
    def get_status(self, name: str) -> dict:
        """获取熔断器状态"""
        ...
    
    def reset(self, name: str) -> None:
        """重置熔断器"""
        ...
```

#### HealthLock - 健康监控锁扣

```python
from typing import Protocol, TypedDict

class HealthStatus(TypedDict):
    healthy: bool
    components: dict[str, bool]
    metrics: dict[str, float]
    timestamp: str

class HealthLock(Protocol):
    """健康监控锁扣协议"""
    
    def check(self) -> HealthStatus:
        """
        执行健康检查
        
        Returns:
            健康状态
        """
        ...
    
    def get_metrics(self) -> dict[str, float]:
        """获取监控指标（可选）"""
        ...
```

#### EngineLock - 循环引擎锁扣

```python
from typing import Protocol, TypedDict, Optional, Callable

class LoopStatus(TypedDict):
    id: str
    name: str
    interval: int
    next_run: str
    status: str  # "running" | "paused" | "stopped"

class EngineLock(Protocol):
    """循环引擎锁扣协议"""
    
    def schedule(self, task: Callable, interval: int, name: Optional[str] = None) -> str:
        """
        调度循环任务
        
        Args:
            task: 要执行的任务函数
            interval: 执行间隔（秒）
            name: 任务名称
            
        Returns:
            Loop ID
        """
        ...
    
    def list(self) -> list[LoopStatus]:
        """列出所有活跃 Loop"""
        ...
    
    def run_once(self, loop_id: str) -> None:
        """立即执行一次 Loop"""
        ...
    
    def cancel(self, loop_id: str) -> None:
        """取消 Loop"""
        ...
```

#### ChaosLock - 混沌工程锁扣

```python
from typing import Protocol, TypedDict, Optional

class FaultInjection(TypedDict):
    id: str
    type: str  # "latency" | "error" | "cpu" | "memory"
    target: str
    duration: int
    params: dict
    status: str  # "running" | "completed" | "failed"

class ChaosLock(Protocol):
    """混沌工程锁扣协议"""
    
    def inject(self, fault_type: str, target: str, duration: int, **params) -> str:
        """
        注入故障
        
        Args:
            fault_type: 故障类型（latency, error, cpu, memory）
            target: 目标组件
            duration: 持续时间（秒）
            **params: 故障参数
            
        Returns:
            实验 ID
        """
        ...
    
    def stop(self, experiment_id: str) -> None:
        """停止混沌实验"""
        ...
    
    def status(self, experiment_id: Optional[str] = None) -> list[FaultInjection]:
        """查看实验状态"""
        ...
```

#### HeavyLock - 重型任务锁扣

```python
from typing import Protocol, TypedDict, Optional

class JobStatus(TypedDict):
    id: str
    name: str
    status: str  # "pending" | "running" | "completed" | "failed"
    progress: float
    result: Optional[dict]
    error: Optional[str]

class HeavyLock(Protocol):
    """重型任务锁扣协议"""
    
    def submit(self, job: dict) -> str:
        """
        提交重型任务
        
        Args:
            job: 任务定义
            
        Returns:
            Job ID
        """
        ...
    
    def status(self, job_id: str) -> JobStatus:
        """查询任务状态"""
        ...
    
    def cancel(self, job_id: str) -> bool:
        """取消任务"""
        ...
    
    def result(self, job_id: str) -> Optional[dict]:
        """获取任务结果"""
        ...
```

### 3.4 自定义实现示例

下面是一个完整的自定义 CompressLock 实现示例：

```python
# my_compress.py
"""自定义 CompressLock 实现 - 使用 Headroom API"""

import requests
from typing import Optional

class HeadroomCompress:
    """基于 Headroom API 的上下文压缩实现"""
    
    def __init__(self, config: dict):
        """
        初始化压缩锁扣
        
        Args:
            config: 从 arclock.yaml 传入的配置
        """
        self.api_key = config.get("api_key")
        self.model = config.get("model", "gpt-4o")
        self.base_url = config.get("base_url", "https://api.headroom.dev")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
    
    def compress(self, context: str, target_ratio: float = 0.5) -> str:
        """
        压缩上下文
        
        Args:
            context: 原始上下文文本
            target_ratio: 目标压缩比例
            
        Returns:
            压缩后的上下文
        """
        response = self.session.post(
            f"{self.base_url}/v1/compress",
            json={
                "model": self.model,
                "content": context,
                "target_ratio": target_ratio,
                "preserve_structure": True
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["compressed"]
    
    def estimate_tokens(self, text: str) -> int:
        """估算 Token 数量"""
        response = self.session.post(
            f"{self.base_url}/v1/tokenize",
            json={"model": self.model, "content": text},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["token_count"]
```

配置到 `arclock.yaml`：

```yaml
arclock:
  compress:
    module: "my_compress"
    class: "HeadroomCompress"
    config:
      api_key: "your-headroom-api-key"
      model: "gpt-4o"
```

---

## 4. systemd 服务配置

Mark42 提供多个 systemd 服务用于生产环境部署。

### 4.1 服务列表

| 服务名 | 模板位置 | 说明 |
|---|---|---|
| `mark42-bootstrap.service` | `mark42/systemd/mark42-bootstrap.service.tmpl` | 启动时初始化 |
| `mark42-armor-guard.service` | `mark42/systemd/mark42-armor-guard.service.tmpl` | 上下文铠甲守护 |
| `mark42-engine-daemon.service` | `mark42/systemd/mark42-engine-daemon.service.tmpl` | 循环引擎 daemon |
| `mark42-watchdog.service` | `mark42/systemd/mark42-watchdog.service.tmpl` | 健康检查看门狗 |
| `mark42-watchdog.timer` | `mark42/systemd/mark42-watchdog.timer` | 看门狗定时器 |

### 4.2 服务模板结构

```ini
# mark42-armor-guard.service
[Unit]
Description=Mark42 Armor Guard - 上下文铠甲守护
Documentation=https://github.com/missyouangeled/Mark1
After=network.target openclaw.service

[Service]
Type=simple
User=%i
WorkingDirectory=/home/%i/.openclaw/workspace
ExecStart=/home/%i/.local/bin/mark42 armor --guard --interval 300
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"
Environment="MARK42_LOG_DIR=/home/%i/.local/state/openclaw/mark42/logs"
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=default.target
```

### 4.3 Drop-in 配置（自定义覆盖）

创建 drop-in 文件来覆盖默认配置，无需修改原始服务文件：

```bash
# 创建 armor-guard 服务的 drop-in 配置
mkdir -p ~/.config/systemd/user/mark42-armor-guard.service.d/
```

编辑 `~/.config/systemd/user/mark42-armor-guard.service.d/override.conf`：

```ini
[Service]
# 自定义检查间隔（改为 5 分钟 = 300 秒）
ExecStart=
ExecStart=/home/%i/.local/bin/mark42 armor --guard --interval 300

# 增加文件描述符限制
LimitNOFILE=65536

# 自定义环境变量
Environment="MARK42_CTX_WARN_PCT=65"
Environment="MARK42_CTX_ALERT_PCT=80"
Environment="MARK42_LOG_LEVEL=DEBUG"

# 内存限制
MemoryHigh=2G
MemoryMax=4G

# CPU 权重
CPUWeight=100
```

应用配置：

```bash
systemctl --user daemon-reload
systemctl --user restart mark42-armor-guard.service
```

### 4.4 常用服务操作

```bash
# 查看所有 Mark42 服务状态
systemctl --user list-units 'mark42-*.service'

# 启用服务（开机自启）
systemctl --user enable mark42-bootstrap.service
systemctl --user enable mark42-armor-guard.service
systemctl --user enable mark42-engine-daemon.service

# 启动/停止/重启
systemctl --user start mark42-armor-guard.service
systemctl --user stop mark42-armor-guard.service
systemctl --user restart mark42-armor-guard.service

# 查看服务日志
journalctl --user -u mark42-armor-guard.service -f
journalctl --user -u mark42-engine-daemon.service --since "1 hour ago"

# 查看看门狗定时器
systemctl --user list-timers mark42-watchdog.timer
```

---

## 5. Compaction-Notifier Hook 配置 (v2.8.0)

**位置**: `~/.openclaw/hooks/compaction-notifier/`

Mark42 提供的中文版压缩通知 Hook，覆盖 OpenClaw 内置的英文通知。

### 5.1 安装 Hook

```bash
# 复制 Hook 到 OpenClaw Hook 目录
cp -r mark42-pkg/hooks/compaction-notifier ~/.openclaw/hooks/
```

### 5.2 Hook 特性

| 特性 | 说明 |
|---|---|
| **纯脚本实现** | 不经过模型调用，零延迟 |
| **中文通知** | 覆盖默认英文通知 |
| **Token 统计** | 显示压缩前后 Token 数量变化 |
| **无额外配置** | 放置即生效 |

### 5.3 通知内容

- **压缩开始**: `🧹 正在压缩对话～！一会说～！`
- **压缩完成**: `✅ 压缩完成（X -> Y tokens），继续聊～！`

### 5.4 工作原理

```
OpenClaw 触发 compact
        │
        ▼
  调用 compaction-notifier hook
        │
        ├─> 开始阶段 → 发送 "正在压缩" 通知
        │
        ▼
  执行上下文压缩
        │
        ▼
  再次调用 compaction-notifier hook
        │
        └─> 完成阶段 → 发送 "压缩完成" 通知（含 Token 统计）
```

---

## 6. 环境变量

Mark42 支持通过环境变量覆盖配置。

### 5.1 路径配置

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `MARK42_WORKSPACE` | Mark42 工作目录 | `~/.openclaw/workspace` |
| `MARK42_STATE_DIR` | 状态文件目录 | `~/.local/state/openclaw/mark42` |
| `MARK42_LOG_DIR` | 日志目录 | `$MARK42_STATE_DIR/logs` |
| `MARK42_SCRATCH` | 临时目录 | `/mnt/data/openclaw/scratch` |

```bash
# 示例：使用自定义数据盘
export MARK42_WORKSPACE="/data/mark42/workspace"
export MARK42_STATE_DIR="/data/mark42/state"
export MARK42_LOG_DIR="/data/logs/mark42"
export MARK42_SCRATCH="/data/scratch"
```

### 5.2 阈值配置

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `MARK42_CTX_WARN_PCT` | 预警阈值百分比 | `70` |
| `MARK42_CTX_ALERT_PCT` | 告警阈值百分比 | `85` |
| `MARK42_CTX_CRIT_PCT` | 紧急阈值百分比 | `95` |
| `MARK42_CTX_BYTES_PER_KTOKEN` | 每千 Token 对应字节数 | `2048` |

```bash
# 示例：为大模型调整阈值
export MARK42_CTX_WARN_PCT=75
export MARK42_CTX_ALERT_PCT=88
export MARK42_CTX_CRIT_PCT=95
```

### 5.3 功能开关

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `MARK42_ALGO_SMARTCRUSH` | 是否启用 SmartCrusher 算法 | `false` |
| `MARK42_ALGO_EXPERIMENT` | 是否启用实验模式 | `false` |

```bash
# 示例：启用实验性功能
export MARK42_ALGO_SMARTCRUSH=true
export MARK42_ALGO_EXPERIMENT=true
```

### 5.4 日志配置

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `MARK42_LOG_LEVEL` | 日志级别 | `INFO` |
| `MARK42_MAX_DAEMON_LOG_LINES` | 单个 daemon 日志最大行数 | `10000` |

```bash
# 示例：调试模式
export MARK42_LOG_LEVEL=DEBUG
```

### 5.5 在 systemd 服务中设置环境变量

编辑服务的 drop-in 配置：

```ini
# ~/.config/systemd/user/mark42-armor-guard.service.d/override.conf
[Service]
Environment="MARK42_LOG_LEVEL=DEBUG"
Environment="MARK42_CTX_WARN_PCT=65"
Environment="MARK42_CTX_ALERT_PCT=80"
Environment="MARK42_ALGO_SMARTCRUSH=true"
```

---

## 📚 更多资源

- [README.md](../README.md) - 快速开始和命令速查
- [ARCHITECTURE.md](../ARCHITECTURE.md) - 架构设计说明
- [CHANGELOG.md](../CHANGELOG.md) - 版本变更历史
- `docs/design/` - 设计文档目录
