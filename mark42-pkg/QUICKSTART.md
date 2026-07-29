# Mark42 快速上手（5 分钟）

> 如果你只想赶紧跑起来，看这一篇就够了。

## 前置条件

- Python 3.10+
- OpenClaw 已安装并正常运行
- Linux 系统（已测试 Ubuntu / Debian）

## 第 1 步：安装（1 分钟）

```bash
cd ~/.openclaw/workspace/mark42-pkg
bash install.sh
```

或者手动安装：

```bash
cd ~/.openclaw/workspace/mark42-pkg
pip install -e . --break-system-packages
```

验证：

```bash
mark42 --version
# 预期输出: Mark42 v2.7.0
```

## 第 2 步：初始化配置（1 分钟）

```bash
mark42 --init
```

向导会问你 5 个问题（按回车用默认值即可）：

1. **路径配置**：工作区在哪、配置文件在哪
2. **上下文阈值**：warn(70%) / alert(85%) / crit(95%)
3. **LLM 模型**：分析和压缩用什么模型
4. **守护进程**：扫描间隔、是否自动压缩
5. **日志级别**：INFO 即可

配置文件生成在 `~/.config/mark42/config.toml`。

## 第 3 步：查看状态（1 分钟）

```bash
mark42 --config
```

预期输出类似：

```
⚙️ Mark42 配置
  版本: 2.7.0
  上下文窗口: 128K
  阈值: warn=70% alert=85% crit=95%
  模型: doubao-seed-2.0-pro
  ...
```

## 第 4 步：检查上下文健康（1 分钟）

```bash
mark42 armor --check
```

这会检查 OpenClaw 当前上下文使用率，告诉你是否需要压缩。

## 第 5 步：启动守护（1 分钟）

如果你用了 systemd：

```bash
systemctl --user enable --now mark42-armor-guard
systemctl --user enable --now mark42-engine-daemon
```

如果没用 systemd，可以手动跑：

```bash
mark42 armor --guard        # 前台跑上下文守护
mark42 engine --daemon      # 前台跑循环引擎
```

## 常见问题

**Q: `pip install` 报 PEP 668 错误？**

加 `--break-system-packages` 参数，或用虚拟环境。

**Q: `mark42` 命令找不到？**

```bash
pip install -e . --break-system-packages  # 重新安装
hash -r  # 刷新 shell 命令缓存
```

**Q: `mark42 --init` 说配置已存在？**

```bash
rm ~/.config/mark42/config.toml  # 删除旧配置
mark42 --init                     # 重新初始化
```

**Q: 上下文检查报 "无法连接 OpenClaw"？**

确保 OpenClaw Gateway 正在运行：

```bash
openclaw status
```

---

下一步：完整教程请看 [TUTORIAL.md](TUTORIAL.md)
