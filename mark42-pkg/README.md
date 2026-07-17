# Mark42

模块化智能铠甲系统 - 为 [OpenClaw](https://github.com/nicepkg/openclaw) 提供上下文守护与循环引擎。

## 功能

- **上下文铠甲 (Armor)**: 实时监测上下文使用率，超阈值自动 LLM 压缩 + 预警
- **循环引擎 (Engine)**: 定时执行注册的循环任务（健康检查、记忆索引、模型回退等）
- **重型战甲 (Heavy)**: 大型异步任务队列与执行
- **日志轮替**: 自动轮替 OpenClaw 会话与 broker 日志
- **意识协议**: 读取协议、心跳守护、记忆快照

## 安装

### 一键安装

```bash
curl -sSL https://raw.githubusercontent.com/your-repo/mark42/main/install.sh | bash
```

### 手动安装

```bash
git clone https://github.com/your-repo/mark42.git
cd mark42
pip install .
mark42 install   # 安装 systemd 服务
```

## 使用

```bash
mark42 status          # 查看系统状态
mark42 armor --check   # 手动检查上下文
mark42 armor --guard   # 启动守护模式
mark42 engine start    # 启动循环引擎
mark42 --help          # 查看所有命令
```

## 依赖

- Python >= 3.10
- OpenClaw (已安装并配置)
- Linux (systemd)

## 配置

Mark42 从 `~/.openclaw/openclaw.json` 读取 OpenClaw 配置（API key、模型等）。
自身配置存储在 `~/.local/state/openclaw/mark42/config.json`。

## License

MIT
