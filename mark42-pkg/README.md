# Mark42

模块化智能铠甲系统 — 为 [OpenClaw](https://github.com/nicepkg/openclaw) 提供上下文守护与循环引擎。

## 功能

- **上下文铠甲 (Armor)**: 实时监测上下文使用率，超阈值自动 LLM 压缩 + 预警
- **循环引擎 (Engine)**: 定时执行循环任务（健康检查、记忆索引、模型回退等）
- **重型战甲 (Heavy)**: 大型异步任务队列与执行
- **日志轮替**: 自动轮替 OpenClaw 会话与 broker 日志

## 快速开始

### 1. 安装

```bash
git clone https://github.com/missyouangeled/Mark1.git
cd Mark1/mark42-pkg
bash install.sh
```

> 安装脚本会自动创建 venv、安装 mark42 命令、渲染 systemd 服务。
> 前提：Python >= 3.10、OpenClaw 已安装。

### 2. 初始化配置

```bash
mark42 --init
```

这会在 `~/.config/mark42/config.toml` 生成默认配置（阈值、路径、模型等）。

### 3. 查看状态

```bash
mark42 status
```

如果 OpenClaw 正在运行，你会看到上下文使用率、Armor/Engine/Heavy 三模块状态。

### 4. 启动守护服务

```bash
mark42 assemble
```

这会拉起 armor-guard 和 engine-daemon 两个守护进程，开始自动监控。

### 5. 手动检查上下文

```bash
mark42 armor --check
```

## 命令速查

| 命令 | 说明 |
|---|---|
| `mark42 status` | 一屏聚合系统状态 |
| `mark42 armor --check` | 手动检查上下文使用率 |
| `mark42 armor --guard` | 启动铠甲守护模式 |
| `mark42 engine start` | 启动循环引擎 |
| `mark42 assemble` | 一键启动完整战甲 |
| `mark42 --init` | 初始化配置文件 |
| `mark42 --config` | 查看/修改配置 |
| `mark42 --help` | 查看所有命令 |

## 依赖

- Python >= 3.10
- OpenClaw（已安装并配置）
- Linux（systemd）

## 配置

| 文件 | 用途 |
|---|---|
| `~/.config/mark42/config.toml` | Mark42 自身配置（阈值、路径等） |
| `~/.openclaw/openclaw.json` | OpenClaw 配置（API key、模型等） |
| `~/.local/state/openclaw/mark42/` | 运行状态、日志、actions 审计 |

## License

MIT
