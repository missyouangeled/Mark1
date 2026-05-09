# 2026-05-09 语音回复与 Control UI 新增能力总结

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 文档类型：功能/代码总结（截至 2026-05-09）

> 说明：本次总结聚焦今天落下并已验证的新增能力、关键代码入口、当前稳定边界，以及后续维护时需要注意的备注。当前验证环境是公司 Linux 机；其中不少代码是通用工作区代码，但本轮实际联调和验收都发生在这台机器上。

---

## 一、当前已进入“正式可用能力”的部分

### 1. 主会话直接回音频

当前确认可用的主形态是：

1. 用户继续在主会话里打字
2. 后台按需生成语音
3. 直接把音频回到主会话

这条形态已经过用户验收：

- 声音质感：通过
- 直接回音频的交互方式：通过

### 2. ChatTTS on-demand 热启动方案

当前正式主线不是“开机常驻 2GB daemon”，而是：

- 按需启动
- 热调用复用
- 空闲自动退出
- 不改 OpenClaw gateway 主配置
- 不影响主会话主体稳定性

#### 关键验证结论

- 冷启动：可用
- 热启动：明显更快
- preset 切换：可用
- 空闲自动退出：可用
- 空闲退出后自动重启：可用
- 崩溃恢复 / stale socket 恢复：可用
- stale PID 清理：已修完

### 3. 语音文件自动清理

生成出来的语音回复不再长期堆积。

当前规则：

- 超过 4 小时的生成语音自动删除
- 采用“双保险”方式：
  - 每次走语音生成链路时顺手清一次
  - 另有每 15 分钟跑一次的本地清理 cron

### 4. Control UI 隐藏内部工具过程事件

当前已在本机 Control UI 品牌补丁链中补上“隐藏内部工具过程垃圾”的前端覆盖逻辑，目标效果是：

- 主聊天界面只看正常回复
- 不再把 `tool call` / `tool output` / `sessions_yield` 之类内部过程暴露给前台

这部分已通过用户现场刷新确认：空的 `Tool` 壳子已消失。

---

## 二、今天新增/收口的关键代码入口

### A. ChatTTS 正式/稳定入口

#### 1) 正式 stable skill

- `skills/chattts-stable/SKILL.md`
- `skills/chattts-stable/scripts/chattts_stable.py`

用途：

- 当前已确认的 ChatTTS stable 主入口
- 固定 hybrid 资产链
- 支持 default / preset-1 / preset-2 / preset-3

#### 2) on-demand 语音 daemon 路径

- `tools/chattts-on-demand/chattts_daemon.py`
- `tools/chattts-on-demand/chattts-daemon.sh`
- `tools/chattts-on-demand/chattts-on-demand.sh`
- `tools/chattts-on-demand/cleanup-old-audio.sh`
- `tools/chattts-on-demand/README.md`

用途：

- 按需拉起 ChatTTS
- 热状态复用
- 空闲自动退出
- 自动清理过期 reply 音频

#### 3) 主会话可直接调用的语音回复入口

- `tools/voice-reply/chattts_voice_reply.py`
- `tools/voice-reply/voice-reply.sh`

用途：

- 给主会话/技能脚本一个稳定、可回退的调用入口
- 内部会做文本清理、长度截断、subprocess 调用、失败静默回退

### B. 语音对话 MVP（当前保留为原型/旁路工具）

- `tools/voice-chat/voice_chat_app.py`
- `tools/voice-chat/index.html`
- `tools/voice-chat/run-voice-chat.sh`
- `tools/voice-chat/README.md`

用途：

- 浏览器录音 → ASR → agent → ChatTTS → 浏览器播放 的半双工验证链路

当前定位：

- 仍保留作验证/参考工具
- 不是当前主线交互形态
- 主线已转向“主会话打字 + 后台生成语音 + 直接回主会话音频”

### C. 语音桥与 UI 修补

- `tools/nvidia-audio-bridge/bridge.py`
- `scripts/apply-openclaw-control-ui-branding.py`

用途：

- 前者承接本地 NVIDIA ASR/TTS 相关桥接优化
- 后者负责 Control UI 品牌补丁与工具事件隐藏覆盖

---

## 三、当前关键行为与边界

### 1. 总优先级

当前这条语音能力的优先级已经明确为：

1. OpenClaw 主体稳定性
2. 语音效果
3. 回复速度

因此后续默认遵循：

- 能隔离就隔离
- 能旁路验证就不碰主链路
- 不为了速度明显牺牲当前已认可的声音质感

### 2. 为什么不用默认开机常驻 2GB daemon

当前机器资源结论是：

- 能扛，但不够宽裕
- 默认开机常驻 2GB 级 daemon 会压缩 OpenClaw 主体稳定余量

因此最终拍板为：

- 不做默认开机常驻
- 改为按需启动 + 空闲自动退出

### 3. 当前已确认“正式可用”，但不是“最终完美形态”

已经可以当正式能力继续微调，但仍保留这些客观边界：

- 冷启动仍比热启动慢
- 更深的自动化集成还可以继续收口
- 但不再把它当一次性实验原型反复推倒

---

## 四、今天顺手完成的清理/收尾

### 1. 会话清理

本次按既定规则处理：

- 保留当前主会话
- 保留仍在使用的主链路
- 清理已结束的旧 dashboard / subagent / 语音测试会话
- 同步清理对应 transcript / trajectory / checkpoint 残留

### 2. 临时文件清理

已清理一批明确属于测试残留的文件，包括：

- 主会话直回音频测试样本
- on-demand 当前轮生成的临时 reply 音频
- stable verify 样本
- `tmp/voice-chat/` 里的运行期输出
- 若干 `__pycache__` 与空文件残留

保留项说明：

- 当前认可的默认模板/样本
- ChatTTS hybrid/stable 资产目录
- 仍有研究价值的脚本/README/公开参考样本
- 当前正式代码入口

---

## 五、后续维护建议

### 建议继续保留的默认工作方式

- 主会话继续作为主体
- 语音回复作为辅助能力
- 用“小步微调”的方式继续维护
- 优先做不影响主链路的改进

### 后续如果继续优化，建议顺序

1. 继续收口主会话直回音频的自动化调用
2. 在不破坏声音质感的前提下，再抠延迟
3. 若后续真有持续重度使用，再重新评估常驻 daemon 是否值得上

---

## 六、给以后接手的人一句话

**截至 2026-05-09，这条语音回复能力已经不是实验品，而是“正式可用、继续微调”的能力。当前最重要的不是大改，而是稳着往前推。**
