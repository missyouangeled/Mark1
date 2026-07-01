# Mark42 Quick Start（2026-07-01）

> 目标：让第一次接手 Mark42 的人，在 **3~10 分钟内确认系统能跑**。
> 不承诺“一键安装到陌生机器”，只承诺“先跑起来、先验活”。

---

## 最小步骤

在仓库根目录执行：

```bash
python3 scripts/mark42.py --init
python3 scripts/mark42.py --config
python3 scripts/mark42.py armor --check
python3 scripts/mark42.py status --json
```

### 成功判据

- `--init` 不报错，能创建 state 目录
- `--config` 能打印版本、阈值、模型表
- `armor --check` 能返回 usagePercent / summary
- `status --json` 能输出完整 JSON，而不是 traceback

---

## 本机 7/01 严格审查实测基线

> ⚠️ 这一段保留的是 **2026-07-01 上午早期严格审查基线**。  
> 如果你要看**当前最新测试口径**，请以：
> - `docs/design/mark42-测试覆盖接力开发方向-20260701.md`
> - `docs/design/mark42-更新日志.md`
> 为准。

```text
316 passed, 8 skipped, 0 fail
coverage: 45.9%
```

`python3 scripts/mark42.py status --json` 严格审查实测包含：

- armor usagePercent
- engine activeLoops / loops
- heavy activeTasks
- logs rotationCount
- broker 事件数
- scratch 目录统计

另外，Armor 真压缩链路已在本机现场验收成功：

```text
🧹 会话截短成功: 1252KB → 1138KB (节省 9.1%)
```

并实际写入：
- `compactTriggered=true`
- `compactMethod=openclaw-sessions-compact`
- `compressionEffective=true`
- `bytesSaved=116087`

---

## 前台启动整套守护

```bash
python3 scripts/mark42.py assemble
```

这会：

- 拉起 `armor --guard`
- 拉起 `engine --daemon`
- 前台监护子进程
- `Ctrl+C` 时优雅收尾

适合开发/调试，不等于安装。

---

## 开发模式 vs 生产守护模式

### 开发模式
入口：

```bash
python3 scripts/mark42.py assemble
```

适合：
- 改代码后立即验证
- 前台盯日志
- 临时会话里手动停启

不要期待它替代 systemd 安装；shell 结束，它也会跟着结束。

### 生产守护模式
入口：

```bash
tools/mark42-systemd/install.sh --apply
```

适合：
- 这台机器需要长期保活
- 需要 user systemd 托管
- 需要 `mark42-watchdog.timer` 定时兜底

它的核心不是“前台看效果”，而是“把 unit 安装好并交给 systemd 托管”。

### 不要混用

以下两种都不推荐：

1. `assemble` 还在前台跑时，再手动启动 `mark42-engine-daemon.service` / `mark42-armor-guard.service`
2. systemd 已稳定托管时，又额外开一个 `python3 scripts/mark42.py assemble`

因为这样很容易造成：
- `armor --guard` / `engine --daemon` 双开
- 心跳文件与日志混杂
- 误判当前到底是谁在托管 Mark42

---

## install.sh 现在怎么用

7/01 上午这轮之后，`install.sh` 已经补出来了，但当前定位仍然是：

> **给维护者先 dry-run / 再 apply / 再人工验收的安装脚本**

当前状态：

- ✅ service 已改成模板占位符（`__MARK42_*`）
- ✅ bootstrap/watchdog 已改成环境变量驱动
- ✅ 已新增 `tools/mark42-systemd/install.sh`
- ✅ 脚本内已包含基础存在性检查与 dry-run 预览
- ✅ 已完成本机真实 `--apply` + 最小验收闭环
- ⚠️ 但还没覆盖陌生机器的一键安装场景
- ⚠️ 本机闭环成立，不等于跨机器完全闭环

### 陌生机器安装前置条件清单

先判断这台机器是否值得进入 `--apply`：

#### 必须有
- Linux + user systemd 可用（`systemctl --user status` 能跑）
- Python 3.10+
- 仓库在目标 workspace 中，且 `scripts/mark42.py` 存在
- `systemctl` / `sed` / `install` 可用
- 当前用户可写 `~/.config/systemd/user/`
- `openclaw-gateway.service` 至少要能确认安装存在，最好已经是 active

#### 最好先确认
- `openclaw` 命令可用
- `~/.openclaw/openclaw.json` 已具备可工作的 provider / API key
- 默认 state / scratch 路径是否符合宿主机策略
- 这台机器到底要走开发模式还是长期托管模式

#### 没确认前先别装
- Gateway 状态不明
- user systemd 会话环境不明
- scratch 路径策略不明
- 机器角色（开发机 / 长期托管机）不明
- 回退办法还没准备

### 先看 dry-run

```bash
tools/mark42-systemd/preflight.sh
tools/mark42-systemd/install.sh
```

## systemd 工具链标准流程（建议直接照着走）

### 1）首装流程

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

### 2）回退流程

```bash
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS --apply
tools/mark42-systemd/verify.sh
```

### 3）恢复后 / 安装后最低验收流程

```bash
tools/mark42-systemd/verify.sh
```

### 4）卸载流程

```bash
tools/mark42-systemd/uninstall.sh
tools/mark42-systemd/uninstall.sh --apply
```

### 真正写入 user systemd

```bash
tools/mark42-systemd/install.sh --apply
```

### 安装后最小验收

```bash
systemctl --user start mark42-bootstrap.service
systemctl --user start mark42-engine-daemon.service
systemctl --user start mark42-armor-guard.service
systemctl --user enable --now mark42-watchdog.timer
systemctl --user status mark42-bootstrap.service mark42-engine-daemon.service mark42-armor-guard.service mark42-watchdog.timer
python3 scripts/mark42.py status --json
```

如果只想走统一入口，也可以直接执行：

```bash
tools/mark42-systemd/verify.sh
```

### 辅助脚本

- `tools/mark42-systemd/preflight.sh`
  - 先把陌生机器前置条件跑一遍
  - `FAIL=0` 再考虑 `install.sh --apply`
  - 现已补：`openclaw status` / `openclaw health --json` / `openclaw models status --json`
  - 会输出 provider 保守摘要：`providers / providersWithOAuth / oauthProfiles / unusableProfiles / missingProvidersInUse`
- `tools/mark42-systemd/uninstall.sh`
  - 把 user systemd 卸载步骤脚本化
  - 默认 dry-run，`--apply` 才真删 unit
- `tools/mark42-systemd/restore.sh`
  - 恢复 `install.sh --apply` 前自动备份的旧 unit
  - 默认 dry-run，`--apply` 才真正覆盖回去
- `tools/mark42-systemd/verify.sh`
  - 安装后 / 恢复后的统一最小验收入口
  - 默认只读，输出 `PASS/WARN/FAIL`

---

## 这份 install.sh 还没完全闭环的地方

1. `openclaw-gateway.service` 仍是显式前提
2. 陌生机器上的回退 / 卸载细节还没完全固化
3. `preflight.sh` / `uninstall.sh` / `restore.sh` 目前是增强基础版，还没覆盖更复杂现场

### 陌生机器回退链路（当前新增）

1. `install.sh --apply` 现在会先自动备份已存在的 Mark42 unit
2. 备份目录格式：

```bash
~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS/
```

3. 如需恢复：

```bash
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS
tools/mark42-systemd/restore.sh --backup-dir ~/.config/systemd/user/mark42-backup-YYYYmmdd-HHMMSS --apply
```

4. 安装后或恢复后，统一做一次最低验收：

```bash
tools/mark42-systemd/verify.sh
```

它会区分：
- `FAIL`：关键依赖缺失 / Gateway 不可读 / unit 缺失
- `WARN`：unit 已安装但尚未启动，或运行态未到位
- `PASS`：状态面可读且已回到最低可运行状态

这条链路的意义不是宣称“自动无损回滚”，而是先把：
- 旧 unit 备份留下来
- 恢复入口标准化
- 陌生机器 apply 前的回退成本降下来

### 本机 7/01 真实 apply 结果

- `mark42-bootstrap.service` → `active (exited)`
- `mark42-engine-daemon.service` → `active (running)`
- `mark42-armor-guard.service` → `active (running)`
- `mark42-watchdog.timer` → `active (waiting)`
- `python3 scripts/mark42.py status --json` 正常
- `activeLoops=4`

### 回退 / 卸载 / 故障恢复（维护者最小版）

#### 回退
- 若 apply 前已备份旧 unit，先停当前 unit，再把备份文件拷回 `~/.config/systemd/user/`
- 然后执行：
  - `systemctl --user daemon-reload`
  - `systemctl --user restart mark42-bootstrap.service`
  - `systemctl --user restart mark42-engine-daemon.service`
  - `systemctl --user restart mark42-armor-guard.service`
  - `systemctl --user enable --now mark42-watchdog.timer`

#### 卸载
- 先执行：
  - `systemctl --user disable --now mark42-watchdog.timer`
  - `systemctl --user stop mark42-engine-daemon.service mark42-armor-guard.service mark42-bootstrap.service`
- 再删除：
  - `~/.config/systemd/user/mark42-bootstrap.service`
  - `~/.config/systemd/user/mark42-engine-daemon.service`
  - `~/.config/systemd/user/mark42-armor-guard.service`
  - `~/.config/systemd/user/mark42-watchdog.service`
  - `~/.config/systemd/user/mark42-watchdog.timer`
- 最后：
  - `systemctl --user daemon-reload`
  - `systemctl --user reset-failed`

#### 故障恢复
按这个顺序查：
1. `systemctl --user status ...`
2. `journalctl --user -u ... -n 80 --no-pager`
3. `python3 scripts/mark42.py status --json`
4. `systemctl --user status openclaw-gateway.service --no-pager`
5. `ls -ld ~/.local/state/openclaw/mark42 ~/.local/state/openclaw/mark42/logs ~/.local/state/openclaw/mark42/engine /mnt/data/openclaw/scratch`

本机这次已知故障样例：
- `status=209/STDOUT`
- `Failed to set up standard output`
- 优先检查 `MARK42_LOG_DIR` 是否存在

#### 卸载
- 先看：`tools/mark42-systemd/uninstall.sh`
- 真执行：`tools/mark42-systemd/uninstall.sh --apply`
- 默认只移除 user systemd unit，不删 state / scratch 数据

---

## 建议阅读顺序

1. `README.md`
2. `docs/design/mark42-商品化路线图.md`
3. `docs/design/mark42-更新日志.md`
4. `scripts/mark42.py --help`
5. `python3 -m pytest scripts/tests/ --no-cov -q`
