# Mark42

模块化智能铠甲系统 - 为 [OpenClaw](https://github.com/openclaw/openclaw) 提供上下文守护与循环引擎。

版本：`v2.8.0`

| 快速开始 | 完整教程 | 配置说明 | 架构设计 |
|----------|----------|----------|----------|
| [QUICKSTART.md](QUICKSTART.md) | [TUTORIAL.md](TUTORIAL.md) | [CONFIG-GUIDE.md](docs/CONFIG-GUIDE.md) | [ARCHITECTURE.md](ARCHITECTURE.md) |

**3 步跑起来：**
```bash
cd mark42-pkg && bash install.sh   # 安装
mark42 --init                      # 配置
mark42 armor --check               # 检查
```

---

## ✨ 功能概览

Mark42 由 10 大核心模块组成，通过 broker 事件总线联动：

| 模块 | 说明 | 核心能力 |
|---|---|---|
| **🛡️ Armor 上下文铠甲** | 实时监控上下文使用率，超阈值自动压缩 | LLM 压缩 / SmartCrusher 算法 / PII 脱敏 |
| **🔄 Engine 循环引擎** | 定时执行循环任务 | 健康检查 / 记忆索引 / 模型回退 / 自定义 Loop |
| **⚙️ Heavy 重型战甲** | 大型异步任务队列与执行 | 工程分批 / 上下文感知 / 后台执行 |
| **🧠 Consciousness 意识自愈** | 自监控与故障恢复 | 异常检测 / 自动修复 / 性能诊断 |
| **📦 ErrorArchive 错误档案** | 错误统一归档与决策 | 错误分类 / 人工审批 / 知识库沉淀 |
| **⚡ CircuitBreaker 熔断器** | 防止级联故障 | 熔断检测 / 自动恢复 / 降级策略 |
| **🌪️ ChaosEngine 混沌工程** | 主动注入故障测试 | 延迟注入 / 错误模拟 / 资源耗尽 |
| **📋 CoreRegistry 核心注册** | 模块注册与发现 | 动态加载 / 依赖检查 / 版本管理 |
| **🤖 AdvisorClient 顾问客户端** | 与 OpenClaw Advisor 通信 | 指标上报 / 建议获取 / 决策执行 |
| **🔌 ArcLock 电磁锁扣** | 通用适配层，支持第三方替换 | 9 大扩展点，零配置开箱即用 |
| **🔍 Audit 审计系统** | 压缩前后上下文完整性审计 | 6 类核对 / Constraint Pinning / Artifact Trail |
| **🔒 ConstraintPinner** | 治理衰减防护 | compact 后自动重新注入关键约束规则 |

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/missyouangeled/Mark1.git
cd Mark1/mark42-pkg
```

### 2. 安装 Mark42

```bash
bash install.sh
```

安装脚本会自动：
- 创建 Python 虚拟环境
- 安装 Mark42 CLI
- 渲染 systemd 服务模板
- 初始化 ArcLock 配置
- 生成默认 config.toml
- 运行 `mark42 status` 验证安装

### 3. 初始化配置

```bash
mark42 --init
```

这会在 `~/.config/mark42/config.toml` 生成默认配置。

### 4. 启动完整战甲

```bash
mark42 assemble
```

一键拉起：
- `armor-guard` 守护进程（上下文监控）
- `engine-daemon` 守护进程（循环引擎）

### 5. 验证状态

```bash
mark42 status
```

如果一切正常，你会看到：
- 上下文使用率百分比
- Armor / Engine / Heavy 三模块状态
- 最近压缩记录
- 活跃 Loop 列表

---

## 🔌 ArcLock 电磁锁扣

ArcLock 是 Mark42 的通用适配层，设计理念：**"不配即用，按需扩展"**。

### 9 大锁扣

| 锁扣 | Protocol 接口 | 可替换为 | 用途 |
|---|---|---|---|
| **CompressLock** | `compress(context: str) -> str` | Headroom / 自定义压缩 | 替换上下文压缩算法 |
| **MemoryLock** | `search(query: str) -> list[Doc]` | Pinecone / Weaviate / ChromaDB | 替换记忆向量引擎 |
| **ConsciousnessLock** | `diagnose() -> Diagnosis` | 自定义运维系统 | 替换自监控与自愈逻辑 |
| **ArchiveLock** | `archive(error: Error) -> str` | PagerDuty / Incident.io | 替换错误归档系统 |
| **BreakerLock** | `call(fn, *args, **kwargs) -> Any` | Hystrix / Resilience4j | 替换熔断器实现 |
| **HealthLock** | `check() -> HealthStatus` | Prometheus Exporter | 替换健康监控 |
| **EngineLock** | `schedule(task, interval) -> str` | Celery Beat / APScheduler | 替换循环调度器 |
| **ChaosLock** | `inject(fault) -> None` | Chaos Mesh / LitmusChaos | 替换混沌工程引擎 |
| **HeavyLock** | `submit(job) -> JobStatus` | Temporal / Airflow / Prefect | 替换重型任务调度 |

### 如何自定义

1. 编辑配置文件：`~/.local/state/openclaw/mark42/arclock.yaml`
2. 只配置你想替换的锁扣，其余自动走 Mark42 默认实现

```yaml
arclock:
  # 示例：替换 CompressLock 为 Headroom
  compress:
    module: "headroom_adapter"
    class: "HeadroomCompress"
    config:
      api_key: "your-api-key"
      model: "gpt-4o"

  # 示例：替换 MemoryLock 为 Pinecone
  memory:
    module: "pinecone_client"
    class: "PineconeMemory"
    config:
      api_key: "your-api-key"
      environment: "us-west-2"
```

配置优先级：`arclock.yaml` > 代码内 `register()` > 默认实现

> 💡 完整示例和 Protocol 接口说明请参考：`docs/CONFIG-GUIDE.md`

---

## 📝 命令速查表

### 基础命令

| 命令 | 说明 |
|---|---|
| `mark42 --init` | 初始化配置文件 |
| `mark42 --config` | 查看当前配置 |
| `mark42 --version` | 查看版本 |
| `mark42 --help` | 查看所有命令 |

### 状态命令

| 命令 | 说明 |
|---|---|
| `mark42 status` | 一屏聚合系统状态 |
| `mark42 status --json` | 输出 JSON 格式 |
| `mark42 status --verbose` | 输出详细状态信息 |
| `mark42 status --metrics` | 显示 Prometheus 指标 |

### Armor 上下文铠甲

| 命令 | 说明 |
|---|---|
| `mark42 armor --check` | 检查上下文健康度 |
| `mark42 armor --compress` | 触发智能压缩 |
| `mark42 armor --dry-run` | 压缩预览（不实际修改） |
| `mark42 armor --guard` | 启动守护模式 |
| `mark42 armor --guard --interval 300` | 守护模式，指定检查间隔（秒） |
| `mark42 armor --queue-stats` | 查看压缩队列统计 |
| `mark42 armor --smartcrush` | SmartCrusher 算法压测 |

### Engine 循环引擎

| 命令 | 说明 |
|---|---|
| `mark42 engine --list` | 列出活跃 Loop |
| `mark42 engine --start --task "任务描述" --interval 300` | 注册新 Loop |
| `mark42 engine --templates` | 列出可用模板 |
| `mark42 engine --run <loop-id>` | 手动触发 Loop 执行 |
| `mark42 engine --kill <loop-id>` | 终止 Loop |
| `mark42 engine --daemon` | 守护进程模式 |
| `mark42 engine --daemon --interval 30` | daemon 模式，指定扫描间隔 |
| `mark42 engine --watch-task <task-name>` | 监控大工程任务 |

### Heavy 重型战甲

| 命令 | 说明 |
|---|---|
| `mark42 heavy --detect <path>` | 自动检测工程是否为大工程 |
| `mark42 heavy --preflight <path>` | 大工程预检 |
| `mark42 heavy --start <path> --task-name <name>` | 大工程开工 |
| `mark42 heavy --finish` | 大工程收工 |
| `mark42 heavy --execute` | 执行下一批次（默认 dry-run） |
| `mark42 heavy --execute-all` | 执行所有 pending 批次 |
| `mark42 heavy --execute-now` | 【安全】实际启动后台进程 |
| `mark42 heavy --cleanup` | 清理 scratch 目录 |

### ArcLock 电磁锁扣

| 命令 | 说明 |
|---|---|
| `mark42 arclock --list` | 列出已配置的锁扣 |
| `mark42 arclock --status` | 查看各锁扣当前实现 |
| `mark42 arclock --reload` | 重新加载配置 |
| `mark42 arclock --test <lock-name>` | 测试锁扣功能 |

### CircuitBreaker 熔断器

| 命令 | 说明 |
|---|---|
| `mark42 breaker --status` | 查看熔断器状态 |
| `mark42 breaker --list` | 列出所有断路器 |
| `mark42 breaker --reset <name>` | 重置指定断路器 |
| `mark42 breaker --metrics` | 显示熔断器指标 |

### ChaosEngine 混沌工程

| 命令 | 说明 |
|---|---|
| `mark42 chaos --list` | 列出可用故障注入 |
| `mark42 chaos --inject <fault-name>` | 注入指定故障 |
| `mark42 chaos --stop <experiment-id>` | 停止混沌实验 |
| `mark42 chaos --status` | 查看实验状态 |

### CoreRegistry 核心注册

| 命令 | 说明 |
|---|---|
| `mark42 cores --list` | 列出所有已注册模块 |
| `mark42 cores --status <module-name>` | 查看模块状态 |
| `mark42 cores --deps` | 显示模块依赖图 |
| `mark42 cores --health` | 模块健康检查 |

### AdvisorClient 顾问客户端

| 命令 | 说明 |
|---|---|
| `mark42 advisor --connect` | 连接 Advisor 服务 |
| `mark42 advisor --status` | 查看连接状态 |
| `mark42 advisor --suggest` | 获取优化建议 |
| `mark42 advisor --apply <suggestion-id>` | 应用建议 |

### ErrorArchive 错误档案

| 命令 | 说明 |
|---|---|
| `mark42 archive list` | 列出错误档案 |
| `mark42 archive show <entry-id>` | 查看错误详情 |
| `mark42 archive approve <entry-id>` | 批准处理方案 |
| `mark42 archive reject <entry-id>` | 驳回处理方案 |
| `mark42 archive stats` | 查看归档统计 |

### Logs 日志轮替

| 命令 | 说明 |
|---|---|
| `mark42 logs --rotate` | 执行日志轮替 |
| `mark42 logs --status` | 查看日志轮替状态 |

### Assemble 完整战甲

| 命令 | 说明 |
|---|---|
| `mark42 assemble` | 一键启动完整战甲 |
| `mark42 assemble --status` | 查看 assemble 状态 |
| `mark42 assemble --stop` | 停止所有守护进程 |
| `mark42 assemble --restart` | 重启所有守护进程 |

### Cost 成本追踪

| 命令 | 说明 |
|---|---|
| `mark42 cost today` | 今日消费统计 |
| `mark42 cost month` | 本月消费统计 |
| `mark42 cost top` | Top N 消费排名 |

---

## ⚙️ 配置文件

| 路径 | 用途 | 说明 |
|---|---|---|
| `~/.openclaw/openclaw.json` | OpenClaw 主配置 | 模型 providers、API key、基础路径 |
| `~/.config/mark42/config.toml` | Mark42 配置 | 阈值、路径、模型路由、daemon 配置 |
| `~/.local/state/openclaw/mark42/arclock.yaml` | ArcLock 配置 | 9 大锁扣自定义实现 |
| `~/.local/state/openclaw/mark42/` | 状态目录 | PID 文件、运行状态、压缩历史 |
| `~/.local/state/openclaw/mark42/logs/` | 日志目录 | 各守护进程日志 |
| `~/.local/state/openclaw/scratch/` | 临时目录 | 大工程分批数据、中间文件 |

---

## 🔧 systemd 服务

| 服务名 | 说明 | 推荐启用 |
|---|---|---|
| `mark42-bootstrap.service` | 启动时初始化服务 | ✅ 是 |
| `mark42-armor-guard.service` | 上下文铠甲守护 | ✅ 是 |
| `mark42-engine-daemon.service` | 循环引擎 daemon | ✅ 是 |
| `mark42-watchdog.timer` | 看门狗定时器（每 5 分钟） | ✅ 是 |
| `mark42-watchdog.service` | 看门狗健康检查服务 | ✅ 是 |

### 常用操作

```bash
# 用户级服务（推荐）
systemctl --user enable mark42-bootstrap.service
systemctl --user start mark42-armor-guard.service
systemctl --user status mark42-engine-daemon.service
systemctl --user restart mark42-armor-guard.service

# 系统级服务（需要 root）
sudo systemctl enable mark42-bootstrap.service
sudo systemctl start mark42-armor-guard.service

# 查看日志
journalctl --user -u mark42-armor-guard.service -f
```

### 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `MARK42_WORKSPACE` | Mark42 工作目录 | `~/.openclaw/workspace` |
| `MARK42_STATE_DIR` | 状态文件目录 | `~/.local/state/openclaw/mark42` |
| `MARK42_LOG_DIR` | 日志目录 | `$MARK42_STATE_DIR/logs` |
| `MARK42_SCRATCH` | 临时目录 | `/mnt/data/openclaw/scratch` |
| `MARK42_CTX_WARN_PCT` | 预警阈值百分比 | `70` |
| `MARK42_CTX_ALERT_PCT` | 告警阈值百分比 | `85` |
| `MARK42_CTX_CRIT_PCT` | 紧急阈值百分比 | `95` |

---

## 🧪 测试

### 运行单元测试

```bash
cd mark42-pkg
python3 -m pytest tests/unit/ -v
```

### 运行集成测试

```bash
python3 -m pytest tests/integration/ -v
```

### 覆盖率测试

```bash
python3 -m pytest --cov=mark42 --cov-report=html
```

### 测试统计 (v2.8.0)

| 测试类型 | 数量 |
|---|---|
| Audit 单元测试 | 73 |
| 其他单元测试 | 163 |
| 集成测试 | 12 |
| **总计** | **248** |

| 模块 | 覆盖率 |
|---|---|
| checker | 87% |
| snapshot_reader | 93% |
| summary_extractor | 80%+ |
| report | 90% |
| pinning | 91% |
| builtin_audit | 87% |

**新增测试**: 5 个 SQLite Fallback 测试（正常返回/无 compaction/CLI 错误/超时/命令不存在）

### 手动测试

```bash
# 测试上下文压缩
mark42 armor --check
mark42 armor --compress --dry-run

# 测试 Loop 引擎
mark42 engine --start --task "测试任务" --interval 60
mark42 engine --list

# 测试混沌工程
mark42 chaos --inject latency --duration 10 --ms 500
```

---

## 🐳 Docker

### 构建镜像

```bash
cd mark42-pkg
docker build -t mark42:latest .
```

### 运行容器

```bash
docker run -d \
  --name mark42 \
  -v ~/.openclaw:/root/.openclaw \
  -v ~/.config/mark42:/root/.config/mark42 \
  -v ~/.local/state/openclaw:/root/.local/state/openclaw \
  mark42:latest
```

### Docker Compose

```yaml
version: '3.8'
services:
  mark42:
    build: .
    volumes:
      - ~/.openclaw:/root/.openclaw
      - ~/.config/mark42:/root/.config/mark42
      - mark42-state:/root/.local/state/openclaw
    restart: unless-stopped

volumes:
  mark42-state:
```

---

## 📚 更多文档

- `docs/CONFIG-GUIDE.md` - 详细配置向导
- `docs/design/` - 设计文档目录
- `ARCHITECTURE.md` - 架构说明
- `CHANGELOG.md` - 变更日志

---

## 📄 License

MIT
