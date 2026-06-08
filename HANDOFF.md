# HANDOFF.md — 2026-06-08 下午

## 状态：会话大小监测补丁（session-size-watcher）✅ 已完成

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

### 清理策略（三层）
1. 其他会话的 checkpoint/trajectory/bak → 全清
2. 当前会话旧 checkpoint → 只保留最新 1 个
3. 当前会话轨迹 trajectory → 全清（OpenClaw 压缩后会重建）

### 当前状态
- 总目录：26.39 MB（INFO 级别，安全）
- 累计清理 2 次：首轮 93.62 MB（其他会话），第二轮 14.13 MB（当前会话 checkpoint+trajectory）

### 如何触发
- 自动：收到用户消息后（MEMORY.md 规则）
- 手动查看：`python3 scripts/openclaw-session-size-watcher.py --print-human`
- 强制清理：`python3 scripts/openclaw-session-size-watcher.py --force-clean`

### 关键文件
- 脚本：`scripts/openclaw-session-size-watcher.py`
- 状态：`~/.local/state/openclaw/session-size-watcher/state.json`
- 规则：`MEMORY.md` 第 133 行
- 工具描述：`TOOLS.md` + `TOOLS_INDEX.md`

### 待推进
- 索引体系试用观察（用户说"先用一阵"）
- wechat-cli 掌机接入验证
- Unity Wall H2M PaintWhite 变体修复
