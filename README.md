# Mark42 快速开始

> 当前仓库不只是一个“workspace repo”，它实际承载着 **Mark42 模块化智能铠甲系统**。
> 这份 README 先解决一个最实际的问题：**第一次拿到仓库的人，怎么在几分钟内确认 Mark42 能跑。**

---

## 1. Mark42 是什么

Mark42 由 4 个主块组成：

- **Armor**：上下文铠甲，负责上下文健康检查、压缩、守护
- **Engine**：循环引擎，负责注册和执行 Loop
- **Heavy**：重型战甲，处理“大工程”任务分批执行
- **Logs/Status**：日志轮替、聚合状态面板

当前状态（2026-07-01 实测）：

- 生产模块：**18**
- 死代码：**0**
- 测试：**316 passed, 8 skipped, 0 fail**
- 覆盖率：**53.3%**

---

## 2. 适用范围

这份 Quick Start 只覆盖 **“本地先跑起来”**，不覆盖“开机自启/通用安装器”。

**适合：**
- 在已有 OpenClaw 环境里验证 Mark42 是否能运行
- 本地开发/调试
- 首次接手项目，先确认状态

**暂不适合：**
- 一键部署到陌生机器
- 自动安装 systemd 服务
- 零配置开箱即用

原因见文末 [为什么现在还没有通用 install.sh](#8-为什么现在还没有通用-installsh)。

---

## 3. 前置条件

### 必需

- Linux
- Python **3.10+**
- 仓库位于 OpenClaw workspace 中
- `openclaw` 命令可用（若要走 compact / daemon / Gateway 路径）

### 推荐

- 已有可工作的 OpenClaw Gateway
- `~/.openclaw/openclaw.json` 已配置模型 provider / API key

> 当前 Mark42 默认模型表使用 `MiniMax-M3`；如果没有可用 provider，LLM 分析路径会退化或失败。

---

## 4. 3 分钟最小启动

在仓库根目录执行：

```bash
python3 scripts/mark42.py --init
python3 scripts/mark42.py --config
python3 scripts/mark42.py armor --check
python3 scripts/mark42.py status
```

### 预期结果

#### 1) `--init`
首次运行会创建：

- `~/.local/state/openclaw/mark42/config.json`
- `~/.local/state/openclaw/mark42/armor/`
- `~/.local/state/openclaw/mark42/engine/`
- `~/.local/state/openclaw/mark42/heavy/`

如果已经初始化过，会提示：

```text
⚙️ Mark42 已初始化（版本: 2.3.0）
```

#### 2) `--config`
你应该能看到：

- 版本号
- 阈值（WARN / ALERT / CRIT）
- 模型配置表
- 守护模式设置

#### 3) `armor --check`
你应该能看到：

- 上下文使用率
- estimatedTokens / contextWindow
- 当前健康摘要（如“上下文 xx%，正常”）

#### 4) `status`
你应该能看到聚合状态页，至少包含：

- Armor 状态
- Engine Loop 数量
- Heavy 活跃任务
- Logs/Broker/Scratch 统计

---

## 5. 常用启动方式

### A. 只做健康检查（最安全）

```bash
python3 scripts/mark42.py armor --check
python3 scripts/mark42.py status
```

适合首次接手、先看系统活没活。

### B. 前台启动整套守护（开发/调试）

```bash
python3 scripts/mark42.py assemble
```

效果：

- 启动 `armor --guard`
- 启动 `engine --daemon`
- 前台保持监护
- `Ctrl+C` 会优雅关闭子进程

适合本地调试。**不要把它误当成通用安装器。**

### C. 单独启动某个组件

```bash
python3 scripts/mark42.py armor --guard --interval 300
python3 scripts/mark42.py engine --daemon --interval 30
```

适合分开看日志、单独定位问题。

---

## 6. 验证命令（建议照着跑）

### 6.1 CLI 帮助是否正常

```bash
python3 scripts/mark42.py --help
python3 scripts/mark42-tests.py --help
```

### 6.2 配置是否能读

```bash
python3 scripts/mark42.py --config
```

### 6.3 聚合状态是否能出 JSON

```bash
python3 scripts/mark42.py status --json
```

### 6.4 测试是否通过

```bash
python3 -m pytest scripts/tests/ --no-cov -q
```

当前基线（2026-07-01）：

```text
316 passed, 8 skipped
```

---

## 7. 目录与状态文件

### 代码入口

- CLI 入口：`scripts/mark42.py`
- 实际主逻辑：`scripts/mark42_modules/cli.py`

### 运行时状态

默认状态目录：

- `~/.local/state/openclaw/mark42/`

其中：

- `armor/`：压缩、memory-index、actions
- `engine/`：loops、daemon-heartbeat
- `heavy/`：大工程任务状态

### 数据盘/回退路径

- `SCRATCH`：优先 `MARK42_SCRATCH`，否则 `/mnt/data/openclaw/scratch`，不存在时回退 `~/.local/state/openclaw/scratch`
- `LOG_DIR`：优先 `/mnt/data/openclaw/mark42/logs`，不存在时回退 `~/.local/state/openclaw/mark42/logs`

---

## 8. 为什么现在还没有通用 `install.sh`

**不是没想写，是现在写出来大概率会骗人。**

目前 systemd/service 这套仍然带有**当前机器专用硬编码**：

- `/home/missyouangeled/.openclaw/workspace/...`
- `/home/missyouangeled/.local/state/openclaw/mark42/...`
- `openclaw-gateway.service` 依赖

具体文件包括：

- `tools/mark42-armor-guard/mark42-armor-guard.service`
- `tools/mark42-engine-daemon/mark42-engine-daemon.service`
- `tools/mark42-bootstrap/mark42-bootstrap.service`
- `tools/mark42-watchdog/mark42-watchdog.service`
- `tools/mark42-bootstrap/mark42-bootstrap.sh`
- `tools/mark42-watchdog/mark42-watchdog.sh`

所以现在如果直接写一个“通用 install.sh”，会有两个坏结果：

1. **看起来能装，实际上只在点点这台机器能跑**
2. **把路径硬编码重新扩散一遍**

### 这意味着什么

当前更诚实的状态是：

- ✅ **Quick Start 已可用**：能让新接手的人先跑通、先验活
- ❌ **通用安装器尚不可交付**：必须先去掉 service / shell 脚本里的用户路径硬编码

### install.sh 的前置条件

在写通用 `install.sh` 之前，至少要先完成：

1. service 模板参数化（不要写死用户名/工作区）
2. bootstrap/watchdog shell 脚本路径参数化
3. 检测 OpenClaw Gateway 是否存在
4. 检测 `openclaw` 命令是否可用
5. 明确“开发模式”和“生产守护模式”的安装差异

不先做这几步，`install.sh` 只是一个更大的坑。

---

## 9. 下一步建议

如果你是维护者，建议按这个顺序继续：

1. **先看这份 README 跑一遍最小命令**
2. 跑测试确认基线
3. 再做 service 去硬编码
4. 最后再写通用 `install.sh`

---

## 10. 一句话总结

**现在的 Mark42 已经适合“本地先跑起来”，还不适合“拿到陌生机器一键装好”。**

这是 7/01 这版 Quick Start 要表达的核心现实。