# Mark42 文档导航

> 所有文档的统一入口。

## 快速开始

| 你想做什么 | 看哪 |
|------------|------|
| 5 分钟跑起来 | [QUICKSTART.md](QUICKSTART.md) |
| 从零完整学习 | [TUTORIAL.md](TUTORIAL.md) |
| 了解架构设计 | [README.md](README.md) |
| 查看配置说明 | [CONFIG-GUIDE.md](docs/CONFIG-GUIDE.md) |

## 命令速查

### 基础命令

| 命令 | 说明 |
|------|------|
| `mark42 --version` | 显示版本号 |
| `mark42 --init` | 交互式配置向导 |
| `mark42 --config` | 查看当前配置 |
| `mark42 status` | 系统状态总览 |

### 上下文铠甲

| 命令 | 说明 |
|------|------|
| `mark42 armor --check` | 检查上下文使用率 |
| `mark42 armor --compress --dry-run` | 预览压缩 |
| `mark42 armor --compress` | 执行压缩 |
| `mark42 armor --guard` | 启动守护（前台） |

### 循环引擎

| 命令 | 说明 |
|------|------|
| `mark42 engine --daemon` | 启动引擎（前台） |
| `mark42 engine --templates` | 查看可用模板 |
| `mark42 engine --start --task "名称" --interval 300` | 启动定时任务 |
| `mark42 engine --kill loop-name` | 停止任务 |

### 日志 / 诊断

| 命令 | 说明 |
|------|------|
| `mark42 logs --status` | 日志状态 |
| `mark42 logs --rotate` | 执行日志轮替 |
| `mark42 --tune-compaction` | 压缩诊断 |
| `mark42 context-safety status` | 安全基线检查 |

### 重型战甲

| 命令 | 说明 |
|------|------|
| `mark42 heavy --preflight /path` | 大工程预检 |
| `mark42 heavy --start /path --task-name my` | 启动 |
| `mark42 heavy --finish --task-name my` | 完成 |
| `mark42 heavy --cleanup --task-name my` | 清理 |

## 配置速查

配置文件：`~/.config/mark42/config.toml`

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `thresholds.warn` | 70 | 预警阈值 (%) |
| `thresholds.alert` | 85 | 告警阈值 (%) |
| `thresholds.crit` | 95 | 紧急阈值 (%) |
| `daemon.scan_interval` | 30 | 引擎扫描间隔 (秒) |
| `daemon.armor_check_interval` | 300 | 铠甲检查间隔 (秒) |
| `daemon.auto_armor_compress` | true | 自动压缩 |
| `logging.level` | INFO | 日志级别 |

## systemd 速查

```bash
# 启动
systemctl --user start mark42-armor-guard mark42-engine-daemon

# 停止
systemctl --user stop mark42-armor-guard mark42-engine-daemon

# 开机自启
systemctl --user enable mark42-armor-guard mark42-engine-daemon

# 查看状态
systemctl --user status mark42-armor-guard

# 查看日志
journalctl --user -u mark42-armor-guard -f
```

## 学习路径推荐

**新手**：QUICKSTART → TUTORIAL → 实操

**有经验的开发者**：README → CONFIG-GUIDE → 架构设计文档

**运维人员**：TUTORIAL 第 4-6 章 → systemd 配置 → 日志轮替

## 文档目录

```
mark42-pkg/
├── QUICKSTART.md        # 5 分钟快速上手
├── TUTORIAL.md          # 完整教程
├── README.md            # 项目介绍 + 架构
├── INDEX.md             # 本文件（导航）
├── CHANGELOG.md         # 更新日志
├── ARCHITECTURE.md      # 架构设计
├── docs/
│   └── CONFIG-GUIDE.md  # 配置详解
├── install.sh           # 一键安装脚本
├── pyproject.toml        # Python 包配置
└── mark42/              # 源代码
    ├── cli/             # 命令行接口
    ├── audit/           # 审计系统
    ├── plugins/         # 插件
    ├── interfaces/      # 接口定义
    ├── templates/       # 配置模板
    └── systemd/         # systemd 模板
```
