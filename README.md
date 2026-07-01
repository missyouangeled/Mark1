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

## 8. 目录与状态文件

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

## 9. `install.sh` 现在到了哪一步

**它已经存在，但目前更适合“维护者手动验收后再 apply”，还不适合宣称“一键安装完成”。**

现在已经完成：

- ✅ 4 个 service 文件改成 **模板占位符**（`__MARK42_*`）
- ✅ `bootstrap.sh` / `watchdog.sh` 改成 **环境变量驱动**
- ✅ `tools/mark42-systemd/install.sh` 已补上
  - 默认 **dry-run**
  - 传 `--apply` 才真正写入 `~/.config/systemd/user/`
  - 会渲染 4 个 service 模板，并复制 `mark42-watchdog.timer`
  - 会做基础检测：`python/systemctl/sed/install`、`mark42.py`、模板文件是否存在
  - 会提示 `openclaw` 命令和 `openclaw-gateway.service` 当前是否可用

### 陌生机器安装前置条件清单

在陌生机器上，**不要一上来就 `--apply`**。先对这张清单：

#### 必须有

1. **Linux + user systemd 可用**
   - 至少要能执行：
   ```bash
   systemctl --user status
   ```
2. **Python 3.10+ 可用**
   - 至少要能执行：
   ```bash
   python3 --version
   ```
3. **当前仓库就在目标 workspace 里**
   - 并且 `scripts/mark42.py` 存在
4. **基础命令存在**
   - `systemctl`
   - `sed`
   - `install`
5. **目标用户对自己的 `~/.config/systemd/user/` 有写权限**
6. **OpenClaw Gateway 已装好，且 `openclaw-gateway.service` 已装好并建议先确认其正常**
   - 因为 bootstrap / engine 的长期行为默认建立在 Gateway 可用之上

#### 最好先确认

1. **`openclaw` 命令可用**
2. **`~/.openclaw/openclaw.json` 已有可工作的 provider / API key**
3. **状态目录与数据盘路径策略明确**
   - 默认 state：`~/.local/state/openclaw/mark42`
   - 默认 scratch：`/mnt/data/openclaw/scratch`
4. **知道这台机器要走哪种模式**
   - 临时调试 → `python3 scripts/mark42.py assemble`
   - 长期托管 → `tools/mark42-systemd/install.sh --apply`

#### 没确认前先别装

如果下面这些还不明确，建议先停在 dry-run：

- `openclaw-gateway.service` 是否真的能稳定运行
- 这台机器有没有 user systemd 会话环境
- `/mnt/data/openclaw/scratch` 不存在时，是否接受默认 scratch 策略
- 这台机器是临时开发机，还是要长期保活的生产托管机
- 出问题后是否有回退办法（至少要先备份旧 unit）

### 推荐先这样用

先看 dry-run：

```bash
tools/mark42-systemd/preflight.sh
tools/mark42-systemd/install.sh
```

需要真正写入时再执行：

```bash
tools/mark42-systemd/install.sh --apply
```

可选参数：

- `--workspace PATH`
- `--python PATH`
- `--state-dir PATH`
- `--scratch PATH`
- `--user-unit-dir PATH`

### systemd 工具链标准流程（推荐按顺序）

#### 1）首装流程

```bash
tools/mark42-systemd/preflight.sh
tools/mark42-systemd/install.sh
tools/mark42-systemd/install.sh --apply
systemctl --user start mark42-bootstrap.service
systemctl --user start mark42-engine-daemon.service
systemctl --user start mark42-armor-guard.service
systemctl --user enable --now mark42-watchdog.timer
tools/mark42-systemd/verify.sh
```

适用：
- 第一次把 Mark42 挂到这台机器的 user systemd
- 准备把这台机器切到长期托管模式

#### 2）回退流程

```bash
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS --apply
tools/mark42-systemd/verify.sh
```

适用：
- `install.sh --apply` 后想恢复旧 unit
- 需要退回到已知稳定版本的 user systemd 配置

#### 3）最低验收流程

```bash
tools/mark42-systemd/verify.sh
```

用途：
- 安装后验收
- 恢复后验收
- 日后怀疑 user systemd 托管状态跑偏时，先做一次标准检查

#### 4）卸载流程

```bash
tools/mark42-systemd/uninstall.sh
tools/mark42-systemd/uninstall.sh --apply
```

用途：
- 只卸载 Mark42 的 user systemd unit
- 不删除工作区代码 / state / scratch 数据

### 现在已经补出的辅助脚本

#### `tools/mark42-systemd/preflight.sh`

用途：
- 把“陌生机器安装前置条件清单”脚本化
- 在真正 `--apply` 前先跑一次机器体检
- 额外补了 Gateway / provider 健康探测

建议先跑：

```bash
tools/mark42-systemd/preflight.sh
```

通过标准：
- `FAIL=0` 才建议进入 `install.sh --apply`
- 有 `WARN` 时不一定阻塞，但要人工确认

当前已覆盖的健康检查：
- `openclaw status`
- `openclaw health --json`（要求健康快照 `ok=true`）
- `openclaw models status --json`（确认 provider/auth 状态面可读，并输出保守摘要）

当前 provider 摘要会保守给出：
- `providers=<n>`
- `providersWithOAuth=<n>`
- `oauthProfiles=<n>`
- `unusableProfiles=<n>`
- `missingProvidersInUse=<n>`

#### `tools/mark42-systemd/uninstall.sh`

用途：
- 把 user systemd 卸载步骤脚本化

先看 dry-run：

```bash
tools/mark42-systemd/uninstall.sh
```

真正卸载：

```bash
tools/mark42-systemd/uninstall.sh --apply
```

它默认只移除 user systemd unit，**不会删除**：
- 工作区代码
- `~/.local/state/openclaw/mark42/`
- `/mnt/data/openclaw/scratch`

#### `tools/mark42-systemd/restore.sh`

用途：
- 恢复 `install.sh --apply` 之前自动备份的旧 Mark42 unit
- 默认 dry-run，只预览恢复动作

示例：

```bash
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS --apply
```

恢复行为：
- stop 当前 Mark42 service（容错）
- disable 当前 `mark42-watchdog.timer`（容错）
- 把备份目录中的 `mark42-*.service` / `mark42-watchdog.timer` 覆盖回 user unit 目录
- `systemctl --user daemon-reload`
- `systemctl --user reset-failed`

#### `tools/mark42-systemd/verify.sh`

用途：
- 统一安装后 / 恢复后的最小验收入口
- 默认只读，不修改 systemd
- 输出 `PASS/WARN/FAIL`，区分“没启动”和“真故障”

示例：

```bash
tools/mark42-systemd/verify.sh
```

当前会检查：
- user systemd 会话是否可访问
- Mark42 unit 文件是否存在
- `openclaw-gateway.service` 是否已安装且 active
- `mark42-bootstrap.service` / `mark42-engine-daemon.service` / `mark42-armor-guard.service` / `mark42-watchdog.timer` 的加载与运行态
- `openclaw status` 是否可读
- `python3 scripts/mark42.py status --json` 是否可读
- `activeLoops` 与 `armor.status` 是否达到最低预期

### 当前还没到“完全交付”的原因

1. **本机已经真实 `--apply` 并跑通最小验收，但仍未覆盖“陌生机器”场景**
2. **开发模式 vs 生产守护模式的文档还在收尾**
3. **安装器目前只负责“渲染 + 写入 + daemon-reload + enable watchdog timer”**
   - 它不会替你自动启动全部 daemon
   - 启动顺序和最终验收仍建议人工确认
4. **`openclaw-gateway.service` 依赖仍然是前提**
   - 这不是 bug，但意味着宿主环境检查必须明确
5. **失败回退 / 卸载说明虽已脚本化基础版本，但陌生机器细节仍需继续收尾**
6. **preflight 已具备基础 Gateway/provider 健康探测，但还不是完整生产级深探测**
7. **现在已补“安装前自动备份 + 显式 restore 入口”，但仍不等于全自动无损回滚**
8. **现在已补统一 `verify.sh` 验收入口，但它仍是“最低验收”，不是完整生产巡检**

### 回退 / 卸载 / 故障恢复

#### 1）快速回退到本机旧 unit

如果这台机器上已经像今天这样先做过备份，可以直接退回：

```bash
backup_dir="$HOME/.config/systemd/user/mark42-backup-20260701-0849"
systemctl --user stop mark42-watchdog.timer mark42-engine-daemon.service mark42-armor-guard.service mark42-bootstrap.service
cp -f "$backup_dir"/mark42-*.service "$HOME/.config/systemd/user/"
cp -f "$backup_dir"/mark42-watchdog.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user restart mark42-bootstrap.service
systemctl --user restart mark42-engine-daemon.service
systemctl --user restart mark42-armor-guard.service
systemctl --user enable --now mark42-watchdog.timer
```

如果没有备份目录，就不要假装“可秒回退”，而是应先保留当前现场，再按 git 历史或已知稳定版本重新渲染安装。

现在也可以优先用脚本化入口：

```bash
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS --apply
```

另外，`tools/mark42-systemd/install.sh --apply` 现在会在覆盖已有 Mark42 unit 前，自动把旧 unit 备份到：

```bash
~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS/
```

至少先把“回退材料”保留下来。

#### 2）卸载 user systemd 安装

```bash
systemctl --user disable --now mark42-watchdog.timer
systemctl --user stop mark42-engine-daemon.service mark42-armor-guard.service mark42-bootstrap.service || true
rm -f ~/.config/systemd/user/mark42-bootstrap.service \
      ~/.config/systemd/user/mark42-engine-daemon.service \
      ~/.config/systemd/user/mark42-armor-guard.service \
      ~/.config/systemd/user/mark42-watchdog.service \
      ~/.config/systemd/user/mark42-watchdog.timer
systemctl --user daemon-reload
systemctl --user reset-failed
```

这只会卸载 user systemd 单元，**不会删除**：

- 工作区代码
- `~/.local/state/openclaw/mark42/` 状态数据
- `/mnt/data/openclaw/scratch` scratch 数据

如果要清状态目录，建议先备份再删，不要把卸载和清数据混成一步。

#### 3）故障恢复顺序

如果 `--apply` 后服务起不来，按这个顺序查：

1. 看 unit 状态
```bash
systemctl --user status mark42-bootstrap.service mark42-engine-daemon.service mark42-armor-guard.service mark42-watchdog.timer
```
2. 看最近日志
```bash
journalctl --user -u mark42-bootstrap.service -u mark42-engine-daemon.service -u mark42-armor-guard.service -u mark42-watchdog.service -n 80 --no-pager
```
3. 看 Mark42 总状态
```bash
python3 scripts/mark42.py status --json
```
4. 看 Gateway 依赖是否活着
```bash
systemctl --user status openclaw-gateway.service --no-pager
```
5. 看目录是否真的存在
```bash
ls -ld ~/.local/state/openclaw/mark42 ~/.local/state/openclaw/mark42/logs ~/.local/state/openclaw/mark42/engine /mnt/data/openclaw/scratch
```

本机这次真实 apply 踩到过的已知故障就是：
- `mark42-armor-guard.service`
- `status=209/STDOUT`
- 根因是 `MARK42_LOG_DIR` 不存在

所以以后如果再看到 `Failed to set up standard output`，优先先查日志目录，而不是先怀疑 Python 逻辑。

### 最小验收流程

执行 `--apply` 后，至少再验这一组：

```bash
tools/mark42-systemd/preflight.sh
systemctl --user start mark42-bootstrap.service
systemctl --user start mark42-engine-daemon.service
systemctl --user start mark42-armor-guard.service
systemctl --user enable --now mark42-watchdog.timer
systemctl --user status mark42-bootstrap.service mark42-engine-daemon.service mark42-armor-guard.service mark42-watchdog.timer
python3 scripts/mark42.py status --json
```

### 这意味着什么

当前更诚实的状态是：

- ✅ **Quick Start 已可用**：能让新接手的人先跑通、先验活
- ✅ **模板化 + 安装脚本已落地**
- ✅ **本机真实 apply 已验过**：bootstrap / engine / armor / watchdog timer 全部通过最小验收
- 🟡 **但仍未达到“陌生机器一键装好”**：因为跨机器前置条件、回退说明、模式分流还没完全写完

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
