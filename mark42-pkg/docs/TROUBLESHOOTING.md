# Mark42 故障排查指南

本文档收集常见问题的症状、原因和解决方法。如果你遇到的问题不在此列，请提交 [Issue](https://github.com/missyouangeled/Mark1/issues)。

> **常用路径速查**
> - 配置：`~/.config/mark42/`
> - 状态：`~/.local/state/openclaw/mark42/`
> - 日志：`~/.local/state/openclaw/mark42/logs/`
> - 数据盘（可选）：`/mnt/data/openclaw/`，可用 `MARK42_DATA_MOUNT` 覆盖

---

## 安装问题

### 问题 1：安装失败

**症状**：`bash install.sh` 或 `pip install -e .` 报错，或编译依赖失败。

**可能原因**
- Python 版本低于 3.10
- pip 版本过旧
- PyPI 源网络问题

**解决方法**
```bash
python3 --version              # 必须 >= 3.10
pip3 install --upgrade pip
# 国内网络可用镜像源
pip3 install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

### 问题 2：mark42 命令找不到

**症状**：`mark42: command not found`

**可能原因**：pip 用户级安装路径不在 `PATH` 中。

**解决方法**
```bash
# 方式一：把用户级 bin 加进 PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 方式二：直接用模块调用
python3 -m mark42 --version
```

---

## 配置问题

### 问题 3：配置未初始化 / 找不到配置

**症状**：首次运行报配置缺失，或行为不符合预期。

**解决方法**
```bash
# 初始化配置
mark42 --init

# 查看当前配置
mark42 --config

# 检查配置目录
ls -la ~/.config/mark42/
```

---

## LLM Provider 连接问题

### 问题 4：LLM 调用失败 / 超时

**症状**：压缩时报 provider 连接失败、超时或鉴权错误。

**可能原因**
- API Key 未配置或错误
- 网络（代理 / 防火墙）
- Provider 服务不可用或额度不足

**解决方法**
```bash
# Mark42 的 LLM 配置见 ~/.config/mark42/model.yaml
# 不配置时会降级到 stub runtime（回声模式，不真正调用 LLM）
cat ~/.config/mark42/model.yaml

# 若需走代理
export HTTPS_PROXY=http://your-proxy:port

# 用 dry-run 先验证流程（不真正压缩）
mark42 armor --dry-run
```

> 说明：Mark42 的 LLM provider 走 fallback 链，全部失败时降级到 `stub`，**不会崩战甲**。若压缩效果不对，先确认 model.yaml 的 runtime 是 `api`/`ollama` 而非默认 `stub`。

---

## 压缩相关问题

### 问题 5：压缩不生效 / 被跳过

**症状**：`mark42 armor --compress` 后 usage 没下降，或日志显示 skip。

**可能原因**
- 当前使用率低于告警阈值（未达触发条件）
- 平台探测期内 OpenClaw 自己已 compact
- compact 锁被占用

**解决方法**
```bash
# 先看健康度和使用率
mark42 armor --check

# 预览压缩会做什么（不实际执行）
mark42 armor --dry-run

# 查看压缩诊断（token 感知 + 质量探针 + 降解检测）
mark42 compaction --token-aware --probe --drift-check
```

---

### 问题 6：compact 锁冲突

**症状**：日志出现 `compact 锁被占用` / `skip-locked`。

**可能原因**：上一次 compact 进程异常退出，锁文件残留；或确有另一进程在跑。

**解决方法**
```bash
# 锁文件位置
ls -la ~/.local/state/openclaw/mark42/armor/compact.lock

# 确认无活跃进程后，手动清理残留锁（锁有 TTL，超时会自动失效）
ps aux | grep mark42
rm -f ~/.local/state/openclaw/mark42/armor/compact.lock
```

---

## 权限问题

### 问题 7：权限被拒绝

**症状**：`PermissionError: [Errno 13] Permission denied`

**可能原因**：曾用 `sudo` 运行，导致状态目录里生成了 root 拥有的文件。

**解决方法**
```bash
# 查找 root 拥有的文件
find ~/.config/mark42 ~/.local/state/openclaw -user root 2>/dev/null

# 修复所有者
chown -R $USER:$USER ~/.config/mark42/ ~/.local/state/openclaw/
```

---

## 系统状态排查

遇到任何异常，先跑一屏状态聚合：

```bash
mark42 status            # 一屏聚合系统状态
mark42 status --json     # JSON 格式（便于脚本处理）
mark42 status --verbose  # 详细信息
```

日志在 `~/.local/state/openclaw/mark42/logs/`，可 `mark42 logs` 管理。

---

## 还是没解决？

- 查阅 [CONFIG-GUIDE.md](docs/CONFIG-GUIDE.md) 了解完整配置项
- 在 [Discussions](https://github.com/missyouangeled/Mark1/discussions) 提问
- 提交 [Issue](https://github.com/missyouangeled/Mark1/issues)，附上 `mark42 status --json` 输出和相关日志
