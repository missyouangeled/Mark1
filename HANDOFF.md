# HANDOFF.md — 2026-06-08 下午

## 状态：会话大小监测补丁（session-size-watcher）✅ 已完成 v2

### 做了什么
新增 `scripts/openclaw-session-size-watcher.py` — 会话文件大小监测与自动修复。

### 工作机制
- **事件驱动**：收到用户消息后，以 `exec(background=true)` 后台运行
- **门控去重**：`--gate-seconds 60`，60 秒内不重复实扫
- **无 resident 进程**：不是 systemd timer，跑完即退

### 阈值（总目录）
- INFO：< 40MB（静默记录）
- CRITICAL：40～60MB（清理旧数据）
- FORCE_CLEAN：> 60MB（大扫除）

### 清理策略（三层，v2 改进）
1. 其他会话的 checkpoint/trajectory/bak → 全清
2. 当前会话旧 checkpoint → 只保留最新 1 个
3. 当前会话 trajectory → **仅当 mtime 比主 jsonl 早 10 分钟以上时删除**（防止误删活跃 trajectory）

### 告警通道（v2 新增）
- 清理错误、检测链路失效、阈值异常 → 写入 `~/.local/state/openclaw/session-size-watcher/alerts.json`
- 手动查看：`python3 scripts/openclaw-session-size-watcher.py --check-alerts`
- 启动时检查：BOOT.md 第 6 步（每次 gateway 重启自动跑）
- 标记已读：`python3 scripts/openclaw-session-size-watcher.py --mark-read`

### 跨模型可靠性（v2 双保险）
1. **主路径**：MEMORY.md 行为规则 → 模型读到后自觉执行
2. **兜底路径**：BOOT.md 启动时跑 `--check-alerts` → 不依赖模型合规性，gateway 重启时强制执行

### 当前状态
- 总目录：27.90 MB（INFO 级别，安全）
- 累计清理 2 次：首轮 93.62 MB（其他会话），第二轮 14.13 MB（当前会话 checkpoint）
- 无未读告警

### 常用命令
```bash
# 查看状态
python3 scripts/openclaw-session-size-watcher.py --print-human

# 检查告警
python3 scripts/openclaw-session-size-watcher.py --check-alerts

# 强制清理
python3 scripts/openclaw-session-size-watcher.py --force-clean
```

### 关键文件
- 脚本：`scripts/openclaw-session-size-watcher.py`
- 状态：`~/.local/state/openclaw/session-size-watcher/state.json` + `alerts.json`
- 规则：`MEMORY.md` 第 133 行
- 启动钩子：`BOOT.md` 第 6 步
- 工具描述：`TOOLS.md` + `TOOLS_INDEX.md`

### 待推进
- 索引体系试用观察
- wechat-cli 掌机接入验证
- Unity Wall H2M PaintWhite 变体修复
