# Mark42

> 当前仓库不只是一个“workspace repo”，它实际承载着 **Mark42 模块化智能铠甲系统**。  
> 如果你是第一次点进来，先记住一句话：
>
> **Mark42 现在已经是一套真实运行中的内部工程系统，而不只是概念代码。**

---

## 1. 当前状态（先看这个）

### 当前一句话结论

- **本机运行闭环：成立**
- **核心守护链路：正常**
- **语义索引链路：已修复并恢复**
- **当前最大边界：尚未完成“陌生机器从零开始”的真实全链路验收**

### 最新基线（2026-07-01）

- 生产模块：**18**
- 死代码：**0**
- 测试：**526 passed, 2 skipped**
- 整体覆盖率：**74.7%**
- 核心服务：`bootstrap / engine-daemon / armor-guard / watchdog.timer / embed-sidecar` **均 active**
- 语义索引：**7206 segments / 384 dim**
- Armor 真压缩链路：**已现场验收成功**（`openclaw-sessions-compact`，会话真实缩小）

### 建议先读哪几份文档

如果你只想 10 分钟建立全貌，按这个顺序读：

1. `docs/design/mark42-最终审查报告-20260701.md`  
   - 看阶段裁定 / 当前权威结论
2. `docs/design/mark42-当前总体状态报告-20260701.md`  
   - 看当前运行态、已修问题、剩余风险
3. `docs/design/mark42-发布摘要-20260701.md`  
   - 看 GitHub / 回看友好的变更摘要
4. `docs/design/mark42-测试覆盖接力开发方向-20260701.md`  
   - 看当前测试接力主线
5. `docs/design/mark42-文档目录.md`  
   - 看完整文档地图

---

## 2. Mark42 是什么

Mark42 由 4 个主块组成：

- **Armor**：上下文铠甲，负责上下文健康检查、压缩、守护
- **Engine**：循环引擎，负责注册和执行 Loop
- **Heavy**：重型战甲，处理“大工程”任务分批执行
- **Logs/Status**：日志轮替、聚合状态面板

它的核心价值不是“功能点很多”，而是已经建立了真实的运行骨架：

- 守护
- 心跳
- 状态聚合
- 日志轮替
- actions 留痕
- watchdog 告警
- systemd 托管
- 运行态巡检与修复复核

换句话说，Mark42 现在更像一套**围绕 OpenClaw 工作流建立的运行护栏层**。

---

## 3. 适用范围

这份 Quick Start 只覆盖 **“本地先跑起来”**，不覆盖“开机自启/通用安装器”。

**适合：**
- 在已有 OpenClaw 环境里验证 Mark42 是否能运行
- 本地开发/调试
- 首次接手项目，先确认状态

**暂不适合：**
- 一键部署到陌生机器
- 自动安装 systemd 服务
- 零配置开箱即用

原因见文末 [为什么现在还没有通用 install.sh](#9-installsh-现在到了哪一步)。

---

## 4. 前置条件

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

## 5. 3 分钟最小启动

在仓库根目录执行：

```bash
python3 scripts/mark42.py --init
python3 scripts/mark42.py --config
python3 scripts/mark42.py armor --check
python3 scripts/mark42.py status --json
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

#### 4) `status --json`
你应该能看到聚合状态输出，至少包含：

- Armor 状态
- Engine Loop 数量
- Heavy 活跃任务
- Logs/Broker/Scratch 统计

---

## 6. 常用启动方式

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

### D. 开发模式 vs 生产守护模式（重要）

#### 开发模式
用这个入口：

```bash
python3 scripts/mark42.py assemble
```

适合场景：
- 本地调试
- 改代码后立刻验证
- 需要前台看日志 / `Ctrl+C` 立即停机

特点：
- 前台跑
- 当前 shell 退出就结束
- 更像“开发会话”，不是长期托管

#### 生产守护模式
用这个入口：

```bash
tools/mark42-systemd/install.sh --apply
```

然后再按验收流程启动/重启对应 unit。

适合场景：
- 这台机器要长期保活
- 需要 user systemd 托管
- 需要 watchdog timer 定时兜底

特点：
- 由 user systemd 托管
- shell 退出不影响服务继续运行
- 更像“长期运行配置”，不是临时调试会话

#### 不要混用的规则

- **临时调试**：优先 `assemble`
- **长期运行**：优先 user systemd
- **不要在 `assemble` 前台跑着的时候，再手动启动同一套 systemd daemon**
- **也不要在 systemd 已托管稳定运行时，又额外开一个 `assemble` 前台副本**

否则最容易出现：
- `armor --guard` / `engine --daemon` 双开
- 心跳文件、日志、broker 事件互相污染
- 你以为在看“生产现场”，其实看的是前台临时进程

---

## 7. 验证命令（建议照着跑）

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

当前推荐参考基线（2026-07-01 最新）：

```text
526 passed, 2 skipped
coverage: 74.7%
```

> 如果你在看更早文档里见到 `316 passed / 45.9%`，那是 7/01 上午较早阶段的审查基线，不是当前最新数字。

---

## 8. 快速导航：目录 / 文档 / 测试 / systemd

### 代码与测试入口

| 目标 | 路径 / 命令 |
|---|---|
| CLI 入口 | `scripts/mark42.py` |
| 主逻辑 | `scripts/mark42_modules/cli.py` |
| 单元/集成测试 | `scripts/tests/` |
| 全量回归 | `python3 -m pytest scripts/tests/ --cov=scripts/mark42_modules --cov-report=term-missing -q` |
| 当前测试接力说明 | `docs/design/mark42-测试覆盖接力开发方向-20260701.md` |

### 文档入口

| 想看什么 | 入口 |
|---|---|
| 当前阶段裁定 | `docs/design/mark42-最终审查报告-20260701.md` |
| 当前运行态 | `docs/design/mark42-当前总体状态报告-20260701.md` |
| 对外可读摘要 | `docs/design/mark42-发布摘要-20260701.md` |
| 完整文档地图 | `docs/design/mark42-文档目录.md` |
| 详细变更留痕 | `docs/design/mark42-更新日志.md` |

### 运行时目录

| 目标 | 路径 |
|---|---|
| 主状态目录 | `~/.local/state/openclaw/mark42/` |
| armor 状态 | `~/.local/state/openclaw/mark42/armor/` |
| engine 状态 | `~/.local/state/openclaw/mark42/engine/` |
| heavy 状态 | `~/.local/state/openclaw/mark42/heavy/` |
| scratch（默认优先） | `/mnt/data/openclaw/scratch` |
| 日志目录（默认优先） | `/mnt/data/openclaw/mark42/logs` |

### systemd 工具链入口

| 场景 | 命令 |
|---|---|
| 安装前体检 | `tools/mark42-systemd/preflight.sh` |
| 安装预览（dry-run） | `tools/mark42-systemd/install.sh` |
| 真正写入 user systemd | `tools/mark42-systemd/install.sh --apply` |
| 最低验收 | `tools/mark42-systemd/verify.sh` |
| 回退旧 unit | `tools/mark42-systemd/restore.sh --backup-dir <dir> --apply` |
| 卸载 unit | `tools/mark42-systemd/uninstall.sh --apply` |

### 一句话边界

- **README 负责快速导航，不展开所有运维细节。**
- 更细的背景、风险、裁定口径，优先看：
  - `docs/design/mark42-当前总体状态报告-20260701.md`
  - `docs/design/mark42-最终审查报告-20260701.md`
  - `docs/design/mark42-更新日志.md`

---

## 10. 下一步建议

如果你是维护者，建议按这个顺序继续：

1. **先看这份 README 跑一遍最小命令**
2. 跑测试确认基线
3. 先执行 `tools/mark42-systemd/preflight.sh`
4. 再执行 `tools/mark42-systemd/install.sh` 看 dry-run 输出
5. 确认宿主机具备 openclaw / Gateway / Python 后，再执行 `--apply`
6. 按上面的最小验收流程逐项确认
7. 若要撤掉托管，优先用 `tools/mark42-systemd/uninstall.sh`

---

## 11. 一句话总结

**现在的 Mark42 已经适合“本地先跑起来”，还不适合“拿到陌生机器一键装好”。**

这是 7/01 这版 Quick Start 要表达的核心现实。
