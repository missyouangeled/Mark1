# Mark42 完整教程

> 从零开始，一步一步学会用 Mark42 守护你的 OpenClaw 上下文。

## 目录

1. [Mark42 是什么](#1-mark42-是什么)
2. [安装全流程](#2-安装全流程)
3. [配置详解](#3-配置详解)
4. [日常使用](#4-日常使用)
5. [进阶功能](#5-进阶功能)
6. [故障排查](#6-故障排查)
7. [FAQ](#7-faq)

---

## 1. Mark42 是什么

Mark42 是一个「上下文铠甲」系统，专门为 OpenClaw 设计。

**它解决什么问题？** OpenClaw 聊天时间长了，上下文会撑满，导致模型"失忆"或崩溃。Mark42 自动监控上下文使用率，在快满时自动压缩，保持对话连贯。

**核心能力：**
- 📊 上下文监控：实时跟踪 token 使用量
- 🗜️ 智能压缩：快满时自动触发 LLM 压缩
- 🛡️ 审计系统：压缩后自动检查信息丢失
- 🔄 循环引擎：支持定时任务（日志轮替、健康检查等）
- 💪 重型战甲：大工程检测和自动化处理

**架构概览：**

```
OpenClaw ←→ Mark42
              │
    ┌─────────┼─────────┐
    │         │         │
  上下文铠甲  循环引擎  重型战甲
    │         │         │
  监控+压缩  定时任务  大工程
    │
  审计系统
  (压缩后检查)
```

---

## 2. 安装全流程

### 2.1 检查前置条件

```bash
python3 --version    # 需要 3.10+
openclaw status      # OpenClaw 需要正常运行
```

### 2.2 一键安装

```bash
cd ~/.openclaw/workspace/mark42-pkg
bash install.sh
```

install.sh 会：
1. 检查 Python 版本
2. 安装 mark42 包（pip install -e .）
3. 安装 systemd 服务模板
4. 提示下一步操作

### 2.3 手动安装

如果 install.sh 不工作：

```bash
cd ~/.openclaw/workspace/mark42-pkg
pip install -e . --break-system-packages
```

### 2.4 验证安装

```bash
mark42 --version
# Mark42 v2.8.1

python3 -c "import mark42; print('OK')"
# OK
```

---

## 3. 配置详解

### 3.1 交互式配置向导

```bash
mark42 --init
```

向导分 5 步，每步按回车用默认值：

**步骤 1：路径配置**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| workspace | ~/.openclaw/workspace | OpenClaw 工作区路径 |
| openclaw_config | ~/.openclaw/openclaw.json | OpenClaw 配置文件 |
| scratch | ~/.local/state/openclaw/scratch | 临时文件目录 |

> 💡 有数据盘的话，scratch 可以指到数据盘，减少 SSD 写入。

**步骤 2：上下文阈值**

| 级别 | 默认值 | 触发行为 |
|------|--------|----------|
| 🟡 warn | 70% | 发送预警 + 自动 LLM 压缩 |
| 🟠 alert | 85% | 强制再次压缩 |
| 🔴 crit | 95% | 紧急处理 |

> 💡 如果你的上下文窗口比较小（如 32K），可以调高到 80/90/97，减少频繁压缩。

**步骤 3：LLM 模型**

分析和压缩用的模型，API key 从 `openclaw.json` 读，这里只选模型名。

默认 `doubao-seed-2.0-pro`，也可以用 `glm-5.2` 或其他。

**步骤 4：守护进程**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| scan_interval | 30 秒 | 引擎扫描间隔 |
| armor_check_interval | 300 秒 | 铠甲检查间隔 |
| auto_armor_compress | true | 自动触发压缩 |
| auto_task_watch | true | 自动监控大任务 |

**步骤 5：日志级别**

- DEBUG：排错时用，输出最详细
- INFO：日常用，推荐
- WARNING：只看警告
- ERROR：只看错误

### 3.2 手动编辑配置

配置文件在 `~/.config/mark42/config.toml`，TOML 格式：

```toml
[thresholds]
warn  = 70
alert = 85
crit  = 95

[models.llmCompress]
model = "doubao-seed-2.0-pro"
```

改完重启生效：

```bash
systemctl --user restart mark42-armor-guard
```

### 3.3 查看当前配置

```bash
mark42 --config
```

---

## 4. 日常使用

### 4.1 启动 / 停止

用 systemd：

```bash
# 启动
systemctl --user start mark42-armor-guard
systemctl --user start mark42-engine-daemon

# 停止
systemctl --user stop mark42-armor-guard
systemctl --user stop mark42-engine-daemon

# 查看状态
systemctl --user status mark42-armor-guard
```

前台手动运行：

```bash
mark42 armor --guard     # 上下文守护
mark42 engine --daemon   # 循环引擎
```

### 4.2 查看状态

```bash
mark42 status
```

输出包括：上下文使用率、上次压缩时间、审计结果、引擎任务列表。

### 4.3 上下文检查

```bash
mark42 armor --check
```

手动触发一次上下文检查，不启动守护进程。

### 4.4 手动压缩

```bash
# 预览（dry-run，不实际执行）
mark42 armor --compress --dry-run

# 实际执行
mark42 armor --compress
```

### 4.5 健康监控

```bash
mark42 status
```

包含内存、磁盘、CPU 健康检查。

### 4.6 成本报告

```bash
mark42 cost
```

查看 LLM 调用次数和费用统计。

---

## 5. 进阶功能

### 5.1 自定义 Loop 任务

```bash
# 启动一个监控任务
mark42 engine --start --task "监控上下文" --interval 300

# 查看运行中的任务
mark42 engine --daemon

# 停止任务
mark42 engine --kill loop-name
```

### 5.2 ArcLock（上下文锁定）

防止关键对话被压缩：

```bash
mark42 arclock --lock "重要决策讨论"
```

### 5.3 日志轮替

```bash
# 查看日志状态
mark42 logs --status

# 执行轮替（清理旧日志）
mark42 logs --rotate
```

### 5.4 上下文安全体检

```bash
# 查看当前安全基线
mark42 context-safety status

# 应用安全基线
mark42 context-safety apply

# 验收（检查是否生效）
mark42 context-safety verify
```

### 5.5 调优压缩

```bash
# 诊断当前压缩配置
mark42 --tune-compaction

# 实际应用调优
mark42 --tune-compaction --apply
```

---

## 6. 故障排查

### 6.1 Gateway 无法启动

**症状**：`openclaw status` 显示 Gateway 未运行

**排查**：
```bash
# 查看日志
journalctl --user -u openclaw-gateway --since "10 min ago"

# 常见原因
# 1. openclaw.json 配置错误
openclaw config validate

# 2. 端口被占用
ss -tlnp | grep 18789
```

### 6.2 压缩不生效

**症状**：上下文已经超过阈值但没有自动压缩

**排查**：
```bash
# 1. 检查守护进程是否运行
systemctl --user status mark42-armor-guard

# 2. 手动检查
mark42 armor --check

# 3. 手动压缩试一下
mark42 armor --compress
```

### 6.3 测试失败

**症状**：pytest 报错

```bash
# 单独运行出错的测试文件
cd ~/.openclaw/workspace
python -m pytest scripts/tests/unit/test_xxx.py -v

# 不要一次跑全部（可能触发 Bad file descriptor）
```

### 6.4 mark42 命令找不到

```bash
# 重新安装
cd ~/.openclaw/workspace/mark42-pkg
pip install -e . --break-system-packages

# 刷新命令缓存
hash -r
```

---

## 7. FAQ

**Q: Mark42 会修改我的 OpenClaw 配置吗？**

不会直接修改。Mark42 读取 `openclaw.json` 获取 API key，但不会写入。唯一例外是 `context-safety apply` 命令，它会在你确认后修改安全相关配置。

**Q: 压缩会丢失信息吗？**

Mark42 有审计系统，每次压缩后自动检查信息保留率。如果发现严重信息丢失，会记录告警。你可以用 `mark42 armor --check` 查看最近的审计结果。

**Q: 可以不用 systemd 吗？**

可以。用 `mark42 armor --guard` 和 `mark42 engine --daemon` 前台运行。但 systemd 方式更稳定（自动重启、开机自启）。

**Q: 支持哪些 LLM 模型？**

任何 OpenClaw 支持的模型都行。推荐 `doubao-seed-2.0-pro`（性价比高）或 `glm-5.2`。

**Q: 如何卸载？**

```bash
pip uninstall mark42 --break-system-packages
systemctl --user disable --now mark42-armor-guard mark42-engine-daemon
rm -rf ~/.config/mark42/
```

---

*更多技术细节请看 [README.md](README.md) 和 [docs/design/](../docs/design/) 目录*
